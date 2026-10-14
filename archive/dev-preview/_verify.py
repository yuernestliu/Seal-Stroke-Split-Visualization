import json, re
from pathlib import Path
text = Path('data/glyphs.js').read_text(encoding='utf-8')
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

for g in data['glyphs']:
    if g['id'].startswith('07432_先'):
        print(f"{g['id']}: {g['metrics']['segmentCount']} 笔")
        for s in g['segments']:
            pts = s['points']
            y0 = pts[0][0]
            print(f"  id={s['id']}, pointCount={s['pointCount']}, 首点 y={y0}, 起={pts[0]}, 终={pts[-1]}")

print()
# 找几个变化的
for kw in ['07433_光', '07547_冻', '07588_凤']:
    for g in data['glyphs']:
        if g['id'].startswith(kw):
            print(f"{g['id']}: {g['metrics']['segmentCount']} 笔")
            for s in g['segments']:
                pts = s['points']
                print(f"  id={s['id']}, 起={pts[0]}")