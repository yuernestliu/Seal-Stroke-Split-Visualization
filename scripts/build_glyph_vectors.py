#!/usr/bin/env python3
"""Trace permitted source PNG outlines into compact, smooth SVG paths.

This derives display geometry only. Imported glyphs, stroke order and research
materials are not changed. Requires Pillow, NumPy, SciPy and scikit-image.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter
from scipy.interpolate import splprep, splev
from skimage.measure import find_contours, approximate_polygon

ROOT = Path(__file__).resolve().parents[1]

def safe_file(relative):
    parts = Path(relative).parts
    if any(p.startswith('_FORBIDDEN_') or p == '..' for p in parts):
        raise ValueError('Source outside permitted scope')
    target = ROOT
    for part in parts:
        target = target / part
        if target.is_symlink():
            raise ValueError('Symlink outside vector conversion scope')
    return target

def number(value):
    return f'{float(value):.2f}'.rstrip('0').rstrip('.')

def trace(relative, smooth=False):
    image = Image.open(safe_file(relative)).convert('L')
    ink = np.asarray(image) < 160
    h, w = ink.shape
    field = gaussian_filter(np.pad(ink.astype(float), 2), sigma=.75 if smooth else .55)
    outlines = find_contours(field, .46)
    paths = []
    # Validate the sampled curves against the original foreground silhouette.
    drawn = np.zeros((h, w), dtype=bool)
    for contour in outlines:
        if smooth and len(contour) > 10:
            curve, _ = splprep([contour[:, 0], contour[:, 1]], s=len(contour)*.10, per=True)
            contour = np.column_stack(splev(np.linspace(0, 1, len(contour)*2), curve))
        points = approximate_polygon(contour, tolerance=.32)[:-1][:, ::-1] - 2
        if len(points) < 3:
            continue
        paths.append(f'M{number(points[0,0])} {number(points[0,1])}')
        sampled = []
        for i, a in enumerate(points):
            prev = points[(i-1) % len(points)]
            b = points[(i+1) % len(points)]
            after = points[(i+2) % len(points)]
            c1 = a + (b-prev)/6
            c2 = b - (after-a)/6
            paths.append('C'+' '.join(number(v) for v in [*c1,*c2,*b]))
            for t in np.linspace(0,1,8):
                sampled.append((1-t)**3*a + 3*(1-t)**2*t*c1 + 3*(1-t)*t*t*c2 + t**3*b)
        paths.append('Z')
        bitmap = Image.new('1',(w*4,h*4))
        ImageDraw.Draw(bitmap).polygon([(float(x*4+2),float(y*4+2)) for x,y in sampled],fill=1)
        mask = np.asarray(bitmap)[2::4,2::4]
        drawn ^= mask
    union = np.logical_or(ink,drawn).sum()
    iou = np.logical_and(ink,drawn).sum()/max(1,union)
    return {'width':w,'height':h,'path':' '.join(paths)}, float(iou)

def main():
    source = safe_file('data/glyphs.js').read_text()
    glyphs = json.loads(source[source.index('{'):source.rindex('}')+1])['glyphs']
    vectors, quality = {}, []
    for glyph in glyphs:
        full, iou = trace(glyph['assets']['original'], smooth=True)
        # Small or fine glyphs use conservative tracing if smoothing changes too
        # much of the original silhouette.
        if iou < .90:
            full, iou = trace(glyph['assets']['original'])
        full['segments'] = [trace(s['image'])[0] for s in glyph['segments']]
        vectors[glyph['id']] = full
        quality.append(iou)
    # A low overlap signals the asset is not an ordinary dark-on-light glyph.
    if min(quality) < .88:
        raise ValueError(f'Outline validation failed: minimum IoU {min(quality):.3f}')
    safe_file('data/glyph-vectors.js').write_text('/* Generated from existing glyph PNGs by scripts/build_glyph_vectors.py. */\nwindow.GLYPH_VECTORS = '+json.dumps(vectors,ensure_ascii=False,separators=(',',':'))+';\n')
    print(f'{len(vectors)} glyph outlines generated; silhouette overlap min={min(quality):.3f}, mean={np.mean(quality):.3f}.')

if __name__ == '__main__':
    main()
