"""Bounded, duplex TCP transport for the captured Aurora raster-job profile."""
from dataclasses import dataclass, asdict
import ipaddress
import re
import select
import socket
import time

from .delivery import DeliveryTracker
from .protocol import STATUS_REQUEST, decode_status_reply
from .wire import raster_plan


class ProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class Endpoint:
    host: str
    main_port: int = 23
    status_port: int = 29
    realtime_port: int = 30
    recovery_port: int = 99

    def __post_init__(self):
        address = ipaddress.IPv4Address(self.host)
        if address.is_unspecified or address.is_multicast or int(address) == 0xffffffff:
            raise ValueError('A unicast IPv4 controller address is required')
        ports = (self.main_port, self.status_port, self.realtime_port, self.recovery_port)
        if any(type(p) is not int or not 1 <= p <= 65535 for p in ports):
            raise ValueError('Controller ports must be between 1 and 65535')
        if len(set(ports)) != len(ports):
            raise ValueError('Controller channels need different ports')


@dataclass(frozen=True)
class Timing:
    connect: float = 5
    handshake: float = 10
    job: float = 7200
    sync_delay: float = 0.5
    feature_delay: float = 0.2
    sync_quiet: float = 0.05

    def __post_init__(self):
        import math
        values = asdict(self)
        if any(not math.isfinite(v) or v <= 0 for v in values.values()):
            raise ValueError('Timeouts and protocol delays must be positive finite values')


class Peer:
    def __init__(self, endpoint, timeout, log, channel):
        self.socket = socket.create_connection(endpoint, timeout=timeout)
        try:
            self.socket.setblocking(False)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except BaseException:
            self.socket.close()
            raise
        self.log = log
        self.channel = channel
        self.pending = bytearray()

    def close(self):
        self.socket.close()

    def _receive(self):
        data = self.socket.recv(65536)
        if not data:
            raise ConnectionError('Controller closed the connection')
        self.log(self.channel, 'rx', data)
        return data

    def send(self, data, deadline, on_read=None):
        remaining = memoryview(data)
        while remaining:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                raise TimeoutError('Controller write timed out')
            readable, writable, _ = select.select([self.socket], [self.socket], [], min(timeout, 0.25))
            if readable:
                received = self._receive()
                if on_read:
                    on_read(received)
                else:
                    self.pending.extend(received)
                    if len(self.pending) > 1024 * 1024:
                        raise ProtocolError('Unconsumed controller replies exceed 1 MiB')
            if writable:
                try:
                    count = self.socket.send(remaining[:16384])
                except BlockingIOError:
                    continue
                if count == 0:
                    raise ConnectionError('Controller write made no progress')
                self.log(self.channel, 'tx', bytes(remaining[:count]))
                remaining = remaining[count:]

    def read(self, timeout):
        if self.pending:
            result = bytes(self.pending)
            self.pending.clear()
            return result
        readable, _, _ = select.select([self.socket], [], [], max(0, timeout))
        if readable:
            try:
                return self._receive()
            except BlockingIOError:
                pass
        return b''


