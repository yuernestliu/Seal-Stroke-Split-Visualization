#!/usr/bin/env python3
"""Serve only the static website; do not expose research, archives or dependencies."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {'index.html', 'license.html', 'styles.css', 'src', 'data', 'assets', 'public'}

class SiteHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        parts = Path(unquote(urlsplit(path).path).lstrip('/')).parts
        if not parts:
            parts = ('index.html',)
        if parts[0] not in ALLOWED or any(p in {'.', '..'} or p.startswith('_FORBIDDEN_') for p in parts):
            return str(ROOT / '__unavailable__')
        candidate = ROOT
        for part in parts:
            candidate = candidate / part
            if candidate.is_symlink():
                return str(ROOT / '__unavailable__')
        return str(candidate)

    def list_directory(self, path):
        self.send_error(404)
        return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=4173)
    args = parser.parse_args()
    print(f'篆游预览: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), SiteHandler).serve_forever()
