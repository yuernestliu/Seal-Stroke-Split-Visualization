import math
from collections import defaultdict

import numpy as np

from .types import Point


NEIGHBOR_OFFSETS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]


def skeleton_neighbors(skeleton: np.ndarray, point: Point) -> list[Point]:
    h, w = skeleton.shape
    y, x = point
    out: list[Point] = []
    for dy, dx in NEIGHBOR_OFFSETS:
        ny, nx = y + dy, x + dx
        if not (0 <= ny < h and 0 <= nx < w and skeleton[ny, nx]):
            continue
        if dy != 0 and dx != 0:
            orth1 = (y, x + dx)
            orth2 = (y + dy, x)
            has_orth1 = 0 <= orth1[0] < h and 0 <= orth1[1] < w and skeleton[orth1]
            has_orth2 = 0 <= orth2[0] < h and 0 <= orth2[1] < w and skeleton[orth2]
            if has_orth1 or has_orth2:
                continue
        out.append((ny, nx))
    return out


def build_graph(skeleton: np.ndarray) -> dict[Point, list[Point]]:
    points = np.argwhere(skeleton)
    graph: dict[Point, list[Point]] = {}
    for y, x in points:
        point = (int(y), int(x))
        graph[point] = skeleton_neighbors(skeleton, point)
    return graph


def node_degrees(graph: dict[Point, list[Point]]) -> dict[Point, int]:
    return {point: len(neigh) for point, neigh in graph.items()}


def _direction_cosine(a: Point, b: Point, c: Point) -> float:
    """Compute cosine of angle between vectors (a->b) and (b->c). Higher = more aligned."""
    dx1, dy1 = b[0] - a[0], b[1] - a[1]
    dx2, dy2 = c[0] - b[0], c[1] - b[1]
    norm1 = math.hypot(dx1, dy1)
    norm2 = math.hypot(dx2, dy2)
    if norm1 == 0 or norm2 == 0:
        return -1.0
    return (dx1 * dx2 + dy1 * dy2) / (norm1 * norm2)


def trace_paths(
    graph: dict[Point, list[Point]],
) -> list[list[Point]]:
    """Trace skeleton paths. Returns list of paths (each is list of points)."""
    degrees = node_degrees(graph)
    critical = {p for p, d in degrees.items() if d != 2}
    visited_edges: set[tuple[Point, Point]] = set()
    paths: list[list[Point]] = []

    def edge_key(a: Point, b: Point) -> tuple[Point, Point]:
        return tuple(sorted((a, b)))

    def _trace_from(start: Point, first: Point) -> None:
        path = [start, first]
        visited_edges.add(edge_key(start, first))
        prev, cur = start, first
        while True:
            deg = degrees.get(cur, 0)
            if deg != 2:
                break
            nxt_candidates = [p for p in graph[cur] if p != prev]
            if not nxt_candidates:
                break
            nxt = nxt_candidates[0]
            key = edge_key(cur, nxt)
            if key in visited_edges:
                break
            path.append(nxt)
            visited_edges.add(key)
            prev, cur = cur, nxt
        paths.append(path)

    for start in critical:
        for nxt in graph[start]:
            key = edge_key(start, nxt)
            if key in visited_edges:
                continue
            _trace_from(start, nxt)

    leftover = set()
    for point, neighs in graph.items():
        for neigh in neighs:
            key = tuple(sorted((point, neigh)))
            if key not in visited_edges:
                leftover.add(key)

    while leftover:
        a, b = leftover.pop()
        cycle = [a, b]
        prev, cur = a, b
        while True:
            neighbors = [p for p in graph[cur] if p != prev]
            if not neighbors:
                break
            nxt = neighbors[0]
            key = tuple(sorted((cur, nxt)))
            if key in leftover:
                leftover.remove(key)
            if nxt == cycle[0]:
                cycle.append(nxt)
                break
            cycle.append(nxt)
            prev, cur = cur, nxt
        paths.append(cycle)

    return [path for path in paths if len(path) >= 2]


