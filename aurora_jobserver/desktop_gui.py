"""Normal JobServer window: CorelDRAW prints automatically when live is enabled."""
import argparse
from datetime import datetime
import json
import logging
import math
from logging.handlers import RotatingFileHandler
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .desktop_server import DesktopJobServer
from . import startup
from . import runtime_paths


ROOT=Path(__file__).resolve().parents[1]
LABELS={'captured_locally':'Captured locally','waiting':'Waiting','held':'Held — not sent',
        'converting':'Converting artwork',
        'canceled':'Canceled','queued':'Queued','preparing':'Preparing','ready':'Ready',
        'connecting':'Connecting','uploading':'Sending','awaiting_report':'At laser — awaiting report',
        'completed':'Completed','completed_with_warning':'Completed — warning',
        'delivery_unknown':'Check physical outcome','delivery_failed':'Delivery failed',
        'failed':'Conversion failed','needs_attention':'Needs attention','nothing_to_cut':'Nothing to cut — not sent',
        'nothing_to_print':'Nothing to print — not sent'}


def valid_seconds(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0


def local_timestamp(value, *, full=False):
    if not valid_seconds(value):
        return '—'
    try:
        stamp=datetime.fromtimestamp(value)
        if full:
            stamp=stamp.astimezone()
        return stamp.strftime('%Y-%m-%d %H:%M:%S %Z' if full else '%m/%d %H:%M:%S')
    except (OverflowError,OSError,ValueError):
        return '—'


def duration_text(seconds):
    if not valid_seconds(seconds):
        return '—'
    try:
        milliseconds=round(seconds*1000)
    except OverflowError:
        return '—'
    minutes,remainder=divmod(milliseconds,60000)
    hours,minutes=divmod(minutes,60)
    return (f'{hours}:{minutes:02d}:{remainder/1000:06.3f}' if hours
            else f'{minutes}:{remainder/1000:06.3f}')


def completion_timing(row):
    """Use the recorded completion reply, never upload/queue elapsed time.

    An operator-confirmed completion has no measured finish time or duration.
    Its reconciliation timestamp must not masquerade as the physical finish.
    """
    delivery=row.get('delivery') or {}
    result=delivery.get('result') or {}
    if row.get('state') not in ('completed','completed_with_warning') or result.get('operator_outcome') or not result:
        return None,None
    completed=delivery.get('updated')
    duration=result.get('job_time')
    return (completed if valid_seconds(completed) else None,
            duration if valid_seconds(duration) else None)


def history_values(row):
    raster=vector='—'
    if row.get('settings'):
        process=row['settings']['process_settings']
        raster=f"{process['raster_power_percent']}% / {process['raster_speed_native']/1000:g} ips"
        vector=f"{process['vector_power_percent']}% / {process['vector_speed_native']/1000:g} ips / {process['vector_ppi']} PPI"
        if row['settings'].get('classic_preferences',{}).get('UseColors'):
            raster='Off' if row['settings'].get('output_mode')=='vector-only' else 'Per-color'
            vector='Off' if row['settings'].get('output_mode')=='raster-only' else 'Per-color'
    completed,duration=completion_timing(row)
    return (row['name'],LABELS.get(row['state'],row['state']),raster,vector,
            local_timestamp(row['received_ns']/1e9),local_timestamp(completed),duration_text(duration))


def palette_detail_lines(settings):
    preferences=settings.get('classic_preferences',{})
    if not preferences.get('UseColors'):
        return []
    lines=['Color palette (saved with this print):']
    for color in preferences.get('Colors',[]):
        if color['Enabled']:
            lines.append(f"  {color['Name']}: {color['PowerPercent']}% at {color['SpeedIps']} ips; {color['Ppi']} PPI")
    if len(lines)==1:
        lines.append('  No enabled colors.')
    return lines


class JobServerWindow:
    def __init__(self, root, backend):
        self.root, self.backend=root,backend
        root.title('Aurora JobServer')
        root.geometry('1280x680')
        root.minsize(920,540)
        style=ttk.Style(root)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        outer=ttk.Frame(root,padding=18)
        outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='Aurora JobServer',font=('Segoe UI',20,'bold')).pack(anchor='w')
        self.mode=tk.StringVar(value='Capture only')
        self.explanation=tk.StringVar(value='CorelDRAW prints are saved locally.')
        self.banner=ttk.Label(outer,textvariable=self.mode,font=('Segoe UI',14,'bold'))
        self.banner.pack(anchor='w',pady=(12,2))
        ttk.Label(outer,textvariable=self.explanation).pack(anchor='w')
        controls=ttk.Frame(outer)
        controls.pack(fill='x',pady=(14,10))
        self.enable=ttk.Button(controls,text='Enable laser printing',command=lambda:self.guard(self.enable_live))
        self.enable.pack(side='left',padx=(0,8))
        self.capture=ttk.Button(controls,text='Capture only',command=lambda:self.guard(backend.capture_only))
        self.capture.pack(side='left',padx=(0,24))
        ttk.Label(controls,text='Laser IP:').pack(side='left')
        self.host=tk.StringVar(value=backend.endpoint.host)
        self.host_entry=ttk.Entry(controls,textvariable=self.host,width=16)
        self.host_entry.pack(side='left',padx=(6,8))
        self.check=ttk.Button(controls,text='Check connection',command=lambda:self.guard(self.check_connection))
        self.check.pack(side='left')
        self.connection=tk.StringVar(value='Connection: not checked')
        ttk.Label(outer,textvariable=self.connection).pack(anchor='w',pady=(0,10))

        table=ttk.Frame(outer)
        table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,columns=('name','status','raster','vector','time','completed','duration'),show='headings',selectmode='browse')
        for key,label,width in [('name','Document',210),('status','Status',190),('raster','Raster',150),
                                ('vector','Vector',200),('time','Received',135),
                                ('completed','Completed',135),('duration','Duration',110)]:
            self.tree.heading(key,text=label)
            self.tree.column(key,width=width,minwidth=150 if key=='name' else width,
                             stretch=key=='name',anchor='e' if key=='duration' else 'w')
        scroll=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview)
        horizontal=ttk.Scrollbar(table,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set,xscrollcommand=horizontal.set)
        self.tree.grid(row=0,column=0,sticky='nsew')
        scroll.grid(row=0,column=1,sticky='ns')
        horizontal.grid(row=1,column=0,sticky='ew')
        table.rowconfigure(0,weight=1);table.columnconfigure(0,weight=1)
        actions=ttk.Frame(outer)
        actions.pack(fill='x',pady=(10,8))
        self.cancel=ttk.Button(actions,text='Cancel waiting print',command=lambda:self.guard(self.cancel_selected))
        self.cancel.pack(side='left',padx=(0,8))
        self.outcome=ttk.Button(actions,text='Record physical outcome…',command=lambda:self.guard(self.resolve_selected))
        self.outcome.pack(side='left')
        self.startup=tk.BooleanVar(value=startup.enabled(backend.root))
        ttk.Checkbutton(actions,text='Open JobServer when I sign in',variable=self.startup,
                        command=lambda:self.guard(self.set_startup)).pack(side='right')
        self.details=tk.Text(outer,height=8,wrap='word',font=('Segoe UI',10),state='disabled')
        self.details.pack(fill='x')
        self.footer=tk.StringVar(value='Waiting for a CorelDRAW print.')
        ttk.Label(outer,textvariable=self.footer).pack(anchor='w',pady=(8,0))
        self.rows={}
        self.last_rows=None
        self.last_snapshot={}
        self.tree.bind('<<TreeviewSelect>>',self.show_details)
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh()

    def guard(self, action):
        try:
            action()
        except Exception as error:
            messagebox.showerror('Aurora JobServer',str(error),parent=self.root)

    def configure(self):
        if self.host.get().strip()!=self.backend.endpoint.host:
            self.backend.configure(self.host.get().strip())

    def enable_live(self):
        self.configure()
        if messagebox.askyesno('Enable laser printing',
                'New CorelDRAW prints will be sent automatically to '+self.backend.endpoint.host+
                '.\n\nPrepare the laser, material and focus before printing.\nEnable laser printing?',parent=self.root):
            self.backend.enable_live()

    def check_connection(self):
        self.configure()
        self.backend.check_connection()

    def selected(self):
        selected=self.tree.selection()
        if not selected:
            raise ValueError('Select a print first.')
        return self.rows[selected[0]]

    def cancel_selected(self):
        self.backend.cancel_pending(self.selected()['id'])

    def resolve_selected(self):
        row=self.selected()
        outcome=simpledialog.askstring('Record physical outcome',
            'After checking that the laser is idle, enter:\n'
            'completed — the print finished\n'
            'not_started — it never ran\n'
            'stopped — it started but was stopped before finishing\n\n'
            'This records the result; it does not resend the job.',parent=self.root)
        if outcome is None:
            return
        if outcome not in ('completed','not_started','stopped'):
            raise ValueError('Enter completed, not_started, or stopped.')
        note=simpledialog.askstring('Physical observation','Describe what you observed at the laser:',parent=self.root)
        if note is not None:
            self.backend.resolve(row['id'],outcome,note)

    def set_startup(self):
        try:
            startup.set_enabled(self.backend.root,self.startup.get())
        except Exception:
            self.startup.set(startup.enabled(self.backend.root))
            raise

    def show_details(self, event=None):
        lines=['Select a print to see its settings and result.']
        selected=self.tree.selection()
        if selected and selected[0] in self.rows:
            row=self.rows[selected[0]]
            lines=[row['name']+' — '+LABELS.get(row['state'],row['state'])]
            settings=row.get('settings')
            if settings:
                p=settings['process_settings']
                if settings.get('classic_preferences',{}).get('UseColors'):
                    raster='Off (Vector Only)' if settings.get('output_mode')=='vector-only' else 'Per-color'
                    vector='Off (Raster Only)' if settings.get('output_mode')=='raster-only' else 'Per-color'
                    lines += [f"Raster: {raster}; {settings['laser_dpi']} DPI",f'Vector: {vector}']
                else:
                    lines += [f"Raster: {p['raster_power_percent']}% at {p['raster_speed_native']/1000:g} ips; {settings['laser_dpi']} DPI",
                              f"Vector: {p['vector_power_percent']}% at {p['vector_speed_native']/1000:g} ips; {p['vector_ppi']} PPI"]
                lines.append('Autostart: '+('On' if settings['autostart'] else 'Off — use the machine Start button'))
                lines.append('Output mode: '+{'raster-and-vector':'Both Raster and Vector','raster-only':'Raster Only','vector-only':'Vector Only'}.get(settings.get('output_mode'),'Unknown'))
                lines += palette_detail_lines(settings)
            if row['error']:
                lines.append(row['error'])
            if row.get('notice'):
                lines.append(row['notice'])
            completed,duration=completion_timing(row)
            if completed is not None:
                lines.append('Completed: '+local_timestamp(completed,full=True)+' (completion report received)')
            delivery=row.get('delivery')
            if delivery and delivery.get('result'):
                result=delivery['result']
                if result.get('operator_outcome'):
                    lines.append('Observed outcome: '+result['operator_outcome']+' — '+result.get('note',''))
                if duration is not None:
                    lines.append(f"Duration: {duration_text(duration)} ({duration:.3f} seconds reported by laser)")
                lines += [f"Warning {warning['code']}: {warning['message']}" for warning in result.get('warnings',[])]
            lines.append('Print ID: '+row['id'])
        self.details.configure(state='normal')
        self.details.delete('1.0','end')
        self.details.insert('1.0','\n'.join(lines))
        self.details.configure(state='disabled')

    def refresh(self):
        state=self.backend.snapshot()
        self.last_snapshot=state
        self.rows={item['id']:item for item in state['rows']}
        mode=state['mode']
        if state['closing']:
            self.mode.set('Finishing and closing…')
            self.explanation.set('The current job and accepted print transfers will finish before JobServer closes.')
        elif state['stopped']:
            self.mode.set('JobServer stopped')
            self.explanation.set('Close and reopen JobServer to restart the receiver.')
        elif mode=='live':
            self.mode.set('Laser printing enabled')
            self.explanation.set('New CorelDRAW prints go automatically to '+state['controller']+'.')
        elif mode=='finishing_current':
            self.mode.set('Finishing current print')
            self.explanation.set('Later prints are being captured locally.')
        else:
            self.mode.set('Capture only')
            self.explanation.set('CorelDRAW prints are saved locally. Laser delivery is disabled.')
        self.connection.set('Connection: '+state['connection']+
                            (' — '+state['connection_detail'] if state['connection_detail'] else ''))
        idle=not(state['busy'] or state['probing'] or state['closing'] or state['stopped'])
        self.enable.configure(state='normal' if idle and mode=='capture_only' else 'disabled')
        self.capture.configure(state='normal' if not state['closing'] and mode!='capture_only' else 'disabled')
        self.host_entry.configure(state='normal' if idle and mode=='capture_only' else 'disabled')
        self.check.configure(state='normal' if idle else 'disabled')
        signature=json.dumps(state['rows'],sort_keys=True)
        if signature!=self.last_rows:
            selected=self.tree.selection()
            self.tree.delete(*self.tree.get_children())
            for row in state['rows']:
                self.tree.insert('', 'end',iid=row['id'],values=history_values(row))
            if selected and self.tree.exists(selected[0]):
                self.tree.selection_set(selected[0])
            elif state['rows']:
                self.tree.selection_set(state['rows'][0]['id'])
            self.last_rows=signature
            self.show_details()
        self.footer.set(state['error'] or (str(len(state['rows']))+' print(s) in history.'))
        selected=self.tree.selection()
        row=self.rows.get(selected[0]) if selected else None
        waiting=row and row['session'] and row['state'] in ('waiting','held') and row['id']!=state['current_print']
        self.cancel.configure(state='normal' if waiting and not state['closing'] else 'disabled')
        unresolved=row and row['state']=='delivery_unknown'
        self.outcome.configure(state='normal' if unresolved and idle and mode=='capture_only' else 'disabled')
        if state['closing'] and state['stopped']:
            self.root.destroy()
            return
        self.root.after(350,self.refresh)

    def close(self):
        self.backend.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,default=runtime_paths.default_state())
    parser.add_argument('--listen-port',type=int,default=515)
    parser.add_argument('--capture-only',action='store_true',help='Start with laser delivery disabled instead of the normal enabled default')
    parser.add_argument('--self-check-report',type=Path,help='Write an offline dependency check and exit; no receiver or device access')
    args=parser.parse_args(argv)
    if args.self_check_report:
        from .package_check import self_check
        return self_check(args.self_check_report)
    args.state.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(args.state/'jobserver.log',
                        maxBytes=2*1024*1024,backupCount=3,encoding='utf-8')])
    root=tk.Tk()
    root.withdraw()
    backend=None
    try:
        backend=DesktopJobServer(args.state,runtime_paths.intake_path(),port=args.listen_port,
                                 preview_root=runtime_paths.preview_root(args.state))
        backend.start(start_enabled=not args.capture_only)
        JobServerWindow(root,backend)
        root.deiconify()
        root.mainloop()
    except Exception as error:
        logging.exception('JobServer could not start')
        messagebox.showerror('Aurora JobServer',str(error),parent=root)
        return 1
    finally:
        if backend and backend.worker_thread and backend.worker_thread.is_alive():
            backend.close()
            backend.wait_closed()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
