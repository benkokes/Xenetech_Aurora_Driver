"""Optional per-user startup using the desktop's requested printing default."""
from pathlib import Path
import subprocess
import sys
from .runtime_paths import frozen


VALUE = 'Aurora JobServer'
KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'


def command(state):
    if frozen():
        return subprocess.list2cmdline([str(Path(sys.executable).resolve()),'--state',str(Path(state).resolve())])
    python = Path(sys.executable)
    windowed = python.with_name('pythonw.exe')
    if windowed.is_file():
        python = windowed
    script = Path(__file__).resolve().parents[1]/'run-desktop-jobserver.pyw'
    return subprocess.list2cmdline([str(python),str(script),'--state',str(Path(state).resolve())])


def enabled(state):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,KEY) as key:
            value,_ = winreg.QueryValueEx(key,VALUE)
            return value == command(state)
    except FileNotFoundError:
        return False


def set_enabled(state, enable):
    import winreg
    desired=command(state)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,KEY,0,winreg.KEY_READ|winreg.KEY_WRITE) as key:
        try:
            existing,_=winreg.QueryValueEx(key,VALUE)
        except FileNotFoundError:
            existing=None
        if existing is not None and existing != desired:
            raise ValueError('A different Aurora startup entry already exists; it was left unchanged.')
        if enable:
            winreg.SetValueEx(key,VALUE,0,winreg.REG_SZ,desired)
        elif existing is not None:
            winreg.DeleteValue(key,VALUE)