def collapse_short_bridges(graph: dict[Point, list[Point]], max_bridge_len: int = 3) -> tuple[dict[Point, list[Point]], dict[Point, int]]:
    """塌缩连接两个非度2节点（交叉点/端点）的短度2链（短桥/毛刺）。

    骨架细化常在交叉点附近产生 1~3 像素的短桥或毛刺像素，它们会在端点聚类时
    充当"伪连接器"，把本应独立的两笔通过直通判据误并。本函数把中间度2节点数
    <= max_bridge_len 的短链塌缩：保留两端、删掉中间、直接连两端邻居。

    特别地，当一端是度1毛刺时，毛刺点会被对端交叉点"吸收"为其新位置，
    从而同时消除毛刺并合并相近交叉点。

    max_bridge_len=0 时不做任何塌缩。
    """
    if max_bridge_len <= 0:
        return graph, node_degrees(graph)
    g = {k: list(v) for k, v in graph.items()}
    deg = {p: len(nbrs) for p, nbrs in g.items()}

    def recompute(p: Point) -> None:
        deg[p] = len(g.get(p, []))

    changed = True
    while changed:
        changed = False
        critical = [p for p, d in deg.items() if d != 2]
        for a in critical:
            if a not in g:
                continue
            for first in list(g[a]):
                path = [a, first]
                prev, cur = a, first
                while deg.get(cur, 0) == 2:
                    nbrs = [p for p in g[cur] if p != prev]
                    if not nbrs:
                        break
                    nxt = nbrs[0]
                    path.append(nxt)
                    prev, cur = cur, nxt
                if cur == a or cur not in g:
                    continue
                if deg.get(cur, 0) == 2:
                    continue
                intermediate = len(path) - 2
                if intermediate > max_bridge_len:
                    continue
                b = cur
                b_bridge_nb = path[-2]
                # 把 b 的非桥邻居接到 a 上
                for nb in list(g[b]):
                    if nb == b_bridge_nb:
                        continue
                    if nb not in g[a]:
                        g[a].append(nb)
                    if a not in g[nb]:
                        g[nb].append(a)
                # 删除中间节点（含 b 端），从其邻居列表里清掉引用
                for node in path[1:]:
                    for nn in list(g.get(node, [])):
                        if node in g.get(nn, []):
                            g[nn] = [p for p in g[nn] if p != node]
                    g.pop(node, None)
                    deg.pop(node, None)
                # a 不再连 first（已被塌缩掉）
                if first in g[a]:
                    g[a] = [p for p in g[a] if p != first]
                recompute(a)
                changed = True
                break
            if changed:
                break
    return g, deg


def point_distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_angle(a: Point, b: Point) -> float:
    return math.atan2(b[0] - a[0], b[1] - a[1])


def angle_delta_deg(a1: float, a2: float) -> float:
    diff = abs(a1 - a2)
    diff = min(diff, 2 * math.pi - diff)
    return math.degrees(diff)


# 在 skeleton_graph.py 中

def group_by_endpoint(
    segments: list[list[Point]],
    max_gap: float = 0.0,
) -> list[tuple[Point, list[tuple[int, bool]]]]:
    """
    把段的端点按距离聚类。距离 <= max_gap 的端点归为同一聚类（同一段的起止不互相聚合）。
    返回 [(代表点, [(seg_idx, is_start), ...]), ...]。
    max_gap=0 时退化为精确坐标匹配。
    """
    eps: list[tuple[int, int, int, bool]] = []  # (y, x, seg_idx, is_start)
    for idx, seg in enumerate(segments):
        if not seg:
            continue
        eps.append((seg[0][0], seg[0][1], idx, True))
        eps.append((seg[-1][0], seg[-1][1], idx, False))
    if not eps:
        return []

    n = len(eps)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # 同一段的两个端点（桥段两端）不应聚类——它们是骨架上相连的两个交叉点，
    # 不是同一交叉点的错位端点。这样可以在用大 gap 聚拢同交叉点散落端点的
    # 同时，避免把桥段两端的两个不同交叉点误并。
    same_seg_ends: set[tuple[Point, Point]] = set()
    for seg in segments:
        if len(seg) >= 2:
            a: Point = (seg[0][0], seg[0][1])
            b: Point = (seg[-1][0], seg[-1][1])
            if a != b:
                same_seg_ends.add((a, b))
                same_seg_ends.add((b, a))

    if max_gap > 0:
        g2 = max_gap * max_gap
        for i in range(n):
            for j in range(i + 1, n):
                if eps[i][2] == eps[j][2]:  # 同一段的起止不聚合
                    continue
                a_pt: Point = (eps[i][0], eps[i][1])
                b_pt: Point = (eps[j][0], eps[j][1])
                if (a_pt, b_pt) in same_seg_ends:  # 桥段两端不聚类
                    continue
                dy = eps[i][0] - eps[j][0]
                dx = eps[i][1] - eps[j][1]
                if dy * dy + dx * dx <= g2:
                    union(i, j)
    else:
        for i in range(n):
            for j in range(i + 1, n):
                if eps[i][2] == eps[j][2]:
                    continue
                a_pt2: Point = (eps[i][0], eps[i][1])
                b_pt2: Point = (eps[j][0], eps[j][1])
                if (a_pt2, b_pt2) in same_seg_ends:
                    continue
                if eps[i][0] == eps[j][0] and eps[i][1] == eps[j][1]:
                    union(i, j)

    groups: dict[int, list[tuple[int, int, int, bool]]] = defaultdict(list)
    for i, ep in enumerate(eps):
        groups[find(i)].append(ep)

    clusters: list[tuple[Point, list[tuple[int, bool]]]] = []
    for members in groups.values():
        rep: Point = (members[0][0], members[0][1])
        clusters.append((rep, [(m[2], m[3]) for m in members]))
    return clusters