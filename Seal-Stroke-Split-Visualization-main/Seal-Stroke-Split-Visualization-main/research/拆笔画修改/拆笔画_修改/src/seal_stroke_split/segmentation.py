from collections import Counter
import math

import numpy as np

from .config import SplitConfig
from .image_ops import connected_components
from .skeleton_graph import angle_delta_deg, build_graph, collapse_short_bridges, group_by_endpoint, point_angle, point_distance, trace_paths
from .types import Point, StrokeSegment
from .thinning import fix_cross_alignment


def _path_angles(path: list[Point], window: int) -> list[float]:
    angles: list[float] = []
    n = len(path)
    for i in range(n):
        left = path[max(0, i - window)]
        right = path[min(n - 1, i + window)]
        if left == right and i + 1 < n:
            right = path[i + 1]
        angles.append(point_angle(left, right))
    return angles

def split_path_by_angle(path: list[Point], config: SplitConfig) -> list[list[Point]]:
    if len(path) <= config.min_segment_points:
        return [path]
    angles = _path_angles(path, config.direction_window)
    split_indices = [0]
    last_split = 0
    for i in range(1, len(path) - 1):
        if i - last_split < config.min_segment_points:
            continue
        delta = angle_delta_deg(angles[i - 1], angles[i + 1])
        if delta >= config.split_angle_deg:
            split_indices.append(i)
            last_split = i
    split_indices.append(len(path) - 1)

    parts: list[list[Point]] = []
    for a, b in zip(split_indices[:-1], split_indices[1:]):
        segment = path[a:b + 1]
        if len(segment) >= 2:
            parts.append(segment)
    return parts or [path]



def _segment_endpoint_angle(segment: list[Point], at_start: bool, window: int) -> float:
    if len(segment) == 1:
        return 0.0
    if at_start:
        a = segment[0]
        b = segment[min(len(segment) - 1, window)]
    else:
        a = segment[-1]
        b = segment[max(0, len(segment) - 1 - window)]
    return point_angle(a, b)


def _combine_segments(
    seg_a: list[Point],
    seg_b: list[Point],
    a_at_start: bool,
    b_at_start: bool,
) -> list[Point]:
    if a_at_start:
        seg_a = list(reversed(seg_a))
    if not b_at_start:
        seg_b = list(reversed(seg_b))
    return seg_a + seg_b[1:]


def merge_segments_at_endpoints(segments: list[list[Point]], config: SplitConfig) -> list[list[Point]]:
    merged = [list(seg) for seg in segments]

    while True:
        endpoint_clusters = group_by_endpoint(merged, config.max_endpoint_gap)
        candidates = []

        for point, members in endpoint_clusters:
            active = [(idx, is_start) for idx, is_start in members if merged[idx]]
            if len(active) < 2:
                continue

            for i in range(len(active)):
                for j in range(i + 1, len(active)):
                    ia, ia_start = active[i]
                    ib, ib_start = active[j]
                    if ia == ib:
                        continue
                    seg_a = merged[ia]
                    seg_b = merged[ib]

                    a_at_start = ia_start
                    b_at_start = ib_start
                    ang_a = _segment_endpoint_angle(seg_a, a_at_start, config.direction_window)
                    ang_b = _segment_endpoint_angle(seg_b, b_at_start, config.direction_window)
                    delta = angle_delta_deg(ang_a, ang_b)

                    merge_type = None
                    score = None

                    if delta <= config.merge_angle_deg:
                        merge_type = 'same_direction'
                        score = delta + abs(len(seg_a) - len(seg_b)) * 0.01

                    # 短段强制合并:长度 ≤ N 且非空段,直接同向合并(用于清理细化残留毛刺)
                    short_len = min(len(seg_a), len(seg_b))
                    if short_len <= config.short_segment_force_merge and short_len > 0:
                        # 优先合并到长段:长段越长越好
                        force_score = -1000.0 - max(len(seg_a), len(seg_b))
                        if merge_type is None or force_score < score:
                            merge_type = 'force_short'
                            score = force_score

                    straightness = abs(delta - 180.0)
                    if len(active) >= 2 and straightness <= config.through_angle_deg:
                        through_score = straightness - min(len(seg_a), len(seg_b)) * 0.01
                        if merge_type is None or through_score < score:
                            merge_type = 'through_junction'
                            score = through_score

                    if merge_type is not None:
                        candidates.append({
                            'ia': ia,
                            'ib': ib,
                            'a_at_start': a_at_start,
                            'b_at_start': b_at_start,
                            'point': point,
                            'merge_type': merge_type,
                            'score': score,
                            'len_a': len(seg_a),
                            'len_b': len(seg_b),
                        })

        if not candidates:
            break

        candidates.sort(key=lambda x: x['score'])

        used_indices = set()
        selected_merges = []

        for cand in candidates:
            ia = cand['ia']
            ib = cand['ib']

            if ia in used_indices or ib in used_indices:
                continue

            if not merged[ia] or not merged[ib]:
                continue

            selected_merges.append(cand)
            used_indices.add(ia)
            used_indices.add(ib)

        for cand in selected_merges:
            ia = cand['ia']
            ib = cand['ib']
            a_at_start = cand['a_at_start']
            b_at_start = cand['b_at_start']

            merged[ia] = _combine_segments(merged[ia], merged[ib], a_at_start, b_at_start)
            merged[ib] = []

        if not selected_merges:
            break

    return [seg for seg in merged if len(seg) >= 2]


