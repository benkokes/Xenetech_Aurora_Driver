"""Exercise the new window, settings details and graceful close on loopback."""
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aurora_jobserver.desktop_server import DesktopJobServer
from aurora_jobserver.desktop_gui import JobServerWindow, tk, ROOT
from aurora_jobserver.printer_settings import default_selection, decode


def main():
    with tempfile.TemporaryDirectory() as temporary:
        backend=DesktopJobServer(temporary,ROOT/'build/frontend/Aurora.XpsIntake.exe',port=0)
        root=tk.Tk()
        root.withdraw()
        backend.start()
        errors=[]
        root.report_callback_exception=lambda kind,value,traceback:errors.append(str(value))
        with patch('aurora_jobserver.desktop_gui.startup.enabled',return_value=False):
            window=JobServerWindow(root,backend)
        # Representative actual receipt settings and controller warning.
        row={'id':'00000000-0000-4000-8000-000000000001','session':None,'received_ns':1,
             'name':'Square and TEST','bytes':72743,'settings':decode(default_selection()),'error':''}
        with backend.mutex:
            backend.inventory[row['id']]=row
        window.refresh()
        assert window.tree.get_children()==(row['id'],)
        assert '45% at 30 ips' in window.details.get('1.0','end')
        assert '15% at 1 ips' in window.details.get('1.0','end')
        assert str(window.enable['state'])=='normal'
        assert str(window.cancel['state'])=='disabled'
        # A controller warning and a physical-resolution record must also display.
        window.rows[row['id']].update(state='completed_with_warning',delivery={'result':{
            'job_time':9.798,'warnings':[{'code':2,'message':"Token 'set_xyup_feed' not found."}]}})
        window.show_details()
        assert '9.798 seconds' in window.details.get('1.0','end')
        assert "Token 'set_xyup_feed'" in window.details.get('1.0','end')
        root.after(500,window.close)
        root.mainloop()
        assert backend.wait_closed(5)
        if errors:
            raise RuntimeError('; '.join(errors))
    print('Desktop window settings, warning display and graceful-close smoke check passed')


if __name__=='__main__':
    main()
