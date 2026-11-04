#!/usr/bin/env python3
"""Adapt student IDS tables into traceable, unconfirmed priors for the 500 pilot."""
import csv,json
from pathlib import Path
from build_library import safe,write_json

def main():
    inventory=json.loads(safe('字库/字表/常用500字.json').read_text())
    wanted={r['glyphId'] for r in inventory['targets'] if r['glyphId']}
    records={}
    folder=safe('资料/部件与笔画/学生资料/部件组成')
    for file in sorted(folder.iterdir(),key=lambda p:p.name):
        if file.name.startswith('_FORBIDDEN_'):continue
        if file.is_symlink() or not file.is_file() or file.suffix!='.csv':continue
        with file.open(encoding='utf-8-sig',newline='') as source:
            for row in csv.DictReader(source):
                name=row.get('文件名','')
                if '/' in name or '\\' in name or name.startswith('_FORBIDDEN_'):continue
                glyph_id=Path(name).stem
                if glyph_id not in wanted:continue
                parts=[p.strip() for p in row.get('归一部件','').split('；') if p.strip()]
                record={'glyphId':glyph_id,'mark':row.get('字',''),'structure':row.get('结构',''),
                    'parts':parts,'status':'candidate_needs_review','method':'student_IDS_prior',
                    'source':file.relative_to(safe('资料')).as_posix(), 'notes':row.get('备注',''),
                    'geometryStatus':'not_pixel_alignment','confirmed':False}
                if glyph_id in records and records[glyph_id]['parts']!=parts:
                    records[glyph_id].setdefault('conflicts',[]).append(record)
                else:records[glyph_id]=record
    write_json('字库/部件候选/500字候选.json',{'schemaVersion':1,'scope':'500','confirmed':False,
        'description':'现代字 IDS / 部首先验候选；不是小篆像素分割结果，也不是梯径分类结果。','records':list(records.values())})
    safe('字库/部件候选/先验索引.js').write_text('/* Candidate IDS priors only; never confirmed geometry. */\nwindow.COMPONENT_PRIORS = '+json.dumps(records,ensure_ascii=False,separators=(',',':'))+';\n')
    print(f'Prepared {len(records)} unconfirmed component priors for {len(wanted)} available pilot glyphs.')

if __name__=='__main__':main()
