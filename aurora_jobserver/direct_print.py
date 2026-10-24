"""Automatic JobServer dispatch for jobs produced by a printer frontend.

The printer frontend supplies an encoded JBS plus its durable print UUID.
Normal dispatch requires no second Send action. This backend does not install
a printer, render XPS, or implement the printer's Properties dialog.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import uuid

from .jbs import MAX_JOB_BYTES, prepare
from .sender import send_job
from .worker import WorkerLock, process_one
from .wire import raster_plan


CONTROLLER_PATH = r'c:\xfiles\jbs\Convert\Default.jbs'
FINISHED = frozenset(('completed', 'completed_with_warning', 'canceled'))


class PrintBridgeBlocked(RuntimeError):
    """A queue problem requires attention; dispatch must not retry the job."""


class DirectPrintBridge:
    def __init__(self, store, endpoint, *, controller_path=CONTROLLER_PATH,
                 timing=None, locks=None):
        self.store = store
        self.endpoint = endpoint
        self.controller_path = controller_path
        self.timing = timing
        self.locks = locks
        self.target = asdict(endpoint) | {'controller_job_path': controller_path}

    def accept(self, source, print_id, printer_settings):
        """Snapshot one encoded Print event, without sending on this call.

        Reopening the same receipt is idempotent. A second deliberate Print has
        a new UUID even if its document bytes are identical. Settings describe
        the encoded commands; they do not override commands after submission.
        """
        if not isinstance(print_id, str) or str(uuid.UUID(print_id)) != print_id:
            raise ValueError('Expected the durable print UUID')
        if not isinstance(printer_settings, dict):
            raise ValueError('Expected per-print printer settings')
        if any(p['print_id']==print_id for p in self.store.print_outcomes()):
            raise ValueError('Print already has a local nothing-to-cut outcome; submit a new Print')
        # Validate before accepting an automatically deliverable receipt.
        # Ordinary artwork drafts and unsupported vector-only jobs stay blocked.
        source = Path(source)
        with source.open('rb') as stream:
            data = stream.read(MAX_JOB_BYTES + 1)
        if len(data) > MAX_JOB_BYTES:
            raise ValueError('Print exceeds the job size limit')
        prepared = prepare(data)
        raster_plan(prepared.data, self.controller_path)
        metadata = {'direct_print': {'schema_version': 1, 'print_id': print_id,
                                    'target': self.target},
                    'printer_settings': printer_settings}
        # Normalize JSON now, so later caller mutation cannot change comparison.
        metadata = json.loads(json.dumps(metadata, allow_nan=False))
        signature = (hashlib.sha256(data).hexdigest(), metadata)
        # Publish only the bytes validated above, even if the frontend replaces
        # its output file while this print is being accepted.
        with tempfile.TemporaryDirectory(prefix='.accept-', dir=self.store.root) as staging:
            snapshot = Path(staging) / source.name
            snapshot.write_bytes(data)
            job_id = self.store.submit(snapshot, metadata, receipt='direct-print:' + print_id)
        job = self.store.get(job_id)
        if (job['source_hash'], job['settings']) != signature:
            raise ValueError('Print receipt already belongs to different bytes or settings')
        return job_id

    def step(self):
        """Prepare and automatically deliver the oldest outstanding Print once.

        Use a dedicated queue. Failed or interrupted delivery stops the bridge;
        it never retries an upload or silently advances beyond a failed print.
        The existing controller lock and durable uncertainty marker still apply.
        No connection-reset command is issued by automatic dispatch.
        """
        with WorkerLock(self.store.root):
            jobs = sorted(self.store.list(), key=lambda job: (job['created'], job['id']))
            for job in jobs:
                metadata = job['settings'].get('direct_print')
                if (not isinstance(metadata, dict) or metadata.get('schema_version') != 1
                        or metadata.get('target') != self.target):
                    raise PrintBridgeBlocked('Dedicated print queue contains another source or target')
            pending = next((job for job in jobs if job['state'] not in FINISHED), None)
            if pending is None:
                return None
            if pending['state'] == 'preparing':
                # Preparation has no machine I/O and can safely be recovered.
                self.store.recover()
                pending = self.store.get(pending['id'])
            if pending['state'] == 'queued':
                pending = process_one(self.store)
            if pending['state'] != 'ready':
                raise PrintBridgeBlocked(f"Print {pending['id']} needs attention: {pending['state']}")
            result = send_job(self.store, pending['id'], self.endpoint, self.controller_path,
                              timing=self.timing, locks=self.locks)
            if result['state'] not in ('completed', 'completed_with_warning'):
                raise PrintBridgeBlocked(f"Print {result['id']} needs attention: {result['state']}")
            return result
