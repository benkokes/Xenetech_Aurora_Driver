"""Export a copy of a Jet-format Xenetech DBI for offline analysis."""
import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "python"))
from access_parser import AccessParser


def encode(value):
    if isinstance(value, (bytes, bytearray)):
        return {"bytes_hex": bytes(value).hex()}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Unsupported database value: {type(value).__name__}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--output", type=Path, default=Path("captures/decoded/machine-database.json"))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Output already exists: {args.output}")
    db = AccessParser(str(args.database))
    result = {"source": str(args.database), "sha256": hashlib.sha256(args.database.read_bytes()).hexdigest(),
              "tables": {}, "errors": {}}
    for name in db.catalog:
        if name.startswith("MSys"):
            continue
        try:
            table = db.parse_table(name)
            result["tables"][name] = table
            print(json.dumps({"table": name, "rows": max((len(v) for v in table.values()), default=0),
                              "columns": list(table)}))
        except Exception as exc:
            result["errors"][name] = repr(exc)
            print(json.dumps({"table": name, "error": repr(exc)}))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=encode), encoding="utf-8")
    if result["errors"] or not result["tables"]:
        raise SystemExit("Database export is incomplete; see error entries")


if __name__ == "__main__":
    main()
