"""
审计所有 124 个字的 segments 完整性：
- segments 数组是否为空
- 每段的 points 是否为空数组
- pointCount 是否 == len(points)
- pixelCount 是否异常（0 或过大）
- id 是否完整覆盖 1..N
"""
import json, re
from pathlib import Path

text = Path(r'data\glyphs.js').read_text(encoding='utf-8')
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
data = json.loads(text[brace:end+1])

problems = []
for g in data['glyphs']:
    gid = g['id']
    segs = g.get('segments', [])
    issue = []

    # 1. segments 数组空
    if not segs:
        issues = ["segments 空"]

    # 2. 每段检查
    for s in segs:
        sid = s.get('id', '?')
        pts = s.get('points', [])
        pc = s.get('pointCount', -1)
        px = s.get('pixelCount', -1)

        if not pts:
            issue.append(f"  id={sid}: points 空")
        if pc != len(pts):
            issue.append(f"  id={sid}: pointCount={pc} != len(points)={len(pts)}")
        if px == 0 and len(pts) > 0:
            issue.append(f"  id={sid}: pixelCount=0 但 points 有 {len(pts)} 点")

    # 3. id 覆盖 1..N
    ids = [s.get('id') for s in segs]
    if sorted(ids) != list(range(1, len(segs)+1)):
        issue.append(f"  ids 不连续: {ids}")

    # 4. lengths 跟 segments 对应
    lens = g.get('metrics', {}).get('lengths', [])
    if len(lens) != len(segs):
        issue.append(f"  lengths({len(lens)}) != segments({len(segs)})")

    if issue:
        problems.append((gid, issue))

print(f"总字数: {len(data['glyphs'])}")
print(f"有问题字数: {len(problems)}")
print()
for gid, issues in problems:
    print(f"{gid}:")
    for s in issues:
        print(s)
    print()