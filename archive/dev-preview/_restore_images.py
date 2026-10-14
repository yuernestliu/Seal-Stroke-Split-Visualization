"""
把 .bak 里 28 个字的 image 字段按 'points 起点' 映射回填到当前 glyphs.js

.bak 里: id=1 image='...stroke_01.png' （原顺序）
当前 js: 排序后顺序变了，但每个 segment 的 points 起点没变
→ 用 (y0, x0) 起点元组作为 key，从 .bak 取 image 路径
"""
import json, re
from pathlib import Path

ROOT = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main')

def extract_data(text):
    m = re.search(r'window\.GLYPH_DATA\s*=\s*', text)
    brace = text.index('{', m.end())
    depth = 0; end = -1; in_str = False; esc = False
    for i in range(brace, len(text)):
        c = text[i]
        if in_str:
            if esc: esc = False
            elif c == chr(92): esc = True
            elif c == chr(34): in_str = False
        else:
            if c == chr(34): in_str = True
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: end = i; break
    return json.loads(text[brace:end+1])

bak = (ROOT / 'data' / 'glyphs.js.bak').read_text(encoding='utf-8')
cur_text = (ROOT / 'data' / 'glyphs.js').read_text(encoding='utf-8')

data_bak = extract_data(bak)
data_cur = extract_data(cur_text)

# 给 .bak 里的字建 points起点 -> image 路径映射（按 id 聚合）
# 每个字独立：{ (y0,x0): image 路径 }
def point_key(s):
    pts = s['points']
    return (tuple(pts[0]), tuple(pts[-1]))  # 起末

bak_map = {}
for g in data_bak['glyphs']:
    gid = g['id']
    bak_map[gid] = {}
    for s in g['segments']:
        if s.get('image'):
            bak_map[gid][point_key(s)] = s['image']

# 对当前 js 的 28 个字补 image
total_filled = 0
total_unmatched = 0
unmatched_examples = []
for g in data_cur['glyphs']:
    gid = g['id']
    if gid not in bak_map:
        continue
    seg_map = bak_map[gid]
    if not any(s.get('image') for s in g['segments']):
        # 这个字当前全缺 image，要从 .bak 补
        for s in g['segments']:
            key = point_key(s)
            if key in seg_map:
                s['image'] = seg_map[key]
                total_filled += 1
            else:
                total_unmatched += 1
                if len(unmatched_examples) < 5:
                    unmatched_examples.append((gid, s['id'], key))

print(f"补回 image 数: {total_filled}")
print(f"未匹配的 segment 数: {total_unmatched}")
if unmatched_examples:
    print("未匹配示例:")
    for x in unmatched_examples:
        print(f"  {x}")

# 写出当前 js（保持原格式 - 用紧凑 JSON + var 头）
# 找 header
m = re.search(r'window\.GLYPH_DATA\s*=\s*', cur_text)
header_end = m.end()
prefix = cur_text[:header_end]
# 找 suffix
suffix_match = re.search(r';\s*$', cur_text)
suffix = suffix_match.group(0) if suffix_match else ';'

new_text = prefix + json.dumps(data_cur, ensure_ascii=False, indent=2) + suffix
(ROOT / 'data' / 'glyphs.js').write_text(new_text, encoding='utf-8')
print(f"已写入: {ROOT / 'data' / 'glyphs.js'}")