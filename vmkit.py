#!/usr/bin/env python3

import sys
from pathlib import Path
import argparse
from io import BytesIO
from tempfile import TemporaryDirectory
import subprocess

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

def run_qemu(iso):
    from godfather import VM, repl

    vm = VM()

    @vm.stdout_handlers.append
    def handle_stdout(data):
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

    args = [
        'qemu-system-x86_64', '-nographic', '-no-reboot',
        '-enable-kvm', '-m', '256',
        '-cdrom', str(iso), '-boot', 'd',
    ]
    vm.start(args)

    try:
        repl(vm=vm)
    finally:
        vm.kill()

def install(target, iso):
    target.mkdir()
    hda = target / 'hd.qcow2'
    run(['qemu-img', 'create', '-f', 'qcow2', hda, '4G'])
    run_qemu(iso)

def parser_for_patchiso(parser):
    parser.add_argument('orig')
    parser.add_argument('-o', '--output')
    parser.set_defaults(handler=lambda o: patchiso(o.orig, o.output))

def parser_for_install(parser):
    parser.add_argument('target')
    parser.add_argument('--iso')
    parser.set_defaults(handler=lambda o: install(Path(o.target), o.iso))

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers()

    parser_for_patchiso(commands.add_parser('patchiso'))
    parser_for_install(commands.add_parser('install'))

    options = parser.parse_args()
    options.handler(options)

if __name__ == '__main__':
    main()
