#!/usr/bin/env python3
"""Build reproducible nested teaching inventories from one permitted image store."""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def safe(relative):
    parts = Path(relative).parts
    if Path(relative).is_absolute() or any(p in {'.', '..'} or p.startswith('_FORBIDDEN_') for p in parts):
        raise ValueError('Path outside scope')
    result = ROOT
    for part in parts:
        result /= part
        if result.is_symlink():
            raise ValueError('Symlink outside scope')
    return result

def payload(relative):
    text = safe(relative).read_text(encoding='utf-8')
    return json.JSONDecoder().raw_decode(text[text.index('{'):])[0]

def write_json(relative, data):
    target = safe(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def main():
    base = payload('data/glyphs.js')['glyphs']
    templates = payload('data/template-glyphs.js')
    cleaned = payload('data/cleaned-glyphs.js')
    vectors = payload('data/glyph-vectors.js')
    prepared = {g['id']: g for g in base + templates['glyphs']}
    entries = []
    directory = safe('字库/原始字形')
    for file in sorted(directory.iterdir(), key=lambda p:p.name):
        if file.name.startswith('_FORBIDDEN_'): continue
        if file.is_symlink() or not file.is_file(): continue
        match = re.fullmatch(r'(\d+)_(.+?)_Z_(.+)\.png', file.name)
        glyph = prepared.get(file.stem, {})
        if match:
            source_id, mark, section = match.groups()
        elif glyph:
            source_id, mark, section = glyph['sourceId'], glyph['mark'], glyph['source']['section']
        else:
            raise ValueError('Unindexed permitted PNG: '+file.name)
        entries.append({'id': file.stem, 'mark': mark, 'sourceId': source_id,
            'section': section, 'image': './字库/原始字形/'+file.name,
            'outlineReady': file.stem in vectors,
            'strokeCleanupChecked': file.stem in cleaned,
            'hasStrokeData': bool(glyph.get('segments')),
            'hasTemplateParts': mark in templates['partsByMark'],
            'hasStory': bool(glyph.get('original_meaning'))})
    by_mark = {e['mark']: e for e in entries}
    conversions = {}
    for line in safe('字库/来源/OpenCC单字映射.txt').read_text().splitlines():
        if not line or line.startswith('#'): continue
        key, value = line.split('\t', 1)
        conversions[key] = value.split()
    with safe('字库/来源/常用字频序.csv').open(encoding='utf-8-sig', newline='') as file:
        frequencies = list(csv.DictReader(file))
    targets = []
    for row in frequencies:
        character = row['hanzi']
        alternatives = [m for m in conversions.get(character, []) if m in by_mark]
        mapped = character if character in by_mark else next(iter(alternatives), None)
        record = {'rank': int(row['rank']), 'character': character,
            'frequency': int(row['count']), 'sealMark': mapped,
            'glyphId': by_mark[mapped]['id'] if mapped else None,
            'mappingStatus': 'exact' if mapped == character else 'converted_needs_review' if mapped else 'missing',
            'alternatives': alternatives if mapped != character else []}
        targets.append(record)
    eligible, seen_ids = [], set()
    for record in targets:
        if record['glyphId'] and record['glyphId'] not in seen_ids:
            eligible.append(record)
            seen_ids.add(record['glyphId'])
    sets, inventory_stats = {}, {}
    for size in [500, 2000]:
        records = eligible[:size]
        if len(records) != size: raise ValueError('Frequency list shorter than requested inventory')
        ids = list(dict.fromkeys(r['glyphId'] for r in records if r['glyphId']))
        selected = [e for e in entries if e['id'] in set(ids)]
        stats = {'targetCharacters': size, 'matchedTargets': sum(bool(r['glyphId']) for r in records),
            'availableGlyphs': len(ids), 'missingTargets': sum(not r['glyphId'] for r in records),
            'convertedTargets': sum(r['mappingStatus']=='converted_needs_review' for r in records),
            'frequencyRankCutoff': records[-1]['rank'],
            'missingInSourceTopN': sum(not r['glyphId'] for r in targets[:size]),
            'cleanedGlyphs': sum(e['strokeCleanupChecked'] for e in selected),
            'outlineGlyphs': sum(e['outlineReady'] for e in selected),
            'strokeDataGlyphs': sum(e['hasStrokeData'] for e in selected),
            'templateGlyphs': sum(e['hasTemplateParts'] for e in selected),
            'storyGlyphs': sum(e['hasStory'] for e in selected)}
        sets[str(size)] = ids
        inventory_stats[str(size)] = stats
        write_json(f'字库/字表/常用{size}字.json', {'status':'candidate_needs_review',
            'basis':'项目已有 BCC 多领域单字频序；按频序选取可匹配且字形ID不重复的前500/2000字。是项目试跑候选集，不是原字频表Top500/2000。高频缺字单列，简繁映射待人工校核。',
            'source':'字库/来源/字频来源.json', 'stats':stats, 'targets':records})
    stats = {'totalGlyphs':len(entries), 'preparedGlyphs':len(prepared),
        'cleanedGlyphs':sum(e['strokeCleanupChecked'] for e in entries),
        'outlineGlyphs':sum(e['outlineReady'] for e in entries),
        'strokeDataGlyphs':sum(e['hasStrokeData'] for e in entries),
        'templateGlyphs':sum(e['hasTemplateParts'] for e in entries),
        'storyGlyphs':sum(e['hasStory'] for e in entries), 'inventories':inventory_stats}
    write_json('字库/字表/全部字形.json', {'stats':stats,'glyphs':entries})
    write_json('字库/字表/待补字形.json', [r for r in targets if not r['glyphId']])
    compact = {'stats':stats, 'entries':[[e['id'],e['mark'],e['section']] for e in entries],
        'sets':sets,'aliases':{r['character']:r['glyphId'] for r in targets if r['glyphId']},
        'imageBase':'./字库/原始字形/'}
    safe('字库/浏览索引.js').write_text('/* Generated by scripts/build_library.py. */\nwindow.SEAL_LIBRARY = '+json.dumps(compact,ensure_ascii=False,separators=(',',':'))+';\n')
    task_path = safe('字库/字表/500字任务表.csv')
    assignments = {}
    if task_path.is_file():
        with task_path.open(encoding='utf-8-sig', newline='') as existing:
            assignments = {row['字形ID']: row for row in csv.DictReader(existing)}
    with task_path.open('w', encoding='utf-8-sig', newline='') as file:
        writer=csv.writer(file)
        writer.writerow(['频序','常用字','小篆字','字形ID','映射状态','原图','轮廓SVG','平滑笔段已核','拆笔资料','模板候选','故事','负责人','复核人','备注'])
        by_id={e['id']:e for e in entries}
        for r in eligible[:500]:
            e=by_id.get(r['glyphId'],{})
            assigned = assignments.get(r['glyphId'], {})
            writer.writerow([r['rank'],r['character'],r['sealMark'] or '',r['glyphId'] or '',r['mappingStatus'],
                '有' if e else '待补','有' if e.get('outlineReady') else '待做',
                '已核' if e.get('strokeCleanupChecked') else '待做','有' if e.get('hasStrokeData') else '待做',
                '待校核' if e.get('hasTemplateParts') else '', '有资料' if e.get('hasStory') else '待补',
                assigned.get('负责人',''), assigned.get('复核人',''), assigned.get('备注','')])
    print(json.dumps(stats,ensure_ascii=False,indent=2))

if __name__ == '__main__': main()
