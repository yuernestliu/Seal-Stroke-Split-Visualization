"""Build web-ready component masks and glyph records from the colored template set."""

from __future__ import annotations

import json
import math
import re
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "按模板识别_连通域数量约束"
OUTPUT = ROOT / "public" / "assets" / "template-parts"
SOURCE_OUT = ROOT / "public" / "assets" / "template-sources"
DATA_OUT = ROOT / "data" / "template-glyphs.js"
PALETTE = ["#eeb377", "#a5c4b1", "#d89181", "#bfafd0", "#e6d38a", "#8eb8c4"]


def load_existing():
    source = (ROOT / "data" / "glyphs.js").read_text(encoding="utf-8")
    payload = source.split("window.GLYPH_DATA =", 1)[1].rsplit(";", 1)[0]
    return json.loads(payload)["glyphs"]


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def build_masks(path: Path):
    image = Image.open(path).convert("RGB")
    width, height = image.size
    pixels = list(image.getdata())
    colors = Counter(pixels)
    candidates = []
    for rgb, count in colors.most_common():
        if max(rgb) - min(rgb) < 38 or min(rgb) > 225:
            continue
        if any(distance(rgb, center) < 38 for center, _ in candidates):
            continue
        candidates.append((rgb, count))
    # Discard tiny color noise while retaining small legitimate components.
    candidates = [(rgb, count) for rgb, count in candidates if count >= max(8, len(pixels) * 0.0008)]
    if not candidates:
        residuals = [max(255 - channel for channel in rgb) for rgb in pixels]
        if max(residuals, default=0) < 8:
            return width, height, []
        peak = max(residuals)
        alphas = [round(alpha * 255 / peak) if alpha >= 8 else 0 for alpha in residuals]
        mass = sum(alphas)
        mask = Image.new("RGBA", image.size)
        mask.putdata([(255, 255, 255, alpha) for alpha in alphas])
        name = f"{path.stem}-part-1.png"
        mask.save(OUTPUT / name, optimize=True)
        cx = sum((i % width) * alpha for i, alpha in enumerate(alphas)) / mass
        cy = sum((i // width) * alpha for i, alpha in enumerate(alphas)) / mass
        return width, height, [{"mask": f"./public/assets/template-parts/{name}", "cx": round(cx, 2), "cy": round(cy, 2), "sourceColor": "#444444", "palette": PALETTE[0], "area": mass}]
    centers = [tuple(255 - channel for channel in rgb) for rgb, _ in candidates]
    alpha_planes = [[0] * len(pixels) for _ in centers]
    sums = [[0, 0, 0] for _ in centers]
    masses = [0] * len(centers)
    for index, rgb in enumerate(pixels):
        residual = tuple(255 - channel for channel in rgb)
        alpha = max(residual)
        if alpha < 8:
            continue
        norm = math.sqrt(sum(channel * channel for channel in residual))
        if norm < 1:
            continue
        # Hue direction stays stable through anti-aliased edges against white.
        chosen = min(range(len(centers)), key=lambda i: sum((residual[j] / norm - centers[i][j] / max(1, math.sqrt(sum(c*c for c in centers[i])))) ** 2 for j in range(3)))
        alpha_planes[chosen][index] = min(255, round(alpha * 255 / max(1, max(centers[chosen]))))
        x, y = index % width, index // width
        weight = alpha_planes[chosen][index]
        sums[chosen][0] += x * weight
        sums[chosen][1] += y * weight
        sums[chosen][2] += weight
        masses[chosen] += alpha_planes[chosen][index]
    parts = []
    for index, rgb in enumerate([rgb for rgb, _ in candidates]):
        if masses[index] < 20:
            continue
        mask = Image.new("RGBA", image.size)
        mask.putdata([(255, 255, 255, alpha) for alpha in alpha_planes[index]])
        name = f"{path.stem}-part-{len(parts) + 1}.png"
        mask.save(OUTPUT / name, optimize=True)
        parts.append({
            "mask": f"./public/assets/template-parts/{name}",
            "cx": round(sums[index][0] / masses[index], 2),
            "cy": round(sums[index][1] / masses[index], 2),
            "sourceColor": "#%02x%02x%02x" % rgb,
            "palette": PALETTE[len(parts) % len(PALETTE)],
            "area": masses[index],
        })
    return width, height, parts


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SOURCE_OUT.mkdir(parents=True, exist_ok=True)
    existing = load_existing()
    existing_marks = {glyph["mark"] for glyph in existing}
    by_mark = {}
    added = []
    seen = set()
    for source_path in sorted(SOURCE.rglob("*.png")):
        match = re.match(r"(?P<source>\d+?)_(?P<mark>.+?)_Z_說文‧(?P<section>.+?)\.png$", source_path.name)
        if not match:
            continue
        source_id, mark, section = match.group("source", "mark", "section")
        if mark in seen:
            continue
        seen.add(mark)
        shutil.copy2(source_path, SOURCE_OUT / source_path.name)
        width, height, parts = build_masks(source_path)
        if parts:
            by_mark[mark] = {"width": width, "height": height, "parts": parts}
        if mark in existing_marks:
            continue
        relative = (Path("public") / "assets" / "template-sources" / source_path.name).as_posix()
        added.append({
            "id": f"{source_id}_{mark}_Z_說文‧{section}",
            "sourceId": source_id,
            "mark": mark,
            "title": mark,
            "unicode": f"U+{ord(mark[0]):04X}",
            "source": {"collection": "说文解字", "section": f"說文‧{section}", "originalFile": relative, "experiment": "template"},
            "definition": "释义待补。",
            "original_meaning": "",
            "meaning_extend": "",
            "structure_desc": "",
            "parts": [],
            "part_type": [],
            "part_comment": [],
            "components": [],
            "reviewStatus": "模板部件待校核",
            "segments": [],
            "assets": {"original": f"./{relative}", "binary": "", "composite": "", "skeleton": "", "overlay": "", "overlap": "", "gallery": ""},
            "templateParts": by_mark.get(mark),
        })
    # Keep the merged records compact; the source images remain the source of truth.
    records = {"glyphs": added, "partsByMark": by_mark, "sourceCount": len(seen)}
    DATA_OUT.write_text("window.TEMPLATE_GLYPH_DATA = " + json.dumps(records, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Processed {len(seen)} glyphs; added {len(added)} new catalog entries; component maps for {len(by_mark)} glyphs.")


if __name__ == "__main__":
    main()
