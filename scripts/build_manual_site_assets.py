"""Build the site-facing SVG manifest from the manually labelled glyph packages.

Every package under ``字库/`` listed in :data:`PACKAGES` is scanned.  A package
that already ships site-facing SVGs (``site-solid.svg``, ``site-color.svg`` and
``site-stroke-NN.svg``) is referenced as-is, so centre-line strokes keep their
``fill="none" stroke=...`` geometry.  Legacy packages without those files are
converted from ``display-split.svg`` into filled shapes.

Glyphs that already have a hand-checked record in ``data/cleaned-glyphs.js`` are
skipped: the site gives those records priority (see ``tests/site-smoke.cjs``),
so listing them here would shadow the curated geometry.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = [
    ROOT / "字库" / "处理结果-current-167",
    ROOT / "字库" / "处理结果-334-500",
]
MANIFEST = ROOT / "data" / "manual-167-assets.js"
CLEANED = ROOT / "data" / "cleaned-glyphs.js"
PALETTE = ["#eeb377", "#a5c4b1", "#d89181", "#bfafd0", "#e6d38a", "#8eb8c4"]
SOLID = "#eadfbb"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def svg_path_attrs(path: ET.Element) -> dict[str, str]:
    attrs = {"d": path.attrib["d"], "fill-rule": path.attrib.get("fill-rule", "evenodd")}
    if path.attrib.get("opacity") not in (None, "1"):
        attrs["opacity"] = path.attrib["opacity"]
    if path.attrib.get("data-stroke-id"):
        attrs["data-stroke-id"] = path.attrib["data-stroke-id"]
    return attrs


def make_svg(view_box: str, paths: list[dict[str, str]], aria: str) -> str:
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": view_box,
            "role": "img",
            "aria-label": aria,
        },
    )
    for attrs in paths:
        ET.SubElement(root, "path", attrs)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True) + "\n"


def cleaned_glyph_ids() -> set[str]:
    """IDs with a curated centre-line record; the site renders those first."""
    if not CLEANED.is_file():
        return set()
    text = CLEANED.read_text(encoding="utf-8")
    data = json.JSONDecoder().raw_decode(text[text.index("{"):])[0]
    return set(data)


def existing_site_assets(directory: Path) -> tuple[Path, Path, list[Path]] | None:
    """Return the package's own site SVGs when they are all present."""
    solid = directory / "site-solid.svg"
    color = directory / "site-color.svg"
    strokes = sorted(directory.glob("site-stroke-*.svg"))
    if solid.is_file() and color.is_file() and strokes:
        return solid, color, strokes
    return None


def build_from_display_split(directory: Path, base_url: str) -> dict:
    """Legacy conversion: turn filled display contours into site SVGs."""
    source = directory / "display-split.svg"
    tree = ET.parse(source)
    source_root = tree.getroot()
    view_box = source_root.attrib["viewBox"]
    source_paths = [
        node
        for node in source_root.iter()
        if local_name(node.tag) == "path" and node.attrib.get("d")
    ]
    base = []
    for node in source_paths:
        attrs = svg_path_attrs(node)
        attrs.update({"fill": SOLID, "stroke": "none"})
        base.append(attrs)
    color_paths = []
    stroke_paths = []
    for index, node in enumerate(source_paths):
        attrs = svg_path_attrs(node)
        attrs.update({"fill": PALETTE[index % len(PALETTE)], "stroke": "none"})
        color_paths.append(attrs)
        stroke_paths.append(attrs)

    (directory / "site-solid.svg").write_text(
        make_svg(view_box, base, f"{directory.name} 纯色展示"), encoding="utf-8"
    )
    (directory / "site-color.svg").write_text(
        make_svg(view_box, color_paths, f"{directory.name} 彩色拆笔展示"), encoding="utf-8"
    )
    stroke_files = []
    for index, attrs in enumerate(stroke_paths, start=1):
        filename = f"site-stroke-{index:02d}.svg"
        one = dict(attrs)
        (directory / filename).write_text(
            make_svg(view_box, [one], f"{directory.name} 第{index}笔"), encoding="utf-8"
        )
        stroke_files.append(f"{base_url}/{filename}")
    return {
        "solid": f"{base_url}/site-solid.svg",
        "color": f"{base_url}/site-color.svg",
        "strokes": stroke_files,
    }


def main() -> None:
    records: dict[str, dict] = {}
    curated = cleaned_glyph_ids()
    skipped: list[str] = []
    for package in PACKAGES:
        if not package.is_dir():
            continue
        relative = package.relative_to(ROOT).as_posix()
        for directory in sorted(p for p in package.iterdir() if p.is_dir()):
            base_url = f"./{relative}/{directory.name}"
            if directory.name in records:
                raise ValueError(f"duplicate glyph across packages: {directory.name}")
            if directory.name in curated:
                skipped.append(directory.name)
                continue
            existing = existing_site_assets(directory)
            if existing:
                solid, color, strokes = existing
                records[directory.name] = {
                    "solid": f"{base_url}/{solid.name}",
                    "color": f"{base_url}/{color.name}",
                    "strokes": [f"{base_url}/{stroke.name}" for stroke in strokes],
                }
            else:
                records[directory.name] = build_from_display_split(directory, base_url)

    manifest = "/* Generated by scripts/build_manual_site_assets.py. */\nwindow.MANUAL_167_ASSETS = "
    manifest += json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    manifest += ";\n"
    MANIFEST.write_text(manifest, encoding="utf-8")
    print(f"generated {len(records)} glyphs and {sum(len(r['strokes']) for r in records.values())} stroke SVGs")
    if skipped:
        print(f"skipped {len(skipped)} curated glyph(s): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
