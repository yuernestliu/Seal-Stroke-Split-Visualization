import json, re
src = open('data/glyphs.js', 'r', encoding='utf-8').read()
m = re.search(r'window\.GLYPH_DATA\s*=\s*(\{[\s\S]*?\n\}\s*);', src)
data = json.loads(m.group(1))
for title in ['净', '冻', '凊', '凌', '先', '宀', '不']:
    g = next((g for g in data['glyphs'] if g['title'] == title), None)
    if not g: continue
    sec = g['source']['section']
    parts = g.get('parts')
    ptypes = g.get('part_type')
    print(f'[{title}] section={sec}, parts={parts}, part_type={ptypes}')
