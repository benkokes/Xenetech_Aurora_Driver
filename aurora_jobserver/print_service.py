"""XP-style automatic print bridge host. Starting it enables delivery on Print.

Development host; no startup/service registration is performed. Requires the
dedicated Aurora driver, its job-attached settings and a selected controller.
"""
import argparse
import json
from pathlib import Path
import threading
import time
import uuid

from .direct_print import DirectPrintBridge
from .print_capture import CaptureServer
from .print_pipeline import prepare_capture
from .store import JobStore, atomic_write
from .transport import Endpoint
from .worker import WorkerLock


class PrintService:
    def __init__(self, root, endpoint, intake_executable, *, timing=None, locks=None,
                 allow_color_vectors=True,allow_color_rasters=True):
        if type(allow_color_vectors) is not bool:
            raise ValueError('Color-vector validation permission must be an explicit boolean')
        self.root = Path(root).resolve()
        self.captures = self.root / 'captures'
        self.captures.mkdir(parents=True,exist_ok=True)
        self.store = JobStore(self.root / 'queue')
        self.bridge = DirectPrintBridge(self.store,endpoint,timing=timing,locks=locks)
        self.intake_executable = Path(intake_executable)
        self.allow_color_vectors = allow_color_vectors
        if type(allow_color_rasters) is not bool:
            raise ValueError('Color-raster validation permission must be an explicit boolean')
        self.allow_color_rasters=allow_color_rasters

    def status(self, state, **detail):
        result = {'state':state, 'updated_ns':time.time_ns(), **detail}
        atomic_write(self.root / 'status.json',json.dumps(result,indent=2).encode())
        print(json.dumps(result),flush=True)

    def poll_once(self, capture_filter=None):
        # Another service host must not convert/dispatch simultaneously. This
        # lock is separate from the queue worker lock used during preparation.
        with WorkerLock(self.root,'print-service.lock'):
            captures = []
            for folder in self.captures.iterdir():
                if not folder.is_dir() or folder.name.startswith('.'):
                    continue
                try:
                    if str(uuid.UUID(folder.name)) != folder.name:
                        continue
                except ValueError:
                    continue
                receipt = json.loads((folder / 'capture.json').read_text())
                captures.append((receipt.get('received_ns',0),folder.name,folder))
            local_outcomes={p['print_id'] for p in self.store.print_outcomes()}
            for _, print_id, folder in sorted(captures):
                with self.store.connect() as db:
                    accepted = db.execute('SELECT job_id FROM receipts WHERE token=?',
                                          ('direct-print:'+print_id,)).fetchone()
                if accepted or print_id in local_outcomes:
                    continue
                if capture_filter is not None and not capture_filter(print_id):
                    continue
                self.status('converting',print_id=print_id)
                output = self.root / 'prepared-prints' / print_id
                result = prepare_capture(folder,output,self.intake_executable,
                                         allow_color_vectors=self.allow_color_vectors,
                                         allow_color_rasters=self.allow_color_rasters)
                if result['state'] in ('nothing_to_cut','nothing_to_print'):
                    self.store.record_no_cut(result)
                    self.status(result['state'],print_id=print_id,message=result['message'])
                    return {'id':print_id,'state':result['state'],'delivery':None}
                self.bridge.accept(output / 'job.cg.jbs',print_id,result['printer_settings'])
                # Preserve arrival order; a later Print cannot overtake this one.
                break
            result = self.bridge.step()
            if result:
                self.status(result['state'],job_id=result['id'],delivery=result['delivery'])
            return result


def run_host(service, server, *, once=False):
    """Receive and dispatch, optionally stopping after one completed print."""
    thread = threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.25},daemon=True)
    thread.start()
    service.status('listening_for_direct_print',queue='aurora-direct',address=server.server_address,
                   controller=service.bridge.endpoint.host,stop_after_one_print=once)
    try:
        while True:
            result = service.poll_once()
            if result is None:
                time.sleep(.25)
            elif once:
                # poll_once returns only after completed delivery; failures raise.
                # Later captures stay retained and are never dispatched here.
                service.status('stopped_after_one_print',job_id=result['id'],
                               delivery_state=result['state'])
                return
    except KeyboardInterrupt:
        service.status('stopped')
    except Exception as error:
        service.status('needs_attention',error=str(error))
        raise
    finally:
        server.shutdown()
        thread.join()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('runtime/direct-print-service'))
    parser.add_argument('--host',required=True,help='Controller IPv4; prints will be sent automatically')
    parser.add_argument('--main-port',type=int,default=23)
    parser.add_argument('--status-port',type=int,default=29)
    parser.add_argument('--realtime-port',type=int,default=30)
    parser.add_argument('--recovery-port',type=int,default=99)
    parser.add_argument('--listen-port',type=int,default=515)
    parser.add_argument('--preview-root',type=Path,default=Path('runtime/print-capture'))
    parser.add_argument('--intake',type=Path,default=Path('build/frontend/Aurora.XpsIntake.exe'))
    parser.add_argument('--once',action='store_true',help='Stop after one completed print')
    parser.add_argument('--require-empty',action='store_true',help='Refuse any existing service backlog')
    args = parser.parse_args(argv)
    if args.require_empty and args.root.exists() and (not args.root.is_dir() or any(args.root.iterdir())):
        parser.error('Use a new empty service root; existing captures and queues must not enter this test')
    if not args.intake.is_file():
        parser.error('Build the XPS intake before starting the print bridge')
    service = PrintService(args.root,Endpoint(args.host,args.main_port,args.status_port,
                           args.realtime_port,args.recovery_port),args.intake)
    with CaptureServer(service.captures,args.listen_port,queue='aurora-direct',
                       routes={'aurora-capture':args.preview_root}) as server:
        run_host(service,server,once=args.once)


if __name__ == '__main__':
    main()
