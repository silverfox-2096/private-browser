#!/usr/bin/env python3
"""Real isolated dual-stack controls; no VPN keys, production network or daemon mounts."""
import argparse
import importlib.util
import json
from pathlib import Path
import random
import shlex
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('policy', ROOT / 'check-local-app-policy.py')
policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)


def run(*args, check=True, timeout=35):
    result = subprocess.run(['docker', *args], text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('Docker fixture command failed: ' + ' '.join(args[:3]) + ': ' + result.stderr)
    return result


def records(text):
    return [json.loads(line) for line in text.splitlines() if line.startswith('{')]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--firewall-image', required=True)
    ap.add_argument('--python-image', default=next(x.split('image:', 1)[1].strip() for x in (ROOT / 'ci/pins/compose.yml').read_text().splitlines() if 'image: python:' in x))
    args = ap.parse_args()
    tag = 'pb-policy-' + uuid.uuid4().hex[:10]
    vpn, peer, browser, existing, no_mount, no_mount_browser = [tag + '-' + x for x in ('vpn', 'peer', 'browser', 'existing', 'no-mount', 'no-mount-browser')]
    containers, networks = [], []
    fixture = str(ROOT / 'ci/policy-fixture.py')
    passed = 0
    def passed_check(message):
        nonlocal passed
        passed += 1
        print('PASS ' + message, flush=True)
    def command(ns, binary, *tokens):
        return run('exec', ns, binary, *tokens).stdout
    def check_policy(expected=0, target=vpn, consumer=browser):
        result = subprocess.run(['python3', str(ROOT / 'check-local-app-policy.py'), '--vpn', target, '--browser', consumer, '--policy-file', str(rules)], text=True, capture_output=True, timeout=120)
        assert result.returncode == expected, (result.returncode, expected, result.stdout, result.stderr)
        if expected:
            assert 'PASS ' not in result.stdout, result.stdout
        return result.stdout
    def launch(name, *options):
        containers.append(name)
        return run('run', '-d', '--name', name, '--pull', 'never', *options).stdout.strip()
    def py_options(ns):
        return ['--network', 'container:' + ns, '--user', '1000:1000', '--cap-drop', 'ALL', '--read-only', '--security-opt', 'no-new-privileges', '-v', fixture + ':/fixture.py:ro']
    def probe(ns, host, port, marker, mode='request', allowed=True):
        result = run('run', '--rm', '--pull', 'never', *py_options(ns), args.python_image, 'python', '/fixture.py', mode, host, str(port), marker, check=False, timeout=15)
        seen = records(result.stdout)
        assert any(x.get('marker') == marker and (x.get('attempt') or x.get('connect_attempt')) for x in seen), result.stdout
        if allowed:
            assert result.returncode == 0 and any(x.get('status') == 200 for x in seen), (result.stdout, result.stderr)
        else:
            assert result.returncode == 1 and any(x.get('network_error') for x in seen), (result.stdout, result.stderr)
        return seen
    def counter(family):
        binary = 'iptables' if family == 4 else 'ip6tables'
        target = '10.0.0.0/8' if family == 4 else 'fc00::/7'
        lines = command(vpn, binary, '-nvxL', 'OUTPUT').splitlines()
        matches = [x for x in lines if 'REJECT' in x and target in x]
        assert len(matches) == 1, lines
        return int(matches[0].split()[0])
    def apply(text, target=vpn):
        # Execute each iptables instruction directly; never shell-evaluate a rules file.
        for line in text.splitlines():
            if line.startswith(('iptables ', 'ip6tables ')):
                command(target, *shlex.split(line))
    try:
        with tempfile.TemporaryDirectory(prefix=tag) as tmp:
            tmp = Path(tmp); rules = tmp / 'rules.txt'; signals = tmp / 'signals'; signals.mkdir()
            full = (ROOT / 'local-app-post-rules.txt').read_text(); rules.write_text(full)
            # New internal networks only; Docker rejects overlaps rather than reusing any live network.
            n = random.randrange(100, 240)
            private, outer, tunnel = f'10.253.{n}', f'198.19.{n}', f'198.18.{n}'
            ipv6 = f'fd42:{random.randrange(0x1000, 0xffff):x}'
            for label, subnet in [('private', private), ('outer', outer), ('tunnel', tunnel)]:
                name = tag + '-' + label
                options = ['--internal', '--subnet', subnet + '.0/24']
                if label == 'private': options += ['--ipv6', '--subnet', ipv6 + '::/64']
                run('network', 'create', *options, name); networks.append(name)
            fw_options = ['--network', networks[0], '--ip', private + '.2', '--ip6', ipv6 + '::2', '--cap-add', 'NET_ADMIN', '--sysctl', 'net.ipv6.conf.all.disable_ipv6=0', '--entrypoint', 'sh']
            # Mount options precede image; no source .env or production credentials.
            launch(vpn, '-v', str(rules) + ':/iptables/post-rules.txt:ro', *fw_options, args.firewall_image, '-c', 'sleep 1800')
            for net, addr in [(networks[1], outer + '.2'), (networks[2], tunnel + '.2')]: run('network', 'connect', '--ip', addr, net, vpn)
            command(vpn, 'ip', 'link', 'set', 'eth2', 'name', 'tun0')
            launch(peer, '--network', networks[0], '--ip', private + '.3', '--ip6', ipv6 + '::3', '--user', '1000:1000', '--read-only', '--cap-drop', 'ALL', '-v', fixture + ':/fixture.py:ro', args.python_image, 'python', '/fixture.py', 'server', '45901')
            for net, addr in [(networks[1], outer + '.3'), (networks[2], tunnel + '.3')]: run('network', 'connect', '--ip', addr, net, peer)
            launch(browser, *py_options(vpn), args.python_image, 'python', '/fixture.py', 'server', '45902')
            time.sleep(1)
            for binary in ['iptables', 'ip6tables']:
                command(vpn, binary, '-P', 'OUTPUT', 'DROP')
                command(vpn, binary, '-A', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT')
                command(vpn, binary, '-A', 'OUTPUT', '-m', 'conntrack', '--ctstate', 'RELATED,ESTABLISHED', '-j', 'ACCEPT')
                command(vpn, binary, '-A', 'OUTPUT', '-o', 'eth0', '-j', 'ACCEPT')
                command(vpn, binary, '-A', 'OUTPUT', '-o', 'tun0', '-j', 'ACCEPT')
            command(vpn, 'iptables', '-A', 'OUTPUT', '-d', outer + '.3', '-p', 'udp', '--dport', '51820', '-j', 'ACCEPT')
            for host in [private + '.3', ipv6 + '::3']: probe(vpn, host, 45901, 'before-' + host)
            check_policy(1); passed_check('unprotected fixture connects in IPv4/IPv6 but cannot receive policy PASS')
            launch(existing, *py_options(vpn), '-v', str(signals) + ':/signals:ro', args.python_image, 'python', '/fixture.py', 'existing', private + '.3', '45901', 'existing-denied')
            for _ in range(60):
                if any(x.get('ready') for x in records(run('logs', existing).stdout)): break
                time.sleep(.1)
            else: raise AssertionError('existing-session positive control did not execute')
            apply(full); check_policy(); passed_check('valid read-only policy and exact kernel/order assertion')
            before = counter(4); (signals / 'go').write_text('go')
            result = run('wait', existing, timeout=15); assert result.stdout.strip() == '1', run('logs', existing).stdout
            log = records(run('logs', existing).stdout)
            assert any(x.get('attempt') and x.get('marker') == 'existing-denied' for x in log)
            assert counter(4) > before
            passed_check('already-established outgoing operation executed and hit matching REJECT counter')
            for family, host in [(4, private + '.3'), (6, ipv6 + '::3')]:
                before = counter(family); probe(vpn, host, 45901, 'denied-v' + str(family), allowed=False); assert counter(family) > before
                passed_check('IPv%s denied operation executed; matching kernel REJECT counter increased' % family)
            for host in [private + '.2', ipv6 + '::2']: probe(peer, host, 45902, 'incoming-' + host)
            for host in ['127.0.0.1', '::1']: probe(vpn, host, 45902, 'loopback-' + host)
            probe(vpn, outer + '.3', 51820, 'transport', mode='udp')
            probe(vpn, tunnel + '.3', 45901, 'vpn-interface')
            passed_check('IPv4/IPv6 incoming replies and loopback, pinned UDP transport and synthetic tun0 route work')
            peer_log = records(run('logs', peer).stdout)
            observed = {x.get('marker') for x in peer_log if x.get('observed')}
            assert {'existing-before', 'transport', 'vpn-interface'} <= observed
            assert not {'existing-denied', 'denied-v4', 'denied-v6'} & observed
            passed_check('working server observations attribute controls and absence of rejected markers')
            for label, content in [('empty', ''), ('partial', '\n'.join(x for x in full.splitlines() if not x.startswith('ip6tables'))), ('malformed', 'iptables "')]:
                rules.write_text(content); check_policy(1); rules.write_text(full); check_policy(); passed_check(label + ' policy file cannot receive PASS even with existing kernel protection')
            command(vpn, 'iptables', '-I', 'OUTPUT', '1', '-m', 'conntrack', '--ctstate', 'RELATED,ESTABLISHED', '-j', 'ACCEPT')
            check_policy(1); command(vpn, 'iptables', '-D', 'OUTPUT', '1'); check_policy(); passed_check('incorrect established-rule order fails')
            command(vpn, 'ip6tables', '-F', 'OUTPUT'); check_policy(1)
            command(vpn, 'ip6tables', '-A', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT'); command(vpn, 'ip6tables', '-A', 'OUTPUT', '-m', 'conntrack', '--ctstate', 'RELATED,ESTABLISHED', '-j', 'ACCEPT')
            apply('\n'.join(x for x in full.splitlines() if x.startswith('ip6tables'))); check_policy(); passed_check('broken IPv6 protection fails and restored policy passes')
            # A second credential-free namespace has loaded rules but no policy mount.
            launch(no_mount, '--network', networks[0], '--cap-add', 'NET_ADMIN', '--sysctl', 'net.ipv6.conf.all.disable_ipv6=0', '--entrypoint', 'sh', args.firewall_image, '-c', 'sleep 1800')
            launch(no_mount_browser, *py_options(no_mount), args.python_image, 'python', '/fixture.py', 'server', '45902')
            apply(full, target=no_mount); check_policy(1, no_mount, no_mount_browser); passed_check('removed bind mount cannot receive PASS even with valid rejects present')
            rules.unlink(); check_policy(1); passed_check('missing host policy file cannot receive PASS')
            print('PASS isolated network suite: %d controls/mutation groups; synthetic tun0/transport is not a real VPN or boot test' % passed, flush=True)
    finally:
        for name in reversed(containers): run('rm', '-f', name, check=False)
        for name in reversed(networks): run('network', 'rm', name, check=False)


if __name__ == '__main__':
    main()
