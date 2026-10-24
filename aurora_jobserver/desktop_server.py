"""Desktop-owned print receiver with explicit live sessions and no backlog replay."""
from dataclasses import asdict
import json
import logging
from pathlib import Path
import socket
import threading
import time
import uuid

from .print_capture import CaptureServer
from .print_service import PrintService
from .printer_settings import settings_from_xps
from .protocol import STATUS_REQUEST, decode_status_reply
from .sender import DeviceGuard, resolve_job
from .store import atomic_write
from .transport import Endpoint
from .worker import WorkerLock
from .runtime_paths import frozen


LOG = logging.getLogger(__name__)


def write_json(path, value):
    atomic_write(Path(path), json.dumps(value, indent=2).encode('utf-8'))


class ManagedCaptureServer(CaptureServer):
    """Track requests so closing the window never discards an accepted capture."""
    def __init__(self, *args, **kwargs):
        self.requests_lock = threading.Lock()
        self.requests = 0
        super().__init__(*args, **kwargs)

    def process_request(self, request, address):
        with self.requests_lock:
            self.requests += 1
        try:
            super().process_request(request, address)
        except BaseException:
            with self.requests_lock:
                self.requests -= 1
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            with self.requests_lock:
                self.requests -= 1

    def active_requests(self):
        with self.requests_lock:
            return self.requests

    def handle_error(self, request, address):
        LOG.exception('Print receiver failed for a local connection')


