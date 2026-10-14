#!/usr/bin/env python3
"""Compare original samples with smooth vectors derived from existing segments.
Does not change the production data, website or original images.
"""
import json, html, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, gaussian_filter1d
from skimage.measure import approximate_polygon

ROOT = Path(__file__).resolve().parents[1]

def permitted(relative):
    target = ROOT
    for part in Path(relative).parts:
        if part == '..' or part.startswith('_FORBIDDEN_'):
            raise ValueError('Path outside allowed scope')
        target = target / part
        if target.is_symlink():
            raise ValueError('Symlink outside preview scope')
    return target

def number(value):
    return f'{float(value):.2f}'.rstrip('0').rstrip('.')

def smooth_path(points):
    p = np.asarray(points,dtype=float)[:,::-1]
    if len(p)>2:
        p = p[np.r_[True,np.any(np.diff(p,axis=0)!=0,axis=1)]]
    if len(p)>3:
        smoothed = gaussian_filter1d(p,sigma=1.2,axis=0,mode='nearest')
        smoothed[0],smoothed[-1] = p[0],p[-1]
        p = approximate_polygon(smoothed,tolerance=.5)
    command = [f'M{number(p[0,0])} {number(p[0,1])}']
    sampled = [p[0]]
    if len(p)==2:
        command.append(f'L{number(p[-1,0])} {number(p[-1,1])}'); sampled.append(p[-1])
    elif len(p)>2:
        start=p[0]
        for i in range(1,len(p)-1):
            end = p[-1] if i==len(p)-2 else (p[i]+p[i+1])/2
            command.append('Q'+' '.join(number(v) for v in [*p[i],*end]))
            for t in np.linspace(0,1,16)[1:]: sampled.append((1-t)**2*start+2*(1-t)*t*p[i]+t*t*end)
            start=end
    else:
        command.append(f'L{number(p[0,0]+.01)} {number(p[0,1])}')
    # Every stroke retains its original endpoints and coordinate system.
    assert np.allclose(p[0],np.asarray(points[0])[::-1])
    assert np.allclose(p[-1],np.asarray(points[-1])[::-1])
    return ' '.join(command),np.asarray(sampled)

PALETTE=['#af773e','#6c977d','#b07063','#8c7caa','#ba9c40','#66979e']

def svg(glyph,strokes,color=False,only=None):
    w,h=glyph['canvas']['width'],glyph['canvas']['height']
    paths=[]
    for i,stroke in enumerate(strokes):
        if only is not None and i!=only:continue
        paths.append(f'<path d="{stroke["path"]}" fill="none" stroke="{PALETTE[i%len(PALETTE)] if color else "#353d31"}" stroke-width="{stroke["width"]}" stroke-linecap="round" stroke-linejoin="round" />')
    return f'<svg viewBox="-3 -3 {w+6} {h+6}" role="img" aria-label="{html.escape(glyph["mark"])}">'+''.join(paths)+'</svg>'

