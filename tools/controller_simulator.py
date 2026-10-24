"""Loopback-only controller fixture, with no path to physical equipment."""
import socket
import threading
import time

from aurora_jobserver.transport import Endpoint


class ControllerSimulator:
    def __init__(self, job, *, warning=False, custom_table=b'', feature=5459,
                 status=b'\xff\xe1\x01\x00\x00\x02\x02\x00',
                 disconnect=None, fragment=False, echo_upload=False, hold=None, startup_status=None,
                 echo=True, require_reset=False):
        self.job = job
        self.warning = warning
        self.custom_table = custom_table
        self.feature = feature
        self.status = status
        self.startup_status = startup_status
        self.synchronized = threading.Event()
        self.echo = echo
        self.require_reset = require_reset
        self.reset_seen = threading.Event()
        self.disconnect = disconnect
        self.fragment = fragment
        self.echo_upload = echo_upload
        self.hold = hold
        self.upload_received = threading.Event()
        self.stopped = threading.Event()
        self.errors = []
        self.main_tx = bytearray()
        self.status_tx = bytearray()
        self.upload = b''
        self.threads = []
        self.listeners = []
        self.clients = []
        for _ in range(4):
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(0.1)
            self.listeners.append(listener)
        self.endpoint = Endpoint('127.0.0.1', *(s.getsockname()[1] for s in self.listeners))

    def __enter__(self):
        for listener, handler in zip(self.listeners, (self._main, self._status, self._realtime, self._recovery)):
            thread = threading.Thread(target=self._serve, args=(listener, handler), daemon=True)
            thread.start()
            self.threads.append(thread)
        return self

    def __exit__(self, *_):
        self.stopped.set()
        if self.hold:
            self.hold.set()
        for client in self.clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for listener in self.listeners:
            listener.close()
        for thread in self.threads:
            thread.join(3)
            if thread.is_alive():
                self.errors.append(AssertionError('Simulator thread failed to stop'))
        if self.errors:
            raise AssertionError(self.errors)

    def _serve(self, listener, handler):
        try:
            while not self.stopped.is_set():
                try:
                    client, address = listener.accept()
                    break
                except socket.timeout:
                    continue
            else:
                return
            assert address[0] == '127.0.0.1'
            self.clients.append(client)
            with client:
                client.settimeout(3)
                handler(client)
        except (EOFError, BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Expected for tests where the client rejects a response or disconnects.
            pass
        except OSError as exc:
            if not self.stopped.is_set():
                self.errors.append(exc)
        except BaseException as exc:
            self.errors.append(exc)

    def _read(self, client, count, transcript, echo=False):
        data = bytearray()
        while len(data) < count:
            chunk = client.recv(min(4096, count - len(data)))
            if not chunk:
                raise EOFError()
            data.extend(chunk)
            transcript.extend(chunk)
            if echo:
                client.sendall(b'transfer in progress\n' * 800)
        return bytes(data)

    def _expect(self, client, request):
        got = self._read(client, len(request), self.main_tx)
        if got != request:
            raise AssertionError(f'Unexpected request: {got[:100]!r}; expected {request[:100]!r}')

    def _reply(self, client, reply):
        if self.fragment:
            for byte in reply:
                client.sendall(bytes([byte]))
                time.sleep(0.0003)
        else:
            client.sendall(reply)

    def _status(self, client):
        count = 0
        while not self.stopped.is_set():
            data = self._read(client, 3, self.status_tx)
            assert data == b'\xff\xe0\x01'
            if count:
                # Main and status sockets run on different fixture threads.
                # Allow the main thread to consume already-sent sync bytes;
                # an early poll without a sync still fails after this bound.
                assert self.synchronized.wait(1), 'Status must be checked again after main-channel sync'
            reply = self.startup_status if count == 0 and self.startup_status is not None else self.status
            self._reply(client, reply)
            count += 1

    def _main(self, client):
        if self.require_reset:
            assert self.reset_seen.wait(1), 'Legacy connection recovery was not requested'
        sync = b'\nM99\n!ZX\n'
        sync_reply = b' M99 \n> !ZX \n> ' if self.echo else b''
        for _ in range(2):
            self._expect(client, sync)
            self.synchronized.set()
            self._reply(client, sync_reply)
        self._expect(client, b'\n0 dsp_feature 1 wchar\n')
        feature = (f'0 dsp_feature 1 wchar #{self.feature:010d}\n'.encode() + b'\x01\n> ' if self.echo
                   else f'#{self.feature:010d}\n\r'.encode() + b'\x01')
        self._reply(client, feature)
        self._expect(client, b'1 dsp_feature 1 wchar\n')
        self._reply(client, b'1 dsp_feature 1 wchar #0330476101\n\x01\n> ' if self.echo else b'#0330476101\n\r\x01')
        self._expect(client, sync)
        self._reply(client, sync_reply)
        self._expect(client, b'\n1 wchar pre_job_table\r')
        self._reply(client, (b'1 wchar pre_job_table ' if self.echo else b'') + b'\x01'
                    + self.custom_table + (b'\x04\n> ' if self.echo else b'\x04'))
        prefix = (b'\ncls\nmsg Preprocessing the job...\nifexists jobtype 5 jobtype\n'
                  b'\ncls\nmsg Please Stand By...\n'
                  b'ifexists JM_PATH JM_PATH c:\\xfiles\\jbs\\Convert\\Default.jbs\n\r'
                  b'ifexists HOTWATCH_CYCLE_START HOTWATCH_CYCLE_START Default.jbs\n')
        expected = prefix + (self.job() if callable(self.job) else self.job)
        if self.disconnect == 'mid_upload':
            self._read(client, 1, self.main_tx)
            return
        self.upload = self._read(client, len(expected), self.main_tx, self.echo_upload)
        assert self.upload == expected
        self.upload_received.set()
        if self.hold:
            if not self.hold.wait(3):
                raise TimeoutError('Test did not release the simulated engraving')
        if self.disconnect == 'after_upload':
            return
        if self.disconnect == 'stall':
            client.recv(1)
            return
        if self.warning:
            self._reply(client, b"\x07Error 2: Token 'set_xyup_feed' not found.\n")
        self._reply(client, b'\xad\x05\x06E0\x06\xac')
        self._expect(client, b'ifexists host_terminate host_terminate\n')
        if self.disconnect == 'after_end':
            return
        self._reply(client, b'\xadP\n\rJOB_TIME 202.0140\n\r\x04\xac')
        client.recv(1)

    def _realtime(self, client):
        client.settimeout(.1)
        while not self.stopped.is_set():
            try:
                data = client.recv(1)
                if not data:
                    return
                raise AssertionError('This profile sends no realtime payload')
            except socket.timeout:
                pass

    def _recovery(self, client):
        self.reset_seen.set()
        assert not client.recv(1), 'Recovery port receives no application payload'


def main():
    import argparse
    import json
    from pathlib import Path
    from aurora_jobserver.jbs import prepare
    from aurora_jobserver.wire import raster_plan

    parser = argparse.ArgumentParser(description='Run a single-job Aurora simulator on loopback only')
    parser.add_argument('job', type=Path)
    parser.add_argument('--warning', action='store_true', help='Include the captured token warning')
    parser.add_argument('--no-echo', action='store_true', help='Use bare feature values and no sync prompts')
    parser.add_argument('--duration', type=float, default=120, help='Maximum lifetime in seconds')
    args = parser.parse_args()
    if not 0 < args.duration <= 3600:
        parser.error('Duration must be positive and at most 3600 seconds')
    data = prepare(args.job.read_bytes()).data
    raster_plan(data, r'c:\xfiles\jbs\Convert\Default.jbs')
    try:
        with ControllerSimulator(data, warning=args.warning, fragment=True, echo=not args.no_echo) as simulator:
            print(json.dumps({'simulation': True, 'host': simulator.endpoint.host,
                              'main_port': simulator.endpoint.main_port,
                              'status_port': simulator.endpoint.status_port,
                              'realtime_port': simulator.endpoint.realtime_port,
                              'recovery_port': simulator.endpoint.recovery_port}), flush=True)
            deadline = time.monotonic() + args.duration
            while simulator.threads[0].is_alive() and time.monotonic() < deadline:
                time.sleep(.1)
            complete = simulator.upload_received.is_set() and not simulator.threads[0].is_alive()
            print(json.dumps({'upload_received': simulator.upload_received.is_set(),
                              'client_stream_bytes': len(simulator.main_tx), 'session_ended': complete}), flush=True)
            return 0 if complete else 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
