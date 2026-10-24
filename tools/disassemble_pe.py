"""Disassemble x86/x64 PE code for offline inspection; never execute it."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "python"))
import capstone
from capstone.x86 import X86_OP_IMM, X86_OP_MEM
import pefile


def disassemble(path):
    pe = pefile.PE(str(path))
    base = pe.OPTIONAL_HEADER.ImageBase
    mode = capstone.CS_MODE_32 if pe.FILE_HEADER.Machine == 0x14C else capstone.CS_MODE_64
    engine = capstone.Cs(capstone.CS_ARCH_X86, mode)
    engine.detail = True
    engine.skipdata = True
    imports = {}
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        for symbol in entry.imports:
            name = symbol.name.decode(errors="replace") if symbol.name else f"ordinal:{symbol.ordinal}"
            imports[symbol.address] = f"{entry.dll.decode()}!{name}"
    exports = {base + symbol.address: symbol.name.decode(errors="replace")
               for symbol in getattr(getattr(pe, "DIRECTORY_ENTRY_EXPORT", None), "symbols", []) if symbol.name}

    def describe(address):
        if address in imports:
            return imports[address]
        if address in exports:
            return exports[address]
        rva = address - base
        section = pe.get_section_by_rva(rva) if rva >= 0 else None
        if section is None:
            return None
        sample = pe.get_data(rva, 180)
        text = sample.split(b"\0")[0]
        if len(text) >= 4 and all(32 <= c < 127 or c in (9, 10, 13) for c in text):
            return repr(text.decode("ascii"))
        text = sample.decode("utf-16le", errors="ignore").split("\0")[0]
        if len(text) >= 4 and all(32 <= ord(c) < 127 or c in "\r\n\t" for c in text):
            return "L" + repr(text)
        return None

    lines = [f"; {path}", f"; image base {base:#x}"]
    for section in pe.sections:
        if not section.Characteristics & 0x20000000:
            continue
        lines.append(f"; section {section.Name!r}")
        for ins in engine.disasm(section.get_data(), base + section.VirtualAddress):
            if ins.address in exports:
                lines.append(f"\n; EXPORT {exports[ins.address]}")
            notes = []
            if ins.id:
                for op in ins.operands:
                    address = op.imm if op.type == X86_OP_IMM else op.mem.disp if op.type == X86_OP_MEM else 0
                    label = describe(address)
                    if label and label not in notes:
                        notes.append(label)
            suffix = " ; " + " | ".join(notes) if notes else ""
            lines.append(f"{ins.address:08x}: {ins.mnemonic:<9} {ins.op_str}{suffix}")
    pe.close()
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("analysis/disassembly"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for path in args.paths:
        target = args.output / (path.name + ".asm")
        target.write_text(disassemble(path), encoding="utf-8")
        print(target)


if __name__ == "__main__":
    main()
