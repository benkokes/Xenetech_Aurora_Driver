"""Command-line entry point for the local Aurora queue."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time

from .store import JobStore
from .worker import InboxWatcher, WorkerLock, process_one


def main():
    parser = argparse.ArgumentParser(description="Aurora JobServer — local queue and job preparation")
    parser.add_argument("--state", type=Path, default=Path("runtime/jobserver"), help="Queue data directory")
    commands = parser.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit", help="Snapshot a .jbs file into the queue")
    submit.add_argument("source", type=Path)
    submit.add_argument("--settings", type=Path, help="Optional per-job JSON metadata; does not change embedded commands")
    commands.add_parser("list", help="List jobs as JSON")
    for name in ("show", "cancel", "retry"):
        commands.add_parser(name).add_argument("id")
    export = commands.add_parser("export", help="Copy a prepared file; never sends it")
    export.add_argument("id")
    export.add_argument("destination", type=Path)
    send = commands.add_parser('send', help='Explicitly send one prepared raster job to a controller')
    send.add_argument('id')
    send.add_argument('--host', required=True, help='Controller IPv4 address; use 127.0.0.1 for a simulator')
    send.add_argument('--main-port', type=int, default=23)
    send.add_argument('--status-port', type=int, default=29)
    send.add_argument('--realtime-port', type=int, default=30)
    send.add_argument('--recovery-port', type=int, default=99)
    send.add_argument('--reset-connection', action='store_true',
                      help='Explicit legacy port-99 recovery; disconnects existing controller clients. Use only when idle.')
    send.add_argument('--controller-path', default=r'c:\xfiles\jbs\Convert\Default.jbs',
                      help='Controller metadata path; this does not choose a local file')
    send.add_argument('--timeout', type=float, default=7200, help='Upload/completion deadline in seconds')
    send.add_argument('--locks', type=Path, help='Shared controller-lock directory across all queues')
    recover = commands.add_parser('recover-deliveries', help='Reconcile interrupted sender records without sending')
    recover.add_argument('--host', required=True)
    recover.add_argument('--locks', type=Path)
    resolve = commands.add_parser('resolve-delivery', help='Record the operator-observed result of an uncertain job')
    resolve.add_argument('id')
    resolve.add_argument('--outcome', required=True, choices=('completed','not_started','stopped'))
    resolve.add_argument('--note', required=True)
    resolve.add_argument('--locks', type=Path)
    commands.add_parser("process", help="Prepare all queued jobs and exit")
    watch = commands.add_parser("watch", help="Observe the inbox and prepare jobs until Ctrl+C")
    watch.add_argument("--inbox", type=Path, help="Defaults to STATE/inbox")
    watch.add_argument("--interval", type=float, default=1.0)
    commands.add_parser("gui", help="Open the desktop queue")
    args = parser.parse_args()
    try:
        store = JobStore(args.state)
        if args.command == "submit":
            settings = json.loads(args.settings.read_text(encoding="utf-8")) if args.settings else None
            print(json.dumps(store.get(store.submit(args.source, settings))))
        elif args.command == "list":
            print(json.dumps(store.list(), indent=2))
        elif args.command == "show":
            print(json.dumps({"job": store.get(args.id), "events": store.history(args.id)}, indent=2))
        elif args.command in ("cancel", "retry"):
            getattr(store, args.command)(args.id)
            print(json.dumps(store.get(args.id)))
        elif args.command == "export":
            print(store.export(args.id, args.destination))
        elif args.command == 'send':
            from .sender import send_job
            from .transport import Endpoint, Timing
            result = send_job(store, args.id, Endpoint(args.host, args.main_port, args.status_port,
                              args.realtime_port, args.recovery_port), args.controller_path,
                              timing=Timing(job=args.timeout), locks=args.locks, reset_connection=args.reset_connection)
            print(json.dumps(result, indent=2))
            return 0 if result['state'] in ('completed','completed_with_warning') else 1
        elif args.command == 'recover-deliveries':
            from .sender import recover_controller
            from .transport import Endpoint
            print(json.dumps({'recovered': recover_controller(store, Endpoint(args.host), locks=args.locks)}))
        elif args.command == 'resolve-delivery':
            from .sender import resolve_job
            print(json.dumps(resolve_job(store, args.id, args.outcome, args.note, locks=args.locks), indent=2))
        elif args.command == "gui":
            from .gui import run
            run(store)
        else:
            if args.command == "watch" and not 0.1 <= args.interval <= 60:
                parser.error("Polling interval must be between 0.1 and 60 seconds")
            with WorkerLock(store.root):
                store.recover()
                watcher = InboxWatcher(store, args.inbox) if args.command == "watch" else None
                while True:
                    if watcher:
                        for job_id in watcher.poll():
                            print(json.dumps({"accepted": job_id}), flush=True)
                    result = process_one(store)
                    if result:
                        print(json.dumps(result), flush=True)
                    elif watcher:
                        time.sleep(args.interval)
                    else:
                        break
    except KeyboardInterrupt:
        print('Interrupted. An active delivery may be uncertain; check its saved history.', file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, RuntimeError, sqlite3.Error) as exc:
        print(f"Aurora JobServer: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
