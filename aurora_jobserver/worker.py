"""Single-worker preparation and non-destructive inbox observation."""
import hashlib
import json
import os
from pathlib import Path

from .jbs import MAX_JOB_BYTES, prepare
from .store import SourceChangedError, atomic_write, digest


class WorkerLock:
    def __init__(self, root, filename='worker.lock'):
        self.path = Path(root) / filename
        self.file = None

    def __enter__(self):
        self.file = self.path.open("a+b")
        self.file.seek(0, 2)
        if not self.file.tell():
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise RuntimeError("A preparation worker is already running for this queue") from exc
        return self

    def __exit__(self, *_):
        if self.file:
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_UN)
            self.file.close()
            self.file = None


def process_one(store):
    job = store.claim()
    if job is None:
        return None
    try:
        folder = store.directory(job["id"])
        source = (folder / "source.jbs").read_bytes()
        if digest(source) != job["source_hash"]:
            raise ValueError("Source snapshot failed its integrity check")
        result = prepare(source)
        atomic_write(folder / "prepared.jbs", result.data)
        store.finish(job["id"], result)
    except Exception as exc:
        store.fail(job["id"], exc)
    return store.get(job["id"])


class InboxWatcher:
    def __init__(self, store, folder=None):
        self.store = store
        self.folder = Path(folder or store.root / "inbox").resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.previous = {}

    def poll(self):
        """Require two equal observations and a footer; never move/delete sources."""
        current = {}
        accepted = []
        for path in sorted(self.folder.glob("*.jbs")):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
                signature = (stat.st_size, stat.st_mtime_ns)
                current[str(path)] = signature
                if not stat.st_size or stat.st_size > MAX_JOB_BYTES or self.previous.get(str(path)) != signature:
                    continue
                with path.open("rb") as stream:
                    stream.seek(max(0, stat.st_size - 64))
                    if not stream.read().rstrip(b"\r\n \t").endswith(b"END_PLOT"):
                        continue
                token = hashlib.sha256(json.dumps([str(path), *signature]).encode()).hexdigest()
                with self.store.connect() as db:
                    if db.execute("SELECT 1 FROM receipts WHERE token=?", (token,)).fetchone():
                        continue
                accepted.append(self.store.submit(path, receipt=token, expected_stat=signature))
            except (FileNotFoundError, PermissionError, SourceChangedError):
                continue
        self.previous = current
        return accepted
