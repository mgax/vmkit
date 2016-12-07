#!/usr/bin/env python3

from pathlib import Path
import argparse
from tempfile import TemporaryDirectory
import subprocess
from contextlib import contextmanager

REPO = Path(__file__).resolve().parent

def run(cmdargs, stdin_data=b'', **kwargs):
    kwargs.setdefault('stdin', subprocess.PIPE)
    p = subprocess.Popen([str(a) for a in cmdargs], **kwargs)
    p.communicate(stdin_data)
    if p.returncode != 0:
        raise RuntimeError("Subprocess failed: {!r}".format(cmdargs))

def patchiso(orig, iso):
    with TemporaryDirectory() as tmp:
        dist = Path(tmp) / 'dist'

        print('copying contents of', orig, 'to', dist)
        run(['cp', '-a', orig, dist])

        patch_path = REPO / 'console-ttyS0.patch'
        print('applying patch', patch_path)
        with patch_path.open('rb') as patch:
            run(['patch', '-d', dist, '-p1'], stdin=patch)

        initrd_gz = dist / 'install.amd' / 'initrd.gz'
        initrd = dist / 'install.amd' / 'initrd'
        print('patching', initrd_gz)
        run(['gunzip', initrd_gz])
        run(['cpio', '-o', '-H', 'newc', '-A', '-F', initrd],
            cwd=str(REPO), stdin_data=b'preseed.cfg\n')
        run(['gzip', initrd])

        run(['cp', REPO / 'finish_install.sh', dist / 'finish_install.sh'])

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

@contextmanager
def qemu(hda, args=[], pipe_stdin=False, pipe_stdout=False):
    base_args = [
        'qemu-system-x86_64', '-nographic', '-no-reboot',
        '-enable-kvm', '-m', '256',
        '-hda', str(hda),
    ]

    vm = subprocess.Popen(
        base_args + args,
        stdin=subprocess.PIPE if pipe_stdin else None,
        stdout=subprocess.DEVNULL if pipe_stdout else None,
    )
    try:
        yield vm
    finally:
        vm.wait()

def install(target, iso):
    target.mkdir()
    hda = target / 'hd.qcow2'
    run(['qemu-img', 'create', '-f', 'qcow2', hda, '4G'])
    with qemu(hda, args=['-cdrom', str(iso), '-boot', 'd']) as vm:
        pass

def console(target):
    with qemu(target / 'hd.qcow2') as vm:
        pass

def ssh(target, t, extra_args):
    import random, socket
    from time import time, sleep
    port = random.randint(10000, 65000)
    qemu_args = [
        '-net', 'nic',
        '-net', 'user,hostfwd=tcp:127.0.0.1:{}-:22'.format(port),
    ]
    hda = target / 'hd.qcow2'
    with qemu(hda, args=qemu_args, pipe_stdin=True, pipe_stdout=True) as vm:
        t0 = time()
        timeout = 10 # seconds
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
            'ssh', 'root@localhost', '-p', str(port),
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'LogLevel ERROR',
        ]
        if t:
            ssh_args += ['-t']
        if extra_args:
            ssh_args += ['/usr/local/sbin/run_and_poweroff'] + extra_args
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
    parser.add_argument('-t', action='store_true')
    parser.add_argument('args', nargs=argparse.REMAINDER)
    parser.set_defaults(handler=lambda o: ssh(Path(o.vm), o.t, o.args))

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
