"""
笔画排序模块：基于现代人笔顺直觉，对拆分后的笔画进行排序。
不依赖任何训练数据，纯几何逻辑。

排序判据全部基于骨架点 (StrokeSegment.points)。

部件内排序：每条笔画与同部件所有其它笔画两两比较，累计胜场；
胜场多的排前面，胜场相同的按重心排（先上后下、同行先左后右）。

交叉处统计：同一交叉处按 8 邻域聚成一块；若某块包含该笔画的端点
（points[0] 或 points[-1]），整块丢弃，不计入该笔画的交叉数（端点交叉不算）。
"""

from typing import List, Tuple
from collections import defaultdict
from functools import cmp_to_key
import numpy as np

from .types import Point, StrokeSegment


# ============================================================
# 1. 部件聚类（Union-Find）—— 基于骨架点共享（精确相等）
# ============================================================

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.rank[ra], self.rank[rb] = self.rank[rb], self.rank[ra]
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def cluster_components(
    segments: List[StrokeSegment]
) -> List[List[int]]:
    """将笔画按骨架点共享聚类为部件。返回: List[部件]，每个部件是笔画索引列表。"""
    n = len(segments)
    if n == 0:
        return []

    point_sets = [set(seg.points) for seg in segments]

    uf = UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if point_sets[i] & point_sets[j]:
                uf.union(i, j)

    groups: dict[int, List[int]] = defaultdict(list)
    for i in range(n):
        root = uf.find(i)
        groups[root].append(i)

    return list(groups.values())


# ============================================================
# 2. 部件排序 —— 基于骨架重心
# ============================================================

ROW_THRESHOLD = 5


def segment_center(seg: StrokeSegment) -> Tuple[float, float]:
    """计算骨架段重心 (y, x)"""
    pts = seg.points
    if not pts:
        return (0.0, 0.0)
    ys = [p[0] for p in pts]
    xs = [p[1] for p in pts]
    return (float(np.mean(ys)), float(np.mean(xs)))


def _center_compare(a_idx: int, b_idx: int, segments: List[StrokeSegment]) -> int:
    """重心比较：a 在前返回负数，b 在前返回正数，相等返回 0。
    先上后下；y 差 < ROW_THRESHOLD 算同一行，同行先左后右。
    """
    ay, ax = segment_center(segments[a_idx])
    by, bx = segment_center(segments[b_idx])
    if abs(ay - by) < ROW_THRESHOLD:
        if ax < bx:
            return -1
        if ax > bx:
            return 1
        return 0
    return -1 if ay < by else 1


