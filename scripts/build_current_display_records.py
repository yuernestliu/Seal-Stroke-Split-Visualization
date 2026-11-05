"""Record the geometry of the current smooth display SVGs without replacing the
legacy manual-v2 contour/skeleton records.

The current site SVGs are centerline display paths, so they are recorded as a
separate geometry version instead of being mislabeled as filled contours.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "字库" / "处理结果-current-167"
TODAY = date.today().isoformat()
NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
COMMAND_RE = re.compile(r"([MLQ])([^MLQ]*)", re.I)


def parse_path(path: ET.Element) -> tuple[list[dict], list[tuple[float, float]]]:
    d = path.attrib.get("d", "")
    commands: list[dict] = []
    points: list[tuple[float, float]] = []
    for match in COMMAND_RE.finditer(d):
        command = match.group(1).upper()
        values = [float(x) for x in NUMBER_RE.findall(match.group(2))]
        if command in {"M", "L"}:
            for i in range(0, len(values) - 1, 2):
                point = (values[i], values[i + 1])
                points.append(point)
                commands.append({"command": command, "point": list(point)})
        elif command == "Q" and len(values) >= 4:
            for i in range(0, len(values) - 3, 4):
                control = (values[i], values[i + 1])
                end = (values[i + 2], values[i + 3])
                points.extend((control, end))
                commands.append({"command": command, "control": list(control), "point": list(end)})
    return commands, points


def read_svg(path: Path) -> tuple[str, str, list[dict]]:
    root = ET.parse(path).getroot()
    view_box = root.attrib.get("viewBox", "")
    paths = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "path":
            continue
        commands, points = parse_path(element)
        paths.append(
            {
                "stroke_id": element.attrib.get("data-stroke-id"),
                "color": element.attrib.get("stroke"),
                "stroke_width": float(element.attrib.get("stroke-width", "0") or 0),
                "d": element.attrib.get("d", ""),
                "commands": commands,
                "points": [list(point) for point in points],
            }
        )
    return view_box, root.attrib.get("aria-label", ""), paths


def main() -> None:
    glyph_dirs = sorted(path for path in PACKAGE.iterdir() if path.is_dir())
    summary = {"schema": "current-display-records-v1", "generated": TODAY, "glyph_count": len(glyph_dirs), "results": []}
    for glyph_dir in glyph_dirs:
        color_svg = glyph_dir / "site-color.svg"
        if not color_svg.exists():
            continue
        view_box, aria_label, paths = read_svg(color_svg)
        nodes: dict[tuple[float, float], dict] = {}
        edges = []
        for index, path in enumerate(paths, 1):
            stroke_id = path["stroke_id"] or f"S{index}"
            points = path["points"]
            endpoints = []
            if points:
                endpoints = [tuple(points[0]), tuple(points[-1])]
            endpoint_ids = []
            for point in endpoints:
                node = nodes.setdefault(point, {"point": list(point), "incident_strokes": set()})
                node["incident_strokes"].add(stroke_id)
            edges.append({"edge_id": f"E{index:04d}", "stroke_id": stroke_id, "color": path["color"], "stroke_width": path["stroke_width"], "d": path["d"], "commands": path["commands"], "points": points, "closed": False})

        node_list = []
        for index, (point, node) in enumerate(sorted(nodes.items()), 1):
            node_list.append({"node_id": f"N{index:04d}", "point": list(point), "incident_strokes": sorted(node["incident_strokes"])})
        source = {}
        source_path = glyph_dir / "source.json"
        if source_path.exists():
            source = json.loads(source_path.read_text(encoding="utf-8"))
        current_source = {
            "schema": "current-display-source-v1",
            "glyph_id": glyph_dir.name,
            "raw_png": source.get("raw_png"),
            "manual_label": source.get("label_png"),
            "display_svg": "site-color.svg",
            "solid_svg": "site-solid.svg",
            "stroke_svgs": sorted(path.name for path in glyph_dir.glob("site-stroke-*.svg")),
            "coordinate_system": "current site SVG viewBox coordinates; origin top-left",
            "geometry_version": "smooth-centerline-display-v1",
            "legacy_records": "source.json, mask.png, outline.svg, skeleton.json, overlay.svg, review.json",
        }
        (glyph_dir / "current-source.json").write_text(json.dumps(current_source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        current_skeleton = {
            "schema": "current-display-skeleton-v1",
            "status": "candidate-needs-manual-review",
            "glyph_id": glyph_dir.name,
            "viewBox": view_box,
            "aria_label": aria_label,
            "coordinate_system": "site SVG viewBox coordinates; x right, y down",
            "nodes": node_list,
            "edges": edges,
            "closed_loops": [],
            "stroke_truth": {"source": "manual label map via current smooth display SVG", "confirmed": False},
        }
        (glyph_dir / "current-skeleton.json").write_text(json.dumps(current_skeleton, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        skeleton_svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" role="img" aria-label="{glyph_dir.name} 当前展示骨架">']
        for edge in edges:
            skeleton_svg.append(f'<path d="{edge["d"]}" fill="none" stroke="#111" stroke-width="{edge["stroke_width"] or 3.2:g}" stroke-linecap="round" stroke-linejoin="round" data-stroke-id="{edge["stroke_id"]}"/>')
        skeleton_svg.append("</svg>\n")
        (glyph_dir / "current-skeleton.svg").write_text("".join(skeleton_svg), encoding="utf-8")

        parameters = {
            "schema": "current-display-parameters-v1",
            "glyph_id": glyph_dir.name,
            "source_script": "scripts/build_manual_site_assets.py",
            "viewBox": view_box,
            "paths": len(edges),
            "stroke_widths": sorted({edge["stroke_width"] for edge in edges}),
            "centerline_display": True,
            "note": "This version records the current smooth centerline display; it is not relabeled as a filled contour.",
        }
        (glyph_dir / "current-parameters.json").write_text(json.dumps(parameters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        review = {
            "schema": "current-display-review-v1",
            "glyph_id": glyph_dir.name,
            "status": "candidate-needs-manual-review",
            "geometry_version": "smooth-centerline-display-v1",
            "outline_reviewed": False,
            "skeleton_reviewed": False,
            "stroke_split_reviewed": False,
            "owner": None,
            "reviewer": None,
            "review_date": TODAY,
            "files": {"display": "site-color.svg", "solid": "site-solid.svg", "skeleton": "current-skeleton.json", "skeleton_svg": "current-skeleton.svg", "source": "current-source.json", "parameters": "current-parameters.json"},
            "issues": ["Current site files are smooth centerline display paths; legacy contour records are kept separately.", "Human visual confirmation is still required."],
        }
        (glyph_dir / "current-review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary["results"].append({"glyph_id": glyph_dir.name, "stroke_count": len(edges), "node_count": len(node_list), "status": review["status"]})
    (PACKAGE / "current-display-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated current-display records for {len(summary['results'])} glyphs")


if __name__ == "__main__":
    main()
