"""Offline transfer plan for the one observed Aurora raster-job path.

These bytes are not a send-all script. Each gate must be satisfied in its own
phase. No sockets, retries, or physical job execution are implemented here.
"""
from dataclasses import dataclass
from pathlib import PureWindowsPath

from .jbs import prepare


SYNC = b'\nM99\n!ZX\n'
FEATURE_ZERO = b'\n0 dsp_feature 1 wchar\n'
FEATURE_ONE = b'1 dsp_feature 1 wchar\n'
PRE_JOB_TABLE = b'\n1 wchar pre_job_table\r'
TERMINATE = b'ifexists host_terminate host_terminate\n'


@dataclass(frozen=True)
class WireStep:
    name: str
    phase: str
    request: bytes
    gate: str
    minimum_delay_ms: int = 0


def raster_plan(job_data, controller_job_path):
    """Reproduce observed framing without guessing other jobtype branches.

controller_job_path is the textual JM_PATH value used by the old sender, not
an instruction to read or write that path on either computer.
"""
    prepared = prepare(job_data)
    if prepared.input_format != 'compressed' or not prepared.rasters:
        raise ValueError('This wire profile requires an already prepared CG raster job')
    path = PureWindowsPath(controller_job_path)
    if (not path.is_absolute() or path.suffix.lower() != '.jbs'
            or len(controller_job_path) > 1024
            or any(ord(char) < 33 or ord(char) > 126 for char in controller_job_path)):
        raise ValueError('Expected an absolute ASCII Windows .jbs path without whitespace')
    path_bytes = controller_job_path.encode('ascii')
    name = path.name.encode('ascii')
    upload = (b'\ncls\nmsg Preprocessing the job...\nifexists jobtype 5 jobtype\n'
              b'\ncls\nmsg Please Stand By...\nifexists JM_PATH JM_PATH ' + path_bytes
              + b'\n\rifexists HOTWATCH_CYCLE_START HOTWATCH_CYCLE_START ' + name + b'\n'
              + prepared.data)
    return (
        WireStep('attach_sync', 'connect', SYNC, 'sync_reply_drain', 500),
        WireStep('feature_sync', 'connect', SYNC, 'sync_reply_drain', 500),
        WireStep('feature_zero', 'connect', FEATURE_ZERO, 'decimal_feature_then_01', 200),
        WireStep('feature_one', 'connect', FEATURE_ONE, 'decimal_feature_then_01'),
        WireStep('job_sync', 'prepare', SYNC, 'sync_reply_drain', 500),
        WireStep('pre_job_table', 'prepare', PRE_JOB_TABLE, 'empty_01_04_table'),
        WireStep('upload', 'transfer', upload, 'channel_5_06_E0_06_then_ac'),
        WireStep('host_terminate', 'finish', TERMINATE, 'job_time_then_04_and_ac_observed'),
    )
