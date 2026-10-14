#!/usr/bin/env python3
"""Generate independent per-glyph drafts, then publish checked entries only."""
import argparse,json,os,re,math
from pathlib import Path
from clean_stroke_geometry import ROOT,permitted,load_glyphs,build_record,source_signature

def validate(record,glyph):
    if record['sourceSignature']!=source_signature(glyph):raise ValueError('Original segment data changed; regenerate and recheck')
    if record['width']!=glyph['canvas']['width'] or record['height']!=glyph['canvas']['height']:raise ValueError('Canvas mismatch')
    if [s['id'] for s in record['strokes']]!=[s['id'] for s in glyph['segments']]:raise ValueError('Stroke identities changed')
    for stroke,source in zip(record['strokes'],glyph['segments']):
        if not stroke['path'].startswith('M') or not 0<stroke['width']<=10:raise ValueError('Invalid stroke geometry')
        if not re.fullmatch(r'[MLQ\d.\s+\-]+',stroke['path']):raise ValueError('Use M/L/Q path commands only')
        commands=re.findall(r'([MLQ])([^MLQ]*)',stroke['path'])
        values=[]
        for index,(command,coordinates) in enumerate(commands):
            numbers=[float(n) for n in coordinates.split()]
            if len(numbers)!=(4 if command=='Q' else 2) or not all(math.isfinite(n) for n in numbers):raise ValueError('Invalid path coordinates')
            if (index==0)!=(command=='M'):raise ValueError('Exactly one initial M is required')
            values.append(numbers)
        first=source['points'][0][::-1];last=source['points'][-1][::-1]
        if any(abs(a-b)>.03 for a,b in zip(values[0],first)) or any(abs(a-b)>.03 for a,b in zip(values[-1][-2:],last)):
            raise ValueError('Original stroke endpoints must be preserved')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['generate','publish'])
    parser.add_argument('--marks',nargs='+')
    parser.add_argument('--ids',nargs='+')
    args=parser.parse_args()
    glyphs=load_glyphs();by_id={g['id']:g for g in glyphs}
    directory=permitted('data/cleaned-glyphs');directory.mkdir(exist_ok=True)
    if args.mode=='generate':
        if not args.marks and not args.ids:parser.error('Select assigned glyphs with --marks or --ids')
        selected=[g for g in glyphs if g['mark'] in (args.marks or []) or g['id'] in (args.ids or [])]
        if not selected:parser.error('No matching glyphs')
        for glyph in selected:
            target=permitted('data/cleaned-glyphs/'+glyph['id']+'.json')
            if target.exists():raise ValueError('Existing record preserved; move it aside before regenerating: '+glyph['id'])
            record=build_record(glyph);validate(record,glyph)
            target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
            print('Draft:',glyph['mark'],glyph['id'])
    else:
        checked={};drafts=0
        with os.scandir(directory) as entries:
            files=sorted(entry.name for entry in entries if not entry.name.startswith('_FORBIDDEN_') and not entry.is_symlink() and entry.is_file(follow_symlinks=False) and entry.name.endswith('.json'))
        for name in files:
            record=json.loads(permitted('data/cleaned-glyphs/'+name).read_text())
            if record.get('status')!='display_checked':drafts+=1;continue
            if name!=record['id']+'.json' or record['id'] in checked:raise ValueError('Duplicate or mismatched glyph record')
            glyph=by_id[record['id']];validate(record,glyph);checked[record['id']]=record
        permitted('data/cleaned-glyphs.js').write_text('/* Generated from individually checked data/cleaned-glyphs/*.json. */\nwindow.CLEANED_GLYPHS = '+json.dumps(checked,ensure_ascii=False,separators=(',',':'))+';\n')
        print(f'Published {len(checked)} checked glyphs; {drafts} drafts excluded.')

if __name__=='__main__':main()
