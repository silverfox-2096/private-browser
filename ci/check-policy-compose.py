#!/usr/bin/env python3
"""Ensure the published Compose recipe still installs the required policy mount."""
import json
from pathlib import Path
import subprocess
import os

ROOT = Path(__file__).resolve().parents[1]


def check(document):
    services = document['services']
    mounts = [v for v in services['gluetun'].get('volumes', [])
              if v.get('target') == '/iptables/post-rules.txt']
    assert len(mounts) == 1, 'required post-rules mount missing/duplicated'
    mount = mounts[0]
    assert mount.get('type') == 'bind' and mount.get('read_only') is True, 'policy must be a read-only bind'
    assert Path(mount['source']).resolve() == (ROOT / 'local-app-post-rules.txt').resolve(), 'unexpected policy source'
    assert services['firefox'].get('network_mode') == 'service:gluetun', 'browser must share Gluetun namespace'
    assert not services['firefox'].get('privileged', False), 'browser must not be privileged'
    assert not {x.upper().removeprefix('CAP_') for x in services['firefox'].get('cap_add', [])}.intersection({'ALL', 'NET_ADMIN'}), 'browser must not administer firewall'


def main():
    # Only this disposable checkout and dummy interpolation values, never the live stack.
    env = dict(os.environ, WIREGUARD_PRIVATE_KEY='unused-policy-fixture', WIREGUARD_ADDRESSES='10.2.0.2/32', GLUETUN_API_KEY='unused-policy-fixture')
    result = subprocess.run(['docker', 'compose', '--project-directory', str(ROOT), '--profile', 'test', 'config', '--format', 'json'], env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, 'Compose recipe could not be inspected'
    document = json.loads(result.stdout)
    check(document)
    # Mutation witnesses: removed or writable policy mounts must fail this gate.
    import copy
    for mutation in ('remove', 'writable'):
        broken = copy.deepcopy(document)
        if mutation == 'remove':
            broken['services']['gluetun']['volumes'] = [v for v in broken['services']['gluetun']['volumes'] if v.get('target') != '/iptables/post-rules.txt']
        else:
            next(v for v in broken['services']['gluetun']['volumes'] if v.get('target') == '/iptables/post-rules.txt')['read_only'] = False
        try:
            check(broken)
        except AssertionError:
            continue
        raise AssertionError('broken Compose policy received PASS')
    print('PASS Compose policy mount/namespace controls and removed/writable-mount mutations')


if __name__ == '__main__':
    main()
