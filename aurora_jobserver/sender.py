"""Explicit single-job delivery with durable attempts and controller locking."""
from dataclasses import asdict
import json
import ipaddress
from pathlib import Path
import time

from .store import atomic_write
from .transport import AuroraSession
from .wire import raster_plan
from .worker import WorkerLock
from .runtime_paths import default_locks


DEFAULT_LOCKS = default_locks()


class DeviceGuard:
    """Serialize this application's senders across queues sharing a lock root.

    This does not evict another application or prove ownership of the device's
    controller ports. A durable marker blocks later sends after an uncertain job.
    """
    def __init__(self, host, root=None):
        host = str(ipaddress.IPv4Address(host))
        self.root = Path(root or DEFAULT_LOCKS)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = WorkerLock(self.root, host + '.lock')
        self.marker = self.root / (host + '.pending.json')

    def __enter__(self):
        try:
            self.lock.__enter__()
        except RuntimeError as exc:
            raise RuntimeError('Another sender holds the controller lock') from exc
        return self

    def __exit__(self, *args):
        return self.lock.__exit__(*args)

    def ensure_clear(self):
        if self.marker.exists():
            raise RuntimeError('An earlier delivery is unresolved. In JobServer, select the print marked '
                               '"Check physical outcome" and use "Record physical outcome…" after checking the laser. '
                               f'No job has been resent. Delivery record: {self.marker}')

    def mark(self, store, job_id, attempt_id):
        atomic_write(self.marker, json.dumps({'queue': str(store.root), 'job_id': job_id,
                    'attempt_id': attempt_id, 'time': time.time()}).encode('utf-8'))

    def clear(self, store, job_id, attempt_id):
        if self.marker.exists():
            record = json.loads(self.marker.read_text())
            expected = {'queue': str(store.root), 'job_id': job_id, 'attempt_id': attempt_id}
            if any(record.get(key) != value for key, value in expected.items()):
                raise RuntimeError('Controller marker belongs to a different delivery; it was retained')
            self.marker.unlink()


class Transcript:
    def __init__(self, directory):
        directory.mkdir(parents=True)
        self.files = {}
        self.directory = directory

    def write(self, channel, direction, data):
        key = (channel, direction)
        if key not in self.files:
            self.files[key] = (self.directory / f'{channel}-{direction}.bin').open('xb', buffering=0)
        remaining = memoryview(data)
        while remaining:
            count = self.files[key].write(remaining)
            if not count:
                raise OSError('Transcript write made no progress')
            remaining = remaining[count:]

    def close(self):
        for output in self.files.values():
            output.close()


def send_job(store, job_id, endpoint, controller_job_path, *, timing=None, locks=None, reset_connection=False):
    # Validate content and framing before acquiring a job or connecting anywhere.
    data = store.prepared_bytes(job_id)
    raster_plan(data, controller_job_path)
    with DeviceGuard(endpoint.host, locks) as guard:
        store.recover_deliveries(endpoint.host)
        guard.ensure_clear()
        record = asdict(endpoint) | {'controller_job_path': controller_job_path, 'reset_connection': reset_connection}
        attempt_id = store.begin_delivery(job_id, record)
        transcript = None
        try:
            transcript = Transcript(store.directory(job_id) / 'deliveries' / attempt_id)

            def stage(name, detail):
                store.delivery_stage(attempt_id, name, detail)
                if name == 'uploading':
                    guard.mark(store, job_id, attempt_id)

            session = AuroraSession(endpoint, timing, transcript.write, stage, reset_connection=reset_connection)
            result = session.deliver(data, controller_job_path)
            store.finish_delivery(attempt_id, result=result)
            guard.clear(store, job_id, attempt_id)
        except BaseException as exc:
            current = store.get(job_id)
            if current['state'] in ('connecting', 'uploading', 'awaiting_report'):
                state = store.finish_delivery(attempt_id, error=f'{type(exc).__name__}: {exc}')
                if state == 'delivery_failed':
                    guard.clear(store, job_id, attempt_id)
            if not isinstance(exc, Exception):
                raise
            # Completed delivery + marker cleanup failure must not be relabeled
            # as a failed job. Its retained marker still prevents another send.
            if current['state'] in ('completed','completed_with_warning'):
                raise
        finally:
            if transcript:
                transcript.close()
        return store.get(job_id)


def recover_controller(store, endpoint, *, locks=None):
    with DeviceGuard(endpoint.host, locks):
        return store.recover_deliveries(endpoint.host)


def resolve_job(store, job_id, outcome, note, *, locks=None):
    job = store.get(job_id)
    attempt = job['delivery']
    if attempt is None:
        raise ValueError('This job has no delivery attempt')
    with DeviceGuard(attempt['host'], locks) as guard:
        store.recover_deliveries(attempt['host'])
        if guard.marker.exists():
            marker = json.loads(guard.marker.read_text())
            if (marker.get('queue'), marker.get('job_id'), marker.get('attempt_id')) != (
                    str(store.root), job_id, attempt['id']):
                raise ValueError('Controller marker belongs to a different queue or job')
        if store.get(job_id)['state'] == 'delivery_unknown':
            store.resolve_delivery(job_id, outcome, note)
        elif store.get(job_id)['state'] not in ('completed','completed_with_warning'):
            raise ValueError('This delivery is not uncertain or completed')
        guard.clear(store, job_id, attempt['id'])
    return store.get(job_id)
