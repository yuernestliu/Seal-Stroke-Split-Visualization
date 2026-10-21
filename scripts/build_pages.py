#!/usr/bin/env python3
"""Package the static website without research, history or development dependencies."""
import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('index.html', 'license.html', 'plan.html', 'styles.css', '.nojekyll',
           'src', 'data', 'assets/fonts', 'public/assets', '模块', '字库')

def allowed_path(relative):
    parts = Path(relative).parts
    if Path(relative).is_absolute() or any(p in {'.', '..'} or p.startswith('_FORBIDDEN_') for p in parts):
        raise ValueError('Path outside packaging scope')
    path = ROOT
    for part in parts:
        path /= part
        if path.is_symlink():
            raise ValueError('Symlink outside packaging scope')
    return path

def permitted_files(directory):
    for entry in sorted(directory.iterdir(), key=lambda p:p.name):
        if entry.name.startswith('_FORBIDDEN_'): continue
        if entry.is_symlink(): continue
        if entry.name in {'.DS_Store', '__pycache__'}: continue
        if entry.is_dir(): yield from permitted_files(entry)
        elif entry.is_file(): yield entry

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='_site', help='New project-relative output folder')
    args = parser.parse_args()
    output = allowed_path(args.output)
    if output.exists():
        raise ValueError('Existing output preserved; choose a new --output directory')
    for relative in SOURCES:
        source = allowed_path(relative)
        if source == output or source in output.parents or output in source.parents:
            raise ValueError('Output must be separate from source directories')
        if not source.exists(): raise ValueError('Missing site source: '+relative)
    output.mkdir(parents=True)
    count, size = 0, 0
    for relative in SOURCES:
        source = allowed_path(relative)
        files = permitted_files(source) if source.is_dir() else (source,)
        for file in files:
            target = output / file.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
            count += 1
            size += target.stat().st_size
    print(json.dumps({'output':args.output,'files':count,'bytes':size,'entry':'index.html'},ensure_ascii=False))

if __name__ == '__main__': main()
