"""Shared centerline cleanup; original glyphs and annotations stay untouched."""
import json, hashlib
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

def source_signature(glyph):
    payload = {'canvas':glyph['canvas'],'segments':[{'id':s['id'],'points':s['points']} for s in glyph['segments']]}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def load_glyphs():
    source=permitted('data/glyphs.js').read_text()
    return json.loads(source[source.index('{'):source.rindex('}')+1])['glyphs']

def build_record(glyph):
    source=permitted(glyph['assets']['original'])
    ink=np.asarray(Image.open(source).convert('L'))<160
    distance=distance_transform_edt(ink)
    radii=[]
    for segment in glyph['segments']:
        points=np.asarray(segment['points'],dtype=int)
        if not len(points) or np.any(points<0) or np.any(points[:,0]>=ink.shape[0]) or np.any(points[:,1]>=ink.shape[1]):
            raise ValueError('Stroke points require manual review')
        radii.extend(distance[points[:,0],points[:,1]].tolist())
    valid=np.asarray(radii);valid=valid[valid>=1]
    if not len(valid):raise ValueError('No stroke centerline inside source ink')
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
    overlap=float(np.logical_and(ink,clean).sum()/max(1,np.logical_or(ink,clean).sum()))
    return {'id':glyph['id'],'mark':glyph['mark'],'width':glyph['canvas']['width'],'height':glyph['canvas']['height'],
            'status':'draft','method':'centerline-quadratic-v1','parameters':{'sigma':1.2,'simplifyTolerance':.5,'strokeWidth':width},
            'sourceSignature':source_signature(glyph),'diagnostics':{'silhouetteOverlap':round(overlap,3),'endpointCheck':'passed'},'strokes':strokes}
