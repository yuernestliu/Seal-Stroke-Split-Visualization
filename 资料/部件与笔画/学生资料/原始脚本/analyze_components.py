"""Build a first-pass component analysis for the 按部首分类 image corpus.

The corpus contains one image per filename character and groups images by the
folder's 說文部首.  This script deliberately treats the folder radical as a
candidate component, not as a complete modern decomposition.  It produces a
machine-readable manifest plus normalized consensus regions that can be
reviewed and refined later.

All paths are explicit or relative to the project directory.  No temporary
files are written outside the project tree.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


NAME_RE = re.compile(r"^(?P<id>\d+)_(?P<char>.+?)_Z_(?P<source>.+)\.png$")
CANVAS = 128
INNER = 112


def parse_name(path: Path) -> dict:
    match = NAME_RE.match(path.name)
    if not match:
        return {
            "filename": path.name,
            "id": None,
            "char": None,
            "source": None,
            "parse_error": True,
        }
    item = match.groupdict()
    item["id"] = int(item["id"])
    item["filename"] = path.name
    item["parse_error"] = False
    return item


def load_mask(path: Path) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    image = Image.open(path).convert("L")
    array = np.asarray(image)
    ink = array < 245
    ys, xs = np.where(ink)
    if len(xs) == 0:
        return np.zeros((CANVAS, CANVAS), dtype=np.uint8), (0, 0, 0, 0)

    left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
    crop = Image.fromarray((ink[top:bottom, left:right] * 255).astype(np.uint8))
    scale = min(INNER / crop.width, INNER / crop.height)
    resized = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        Image.Resampling.NEAREST,
    )
    canvas = Image.new("L", (CANVAS, CANVAS), 0)
    x = (CANVAS - resized.width) // 2
    y = (CANVAS - resized.height) // 2
    canvas.paste(resized, (x, y))
    return (np.asarray(canvas) > 0).astype(np.uint8), (left, top, right, bottom)


def bbox(mask: np.ndarray) -> list[int]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return [0, 0, 0, 0]
    return [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]


def consensus(masks: list[np.ndarray]) -> tuple[np.ndarray, float]:
    if not masks:
        return np.zeros((CANVAS, CANVAS), dtype=np.uint8), 0.0
    stack = np.stack(masks)
    # The lower bound prevents a single unusual glyph from defining a group,
    # while still allowing small groups to produce a useful candidate.
    threshold = max(0.45, min(0.72, 1.0 - 1.0 / max(2, len(masks))))
    result = (stack.mean(axis=0) >= threshold).astype(np.uint8)
    coverage = float(result.sum() / max(1, (stack.mean(axis=0) > 0).sum()))
    return result, round(coverage, 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve()
    input_dir = (args.input or root / "按部首分类").resolve()
    output_path = (args.output or root / "analysis" / "component-candidates.json").resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    paths = sorted(input_dir.rglob("*.png"))
    groups: dict[str, list[tuple[Path, dict, np.ndarray, tuple[int, int, int, int]]]] = defaultdict(list)
    records: list[dict] = []
    parse_errors = []

    for path in paths:
        meta = parse_name(path)
        if meta["parse_error"]:
            parse_errors.append(str(path.relative_to(root)))
        try:
            mask, original_bbox = load_mask(path)
        except Exception as exc:  # keep the corpus scan resumable
            meta["load_error"] = str(exc)
            mask, original_bbox = np.zeros((CANVAS, CANVAS), dtype=np.uint8), (0, 0, 0, 0)
        relative = path.relative_to(root).as_posix()
        group = path.parent.name
        meta.update({"path": relative, "group": group, "width": Image.open(path).width, "height": Image.open(path).height})
        groups[group].append((path, meta, mask, original_bbox))

    group_results = {}
    for group, items in sorted(groups.items()):
        masks = [item[2] for item in items]
        shared, coverage = consensus(masks)
        group_results[group] = {
            "count": len(items),
            "candidate_component": group,
            "candidate_region_normalized": bbox(shared),
            "consensus_coverage": coverage,
            "confidence": "high" if len(items) >= 8 and coverage >= 0.45 else "medium" if len(items) >= 3 else "low",
        }
        shared_box = bbox(shared)
        for _, meta, _, original_box in items:
            left, top, right, bottom = original_box
            width = max(1, right - left)
            height = max(1, bottom - top)
            x0, y0, x1, y1 = shared_box
            meta["components"] = [{
                "name": group,
                "kind": "radical-folder-candidate",
                "confidence": group_results[group]["confidence"],
                "region": [
                    left + round((x0 - 8) / INNER * width),
                    top + round((y0 - 8) / INNER * height),
                    left + round((x1 - 8) / INNER * width),
                    top + round((y1 - 8) / INNER * height),
                ],
            }]
            meta["decomposition_status"] = "radical_candidate_only"
            records.append(meta)

    records.sort(key=lambda item: (item.get("id") is None, item.get("id") or 0, item["filename"]))
    payload = {
        "schema_version": 1,
        "generated_by": "scripts/analyze_components.py",
        "input": input_dir.relative_to(root).as_posix(),
        "image_count": len(records),
        "group_count": len(group_results),
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors,
        "groups": group_results,
        "records": records,
        "notes": [
            "The folder radical is a candidate component and is not a complete modern decomposition.",
            "Regions are heuristic mappings from normalized group consensus back to each source image.",
            "Records with decomposition_status=radical_candidate_only require modern-component data or review.",
        ],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = output_path.with_name("component-candidates-summary.md")
    top_groups = sorted(group_results.items(), key=lambda pair: pair[1]["count"], reverse=True)[:20]
    lines = [
        "# 部件候选分析摘要",
        "",
        f"- 图片：{len(records):,}",
        f"- 分组：{len(group_results):,}",
        f"- 文件名解析异常：{len(parse_errors):,}",
        "- 当前阶段：仅生成按部首文件夹推断的部件候选和启发式区域，尚未声称完成现代字体拆分。",
        "",
        "## 图片最多的分组",
        "",
        "| 分组 | 图片数 | 置信度 | 共识覆盖率 |",
        "| --- | ---: | --- | ---: |",
    ]
    lines.extend(f"| {name} | {info['count']} | {info['confidence']} | {info['consensus_coverage']:.4f} |" for name, info in top_groups)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "summary": str(summary_path), "images": len(records), "groups": len(group_results)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