def absorb_tiny_segments(segments: list[list[Point]], config: SplitConfig) -> list[list[Point]]:
    merged = [list(seg) for seg in segments]
    changed = True
    while changed:
        changed = False
        clusters = group_by_endpoint(merged, config.max_endpoint_gap)
        for idx, seg in enumerate(merged):
            if not seg or len(seg) > config.tiny_segment_points:
                continue
            candidate = None
            best_score = None
            for rep, members in clusters:
                my_starts = [is_start for sidx, is_start in members if sidx == idx]
                if not my_starts:
                    continue
                neighbors = [(sidx, is_start) for sidx, is_start in members if sidx != idx and merged[sidx]]
                for tiny_at_start in my_starts:
                    tiny_angle = _segment_endpoint_angle(seg, tiny_at_start, config.direction_window)
                    for other_idx, other_at_start in neighbors:
                        other_seg = merged[other_idx]
                        other_angle = _segment_endpoint_angle(other_seg, other_at_start, config.direction_window)
                        delta = min(angle_delta_deg(tiny_angle, other_angle), abs(angle_delta_deg(tiny_angle, other_angle) - 180.0))
                        other_endpoint = other_seg[0] if other_at_start else other_seg[-1]
                        end_dist = point_distance(other_endpoint, seg[0] if tiny_at_start else seg[-1])
                        score = delta + len(seg) * 0.5 - len(other_seg) * 0.02
                        # 端点距离很近时,跳过角度要求,强制吸收(清理细化残留毛刺)
                        if end_dist <= config.tiny_merge_distance:
                            score -= 1000.0
                        if best_score is None or score < best_score:
                            best_score = score
                            candidate = (idx, other_idx, tiny_at_start, other_at_start)
            if candidate is None:
                continue
            tiny_idx, other_idx, tiny_at_start, other_at_start = candidate
            tiny_seg = merged[tiny_idx]
            other_seg = merged[other_idx]
            tiny_forward = tiny_seg if tiny_at_start else list(reversed(tiny_seg))
            if other_at_start:
                combined = tiny_forward + other_seg[1:]
            else:
                combined = other_seg + tiny_forward[1:]
            merged[other_idx] = combined
            merged[tiny_idx] = []
            changed = True
            break
    return [seg for seg in merged if len(seg) >= 2]


def segment_skeleton(skeleton: np.ndarray, config: SplitConfig) -> list[StrokeSegment]:
    aligned = fix_cross_alignment(skeleton)
    graph = build_graph(aligned)
    graph, _ = collapse_short_bridges(graph, config.bridge_collapse_len)
    base_paths = trace_paths(graph)

    split_paths: list[list[Point]] = []
    for path in base_paths:
        split_paths.extend(split_path_by_angle(path, config))

    merged = merge_segments_at_endpoints(split_paths, config)
    cleaned = absorb_tiny_segments(merged, config)
    attached = _fold_attach_pass(cleaned, config)
    

    return [StrokeSegment(stroke_id=i + 1, points=path) for i, path in enumerate(attached)]


def _fold_attach_pass(segments: list[list[Point]], config: SplitConfig) -> list[list[Point]]:
    """通用规则:折角接续合并
    某笔内部有 Δ≥45° 的拐角,且拐点下半段方向与下一笔全程方向同向(delta≤30°),
    且拐点与下一笔起点距离≤6,则:
      新笔 i = 笔 i 上半段 + 笔 (i+1)
      新笔 (i+1) = 笔 i 下半段
    仅在满足全部条件时触发,避免误伤含折角的常规笔画。
    """
    fold_deg = getattr(config, "fold_attach_angle_deg", 45.0)
    dir_tol = getattr(config, "fold_attach_dir_tol_deg", 30.0)
    gap_max = getattr(config, "fold_attach_gap_max", 6.0)
    W = 8

    def _fold_pos(pts: list[Point]) -> tuple[int, float] | None:
        if len(pts) < 2 * W + 2:
            return None
        best_delta = 0.0
        best_i = -1
        for i in range(W, len(pts) - W):
            a1 = point_angle(pts[i - W], pts[i])
            a2 = point_angle(pts[i], pts[i + W])
            dd = angle_delta_deg(a1, a2)
            if dd > best_delta:
                best_delta = dd
                best_i = i
        if best_delta >= fold_deg:
            return best_i, best_delta
        return None

    out: list[list[Point]] = []
    i = 0
    while i < len(segments):
        cur = segments[i]
        if i + 1 < len(segments):
            fold = _fold_pos(cur)
            if fold is not None:
                pos, _delta = fold
                nxt = segments[i + 1]
                d1 = point_angle(cur[pos], cur[-1])
                d2 = point_angle(nxt[0], nxt[-1])
                gap = point_distance(cur[pos], nxt[0])
                if angle_delta_deg(d1, d2) <= dir_tol and gap <= gap_max:
                    upper = cur[: pos + 1]
                    lower = cur[pos:]
                    new_cur = upper + nxt
                    new_next = lower
                    out.append(new_cur)
                    out.append(new_next)
                    i += 2
                    continue
        out.append(cur)
        i += 1
    return out


