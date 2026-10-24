"""Offline frozen-application dependency check; never starts the print bridge."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

from . import runtime_paths


def self_check(report_path):
    report_path=Path(report_path)
    if report_path.exists():raise ValueError('Preserve prior self-check evidence; choose a new report')
    result={'schema_version':1,'state':'failed','frozen':runtime_paths.frozen(),
        'executable':sys.executable,'os':platform.platform(),'python':platform.python_version(),
        'desktop_default_printing':'enabled_for_new_submissions',
        'physical_device_io':False,'receiver_started':False,'startup_registration_changed':False}
    try:
        import tkinter as tk
        from .jbs import prepare
        from .color_rasters import ExposureSurface,plan_global_rasters,encode_raster_draft
        from .color_settings import ColorProcess
        from tools.compare_preference_jobs import decode
        root=tk.Tk();root.withdraw();result['tk_version']=root.tk.call('info','patchlevel');root.destroy()
        raw,cg=encode_raster_draft(plan_global_rasters(ExposureSurface(0,0,2,2,b'\xff\0\x80\xff'),
            ColorProcess(30000,45,1000)),'PackageCheck')
        assert decode(cg)['rasters'][0]['pixels']==b'\xff\0\x80\xff'
        try:prepare(cg)
        except ValueError:pass
        else:raise AssertionError('Draft delivery guard failed')
        reader=runtime_paths.intake_path()
        process=subprocess.run([str(reader)],capture_output=True,timeout=15)
        assert process.returncode==1 and b'Usage:' in process.stderr+process.stdout
        result.update(state='passed',codec_roundtrip=True,draft_guard=True,
            native_intake=str(reader),native_intake_sha256=hashlib.sha256(reader.read_bytes()).hexdigest(),
            native_intake_started=True,state_directory=str(runtime_paths.default_state()),
            locks_directory=str(runtime_paths.default_locks()))
    except Exception as error:
        result['error']=str(error)
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return 0 if result['state']=='passed' else 1
