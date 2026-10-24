"""Read PE metadata and strings without loading or executing vendor binaries."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "python"))
import pefile


def inspect(path, root):
    data = path.read_bytes()
    pe = pefile.PE(data=data)
    result = {
        "path": path.relative_to(root).as_posix(),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "machine": hex(pe.FILE_HEADER.Machine),
        "image_base": hex(pe.OPTIONAL_HEADER.ImageBase),
        "subsystem": pe.OPTIONAL_HEADER.Subsystem,
        "imports": {},
        "exports": [],
        "version": {},
    }
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        result["imports"][entry.dll.decode(errors="replace")] = [
            {"name": i.name.decode(errors="replace") if i.name else f"ordinal:{i.ordinal}",
             "iat_va": hex(i.address)} for i in entry.imports
        ]
    for entry in getattr(getattr(pe, "DIRECTORY_ENTRY_EXPORT", None), "symbols", []):
        result["exports"].append({"name": entry.name.decode(errors="replace") if entry.name else None,
                                  "ordinal": entry.ordinal, "rva": hex(entry.address)})
    for group in getattr(pe, "FileInfo", []):
        for info in group:
            for table in getattr(info, "StringTable", []):
                result["version"].update({k.decode(errors="replace"): v.decode(errors="replace")
                                          for k, v in table.entries.items()})
    strings = []
    for pattern, encoding in [(rb"[\x20-\x7e]{5,}", "ascii"),
                              (rb"(?:[\x20-\x7e]\x00){5,}", "utf-16le")]:
        for match in re.finditer(pattern, data):
            offset = match.start()
            try:
                rva = pe.get_rva_from_offset(offset)
                va = hex(pe.OPTIONAL_HEADER.ImageBase + rva) if rva is not None else None
            except pefile.PEFormatError:
                va = None
            strings.append({"offset": hex(offset), "va": va,
                            "text": match.group().decode(encoding)})
    result["strings"] = sorted(strings, key=lambda x: int(x["offset"], 16))
    pe.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("analysis/pe"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path.cwd()
    index = []
    for source in args.paths:
        paths = source.rglob("*") if source.is_dir() else [source]
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in {".exe", ".dll", ".ocx", ".cpl", ".sys"}:
                continue
            path = path.resolve()
            try:
                result = inspect(path, root)
            except pefile.PEFormatError as exc:
                index.append({"path": str(path), "error": str(exc)})
                continue
            name = result["path"].replace("/", "__")
            (args.output / (name + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
            (args.output / (name + ".strings.txt")).write_text(
                "\n".join(f'{s["offset"]}\t{s["va"]}\t{s["text"]}' for s in result["strings"]), encoding="utf-8")
            index.append({k: v for k, v in result.items() if k not in {"strings", "exports", "imports"}})
    (args.output / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Inspected {len(index)} files; reports: {args.output}")


if __name__ == "__main__":
    main()
