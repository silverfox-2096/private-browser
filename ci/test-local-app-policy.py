#!/usr/bin/env python3
"""Mutation controls: healthy metadata/browser verdicts cannot mask policy defects."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('policy', ROOT / 'check-local-app-policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / 'rules.txt'
        self.content = (ROOT / 'local-app-post-rules.txt').read_text()
        self.file.write_text(self.content)
        self.vpn = {'id': 'vpn-id', 'running': True, 'health': 'healthy',
                    'network': 'bridge', 'privileged': False, 'caps': [],
                    'mounts': [{'Destination': '/iptables/post-rules.txt', 'Type': 'bind',
                                'RW': False, 'Source': str(self.file)}]}
        self.browser = {'id': 'browser-id', 'running': True, 'network': 'container:vpn-id',
                        'privileged': False, 'caps': [], 'mounts': [],
                        'seven_browser_checks': ['PASS'] * 7}
        self.kernel = {}
        for family, binary in ((4, 'iptables'), (6, 'ip6tables')):
            lines = []
            for line in self.content.splitlines():
                if line.startswith(binary + ' '):
                    tail = line.split(' -I OUTPUT 1 ', 1)[1]
                    tokens = tail.split()
                    # Model the actual canonical -S ordering and default reject type.
                    tail = ' '.join(tokens[3:5] + tokens[:3] + tokens[5:])
                    lines.insert(0, '-A OUTPUT ' + tail + ' --reject-with ' +
                                 ('icmp-port-unreachable' if family == 4 else 'icmp6-port-unreachable'))
            self.kernel[binary] = '\n'.join(['-P OUTPUT DROP'] + lines + [
                '-A OUTPUT -o lo -j ACCEPT',
                '-A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT',
                '-A OUTPUT -o tun0 -j ACCEPT']) + '\n'

    def observed(self, *args):
        if args[0] == 'inspect':
            return json.dumps(self.vpn if args[-1] == 'vpn' else self.browser)
        if args[2] == 'cat':
            return self.file.read_text()
        return self.kernel[args[2]]

    def verify(self):
        with patch.object(policy, 'command', self.observed):
            policy.verify('vpn', 'browser', self.file)

    def test_valid_policy(self):
        self.verify()

    def test_observed_regressions_cannot_pass_healthy_seven_of_seven(self):
        mutations = {
            'removed mount': lambda: self.vpn.update(mounts=[]),
            'writable mount': lambda: self.vpn['mounts'][0].update(RW=True),
            'wrong source': lambda: self.vpn['mounts'][0].update(Source='/different'),
            'missing file': lambda: self.file.unlink(),
            'empty file': lambda: self.file.write_text(''),
            'partial file': lambda: self.file.write_text(self.content.replace('ip6tables -I OUTPUT 1 ! -o lo -d fc00::/7 -m conntrack --ctdir ORIGINAL -j REJECT', '')),
            'malformed file': lambda: self.file.write_text('iptables "'),
            'wrong namespace': lambda: self.browser.update(network='bridge'),
            'browser firewall capability': lambda: self.browser.update(caps=['CAP_NET_ADMIN']),
            'browser all capabilities': lambda: self.browser.update(caps=['ALL']),
            'browser privileged': lambda: self.browser.update(privileged=True),
            'IPv4 missing': lambda: self.kernel.update(iptables='-P OUTPUT DROP\n'),
            'IPv6 missing': lambda: self.kernel.update(ip6tables='-P OUTPUT DROP\n'),
            'wrong IPv6 reject type': lambda: self.kernel.update(ip6tables=self.kernel['ip6tables'].replace('icmp6-port-unreachable', 'icmp-port-unreachable')),
            'reply rather than original': lambda: self.kernel.update(iptables=self.kernel['iptables'].replace('--ctdir ORIGINAL', '--ctdir REPLY')),
            'accept before rejects': lambda: self.kernel.update(iptables=self.kernel['iptables'].replace('-P OUTPUT DROP', '-P OUTPUT DROP\n-A OUTPUT -j ACCEPT')),
            'default accept': lambda: self.kernel.update(iptables=self.kernel['iptables'].replace('-P OUTPUT DROP', '-P OUTPUT ACCEPT')),
            'no loopback allowance': lambda: self.kernel.update(ip6tables=self.kernel['ip6tables'].replace('-A OUTPUT -o lo -j ACCEPT\n', '')),
            'no reply allowance': lambda: self.kernel.update(iptables=self.kernel['iptables'].replace('-A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT\n', '')),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self.setUp()
                mutate()
                self.assertEqual(self.vpn['health'], 'healthy')
                self.assertEqual(self.browser['seven_browser_checks'], ['PASS'] * 7)
                with self.assertRaises(policy.Defect):
                    self.verify()

    def test_no_pass_when_docker_observation_fails(self):
        for failure in (OSError('missing'), subprocess.TimeoutExpired('docker', 20)):
            with self.subTest(failure=failure), patch.object(subprocess, 'run', side_effect=failure):
                with self.assertRaises(policy.Unavailable):
                    policy.command('exec', 'vpn', 'ip6tables', '-S', 'OUTPUT')
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', '')):
            with self.assertRaises(policy.Unavailable):
                policy.command('exec', 'vpn', 'iptables', '-S', 'OUTPUT')

    def test_mount_content_mismatch(self):
        original = self.observed
        def changed(*args):
            return 'different' if args[0] == 'exec' and args[2] == 'cat' else original(*args)
        with patch.object(policy, 'command', changed), self.assertRaises(policy.Defect):
            policy.verify('vpn', 'browser', self.file)


if __name__ == '__main__':
    unittest.main(verbosity=2)