class AuroraSession:
    """One connection and one explicit delivery; never reconnects or retries."""
    def __init__(self, endpoint, timing=None, log=None, stage=None, reset_connection=False):
        self.endpoint = endpoint
        self.timing = timing or Timing()
        self.log = log or (lambda channel, direction, data: None)
        self.stage = stage or (lambda name, detail: None)
        self.reset_connection = reset_connection

    def _exchange(self, peer, request, gate, delay=0):
        started = time.monotonic()
        deadline = started + self.timing.handshake
        peer.send(request, deadline)
        response = bytearray()
        last_data = started
        while True:
            now = time.monotonic()
            if (now - started >= delay and gate(bytes(response))
                    and now - last_data >= self.timing.sync_quiet):
                return bytes(response)
            if now >= deadline:
                raise TimeoutError('Controller handshake response timed out')
            data = peer.read(min(0.025, deadline - now))
            if data:
                response.extend(data)
                last_data = time.monotonic()
                if len(response) > 1024 * 1024:
                    raise ProtocolError('Controller handshake response exceeds 1 MiB')
                if b'\x07' in response or b'Error ' in response:
                    raise ProtocolError('Controller reported an error before job upload')

    def _status(self, peer, allow_startup=False):
        deadline = time.monotonic() + self.timing.handshake
        peer.send(STATUS_REQUEST, deadline)
        response = bytearray()
        while len(response) < 8:
            if time.monotonic() >= deadline:
                raise TimeoutError('Status query timed out')
            response.extend(peer.read(min(0.1, deadline - time.monotonic())))
        status = decode_status_reply(bytes(response))
        allowed = (0x0200, 0x1200) if allow_startup else (0x0200,)
        if status.flags_4_5 not in allowed or status.byte_6 != 2:
            raise ProtocolError(f'Controller status differs from the captured session profile: {status.raw_hex}')
        return status

    def deliver(self, job_data, controller_job_path):
        plan = raster_plan(job_data, controller_job_path)
        if self.reset_connection:
            # Explicit operator-requested legacy recovery, never an automatic
            # reaction to a failed physical upload or a job retry.
            recovery_result = 'connected'
            try:
                with socket.create_connection((self.endpoint.host, self.endpoint.recovery_port), self.timing.connect):
                    pass
            except ConnectionRefusedError:
                # This controller refuses port 99 even on the successful host
                # diagnostic. The native recovery path ignores connect's result.
                # Re-establishing channels and checking features is the proof.
                recovery_result = 'refused'
            self.stage('connection_reset', {'port': self.endpoint.recovery_port, 'result': recovery_result})
            time.sleep(self.timing.sync_delay)
        peer = Peer((self.endpoint.host, self.endpoint.main_port), self.timing.connect, self.log, 'main')
        status_peer = None
        realtime_peer = None
        tracker = DeliveryTracker()
        try:
            status_peer = Peer((self.endpoint.host, self.endpoint.status_port), self.timing.connect, self.log, 'status')
            realtime_peer = Peer((self.endpoint.host, self.endpoint.realtime_port), self.timing.connect, self.log, 'realtime')
            initial_status = self._status(status_peer, allow_startup=True)
            self.stage('status_initial', asdict(initial_status))
            features = []
            for step in plan[:5]:
                if step.name.startswith('feature_') and step.name != 'feature_sync':
                    index = 0 if step.name == 'feature_zero' else 1
                    pattern = re.compile(rb'#([0-9]{10})[\r\n]+\x01')
                    response = self._exchange(peer, step.request, lambda data: pattern.search(data) is not None,
                                              self.timing.feature_delay)
                    features.append(int(pattern.search(response)[1]))
                else:
                    # The vendor synchronizer sleeps, drains available bytes,
                    # and returns even when controller echo/prompts are disabled.
                    self._exchange(peer, step.request, lambda data: True, self.timing.sync_delay)
                if step.name == 'attach_sync':
                    # XP opens main first and observes 1200 -> 0200 across this
                    # synchronization. Do not upload while 1200 persists.
                    status = self._status(status_peer)
                    self.stage('status', asdict(status))
            self.stage('features', {'values': features})
            if features != [5459, 330476101]:
                raise ProtocolError('Controller feature values differ from this Aurora capture profile')
            table = self._exchange(peer, plan[5].request, lambda data: b'\x01' in data and b'\x04' in data)
            start = table.index(b'\x01') + 1
            end = table.index(b'\x04', start)
            if table[start:end] != b'':
                raise ProtocolError('Controller has an unimplemented custom pre-job table')
            # Persist the uncertain-delivery boundary before the first upload byte.
            self.stage('uploading', {'bytes': len(plan[6].request)})
            tracker.begin_upload()
            deadline = time.monotonic() + self.timing.job

            def during_upload(data):
                actions = tracker.feed(data)
                if actions or tracker.state == 'delivery_unknown':
                    raise ProtocolError('Controller ended a job before this upload finished')

            peer.send(plan[6].request, deadline, during_upload)
            self.stage('uploaded', {'bytes': len(plan[6].request)})
            while tracker.state in ('awaiting_end', 'awaiting_job_report'):
                if time.monotonic() >= deadline:
                    raise TimeoutError('Job completion report timed out')
                data = peer.read(min(0.25, deadline - time.monotonic()))
                if not data:
                    continue
                for request in tracker.feed(data):
                    self.stage('awaiting_report', {'end_code': tracker.end_code})
                    peer.send(request, deadline, lambda chunk: tracker.feed(chunk))
            if tracker.state not in ('completed', 'completed_with_warning'):
                raise ProtocolError(f'Unrecognized controller job outcome: {tracker.end_code}')
            return {'state': tracker.state, 'warnings': tracker.errors, 'job_time': tracker.job_time,
                    'end_code': tracker.end_code, 'features': features, 'status': asdict(status)}
        finally:
            peer.close()
            if status_peer:
                status_peer.close()
            if realtime_peer:
                realtime_peer.close()
