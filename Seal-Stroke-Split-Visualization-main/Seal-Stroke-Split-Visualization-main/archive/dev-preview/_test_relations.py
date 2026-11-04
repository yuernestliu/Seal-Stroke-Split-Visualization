"""模拟新 relation-engine 逻辑，跑在 Python 上验证输出。"""
import re
import json
from collections import Counter

# 读 glyphs.js
with open('data/glyphs.js', 'r', encoding='utf-8') as f:
    src = f.read()

# 提取 glyphs 数组
m = re.search(r'window\.GLYPH_DATA\s*=\s*(\{[\s\S]*?\n\}\s*);', src)
if not m:
    print('no match'); raise SystemExit
data = json.loads(m.group(1))
glyphs = data['glyphs']
print(f'loaded {len(glyphs)} glyphs')

# 用 ComponentDeriver 派生字段
for g in glyphs:
    section = g.get('source', {}).get('section', '') or ''
    radical = ''
    if section.startswith('說文‧'):
        radical = section[3:].rstrip('部')
    elif section and section != '来源待补':
        radical = section.rstrip('部')
    g['_radical'] = radical
    parts = g.get('parts') or []
    types = g.get('part_type') or []
    phonetic, semantic = [], []
    for i, p in enumerate(parts):
        t = types[i] if i < len(types) else ''
        if t in ('声旁', '声旁构件'):
            phonetic.append(p)
        elif t == '形旁':
            semantic.append(p)
    g['_phonetic'] = phonetic
    g['_semantic'] = semantic

# 统计
radicals = Counter(g['_radical'] for g in glyphs)
ph_chars = Counter(p for g in glyphs for p in g['_phonetic'])
sm_chars = Counter(p for g in glyphs for p in g['_semantic'])
print('--- 有数据的字 ---')
print('有 parts 数据:', sum(1 for g in glyphs if g.get('parts')))
print('有 _radical  :', sum(1 for g in glyphs if g['_radical']))
print('有 _phonetic :', sum(1 for g in glyphs if g['_phonetic']))
print('有 _semantic :', sum(1 for g in glyphs if g['_semantic']))
print()
print('--- 声旁 Top 10 ---')
for k, v in ph_chars.most_common(10): print(f'  {k}: {v} 字')
print('--- 形旁 Top 10 ---')
for k, v in sm_chars.most_common(10): print(f'  {k}: {v} 字')
print('--- 部首 Top 10 ---')
for k, v in radicals.most_common(10): print(f'  {k}: {v} 字')

# 关系函数（移植自 JS）
def intersect(a, b):
    if not a or not b: return []
    s = set(a); return [x for x in b if x in s]

def describe(src, cnd, distance=0):
    ph = intersect(src['_phonetic'], cnd['_phonetic'])
    sm = intersect(src['_semantic'], cnd['_semantic'])
    rd = [src['_radical']] if src['_radical'] and src['_radical']==cnd['_radical'] else []
    cnt = (1 if ph else 0) + (1 if sm else 0) + (1 if rd else 0)
    if cnt == 0: return None
    if ph: primary, t, base = ph, 'phonetic', 100
    elif sm: primary, t, base = sm, 'semantic', 88
    else: primary, t, base = rd, 'radical', 72
    label_map = {'phonetic':'同声旁','semantic':'同形旁','radical':'同部首'}
    pl = primary[0] if primary else ''
    label = f"{label_map[t]}·{pl}" if pl else label_map[t]
    bonus = (cnt - 1) * 4
    score = base + bonus - distance * 6
    return {'type': t, 'label': label, 'score': score, 'matches': {'phonetic':ph,'semantic':sm,'radical':rd}}

def related(glyphs, src, limit=6):
    out = []
    for c in glyphs:
        if c['id'] == src['id']: continue
        rel = describe(src, c)
        if not rel: continue
        out.append({'glyph': c, **rel})
    out.sort(key=lambda r: -r['score'])
    return out[:limit]

# 选 6 个有数据的字演示
print('\n--- 演示 6 个字的相关字形 ---')
for title in ['不', '先', '净', '凤', '宀', '尚']:
    g = next((g for g in glyphs if g['title']==title), None)
    if not g: continue
    rels = related(glyphs, g, 6)
    print(f'\n[{title}] radical={g["_radical"]} phonetic={g["_phonetic"]} semantic={g["_semantic"]}')
    for r in rels:
        print(f"  {r['glyph']['title']:>4}  score={r['score']:6.1f}  {r['label']}  ({r['type']})")
