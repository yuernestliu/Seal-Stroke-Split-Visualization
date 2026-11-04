import sys
from pathlib import Path
ROOT = Path(r"c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main")
sys.path.insert(0, str(ROOT / "拆笔画修改" / "拆笔画_修改" / "src"))

import json, re
text = open(ROOT / "data" / "glyphs.js.bak", encoding="utf-8").read()
text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
start = text.index("window.GLYPH_DATA")
eq = text.index("=", start)
brace = text.index("{", eq)
depth = 0
end = -1
for i in range(brace, len(text)):
    c = text[i]
    if c == "{":
        depth += 1
    elif c == "}":
        depth -= 1
        if depth == 0:
            end = i
            break
body = text[brace:end+1]
d = json.loads(body)
g = next(x for x in d["glyphs"] if x["id"] == "08166_否_Z_說文‧不部")

from seal_stroke_split.stroke_ordering import (
    _intersection_count, _y_range, _compare_strokes, _center_compare,
    segment_center
)
from seal_stroke_split.types import StrokeSegment

seg_objs = [
    StrokeSegment(stroke_id=s["id"], points=[tuple(p) for p in s["points"]])
    for s in g["segments"]
]
point_sets = [set(seg.points) for seg in seg_objs]

print("=== 每笔信息 ===")
for i, seg in enumerate(seg_objs):
    a, b = _y_range(seg)
    c = segment_center(seg)
    cross = _intersection_count(i, seg_objs, point_sets)
    print("  idx={} stroke_id={} yrange=({},{})  center=({:.1f},{:.1f})  cross={}".format(
        i, seg.stroke_id, a, b, c[0], c[1], cross))

print("\n=== 两两比较结果（A赢=+1, B赢=-1, 平=0）===")
wins = [0] * len(seg_objs)
crossings_cache = {i: _intersection_count(i, seg_objs, point_sets) for i in range(len(seg_objs))}
for i in range(len(seg_objs)):
    for j in range(i+1, len(seg_objs)):
        r = _compare_strokes(i, j, seg_objs, crossings_cache)
        if r > 0:
            wins[i] += 1
            who = "A(idx={})".format(i)
        elif r < 0:
            wins[j] += 1
            who = "B(idx={})".format(j)
        else:
            who = "平"
        a_yr, b_yr = _y_range(seg_objs[i]), _y_range(seg_objs[j])
        a_cr, b_cr = crossings_cache[i], crossings_cache[j]
        print("  ({},{}): y({}..{},{}..{}) cross({},{}) -> {}".format(
            i, j, a_yr[0], a_yr[1], b_yr[0], b_yr[1], a_cr, b_cr, who))

print("\n=== 胜场 ===")
for i, w in enumerate(wins):
    print("  idx={} stroke_id={} wins={}".format(i, seg_objs[i].stroke_id, w))