class DesktopJobServer:
    def __init__(self, root, intake, *, endpoint=None, port=515, preview_root=None,
                 timing=None, locks=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.intake = Path(intake).resolve()
        self.port = port
        self.preview_root = Path(preview_root or self.root/'preview-captures').resolve()
        self.capture_root = self.root/'capture-only'
        self.capture_root.mkdir(exist_ok=True)
        self.session_root = self.root/'sessions'
        self.session_root.mkdir(exist_ok=True)
        settings = self.root/'settings.json'
        configured = json.loads(settings.read_text())['endpoint'] if settings.exists() else {'host':'127.0.0.1' if frozen() else '192.168.1.244'}
        self.endpoint = endpoint or Endpoint(**configured)
        self.timing, self.locks = timing, locks
        self.mutex = threading.RLock()
        self.mode = 'capture_only'   # Never persist/recover a live mode.
        self.error = ''
        self.connection = 'Not checked'
        self.connection_raw = ''
        self.current_print = None
        self.probing = False
        self.busy = False
        self.service = None
        self.session = None
        self.services = {}
        self.cancelled = {}
        self.inventory = {}
        self.inventory_stamps = {}
        self.capture_errors = {}
        self.server = None
        self.receiver_thread = None
        self.worker_thread = None
        self.catalog_thread = None
        self.catalog_stop = threading.Event()
        self.application_lock = None
        self.closing = threading.Event()
        self.stopped = threading.Event()
        self.wake = threading.Event()
        # Old sessions are history only. Merely reopening this app never
        # reconstructs a dispatch worker for any of them.
        from .store import JobStore
        self.history_stores = {}
        for folder in self.session_root.iterdir():
            if folder.is_dir() and (folder/'session.json').is_file():
                if str(uuid.UUID(folder.name)) != folder.name:
                    continue
                self.history_stores[folder.name] = JobStore(folder/'queue')
                self.cancelled[folder.name] = {p.stem for p in (folder/'cancelled').glob('*.json')}

    def start(self, *, start_enabled=False):
        if type(start_enabled) is not bool:
            raise ValueError('Startup printing mode must be an explicit boolean')
        if not self.intake.is_file():
            raise ValueError('The artwork converter is missing. Build the printer frontend first.')
        self.application_lock = WorkerLock(self.root, 'desktop.lock')
        self.application_lock.__enter__()
        try:
            self.server = ManagedCaptureServer(self.capture_root, self.port, queue='aurora-direct',
                                               routes={'aurora-capture':self.preview_root})
            # A crashed sender's last database stage is not evidence that the
            # physical job stopped. Recover its record without any device I/O.
            for store in self.history_stores.values():
                hosts = {store.get(job['id'])['delivery']['host'] for job in store.list()
                         if job['state'] in ('connecting','uploading','awaiting_report')}
                for host in hosts:
                    with DeviceGuard(host, self.locks):
                        store.recover_deliveries(host)
            if start_enabled:
                try:
                    # The desktop's requested default opens a fresh routing
                    # session. Existing captures/sessions are history only.
                    self.enable_live()
                except RuntimeError as error:
                    # Keep the window available to record an unresolved prior
                    # delivery; never override the durable controller guard.
                    self.error='Automatic laser printing is held: '+str(error)
        except BaseException:
            if self.server:
                self.server.server_close()
            self.application_lock.__exit__(None,None,None)
            self.application_lock = None
            raise
        self.receiver_thread = threading.Thread(target=self.server.serve_forever,
            kwargs={'poll_interval':.1}, name='aurora-receiver', daemon=False)
        self.worker_thread = threading.Thread(target=self._work, name='aurora-print-worker', daemon=False)
        self.catalog_thread = threading.Thread(target=self._catalog, name='aurora-print-history', daemon=False)
        self.receiver_thread.start()
        self.catalog_thread.start()
        self.worker_thread.start()
        self._persist_status()

    def configure(self, host):
        with self.mutex:
            if self.mode != 'capture_only' or self.busy or self.probing or self.closing.is_set():
                raise ValueError('Switch to capture-only and finish the current operation before changing the laser address.')
            self.endpoint = Endpoint(host)
            write_json(self.root/'settings.json', {'schema_version':1, 'endpoint':asdict(self.endpoint)})
            self.connection, self.connection_raw = 'Not checked', ''

    def enable_live(self):
        with self.mutex:
            if self.closing.is_set() or self.mode != 'capture_only' or self.busy or self.probing:
                raise ValueError('Finish the current operation before enabling laser printing.')
            if self.server is None or self.stopped.is_set():
                raise ValueError('The print receiver is not running.')
            with DeviceGuard(self.endpoint.host, self.locks) as guard:
                guard.ensure_clear()
            session = str(uuid.uuid4())
            folder = self.session_root/session
            folder.mkdir(exist_ok=False)
            service = PrintService(folder, self.endpoint, self.intake, timing=self.timing, locks=self.locks)
            write_json(folder/'session.json', {'schema_version':1, 'id':session,
                'enabled_ns':time.time_ns(), 'endpoint':asdict(self.endpoint)})
            self.services[session] = service
            self.history_stores[session] = service.store
            self.cancelled[session] = set()
            self.session, self.service = session, service
            self.error = ''
            self.mode = 'live'
            # A request snapshots its destination at the start of its LPR job.
            # Files received before this switch can never enter this fresh folder.
            self.server.routes[b'aurora-direct'] = service.captures
            self._persist_status()
            self.wake.set()
            return session

    def capture_only(self):
        with self.mutex:
            if self.server:
                self.server.routes[b'aurora-direct'] = self.capture_root
            self.mode = 'finishing_current' if self.current_print else 'capture_only'
            self._persist_status()
            self.wake.set()

    def _select_capture(self, session, print_id):
        with self.mutex:
            if (self.mode != 'live' or self.session != session or self.closing.is_set()
                    or print_id in self.cancelled[session]):
                return False
            self.current_print = print_id
            self._persist_status()
            return True

    def cancel_pending(self, print_id):
        with self.mutex:
            item = self.inventory.get(print_id)
            if not item or item['session'] is None or print_id == self.current_print:
                raise ValueError('Only a waiting print can be canceled here. A current delivery must finish.')
            session = item['session']
            for job in self.history_stores[session].list():
                if job['settings'].get('direct_print',{}).get('print_id') == print_id:
                    raise ValueError('This print has already been processed; its delivery cannot be canceled here.')
            directory = self.session_root/session/'cancelled'
            directory.mkdir(exist_ok=True)
            write_json(directory/(print_id+'.json'), {'print_id':print_id, 'cancelled_ns':time.time_ns()})
            self.cancelled[session].add(print_id)
            self.wake.set()

    def check_connection(self):
        with self.mutex:
            if self.busy or self.current_print or self.probing or self.closing.is_set():
                raise ValueError('Wait until the current operation finishes before checking the connection.')
            self.probing = True
            self.connection = 'Checking…'
            endpoint = self.endpoint
        threading.Thread(target=self._probe, args=(endpoint,), name='aurora-status-check', daemon=False).start()

    def _probe(self, endpoint):
        try:
            # Status-only channel; never opens the job or recovery channel.
            with DeviceGuard(endpoint.host, self.locks):
                with socket.create_connection((endpoint.host,endpoint.status_port),timeout=2) as client:
                    client.settimeout(2)
                    client.sendall(STATUS_REQUEST)
                    frame = bytearray()
                    while len(frame)<8:
                        part=client.recv(8-len(frame))
                        if not part:
                            raise ConnectionError('The laser closed its status connection.')
                        frame.extend(part)
                    status=decode_status_reply(bytes(frame))
            with self.mutex:
                self.connection = 'Laser responded'
                self.connection_raw = status.raw_hex
        except Exception as error:
            with self.mutex:
                self.connection = 'No status response'
                self.connection_raw = str(error)
        finally:
            with self.mutex:
                self.probing = False
            self.wake.set()

    def resolve(self, print_id, outcome, note):
        with self.mutex:
            if self.mode != 'capture_only' or self.busy or self.probing:
                raise ValueError('Switch to capture-only and finish the current operation first.')
            if not note.strip():
                raise ValueError('Describe what happened at the laser.')
            for store in self.history_stores.values():
                for job in store.list():
                    if job['settings'].get('direct_print',{}).get('print_id') == print_id:
                        result=resolve_job(store,job['id'],outcome,note,locks=self.locks)
                        previous_error=self.capture_errors.pop(print_id,None)
                        if self.error == previous_error:
                            self.error=''
                        self._persist_status()
                        self.wake.set()
                        return result
            raise ValueError('Select a print with a delivery record.')

    def _collect(self):
        folders=[(None,self.capture_root)]
        folders.extend((p.name,p/'captures') for p in self.session_root.iterdir() if p.is_dir())
        for session, folder in folders:
            for directory in folder.iterdir():
                # The receiver publishes a UUID directory only after a clean
                # LPR close. Do not descend into .receiving-* even to glob:
                # an open Windows directory-search handle can block rename.
                if directory.name.startswith('.') or not directory.is_dir():
                    continue
                receipt=directory/'capture.json'
                if not receipt.is_file():
                    continue
                stamp=receipt.stat().st_mtime_ns
                if self.inventory_stamps.get(str(receipt)) == stamp:
                    continue
                data=json.loads(receipt.read_text())
                print_id=data['id']
                if str(uuid.UUID(print_id)) != print_id or receipt.parent.name != print_id:
                    raise ValueError('Invalid capture identifier in the desktop history.')
                item={'id':print_id,'session':session,'received_ns':data.get('received_ns',0),
                      'name':data.get('lpr_metadata',{}).get('J',['Print job'])[0],
                      'bytes':data['files']['document']['bytes'],'settings':None,'error':''}
                try:
                    item['settings']=settings_from_xps(receipt.parent/'source.bin')
                except Exception as error:
                    item['error']=str(error)
                with self.mutex:
                    self.inventory[print_id]=item
                    self.inventory_stamps[str(receipt)]=stamp

    def snapshot(self):
        with self.mutex:
            rows={key:dict(value) for key,value in self.inventory.items()}
            for print_id,item in rows.items():
                session=item['session']
                item['state']='captured_locally' if session is None else 'held'
                if session==self.session and self.mode=='live':
                    item['state']='waiting'
                if print_id==self.current_print:
                    item['state']='converting'
                if print_id in self.cancelled.get(session,set()):
                    item['state']='canceled'
                if item['error']:
                    item['state']='needs_attention'
                if print_id in self.capture_errors:
                    item['state']='needs_attention'
                    item['error']=self.capture_errors[print_id]
                item['job_id']=None
                item['delivery']=None
            for session,store in self.history_stores.items():
                for outcome in store.print_outcomes():
                    if outcome['print_id'] in rows:
                        rows[outcome['print_id']].update(state=outcome['state'],error='',
                            notice=outcome['message'],settings=outcome['printer_settings'])
                for job in store.list():
                    print_id=job['settings'].get('direct_print',{}).get('print_id')
                    if print_id not in rows:
                        continue
                    rows[print_id].update(state=job['state'],job_id=job['id'],error=job['error'] or '')
                    if session != self.session and job['state'] in ('queued','preparing','ready'):
                        rows[print_id]['state']='held'
                    if job['state'] in ('completed','completed_with_warning','delivery_unknown','delivery_failed'):
                        rows[print_id]['delivery']=store.get(job['id'])['delivery']
            return {'mode':self.mode,'controller':self.endpoint.host,'connection':self.connection,
                    'connection_detail':self.connection_raw,'error':self.error,
                    'current_print':self.current_print,'busy':self.busy,'probing':self.probing,
                    'closing':self.closing.is_set(),'stopped':self.stopped.is_set(),
                    'rows':sorted(rows.values(),key=lambda item:item['received_ns'],reverse=True)}

    def _persist_status(self):
        write_json(self.root/'desktop-status.json', {'mode':self.mode,'controller':self.endpoint.host,
            'session':self.session,'current_print':self.current_print,'error':self.error,
            'preferences_schema_version':2,'classic_preferences_versions':[1,2],
            'print_pipeline_version':4,'vector_only_dpi':[167],
            'per_color_vector_dpi':[167],
            'per_color_raster_dpi':[167],'per_color_mixed_dpi':[167],
            'cut_selection':'hairline-width-any-color',
            'updated_ns':time.time_ns()})

    def _catalog(self):
        while not self.catalog_stop.is_set():
            try:
                self._collect()
            except Exception as error:
                LOG.exception('Could not refresh local print history')
                with self.mutex:
                    self.error=str(error)
                self.capture_only()
            self.catalog_stop.wait(.25)

    def _work(self):
        try:
            while not self.closing.is_set():
                with self.mutex:
                    service=self.service if self.mode=='live' and not self.probing else None
                    session=self.session
                    self.busy=service is not None
                if service:
                    try:
                        service.poll_once(capture_filter=lambda print_id:self._select_capture(session,print_id))
                    except Exception as error:
                        LOG.exception('Automatic print stopped')
                        with self.mutex:
                            self.error=str(error)
                            if self.current_print:
                                self.capture_errors[self.current_print]=str(error)
                            self.mode='capture_only'
                            self.server.routes[b'aurora-direct']=self.capture_root
                    finally:
                        with self.mutex:
                            self.current_print=None
                            self.busy=False
                            if self.mode=='finishing_current':
                                self.mode='capture_only'
                            self._persist_status()
                self.wake.wait(.25)
                self.wake.clear()
        except Exception as error:
            LOG.exception('JobServer background worker stopped')
            with self.mutex:
                self.error=str(error)
                self.mode='capture_only'
                self.server.routes[b'aurora-direct']=self.capture_root
                self.busy=False
        finally:
            # Close the listener first, then finish all accepted LPR receives.
            # Any files arriving during an active-job shutdown remain local.
            self.server.shutdown()
            self.receiver_thread.join()
            while self.server.active_requests() or self.probing:
                time.sleep(.05)
            self.server.server_close()
            self.catalog_stop.set()
            self.catalog_thread.join()
            try:
                self._collect()
            except Exception:
                LOG.exception('Could not finish refreshing print history')
            finally:
                if self.application_lock:
                    self.application_lock.__exit__(None,None,None)
                self.stopped.set()

    def close(self):
        self.capture_only()
        self.closing.set()
        self.wake.set()

    def wait_closed(self, timeout=None):
        return self.stopped.wait(timeout)
