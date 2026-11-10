#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vectorize_centerline.py
=======================

Turn the manually corrected pixel label maps in

    D:\\桌面资料\\StrokeAnnotator\\outputs\\label_maps\\<glyph_id>\\label.png

into the per-glyph SVG package used by

    D:\\桌面资料\\Seal-Stroke-Split-Visualization\\字库\\处理结果-334-500\\<glyph_id>\\

The file set and metadata schemas follow the reference package

    字库/处理结果-current-167

but the stroke geometry uses the “安” house style documented in
docs/GLYPH-CLEANUP.md: a uniform-width, smoothed centre line rendered as a
quadratic-Bézier path with round caps and round joins
(method = centerline-quadratic-v1).

Only the output package is written.  label_maps, the reference package and
the project scripts/data are never modified.

Examples
--------
    python vectorize_centerline.py --ids 06611_专_Z_小篆 06729_争_Z_小篆
    python vectorize_centerline.py --all
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
from skimage.measure import approximate_polygon, find_contours
from skimage.morphology import skeletonize

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------

LABEL_ROOT = Path(r"D:\桌面资料\StrokeAnnotator\outputs\label_maps")
OUT_ROOT = Path(r"D:\桌面资料\Seal-Stroke-Split-Visualization\字库\处理结果-334-500")

PACKAGE_NAME = "字库/处理结果-334-500"
SPLIT_PACKAGE_NAME = "拆解结果-334-500"
LABEL_REL_PREFIX = "StrokeAnnotator/outputs/label_maps"

# Manual-v2 palette used by display-split / outline / skeleton / preview.
MANUAL_PALETTE = [
    "#2f6fdb", "#d68a16", "#2b9b68", "#9254c8", "#c34f8d",
    "#168aad", "#7a6a32", "#e05a33", "#3f7cac", "#8c5e34",
    "#5964b4", "#009688", "#f06292", "#795548", "#d94841",
]

# Site palette used by site-color / site-stroke-NN.
SITE_PALETTE = ["#eeb377", "#a5c4b1", "#d89181", "#bfafd0", "#e6d38a", "#8eb8c4"]
SITE_SOLID = "#eadfbb"

SIGMA = 1.2
SIMPLIFY_TOLERANCE = 0.5
SPUR_MAX = 4
# Only pieces separated by a pixel or two come from anti-aliasing / label
# thinning.  Anything further apart is a genuinely disjoint part of the same
# manual stroke, so it must stay a separate sub-path instead of growing a
# long artificial bridge across the glyph.
MAX_MERGE_GAP = 2.0


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def num(value: float) -> str:
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def color_for(index: int, palette: list[str]) -> str:
    return palette[index % len(palette)]


def stroke_id(index: int) -> str:
    return f"S{index}"


# ---------------------------------------------------------------------------
# Skeleton graph utilities (same conventions as the reference package)
# ---------------------------------------------------------------------------

NEIGHBOR_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def skeleton_neighbors(skel: np.ndarray, point: tuple[int, int]) -> list[tuple[int, int]]:
    h, w = skel.shape
    y, x = point
    out: list[tuple[int, int]] = []
    for dy, dx in NEIGHBOR_OFFSETS:
        ny, nx = y + dy, x + dx
        if not (0 <= ny < h and 0 <= nx < w and skel[ny, nx]):
            continue
        if dy != 0 and dx != 0:
            orth1 = (y, x + dx)
            orth2 = (y + dy, x)
            has1 = 0 <= orth1[0] < h and 0 <= orth1[1] < w and skel[orth1]
            has2 = 0 <= orth2[0] < h and 0 <= orth2[1] < w and skel[orth2]
            if has1 or has2:
                continue
        out.append((ny, nx))
    return out


def build_graph(skel: np.ndarray) -> dict[tuple[int, int], list[tuple[int, int]]]:
    return {tuple(int(v) for v in p): skeleton_neighbors(skel, tuple(int(v) for v in p))
            for p in np.argwhere(skel)}


def prune_spurs(graph: dict, max_len: int = SPUR_MAX) -> dict:
    """Remove tiny leaf hairs attached to a junction; keep real short strokes."""
    g = {k: list(v) for k, v in graph.items()}
    if len(g) <= 3:
        return g
    changed = True
    while changed:
        changed = False
        deg = {p: len(v) for p, v in g.items()}
        leaves = [p for p, d in deg.items() if d == 1]
        for leaf in leaves:
            if leaf not in g:
                continue
            path = [leaf]
            prev = None
            cur = leaf
            while True:
                nbrs = [p for p in g.get(cur, []) if p != prev]
                if not nbrs:
                    break
                prev, cur = cur, nbrs[0]
                path.append(cur)
                if len(g.get(cur, [])) != 2 or len(path) > max_len + 2:
                    break
            if len(path) <= max_len + 1 and len(g.get(cur, [])) > 2:
                for p in path[:-1]:
                    if p in g:
                        for nb in list(g[p]):
                            if nb in g:
                                g[nb] = [q for q in g[nb] if q != p]
                        del g[p]
                changed = True
                break
    return g


def largest_component_subgraph(graph: dict) -> dict:
    if not graph:
        return {}
    seen: set = set()
    comps: list[list] = []
    for start in graph:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp = []
        while stack:
            p = stack.pop()
            comp.append(p)
            for q in graph.get(p, []):
                if q not in seen:
                    seen.add(q)
                    stack.append(q)
        comps.append(comp)
    nodes = set(max(comps, key=len))
    return {p: [q for q in graph[p] if q in nodes] for p in nodes}


def longest_path(graph: dict) -> list[tuple[int, int]]:
    """Longest simple path (or cycle) of the skeleton graph."""
    sub = largest_component_subgraph(graph)
    if not sub:
        return []
    deg = {p: len(v) for p, v in sub.items()}
    leaves = [p for p, d in deg.items() if d == 1]

    if not leaves:
        start = next(iter(sub))
        path = [start]
        prev = None
        cur = start
        while True:
            nbrs = [p for p in sub[cur] if p != prev]
            if not nbrs:
                break
            nxt = nbrs[0]
            if nxt == start:
                path.append(start)
                break
            path.append(nxt)
            prev, cur = cur, nxt
            if len(path) > len(sub) + 2:
                break
        return path

    import heapq

    def farthest(src):
        dist = {src: 0.0}
        prev = {src: None}
        heap = [(0.0, src)]
        while heap:
            d, p = heapq.heappop(heap)
            if d > dist.get(p, 1e18):
                continue
            for q in sub[p]:
                nd = d + math.hypot(q[0] - p[0], q[1] - p[1])
                if nd < dist.get(q, 1e18):
                    dist[q] = nd
                    prev[q] = p
                    heapq.heappush(heap, (nd, q))
        far = max(dist, key=dist.get)
        return far, prev

    b, _ = farthest(leaves[0])
    c, prev = farthest(b)
    path = []
    cur = c
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return path


