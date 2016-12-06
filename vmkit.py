#!/usr/bin/env python3

import sys
from pathlib import Path
import argparse
from io import BytesIO
from tempfile import TemporaryDirectory
import subprocess
from contextlib import contextmanager

def run(cmdargs, stdin_data=b'', **kwargs):
    kwargs.setdefault('stdin', subprocess.PIPE)
    p = subprocess.Popen([str(a) for a in cmdargs], **kwargs)
    p.communicate(stdin_data)
    if p.returncode != 0:
        raise RuntimeError("Subprocess failed: {!r}".format(cmdargs))

def patchiso(orig, iso):
    repo = Path(__file__).resolve().parent

    with TemporaryDirectory() as tmp:
        dist = Path(tmp) / 'dist'

        print('copying contents of', orig, 'to', dist)
        run(['cp', '-a', orig, dist])

        patch_path = repo / 'console-ttyS0.patch'
        print('applying patch', patch_path)
        with patch_path.open('rb') as patch:
            run(['patch', '-d', dist, '-p1'], stdin=patch)

        initrd_gz = dist / 'install.amd' / 'initrd.gz'
        initrd = dist / 'install.amd' / 'initrd'
        print('patching', initrd_gz)
        run(['gunzip', initrd_gz])
        run(['cpio', '-o', '-H', 'newc', '-A', '-F', initrd],
            cwd=str(repo), stdin_data=b'preseed.cfg\n')
        run(['gzip', initrd])

        run(['cp', repo / 'finish_install.sh', dist / 'finish_install.sh'])

        print('creating ISO image', iso)
        run([
          'xorriso', '-as', 'mkisofs',
          '-r', '-J', '-joliet-long',
          '-no-emul-boot',
          '-boot-load-size', '4',
          '-boot-info-table',
          '-b', 'isolinux/isolinux.bin',
          '-c', 'isolinux/boot.cat',
          '-o', iso,
          dist,
        ])

def echo_stdout(vm):
    @vm.stdout_handlers.append
    def handle_stdout(data):
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

@contextmanager
def qemu(hda, args=[], pipe_stdin=False):
    from godfather import VM

    vm = VM()

    base_args = [
        'qemu-system-x86_64', '-nographic', '-no-reboot',
        '-enable-kvm', '-m', '256',
        '-hda', str(hda),
    ]
    vm.start(base_args + args, pipe_stdin)

    try:
        yield vm
    finally:
        vm.wait()

def install(target, iso):
    target.mkdir()
    hda = target / 'hd.qcow2'
    run(['qemu-img', 'create', '-f', 'qcow2', hda, '4G'])
    with qemu(hda, args=['-cdrom', str(iso), '-boot', 'd']) as vm:
        echo_stdout(vm)

def console(target):
    with qemu(target / 'hd.qcow2') as vm:
        echo_stdout(vm)

def ssh(target, timeout):
    import random, socket
    from time import time, sleep
    port = random.randint(10000, 65000)
    qemu_args = [
        '-net', 'nic',
        '-net', 'user,hostfwd=tcp:127.0.0.1:{}-:22'.format(port),
    ]
    with qemu(target / 'hd.qcow2', args=qemu_args, pipe_stdin=True) as vm:
        t0 = time()
        while True:
            if time() - t0 > timeout:
                vm.kill()
                raise RuntimeError("waited {} seconds for the port to open"
                    .format(timeout))
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(('127.0.0.1', port))
                s.close()
            except ConnectionRefusedError:
                sleep(.3)
            else:
                break
        ssh_args = [
            'ssh', 'localhost', '-p', str(port),
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
        ]
        subprocess.Popen(ssh_args).wait()

def parser_for_patchiso(parser):
    parser.add_argument('orig')
    parser.add_argument('-o', '--output', required=True)
    parser.set_defaults(handler=lambda o: patchiso(o.orig, o.output))

def parser_for_install(parser):
    parser.add_argument('target')
    parser.add_argument('--iso')
    parser.set_defaults(handler=lambda o: install(Path(o.target), o.iso))

def parser_for_console(parser):
    parser.add_argument('--vm', default='.')
    parser.set_defaults(handler=lambda o: console(Path(o.vm)))

def parser_for_ssh(parser):
    parser.add_argument('--vm', default='.')
    parser.add_argument('--timeout', default=10)
    parser.set_defaults(handler=lambda o: ssh(Path(o.vm), o.timeout))

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers()

    parser_for_patchiso(commands.add_parser('patchiso'))
    parser_for_install(commands.add_parser('install'))
    parser_for_console(commands.add_parser('console'))
    parser_for_ssh(commands.add_parser('ssh'))

    options = parser.parse_args()
    handler = getattr(options, 'handler', lambda _: parser.print_help())
    handler(options)


if __name__ == '__main__':
    main()
