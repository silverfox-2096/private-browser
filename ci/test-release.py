#!/usr/bin/env python3
"""Offline packaging controls. All release receipts/images here are synthetic.

These checks never publish, pull or start images, and do not create real acceptance
records. The Git source is read-only; output is in temporary directories.
"""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT / 'ci' / 'release.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = m.git('rev-parse', 'HEAD').decode().strip()
        images = {s: 'ghcr.io/silverfox-2096/private-browser-' + s + '@sha256:' + c * 64
                  for s, c in zip(m.SERVICES, ('a', 'b'))}
        self.manifest = {'schema': 1, 'version': 'v0.0.0-rc.0', 'source': source,
                         'platform': 'linux/amd64', 'created': '2026-10-22T06:00:00Z',
                         'images': images, 'provenance': {s: {'source': source, 'image': images[s], 'sha256': 'c' * 64} for s in m.SERVICES},
                         'measurements': {'install_seconds': 1, 'peak_memory_mib': 1, 'disk_mib': 1}}
        self.evidence = {'schema': 1, 'source': source, 'images': images,
                         'gates': {name: {'status': 'PASS', 'scope': 'actual-runtime' if name in m.RUNTIME_GATES else 'exact-artifact',
                                          'source': source, 'images': images, 'report_sha256': 'd' * 64} for name in m.GATES}}
        self.manifest_path = self.root / 'manifest.json'
        self.evidence_path = self.root / 'evidence.json'

    def write(self):
        self.manifest_path.write_bytes(m.normalized(self.manifest))
        self.evidence_path.write_bytes(m.normalized(self.evidence))

    def package(self, name='bundle'):
        self.write()
        out = self.root / name
        m.prepare(self.manifest_path, self.evidence_path, out)
        return out

    def rehash(self, out):
        (out / 'SHA256SUMS').write_text(''.join(m.digest((out / name).read_bytes()) + '  ' + name + '\n' for name in sorted(m.FILES - {'SHA256SUMS'})))

    def test_package_and_verify_repeatable(self):
        first, second = self.package(), self.package('second')
        m.verify(first)
        self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()}, {p.name: p.read_bytes() for p in second.iterdir()})
        recipe = (first / 'docker-compose.release.yml').read_text()
        for image in self.manifest['images'].values(): self.assertIn(image, recipe)
        self.assertNotIn('pull_policy: never', recipe)
        self.assertIn('network_mode: "service:gluetun"', recipe)
        self.assertIn('./local-app-post-rules.txt:/iptables/post-rules.txt:ro', recipe)
        self.assertIn('./startup-guard.sh:/run/private-browser-startup.sh:ro', recipe)
        self.assertIn('./maintenance:/run/private-browser-maintenance:ro', recipe)
        self.assertIn('./webauth-htpasswd:/config/webauth-htpasswd', recipe)

    def test_compose_semantics_preserved(self):
        out = self.package()
        source = self.root / 'source.yml'
        source.write_bytes(m.git('show', self.manifest['source'] + ':docker-compose.yml'))
        env = {k: v for k, v in os.environ.items() if not k.startswith(('COMPOSE_', 'DOCKER_'))}
        env.update(WIREGUARD_PRIVATE_KEY='unused-release-fixture', WIREGUARD_ADDRESSES='10.2.0.2/32', GLUETUN_API_KEY='unused-release-fixture', VPN_SERVICE_PROVIDER='protonvpn', SERVER_COUNTRIES='Singapore')
        def resolve(path):
            result = subprocess.run(['docker', 'compose', '--project-directory', str(ROOT), '-f', str(path), '--profile', 'test', 'config', '--format', 'json'], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, 'Compose could not inspect the fixture')
            return json.loads(result.stdout)
        original, generated = resolve(source), resolve(out / 'docker-compose.release.yml')
        for service in m.SERVICES:
            self.assertNotIn('build', generated['services'][service])
            self.assertEqual(generated['services'][service]['image'], self.manifest['images'][service])
            self.assertEqual(generated['services'][service]['pull_policy'], 'missing')
            for document in (original, generated):
                for field in ('build', 'image', 'pull_policy'): document['services'][service].pop(field, None)
        self.assertEqual(original, generated)

    def test_no_missing_failed_or_incomplete_gates(self):
        for name in m.GATES:
            for value in ('FAIL', 'INCOMPLETE', 'NOT RUN'):
                broken = copy.deepcopy(self.evidence)
                broken['gates'][name]['status'] = value
                with self.subTest(name=name, value=value), self.assertRaises(m.Invalid): m.validate_evidence(self.manifest, broken)
            broken = copy.deepcopy(self.evidence)
            del broken['gates'][name]
            with self.assertRaises(m.Invalid): m.validate_evidence(self.manifest, broken)

    def test_scopes_and_image_identity_cannot_drift(self):
        for name in m.GATES:
            broken = copy.deepcopy(self.evidence)
            broken['gates'][name]['source'] = '0' * 40
            with self.assertRaises(m.Invalid): m.validate_evidence(self.manifest, broken)
            broken['gates'][name]['source'] = self.manifest['source']
            broken['gates'][name]['scope'] = 'synthetic'
            with self.assertRaises(m.Invalid): m.validate_evidence(self.manifest, broken)
        broken = copy.deepcopy(self.evidence)
        broken['images'] = dict(broken['images'], firefox=self.manifest['images']['firefox'][:-1] + 'c')
        with self.assertRaises(m.Invalid): m.validate_evidence(self.manifest, broken)

    def test_mutable_unexpected_registry_and_wrong_platform_rejected(self):
        for reference in ('ghcr.io/silverfox-2096/private-browser-firefox:latest', 'ghcr.io/other/firefox@sha256:' + 'a' * 64, 'http://example.invalid/image', '--option'):
            broken = copy.deepcopy(self.manifest)
            broken['images']['firefox'] = reference
            with self.assertRaises(m.Invalid): m.validate_manifest(broken)
        self.manifest['platform'] = 'linux/arm64'
        with self.assertRaises(m.Invalid): m.validate_manifest(self.manifest)

    def test_invalid_metadata_measurements_and_private_fields_rejected(self):
        for field, value in (('schema', True), ('created', '2026-99-99T00:00:00Z'), ('source', 'main'), ('version', '../../escape'), ('WIREGUARD_PRIVATE_KEY', 'DO-NOT-PUBLISH')):
            broken = copy.deepcopy(self.manifest)
            broken[field] = value
            with self.assertRaises((m.Invalid, ValueError)): m.validate_manifest(broken)
        for value in (0, -1, True, 'unmeasured'):
            broken = copy.deepcopy(self.manifest)
            broken['measurements']['disk_mib'] = value
            with self.assertRaises(m.Invalid): m.validate_manifest(broken)

    def test_provenance_must_match_exact_artifacts(self):
        for field, value in (('source', '0' * 40), ('image', 'other'), ('sha256', 'missing')):
            broken = copy.deepcopy(self.manifest)
            broken['provenance']['firefox'][field] = value
            with self.assertRaises(m.Invalid): m.validate_manifest(broken)

    def test_missing_evidence_never_creates_output(self):
        self.evidence['gates']['clean-install']['status'] = 'NOT RUN'
        self.write()
        with patch.object(m, 'git') as git, self.assertRaises(m.Invalid):
            m.prepare(self.manifest_path, self.evidence_path, self.root / 'bundle')
        git.assert_not_called()
        self.assertFalse((self.root / 'bundle').exists())

    def test_existing_output_and_symlink_never_overwritten(self):
        out = self.package()
        original = (out / 'SHA256SUMS').read_bytes()
        with self.assertRaises(m.Invalid): self.package()
        self.assertEqual((out / 'SHA256SUMS').read_bytes(), original)
        link = self.root / 'link'
        link.symlink_to(out)
        with self.assertRaises(m.Invalid): m.verify(link)

    def test_corruption_missing_unexpected_and_link_files_rejected(self):
        out = self.package()
        notes = out / 'RELEASE-NOTES.md'
        original = notes.read_bytes()
        notes.write_text('changed')
        with self.assertRaises(m.Invalid): m.verify(out)
        notes.write_bytes(original)
        (out / 'private-key').write_text('not-public')
        with self.assertRaises(m.Invalid): m.verify(out)
        (out / 'private-key').unlink()
        notes.unlink()
        with self.assertRaises(m.Invalid): m.verify(out)
        notes.symlink_to(self.manifest_path)
        with self.assertRaises(m.Invalid): m.verify(out)

    def test_rehashed_compose_changes_still_rejected(self):
        out = self.package()
        recipe = out / 'docker-compose.release.yml'
        recipe.write_text(recipe.read_text().replace('/iptables/post-rules.txt:ro', '/iptables/post-rules.txt'))
        self.rehash(out)
        with self.assertRaises(m.Invalid): m.verify(out)

    def test_checksum_duplicates_traversal_and_missing_entries_rejected(self):
        out = self.package()
        sums = out / 'SHA256SUMS'
        original = sums.read_text()
        duplicate = original.splitlines()
        duplicate[1] = duplicate[0]
        for invalid in ('\n'.join(duplicate), original + original.splitlines()[0] + '\n', '\n'.join(original.splitlines()[1:]), original.replace('  release.json', '  ../release.json')):
            sums.write_text(invalid)
            with self.assertRaises(m.Invalid): m.verify(out)

    def test_archive_links_paths_and_secret_backups_rejected(self):
        valid = m.git('archive', '--format=tar', '--prefix=source/', self.manifest['source'])
        m.check_source_files(valid, 'source')
        def append(item):
            buf = io.BytesIO()
            with tarfile.open(fileobj=io.BytesIO(valid), mode='r:') as original, tarfile.open(fileobj=buf, mode='w') as target:
                for entry in original:
                    target.addfile(entry, original.extractfile(entry) if entry.isfile() else None)
                target.addfile(item, io.BytesIO(b'x') if item.isfile() else None)
            return buf.getvalue()
        for name in ('../escape', '/absolute', 'source/.env', 'source/.env.backup', 'source/webauth-htpasswd.bak', 'source/provider.conf', 'source/key.pem'):
            item = tarfile.TarInfo(name); item.size = 1
            with self.subTest(name=name), self.assertRaises(m.Invalid): m.check_source_files(append(item), 'source')
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE):
            item = tarfile.TarInfo('source/link'); item.type = kind; item.linkname = '/private'
            with self.assertRaises(m.Invalid): m.check_source_files(append(item), 'source')

    def test_archive_limit_and_complete_runtime_inventory(self):
        valid = m.git('archive', '--format=tar', '--prefix=source/', self.manifest['source'])
        with patch.object(m, 'MAX_ARCHIVE', 32), self.assertRaises(m.Invalid): m.check_source_files(valid, 'source')
        buf = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(valid), mode='r:') as original, tarfile.open(fileobj=buf, mode='w') as target:
            for entry in original:
                if entry.name != 'source/startup-guard.sh':
                    target.addfile(entry, original.extractfile(entry) if entry.isfile() else None)
        with self.assertRaises(m.Invalid): m.check_source_files(buf.getvalue(), 'source')

    def test_duplicate_json_keys_rejected(self):
        self.manifest_path.write_text('{"schema":1,"schema":2}')
        with self.assertRaises(m.Invalid): m.read_json(self.manifest_path)

    def test_source_archive_preserves_executable_entry_points(self):
        valid = m.git('archive', '--format=tar', '--prefix=source/', self.manifest['source'])
        buf = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(valid), mode='r:') as original, tarfile.open(fileobj=buf, mode='w') as target:
            for entry in original:
                if entry.name == 'source/setup.sh': entry.mode = 0o644
                target.addfile(entry, original.extractfile(entry) if entry.isfile() else None)
        with self.assertRaises(m.Invalid): m.check_source_files(buf.getvalue(), 'source')

    def test_unknown_compose_layout_refused(self):
        original = m.git('show', self.manifest['source'] + ':docker-compose.yml')
        with self.assertRaises(m.Invalid): m.compose_recipe(original.replace(b'    build:\n', b'    build: ./other\n', 1), self.manifest['images'])


if __name__ == '__main__': unittest.main(verbosity=2)
