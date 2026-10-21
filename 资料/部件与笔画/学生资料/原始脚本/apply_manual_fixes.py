# -*- coding: utf-8 -*-
"""按人工审核意见重新标红。

用法：用户在 人工·/ 下建子文件夹，子文件夹名表达规则，里面放标错的字图
（文件名与 按部首分类/ 里的原图一致）。本脚本对每张图按规则重新选取
连通域标红，并覆盖 部首识别/<部首>/<结构>/ 里的对应输出。

支持的规则文件夹名：
- 最左：部首 = 像素重心 x 最小的连通域
- 最右：部首 = 像素重心 x 最大的连通域
- 最上：部首 = 像素重心 y 最小的连通域
- 最下：部首 = 像素重心 y 最大的连通域

修正记录写到 部首识别/_人工修正记录.csv。不改动 人工· 里的任何文件。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from mark_radicals_bucket_one import (  # noqa: E402
    NEIGHBORHOOD,
    load_component_csv,
    save_marked,
)
from identify_radical_images import get_filename_parts  # noqa: E402

RULE_BY_FOLDER = {"最左": "left", "最右": "right",
                  "最上": "top", "最下": "bottom"}


def pick(components: list[tuple], rule: str) -> int:
    """components 元素: (cx, cy, size, index)，返回 index。"""
    if rule == "left":
        return min(components, key=lambda c: (c[0], -c[2]))[3]
    if rule == "right":
        return max(components, key=lambda c: (c[0], c[2]))[3]
    if rule == "top":
        return min(components, key=lambda c: (c[1], -c[2]))[3]
    if rule == "bottom":
        return max(components, key=lambda c: (c[1], c[2]))[3]
    raise ValueError(rule)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    manual_root = next(d for d in root.iterdir()
                       if d.is_dir() and d.name.startswith("人工"))
    comp_cache: dict[str, dict] = {}

    log_rows: list[list] = []
    for folder in sorted(manual_root.iterdir()):
        rule = RULE_BY_FOLDER.get(folder.name)
        if rule is None or not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.png")):
            hits = list((root / "按部首分类").glob(f"*/{path.name}"))
            if not hits:
                log_rows.append([folder.name, path.name, "", "",
                                 "在按部首分类中找不到原图，跳过"])
                continue
            radical = hits[0].parent.name
            char, _ = get_filename_parts(hits[0])
            gray = np.asarray(Image.open(hits[0]).convert("L"))
            black = gray == 0

            if char == radical:  # 部首字本身整字标红，不存在选块
                mask = black
                note = "部首字本身，整字标红"
            else:
                labels, count = label(black, structure=NEIGHBORHOOD)
                comps = []
                for index in range(1, count + 1):
                    ys, xs = np.where(labels == index)
                    comps.append((float(xs.mean()), float(ys.mean()),
                                  int(xs.size), index))
                if not comps:
                    log_rows.append([folder.name, path.name, radical, char,
                                     "无墨迹，跳过"])
                    continue
                mask = labels == pick(comps, rule)
                note = ""

            # 输出位置：沿用现有结构子文件夹；没有就按部件组成 CSV 的结构
            if radical not in comp_cache:
                comp_cache[radical] = load_component_csv(root, radical)
            existing = list((root / "部首识别" / radical).rglob(path.name))
            if existing:
                out_dir = existing[0].parent
            else:
                structure = comp_cache[radical].get(
                    path.name, ("其他结构", []))[0]
                out_dir = root / "部首识别" / radical / structure
            save_marked(gray, mask, out_dir / path.name)
            log_rows.append([folder.name, path.name, radical, char,
                             f"已按{folder.name}规则重标 -> {out_dir.relative_to(root / '部首识别')}"
                             + (f"（{note}）" if note else "")])
            print(f"[{folder.name}] {char}: {log_rows[-1][4]}")

    with open(root / "部首识别" / "_人工修正记录.csv", "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["规则", "文件名", "部首", "字", "结果"])
        w.writerows(log_rows)
    print(f"共处理 {len(log_rows)} 条，记录 -> 部首识别/_人工修正记录.csv")


if __name__ == "__main__":
    main()
