import re, json
for name in ['data/glyphs.js.bak', 'data/glyphs.js']:
    text = open(name, encoding='utf-8').read()
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # 直接抓 {...} 内容（贪婪匹配）
    start = text.index('window.GLYPH_DATA')
    eq = text.index('=', start)
    brace = text.index('{', eq)
    # 配对
    depth = 0
    end = -1
    for i in range(brace, len(text)):
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    body = text[brace:end+1]
    d = json.loads(body)
    g = next(x for x in d['glyphs'] if x['id'] == '08166_否_Z_說文‧不部')
    print('===', name, '===')
    for s in g['segments']:
        pts = s['points']
        ys = [p[0] for p in pts]
        xs = [p[1] for p in pts]
        print('  id={} pc={} ymin={} ymax={} xmin={} xmax={}'.format(
            s['id'], s['pointCount'], min(ys), max(ys), min(xs), max(xs)))
    print('lengths=', g['metrics']['lengths'])
    print()