def node_degrees_from_segments(segments: list[list[Point]]) -> dict[Point, int]:
    from collections import Counter
    endpoints: Counter[Point] = Counter()
    for seg in segments:
        if len(seg) >= 2:
            endpoints[seg[0]] += 1
            endpoints[seg[-1]] += 1
    return dict(endpoints)


def _distance_maps(mask: np.ndarray, segments: list[StrokeSegment]) -> tuple[np.ndarray, np.ndarray]:
    fg_points = np.argwhere(mask)
    if len(fg_points) == 0:
        return np.zeros((0, 0)), fg_points
    distances = np.empty((len(segments), len(fg_points)), dtype=np.float32)
    for idx, seg in enumerate(segments):
        seg_points = np.array(seg.points, dtype=np.float32)
        diff = fg_points[:, None, :].astype(np.float32) - seg_points[None, :, :]
        sq_dist = np.sum(diff * diff, axis=2)
        distances[idx] = np.sqrt(np.min(sq_dist, axis=1))
    return distances, fg_points


def _reassign_tiny_regions(stroke_map: np.ndarray, mask: np.ndarray, config: SplitConfig) -> np.ndarray:
    refined = stroke_map.copy()
    max_id = int(refined.max())
    for stroke_id in range(1, max_id + 1):
        label_mask = refined == stroke_id
        for comp in connected_components(label_mask):
            if len(comp) >= config.min_region_area:
                continue
            neighbor_votes: Counter[int] = Counter()
            for y, x in comp:
                for ny in range(max(0, y - 1), min(refined.shape[0], y + 2)):
                    for nx in range(max(0, x - 1), min(refined.shape[1], x + 2)):
                        other = int(refined[ny, nx])
                        if other != 0 and other != stroke_id:
                            neighbor_votes[other] += 1
            replacement = neighbor_votes.most_common(1)[0][0] if neighbor_votes else 0
            if replacement == 0:
                continue
            ys, xs = zip(*comp)
            refined[np.array(ys), np.array(xs)] = replacement
    refined[~mask] = 0
    return refined


def assign_foreground_to_strokes(
    mask: np.ndarray,
    segments: list[StrokeSegment],
    config: SplitConfig,
) -> tuple[np.ndarray, list[np.ndarray]]:
    if not segments:
        empty = np.zeros(mask.shape, dtype=np.int32)
        return empty, []

    distances, fg_points = _distance_maps(mask, segments)
    stroke_map = np.zeros(mask.shape, dtype=np.int32)
    nearest = np.argmin(distances, axis=0) + 1
    ys = fg_points[:, 0]
    xs = fg_points[:, 1]
    stroke_map[ys, xs] = nearest
    stroke_map = _reassign_tiny_regions(stroke_map, mask, config)

    min_dist = np.min(distances, axis=0)
    stroke_masks: list[np.ndarray] = []
    for idx in range(len(segments)):
        own_dist = distances[idx]
        allow = own_dist <= (min_dist + config.overlap_margin)
        stroke_mask = np.zeros(mask.shape, dtype=bool)
        stroke_mask[ys, xs] = allow
        stroke_masks.append(stroke_mask)

    return stroke_map, stroke_masks


def fill_back_gray_pixels(
    gray: np.ndarray,
    segments: list[StrokeSegment],
    stroke_map: np.ndarray,
    stroke_masks: list[np.ndarray],
    config: SplitConfig,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """把二值化时被丢弃的灰色像素(灰度 1~254)回填到已拆分的笔画中。

    二值化只保留灰度 == threshold(默认 0) 的纯黑像素，灰度 1~254 的像素被当作
    背景丢弃。本函数在笔画拆分完成后调用，把这些灰色像素按"到各笔画骨架的最近
    距离"归入最近的那一笔，从而恢复出圆润完整的笔画。纯白(255)仍是背景，不回填。
    """
    if not segments:
        return stroke_map, stroke_masks

    # 灰色前景：非纯黑(0)、非纯白(255)，且尚未被已有前景覆盖
    unfilled = (gray > 0) & (gray < 255) & (stroke_map == 0)
    if not unfilled.any():
        return stroke_map, stroke_masks

    distances, fg_points = _distance_maps(unfilled, segments)
    nearest = np.argmin(distances, axis=0) + 1
    ys = fg_points[:, 0]
    xs = fg_points[:, 1]
    stroke_map[ys, xs] = nearest

    min_dist = np.min(distances, axis=0)
    for idx in range(len(segments)):
        allow = distances[idx] <= (min_dist + config.overlap_margin)
        stroke_masks[idx][ys, xs] |= allow

    return stroke_map, stroke_masks