"""SQLite queue, immutable job snapshots, and append-only event history."""
from contextlib import contextmanager, closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .jbs import MAX_JOB_BYTES


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('queued','preparing','ready','failed','canceled',
 'connecting','uploading','awaiting_report','completed','completed_with_warning',
 'delivery_unknown','delivery_failed')),
 source_name TEXT NOT NULL, source_hash TEXT NOT NULL, source_bytes INTEGER NOT NULL,
 settings TEXT NOT NULL, output_hash TEXT, output_bytes INTEGER, rasters INTEGER,
 input_format TEXT, auto_start INTEGER, title TEXT, error TEXT, attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(id),
 time REAL NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS receipts (
 token TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id)
);
CREATE TABLE IF NOT EXISTS deliveries (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
 created REAL NOT NULL, updated REAL NOT NULL, state TEXT NOT NULL,
 host TEXT NOT NULL, endpoint TEXT NOT NULL, upload_started INTEGER NOT NULL DEFAULT 0,
 result TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS print_outcomes (
 print_id TEXT PRIMARY KEY, source_hash TEXT NOT NULL, created REAL NOT NULL,
 result TEXT NOT NULL
);
"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


class SourceChangedError(ValueError):
    """A watched file changed before a consistent snapshot could be taken."""


def atomic_write(path, data):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".part")
    try:
        with temporary.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class JobStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "jobs").mkdir(exist_ok=True)
        (self.root / "inbox").mkdir(exist_ok=True)
        self.database = self.root / "queue.sqlite3"
        with self.connect() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] > 2:
                raise RuntimeError('This queue was created by a newer JobServer version')
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
            self._migrate(db)

    def print_outcomes(self):
        with self.connect() as db:
            return [json.loads(row['result']) for row in db.execute('SELECT result FROM print_outcomes ORDER BY created,print_id')]

    def record_no_cut(self, result):
        print_id=result.get('print_id')
        source_hash=result.get('source_sha256','')
        if (not isinstance(print_id,str) or str(uuid.UUID(print_id))!=print_id
                or not isinstance(source_hash,str) or len(source_hash)!=64 or any(c not in '0123456789abcdef' for c in source_hash)
                or not ((result.get('state')=='nothing_to_cut'
                         and result.get('printer_settings',{}).get('output_mode')=='vector-only')
                        or (result.get('state')=='nothing_to_print'
                            and result.get('printer_settings',{}).get('output_mode') in ('raster-only','raster-and-vector')
                            and result.get('printer_settings',{}).get('classic_preferences',{}).get('UseColors') is True))
                or result.get('physical_delivery_performed_by_pipeline') is not False):
            raise ValueError('Expected a verified local nothing-to-cut result')
        encoded=json.dumps(result,sort_keys=True,allow_nan=False)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM receipts WHERE token=?',('direct-print:'+print_id,)).fetchone():
                raise ValueError('Print already belongs to a deliverable job')
            old=db.execute('SELECT result FROM print_outcomes WHERE print_id=?',(print_id,)).fetchone()
            if old:
                if old['result']!=encoded:raise ValueError('Print outcome changed')
                return
            db.execute('INSERT INTO print_outcomes VALUES(?,?,?,?)',(print_id,source_hash,time.time(),encoded))

    def _migrate(self, db):
        definition = db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
        if 'delivery_unknown' not in definition:
            # SQLite CHECK constraints require a table rebuild. Keep the original
            # table name for the event/receipt foreign keys and do this atomically.
            backup = self.root / 'queue-v1-backup.sqlite3'
            if not backup.exists():
                with closing(sqlite3.connect(backup)) as destination:
                    db.backup(destination)
            db.execute('PRAGMA foreign_keys=OFF')
            try:
                db.execute('BEGIN IMMEDIATE')
                table = SCHEMA.split(';', 1)[0].replace('IF NOT EXISTS jobs', 'jobs_v2')
                db.execute(table)
                db.execute('INSERT INTO jobs_v2 SELECT * FROM jobs')
                db.execute('DROP TABLE jobs')
                db.execute('ALTER TABLE jobs_v2 RENAME TO jobs')
                if db.execute('PRAGMA foreign_key_check').fetchall():
                    raise RuntimeError('Queue migration failed its foreign-key check')
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA user_version=2')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def directory(self, job_id):
        if str(uuid.UUID(job_id)) != job_id:
            raise ValueError("Invalid job ID")
        return self.root / "jobs" / job_id

    @staticmethod
    def event(db, job_id, kind, detail=""):
        db.execute("INSERT INTO events(job_id,time,kind,detail) VALUES(?,?,?,?)",
                   (job_id, time.time(), kind, detail))

    @staticmethod
    def record(row):
        if row is None:
            raise KeyError("Job not found")
        result = dict(row)
        result["settings"] = json.loads(result["settings"])
        if result["auto_start"] is not None:
            result["auto_start"] = bool(result["auto_start"])
        return result

    def submit(self, source, settings=None, receipt=None, expected_stat=None):
        source = Path(source)
        if settings is None:
            settings = {}
        if not isinstance(settings, dict):
            raise ValueError("Settings must be a JSON object")
        settings_json = json.dumps(settings, sort_keys=True, allow_nan=False)
        before = source.stat()
        if expected_stat is not None and (before.st_size, before.st_mtime_ns) != expected_stat:
            raise SourceChangedError("Source changed since the inbox observation")
        if before.st_size > MAX_JOB_BYTES:
            raise ValueError("Job exceeds the 64 MiB limit")
        with source.open("rb") as stream:
            data = stream.read(MAX_JOB_BYTES + 1)
        after = source.stat()
        if len(data) > MAX_JOB_BYTES or (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            raise SourceChangedError("Source changed during submission; try again after printing finishes")
        if not data:
            raise ValueError("The file is empty; submit the actual .jbs job instead of an empty .prn")
        job_id = str(uuid.uuid4())
        folder = self.directory(job_id)
        folder.mkdir()
        atomic_write(folder / "source.jbs", data)
        atomic_write(folder / "settings.json", settings_json.encode("utf-8"))
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if receipt:
                existing = db.execute("SELECT job_id FROM receipts WHERE token=?", (receipt,)).fetchone()
                if existing:
                    (folder / "source.jbs").unlink()
                    (folder / "settings.json").unlink()
                    folder.rmdir()
                    return existing["job_id"]
            db.execute("""INSERT INTO jobs(id,created,updated,state,source_name,source_hash,source_bytes,settings)
                          VALUES(?,?,?,'queued',?,?,?,?)""",
                       (job_id, now, now, source.name, digest(data), len(data), settings_json))
            self.event(db, job_id, "submitted", source.name)
            if receipt:
                db.execute("INSERT INTO receipts(token,job_id) VALUES(?,?)", (receipt, job_id))
        return job_id

    def get(self, job_id):
        self.directory(job_id)
        with self.connect() as db:
            result = self.record(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
            attempt = db.execute('SELECT * FROM deliveries WHERE job_id=? ORDER BY created DESC,id DESC LIMIT 1',
                                 (job_id,)).fetchone()
            result['delivery'] = self.delivery_record(attempt) if attempt else None
            return result

    def list(self):
        with self.connect() as db:
            return [self.record(row) for row in db.execute("SELECT * FROM jobs ORDER BY created DESC,id")]

    def history(self, job_id):
        self.get(job_id)
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM events WHERE job_id=? ORDER BY seq", (job_id,))]

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created,id LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET state='preparing',updated=?,attempts=attempts+1,error=NULL WHERE id=?",
                       (time.time(), row["id"]))
            self.event(db, row["id"], "preparing")
            return self.record(row)

    def recover(self):
        """Only call while holding the exclusive preparation-worker lock."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT id FROM jobs WHERE state='preparing'").fetchall()
            for row in rows:
                db.execute("UPDATE jobs SET state='queued',updated=? WHERE id=?", (time.time(), row["id"]))
                self.event(db, row["id"], "recovered", "Interrupted preparation requeued; no device delivery occurred")
            return len(rows)

    def finish(self, job_id, prepared):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("""UPDATE jobs SET state='ready',updated=?,output_hash=?,output_bytes=?,
                rasters=?,input_format=?,auto_start=?,title=?,error=NULL WHERE id=? AND state='preparing'""",
                (time.time(), digest(prepared.data), len(prepared.data), prepared.rasters,
                 prepared.input_format, int(prepared.auto_start), prepared.title, job_id)).rowcount
            if changed:
                self.event(db, job_id, "ready", "Prepared locally; not sent to the engraver")
            return bool(changed)

    def fail(self, job_id, error):
        with self.connect() as db:
            changed = db.execute("UPDATE jobs SET state='failed',updated=?,error=? WHERE id=? AND state='preparing'",
                                 (time.time(), str(error), job_id)).rowcount
            if changed:
                self.event(db, job_id, "failed", str(error))

    def cancel(self, job_id):
        self.get(job_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("""UPDATE jobs SET state='canceled',updated=? WHERE id=?
                AND state IN ('queued','preparing','ready','failed','delivery_failed')""",
                                 (time.time(), job_id)).rowcount
            if changed:
                self.event(db, job_id, "canceled", "Files and history retained")
            elif db.execute('SELECT state FROM jobs WHERE id=?', (job_id,)).fetchone()[0] != 'canceled':
                raise ValueError('A physical delivery cannot be canceled or relabeled by the local Cancel action')

    def retry(self, job_id):
        self.get(job_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("""UPDATE jobs SET state='queued',updated=?,error=NULL,
                                    output_hash=NULL,output_bytes=NULL,rasters=NULL,input_format=NULL,
                                    auto_start=NULL,title=NULL WHERE id=?
                                    AND state IN ('failed','canceled','delivery_failed')""", (time.time(), job_id)).rowcount
            if not changed:
                raise ValueError("Only failed, canceled, or confirmed not-sent jobs can be queued again")
            self.event(db, job_id, "requeued")

    def export(self, job_id, destination):
        job = self.get(job_id)
        if job["state"] != "ready":
            raise ValueError("Only ready jobs can be exported")
        data = (self.directory(job_id) / "prepared.jbs").read_bytes()
        if digest(data) != job["output_hash"]:
            raise ValueError("Prepared file failed its integrity check")
        destination = Path(destination)
        with destination.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        with self.connect() as db:
            self.event(db, job_id, "exported", str(destination.resolve()))
        return destination

    def prepared_bytes(self, job_id):
        job = self.get(job_id)
        if job['state'] != 'ready':
            raise ValueError('Only a ready job can begin a delivery')
        data = (self.directory(job_id) / 'prepared.jbs').read_bytes()
        if digest(data) != job['output_hash']:
            raise ValueError('Prepared file failed its integrity check')
        return data

    @staticmethod
    def delivery_record(row):
        result = dict(row)
        result['endpoint'] = json.loads(result['endpoint'])
        result['result'] = json.loads(result['result']) if result['result'] else None
        result['upload_started'] = bool(result['upload_started'])
        return result

    def begin_delivery(self, job_id, endpoint):
        self.directory(job_id)
        attempt_id = str(uuid.uuid4())
        now = time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            blocked = db.execute("""SELECT id FROM deliveries WHERE host=? AND
                state IN ('connecting','uploading','awaiting_report','delivery_unknown')""",
                (endpoint['host'],)).fetchone()
            if blocked:
                raise ValueError('An active or uncertain delivery already exists for this controller')
            changed = db.execute("UPDATE jobs SET state='connecting',updated=?,error=NULL WHERE id=? AND state='ready'",
                                 (now, job_id)).rowcount
            if not changed:
                raise ValueError('Only a ready job can begin a delivery')
            db.execute("""INSERT INTO deliveries(id,job_id,created,updated,state,host,endpoint)
                VALUES(?,?,?,?,'connecting',?,?)""",
                (attempt_id, job_id, now, now, endpoint['host'], json.dumps(endpoint)))
            self.event(db, job_id, 'connecting', attempt_id)
        return attempt_id

    def delivery_stage(self, attempt_id, stage, detail):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            attempt = db.execute('SELECT * FROM deliveries WHERE id=?', (attempt_id,)).fetchone()
            if attempt is None or attempt['state'] not in ('connecting','uploading','awaiting_report'):
                raise ValueError('Delivery attempt is no longer active')
            if stage in ('uploading', 'awaiting_report'):
                expected = 'connecting' if stage == 'uploading' else 'uploading'
                if attempt['state'] != expected:
                    raise ValueError('Invalid delivery phase transition')
                db.execute('UPDATE deliveries SET state=?,updated=?,upload_started=1 WHERE id=?',
                           (stage, time.time(), attempt_id))
                db.execute('UPDATE jobs SET state=?,updated=? WHERE id=?',
                           (stage, time.time(), attempt['job_id']))
            self.event(db, attempt['job_id'], stage, json.dumps(detail))

    def finish_delivery(self, attempt_id, result=None, error=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            attempt = db.execute('SELECT * FROM deliveries WHERE id=?', (attempt_id,)).fetchone()
            if attempt is None or attempt['state'] not in ('connecting','uploading','awaiting_report'):
                raise ValueError('Delivery attempt is no longer active')
            if result is None:
                state = 'delivery_unknown' if attempt['upload_started'] else 'delivery_failed'
            else:
                state = result['state']
                if state not in ('completed','completed_with_warning') or not attempt['upload_started']:
                    raise ValueError('Invalid delivery outcome')
            result_json = json.dumps(result, allow_nan=False) if result is not None else None
            message = str(error) if error is not None else None
            db.execute('UPDATE deliveries SET state=?,updated=?,result=?,error=? WHERE id=?',
                       (state, time.time(), result_json, message, attempt_id))
            db.execute('UPDATE jobs SET state=?,updated=?,error=? WHERE id=?',
                       (state, time.time(), message, attempt['job_id']))
            self.event(db, attempt['job_id'], state, message or result_json or '')
            return state

    def recover_deliveries(self, host):
        """Call only while holding the shared controller sender lock."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            attempts = db.execute("""SELECT * FROM deliveries WHERE host=?
                AND state IN ('connecting','uploading','awaiting_report')""", (host,)).fetchall()
            for attempt in attempts:
                state = 'delivery_unknown' if attempt['upload_started'] else 'delivery_failed'
                reason = 'Sender interrupted; automatic repeat is disabled'
                db.execute('UPDATE deliveries SET state=?,updated=?,error=? WHERE id=?',
                           (state, time.time(), reason, attempt['id']))
                db.execute('UPDATE jobs SET state=?,updated=?,error=? WHERE id=?',
                           (state, time.time(), reason, attempt['job_id']))
                self.event(db, attempt['job_id'], state, reason)
            return len(attempts)

    def resolve_delivery(self, job_id, outcome, note):
        if outcome not in ('completed', 'not_started', 'stopped') or not note.strip():
            raise ValueError('Resolution needs an observed outcome and a nonempty operator note')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = db.execute('SELECT state FROM jobs WHERE id=?', (job_id,)).fetchone()
            attempt = db.execute('SELECT * FROM deliveries WHERE job_id=? ORDER BY created DESC,id DESC LIMIT 1',
                                 (job_id,)).fetchone()
            if job is None or job['state'] != 'delivery_unknown' or attempt is None:
                raise ValueError('Only an uncertain delivery can be resolved')
            state = 'completed_with_warning' if outcome == 'completed' else 'delivery_failed'
            record = json.dumps({'operator_outcome': outcome, 'note': note})
            db.execute('UPDATE deliveries SET state=?,updated=?,result=?,error=NULL WHERE id=?',
                       (state, time.time(), record, attempt['id']))
            db.execute('UPDATE jobs SET state=?,updated=?,error=NULL WHERE id=?', (state, time.time(), job_id))
            self.event(db, job_id, 'delivery_resolved', record)
