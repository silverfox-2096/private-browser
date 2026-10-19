#!/usr/bin/env python3
"""Render `go list -mod=readonly -m -u -json all` without changing the module graph."""
import json
from pathlib import Path
import sys


def render(text):
    decoder = json.JSONDecoder()
    modules = []
    while text.strip():
        item, end = decoder.raw_decode(text.lstrip())
        if not isinstance(item, dict) or not isinstance(item.get('Path'), str):
            raise ValueError('Expected a Go module record with a Path')
        modules.append(item)
        text = text.lstrip()[end:]
    if not modules:
        raise ValueError('Empty module update report is not a successful observation')
    updates = [m for m in modules if isinstance(m.get('Update'), dict)]
    lines = ['## Source-aware Go module updates', '',
             f'Observed {len(modules)} module records; {len(updates)} available updates.', '',
             'This report proposes no edits or deployment; scan/runtime review is required.', '']
    if updates:
        lines += ['| Module | Locked | Available |', '|---|---|---|']
        for m in updates:
            current, available = m.get('Version'), m['Update'].get('Version')
            if not isinstance(current, str) or not isinstance(available, str):
                raise ValueError('Update record has no valid current/available version')
            clean = lambda s: s.replace('|', r'\|').replace('\n', ' ')
            lines.append(f'| {clean(m["Path"])} | {clean(current)} | {clean(available)} |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    print(render(Path(sys.argv[1]).read_text()), end='')