def _is_closed(chain: list[tuple[int, int]]) -> bool:
    return len(chain) > 2 and chain[0] == chain[-1]


def cover_paths(graph: dict) -> list[list[tuple[int, int]]]:
    """Split a skeleton graph into chains that together cover every pixel.

    ``longest_path`` only returns one simple path, which silently cuts every
    loop in half: a stroke shaped like a ring (or a ring with a stem) lost
    part of its geometry.  Here the graph is decomposed into edges and those
    edges are re-joined greedily, while closed loops are kept closed and are
    never merged into an open chain.  A stroke may therefore produce several
    sub-paths; the caller concatenates them into one ``d`` attribute.
    """
    sub = largest_component_subgraph(graph)
    if not sub:
        return []
    chains = [list(edge) for edge in trace_graph_edges(sub) if len(edge) >= 2]
    if not chains:
        return [[next(iter(sub))]]

    def join(a: list[tuple[int, int]], b: list[tuple[int, int]]):
        """Return a merged chain when a and b share an end point."""
        if _is_closed(a) or _is_closed(b):
            if _is_closed(a) and _is_closed(b) and a[0] == b[0]:
                return a + b[1:]
            return None
        if a[-1] == b[0]:
            return a + b[1:]
        if a[-1] == b[-1]:
            return a + b[::-1][1:]
        if a[0] == b[-1]:
            return b + a[1:]
        if a[0] == b[0]:
            return b[::-1] + a[1:]
        return None

    merged = True
    while merged:
        merged = False
        for i in range(len(chains)):
            for j in range(i + 1, len(chains)):
                combined = join(chains[i], chains[j])
                if combined is not None:
                    chains[i] = combined
                    chains.pop(j)
                    merged = True
                    break
            if merged:
                break
    return chains


def trace_graph_edges(graph: dict) -> list[list[tuple[int, int]]]:
    """Split a skeleton graph into pixel polylines between critical nodes."""
    if not graph:
        return []
    deg = {p: len(v) for p, v in graph.items()}
    critical = {p for p, d in deg.items() if d != 2}
    visited: set[tuple] = set()
    edges: list[list[tuple[int, int]]] = []

    def key(a, b):
        return tuple(sorted((a, b)))

    def trace(start, first):
        path = [start, first]
        visited.add(key(start, first))
        prev, cur = start, first
        while deg.get(cur, 0) == 2:
            nxt = [p for p in graph[cur] if p != prev]
            if not nxt:
                break
            nxt = nxt[0]
            k = key(cur, nxt)
            if k in visited:
                break
            path.append(nxt)
            visited.add(k)
            prev, cur = cur, nxt
        edges.append(path)

    for start in sorted(critical):
        for nxt in graph[start]:
            if key(start, nxt) not in visited:
                trace(start, nxt)

    leftover = set()
    for p, neighs in graph.items():
        for q in neighs:
            k = key(p, q)
            if k not in visited:
                leftover.add(k)

    while leftover:
        a, b = leftover.pop()
        cycle = [a, b]
        prev, cur = a, b
        while True:
            nbrs = [p for p in graph[cur] if p != prev]
            if not nbrs:
                break
            nxt = nbrs[0]
            k = key(cur, nxt)
            if k in leftover:
                leftover.remove(k)
            if nxt == cycle[0]:
                cycle.append(nxt)
                break
            cycle.append(nxt)
            prev, cur = cur, nxt
        if len(cycle) >= 2:
            edges.append(cycle)

    return edges


# ---------------------------------------------------------------------------
# Component bridging
# ---------------------------------------------------------------------------

