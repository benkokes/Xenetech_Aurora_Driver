"""Preview the observed PU/PD/V vector subset of a decoded JBS, offline.

Coordinates are displayed in native job units; no physical calibration or
interpretation of unknown commands is implied. This never sends a job.
"""
import argparse
from html import escape
import json
from pathlib import Path
import re


MOVE = re.compile(r"^([+-]?\d+(?:\.\d*)?)\s+([+-]?\d+(?:\.\d*)?)\s+V$")


def paths_from_segments(segments):
    paths = []
    current = []
    position = None
    down = False
    moves = 0
    for segment in segments:
        for line in segment["text"].splitlines():
            line = line.strip()
            if line == "PU":
                if len(current) > 1:
                    paths.append(current)
                current = []
                down = False
            elif line == "PD":
                down = True
                current = [position] if position is not None else []
            else:
                match = MOVE.fullmatch(line)
                if match:
                    moves += 1
                    position = (float(match[1]), float(match[2]))
                    if down:
                        current.append(position)
    if len(current) > 1:
        paths.append(current)
    return paths, moves


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, default=Path("captures/decoded/vector-preview"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if report["status"] != "raw_rasters_decoded":
        parser.error("This preview requires the decoded raw job's text segments")
    paths, moves = paths_from_segments(report["text_segments"])
    if not paths:
        parser.error("No supported vector paths found")
    xs = [p[0] for path in paths for p in path]
    ys = [p[1] for path in paths for p in path]
    left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
    margin = max(right - left, bottom - top) * 0.015 or 1
    width = right - left + 2 * margin
    height = bottom - top + 2 * margin
    stroke = max(width, height) / 1500
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{left-margin} {top-margin} {width} {height}">',
           '<title>Observed vector coordinates; physical units uncalibrated</title>',
           f'<rect x="{left-margin}" y="{top-margin}" width="{width}" height="{height}" fill="white"/>',
           f'<g fill="none" stroke="black" stroke-width="{stroke}">']
    for path in paths:
        coordinates = " ".join(f"{x:g},{y:g}" for x, y in path)
        svg.append(f'<polyline points="{escape(coordinates)}"/>')
    svg.extend(["</g>", "</svg>"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".svg").write_text("\n".join(svg), encoding="utf-8")
    summary = {"source": report["path"], "paths": len(paths), "coordinate_moves": moves,
               "native_coordinate_bounds": [left, top, right, bottom],
               "interpretation": "Observed PU/PD/V subset only; physical units uncalibrated"}
    args.output.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    from PIL import Image, ImageDraw
    scale = min(1500 / width, 1200 / height)
    image = Image.new("RGB", (max(1, round(width * scale)), max(1, round(height * scale))), "white")
    draw = ImageDraw.Draw(image)
    for path in paths:
        draw.line([((x - left + margin) * scale, (y - top + margin) * scale) for x, y in path], fill="black")
    image.save(args.output.with_suffix(".png"))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
