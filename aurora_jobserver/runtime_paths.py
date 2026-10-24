"""Separate installed application resources from writable per-user records."""
import os
from pathlib import Path
import sys


def frozen():
    return bool(getattr(sys,'frozen',False))


def project_root():
    return Path(__file__).resolve().parents[1]


def bundle_root():
    return Path(getattr(sys,'_MEIPASS',project_root())).resolve()


def user_root():
    local=os.environ.get('LOCALAPPDATA')
    if not local or not Path(local).is_absolute():
        raise ValueError('Windows LOCALAPPDATA must name an absolute writable user directory')
    return Path(local)/'AuroraJobServer'


def default_state():
    return user_root()/'state' if frozen() else project_root()/'runtime/desktop-jobserver'


def default_locks():
    return user_root()/'device-locks' if frozen() else project_root()/'runtime/device-locks'


def intake_path():
    return bundle_root()/'native/Aurora.XpsIntake.exe' if frozen() else project_root()/'build/frontend/Aurora.XpsIntake.exe'


def preview_root(state):
    return Path(state)/'preview-captures' if frozen() else project_root()/'runtime/print-capture'
