#!/usr/bin/env python3
"""Summarize BuildKit's actual material digests and the installed Firefox package."""
import json
import os
from pathlib import Path
import subprocess
import sys

metadata = json.loads(Path(sys.argv[1]).read_text())
materials = metadata.get('buildx.build.provenance', {}).get('materials', [])
if not materials:
    sys.exit('Missing resolved materials in BuildKit metadata')
image = 'private-firefox:ci'
version = subprocess.check_output([
    'docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'dpkg-query',
    image, '-W', '-f=${Version}', 'firefox',
], text=True).strip()
if not version:
    sys.exit('Missing installed Firefox package version')
lines = ['## Resolved Firefox build inputs', '',
         f'Commit: `{os.environ.get("GITHUB_SHA", "local build")}`',
         f'Firefox Debian package: `{version}`',
         f'Output image: `{metadata["containerimage.digest"]}`', '',
         '| Build material | Resolved digest |', '|---|---|']
for item in materials:
    digest = item.get('digest', {}).get('sha256')
    if not digest:
        sys.exit('Missing material digest')
    uri = str(item['uri']).replace('|', '%7C').replace('\n', '')
    lines.append(f'| `{uri}` | `sha256:{digest}` |')
output = '\n'.join(lines) + '\n'
print(output)
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write(output)
