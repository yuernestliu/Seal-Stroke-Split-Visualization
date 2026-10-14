import json, re
text = open('data/glyphs.js', encoding='utf-8').read()
text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
m = re.search(r'window\.GLYPH_DATA\s*=\s*(\{.*\})\s*;?\s*$', text, flags=re.DOTALL)
d = json.loads(m.group(1))
for g in d['glyphs']:
    if g['id'] in ('08166_否_Z_說文‧不部', '00194_㒸_Z_說文‧八部', '07008_侠_Z_說文‧人部'):
        print(g['id'])
        for s in g['segments']:
            pts = s['points']
            ys = [p[0] for p in pts]
            xs = [p[1] for p in pts]
            print('  id={} pointCount={} y_range=({},{}) x_range=({},{})'.format(
                s['id'], s['pointCount'], min(ys), max(ys), min(xs), max(xs)))
        print()
