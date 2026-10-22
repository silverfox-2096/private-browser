#!/usr/bin/env python3
"""Credential-free onboarding regressions; no real Docker or VPN is used."""
import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'onboard.py'
spec = importlib.util.spec_from_file_location('onboard', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
KEY = base64.b64encode(bytes(range(32))).decode()
HASH = 'browser:$2y$05$' + 'a' * 53 + '\n'
WG = '[Interface]\nPrivateKey = ' + KEY + '\nAddress = 10.2.0.2/32\nDNS = 10.2.0.1\n\n[Peer]\nPublicKey = ' + KEY + '\nAllowedIPs = 0.0.0.0/0\nEndpoint = example.invalid:51820\n'
ENV = "WIREGUARD_PRIVATE_KEY='" + KEY + "'\nWIREGUARD_ADDRESSES='10.2.0.2/32'\nGLUETUN_API_KEY='" + 'b' * 64 + "'\nVPN_SERVICE_PROVIDER='protonvpn'\nSERVER_COUNTRIES='Singapore'\n"


class Onboard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'repo with spaces'
        self.root.mkdir()
        self.config = self.base / 'provider.conf'
        self.config.write_text(WG)
        (self.root / 'ci' / 'pins').mkdir(parents=True)
        shutil.copy2(SOURCE.parents[1] / 'ci' / 'pins' / 'compose.yml', self.root / 'ci' / 'pins' / 'compose.yml')
        self.addCleanup(patch.stopall)
        patch.object(m, 'ROOT', self.root).start()
        patch.dict(os.environ, {}, clear=True).start()

    def files(self):
        m.create_private(self.root / '.env', ENV)
        m.create_private(self.root / 'webauth-htpasswd', HASH)

    def wizard(self, answers=None, passwords=None, **kwargs):
        with patch.object(m, 'prerequisites'), patch.object(m, 'owned_containers', return_value=[]), patch.object(m, 'port_available'), patch.object(m.sys.stdin, 'isatty', return_value=True), patch('builtins.input', side_effect=answers or ['y', str(self.config), '', 'browser']), patch.object(m.getpass, 'getpass', side_effect=passwords or ['synthetic-password'] * 2), patch.object(m, 'hash_password', return_value=HASH), contextlib.redirect_stdout(io.StringIO()):
            return m.setup(**kwargs)

    def test_provider_import(self):
        self.assertEqual(m.import_wireguard(self.config), (KEY, '10.2.0.2/32'))

    def test_hooks_rejected_without_execution(self):
        for option in ('PostUp', 'PreUp', 'PostDown', 'PreDown', 'SaveConfig', 'Table'):
            with self.subTest(option=option):
                self.config.write_text(WG.replace('[Interface]', '[Interface]\n' + option + ' = touch /never-execute'))
                with patch.object(m, 'run') as run, self.assertRaises(m.Problem):
                    m.import_wireguard(self.config)
                run.assert_not_called()

    def test_invalid_configs_redacted(self):
        for content in ('', WG.replace(KEY, 'secret-invalid'), WG.replace('10.2.0.2/32', '::1/128'), WG + '\n[Peer]\nPublicKey=x', WG.replace('[Interface]', '[DEFAULT]\nX=y\n[Interface]')):
            self.config.write_text(content)
            with self.assertRaises(m.Problem) as caught:
                m.import_wireguard(self.config)
            self.assertNotIn('secret-invalid', str(caught.exception))
            self.assertNotIn(KEY, str(caught.exception))

    def test_large_config_rejected(self):
        self.config.write_text('x' * 65537)
        with self.assertRaises(m.Problem):
            m.import_wireguard(self.config)

    def test_files_private_and_complete(self):
        self.files()
        for name in ('.env', 'webauth-htpasswd'):
            self.assertEqual(stat.S_IMODE((self.root / name).stat().st_mode), 0o600)
        self.assertEqual(m.environment()['WIREGUARD_PRIVATE_KEY'], KEY)
        self.assertTrue(m.login_exists())
        self.assertEqual(list(self.root.glob('.pb-secret-*')), [])

    def test_no_overwrite_and_no_temporary_secret(self):
        self.files()
        with self.assertRaises(m.Problem):
            m.create_private(self.root / '.env', 'replacement')
        self.assertEqual((self.root / '.env').read_text(), ENV)
        self.assertEqual(list(self.root.glob('.pb-secret-*')), [])

    def test_interrupted_write_cleans_temporary_file(self):
        with patch.object(m.os, 'link', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            m.create_private(self.root / '.env', 'secret')
        self.assertFalse((self.root / '.env').exists())
        self.assertEqual(list(self.root.glob('.pb-secret-*')), [])

    def test_symlink_directory_hardlink_refused(self):
        for kind in ('symlink', 'directory', 'hardlink'):
            with self.subTest(kind=kind):
                target = self.root / '.env'
                if kind == 'symlink': target.symlink_to(self.config)
                elif kind == 'directory': target.mkdir()
                else: os.link(self.config, target)
                with self.assertRaises(m.Problem): m.environment()
                target.rmdir() if target.is_dir() else target.unlink()

    def test_loose_permissions_refused_without_chmod(self):
        self.files()
        (self.root / '.env').chmod(0o644)
        with self.assertRaises(m.Problem): m.environment()
        self.assertEqual(stat.S_IMODE((self.root / '.env').stat().st_mode), 0o644)

    def test_nonliteral_or_unknown_env_refused(self):
        for line in ('COMPOSE_PROJECT_NAME=other\n', 'GLUETUN_API_KEY=duplicate\n', 'EXTRA=$(touch /never-execute)\n', 'EXTRA=`something`\n'):
            path = self.root / '.env'
            m.create_private(path, ENV + line)
            with patch.object(m, 'run') as run, self.assertRaises(m.Problem): m.environment()
            run.assert_not_called()
            path.unlink()

    def test_shell_credentials_cannot_override_env(self):
        self.files()
        for key in (*m.SECRET_KEYS, 'VPN_SERVICE_PROVIDER', 'SERVER_COUNTRIES'):
            with patch.dict(os.environ, {key: 'SENSITIVE'}), self.assertRaises(m.Problem) as caught: m.environment()
            self.assertNotIn('SENSITIVE', str(caught.exception))

    def test_invalid_control_key_and_country(self):
        for content in (ENV.replace('b' * 64, 'x'), ENV.replace('Singapore', 'SG; echo secret')):
            m.create_private(self.root / '.env', content)
            with self.assertRaises(m.Problem): m.environment()
            (self.root / '.env').unlink()

    def test_clean_setup_configure_only(self):
        self.assertEqual(self.wizard(configure_only=True), 0)
        self.assertEqual(m.environment()['WIREGUARD_PRIVATE_KEY'], KEY)
        self.assertEqual(len(m.environment()['GLUETUN_API_KEY']), 64)
        self.assertTrue(m.login_exists())

    def test_rerun_preserves_exact_credentials(self):
        self.files()
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(self.wizard(configure_only=True), 0)
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir() if p.is_file()})

    def test_partial_setup_reuses_env(self):
        m.create_private(self.root / '.env', ENV)
        self.assertEqual(self.wizard(answers=['browser'], configure_only=True), 0)
        self.assertEqual((self.root / '.env').read_text(), ENV)
        self.assertTrue(m.login_exists())

    def test_partial_setup_reuses_login(self):
        m.create_private(self.root / 'webauth-htpasswd', HASH)
        self.assertEqual(self.wizard(answers=['y', str(self.config), 'Singapore'], configure_only=True), 0)
        self.assertEqual((self.root / 'webauth-htpasswd').read_text(), HASH)

    def test_password_failures_create_nothing(self):
        for values in (['a', 'a'], ['synthetic-password', 'mismatch'], ['a' * 73] * 2, ['a' * 12 + '\n'] * 2):
            with self.assertRaises(m.Problem): self.wizard(passwords=values, configure_only=True)
            self.assertEqual([p for p in self.root.iterdir() if p.name != 'ci'], [])

    def test_cancelled_password_creates_nothing(self):
        with self.assertRaises(EOFError): self.wizard(passwords=[EOFError()], configure_only=True)
        self.assertEqual([p for p in self.root.iterdir() if p.name != 'ci'], [])

    def test_option_like_username_rejected(self):
        with self.assertRaises(m.Problem):
            self.wizard(answers=['y', str(self.config), '', '-c'], configure_only=True)
        self.assertFalse((self.root / '.env').exists())

    def test_import_from_repo_refused(self):
        path = self.root / 'provider.conf'
        path.write_text(WG)
        with self.assertRaises(m.Problem): self.wizard(answers=['y', str(path)], configure_only=True)
        self.assertFalse((self.root / '.env').exists())

    def test_no_noninteractive_secret_input(self):
        with patch.object(m, 'prerequisites'), patch.object(m, 'owned_containers', return_value=[]), patch.object(m, 'port_available'), patch.object(m.sys.stdin, 'isatty', return_value=False), self.assertRaises(m.Problem): m.setup(True)

    def test_foreign_container_and_overrides_refused(self):
        good = {'com.docker.compose.project.working_dir': str(self.root), 'com.docker.compose.project.config_files': str(self.root / 'docker-compose.yml'), 'com.docker.compose.project': m.project_name()}
        for delta in ({'com.docker.compose.project.working_dir': '/other'}, {'com.docker.compose.project.config_files': 'override.yml'}, {'com.docker.compose.project': 'other'}, {}):
            with patch.object(m, 'docker', side_effect=['private-firefox\n', json.dumps(good | delta)]):
                if delta:
                    with self.assertRaises(m.Problem): m.owned_containers()
                else: self.assertEqual(m.owned_containers(), ['private-firefox'])

    def test_setup_never_restarts_existing_containers(self):
        self.files()
        with patch.object(m, 'prerequisites'), patch.object(m, 'owned_containers', return_value=['private-firefox']), patch.object(m, 'compose') as compose, patch.object(m, 'start') as start, contextlib.redirect_stdout(io.StringIO()): self.assertEqual(m.setup(), 0)
        compose.assert_not_called()
        start.assert_not_called()

    def test_existing_containers_missing_env_fails(self):
        with patch.object(m, 'prerequisites'), patch.object(m, 'owned_containers', return_value=['private-firefox']), self.assertRaises(m.Problem): m.setup()

    def test_read_only_doctor_on_stopped_installation(self):
        self.files()
        before = sorted(p.name for p in self.root.iterdir())
        with patch.object(m, 'prerequisites'), patch.object(m, 'owned_containers', return_value=[]), patch.object(m, 'port_available'), patch.object(m, 'compose') as compose, patch.object(m, 'run') as run, contextlib.redirect_stdout(io.StringIO()): self.assertEqual(m.doctor(), 0)
        compose.assert_not_called()
        run.assert_not_called()
        self.assertEqual(before, sorted(p.name for p in self.root.iterdir()))

    def test_doctor_preserves_incomplete_and_failure(self):
        self.files()
        for rc, expected in ((1, 1), (3, 3), (127, 3)):
            with patch.object(m, 'prerequisites'), patch.object(m, 'owned_containers', return_value=['private-firefox']), patch.object(m, 'status'), patch.object(m, 'run', return_value=Mock(returncode=rc)), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(m.Problem) as caught: m.doctor()
            self.assertEqual(caught.exception.code, expected)

    def test_failed_build_never_launches(self):
        self.files()
        with patch.object(m, 'owned_containers', return_value=[]), patch.object(m, 'port_available'), patch.object(m, 'compose', side_effect=m.Problem('failed build', 1)), patch.object(m, 'run') as run, contextlib.redirect_stdout(io.StringIO()), self.assertRaises(m.Problem): m.start()
        run.assert_not_called()

    def test_compose_mutations_keep_managed_process_protection(self):
        with patch.object(m, 'run', return_value=Mock(returncode=0)) as run:
            m.compose('down')
        self.assertTrue(run.call_args.kwargs['managed'])
        self.assertEqual(run.call_args.kwargs['env']['COMPOSE_PROJECT_NAME'], m.project_name())

    def test_start_keeps_managed_process_protection(self):
        self.files()
        with patch.object(m, 'owned_containers', return_value=['private-firefox']), patch.object(m, 'run', return_value=Mock(returncode=0)) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.start(), 0)
        self.assertTrue(run.call_args.kwargs['managed'])

    def test_managed_runner_never_accepts_secret_input(self):
        with patch.object(m, 'managed_process') as process, self.assertRaises(m.Problem):
            m.run(['command'], data='secret', managed=True)
        process.assert_not_called()

    def test_launch_failure_never_reports_ready(self):
        self.files()
        for rc in (1, 3, 127):
            output = io.StringIO()
            with patch.object(m, 'owned_containers', return_value=['private-firefox']), patch.object(m, 'run', return_value=Mock(returncode=rc)), contextlib.redirect_stdout(output), self.assertRaises(m.Problem) as caught: m.start()
            self.assertNotIn('READY:', output.getvalue())
            self.assertEqual(caught.exception.code, 1 if rc == 1 else 3)

    def test_lock_excludes_concurrent_mutations(self):
        with m.setup_lock():
            script = 'import fcntl,os,sys; f=os.open(sys.argv[1],os.O_WRONLY); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)'
            self.assertNotEqual(subprocess.run([sys.executable, '-c', script, str(self.root / '.pb-setup.lock')], capture_output=True).returncode, 0)

    def test_helper_has_no_password_arguments_or_mounts(self):
        secret = 'synthetic-password'
        with patch.object(m.shutil, 'which', return_value=None), patch.object(m, 'run', side_effect=[Mock(returncode=0), Mock(returncode=0, stdout=HASH)]) as run, contextlib.redirect_stdout(io.StringIO()): self.assertEqual(m.hash_password('browser', secret), HASH)
        args, kwargs = run.call_args
        self.assertNotIn(secret, ' '.join(args[0]))
        self.assertNotIn('-v', args[0])
        self.assertIn('none', args[0])
        self.assertEqual(kwargs['data'], secret + '\n')
        self.assertIn('@sha256:', m.helper_image())

    @unittest.skipUnless(shutil.which('htpasswd'), 'host htpasswd not installed')
    def test_real_bcrypt_generation_and_password_check(self):
        result = m.hash_password('browser', 'synthetic-password')
        m.create_private(self.root / 'webauth-htpasswd', result)
        self.assertTrue(m.login_exists())
        checked = subprocess.run(['htpasswd', '-vi', str(self.root / 'webauth-htpasswd'), 'browser'], input='synthetic-password\n', text=True, capture_output=True)
        self.assertEqual(checked.returncode, 0)

    def test_missing_tools_and_remote_context_fail_closed(self):
        with patch.object(m.shutil, 'which', return_value=None), self.assertRaises(m.Problem): m.prerequisites()
        with patch.object(m.shutil, 'which', return_value='/tool'), patch.object(m, 'docker', side_effect=['remote', '"ssh://remote"', '{"OSType":"linux","Architecture":"amd64"}']), self.assertRaises(m.Problem): m.prerequisites()
        with patch.dict(os.environ, {'COMPOSE_FILE': 'sensitive'}), self.assertRaises(m.Problem) as caught: m.prerequisites()
        self.assertNotIn('sensitive', str(caught.exception))

    def test_docker_platform_security_and_schema(self):
        good = {'OSType': 'linux', 'Architecture': 'amd64', 'SecurityOptions': ['name=seccomp']}
        for info, expected in ((good, None), ([], 3), (good | {'SecurityOptions': None}, 3),
                               (good | {'SecurityOptions': ['name=rootless']}, 2),
                               (good | {'Architecture': 'aarch64'}, 2),
                               (good | {'OperatingSystem': 'Docker Desktop'}, 2)):
            with self.subTest(info=info), patch.object(m.os, 'geteuid', return_value=1000), patch.object(m.shutil, 'which', return_value='/tool'), patch.object(m, 'docker', side_effect=['default', '"unix:///var/run/docker.sock"', json.dumps(info)]), patch.object(m.Path, 'exists', return_value=True), patch.object(m, 'run', return_value=Mock(returncode=0)):
                if expected:
                    with self.assertRaises(m.Problem) as caught: m.prerequisites()
                    self.assertEqual(caught.exception.code, expected)
                else: self.assertEqual(m.prerequisites(), good)

    def test_mutable_or_unexpected_helper_pin_refused(self):
        manifest = self.root / 'ci' / 'pins' / 'compose.yml'
        for reference in ('httpd:2.4-alpine', 'untrusted/helper@sha256:' + 'a' * 64, 'httpd:3.0-alpine@sha256:' + 'a' * 64):
            manifest.write_text('services:\n  helper:\n    image: ' + reference + '\n')
            with self.assertRaises(m.Problem): m.helper_image()

    def test_unreadable_container_labels_are_incomplete(self):
        with patch.object(m, 'docker', side_effect=['private-firefox\n', '["bad-schema"]']), self.assertRaises(m.Problem) as caught: m.owned_containers()
        self.assertEqual(caught.exception.code, 3)

    def test_timeout_does_not_kill_child_and_retains_lock(self):
        (self.root / 'verify.sh').write_text('sleep 0.5\ntouch completed\n')
        real_popen = subprocess.Popen
        children = []
        def launch(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            children.append(child)
            child.wait = Mock(side_effect=subprocess.TimeoutExpired('fixture', .01))
            return child
        with m.setup_lock(), patch.object(m.subprocess, 'Popen', side_effect=launch), self.assertRaises(m.Problem) as caught:
            m.lifecycle('verify.sh')
        self.assertEqual(caught.exception.code, 3)
        check = 'import fcntl,os,sys; f=os.open(sys.argv[1],os.O_WRONLY); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)'
        self.assertNotEqual(subprocess.run([sys.executable, '-c', check, str(self.root / '.pb-setup.lock')], capture_output=True).returncode, 0)
        child = children[0]
        del child.wait
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertTrue((self.root / 'completed').exists())

    def test_ctrl_c_waits_for_restoration(self):
        (self.root / 'verify.sh').write_text("#!/bin/bash\ntrap 'sleep 0.2; touch restored; exit 130' INT\ntouch ready\nsleep 30\n")
        worker = self.base / 'worker.py'
        worker.write_text('import importlib.util,pathlib,sys\ns=importlib.util.spec_from_file_location("onboard",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nm.ROOT=pathlib.Path(sys.argv[2])\nwith m.setup_lock():\n r=m.lifecycle("verify.sh")\nsys.exit(r)\n')
        process = subprocess.Popen([sys.executable, str(worker), str(SOURCE), str(self.root)], start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not (self.root / 'ready').exists() and time.monotonic() < deadline: time.sleep(.02)
            self.assertTrue((self.root / 'ready').exists())
            os.killpg(process.pid, signal.SIGINT)
            out, err = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 130, out + err)
            self.assertTrue((self.root / 'restored').exists())
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()


if __name__ == '__main__': unittest.main(verbosity=2)
