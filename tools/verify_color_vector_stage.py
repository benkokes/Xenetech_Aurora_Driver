"""Verify a staged color job once against a controller bound ONLY to loopback."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from aurora_jobserver.direct_print import DirectPrintBridge
from aurora_jobserver.store import JobStore
from aurora_jobserver.transport import Timing
from tools.controller_simulator import ControllerSimulator


def verify(staging, destination):
    staging, destination=Path(staging),Path(destination)
    if destination.exists():
        raise ValueError('Verification destination already exists')
    report=json.loads((staging/'staging.json').read_text(encoding='utf-8'))
    prepared=staging/'prepared'
    result=json.loads((prepared/'print-job.json').read_text(encoding='utf-8'))
    source=prepared/'job.cg.jbs'
    data=source.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    if (digest!=report['cg_sha256'] or digest!=result['cg_sha256']
            or result['state']!='encoded_for_direct_print'):
        raise ValueError('Staged color job changed')
    original_connect=socket.create_connection
    def loopback_only(address,*args,**kwargs):
        if address[0]!='127.0.0.1':
            raise AssertionError('Physical connection forbidden in stage verification')
        return original_connect(address,*args,**kwargs)
    timing=Timing(connect=1,handshake=1,job=3,sync_delay=.005,feature_delay=.005,sync_quiet=.005)
    with ControllerSimulator(data,echo=False,fragment=True) as simulator, patch('socket.create_connection',side_effect=loopback_only):
        store=JobStore(destination/'queue')
        bridge=DirectPrintBridge(store,simulator.endpoint,timing=timing,locks=destination/'locks')
        job=bridge.accept(source,result['print_id'],result['printer_settings'])
        delivered=bridge.step()
        if delivered['state']!='completed' or not simulator.upload_received.is_set():
            raise AssertionError('Staged job did not complete in the simulator')
        if bridge.step() is not None:
            raise AssertionError('Staged print was dispatched twice')
        uploads=sum(event['kind']=='uploaded' for event in store.history(job))
        if uploads!=1:
            raise AssertionError('Expected exactly one simulated upload')
        retained=(store.directory(job)/'prepared.jbs').read_bytes()
        if retained!=data:
            raise AssertionError('Queued bytes differ from the staged job')
    verification={'state':'exact_staged_job_completed_once_on_loopback',
        'cg_sha256':digest,'simulator_endpoint':'127.0.0.1',
        'simulated_upload_count':uploads,'physical_device_io':False,
        'real_controller_report':False,'hardware_acceptance_still_required':True}
    (destination/'verification.json').write_text(json.dumps(verification,indent=2)+'\n',encoding='utf-8')
    return verification


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staging',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    print(json.dumps(verify(args.staging,args.destination)))


if __name__=='__main__':
    main()
