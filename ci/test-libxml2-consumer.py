#!/usr/bin/env python3
"""Run an original-header consumer against an exact Firefox artifact; no VPN."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
image = sys.argv[1] if len(sys.argv) > 1 else 'private-firefox:ci'
identity = subprocess.check_output(['docker', 'image', 'inspect', '-f', '{{.Id}}', image], text=True).strip()
with tempfile.TemporaryDirectory(prefix='pb-xml-consumer-') as temp:
    subprocess.run(['docker', 'buildx', 'build', '--output', 'type=local,dest=' + temp,
                    '-f', str(ROOT / 'libxml2-patched' / 'Dockerfile.consumer'),
                    str(ROOT / 'libxml2-patched')], check=True)
    print('Exact runtime image: ' + identity, flush=True)
    print('Compiler headers:\n' + (Path(temp) / 'headers.txt').read_text(), flush=True)
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cap-drop', 'ALL',
                    '--read-only', '--user', f'{os.getuid()}:{os.getgid()}',
                    '--tmpfs', '/tmp:rw,nosuid,nodev', '-e', 'XDG_CACHE_HOME=/tmp/cache',
                    '-v', temp + ':/test:ro', '--entrypoint', '/test/consumer-smoke', identity], check=True)
print(json.dumps({'status': 'PASS', 'image': identity,
                  'scope': 'original-header DOM/entity, actual librsvg/GdkPixbuf and malformed SVG error handling; isolated no-network runtime'}))
