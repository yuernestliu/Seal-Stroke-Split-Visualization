import urllib.request, urllib.parse

urls = [
    'http://localhost:8765/index.html',
    'http://localhost:8765/data/glyphs.js',
    'http://localhost:8765/data/xiaozhuan-index.json',
    'http://localhost:8765/src/render_xiaozhuan.js',
    'http://localhost:8765/src/ui.js',
    'http://localhost:8765/assets/xiaozhuan/' + urllib.parse.quote('07432_先_Z_說文‧先部.png'),
    'http://localhost:8765/assets/xiaozhuan/' + urllib.parse.quote('06631_丧_Z_小篆.png'),
]
for u in urls:
    name = u.rsplit('/', 1)[-1][:60]
    try:
        r = urllib.request.urlopen(u)
        body = r.read()
        print(f'{r.status:3d} {len(body):>7d}  {name}')
    except Exception as e:
        print(f'ERR             {name}  {e}')
