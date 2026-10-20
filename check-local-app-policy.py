#!/usr/bin/env python3
"""Trusted host-side policy assertion. 0 PASS, 1 observed defect, 3 missing evidence.

Never executes policy text or grants privileges to the browser. Expected policy is
fixed here, independently of the potentially missing/broken mounted rules file.
"""
import argparse
import ipaddress
import json
from pathlib import Path
import shlex
import subprocess
import sys

NETWORKS = {4: ('0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
                '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16', '224.0.0.0/4'),
            6: ('fc00::/7', 'fe80::/10')}


class Defect(Exception):
    """Observed missing or broken protection."""


class Unavailable(Exception):
    """The observation did not execute or could not be read."""


def command(*args):
    try:
        result = subprocess.run(['docker', *args], text=True, capture_output=True, timeout=20)
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise Unavailable('Docker observation unavailable') from exc
    if result.returncode:
        raise Unavailable('Docker observation failed (exit %s)' % result.returncode)
    return result.stdout


def reject(tokens, family):
    """Accept only the supported original-direction, non-loopback reject form."""
    t = list(tokens)
    if len(t) >= 2 and t[-2] == '--reject-with':
        wanted = 'icmp-port-unreachable' if family == 4 else 'icmp6-port-unreachable'
        if t[-1] != wanted:
            raise Defect('wrong reject address family/type')
        t = t[:-2]
    # iptables -S canonicalizes the argument order; policy source has ! -o first.
    if len(t) != 11:
        raise Defect('unexpected reject rule shape')
    if t[:2] == ['!', '-o']:
        # ! -o lo -d NET ... -> -d NET ! -o lo ...
        t = t[3:5] + t[:3] + t[5:]
    if t[:1] != ['-d'] or t[2:] != ['!', '-o', 'lo', '-m', 'conntrack', '--ctdir', 'ORIGINAL', '-j', 'REJECT']:
        raise Defect('rule does not reject original-direction non-loopback traffic')
    try:
        network = ipaddress.ip_network(t[1])
    except ValueError as exc:
        raise Defect('invalid rule address') from exc
    if network.version != family:
        raise Defect('wrong rule address family')
    return str(network)


def check_file(content):
    found = {4: [], 6: []}
    for line in content.splitlines():
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError as exc:
            raise Defect('malformed policy file') from exc
        if not tokens:
            continue
        if tokens[0] not in ('iptables', 'ip6tables') or tokens[1:4] != ['-I', 'OUTPUT', '1']:
            raise Defect('unexpected command in policy file')
        family = 4 if tokens[0] == 'iptables' else 6
        found[family].append(reject(tokens[4:], family))
    for family, networks in NETWORKS.items():
        if sorted(found[family]) != sorted(networks):
            raise Defect('missing/duplicate/extra IPv%s policy file rules' % family)


def check_kernel(text, family):
    try:
        lines = [shlex.split(line) for line in text.splitlines() if line.strip()]
    except ValueError as exc:
        raise Unavailable('cannot parse kernel rules') from exc
    if not lines or lines[0] != ['-P', 'OUTPUT', 'DROP']:
        raise Defect('IPv%s OUTPUT default is not DROP' % family)
    rules = lines[1:]
    count = len(NETWORKS[family])
    if len(rules) < count + 2 or any(x[:2] != ['-A', 'OUTPUT'] for x in rules):
        raise Defect('IPv%s required OUTPUT rules absent' % family)
    actual = [reject(x[2:], family) for x in rules[:count]]
    if sorted(actual) != sorted(NETWORKS[family]):
        raise Defect('IPv%s rejects missing or behind another rule' % family)
    later = [x[2:] for x in rules[count:]]
    if ['-o', 'lo', '-j', 'ACCEPT'] not in later:
        raise Defect('IPv%s loopback control absent' % family)
    if not any(x in later for x in (
            ['-m', 'conntrack', '--ctstate', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'],
            ['-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])):
        raise Defect('IPv%s incoming reply control absent' % family)


def inspect(name):
    # Selected metadata only: no complete Config/Env, credentials or profile.
    fmt = '{"id":{{json .Id}},"running":{{json .State.Running}},"network":{{json .HostConfig.NetworkMode}},"privileged":{{json .HostConfig.Privileged}},"caps":{{json .HostConfig.CapAdd}},"mounts":{{json .Mounts}}}'
    try:
        return json.loads(command('inspect', '--format', fmt, name))
    except (ValueError, TypeError) as exc:
        raise Unavailable('container metadata unreadable') from exc


def verify(vpn_name, browser_name, policy):
    vpn, browser = inspect(vpn_name), inspect(browser_name)
    if not vpn['running'] or not browser['running']:
        raise Unavailable('VPN/browser not running')
    if browser['network'] not in ('container:' + vpn['id'], 'container:' + vpn_name):
        raise Defect('browser does not share the inspected VPN namespace')
    caps = {x.upper().removeprefix('CAP_') for x in (browser['caps'] or [])}
    if browser['privileged'] or caps.intersection({'NET_ADMIN', 'ALL'}):
        raise Defect('browser has forbidden firewall privileges')
    mounts = [x for x in vpn['mounts'] if x['Destination'] == '/iptables/post-rules.txt']
    if len(mounts) != 1 or mounts[0]['Type'] != 'bind' or mounts[0]['RW']:
        raise Defect('required read-only policy bind mount absent or writable')
    policy = Path(policy).resolve()
    if Path(mounts[0]['Source']).resolve() != policy:
        raise Defect('policy bind source differs from expected host file')
    if not policy.is_file():
        raise Defect('host policy file missing/not regular')
    try:
        content = policy.read_text()
    except (OSError, UnicodeError) as exc:
        raise Unavailable('host policy file unreadable') from exc
    check_file(content)
    mounted = command('exec', vpn_name, 'cat', '/iptables/post-rules.txt')
    if content != mounted:
        raise Defect('mounted policy differs from expected host file')
    for family, binary in ((4, 'iptables'), (6, 'ip6tables')):
        check_kernel(command('exec', vpn_name, binary, '-S', 'OUTPUT'), family)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vpn', default='gluetun-proton')
    parser.add_argument('--browser', default='private-firefox')
    parser.add_argument('--policy-file', type=Path, default=Path(__file__).resolve().parent / 'local-app-post-rules.txt')
    args = parser.parse_args()
    try:
        verify(args.vpn, args.browser, args.policy_file)
    except Defect as exc:
        print('FAIL  local-app policy: ' + str(exc))
        return 1
    except (Unavailable, KeyError, TypeError, OSError, UnicodeError, ValueError) as exc:
        detail = str(exc) if isinstance(exc, Unavailable) else 'observation schema incomplete'
        print('INCOMPLETE  local-app policy: ' + detail)
        return 3
    print('PASS  local-app policy: read-only source, shared namespace and ordered IPv4/IPv6 kernel rejects verified')
    return 0


if __name__ == '__main__':
    sys.exit(main())
