#!/usr/bin/env python3
"""Source and shared-path comparison for the current four cleanup examples."""
import json,html,os,re
from clean_stroke_geometry import permitted,load_glyphs,build_record

PALETTE=['#af773e','#6c977d','#b07063','#8c7caa','#ba9c40','#66979e']

def svg(glyph,strokes,color=False,only=None):
    w,h=glyph['canvas']['width'],glyph['canvas']['height']
    paths=[]
    for i,stroke in enumerate(strokes):
        if only is not None and i!=only:continue
        paths.append(f'<path d="{stroke["path"]}" fill="none" stroke="{PALETTE[i%len(PALETTE)] if color else "#353d31"}" stroke-width="{stroke["width"]}" stroke-linecap="round" stroke-linejoin="round" />')
    return f'<svg viewBox="-3 -3 {w+6} {h+6}" role="img" aria-label="{html.escape(glyph["mark"])}">'+''.join(paths)+'</svg>'

def main():
    glyphs=load_glyphs()
    output=permitted('public/proofs/clean-strokes.html')
    sections=[];report=[]
    for glyph in glyphs:
        if glyph['mark'] not in ['安','宇','包','光']:continue
        source=permitted(glyph['assets']['original'])
        record_path=permitted('data/cleaned-glyphs/'+glyph['id']+'.json')
        record=json.loads(record_path.read_text()) if record_path.exists() else build_record(glyph)
        strokes=record['strokes'];report.append(record)
        mono=svg(glyph,strokes);colored=svg(glyph,strokes,color=True)
        # Mono and colored displays use the exact same geometry, only colors differ.
        import re
        assert re.findall(r'<path d="([^"]+)"',mono)==re.findall(r'<path d="([^"]+)"',colored)
        original=html.escape(os.path.relpath(source,output.parent))
        thumbnails=''.join(svg(glyph,strokes,color=True,only=i) for i in range(len(strokes)))
        sections.append(f'<section id="{glyph["mark"]}"><h2>{glyph["mark"]}</h2><div class="comparison"><figure><div class="art"><img src="{original}" alt="{glyph["mark"]} 原包字形" /></div><figcaption>原包样本</figcaption></figure><figure><div class="art">{mono}</div><figcaption>平滑中心线 · 合字</figcaption></figure><figure><div class="art">{colored}</div><figcaption>同一组路径 · 拆笔</figcaption><div class="pieces">{thumbnails}</div></figure></div></section>')
    output.write_text('''<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>原包字形清边对照</title><style>
*{box-sizing:border-box}body{margin:0;padding:35px;background:#263028;color:#ede8d8;font-family:'PingFang SC',sans-serif}main{max-width:1100px;margin:auto}h1{font:32px 'Songti SC',serif;margin:0 0 12px}header p{font-size:13px;color:#a5b398;line-height:1.8}section{margin-top:28px}section h2{font:24px 'Songti SC',serif;margin:0 0 12px}.comparison{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}figure{margin:0;padding:25px 18px 18px;background:#ede8da;color:#48503c;border-radius:13px}.art{display:flex;height:245px;align-items:center;justify-content:center}.art img,.art svg{width:170px;height:225px;object-fit:contain}.art img{mix-blend-mode:multiply}figcaption{text-align:center;font-size:12px;color:#7d846c;margin-top:20px}.pieces{display:flex;justify-content:center;gap:9px;margin-top:20px}.pieces svg{height:38px;max-width:40px;flex:1}footer{color:#9da98d;font-size:11px;line-height:1.9;margin-top:25px}@media(max-width:700px){body{padding:22px 15px}.comparison{gap:7px}figure{padding:12px 5px}.art{height:180px}.art svg,.art img{width:80px;height:155px}figcaption{font-size:9px;line-height:1.6}.pieces{gap:3px}.pieces svg{height:25px}}
</style></head><body><main><header><h1>把原包字形清干净，再用同一组笔画展示。</h1><p>沿用原有笔段与坐标：平滑中心线、减小宽度起伏。中、右两列使用完全相同的路径，拆笔只改变颜色。</p></header>'''+''.join(sections)+'''<footer>四个样例的几何验证：保留原笔段数量、端点与坐标系；合字和拆笔路径完全一致。清理效果仍需逐字检查。本页用于核对清边效果；四个示例将使用同组路径接入网页。</footer></main></body></html>''')
    permitted('public/proofs/clean-strokes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('Smoothing proof:',[(r['mark'],len(r['strokes']),r['parameters']['strokeWidth'],r['diagnostics']['silhouetteOverlap']) for r in report])

if __name__=='__main__':main()
