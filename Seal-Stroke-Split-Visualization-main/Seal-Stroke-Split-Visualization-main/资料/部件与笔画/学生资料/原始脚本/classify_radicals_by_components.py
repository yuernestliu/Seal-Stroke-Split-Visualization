# -*- coding: utf-8 -*-
"""按部首字的连通域数量，把整个部首子文件夹归类到 按连通域分类/一、二、三...

定义（用户给定）：
- 相连：一个像素与周围 8 个像素（8 邻域）中任一墨迹像素相连
- 连通域：8 邻域传递闭包构成的墨迹块
- 墨迹：灰度像素值 == 0（项目铁律）
- 部首字：与部首文件夹同名的那个字图（如 刀 文件夹里的 07616_刀_Z_說文‧刀部.png）
- 归类单位：整个部首文件夹（如 按部首分类/刀 整体复制到 按连通域分类/一/刀）

只新增 按连通域分类/ 目录，不修改任何现有文件；每次运行先清空重建该目录。
"""
import csv
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(r"d:\古汉字网站\GitHub新\Seal-Stroke-Split-Visualization")
SRC = ROOT / "按部首分类"
DST = ROOT / "按连通域分类"

CN = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
      6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}


def cn(n: int) -> str:
    if n <= 10:
        return CN[n]
    if n < 20:
        return "十" + CN[n - 10]
    return str(n)  # 超过十九按数字命名（预计不会出现）


STRUCT8 = np.ones((3, 3), dtype=int)  # 8 邻域


def count_components(png_path: Path):
    """返回该图的墨迹连通域数；无墨迹返回 None"""
    arr = np.array(Image.open(png_path).convert("L"))
    ink = arr == 0
    if not ink.any():
        return None
    _, n = ndimage.label(ink, structure=STRUCT8)
    return n


def main():
    if DST.exists():
        shutil.rmtree(DST)  # 清空重建（本目录全部为生成产物）
    DST.mkdir(exist_ok=True)
    rows, fails = [], []

    for rdir in sorted(SRC.iterdir()):
        if not rdir.is_dir():
            continue
        radical = rdir.name
        self_file = None
        for png in sorted(rdir.rglob("*.png")):
            parts = png.stem.split("_")
            if len(parts) >= 2 and parts[1] == radical:
                self_file = png
                break
        if self_file is None:
            fails.append([radical, "未找到与部首同名的字图"])
            continue

        n = count_components(self_file)
        if n is None:
            fails.append([radical, f"图像无墨迹: {self_file.name}"])
            continue

        shutil.copytree(rdir, DST / cn(n) / radical)  # 整个部首文件夹复制
        rows.append([radical, self_file.name, n, cn(n)])

    with open(DST / "_明细.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["部首", "文件名", "连通域数", "归入子文件夹"])
        w.writerows(rows)

    with open(DST / "_未找到部首字.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["部首文件夹", "原因"])
        w.writerows(fails)

    dist = Counter(r[2] for r in rows)
    print(f"成功: {len(rows)}  失败: {len(fails)}")
    for k in sorted(dist):
        print(f"  {k} 个连通域: {dist[k]} 个部首 -> {cn(k)}")
    if fails:
        print("失败清单:")
        for r in fails:
            print("  ", r)


if __name__ == "__main__":
    main()