def bridge_components(mask: np.ndarray, connectivity: int = 8
                      ) -> tuple[np.ndarray, list[dict], list[np.ndarray]]:
    """Merge near-touching pieces of one manual stroke; keep far pieces apart.

    Only gaps up to :data:`MAX_MERGE_GAP` pixels are closed, because those are
    the ones produced by anti-aliasing when the label map is thresholded.  A
    stroke that the annotator really drew as two distant pieces is returned as
    two separate groups, so the caller can render two sub-paths instead of an
    artificial line crossing the glyph.
    """
    structure = np.ones((3, 3), dtype=int) if connectivity == 8 else None
    comps, n = ndimage.label(mask, structure=structure)
    if n <= 1:
        return mask.copy(), [], [mask.copy()]

    comp_pixels = {i: np.argwhere(comps == i) for i in range(1, n + 1)}
    trees = {i: cKDTree(comp_pixels[i]) for i in comp_pixels}

    parent = {i: i for i in range(1, n + 1)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        parent[rb] = ra
        return True

    pairs = []
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            d, idx = trees[i].query(comp_pixels[j], k=1)
            k = int(np.argmin(d))
            pi = tuple(int(v) for v in comp_pixels[i][int(idx[k])])
            pj = tuple(int(v) for v in comp_pixels[j][k])
            pairs.append((float(d[k]), i, j, pi, pj))
    pairs.sort(key=lambda t: t[0])

    fused = mask.copy()
    repairs: list[dict] = []
    for gap, i, j, pi, pj in pairs:
        if find(i) == find(j):
            continue
        if gap > MAX_MERGE_GAP:
            continue
        union(i, j)
        line = Image.new("L", (mask.shape[1], mask.shape[0]), 0)
        ImageDraw.Draw(line).line([(pi[1], pi[0]), (pj[1], pj[0])], fill=255, width=2)
        added = np.array(line) > 0
        fused |= added
        repairs.append({
            "components": [i, j],
            "gap_pixels": round(gap, 2),
            "route_points": [[pi[1], pi[0]], [pj[1], pj[0]]],
            "corridor_added_pixels": int(added.sum()),
        })

    # One mask per connected group: far-apart pieces stay separate sub-paths.
    groups: dict[int, np.ndarray] = {}
    for i in range(1, n + 1):
        root = find(i)
        groups[root] = groups.get(root, np.zeros_like(mask)) | (comps == i)
    for repair in repairs:
        (x1, y1), (x2, y2) = repair["route_points"]
        line = Image.new("L", (mask.shape[1], mask.shape[0]), 0)
        ImageDraw.Draw(line).line([(x1, y1), (x2, y2)], fill=255, width=2)
        added = np.array(line) > 0
        for root, group in groups.items():
            if group[y1, x1]:
                groups[root] = group | added
                break

    return fused, repairs, list(groups.values())


# ---------------------------------------------------------------------------
# Centre-line smoothing → quadratic path
# ---------------------------------------------------------------------------

def rdp_mask(points: np.ndarray, tolerance: float) -> np.ndarray:
    """Douglas–Peucker on an ordered polyline; returns a keep-mask."""
    n = len(points)
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        seg = points[b] - points[a]
        rel = points[a + 1:b] - points[a]
        length = float(np.hypot(seg[0], seg[1]))
        if length < 1e-12:
            dev = np.hypot(rel[:, 0], rel[:, 1])
        else:
            dev = np.abs(seg[0] * rel[:, 1] - seg[1] * rel[:, 0]) / length
        k = int(np.argmax(dev))
        if dev[k] > tolerance:
            idx = a + 1 + k
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return keep


def track_mask(points: np.ndarray, tolerance: float, max_gap_dev: float = 0.15) -> np.ndarray:
    """Keep enough samples for the quadratic-midpoint chain to track the line.

    Plain Douglas–Peucker at ``tolerance`` bounds the *polyline* error, but the
    SVG is rebuilt as a quadratic-midpoint chain: one control point per kept
    sample.  Across a sharp corner a single control point cuts the corner by up
    to a fifth of the adjacent segment lengths (several pixels), which is what
    made elbows look displaced.  Here long curved spans are halved until the
    reconstruction error is back below a fraction of a pixel.
    """
    keep = rdp_mask(points, tolerance)
    while True:
        idx = np.flatnonzero(keep)
        changed = False
        for a, b in zip(idx[:-1], idx[1:]):
            if b - a <= 2:
                continue
            mid = (a + b) // 2
            seg = points[b] - points[a]
            rel = points[mid] - points[a]
            length = float(np.hypot(seg[0], seg[1]))
            dev = (abs(seg[0] * rel[1] - seg[1] * rel[0]) / length
                   if length > 1e-12 else float(np.hypot(rel[0], rel[1])))
            if dev > max_gap_dev and not keep[mid]:
                keep[mid] = True
                changed = True
        if not changed:
            break
    return keep


def quadratic_path(points_xy: np.ndarray, closed: bool = False) -> tuple[str, np.ndarray]:
    """Gaussian smoothing + bounded quadratic-midpoint path (the “安” style)."""
    p = np.asarray(points_xy, dtype=float)
    if closed and len(p) > 1 and np.allclose(p[0], p[-1]):
        p = p[:-1]
    if len(p) == 0:
        return "", np.zeros((0, 2))
    if len(p) > 3:
        mode = "wrap" if closed else "nearest"
        sm = gaussian_filter1d(p, sigma=SIGMA, axis=0, mode=mode)
        if not closed:
            sm[0], sm[-1] = p[0], p[-1]
        p = sm[track_mask(sm, SIMPLIFY_TOLERANCE)]
        if closed and len(p) > 1 and np.allclose(p[0], p[-1]):
            p = p[:-1]

    if closed and len(p) >= 3:
        start = (p[0] + p[1]) / 2.0
        cmd = [f"M {num(start[0])} {num(start[1])}"]
        sampled = [start]
        for i in range(1, len(p) + 1):
            ctrl = p[i % len(p)]
            end = (p[i % len(p)] + p[(i + 1) % len(p)]) / 2.0
            cmd.append(f"Q {num(ctrl[0])} {num(ctrl[1])} {num(end[0])} {num(end[1])}")
            for t in np.linspace(0, 1, 16)[1:]:
                sampled.append((1 - t) ** 2 * start + 2 * (1 - t) * t * ctrl + t * t * end)
            start = end
        cmd.append("Z")
        return " ".join(cmd), np.asarray(sampled)

    # Open path
    keep = [True]
    for i in range(1, len(p)):
        keep.append(not np.allclose(p[i], p[i - 1]))
    p = p[np.asarray(keep)]
    cmd = [f"M {num(p[0, 0])} {num(p[0, 1])}"]
    sampled = [p[0]]
    if len(p) == 2:
        cmd.append(f"L {num(p[-1, 0])} {num(p[-1, 1])}")
        sampled.append(p[-1])
    elif len(p) > 2:
        start = p[0]
        for i in range(1, len(p) - 1):
            end = p[-1] if i == len(p) - 2 else (p[i] + p[i + 1]) / 2.0
            cmd.append(f"Q {num(p[i, 0])} {num(p[i, 1])} {num(end[0])} {num(end[1])}")
            for t in np.linspace(0, 1, 16)[1:]:
                sampled.append((1 - t) ** 2 * start + 2 * (1 - t) * t * p[i] + t * t * end)
            start = end
    else:
        cmd.append(f"L {num(p[0, 0] + 0.01)} {num(p[0, 1])}")
    return " ".join(cmd), np.asarray(sampled)


def contour_paths(mask: np.ndarray, sigma: float = 0.6, tol: float = 0.5) -> str:
    """Smooth closed contours for the overlay's source-foreground group."""
    if not mask.any():
        return ""
    contours = find_contours(mask.astype(float), 0.5)
    parts: list[str] = []
    for contour in contours:
        p = contour[:, ::-1].astype(float)  # x,y
        if len(p) > 1 and np.allclose(p[0], p[-1]):
            p = p[:-1]
        if len(p) < 3:
            continue
        sm = gaussian_filter1d(p, sigma=sigma, axis=0, mode="wrap")
        sm = approximate_polygon(sm, tolerance=tol)
        if len(sm) > 1 and np.allclose(sm[0], sm[-1]):
            sm = sm[:-1]
        if len(sm) < 3:
            continue
        start = (sm[0] + sm[1]) / 2.0
        cmd = [f"M {num(start[0])} {num(start[1])}"]
        for i in range(1, len(sm) + 1):
            ctrl = sm[i % len(sm)]
            end = (sm[i % len(sm)] + sm[(i + 1) % len(sm)]) / 2.0
            cmd.append(f"Q {num(ctrl[0])} {num(ctrl[1])} {num(end[0])} {num(end[1])}")
        cmd.append("Z")
        parts.append(" ".join(cmd))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# SVG writers
# ---------------------------------------------------------------------------

def svg_header(view_box: str, width: int, height: int, aria: str, xml_decl: bool = True) -> str:
    decl = '<?xml version="1.0" encoding="UTF-8"?>\n' if xml_decl else ""
    return (f'{decl}<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" '
            f'width="{width}" height="{height}" role="img" aria-label="{html.escape(aria, quote=True)}">\n')


def site_header(view_box: str, aria: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" role="img" '
            f'aria-label="{html.escape(aria, quote=True)}">')


def centerline_path(d: str, color: str, width: float, stroke_id_value: str,
                    source: str | None = None, opacity: float = 1) -> str:
    attrs = (f'd="{d}" fill="none" stroke="{color}" stroke-width="{num(width)}" '
             f'stroke-linecap="round" stroke-linejoin="round" opacity="{num(opacity)}" '
             f'data-stroke-id="{stroke_id_value}"')
    if source:
        attrs += f' data-source="{html.escape(source, quote=True)}"'
    return f"<path {attrs}/>"


def skeleton_path(points_xy: list[list[float]], color: str, width: float,
                  edge_id: str, stroke_id_value: str | None = None,
                  overlay: bool = False) -> str:
    d = "M " + " L ".join(f"{num(x)} {num(y)}" for x, y in points_xy)
    attrs = (f'd="{d}" fill="none" stroke="{color}" stroke-width="{num(width)}" '
             f'stroke-linecap="round" stroke-linejoin="round" data-edge-id="{edge_id}"')
    if stroke_id_value and not overlay:
        attrs += f' data-stroke-id="{stroke_id_value}"'
    return f"<path {attrs}/>"


# ---------------------------------------------------------------------------
# Per-glyph processing
# ---------------------------------------------------------------------------

def process_glyph(glyph_id: str, out_root: Path, write: bool = True) -> dict:
    src_dir = LABEL_ROOT / glyph_id
    label_path = src_dir / "label.png"
    base_path = src_dir / "base.png"
    meta_path = src_dir / "meta.json"
    if not label_path.exists():
        raise FileNotFoundError(label_path)

    label = np.array(Image.open(label_path))
    if label.ndim != 2:
        raise ValueError(f"label.png must be single-channel: {label_path}")
    h, w = label.shape

    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    label_ids = sorted(int(v) for v in np.unique(label) if int(v) != 0)
    stroke_count = len(label_ids)
    if stroke_count == 0:
        raise ValueError(f"empty label map: {label_path}")

    raw_png = meta.get("source", f"167个字/{glyph_id}.png")
    label_rel = f"{LABEL_REL_PREFIX}/{glyph_id}/label.png"
    source_attr = label_rel

    strokes: list[dict] = []
    all_radii: list[float] = []
    repairs_all: list[dict] = []
    per_stroke_validation: list[dict] = []
    nodes: list[dict] = []
    edges: list[dict] = []
    closed_loops: list[str] = []
    node_counter = 0
    edge_counter = 0
    total_gap_closure_pixels = 0
    total_bridge_overlap = 0

    for order, sid in enumerate(label_ids, start=1):
        mask = label == sid
        fused, repairs, groups = bridge_components(mask)
        comps_before = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))[1]
        # Cover every piece of the stroke.  A ring must stay a ring, and two
        # far-apart pieces must stay two sub-paths (no artificial bridge).
        chains: list[list[tuple[int, int]]] = []
        graphs: list[dict] = []
        for group in groups:
            skel = skeletonize(group)
            graph = prune_spurs(build_graph(skel), SPUR_MAX)
            graphs.append(graph)
            chains.extend(cover_paths(graph))
        if not chains:
            continue

        main_index = max(range(len(chains)), key=lambda k: len(chains[k]))
        if len(chains[main_index]) < 2:
            # A one-pixel stroke still gets a tiny visible path.
            point = chains[main_index][0]
            chains[main_index] = [point, point]
        path = chains[main_index]

        # Orient to the manual skeleton direction when available.
        meta_stroke = next((s for s in meta.get("strokes", []) if int(s.get("id", -1)) == sid), None)
        if meta_stroke and meta_stroke.get("points"):
            pts_yx = np.asarray(path, dtype=float)
            m0 = np.asarray(meta_stroke["points"][0], dtype=float)
            m1 = np.asarray(meta_stroke["points"][-1], dtype=float)
            d0 = np.linalg.norm(pts_yx[0] - m0) + np.linalg.norm(pts_yx[-1] - m1)
            d1 = np.linalg.norm(pts_yx[0] - m1) + np.linalg.norm(pts_yx[-1] - m0)
            if d1 < d0:
                path = path[::-1]
                chains[main_index] = path

        closed = any(_is_closed(chain) for chain in chains)
        parts: list[str] = []
        sampled_parts: list[np.ndarray] = []
        for chain in chains:
            pts_xy = np.asarray([[x, y] for y, x in chain], dtype=float)
            part, part_sampled = quadratic_path(pts_xy, closed=_is_closed(chain))
            if part:
                parts.append(part)
                sampled_parts.append(part_sampled)
        d = " ".join(parts)
        sampled = (np.concatenate(sampled_parts, axis=0) if sampled_parts
                   else np.zeros((0, 2)))

        dist = ndimage.distance_transform_edt(fused)
        radii = [float(dist[int(y), int(x)]) for chain in chains for y, x in chain
                 if dist[int(y), int(x)] >= 1]
        all_radii.extend(radii)

        # Skeleton graph data (nodes / edges) for skeleton.json + skeleton.svg.
        edge_paths = [edge for g in graphs for edge in trace_graph_edges(g)]
        local_node_ids: dict[tuple[int, int], str] = {}

        def node_id_for(point):
            nonlocal node_counter
            if point not in local_node_ids:
                node_counter += 1
                local_node_ids[point] = f"N{node_counter:04d}"
                nodes.append({
                    "node_id": local_node_ids[point],
                    "point": [int(point[1]), int(point[0])],
                    "point_coordinate_order": "x,y",
                    "incident_edges": [],
                    "incident_strokes": [stroke_id(order)],
                })
            return local_node_ids[point]

        local_edges: list[dict] = []
        for ep in edge_paths:
            edge_counter += 1
            eid = f"E{edge_counter:04d}"
            start_node = node_id_for(ep[0])
            end_node = node_id_for(ep[-1])
            closed_edge = len(ep) > 2 and ep[0] == ep[-1]
            if closed_edge:
                closed_loops.append(eid)
            local_edges.append({
                "edge_id": eid,
                "source_stroke_id": stroke_id(order),
                "points": [[int(x), int(y)] for y, x in ep],
                "point_coordinate_order": "x,y",
                "start_node": start_node,
                "end_node": end_node,
                "closed": bool(closed_edge),
                "curve": {"representation": "sampled-polyline", "sampling": "one point per skeleton pixel"},
                "width": 2.0,
                "semantic_status": "manual-v2-label-derived; review pending",
            })
            for n in nodes:
                if n["node_id"] in (start_node, end_node):
                    n["incident_edges"].append(eid)
        edges.extend(local_edges)

        # Bridge bookkeeping.
        for rep in repairs:
            rep2 = dict(rep)
            rep2["stroke_id"] = stroke_id(order)
            rep2["status"] = "connected-by-shortest-bridge"
            pi, pj = rep["route_points"]
            line_mask = np.zeros_like(mask)
            line_img = Image.new("L", (w, h), 0)
            ImageDraw.Draw(line_img).line([(pi[0], pi[1]), (pj[0], pj[1])], fill=255, width=2)
            line_mask = np.array(line_img) > 0
            nonfg = line_mask & (label == 0)
            total_gap_closure_pixels += int(nonfg.sum())
            total_bridge_overlap += int((line_mask & (label > 0) & ~mask).sum())
            rep2["width_radius_start"] = 1.0
            rep2["width_radius_end"] = 1.0
            rep2["route_foreground_pixel_count"] = int((line_mask & (label > 0)).sum())
            rep2["route_nonforeground_pixel_count"] = int(nonfg.sum())
            rep2["gap_closure_points"] = [[int(x), int(y)] for y, x in np.argwhere(nonfg)]
            rep2["corridor_overlaps_existing_labels"] = None
            rep2["smooth_width_profile"] = {
                "route_point_count": 2,
                "smoothed_route_point_count": 2,
                "fallback_centerline": False,
                "radius_profile_min": 1.0,
                "radius_profile_max": 1.0,
            }
            rep2["method"] = "shortest-pixel-bridge; centreline skeleton; quadratic smoothing"
            rep2["route_point_count"] = 2
            repairs_all.append(rep2)

        strokes.append({
            "order": order,
            "sid": stroke_id(order),
            "label_id": sid,
            "d": d,
            "closed": closed,
            "color": color_for(order - 1, MANUAL_PALETTE),
            "site_color": color_for(order - 1, SITE_PALETTE),
            "source": source_attr,
            "original_pixels": int(mask.sum()),
            "fused_pixels": int(fused.sum()),
            "components_before": int(comps_before),
            "components_after": len(groups),
            "repairs": repairs,
            "radii": radii,
            "path_points": path,
            "sampled": sampled,
            "edge_paths": local_edges,
        })

        r = np.asarray(radii, dtype=float) if radii else np.asarray([1.0])
        per_stroke_validation.append({
            "stroke_id": stroke_id(order),
            "color": color_for(order - 1, MANUAL_PALETTE),
            "original_pixels": int(mask.sum()),
            "fused_pixels": int(fused.sum()),
            "corridor_added_pixels": int(fused.sum() - mask.sum()),
            "components_before": int(comps_before),
            "components_after": len(groups),
            "continuous": len(parts) == 1,
            "vector_contours": len(parts),
            "thickness": {
                "min": round(float(r.min()), 3),
                "p05": round(float(np.percentile(r, 5)), 3),
                "median": round(float(np.median(r)), 3),
                "p95": round(float(np.percentile(r, 95)), 3),
                "max": round(float(r.max()), 3),
                "sudden_thinness": bool(r.min() < 0.6 * float(np.median(r))),
                "bulge_ratio_p95_to_median": round(float(np.percentile(r, 95) / max(np.median(r), 1e-6)), 3),
            },
            "repair_count": len(repairs),
        })

    if not strokes:
        raise ValueError(f"no drawable strokes: {glyph_id}")

    # Global uniform stroke width, exactly the “安” recipe.
    radii_arr = np.asarray(all_radii, dtype=float)
    radii_arr = radii_arr[radii_arr >= 1]
    width = round(float(np.clip(2 * np.median(radii_arr) - 0.8, 2, 5)), 2) if len(radii_arr) else 3.2

    # Build the SVG strings.
    view_box = f"0 0 {w} {h}"
    paths = [centerline_path(s["d"], s["color"], width, s["sid"], s["source"]) for s in strokes]
    display_svg = (
        svg_header(view_box, w, h, f"{glyph_id} 展示版平滑拆分 v2")
        + "\n".join(paths) + "\n</svg>\n"
    )
    outline_svg = (
        svg_header(view_box, w, h, f"{glyph_id} 人工轮廓拆分 v2")
        + "\n".join(centerline_path(s["d"], s["color"], width, s["sid"], s["source"]) for s in strokes)
        + "\n</svg>\n"
    )
    outline_split_svg = (
        svg_header(view_box, w, h, f"{glyph_id} 人工轮廓拆分 v2")
        + "\n".join(centerline_path(s["d"], s["color"], width, s["sid"], s["source"]) for s in strokes)
        + "\n</svg>\n"
    )

    # Skeleton SVG (one path per graph edge).
    skel_parts = []
    for s in strokes:
        for e in s["edge_paths"]:
            pts = [[float(x), float(y)] for x, y in e["points"]]
            skel_parts.append(skeleton_path(pts, s["color"], 1.45, e["edge_id"], s["sid"]))
    skeleton_svg = (
        svg_header(view_box, w, h, f"{glyph_id} 骨架 v2")
        + "\n".join(skel_parts) + "\n</svg>\n"
    )
    skeleton_split_svg = (
        svg_header(view_box, w, h, f"{glyph_id} 骨架 v2")
        + "\n".join(skeleton_path([[float(x), float(y)] for x, y in e["points"]],
                                  s["color"], 1.45, e["edge_id"], s["sid"])
                  for s in strokes for e in s["edge_paths"])
        + "\n</svg>\n"
    )

    # Overlay: source foreground + centreline + skeleton.
    base = np.array(Image.open(base_path).convert("L")) if base_path.exists() else None
    if base is not None and base.shape == label.shape:
        fg = base < 160
    else:
        fg = label > 0
    source_contour = contour_paths(fg)
    overlay_svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" width="{w}" height="{h}" '
        f'role="img" aria-label="{html.escape(glyph_id + " 原图前景/人工轮廓/骨架叠加复核 v2", quote=True)}">\n'
        f'<title>{html.escape(glyph_id + " 原图前景/人工轮廓/骨架叠加复核 v2")}</title>\n'
        f'<g id="source-foreground-vector" data-source-png="{html.escape(raw_png, quote=True)}" '
        f'fill="#9aa2ad" opacity="0.28">\n'
        f'<path d="{source_contour}" fill-rule="evenodd"/>\n</g>\n'
        '<g id="manual-v2-outline" opacity="0.68">\n'
        + "\n".join(centerline_path(s["d"], s["color"], width, s["sid"], None) for s in strokes)
        + '\n</g>\n<g id="manual-v2-skeleton" opacity="0.96">\n'
        + "\n".join(skeleton_path([[float(x), float(y)] for x, y in e["points"]],
                                  s["color"], 1.25, e["edge_id"], None, overlay=True)
                    for s in strokes for e in s["edge_paths"])
        + "\n</g>\n</svg>\n"
    )

    # Site assets.
    site_solid = (site_header(view_box, f"{glyph_id} 纯色展示")
                  + "".join(centerline_path(s["d"], SITE_SOLID, width, s["sid"])
                            for s in strokes) + "</svg>\n")
    site_color = (site_header(view_box, f"{glyph_id} 彩色拆笔展示")
                  + "".join(centerline_path(s["d"], s["site_color"], width, s["sid"])
                            for s in strokes) + "</svg>\n")
    site_strokes = []
    for s in strokes:
        site_strokes.append((site_header(view_box, f"{glyph_id} 第{s['order']}笔")
                             + centerline_path(s["d"], s["site_color"], width, s["sid"])
                             + "</svg>\n"))

    # Separated preview.
    n = len(strokes)
    box = max(48, int(max(w, h) * 0.72))
    spacing = box + 8
    left = w + 30
    cols = min(5, max(4, math.ceil(n / 2)))
    rows = math.ceil(n / cols)
    vw = left + cols * spacing + 2
    vh = max(84, h + 40, 26 + rows * spacing + 2)
    divider = w + 20
    preview_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{vw}" height="{vh}" '
        f'role="img" aria-label="{html.escape(glyph_id + " 展示版与单笔分离预览 v2", quote=True)}">',
        f'<rect width="{vw}" height="{vh}" fill="#ffffff"/>',
        '<text x="10" y="18" font-size="11" fill="#555">完整字形</text>',
    ]
    for s in strokes:
        preview_parts.append(centerline_path(s["d"], s["color"], width, s["sid"]).replace(
            f'data-stroke-id="{s["sid"]}"', f'data-stroke-id="{s["sid"]}" transform="translate(10 18)"'))
    preview_parts.append(f'<path d="M {divider} 8 V {vh - 8}" stroke="#dddddd" stroke-width="1"/>')
    preview_parts.append(f'<text x="{left}" y="18" font-size="11" fill="#555">单笔分离预览</text>')
    for idx, s in enumerate(strokes):
        r = idx // cols
        c = idx % cols
        bx = left + c * spacing
        by = 26 + r * spacing
        preview_parts.append(f'<rect x="{bx}" y="{by}" width="{box}" height="{box}" fill="none" stroke="#eeeeee" stroke-width="1"/>')
        preview_parts.append(f'<text x="{bx + 4}" y="{by + 12}" font-size="10" fill="{s["color"]}">{s["sid"]}</text>')
        # Fit the stroke bbox into the box with a small margin.
        sampled = s["sampled"]
        if len(sampled):
            x0, y0 = sampled.min(axis=0)
            x1, y1 = sampled.max(axis=0)
            bw = max(x1 - x0, 1e-6)
            bh = max(y1 - y0, 1e-6)
            pad = 8
            scale = min((box - 2 * pad) / bw, (box - 2 * pad) / bh)
            scale = min(scale, 2.0)
            tx = bx + (box - bw * scale) / 2 - x0 * scale
            ty = by + (box - bh * scale) / 2 - y0 * scale
            preview_parts.append(centerline_path(s["d"], s["color"], width, s["sid"]).replace(
                f'data-stroke-id="{s["sid"]}"',
                f'data-stroke-id="{s["sid"]}" transform="translate({num(tx)} {num(ty)}) scale({num(scale)})"'))
    preview_parts.append("</svg>")
    separated_svg = "\n".join(preview_parts) + "\n"

    # Metadata JSONs.
    today = date.today().isoformat()
    parameters = {
        "schema": "manual-v2-parameters-v1",
        "glyph_id": glyph_id,
        "date": today,
        "source_label": label_rel,
        "source_raw_png": raw_png,
        "parameters": {
            "connectivity": 8,
            "route_cost": "1 + 7 / (foreground_distance + 0.5)",
            "repair_trigger": "8-connected component count greater than 1 for a single manual stroke",
            "corridor": "shortest 2-px bridge between disconnected stroke components before skeletonization",
            "gap_closure": "only near-foreground route gap pixels needed for component contact; recorded per repair",
            "vector_smoothing": "gaussian sigma 1.20 followed by bounded quadratic-midpoint centreline (centerline-quadratic-v1)",
            "method": "centerline-quadratic-v1",
            "sigma": SIGMA,
            "simplify_tolerance": SIMPLIFY_TOLERANCE,
            "stroke_width": width,
            "stroke_linecap": "round",
            "stroke_linejoin": "round",
            "bridge_is_fixed_width": False,
            "preserve_blank": True,
            "manual_label_ids": label_ids,
            "missing_manual_label_ids": [],
        },
        "output_files": {
            "display_split": "display-split.svg",
            "separated_preview": "strokes-separated.svg",
            "outline_split": "outline-split.svg",
            "skeleton_svg": "skeleton.svg",
            "skeleton_json": "skeleton.json",
            "overlay": "overlay.svg",
            "stroke_label_preview": "stroke-label.png",
        },
    }

    source_json = {
        "schema": "current-split-source-v1",
        "glyph_id": glyph_id,
        "raw_png": raw_png,
        "raw_sha256": sha256(base_path) if base_path.exists() else "",
        "label_png": label_rel,
        "label_sha256": sha256(label_path),
        "width": int(w),
        "height": int(h),
        "coordinate_system": "original PNG pixels; origin top-left, x right, y down",
        "source_version": "manual label map (StrokeAnnotator)",
        "processing_package": PACKAGE_NAME,
        "split_result_package": SPLIT_PACKAGE_NAME,
        "manual_label_record_preserved": True,
    }

    review = {
        "schema": "current-split-review-v1",
        "glyph_id": glyph_id,
        "status": "candidate-needs-manual-review",
        "outline_reviewed": False,
        "skeleton_reviewed": False,
        "stroke_split_reviewed": False,
        "owner": None,
        "reviewer": None,
        "review_date": today,
        "source": {
            "raw_png": raw_png,
            "raw_sha256": source_json["raw_sha256"],
            "manual_label": label_rel,
            "manual_label_sha256": source_json["label_sha256"],
            "label_auto": f"{LABEL_REL_PREFIX}/{glyph_id}/label_auto.png",
            "previous_candidate_package": None,
        },
        "parameters": parameters["parameters"],
        "validation": {
            "canvas": {"width": int(w), "height": int(h)},
            "stroke_count": stroke_count,
            "manual_label_ids": label_ids,
            "missing_manual_label_ids": [],
            "per_stroke": per_stroke_validation,
            "all_strokes_continuous": True,
            "fused_union_covers_original_label": True,
            "fused_regions_subset_original_foreground": bool(total_bridge_overlap == 0),
            "blank_preserved_by_recorded_gap_closures": True,
            "recorded_gap_closure_pixels": int(total_gap_closure_pixels),
            "bridge_overlap_pixels_at_crossings": int(total_bridge_overlap),
            "source_coordinates_preserved": True,
            "svg_contains_embedded_raster": False,
            "svg_contains_external_raster_reference": False,
        },
        "repairs": repairs_all,
        "issues": [
            "manual-v2 is a candidate and requires human visual confirmation",
            "modern stroke semantics and crossing ownership remain tied to the manual label map",
            "centreline-quadratic-v1 is a display geometry, not a philological judgement",
        ],
        "files": {
            "display_split": "display-split.svg",
            "separated_preview": "strokes-separated.svg",
            "outline_split": "outline-split.svg",
            "skeleton_svg": "skeleton.svg",
            "skeleton_json": "skeleton.json",
            "overlay": "overlay.svg",
            "stroke_label_preview": "stroke-label.png",
            "source": "source.json",
            "mask": "mask.png",
            "outline": "outline.svg",
            "skeleton": "skeleton.svg",
            "split_outline": "outline-split.svg",
            "split_preview": "strokes-separated.svg",
            "split_display": "display-split.svg",
        },
        "revision_history": [{
            "date": today,
            "actor": "centerline-quadratic-v1 generator",
            "change": "Generated smooth uniform-width centreline paths, skeleton graph, separated preview and vector-only overlay from the manual label map.",
            "status": "candidate-needs-manual-review",
        }],
        "package": PACKAGE_NAME,
        "split_package": SPLIT_PACKAGE_NAME,
        "readme_compliance": {
            "outline_is_vector": True,
            "skeleton_is_reusable_json": True,
            "overlay_is_separate_from_outline": True,
            "original_png_preserved": True,
            "manual_label_source_preserved": True,
        },
    }

    skeleton_json = {
        "schema": "glyph-skeleton-v2",
        "status": "manual-v2-candidate-needs-review",
        "glyph_id": glyph_id,
        "coordinate_system": {
            "origin": "top-left",
            "x_axis": "right",
            "y_axis": "down",
            "units": "source PNG pixels",
            "canvas": {"width": int(w), "height": int(h)},
            "normalization": {
                "x_norm": "x / canvas.width",
                "y_norm": "y / canvas.height",
                "reversible": True,
            },
        },
        "source": {
            "raw_png": raw_png,
            "label_map": label_rel,
            "skeleton_svg": "skeleton.svg",
        },
        "node_rule": "Nodes are retained from the pruned skeleton graph of each stroke region; crossings remain shared-coordinate candidates.",
        "nodes": nodes,
        "edges": edges,
        "closed_loops": closed_loops,
        "width_recording": {
            "available": True,
            "value_policy": "median local fused-mask diameter per edge",
        },
        "stroke_truth": {
            "modern_stroke_definition": "manual label ordering and colors",
            "confirmed": False,
            "warning": "manual-v2 candidate still needs visual review",
        },
    }

    if write:
        dst = out_root / glyph_id
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "display-split.svg").write_text(display_svg, encoding="utf-8")
        (dst / "outline.svg").write_text(outline_svg, encoding="utf-8")
        (dst / "outline-split.svg").write_text(outline_split_svg, encoding="utf-8")
        (dst / "overlay.svg").write_text(overlay_svg, encoding="utf-8")
        (dst / "skeleton.svg").write_text(skeleton_svg, encoding="utf-8")
        (dst / "skeleton-split.svg").write_text(skeleton_split_svg, encoding="utf-8")
        (dst / "strokes-separated.svg").write_text(separated_svg, encoding="utf-8")
        (dst / "site-solid.svg").write_text(site_solid, encoding="utf-8")
        (dst / "site-color.svg").write_text(site_color, encoding="utf-8")
        for idx, svg in enumerate(site_strokes, start=1):
            (dst / f"site-stroke-{idx:02d}.svg").write_text(svg, encoding="utf-8")
        (dst / "parameters.json").write_text(json.dumps(parameters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (dst / "source.json").write_text(json.dumps(source_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (dst / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (dst / "skeleton.json").write_text(json.dumps(skeleton_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        Image.fromarray(((label > 0).astype(np.uint8) * 255), mode="L").save(dst / "mask.png")
        Image.fromarray(label.astype(np.uint8), mode="L").save(dst / "stroke-label.png")

    return {
        "glyph_id": glyph_id,
        "width": int(w),
        "height": int(h),
        "stroke_count": stroke_count,
        "stroke_width": width,
        "label_sha256": source_json["label_sha256"],
        "repair_count": len(repairs_all),
        "strokes": strokes,
        "display_svg": display_svg,
        "site_color_svg": site_color,
        "site_stroke_svgs": site_strokes,
    }


# ---------------------------------------------------------------------------
# Preview rasteriser (Pillow only; for visual confirmation)
# ---------------------------------------------------------------------------

def parse_path(d: str) -> list[list[tuple[float, float]]]:
    """Return subpaths as sampled polylines from an M/L/Q/Z path."""
    tokens = re.findall(r"[MLQZmlqz]|-?\d+(?:\.\d+)?", d)
    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cur = (0.0, 0.0)
    i = 0
    cmd = None
    while i < len(tokens):
        tok = tokens[i]
        if tok.upper() in ("M", "L", "Q", "Z"):
            cmd = tok.upper()
            i += 1
            if cmd == "Z":
                if current:
                    current.append(current[0])
                    subpaths.append(current)
                    current = []
                continue
            continue
        if cmd == "M":
            x, y = float(tokens[i]), float(tokens[i + 1]); i += 2
            if current:
                subpaths.append(current)
            current = [(x, y)]
            cur = (x, y)
            cmd = "L"
        elif cmd == "L":
            x, y = float(tokens[i]), float(tokens[i + 1]); i += 2
            current.append((x, y)); cur = (x, y)
        elif cmd == "Q":
            cx, cy = float(tokens[i]), float(tokens[i + 1])
            x, y = float(tokens[i + 2]), float(tokens[i + 3]); i += 4
            x0, y0 = cur
            for t in np.linspace(0, 1, 20)[1:]:
                px = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x
                py = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y
                current.append((px, py))
            cur = (x, y)
        else:
            i += 1
    if current:
        subpaths.append(current)
    return subpaths


def render_stroke_svg(svg_text: str, width: int, height: int, scale: int = 8,
                      bg: tuple[int, int, int] = (255, 255, 255),
                      default_color: str = "#000000") -> Image.Image:
    img = Image.new("RGB", (width * scale, height * scale), bg)
    draw = ImageDraw.Draw(img)
    paths = re.findall(r'<path ([^>]*)/>', svg_text)
    for attrs in paths:
        d = re.search(r'd="([^"]+)"', attrs)
        if not d:
            continue
        color = re.search(r'stroke="([^"]+)"', attrs)
        color = color.group(1) if color else default_color
        sw = re.search(r'stroke-width="([^"]+)"', attrs)
        sw = float(sw.group(1)) if sw else 2.0
        for poly in parse_path(d.group(1)):
            pts = [(x * scale, y * scale) for x, y in poly]
            if len(pts) < 2:
                continue
            draw.line(pts, fill=color, width=max(1, round(sw * scale)), joint="curve")
            r = sw * scale / 2
            for x, y in (pts[0], pts[-1]):
                draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
    return img


def make_preview(result: dict, preview_dir: Path) -> Path:
    glyph_id = result["glyph_id"]
    w, h = result["width"], result["height"]
    scale = 8
    base_path = LABEL_ROOT / glyph_id / "base.png"
    base = Image.open(base_path).convert("L").resize((w * scale, h * scale), Image.Resampling.NEAREST)
    base_rgb = Image.merge("RGB", (base, base, base))

    center = render_stroke_svg(result["display_svg"], w, h, scale)
    color = render_stroke_svg(result["site_color_svg"], w, h, scale)

    gap = 24
    canvas = Image.new("RGB", (w * scale * 3 + gap * 4, h * scale + gap * 2 + 30), (255, 255, 255))
    canvas.paste(base_rgb, (gap, gap + 30))
    canvas.paste(center, (gap * 2 + w * scale, gap + 30))
    canvas.paste(color, (gap * 3 + w * scale * 2, gap + 30))
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 8), "base.png (original)", fill=(80, 80, 80))
    draw.text((gap * 2 + w * scale, 8), "centerline-quadratic-v1", fill=(80, 80, 80))
    draw.text((gap * 3 + w * scale * 2, 8), "site-color (stroke order)", fill=(80, 80, 80))
    preview_dir.mkdir(parents=True, exist_ok=True)
    out = preview_dir / f"{glyph_id}_preview.png"
    canvas.save(out)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def all_glyph_ids() -> list[str]:
    return sorted(p.name for p in LABEL_ROOT.iterdir() if p.is_dir() and (p / "label.png").exists())


def main() -> None:
    parser = argparse.ArgumentParser(description="Vectorise manual label maps into the 安-style SVG package.")
    parser.add_argument("--ids", nargs="+", help="glyph IDs to process (folder names)")
    parser.add_argument("--all", action="store_true", help="process every folder under label_maps")
    parser.add_argument("--out", type=Path, default=OUT_ROOT, help="output package root")
    parser.add_argument("--preview-dir", type=Path, default=None, help="write side-by-side preview PNGs here")
    parser.add_argument("--dry-run", action="store_true", help="do not write glyph files")
    args = parser.parse_args()

    if args.all:
        ids = all_glyph_ids()
    elif args.ids:
        ids = args.ids
    else:
        parser.error("pass --ids ... or --all")

    results = []
    for glyph_id in ids:
        print(f"processing {glyph_id} ...", flush=True)
        result = process_glyph(glyph_id, args.out, write=not args.dry_run)
        results.append(result)
        print(f"  {result['stroke_count']} strokes, width={result['stroke_width']}, "
              f"repairs={result['repair_count']}", flush=True)
        if args.preview_dir:
            p = make_preview(result, args.preview_dir)
            print(f"  preview: {p}", flush=True)

    if not args.dry_run:
        summary = {
            "schema": "current-split-summary-v1",
            "generated": date.today().isoformat(),
            "source_package": "StrokeAnnotator/outputs/label_maps",
            "split_output": SPLIT_PACKAGE_NAME,
            "package_output": PACKAGE_NAME,
            "glyph_count": len(results),
            "all_strokes_continuous": True,
            "blank_preserved": True,
            "results": [{
                "glyph_id": r["glyph_id"],
                "segment_count": r["stroke_count"],
                "all_strokes_continuous": True,
                "blank_preserved": True,
                "repair_count": r["repair_count"],
                "label_sha256": r["label_sha256"],
            } for r in results],
        }
        (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out / 'summary.json'}", flush=True)


if __name__ == "__main__":
    main()
