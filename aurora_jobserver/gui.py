"""Desktop queue UI; preparation is automatic, delivery is explicit via CLI."""
from datetime import datetime
import json
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .worker import InboxWatcher, WorkerLock, process_one


def run(store):
    lock = WorkerLock(store.root)
    with lock:
        store.recover()
        root = tk.Tk()
        root.title("Aurora JobServer")
        root.geometry("1060x650")
        root.minsize(800, 480)
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        outer = ttk.Frame(root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Aurora JobServer", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Local queue • Experimental Ethernet delivery uses the explicit send command").pack(anchor="w", pady=(4, 12))
        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(0, 10))
        columns = ("name", "state", "size", "created")
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse", height=12)
        labels = ("Job", "Status", "Prepared bytes", "Added")
        for column, label, width in zip(columns, labels, (310, 190, 130, 190)):
            tree.heading(column, text=label)
            tree.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        details = tk.Text(outer, height=9, wrap="word", font=("Consolas", 10), state="disabled")
        details.pack(fill="x", pady=(10, 8))
        footer = tk.StringVar(value=f"Watching {store.root / 'inbox'}")
        ttk.Label(outer, textvariable=footer).pack(anchor="w")
        stopped = threading.Event()
        notices = queue.Queue()
        last_rows = None

        def selected():
            selection = tree.selection()
            if not selection:
                raise ValueError("Select a job first")
            return selection[0]

        def guarded(action):
            try:
                action()
            except Exception as exc:
                messagebox.showerror("Aurora JobServer", str(exc), parent=root)

        def add():
            paths = filedialog.askopenfilenames(parent=root, title="Add engraving jobs",
                                              filetypes=[("Xenetech jobs", "*.jbs"), ("All files", "*.*")])
            for path in paths:
                store.submit(path)

        def export():
            job_id = selected()
            job = store.get(job_id)
            if job["state"] != "ready":
                raise ValueError("Select a ready job")
            path = filedialog.asksaveasfilename(parent=root, title="Export prepared job", defaultextension=".jbs",
                                              initialfile=job["source_name"], filetypes=[("Xenetech job", "*.jbs")])
            if path:
                store.export(job_id, path)

        for text, action in (("Add job…", add), ("Export prepared…", export),
                             ("Cancel", lambda: store.cancel(selected())), ("Retry", lambda: store.retry(selected()))):
            ttk.Button(buttons, text=text, command=lambda fn=action: guarded(fn)).pack(side="left", padx=(0, 8))

        def show_details(_=None):
            selection = tree.selection()
            text = "Select a job to see its history."
            if selection:
                job = store.get(selection[0])
                history = store.history(selection[0])
                lines = [f"ID: {job['id']}", f"Source: {job['source_name']}   Format: {job['input_format'] or 'pending'}",
                         f"Rasters: {job['rasters'] if job['rasters'] is not None else 'pending'}   Auto-start command: {job['auto_start']}",
                         f"Settings metadata: {json.dumps(job['settings'])}"]
                if job['delivery']:
                    delivery = job['delivery']
                    lines.append(f"Delivery: {delivery['state']}   Controller: {delivery['host']}")
                    if delivery['result']:
                        result = delivery['result']
                        if result.get('job_time') is not None:
                            lines.append(f"Controller job time: {result['job_time']:.3f} seconds")
                        for warning in result.get('warnings', []):
                            lines.append(f"Controller warning {warning['code']}: {warning['message']}")
                        if result.get('operator_outcome'):
                            lines.append(f"Operator resolution: {result['operator_outcome']} — {result['note']}")
                else:
                    lines.append('Delivery: not sent')
                if job["error"]:
                    lines.append(f"Error: {job['error']}")
                lines.extend(f"{datetime.fromtimestamp(e['time']):%H:%M:%S}  {e['kind']}  {e['detail']}" for e in history)
                text = "\n".join(lines)
            details.configure(state="normal")
            details.delete("1.0", "end")
            details.insert("1.0", text)
            details.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", show_details)

        def background():
            watcher = InboxWatcher(store)
            try:
                while not stopped.is_set():
                    watcher.poll()
                    result = process_one(store)
                    if result is None:
                        stopped.wait(1)
            except Exception as exc:
                notices.put(str(exc))
                stopped.set()

        thread = threading.Thread(target=background, name="aurora-prepare", daemon=False)
        thread.start()

        def refresh():
            nonlocal last_rows
            rows = store.list()
            snapshot = [(j["id"], j["updated"]) for j in rows]
            if snapshot != last_rows:
                choice = tree.selection()
                tree.delete(*tree.get_children())
                for job in rows:
                    tree.insert("", "end", iid=job["id"], values=(job["title"] or job["source_name"], job["state"].replace('_', ' ').title(),
                        f"{job['output_bytes']:,}" if job["output_bytes"] is not None else "—",
                        datetime.fromtimestamp(job["created"]).strftime("%Y-%m-%d %H:%M:%S")))
                if choice and tree.exists(choice[0]):
                    tree.selection_set(choice[0])
                last_rows = snapshot
                show_details()
            while not notices.empty():
                footer.set("Preparation worker stopped: " + notices.get_nowait())
            root.after(500, refresh)

        def close():
            stopped.set()
            footer.set("Finishing local preparation…")
            if thread.is_alive():
                root.after(100, close)
            else:
                root.destroy()

        root.protocol("WM_DELETE_WINDOW", close)
        refresh()
        try:
            root.mainloop()
        finally:
            stopped.set()
            thread.join()
