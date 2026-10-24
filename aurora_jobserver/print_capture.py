"""Loopback-only LPR print capture; never converts or sends engraving jobs.

Implements the bounded receive-job subset of RFC 1179. Windows' built-in TCP
port monitor supplies byte-counted files, avoiding file-overwrite races and
requiring no third-party port monitor inside the print spooler.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import time
import uuid


MAX_DOCUMENT = 64 * 1024 * 1024
MAX_CONTROL = 64 * 1024
FILE_COMMAND = re.compile(rb"([\x02\x03])([0-9]{1,9}) ([!-~]{1,200})\n")


def save_json(path, value):
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, indent=2, ensure_ascii=True)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())


class CaptureServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, root, port=515, queue='aurora-capture', timeout=60, *, routes=None):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', queue):
            raise ValueError('Invalid capture queue name')
        if not 0 <= port <= 65535 or not 0.1 <= timeout <= 600:
            raise ValueError('Invalid capture port or timeout')
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.queue = queue.encode('ascii')
        self.routes = {self.queue:self.root}
        for name, folder in (routes or {}).items():
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', name) or name.encode('ascii') in self.routes:
                raise ValueError('Invalid or duplicate LPR queue route')
            path = Path(folder).resolve()
            if path in self.routes.values():
                raise ValueError('LPR queues must have separate capture directories')
            path.mkdir(parents=True,exist_ok=True)
            self.routes[name.encode('ascii')] = path
        self.timeout_seconds = timeout
        super().__init__(('127.0.0.1', port), CaptureHandler, bind_and_activate=False)
        try:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.server_bind()
            self.server_activate()
        except BaseException:
            self.server_close()
            raise

    def handle_error(self, request, client_address):
        # Expected malformed/incomplete print sessions are retained with errors
        # by the handler. Unexpected exceptions remain visible to the operator.
        super().handle_error(request, client_address)


class CaptureHandler(socketserver.StreamRequestHandler):
    def setup(self):
        self.request.settimeout(self.server.timeout_seconds)
        super().setup()
        self.deadline = time.monotonic() + 600

    def line(self):
        if time.monotonic() > self.deadline:
            raise TimeoutError('Capture session exceeded ten minutes')
        line = self.rfile.readline(4097)
        if len(line) > 4096 or (line and not line.endswith(b'\n')):
            raise ValueError('Incomplete or oversized LPR command')
        return line

    def ack(self, accepted=True):
        self.wfile.write(b'\0' if accepted else b'\1')
        self.wfile.flush()

    def receive(self, path, size):
        digest = hashlib.sha256()
        remaining = size
        with path.open('xb') as output:
            while remaining:
                if time.monotonic() > self.deadline:
                    raise TimeoutError('Capture session exceeded ten minutes')
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    raise ValueError('Print file ended before its advertised length')
                output.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
            if self.rfile.read(1) != b'\0':
                raise ValueError('Missing LPR file completion marker')
            output.flush()
            os.fsync(output.fileno())
        return digest.hexdigest()

    def handle(self):
        directory = None
        try:
            command = self.line()
            queue = command[1:-1] if command.endswith(b'\n') else b''
            if queue not in self.server.routes:
                self.ack(False)
                return
            root = self.server.routes[queue]
            if command[:1] in (b'\x03',b'\x04'):
                self.wfile.write(b'Aurora local document capture is online.\n')
                return
            if command[:1] != b'\x02':
                self.ack(False)
                return
            capture_id = str(uuid.uuid4())
            directory = root / ('.receiving-' + capture_id)
            directory.mkdir()
            self.ack()
            files = {}
            aborted = False
            while True:
                line = self.line()
                if not line:
                    break
                if line == b'\x01\n':
                    aborted = True
                    break
                match = FILE_COMMAND.fullmatch(line)
                if not match:
                    raise ValueError('Unsupported LPR subcommand')
                kind = 'control' if match[1] == b'\x02' else 'document'
                size = int(match[2])
                if kind in files or not 0 < size <= (MAX_CONTROL if kind == 'control' else MAX_DOCUMENT):
                    raise ValueError('Duplicate file or unsupported file length; enable LPR byte counting')
                self.ack()
                filename = 'control.lpr' if kind == 'control' else 'source.bin'
                sha256 = self.receive(directory / filename, size)
                files[kind] = {'lpr_name': match[3].decode('ascii'), 'bytes': size, 'sha256': sha256, 'file': filename}
                # Both raw files and the durable pending record exist before the
                # final file ACK. Only a clean session close publishes a capture.
                if len(files) == 2:
                    save_json(directory / 'received.json', {'id': capture_id, 'state': 'received_pending_close', 'files': files})
                self.ack()
            if aborted:
                raise ValueError('Client aborted the LPR job')
            if len(files) != 2:
                raise ValueError('LPR session did not supply both control and document files')
            control = (directory / 'control.lpr').read_bytes()
            metadata = {}
            for line in control.splitlines():
                if line[:1] in (b'H', b'P', b'J', b'N'):
                    metadata.setdefault(line[:1].decode('ascii'), []).append(line[1:].decode('cp1252', errors='replace'))
            save_json(directory / 'capture.json', {
                'schema_version': 1, 'id': capture_id, 'state': 'captured',
                'received_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'received_ns': time.time_ns(),
                'queue': queue.decode('ascii'), 'files': files, 'lpr_metadata': metadata,
                'purpose': 'local_print_document_capture_only',
            })
            directory.rename(root / capture_id)
            print(json.dumps({'captured': capture_id, 'bytes': files['document']['bytes']}), flush=True)
        except (OSError, ValueError, TimeoutError) as error:
            if directory is not None and directory.exists():
                save_json(directory / 'failed.json', {'state': 'incomplete', 'error': str(error)})
            try:
                self.ack(False)
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('runtime/print-capture'))
    parser.add_argument('--port', type=int, default=515)
    parser.add_argument('--queue', default='aurora-capture')
    parser.add_argument('--direct-root',type=Path,help='Also capture aurora-direct into a separate directory; never sends')
    args = parser.parse_args()
    routes = {'aurora-direct':args.direct_root} if args.direct_root else None
    with CaptureServer(args.root, args.port, queue=args.queue, routes=routes) as server:
        print(json.dumps({'listening': list(server.server_address), 'queue': args.queue, 'root': str(server.root)}), flush=True)
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