def sort_components(
    components: List[List[int]],
    segments: List[StrokeSegment]
) -> List[List[int]]:
    """对部件进行排序（先上后下，同一行则先左后右），基于骨架重心。"""
    if len(components) <= 1:
        return components

    comp_info = []
    for comp in components:
        all_ys: List[int] = []
        all_xs: List[int] = []
        for idx in comp:
            for y, x in segments[idx].points:
                all_ys.append(y)
                all_xs.append(x)
        if all_ys:
            cy = float(np.mean(all_ys))
            cx = float(np.mean(all_xs))
        else:
            cy = cx = 0.0
        comp_info.append({'indices': comp, 'y': cy, 'x': cx})

    def comp_key(item):
        return (int(item['y'] // ROW_THRESHOLD), item['x'])

    comp_info.sort(key=comp_key)
    return [item['indices'] for item in comp_info]


# ============================================================
# 3. 闭合笔画检测 —— 基于骨架首尾
# ============================================================

def is_closed_stroke(seg: StrokeSegment) -> bool:
    """骨架段是否闭合：首尾骨架点足够近，且路径足够长。"""
    pts = seg.points
    if len(pts) < 8:
        return False
    y0, x0 = pts[0]
    y1, x1 = pts[-1]
    return abs(y0 - y1) <= 1 and abs(x0 - x1) <= 1


# ============================================================
# 4. 部件内排序 —— 两两比较 + 胜场累计
# ============================================================

def _intersection_count(
    idx: int,
    segments: List[StrokeSegment],
    point_sets: List[set],
) -> int:
    """idx 段与其它笔画的骨架有多少处交集（不含端点交叉）。

    同一交叉处可能共享连续多个骨架点，按 8 邻域连通聚成"一处"。
    共享点判定用精确相等坐标。
    若某处包含 idx 的端点（points[0] 或 points[-1]），整块丢弃，不计入交叉数。
    各段各算各的：同一处对 A 可能是端点交叉（不算），对 B 可能是中间交叉（算）。
    """
    own = point_sets[idx]
    shared_points = set()
    for j, other in enumerate(point_sets):
        if j == idx:
            continue
        shared_points |= (own & other)

    if not shared_points:
        return 0

    pts = segments[idx].points
    if not pts:
        return 0
    end_points = {pts[0], pts[-1]}

    shared_list = list(shared_points)
    shared_set = set(shared_list)
    visited = set()
    count = 0
    for p in shared_list:
        if p in visited:
            continue
        block = []
        queue = [p]
        visited.add(p)
        while queue:
            cy, cx = queue.pop()
            block.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    npt = (cy + dy, cx + dx)
                    if npt in shared_set and npt not in visited:
                        visited.add(npt)
                        queue.append(npt)
        # 这一块是否包含 idx 的端点；包含则整块丢弃
        if any(pt in end_points for pt in block):
            continue
        count += 1
    return count


def _y_range(seg: StrokeSegment) -> Tuple[int, int]:
    """段的骨架点 y 范围 (min_y, max_y)。空段返回 (0, 0)。"""
    ys = [p[0] for p in seg.points]
    if not ys:
        return (0, 0)
    return (min(ys), max(ys))


def _compare_strokes(
    a_idx: int,
    b_idx: int,
    segments: List[StrokeSegment],
    crossings_cache: dict,
) -> int:
    """两两比较 A、B。A 赢返回 1，B 赢返回 -1。

    规则：
      1. A 所有点 y <= B 所有点 y（允许接触）→ A 赢
         B 所有点 y <= A 所有点 y → B 赢
         否则进规则 2
      2. 交叉处数量多的赢
      3. 交叉数相同 → 重心（先上后下、同行先左后右）
    """
    a_min_y, a_max_y = _y_range(segments[a_idx])
    b_min_y, b_max_y = _y_range(segments[b_idx])

    # 规则 1
    if a_max_y <= b_min_y:
        return 1
    if b_max_y <= a_min_y:
        return -1

    # 规则 2
    a_cross = crossings_cache[a_idx]
    b_cross = crossings_cache[b_idx]
    if a_cross > b_cross:
        return 1
    if a_cross < b_cross:
        return -1

    # 规则 3
    cmp = _center_compare(a_idx, b_idx, segments)
    return -cmp  # _center_compare 返回负数表示 a 在前，转成 a 赢返回 1


def sort_strokes_within_component(
    indices: List[int],
    segments: List[StrokeSegment],
    point_sets: List[set],
) -> List[int]:
    """部件内排序：每条笔画与同部件所有其它笔画两两比较，累计胜场。"""
    if len(indices) <= 1:
        return indices

    # 预计算交叉数（两两比较里反复用）
    crossings_cache = {
        idx: _intersection_count(idx, segments, point_sets)
        for idx in indices
    }

    # 每条笔画累计胜场
    wins = {idx: 0 for idx in indices}
    for i in range(len(indices)):
        for j in range(i + 1, len(indices)):
            a_idx = indices[i]
            b_idx = indices[j]
            result = _compare_strokes(a_idx, b_idx, segments, crossings_cache)
            if result > 0:
                wins[a_idx] += 1
            elif result < 0:
                wins[b_idx] += 1
            # result == 0 时（规则3兜底，理论不会到 0）不加分

    def final_cmp(a_idx: int, b_idx: int) -> int:
        if wins[a_idx] != wins[b_idx]:
            return -1 if wins[a_idx] > wins[b_idx] else 1
        return _center_compare(a_idx, b_idx, segments)

    return sorted(indices, key=cmp_to_key(final_cmp))


# ============================================================
# 5. 主入口
# ============================================================

def order_strokes(
    stroke_masks: List[np.ndarray],
    segments: List[StrokeSegment]
) -> Tuple[List[np.ndarray], List[StrokeSegment]]:
    """对笔画进行排序的主入口函数。

    排序判据全部基于骨架段 (segments)；stroke_masks 仅按最终顺序重排后返回。
    """
    if len(segments) <= 1:
        return stroke_masks, segments

    point_sets = [set(seg.points) for seg in segments]

    components = cluster_components(segments)
    components_sorted = sort_components(components, segments)

    sorted_indices: List[int] = []
    for comp in components_sorted:
        inner_sorted = sort_strokes_within_component(comp, segments, point_sets)
        sorted_indices.extend(inner_sorted)

    sorted_masks = [stroke_masks[i] for i in sorted_indices]
    sorted_segments = [segments[i] for i in sorted_indices]

    for new_id, seg in enumerate(sorted_segments, start=1):
        seg.stroke_id = new_id

    return sorted_masks, sorted_segments