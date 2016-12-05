#!/usr/bin/env python3

import re
import subprocess
import threading
import code

def repl(**locals):
    from pprint import pprint
    locals['pp'] = pprint
    code.InteractiveConsole(locals).interact()

def thread(target, *args, **kwargs):
    t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    t.start()

class VM:
    def __init__(self):
        self.stdout_handlers = []

    def start(self, args, pipe_stdin=False):
        options = dict(stdout=subprocess.PIPE, bufsize=0)
        if pipe_stdin:
            options['stdin'] = subprocess.PIPE
        self.p = subprocess.Popen(args, **options)
        threading.Thread(target=self._stdout_thread, daemon=True).start()

    def _stdout_thread(self):
        while True:
            data = self.p.stdout.read(1024)
            if not data:
                return
            for handler in self.stdout_handlers:
                handler(data)

    def kbd(self, data):
        self.p.stdin.write(data)
        self.p.stdin.flush()

    def kill(self):
        self.p.kill()
        return self.wait()

    def wait(self):
        self.p.wait()
        print('vm has exited')

class Watcher:
    def __init__(self, vm, window=1024):
        self.window = window
        self.queue = []
        self.prev = b''
        vm.stdout_handlers.append(self.incoming)

    def add(self, pattern, callback):
        self.queue.append((pattern, callback))

    def incoming(self, data):
        while data:
            buffer, data = data[:self.window], data[self.window:]
            buffer = self.prev + buffer

            while self.queue:
                (pattern, callback) = self.queue[0]
                m = re.search(pattern, buffer)
                if not m:
                    break
                self.queue.pop(0)
                callback(m)
                buffer = buffer[m.end():]

            self.prev = buffer[-self.window:]

def handle_output(vm, output):
    output_file = open(output, 'ab')
    def handle_stdout(data):
        output_file.write(data)
        output_file.flush()
    vm.stdout_handlers.append(handle_stdout)

def run(args, output):
    vm = VM()
    if output:
        handle_output(vm, output)
    vm.start(args)
    try:
        repl(vm=vm)
    finally:
        vm.kill()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output')
    parser.add_argument('cmd', nargs='+')
    options = parser.parse_args()
    run(options.cmd, options.output)
