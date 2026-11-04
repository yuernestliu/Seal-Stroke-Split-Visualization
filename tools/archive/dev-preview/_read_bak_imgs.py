"""读 .bak 里 07432_先 每个 segment 的 image 字段值"""
import json, re
from pathlib import Path

bak = (Path(r'data\glyphs.js.bak')).read_text(encoding='utf-8')

m = re.search(r'window\.GLYPH_DATA\s*=\s*', bak)
brace = bak.index('{', m.end())
depth = 0; end = -1; in_str = False; esc = False
for i in range(brace, len(bak)):
    c = bak[i]
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
data = json.loads(bak[brace:end+1])

# 找 07432_先
for g in data['glyphs']:
    if g['id'].startswith('07432_先_'):
        print(f"=== {g['id']} ===")
        for s in g['segments']:
            print(f"  id={s['id']}: 起={s['points'][0]} image={s.get('image', '<缺>')!r}")
        break