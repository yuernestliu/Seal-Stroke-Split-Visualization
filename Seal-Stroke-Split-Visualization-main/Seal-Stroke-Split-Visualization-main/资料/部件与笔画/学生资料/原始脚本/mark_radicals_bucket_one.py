# -*- coding: utf-8 -*-
"""按"部件组成"CSV 推断部首槽位并标红（方法由用户 2026-10 指定）。

核心思路：读 部件组成/<部首>.csv 的"结构"和"归一部件"两列，
按部件书写顺序（= IDS 首层顺序 = 空间顺序）推断部首所在槽位：
- 左右/左中右结构：槽位 0 = 最左，末位 = 最右，中间位 = 最接近中列区域
- 上下/上中下结构：槽位 0 = 最上，末位 = 最下，中间位 = 最接近中行区域
  （"最左/最下"等均按连通域像素重心判断，平手取块更大的）

其他规则：
- 部首字本身（如"口"）：整字标红
- 部首在归一部件中出现多次：按首次槽位选取，并标待复核
- 独体结构无法定位：保留未标红原图，进待复核
- 其他结构（含包围类，槽位推断不可靠）：用 IDS 部首目标框选最近重心，
  全部进待复核
- 灰色抗锯齿像素归入最近的黑色连通域，同判红/灰
- 选中块占整字墨迹超 85% 标疑似粘连，进待复核

图像规则（项目铁律）：灰度 ==0 为墨迹，8 邻域连通域。
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, label

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from identify_radical_images import (  # noqa: E402
    choose_alternative,
    get_filename_parts,
    load_ids,
    locate_target,
    parse_tree,
)

NEIGHBORHOOD = np.ones((3, 3), dtype=np.uint8)
OVERSIZE_RATIO = 0.85    # 选中块占整字墨迹比例警戒线

LINEAR_H = {"左右结构", "左中右结构"}
LINEAR_V = {"上下结构", "上中下结构"}

# 部件组成 CSV 的"结构"列是简称，映射回全称
SHORT2FULL = {"左右": "左右结构", "上下": "上下结构",
              "左中右": "左中右结构", "上中下": "上中下结构",
              "独体": "独体"}


def load_component_csv(root: Path, radical: str) -> dict:
    """读 部件组成/<部首>.csv -> {文件名: (结构, [归一部件...])}"""
    path = root / "部件组成" / f"{radical}.csv"
    if not path.exists():
        return {}
    info = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            parts = [p for p in row["归一部件"].split("；") if p]
            info[row["文件名"]] = (SHORT2FULL.get(row["结构"], "其他结构"), parts)
    return info


def save_marked(gray: np.ndarray, mask: np.ndarray, path: Path) -> None:
    """部首块染红（按墨迹深浅渐变），灰色像素按最近黑色连通域归属。"""
    rgb = np.repeat(gray[:, :, None], 3, axis=2).astype(np.uint8)
    black = gray == 0
    red_gray = np.zeros_like(black)
    if black.any() and mask.any():
        black_labels, _ = label(black, structure=NEIGHBORHOOD)
        selected = set(np.unique(black_labels[mask & black])) - {0}
        _, nearest = distance_transform_edt(~black, return_indices=True)
        nearest_labels = black_labels[tuple(nearest)]
        red_gray = (gray != 0) & (gray < 255) & np.isin(
            nearest_labels, list(selected))
    red_mask = (mask & black) | red_gray
    strength = np.clip((255.0 - gray) / 255.0, 0.0, 1.0)
    red = np.stack([255.0 - 35.0 * strength,
                    255.0 - 215.0 * strength,
                    255.0 - 215.0 * strength], axis=2).astype(np.uint8)
    rgb[red_mask] = red[red_mask]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        Image.fromarray(rgb, mode="RGB").save(f, format="PNG")


def pick_by_slot(comps: list[tuple], structure: str, slot: int, n: int) -> tuple:
    """按槽位选连通域。comps 元素: (cx_norm, cy_norm, size, index)。

    槽位 0 取最左/最上，末位取最右/最下；中间槽位取最接近
    该槽位区域中心的（区域按 n 等分）。
    """
    horizontal = structure in LINEAR_H

    def coord(c):
        return c[0] if horizontal else c[1]

    if slot == 0:
        return min(comps, key=lambda c: (coord(c), -c[2]))
    if slot == n - 1:
        return max(comps, key=lambda c: (coord(c), c[2]))
    center = (slot + 0.5) / n
    return min(comps, key=lambda c: (abs(coord(c) - center), -c[2]))


def nearest_box_mask(black: np.ndarray, ids: dict, char: str,
                     radical: str) -> tuple[np.ndarray | None, str | None]:
    """暂替策略：用 IDS 部首目标框选重心最近的连通域。失败返回 (None, seq)。"""
    sequences = ids.get(char)
    if not sequences:
        return None, None
    sequence = choose_alternative(sequences)[0]
    box = None
    try:
        tree, used = parse_tree(sequence)
        if used == len(sequence):
            box, _outer = locate_target(tree, {radical})
    except (IndexError, ValueError):
        box = None
    if box is None:
        return None, sequence

    labels, count = label(black, structure=NEIGHBORHOOD)
    if count == 0:
        return np.zeros_like(black), sequence
    hgt, wid = black.shape
    bx0, by0, bx1, by1 = box
    tx, ty = (bx0 + bx1) / 2, (by0 + by1) / 2
    comps = []
    for index in range(1, count + 1):
        ys, xs = np.where(labels == index)
        comps.append((xs.mean() / max(1, wid - 1), ys.mean() / max(1, hgt - 1),
                      int(xs.size), index))
    chosen = min(comps, key=lambda c: ((c[0] - tx) ** 2 + (c[1] - ty) ** 2,
                                       -c[2]))
    return labels == chosen[3], sequence


def contact_sheet(radical: str, rows: list, root: Path) -> None:
    out = root / "部首识别" / f"_对照_{radical}.html"
    lines = ["<!doctype html><meta charset='utf-8'>",
             "<title>部首标红对照 - %s</title>" % radical,
             "<style>body{font-family:sans-serif;background:#222;color:#eee}"
             "table{border-collapse:collapse}td{padding:4px;border:1px solid #555;"
             "font-size:12px}img{width:140px;height:140px;object-fit:contain;"
             "background:#fff}.bad{color:#ff6b6b}</style>",
             "<h2>部首标红对照：%s（左原图 / 右标红）</h2><table>" % radical]
    for _, fname, char, structure, status in rows:
        cls = " class='bad'" if status == "复核" else ""
        lines.append(
            f"<tr><td>{char}{cls}<br>{structure}<br>{status}</td>"
            f"<td><img src='../按部首分类/{radical}/{fname}'></td>"
            f"<td><img src='{radical}/{structure}/{fname}'></td></tr>")
    lines.append("</table>")
    out.write_text("\n".join(lines), encoding="utf-8")


def process_radical(radical: str, root: Path, ids: dict):
    source = root / "按部首分类" / radical
    out_root = root / "部首识别" / radical
    if out_root.exists():
        shutil.rmtree(out_root)  # 本目录全部为本脚本生成产物
    out_root.mkdir(parents=True)
    comp_info = load_component_csv(root, radical)

    rows, reviews = [], []
    for path in sorted(source.glob("*.png")):
        char, _ = get_filename_parts(path)
        gray = np.asarray(Image.open(path).convert("L"))
        black = gray == 0

        if char == radical:  # 部首字本身：整字标红
            save_marked(gray, black, out_root / "其他结构" / path.name)
            rows.append([radical, path.name, char, "其他结构", "自动"])
            continue

        info = comp_info.get(path.name)
        if info is None:  # CSV 覆盖全语料，正常不会走到这里
            reviews.append([radical, path.name, char, "",
                            "部件组成CSV无此字，未标红", ""])
            save_marked(gray, np.zeros_like(black),
                        out_root / "其他结构" / path.name)
            rows.append([radical, path.name, char, "", "复核"])
            continue
        structure, parts = info

        if structure == "独体":  # 独体无槽位可言，交人工
            reviews.append([radical, path.name, char, structure,
                            "独体结构无法定位，未标红请复核", ""])
            save_marked(gray, np.zeros_like(black),
                        out_root / structure / path.name)
            rows.append([radical, path.name, char, structure, "复核"])
            continue

        if structure not in LINEAR_H and structure not in LINEAR_V:
            # 包围等其他结构：槽位推断不可靠，暂用 IDS 目标框，全部进复核
            mask, sequence = nearest_box_mask(black, ids, char, radical)
            if mask is None:
                reviews.append([radical, path.name, char, structure,
                                "定位无目标框，未标红请复核", sequence or ""])
                save_marked(gray, np.zeros_like(black),
                            out_root / structure / path.name)
                rows.append([radical, path.name, char, structure, "复核"])
                continue
            reviews.append([radical, path.name, char, structure,
                            "按最近目标框选取，请复核", sequence or ""])
            save_marked(gray, mask, out_root / structure / path.name)
            rows.append([radical, path.name, char, structure, "复核"])
            continue

        if radical not in parts:
            reviews.append([radical, path.name, char, structure,
                            "归一部件中无部首，未标红请复核", ""])
            save_marked(gray, np.zeros_like(black),
                        out_root / structure / path.name)
            rows.append([radical, path.name, char, structure, "复核"])
            continue

        flags = []
        if parts.count(radical) > 1:
            flags.append("部首多次出现，按首次位置选取")
        slot = parts.index(radical)
        n = len(parts)

        labels, count = label(black, structure=NEIGHBORHOOD)
        if count == 0:
            reviews.append([radical, path.name, char, structure, "无墨迹", ""])
            rows.append([radical, path.name, char, structure, "复核"])
            continue
        hgt, wid = black.shape
        comps = []
        for index in range(1, count + 1):
            ys, xs = np.where(labels == index)
            comps.append((xs.mean() / max(1, wid - 1),
                          ys.mean() / max(1, hgt - 1),
                          int(xs.size), index))

        chosen = pick_by_slot(comps, structure, slot, n)
        mask = labels == chosen[3]

        ratio = mask.sum() / max(1, black.sum())
        if ratio > OVERSIZE_RATIO:
            flags.append(f"选中块占整字{ratio:.0%}，疑似粘连")
        for flag in flags:
            reviews.append([radical, path.name, char, structure, flag, ""])

        save_marked(gray, mask, out_root / structure / path.name)
        rows.append([radical, path.name, char, structure,
                     "复核" if flags else "自动"])
    return rows, reviews


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radical", action="append", required=True,
                    help="可重复：--radical 口 --radical 十")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    ids = load_ids(root / "data" / "ids.txt")

    all_reviews: list[list] = []
    for radical in args.radical:
        rows, reviews = process_radical(radical, root, ids)
        contact_sheet(radical, rows, root)
        auto = sum(1 for r in rows if r[4] == "自动")
        print(f"{radical}: 共 {len(rows)}，自动 {auto}，复核 {len(rows) - auto}")
        all_reviews.extend(reviews)

    name = "+".join(args.radical)
    if len(name) > 80:  # 部首太多时拼接名会超 Windows 文件名上限
        name = "批量"
    with open(root / "部首识别" / f"_待复核_{name}.csv", "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["部首", "文件名", "字", "结构", "原因", "IDS序列"])
        w.writerows(all_reviews)
    print(f"待复核合计 {len(all_reviews)} 条 -> 部首识别/_待复核_{name}.csv")


if __name__ == "__main__":
    main()
