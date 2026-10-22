#!/usr/bin/env python3
"""Isolated release install/update/recovery controls. No real Docker or VPN.

Bundles use synthetic receipts and nonexistent image digests. Real filesystem
transactions and actual packager/source-controller checks execute in temp dirs.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class ReleaseMode(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base / 'installation'; self.root.mkdir()
        self.files = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
        self.files = sorted(set(self.files) | {'scripts/release_mode.py'})
        for name in self.files:
            source, target = ROOT / name, self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        self.api = load('onboard_fixture', self.root / 'scripts' / 'onboard.py')
        mode = load('mode_fixture', self.root / 'scripts' / 'release_mode.py')
        self.release = mode.Releases(self.api)
        self.calls = []; self.optional = False; self.running = True
        self.sockets = {'/proc/net/tcp': 'sl local_address rem_address st\n0: 00000000:16A8 00000000:0000 0A\n',
                        '/proc/net/tcp6': 'sl local_address remote_address st\n0: 00000000000000000000000000000000:16A8 00000000000000000000000000000000:0000 0A\n'}
        self.network_results = []; self.policy_results = []; self.compose_failures = []
        self.http = None; self.after_status = '302'; self.owner_error = False; self.pull_error = False
        self.old_bundle = self.bundle('v0.0.0-rc.1', ('a', 'b'))
        self.new_bundle = self.bundle('v0.0.0-rc.2', ('c', 'd'))
        self.old = self.release.stage(self.old_bundle)
        self.current = self.ids(self.old['active'])
        self.cached = set(self.old['active']['manifest']['images'].values())
        self.api.create_private(self.root / '.env', 'synthetic credential bytes: preserve me\n')
        self.api.create_private(self.root / 'webauth-htpasswd', 'synthetic login bytes: preserve me\n')
        self.addCleanup(patch.stopall)
        patch.object(self.api, 'docker', side_effect=self.docker).start()
        patch.object(self.api, 'run', side_effect=self.command).start()
        patch.object(self.api, 'compose', side_effect=self.compose).start()
        patch.object(self.api, 'owned_containers', side_effect=self.owned).start()
        patch.object(self.api, 'lifecycle', side_effect=self.lifecycle).start()
        patch.object(self.api, 'compose_environment', return_value={}).start()

    def bundle(self, version, letters):
        package = self.release.package
        source = 'e' * 40
        images = {service: 'ghcr.io/silverfox-2096/private-browser-' + service + '@sha256:' + letter * 64
                  for service, letter in zip(package.SERVICES, letters)}
        manifest = {'schema': 1, 'version': version, 'source': source, 'platform': 'linux/amd64', 'created': '2026-10-22T06:00:00Z', 'images': images,
                    'provenance': {service: {'source': source, 'image': reference, 'sha256': 'f' * 64} for service, reference in images.items()},
                    'measurements': {'install_seconds': 1, 'peak_memory_mib': 1, 'disk_mib': 1}}
        evidence = {'schema': 1, 'source': source, 'images': images,
                    'gates': {name: {'status': 'PASS', 'scope': 'actual-runtime' if name in package.RUNTIME_GATES else 'exact-artifact', 'source': source, 'images': images, 'report_sha256': 'f' * 64} for name in package.GATES}}
        manifest_path, evidence_path = self.base / 'fixture-manifest.json', self.base / 'fixture-evidence.json'
        manifest_path.write_bytes(package.normalized(manifest)); evidence_path.write_bytes(package.normalized(evidence))
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as archive:
            for name in self.files:
                data = (self.root / name).read_bytes()
                member = tarfile.TarInfo('private-browser-' + version + '/' + name); member.size = len(data); member.mode = (self.root / name).stat().st_mode & 0o777
                archive.addfile(member, io.BytesIO(data))
        def git(*args):
            if args[0] == 'rev-parse': return (source + '\n').encode()
            if args[0] == 'archive': return buf.getvalue()
            if args[0] == 'show': return (self.root / 'docker-compose.yml').read_bytes()
            raise AssertionError(args)
        output = self.base / version
        with patch.object(package, 'git', side_effect=git): package.prepare(manifest_path, evidence_path, output)
        return output

    @staticmethod
    def ids(entry):
        return {service: 'sha256:' + hashlib.sha256(reference.encode()).hexdigest() for service, reference in entry['manifest']['images'].items()}

    def owned(self, expected_recipe=None):
        self.calls.append(('ownership', expected_recipe))
        if self.owner_error: raise self.api.Problem('foreign containers', 2)
        return ['gluetun-proton', 'private-firefox'] + (['creepjs-server'] if self.optional else [])

    def docker(self, *args, **kwargs):
        self.calls.append(('docker', args))
        if args[:2] == ('image', 'inspect'):
            if args[-1] not in self.cached: raise self.api.Problem('image not cached', 3)
            return 'sha256:' + hashlib.sha256(args[-1].encode()).hexdigest() + ' linux/amd64\n'
        if args[0] == 'inspect':
            if args[2] == '{{.Image}}': return self.current['gluetun' if args[-1] == 'gluetun-proton' else 'firefox'] + '\n'
            if args[2] == '{{.State.Running}}': return ('true' if self.running else 'false') + '\n'
            if args[2] == '{{.State.Health.Status}}': return 'healthy\n'
        if args[0] == 'exec':
            if args[2] in ('test', 'grep'): return ''
            if args[2] == 'cat': return self.sockets[args[3]]
        raise AssertionError(args)

    def command(self, args, **kwargs):
        self.calls.append(('run', tuple(args), kwargs.get('managed', False)))
        if args[:2] == ['docker', 'pull']:
            if not self.pull_error: self.cached.add(args[-1])
            return subprocess.CompletedProcess(args, 1 if self.pull_error else 0, '', '')
        if args[0] == 'curl': return subprocess.CompletedProcess(args, 0, self.http or ('503' if (self.root / 'maintenance' / 'active').exists() else self.after_status), '')
        if str(args[-1]).endswith('check-local-app-policy.py'):
            rc = self.policy_results.pop(0) if self.policy_results else 0
            return subprocess.CompletedProcess(args, rc, '', '')
        if args[0] == 'bash' and str(args[-1]).endswith('launch.sh'):
            self.calls.append(('launch-env', kwargs['env']))
            return subprocess.CompletedProcess(args, 0, '', '')
        raise AssertionError(args)

    def compose(self, *args, **kwargs):
        self.calls.append(('compose', args))
        if self.compose_failures:
            rc = self.compose_failures.pop(0)
            if rc: raise self.api.Problem('compose fixture failure', rc)
        if 'down' in args: self.running = False
        if 'up' in args:
            self.running = True
            self.current = self.ids(self.release.state()['active'])
        return subprocess.CompletedProcess(args, 0, '', '')

    def lifecycle(self, script):
        self.calls.append(('network', dict(self.current)))
        return self.network_results.pop(0) if self.network_results else 0

    def perform(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()): return self.release.update(self.new_bundle, **kwargs)

    def test_stage_private_pinned_recipe_and_rerun(self):
        before = (self.root / '.pb-release.json').read_bytes()
        self.assertEqual(self.release.stage(self.old_bundle), self.old)
        self.assertEqual((self.root / '.pb-release.json').read_bytes(), before)
        self.assertEqual((self.root / '.pb-release.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.api.compose_path(), self.root / 'docker-compose.release.yml')
        with self.assertRaises(self.api.Problem): self.release.stage(self.new_bundle)

    def test_successful_update_preserves_credentials_and_previous(self):
        private = {name: (self.root / name).read_bytes() for name in ('.env', 'webauth-htpasswd')}
        self.assertEqual(self.perform(), 0)
        state = self.release.state()
        self.assertEqual(state['previous'], self.old['active'])
        self.assertEqual(state['active']['manifest']['version'], 'v0.0.0-rc.2')
        for name, data in private.items(): self.assertEqual((self.root / name).read_bytes(), data)
        self.assertFalse((self.root / 'maintenance' / 'active').exists())
        self.assertFalse((self.root / '.pb-release-transaction.json').exists())
        self.assertEqual([call[0] for call in self.calls].count('network'), 1)
        self.assertTrue(all(call[2] for call in self.calls if call[0] == 'run' and call[1][:2] == ('docker', 'pull')))

    def test_failure_and_incomplete_rollback_preserve_original_verdict(self):
        for rc in (1, 3, 130):
            with self.subTest(rc=rc):
                self.network_results = [rc, 0]
                with self.assertRaises(self.api.Problem) as caught: self.perform()
                self.assertEqual(caught.exception.code, rc)
                self.assertEqual(self.release.state(), self.old)
                self.assertEqual(self.current, self.ids(self.old['active']))
                self.assertFalse((self.root / 'maintenance' / 'active').exists())
                self.assertFalse((self.root / '.pb-release-transaction.json').exists())

    def test_failed_recovery_retains_gate_and_transaction(self):
        self.network_results = [1, 3]
        with self.assertRaises(self.api.Problem) as caught: self.perform()
        self.assertEqual(caught.exception.code, 3)
        self.assertIn('INCOMPLETE', str(caught.exception))
        self.assertTrue((self.root / 'maintenance' / 'active').exists())
        self.assertTrue((self.root / '.pb-release-transaction.json').exists())

    def test_explicit_recovery_after_failed_rollback(self):
        self.network_results = [1, 3]
        with self.assertRaises(self.api.Problem): self.perform()
        self.network_results = [0]
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(self.release.recover(), 0)
        self.assertEqual(self.release.state(), self.old)
        self.assertFalse((self.root / '.pb-release-transaction.json').exists())
        self.assertIn(('ownership', self.root / 'docker-compose.release.yml'), self.calls)

    def test_explicit_rollback_to_previous_release(self):
        self.perform()
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(self.release.recover(), 0)
        self.assertEqual(self.release.state()['active'], self.old['active'])
        self.assertEqual(self.current, self.ids(self.old['active']))

    def test_existing_viewer_prevents_transition(self):
        self.sockets['/proc/net/tcp6'] += '1: 00000000000000000000000000000000:16A8 00000000000000000000000000000000:1234 01\n'
        with self.assertRaises(self.api.Problem) as caught: self.perform()
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(any(call[0] == 'compose' for call in self.calls))
        self.assertFalse((self.root / 'maintenance' / 'active').exists())
        self.assertEqual(self.release.state(), self.old)

    def test_unreadable_tcp4_or_tcp6_never_counts_as_zero(self):
        for path in self.sockets:
            previous = self.sockets[path]; self.sockets[path] = ''
            with self.assertRaises(self.api.Problem): self.perform()
            self.assertFalse(any(call[0] == 'compose' for call in self.calls))
            self.assertFalse((self.root / 'maintenance' / 'active').exists())
            self.sockets[path] = previous

    def test_gate_must_return_503_before_viewer_read(self):
        self.http = '302'
        with self.assertRaises(self.api.Problem): self.perform()
        self.assertFalse(any(call[0] == 'docker' and call[1][:3] == ('exec', 'private-firefox', 'cat') for call in self.calls))
        self.assertFalse(any(call[0] == 'compose' for call in self.calls))

    def test_foreign_containers_never_trigger_pull_or_gate(self):
        self.owner_error = True
        with self.assertRaises(self.api.Problem): self.perform()
        self.assertFalse(any(call[0] in ('compose', 'run') for call in self.calls))
        self.assertFalse((self.root / 'maintenance' / 'active').exists())

    def test_download_failure_does_not_touch_services_or_gate(self):
        self.pull_error = True
        with self.assertRaises(self.api.Problem): self.perform()
        self.assertFalse(any(call[0] == 'compose' for call in self.calls))
        self.assertFalse((self.root / 'maintenance' / 'active').exists())
        self.assertEqual(self.release.state(), self.old)

    def test_policy_failure_requires_verified_rollback(self):
        self.policy_results = [3, 0]
        with self.assertRaises(self.api.Problem) as caught: self.perform()
        self.assertEqual(caught.exception.code, 3)
        self.assertEqual(self.release.state(), self.old)
        self.assertEqual([call[0] for call in self.calls].count('network'), 1)

    def test_optional_service_is_restored_on_update_and_rollback(self):
        self.optional = True
        self.network_results = [1, 0]
        with self.assertRaises(self.api.Problem): self.perform()
        ups = [call[1] for call in self.calls if call[0] == 'compose' and 'up' in call[1]]
        self.assertEqual(len(ups), 2)
        self.assertTrue(all('creepjs' in args and '--profile' in args for args in ups))

    def test_changed_controller_and_tampered_bundle_refused(self):
        (self.root / 'startup-guard.sh').write_text('changed')
        with self.assertRaises(self.api.Problem): self.perform()
        self.assertFalse(any(call[0] in ('compose', 'run') for call in self.calls))

    def test_tampered_release_recipe_never_falls_back_to_source(self):
        (self.root / 'docker-compose.release.yml').write_text('changed')
        with self.assertRaises(self.api.Problem): self.api.compose_path()

    def test_recipe_only_interruption_is_resumable(self):
        (self.root / '.pb-release.json').unlink()
        with self.assertRaises(self.api.Problem): self.api.compose_path()
        self.assertEqual(self.release.stage(self.old_bundle), self.old)

    def test_gate_ownership_change_is_not_cleared(self):
        self.network_results = [1]
        def failed(ids):
            gate = self.root / 'maintenance' / 'active'
            backup = self.root / 'old-gate'; gate.rename(backup)
            self.api.create_private(gate, '')
            raise self.api.Problem('fixture failure', 1)
        with patch.object(self.release, 'readiness', side_effect=failed), self.assertRaises(self.api.Problem): self.perform()
        self.assertTrue((self.root / 'maintenance' / 'active').exists())
        self.assertTrue((self.root / '.pb-release-transaction.json').exists())

    def test_failed_compose_up_rolls_back(self):
        self.compose_failures = [0, 1, 0, 0]
        with self.assertRaises(self.api.Problem): self.perform()
        self.assertEqual(self.release.state(), self.old)
        self.assertEqual(self.current, self.ids(self.old['active']))

    def test_recovery_refuses_malformed_journal_and_foreign_owner(self):
        self.network_results = [1, 3]
        with self.assertRaises(self.api.Problem): self.perform()
        self.owner_error = True
        before = len([call for call in self.calls if call[0] == 'compose'])
        with self.assertRaises(self.api.Problem): self.release.recover()
        self.assertEqual(len([call for call in self.calls if call[0] == 'compose']), before)
        self.owner_error = False
        self.release.write('.pb-release-transaction.json', '{"schema":1}')
        with self.assertRaises(self.api.Problem): self.release.recover()
        self.assertTrue((self.root / 'maintenance' / 'active').exists())

    def test_start_uses_pins_without_build_and_opens_after_identity_check(self):
        with patch.object(self.api, 'environment', return_value={'fixture': 'present'}), patch.object(self.api, 'login_exists', return_value=True), patch.object(self.api, 'open_browser', side_effect=lambda: self.calls.append(('open',))), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.api.start(), 0)
        self.assertFalse(any(call[0] == 'compose' and 'build' in call[1] for call in self.calls))
        self.assertEqual(self.calls[-1], ('open',))
        launch = next(call[1] for call in self.calls if call[0] == 'launch-env')
        self.assertEqual(launch['PB_NO_OPEN'], '1')
        self.assertEqual(launch['COMPOSE_FILE'], str(self.root / 'docker-compose.release.yml'))
        self.assertFalse(any(call[0] == 'run' and call[1][:2] == ('docker', 'pull') for call in self.calls))

    def test_wrong_running_image_never_opens_browser(self):
        self.current['firefox'] = 'sha256:' + '0' * 64
        with patch.object(self.api, 'environment', return_value={'fixture': 'present'}), patch.object(self.api, 'login_exists', return_value=True), patch.object(self.api, 'open_browser') as opened, contextlib.redirect_stdout(io.StringIO()), self.assertRaises(self.api.Problem): self.api.start()
        opened.assert_not_called()

    def test_cli_update_routes_release_and_refuses_implicit_source_rebuild(self):
        with patch.object(self.api, 'prerequisites'), patch.object(self.api, 'environment', return_value={'fixture': 'present'}), patch.object(self.api, 'login_exists', return_value=True), patch.object(self.api, 'confirm', return_value=True), patch.object(self.api.sys, 'argv', ['pb', 'update']), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.api.main(), 2)
        self.assertFalse(any(call[0] == 'network' or call[0] == 'compose' for call in self.calls))
        with patch.object(self.api, 'prerequisites'), patch.object(self.api, 'environment', return_value={'fixture': 'present'}), patch.object(self.api, 'login_exists', return_value=True), patch.object(self.api, 'confirm', return_value=True), patch.object(self.api.sys, 'argv', ['pb', 'update', '--release', str(self.new_bundle)]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.api.main(), 0)
        self.assertEqual(self.release.state()['active']['manifest']['version'], 'v0.0.0-rc.2')

    def test_pending_transaction_blocks_start_before_observations(self):
        self.api.create_private(self.root / '.pb-release-transaction.json', '{}')
        with patch.object(self.api.sys, 'argv', ['pb', 'start']), contextlib.redirect_stderr(io.StringIO()): self.assertEqual(self.api.main(), 2)
        self.assertEqual(self.calls, [])

    def test_recovery_when_failed_transition_left_browser_stopped(self):
        self.network_results = [1, 3]
        with self.assertRaises(self.api.Problem): self.perform()
        self.running = False
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(self.release.recover(), 0)
        self.assertTrue(self.running)
        self.assertEqual(self.release.state(), self.old)

    def test_recovery_after_verified_update_crashed_during_gate_cleanup(self):
        original = self.release.release_gate
        def cleanup_failure(token):
            original(token)
            raise OSError('synthetic cleanup interruption')
        with patch.object(self.release, 'release_gate', side_effect=cleanup_failure), self.assertRaises(OSError): self.perform()
        self.assertFalse((self.root / 'maintenance' / 'active').exists())
        self.assertEqual(self.release.json_file('.pb-release-transaction.json')['phase'], 'accepted')
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(self.release.recover(), 0)
        self.assertEqual(self.release.state(), self.old)

    def test_broken_metadata_symlink_never_falls_back_to_source(self):
        (self.root / '.pb-release.json').unlink()
        (self.root / '.pb-release.json').symlink_to(self.root / 'missing-target')
        with self.assertRaises(self.api.Problem): self.api.compose_path()

    def test_live_mutation_timeout_never_starts_competing_rollback(self):
        with patch.object(self.api, 'compose', side_effect=self.api.OperationRunning('still running', 3)), self.assertRaises(self.api.Problem) as caught:
            self.perform()
        self.assertEqual(caught.exception.code, 3)
        self.assertNotIn('Previous images and network/policy recovery were verified', str(caught.exception))
        self.assertTrue((self.root / 'maintenance' / 'active').exists())
        self.assertTrue((self.root / '.pb-release-transaction.json').exists())
        self.assertFalse(any(call[0] == 'network' for call in self.calls))
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(self.release.recover(), 0)
        self.assertEqual(self.release.state(), self.old)

    def test_recovery_when_viewer_container_is_absent(self):
        self.network_results = [1, 3]
        with self.assertRaises(self.api.Problem): self.perform()
        with patch.object(self.api, 'owned_containers', return_value=[]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.release.recover(), 0)
        self.assertEqual(self.release.state(), self.old)

    def test_linked_runtime_folder_is_refused(self):
        directory = self.root / 'maintenance'
        directory.rename(self.root / 'actual-maintenance')
        directory.symlink_to(self.root / 'actual-maintenance')
        with self.assertRaises(self.api.Problem): self.release.state()
        self.assertFalse(any(call[0] in ('run', 'compose') for call in self.calls))

    def test_configure_only_cli_stages_release_without_pull_or_build(self):
        (self.root / '.pb-release.json').unlink()
        (self.root / 'docker-compose.release.yml').unlink()
        private = (self.root / '.env').read_bytes()
        with patch.object(self.api, 'prerequisites'), patch.object(self.api, 'owned_containers', return_value=[]), patch.object(self.api, 'port_available'), patch.object(self.api, 'environment', return_value={'fixture': 'present'}), patch.object(self.api, 'login_exists', return_value=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.api.setup(True, self.new_bundle), 0)
        self.assertEqual(self.release.state()['active']['manifest']['version'], 'v0.0.0-rc.2')
        self.assertEqual((self.root / '.env').read_bytes(), private)
        self.assertFalse(any(call[0] in ('run', 'compose') for call in self.calls))

    def test_invalid_bundle_is_refused_before_credential_prompts(self):
        (self.root / '.pb-release.json').unlink()
        (self.root / 'docker-compose.release.yml').unlink()
        (self.new_bundle / 'release.json').write_text('{}')
        with patch.object(self.api, 'prerequisites'), patch.object(self.api, 'owned_containers', return_value=[]), patch.object(self.api, 'environment') as environment, patch.object(self.api, 'hash_password') as password, self.assertRaises(self.api.Problem):
            self.api.setup(True, self.new_bundle)
        environment.assert_not_called()
        password.assert_not_called()
        self.assertFalse((self.root / '.pb-release.json').exists())

    def test_cli_rollback_admits_pending_transaction_without_clearing_gate_first(self):
        self.network_results = [1, 3]
        with self.assertRaises(self.api.Problem): self.perform()
        with patch.object(self.api, 'prerequisites'), patch.object(self.api, 'environment', return_value={'fixture': 'present'}), patch.object(self.api, 'login_exists', return_value=True), patch.object(self.api, 'confirm', return_value=True), patch.object(self.api.sys, 'argv', ['pb', 'rollback']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.api.main(), 0)
        self.assertFalse((self.root / 'maintenance' / 'active').exists())
        self.assertEqual(self.release.state(), self.old)

    def test_unverified_login_reenables_gate_and_never_reports_updated(self):
        self.after_status = '500'
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(self.api.Problem) as caught:
            self.release.update(self.new_bundle)
        self.assertEqual(caught.exception.code, 3)
        self.assertNotIn('UPDATED:', output.getvalue())
        self.assertTrue((self.root / 'maintenance' / 'active').exists())
        self.assertTrue((self.root / '.pb-release-transaction.json').exists())
        self.after_status = '302'
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(self.release.recover(), 0)
        self.assertEqual(self.release.state(), self.old)

    def test_parser_accepts_actual_kernel_tcp4_and_tcp6_headers(self):
        for name, address in (('tcp', '00000000'), ('tcp6', '00000000000000000000000000000000')):
            path = Path('/proc/net') / name
            if not path.exists(): self.skipTest('kernel does not expose this socket-table header')
            with path.open() as handle: header = handle.readline()
            # Read the public schema header only, never live connection rows.
            self.assertEqual(self.release.viewers(header), 0)
            row = '0: ' + address + ':16A8 ' + address + ':1234 01\n'
            self.assertEqual(self.release.viewers(header + row), 1)
            with self.assertRaises(ValueError): self.release.viewers(header + 'malformed\n')


if __name__ == '__main__': unittest.main(verbosity=2)