def main():
    raw=permitted('data/glyphs.js').read_text()
    glyphs=json.loads(raw[raw.index('{'):raw.rindex('}')+1])['glyphs']
    output=permitted('public/proofs/clean-strokes.html')
    sections=[];report=[]
    for glyph in glyphs:
        if glyph['mark'] not in ['宇','包','光']:continue
        source=permitted(glyph['assets']['original'])
        ink=np.asarray(Image.open(source).convert('L'))<160
        distance=distance_transform_edt(ink)
        radii=[]
        for segment in glyph['segments']:
            yx=np.asarray(segment['points'],dtype=int)
            radii.extend(distance[yx[:,0],yx[:,1]].tolist())
        valid=np.asarray(radii);valid=valid[valid>=1]
        width=round(float(np.clip(2*np.median(valid)-.8,2,5)),2)
        strokes=[]
        scale=8;canvas=Image.new('L',(ink.shape[1]*scale,ink.shape[0]*scale));draw=ImageDraw.Draw(canvas)
        for segment in glyph['segments']:
            path,curve=smooth_path(segment['points'])
            strokes.append({'id':segment['id'],'path':path,'width':width})
            coords=[(float((x+.5)*scale),float((y+.5)*scale)) for x,y in curve]
            draw.line(coords,fill=255,width=round(width*scale),joint='curve')
            radius=width*scale/2
            for x,y in coords:draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=255)
        clean=np.asarray(canvas.resize((ink.shape[1],ink.shape[0]),Image.Resampling.LANCZOS))>=128
        iou=float(np.logical_and(ink,clean).sum()/max(1,np.logical_or(ink,clean).sum()))
        report.append({'id':glyph['id'],'mark':glyph['mark'],'width':width,'overlap':round(iou,3),'strokes':strokes})
        mono=svg(glyph,strokes);colored=svg(glyph,strokes,color=True)
        # Mono and colored displays use the exact same geometry, only colors differ.
        import re
        assert re.findall(r'<path d="([^"]+)"',mono)==re.findall(r'<path d="([^"]+)"',colored)
        original=html.escape(os.path.relpath(source,output.parent))
        thumbnails=''.join(svg(glyph,strokes,color=True,only=i) for i in range(len(strokes)))
        sections.append(f'<section><h2>{glyph["mark"]}</h2><div class="comparison"><figure><div class="art"><img src="{original}" alt="{glyph["mark"]} 原包字形" /></div><figcaption>原包样本</figcaption></figure><figure><div class="art">{mono}</div><figcaption>平滑中心线 · 合字</figcaption></figure><figure><div class="art">{colored}</div><figcaption>同一组路径 · 拆笔</figcaption><div class="pieces">{thumbnails}</div></figure></div></section>')
    output.write_text('''<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>原包字形清边对照</title><style>
*{box-sizing:border-box}body{margin:0;padding:35px;background:#263028;color:#ede8d8;font-family:'PingFang SC',sans-serif}main{max-width:1100px;margin:auto}h1{font:32px 'Songti SC',serif;margin:0 0 12px}header p{font-size:13px;color:#a5b398;line-height:1.8}section{margin-top:28px}section h2{font:24px 'Songti SC',serif;margin:0 0 12px}.comparison{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}figure{margin:0;padding:25px 18px 18px;background:#ede8da;color:#48503c;border-radius:13px}.art{display:flex;height:245px;align-items:center;justify-content:center}.art img,.art svg{width:170px;height:225px;object-fit:contain}.art img{mix-blend-mode:multiply}figcaption{text-align:center;font-size:12px;color:#7d846c;margin-top:20px}.pieces{display:flex;justify-content:center;gap:9px;margin-top:20px}.pieces svg{height:38px;max-width:40px;flex:1}footer{color:#9da98d;font-size:11px;line-height:1.9;margin-top:25px}@media(max-width:700px){body{padding:22px 15px}.comparison{gap:7px}figure{padding:12px 5px}.art{height:180px}.art svg,.art img{width:80px;height:155px}figcaption{font-size:9px;line-height:1.6}.pieces{gap:3px}.pieces svg{height:25px}}
</style></head><body><main><header><h1>把原包字形清干净，再用同一组笔画展示。</h1><p>沿用原有笔段与坐标：平滑中心线、减小宽度起伏。中、右两列使用完全相同的路径，拆笔只改变颜色。</p></header>'''+''.join(sections)+'''<footer>三个样例的几何验证：保留原笔段数量、端点与坐标系；合字和拆笔路径完全一致。清理效果仍需逐字检查。本页为方法对照，未替换网站默认字体。</footer></main></body></html>''')
    permitted('public/proofs/clean-strokes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('Smoothing proof:',[(r['mark'],len(r['strokes']),r['width'],r['overlap']) for r in report])

if __name__=='__main__':main()
