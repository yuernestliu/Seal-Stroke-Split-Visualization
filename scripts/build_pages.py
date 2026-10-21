#!/usr/bin/env python3
"""Export only frontend code, minimal display data and images referenced by the UI."""
import argparse
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
GLYPH_KEYS = ('id','sourceId','mark','title','components','reviewStatus','metrics',
              'parts','part_type','original_meaning','meaning_extend','structure_desc',
              'part_comment','xing_pang','sheng_pang')


def allowed_path(relative):
    parts = Path(relative).parts
    if Path(relative).is_absolute() or any(p in {'.','..'} or p.startswith('_FORBIDDEN_') for p in parts):
        raise ValueError('Path outside packaging scope')
    path = ROOT
    for part in parts:
        path /= part
        if path.is_symlink():
            raise ValueError('Symlink outside packaging scope')
    return path


def payload(relative):
    text = allowed_path(relative).read_text(encoding='utf-8')
    return json.JSONDecoder().raw_decode(text[text.index('{'):])[0]


def display_glyph(glyph):
    result = {key:glyph[key] for key in GLYPH_KEYS if key in glyph}
    result['source'] = {k:v for k,v in glyph['source'].items() if k in ('collection','section','experiment')}
    result['assets'] = {k:v for k,v in glyph['assets'].items() if k in ('original','composite') and v}
    result['segments'] = [{k:v for k,v in s.items() if k in ('id','pointCount','pixelCount','points','image')} for s in glyph.get('segments',[])]
    return result


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        for key in ('src','href'):
            if attrs.get(key): self.paths.append(attrs[key])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',default='_site',help='New project-relative output folder')
    args = parser.parse_args()
    output = allowed_path(args.output)
    if output.exists(): raise ValueError('Existing output preserved; choose a new --output directory')
    if output == ROOT or any(p in {'src','data','assets','public','模块','字库','scripts','docs','资料','research','archive','.git','.github','node_modules'} for p in Path(args.output).parts):
        raise ValueError('Output must be separate from source directories')
    needed = {'.nojekyll'}
    overrides = {}

    def add_url(url, parent=''):
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc or not parsed.path: return
        if parsed.path.startswith('/'): raise ValueError('Website assets must use project-relative URLs')
        path = (Path(parent) / unquote(parsed.path)).as_posix()
        allowed_path(path)
        needed.add(path)

    for entry in ('index.html','plan.html','license.html'):
        needed.add(entry)
        links = Links()
        links.feed(allowed_path(entry).read_text())
        for url in links.paths: add_url(url)
    for css in [name for name in needed if name.endswith('.css')]:
        for url in re.findall(r'url\(["\']?([^\)"\']+)["\']?\)',allowed_path(css).read_text()):
            add_url(url,Path(css).parent.as_posix())

    def export(relative, variable, data):
        if relative not in needed: raise ValueError('Unreferenced display export: '+relative)
        overrides[relative] = '/* Display export only; full research records remain in the repository. */\nwindow.'+variable+' = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n'

    base = payload('data/glyphs.js')
    base_display = {'glyphs':[display_glyph(g) for g in base['glyphs']]}
    export('data/glyphs.js','GLYPH_DATA',base_display)
    template = payload('data/template-glyphs.js')
    template_display = {'glyphs':[display_glyph(g) for g in template['glyphs']],
        'partsByMark':{mark:{'width':v['width'],'height':v['height'],
            'parts':[{k:x for k,x in part.items() if k in ('mask','cx','cy','palette')} for part in v['parts']]}
            for mark,v in template['partsByMark'].items()}}
    export('data/template-glyphs.js','TEMPLATE_GLYPH_DATA',template_display)
    clean = payload('data/cleaned-glyphs.js')
    export('data/cleaned-glyphs.js','CLEANED_GLYPHS',
        {key:{k:v for k,v in value.items() if k in ('id','mark','width','height','status','strokes')} for key,value in clean.items()})
    priors = payload('字库/部件候选/先验索引.js')
    export('字库/部件候选/先验索引.js','COMPONENT_PRIORS',
        {key:{k:v for k,v in value.items() if k in ('parts','status','confirmed','method')} for key,value in priors.items()})

    for glyph in base_display['glyphs']+template_display['glyphs']:
        for url in glyph['assets'].values(): add_url(url)
        for segment in glyph['segments']:
            if segment.get('image'): add_url(segment['image'])
    for record in template_display['partsByMark'].values():
        for part in record['parts']: add_url(part['mask'])
    inventory = payload('字库/浏览索引.js')
    for glyph_id,mark,section in inventory['entries']: add_url(inventory['imageBase']+glyph_id+'.png')
    for filename in payload('data/xiaozhuan-index.js').values(): add_url('./字库/原始字形/'+filename)
    story_source = allowed_path('模块/字源故事/故事数据.js')
    story_code = "const fs=require('node:fs'),vm=require('node:vm');const context={window:{}};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context,{timeout:1000});process.stdout.write(JSON.stringify(context.window.GLYPH_STORIES));"
    stories = json.loads(subprocess.check_output(['node','-e',story_code,str(story_source)],text=True))
    for story in stories.values():
        for step in story.get('timeline',[]):
            if step.get('image'): add_url(step['image'])

    output.mkdir(parents=True)
    size = 0
    for relative in sorted(needed):
        source = allowed_path(relative)
        if not source.is_file(): raise ValueError('Missing display asset: '+relative)
        if relative.endswith(('.csv','.json','.txt')): raise ValueError('Research data cannot be published: '+relative)
        destination = output / relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        if relative in overrides: destination.write_text(overrides[relative],encoding='utf-8')
        else: shutil.copy2(source,destination)
        size += destination.stat().st_size
    print(json.dumps({'output':args.output,'files':len(needed),'bytes':size,
        'displayExports':list(overrides),'entry':'index.html'},ensure_ascii=False))


if __name__ == '__main__': main()
