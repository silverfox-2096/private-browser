#!/usr/bin/env python3
"""Local prebuilt-image selection and rollback for compatible controller files.

Bundle verification checks consistency, not publisher authenticity. No remote
release discovery, unattended update, or production migration is performed.
"""
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import tarfile
import tempfile
import time

STATE = '.pb-release.json'
RECIPE = 'docker-compose.release.yml'
JOURNAL = '.pb-release-transaction.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Releases:
    def __init__(self, api):
        self.api = api
        self.root = api.ROOT
        spec = importlib.util.spec_from_file_location('pb_release_packager', self.root / 'ci' / 'release.py')
        self.package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.package)

    def problem(self, message, code=3):
        return self.api.Problem(message, code)

    def json_file(self, name):
        path = self.root / name
        if not self.api.private_file(path):
            return None
        try:
            return self.package.read_json(path)
        except (self.package.Invalid, OSError, ValueError, UnicodeError) as exc:
            raise self.problem('Release metadata is incomplete; preserve it and consult RELEASING.md.') from exc

    def write(self, name, value):
        """Atomic, private replacement; refuse links and foreign/loose files."""
        path = self.root / name
        if not self.api.private_file(path):
            self.api.create_private(path, value)
            return
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix='.pb-secret-', dir=self.root)
            with os.fdopen(fd, 'w') as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    def check_entry(self, entry):
        try:
            self.package.exact_fields(entry, ('manifest', 'recipe', 'sources'), 'installed release')
            self.package.validate_manifest(entry['manifest'])
            self.package.require(isinstance(entry['sources'], dict), 'controller checksums must be an object')
            required = {'scripts/onboard.py', 'scripts/release_mode.py', 'ci/release.py', 'docker-compose.yml',
                        'startup-guard.sh', 'local-app-post-rules.txt', 'check-local-app-policy.py',
                        'launch.sh', 'verify.sh', 'pb', 'setup.sh', 'maintenance.conf', 'ci/pins/compose.yml'}
            self.package.require(required <= set(entry['sources']), 'incomplete controller checksums')
            for name, checksum in entry['sources'].items():
                path = Path(name)
                self.package.require(not path.is_absolute() and '..' not in path.parts
                                     and re.fullmatch(self.package.SHA, checksum), 'invalid controller checksum')
                source = self.root / path
                self.package.require(not any(parent.is_symlink() for parent in source.parents if parent != self.root and self.root in parent.parents),
                                     'controller directory is linked outside this installation')
                self.package.require(source.is_file() and not source.is_symlink()
                                     and sha(source.read_bytes()) == checksum,
                                     'installed controller files changed; manual source migration is required')
            recipe = self.package.compose_recipe((self.root / 'docker-compose.yml').read_bytes(), entry['manifest']['images'])
            self.package.require(entry['recipe'] == recipe, 'release recipe does not match the installed controller')
            for name in ('maintenance', 'gluetun'):
                directory = self.root / name
                if directory.exists() or directory.is_symlink():
                    self.package.require(directory.is_dir() and not directory.is_symlink(), 'runtime directory must not be a link or special file')
        except (self.package.Invalid, OSError, ValueError, TypeError, AttributeError) as exc:
            raise self.problem('Release/controller verification did not pass. Use the original installation and review RELEASING.md before migration.') from exc
        return entry

    def state(self, *, check_recipe=True):
        state = self.json_file(STATE)
        recipe = self.root / RECIPE
        if state is None:
            if recipe.exists() or recipe.is_symlink():
                raise self.problem('Release setup was interrupted. Rerun setup with the same --release bundle; do not fall back to a source build.')
            return None
        try:
            self.package.exact_fields(state, ('schema', 'active', 'previous'), 'release state')
            self.package.require(type(state['schema']) is int and state['schema'] == 1, 'unsupported release state')
            self.check_entry(state['active'])
            if state['previous'] is not None:
                self.check_entry(state['previous'])
            if check_recipe:
                self.package.require(self.api.private_file(recipe) and recipe.read_text() == state['active']['recipe'], 'active recipe differs')
        except (self.package.Invalid, OSError, ValueError, TypeError) as exc:
            raise self.problem('Active release state is incomplete. Preserve it and use the rollback/recovery guide.') from exc
        return state

    def candidate(self, bundle):
        try:
            self.package.verify(bundle)
            manifest = self.package.read_json(bundle / 'release.json')
            with gzip.open(bundle / 'source.tar.gz', 'rb') as handle:
                archive = handle.read(self.package.MAX_ARCHIVE + 1)
            prefix = 'private-browser-' + manifest['version'] + '/'
            sources = {}
            with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as files:
                for member in files:
                    if not member.isfile():
                        continue
                    name = member.name[len(prefix):]
                    # Bind the executable controller and all maintained configs,
                    # tools and pins to the reviewed source; docs may be annotated.
                    if name.endswith(('.md', '.svg', '.cast', '.txt')) and name != 'local-app-post-rules.txt':
                        continue
                    sources[name] = sha(files.extractfile(member).read())
            entry = {'manifest': manifest, 'recipe': (bundle / 'docker-compose.release.yml').read_text(), 'sources': sources}
            return self.check_entry(entry)
        except (self.package.Invalid, OSError, ValueError, KeyError, EOFError, tarfile.TarError) as exc:
            raise self.problem('Release bundle did not verify. No release was installed; obtain a complete reviewed bundle and verify its publisher/provenance.') from exc

    def select(self, state):
        self.check_entry(state['active'])
        # A journal protects both replacements during a running update. For first
        # installation, an interrupted recipe-only write is resumable by stage().
        self.write(RECIPE, state['active']['recipe'])
        self.write(STATE, json.dumps(state, indent=2, sort_keys=True) + '\n')

    def stage(self, bundle):
        entry = self.candidate(bundle)
        state = self.json_file(STATE)
        if state is not None:
            current = self.state()
            if current['active'] != entry:
                raise self.problem('A different release is already selected. Use ./pb update --release BUNDLE.')
            return current
        recipe = self.root / RECIPE
        if recipe.exists() or recipe.is_symlink():
            if not self.api.private_file(recipe) or recipe.read_text() != entry['recipe']:
                raise self.problem('A different or incomplete release recipe exists; it was preserved.')
        state = {'schema': 1, 'active': entry, 'previous': None}
        self.select(state)
        return state

    def pull(self, entry):
        ids = {}
        for service, reference in entry['manifest']['images'].items():
            try:
                observed = self.api.docker('image', 'inspect', '--format', '{{.Id}} {{.Os}}/{{.Architecture}}', reference).strip()
            except self.api.Problem:
                observed = ''
            match = re.fullmatch(r'(sha256:[0-9a-f]{64}) linux/amd64', observed)
            if match:
                ids[service] = match[1]
                continue  # A cached immutable image needs no registry round-trip.
            result = self.api.run(['docker', 'pull', '--platform', 'linux/amd64', reference], timeout=600,
                                  env=self.api.compose_environment(), managed=True)
            if result.returncode:
                raise self.problem('The pinned release image could not be downloaded; existing software was preserved.', 1)
            observed = self.api.docker('image', 'inspect', '--format', '{{.Id}} {{.Os}}/{{.Architecture}}', reference).strip()
            match = re.fullmatch(r'(sha256:[0-9a-f]{64}) linux/amd64', observed)
            if not match:
                raise self.problem('Downloaded image identity/platform is incomplete; nothing was started.')
            ids[service] = match[1]
        return ids

    def identities(self, entry):
        ids = {}
        for service, reference in entry['manifest']['images'].items():
            observed = self.api.docker('image', 'inspect', '--format', '{{.Id}} {{.Os}}/{{.Architecture}}', reference).strip()
            match = re.fullmatch(r'(sha256:[0-9a-f]{64}) linux/amd64', observed)
            if not match:
                raise self.problem('Previous release images are unavailable; rollback cannot be guaranteed.')
            ids[service] = match[1]
        return ids

    def assert_images(self, ids):
        for service, name in (('gluetun', 'gluetun-proton'), ('firefox', 'private-firefox')):
            if self.api.docker('inspect', '--format', '{{.Image}}', name).strip() != ids[service]:
                raise self.problem('The running containers do not match the selected immutable images.', 1)

    def http_status(self):
        result = self.api.run(['curl', '-sk', '--max-time', '5', '-H', 'Connection: close', '-o', '/dev/null',
                               '-w', '%{http_code}', 'https://127.0.0.1:7814'], timeout=10)
        if result.returncode or not re.fullmatch(r'[0-9]{3}', result.stdout):
            raise self.problem('The local viewer response could not be verified.')
        return result.stdout

    @staticmethod
    def viewers(table):
        lines = table.splitlines()
        if not lines or not all(word in lines[0] for word in ('local_address', 'rem_address', 'st')):
            raise ValueError('unreadable socket table')
        count = 0
        for line in lines[1:]:
            fields = line.split()
            if len(fields) < 4 or not re.fullmatch(r'[0-9A-Fa-f]+:[0-9A-Fa-f]{4}', fields[1]) or not re.fullmatch(r'[0-9A-Fa-f]{2}', fields[3]):
                raise ValueError('malformed socket observation')
            if fields[1].rsplit(':', 1)[1].upper() == '16A8' and fields[3].upper() == '01':
                count += 1
        return count

    def gate_admission(self, *, allow_stopped=False, allow_missing=False):
        if allow_missing:
            return  # Readable engine inventory proves there is no viewer container.
        if allow_stopped:
            running = self.api.docker('inspect', '--format', '{{.State.Running}}', 'private-firefox').strip()
            if running == 'false':
                return  # Failed transition left no running viewer process.
            if running != 'true':
                raise self.problem('Browser running state could not be verified; recovery was refused.')
        if self.api.docker('exec', 'private-firefox', 'test', '-f', '/run/private-browser-maintenance/active') != '':
            raise self.problem('Maintenance mount could not be verified.')
        self.api.docker('exec', 'private-firefox', 'grep', '-qF',
                        'include /opt/base/etc/nginx/private-browser-maintenance.conf;', '/opt/base/etc/nginx/default_site.conf')
        if self.http_status() != '503':
            raise self.problem('Maintenance did not block new viewer requests; no update performed.')
        try:
            total = sum(self.viewers(self.api.docker('exec', 'private-firefox', 'cat', path))
                        for path in ('/proc/net/tcp', '/proc/net/tcp6'))
        except ValueError as exc:
            raise self.problem('Connected viewers could not be read; no update performed.') from exc
        if total:
            raise self.problem('A viewer is still connected. Close it and retry; no update performed.', 2)

    def gate_token(self):
        path = self.root / 'maintenance' / 'active'
        if not self.api.private_file(path):
            raise self.problem('The owned maintenance gate is missing.')
        meta = path.stat()
        return [meta.st_dev, meta.st_ino]

    def release_gate(self, token):
        if self.gate_token() != token:
            raise self.problem('Maintenance gate ownership changed; preserve it for manual recovery.')
        (self.root / 'maintenance' / 'active').unlink()

    def readiness(self, ids):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.api.docker('inspect', '--format', '{{.State.Health.Status}}', 'gluetun-proton').strip() == 'healthy' and self.api.docker('inspect', '--format', '{{.State.Running}}', 'private-firefox').strip() == 'true':
                break
            time.sleep(2)
        else:
            raise self.problem('Release readiness did not complete.', 1)
        self.assert_images(ids)
        if self.http_status() != '503':
            raise self.problem('Maintenance protection was lost during the transition.', 1)
        result = self.api.run([self.api.sys.executable, str(self.root / 'check-local-app-policy.py')], timeout=150)
        if result.returncode:
            raise self.problem('Installed policy did not pass.', 1 if result.returncode == 1 else 3)
        rc = self.api.lifecycle('verify.sh')
        if rc:
            raise self.problem('Installed network verification did not pass.', rc if rc in (1, 2, 3, 130) else 3)
        self.assert_images(ids)

    def up(self, optional):
        if optional:
            self.api.compose('--profile', 'test', 'up', '-d', '--force-recreate', 'gluetun', 'firefox', 'creepjs')
        else:
            self.api.compose('up', '-d', '--force-recreate', 'gluetun', 'firefox')

    def finish(self, journal):
        # Retain recoverability across a crash between accepting the software,
        # clearing maintenance and observing the normal authenticated login.
        journal['phase'] = 'accepted'
        self.write(JOURNAL, json.dumps(journal, indent=2, sort_keys=True) + '\n')
        self.release_gate(journal['gate'])
        try:
            if self.http_status() != '302':
                raise self.problem('The normal login redirect was not confirmed.')
        except self.api.Problem as exc:
            gate = self.root / 'maintenance' / 'active'
            if not gate.exists() and not gate.is_symlink():
                self.api.create_private(gate, '')
                journal['gate'] = self.gate_token()
                self.write(JOURNAL, json.dumps(journal, indent=2, sort_keys=True) + '\n')
            raise self.problem('The login response is INCOMPLETE. Maintenance and the transition record were retained; close the viewer and use ./pb rollback. No update or recovery success is claimed.') from exc
        (self.root / JOURNAL).unlink()

    def update(self, bundle=None, *, rollback=False):
        old = self.state()
        if old is None:
            raise self.problem('Prebuilt release updates require a release installation. Source installations keep their existing update workflow.', 2)
        if self.json_file(JOURNAL) is not None:
            raise self.problem('An interrupted release transition needs ./pb rollback before another update.')
        self.api.owned_containers()
        candidate = old['previous'] if rollback else self.candidate(bundle)
        if candidate is None:
            raise self.problem('No previous accepted release is recorded.', 2)
        if candidate == old['active']:
            print('Already using this release. Nothing changed.')
            return 0
        before = self.identities(old['active'])
        self.assert_images(before)
        # Prefetch is non-disruptive; the gate/viewer observation follows it.
        target = self.pull(candidate)
        optional = 'creepjs-server' in self.api.owned_containers() and self.api.docker('inspect', '--format', '{{.State.Running}}', 'creepjs-server').strip() == 'true'
        gate = self.root / 'maintenance' / 'active'
        gate.parent.mkdir(exist_ok=True)
        self.api.create_private(gate, '')
        token = self.gate_token()
        try:
            self.gate_admission()
        except BaseException:
            self.release_gate(token)
            raise
        journal = {'schema': 1, 'phase': 'transition', 'before': old, 'candidate': candidate, 'before_ids': before,
                   'target_ids': target, 'optional': optional, 'gate': token}
        self.write(JOURNAL, json.dumps(journal, indent=2, sort_keys=True) + '\n')
        try:
            self.select({'schema': 1, 'active': candidate, 'previous': old['active']})
            self.api.compose('--profile', 'test', 'down', timeout=180)
            self.up(optional)
            self.readiness(target)
        except self.api.OperationRunning as exc:
            raise self.problem('The release operation may still be running. Maintenance and its transaction were retained; wait for the operation lock to clear before ./pb rollback. No rollback or acceptance is claimed.') from exc
        except (self.api.Problem, KeyboardInterrupt, OSError, ValueError) as exc:
            previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                self.restore(journal)
            finally:
                signal.signal(signal.SIGINT, previous)
            code = exc.code if isinstance(exc, self.api.Problem) else 130 if isinstance(exc, KeyboardInterrupt) else 3
            raise self.problem('The release was not accepted. Previous images and network/policy recovery were verified; browser-session data cannot be restored.', code) from exc
        self.finish(journal)
        print('UPDATED: pinned images, local-app policy and installed network checks passed.\n'
              'Browser WebRTC/DNS checks remain separate; see QUICKSTART.md.')
        return 0

    def restore(self, journal):
        try:
            if self.identities(journal['before']['active']) != journal['before_ids']:
                raise self.problem('The recorded rollback images are unavailable or changed.')
            self.select(journal['before'])
            self.api.compose('--profile', 'test', 'down', timeout=180)
            self.up(journal['optional'])
            self.readiness(journal['before_ids'])
            self.finish(journal)
        except self.api.OperationRunning as exc:
            raise self.problem('The recovery operation may still be running. Its lock, maintenance gate and transaction remain; do not start a competing operation. Recovery is INCOMPLETE.') from exc
        except (self.api.Problem, OSError, ValueError, KeyboardInterrupt) as exc:
            raise self.problem('Rollback recovery is INCOMPLETE. The maintenance gate and transaction were retained; avoid browsing and follow RELEASING.md.') from exc

    def recover(self):
        journal = self.json_file(JOURNAL)
        if journal is None:
            return self.update(rollback=True)
        try:
            self.package.exact_fields(journal, ('schema', 'phase', 'before', 'candidate', 'before_ids', 'target_ids', 'optional', 'gate'), 'transition journal')
            self.package.require(type(journal['schema']) is int and journal['schema'] == 1, 'invalid journal schema')
            self.package.require(journal['phase'] in ('transition', 'accepted'), 'invalid transition phase')
            self.package.require(type(journal['optional']) is bool, 'invalid optional-service state')
            self.package.exact_fields(journal['before'], ('schema', 'active', 'previous'), 'recorded release state')
            self.package.require(type(journal['before']['schema']) is int and journal['before']['schema'] == 1, 'invalid recorded release state')
            self.check_entry(journal['before']['active'])
            if journal['before']['previous'] is not None:
                self.check_entry(journal['before']['previous'])
            self.check_entry(journal['candidate'])
            for key in ('before_ids', 'target_ids'):
                self.package.exact_fields(journal[key], ('gluetun', 'firefox'), 'transition identities')
                self.package.require(all(isinstance(value, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', value) for value in journal[key].values()), 'invalid transition identities')
            self.package.require(isinstance(journal['gate'], list) and len(journal['gate']) == 2 and all(type(x) is int for x in journal['gate']), 'invalid gate token')
            # Metadata/recipe may be inconsistent after a crash. Ownership still
            # must match this exact checkout/project/recipe before any mutation.
            owned = self.api.owned_containers(expected_recipe=self.root / RECIPE)
            gate = self.root / 'maintenance' / 'active'
            if not gate.exists() and not gate.is_symlink() and journal['phase'] == 'accepted':
                self.api.create_private(gate, '')
                journal['gate'] = self.gate_token()
                self.write(JOURNAL, json.dumps(journal, indent=2, sort_keys=True) + '\n')
            self.package.require(self.gate_token() == journal['gate'], 'gate ownership changed')
            self.gate_admission(allow_stopped=True, allow_missing='private-firefox' not in owned)
        except (self.package.Invalid, OSError, ValueError, KeyError, TypeError) as exc:
            raise self.problem('Release recovery admission is incomplete; keep maintenance active and obtain manual review.') from exc
        previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            self.restore(journal)
        finally:
            signal.signal(signal.SIGINT, previous)
        print('ROLLED BACK: recorded prior images and network/policy recovery verified. Session data was not restored.')
        return 0
