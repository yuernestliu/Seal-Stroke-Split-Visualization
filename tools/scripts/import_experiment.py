#!/usr/bin/env python3
"""Import one stroke-segmentation experiment into the static site dataset.

The script deliberately keeps generated data separate from editorial notes. Run it
again after a new experiment, then commit the changed `data/glyphs.js` and assets.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT = PROJECT_ROOT.parent / "v1" / "拆笔画" / "outputs" / "experiment_v1"
DEFAULT_SOURCE_IMAGES = PROJECT_ROOT.parent / "v1" / "拆笔画" / "data" / "小篆例"


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_glyph_name(image_name: str) -> tuple[str, str, str]:
    stem = Path(image_name).stem
    pieces = stem.split("_")
    source_id = pieces[0]
    mark = pieces[1] if len(pieces) > 1 else "未名"
    source = "_".join(pieces[2:]) if len(pieces) > 2 else "来源待补"
    return source_id, mark, source


def relative_asset(path: Path) -> str:
    return "./" + path.relative_to(PROJECT_ROOT).as_posix()


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("*.json"))


def glyph_code(mark: str) -> str:
    if len(mark) != 1:
        return "待录入"
    return f"U+{ord(mark):04X}"


def png_dimensions(path: Path) -> tuple[int, int]:
    """Read the dimensions from a PNG header without adding an image dependency."""
    with path.open("rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Expected a PNG file: {path}")
    return struct.unpack(">II", header[16:24])


def build_glyph(entry: dict, experiment: Path, source_images: Path, version: str, notes: dict) -> dict:
    source_id, mark, source_name = parse_glyph_name(entry["image"])
    folder = Path(entry["image"]).stem
    source_dir = Path(entry["image"]).with_suffix("")
    result = read_json(experiment / source_dir / "result.json")
    note = notes.get(folder, {})
    asset_root = PROJECT_ROOT / "public" / "assets" / "experiments" / version / folder
    original_path = PROJECT_ROOT / "public" / "assets" / "sources" / version / entry["image"]

    if (source_images / entry["image"]).exists():
        original_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_images / entry["image"], original_path)

    files = {
        "original": relative_asset(original_path),
        "binary": relative_asset(asset_root / "binary.png"),
        "composite": relative_asset(asset_root / "strokes.png"),
        "skeleton": relative_asset(asset_root / "skeleton.png"),
        "overlay": relative_asset(asset_root / "overlay.png"),
        "overlap": relative_asset(asset_root / "overlap.png"),
        "gallery": relative_asset(asset_root / result["stroke_gallery"]),
    }
    canvas_width, canvas_height = png_dimensions(asset_root / "binary.png")
    segments = []
    for index, segment in enumerate(result.get("segments", [])):
        stroke_file = result.get("stroke_files", [])[index]
        segments.append(
            {
                "id": segment.get("stroke_id", index + 1),
                "pointCount": segment.get("point_count", entry["segment_lengths"][index]),
                "pixelCount": segment.get("pixel_count"),
                "points": segment.get("points", []),
                "image": relative_asset(asset_root / stroke_file),
            }
        )

    return {
        "id": folder,
        "sourceId": source_id,
        "mark": mark,
        "title": note.get("title", mark if mark != "未名" else "未命名字形"),
        "unicode": glyph_code(mark),
        "source": {
            "collection": "说文解字",
            "section": source_name.replace("Z_", "") if source_name else "待补",
            "originalFile": entry["image"],
            "experiment": version,
        },
        "definition": note.get("definition", "释义待团队校释。"),
        "formation": note.get("formation", "构形方式待人工标注。"),
        "components": note.get("components", []),
        "reviewStatus": note.get("reviewStatus", "待补释义与部件标注"),
        "metrics": {
            "segmentCount": result["segment_count"],
            "overlapPixels": result.get("overlap_pixel_count", 0),
            "lengths": result["segment_lengths"],
        },
        "canvas": {
            "width": canvas_width,
            "height": canvas_height,
        },
        "segments": segments,
        "assets": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a stroke experiment for the glyph explorer.")
    parser.add_argument("--experiment", type=Path, default=DEFAULT_EXPERIMENT)
    parser.add_argument("--source-images", type=Path, default=DEFAULT_SOURCE_IMAGES)
    parser.add_argument("--version", default="v1")
    args = parser.parse_args()

    experiment = args.experiment.resolve()
    source_images = args.source_images.resolve()
    summary = read_json(experiment / "summary.json")
    notes_path = PROJECT_ROOT / "data" / "glyph-notes.json"
    notes = read_json(notes_path) if notes_path.exists() else {}

    destination_root = PROJECT_ROOT / "public" / "assets" / "experiments" / args.version
    destination_root.mkdir(parents=True, exist_ok=True)
    glyphs = []
    for entry in summary["results"]:
        folder = Path(entry["image"]).stem
        source_dir = Path(entry["image"]).with_suffix("")
        copy_tree(experiment / source_dir, destination_root / folder)
        glyphs.append(build_glyph(entry, experiment, source_images, args.version, notes))

    payload = {"dataset": {"name": "小篆笔画拆解", "version": args.version, "count": len(glyphs)}, "glyphs": glyphs}
    output = PROJECT_ROOT / "data" / "glyphs.js"
    output.write_text(
        "/* Generated by scripts/import_experiment.py. Do not hand-edit. */\n"
        + "window.GLYPH_DATA = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Imported {len(glyphs)} glyphs from {experiment}")


if __name__ == "__main__":
    main()
