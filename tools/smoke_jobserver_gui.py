"""Start the real queue GUI hidden, exercise its event loop, and close it."""
import argparse
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aurora_jobserver import gui
from aurora_jobserver.store import JobStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path("runtime/gui-smoke"))
    parser.add_argument('--expect-delivery-state', help='Select the first row and verify its delivery details')
    args = parser.parse_args()
    original = gui.tk.Tk
    errors = []
    def hidden_root():
        root = original()
        root.withdraw()
        root.report_callback_exception = lambda kind, value, traceback: errors.append(str(value))
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        def check_details():
            try:
                tree = next(w for w in widgets(root) if isinstance(w, gui.ttk.Treeview))
                tree.selection_set(tree.get_children()[0])
                tree.event_generate('<<TreeviewSelect>>')
                root.after(100, verify_details)
            except Exception as exc:
                errors.append(str(exc))
        def verify_details():
            text = next(w for w in widgets(root) if isinstance(w, gui.tk.Text)).get('1.0', 'end')
            if f'Delivery: {args.expect_delivery_state}' not in text:
                errors.append('Selected job did not display its saved delivery status')
        if args.expect_delivery_state:
            root.after(500, check_details)
        root.after(1500, root.destroy)
        return root
    with patch.object(gui.tk, "Tk", hidden_root):
        gui.run(JobStore(args.state))
    if errors:
        raise RuntimeError("; ".join(errors))
    print("Desktop queue event-loop smoke check passed")


if __name__ == "__main__":
    main()
