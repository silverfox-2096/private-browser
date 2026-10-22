#!/usr/bin/env python3
"""Offline release packaging and integrity checks. No Docker, network or installation.

Consistency checking of reviewed evidence is not independent proof of those tests.
A package and its checksums do not authenticate its publisher; see RELEASING.md.
"""
import argparse
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ('gluetun', 'firefox')
GATES = ('upstream-contracts', 'startup-guard', 'policy-network', 'fingerprint',
         'network', 'browser', 'recovery', 'vulnerability-scan',
         'advisory-disposition', 'clean-install', 'novice-trial')
RUNTIME_GATES = {'network', 'browser', 'recovery', 'clean-install', 'novice-trial'}
FILES = {'release.json', 'evidence.json', 'docker-compose.release.yml',
         'source.tar.gz', 'RELEASE-NOTES.md', 'SHA256SUMS'}
SHA = r'[0-9a-f]{64}'
REVISION = r'[0-9a-f]{40}'
VERSION = r'v[0-9]+\.[0-9]+\.[0-9]+(?:-rc\.[0-9]+)?'
DATE = r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z'
MAX_ARCHIVE = 128 * 1024 * 1024


class Invalid(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def exact_fields(value, fields, label):
    require(isinstance(value, dict) and set(value) == set(fields), label + ' has missing or unexpected fields')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1048576,
            'expected a regular JSON file of at most 1 MiB')
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON fields are not accepted')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique_pairs)


def validate_manifest(manifest):
    exact_fields(manifest, ('schema', 'version', 'source', 'platform', 'created', 'images',
                            'provenance', 'measurements'), 'release manifest')
    require(type(manifest['schema']) is int and manifest['schema'] == 1, 'unsupported release schema')
    for key, pattern in (('version', VERSION), ('source', REVISION), ('created', DATE)):
        require(isinstance(manifest[key], str) and re.fullmatch(pattern, manifest[key]), 'invalid ' + key)
    datetime.datetime.strptime(manifest['created'], '%Y-%m-%dT%H:%M:%SZ')
    require(manifest['platform'] == 'linux/amd64', 'only Linux/amd64 is initially supported')
    exact_fields(manifest['images'], SERVICES, 'image identities')
    exact_fields(manifest['provenance'], SERVICES, 'provenance receipts')
    for service in SERVICES:
        reference = manifest['images'][service]
        repository = 'ghcr.io/silverfox-2096/private-browser-' + service
        require(isinstance(reference, str) and re.fullmatch(re.escape(repository) + '@sha256:' + SHA, reference),
                'images must use the expected owner/repository and immutable digest')
        receipt = manifest['provenance'][service]
        exact_fields(receipt, ('source', 'image', 'sha256'), 'provenance receipt')
        require(receipt['source'] == manifest['source'] and receipt['image'] == reference,
                'provenance must identify the exact source and image')
        require(isinstance(receipt['sha256'], str) and re.fullmatch(SHA, receipt['sha256']), 'invalid provenance checksum')
    measures = manifest['measurements']
    exact_fields(measures, ('install_seconds', 'peak_memory_mib', 'disk_mib'), 'clean-install measurements')
    require(all(type(value) is int and value > 0 for value in measures.values()),
            'record positive measured install duration, memory and disk values')


def validate_evidence(manifest, evidence):
    exact_fields(evidence, ('schema', 'source', 'images', 'gates'), 'acceptance evidence')
    require(type(evidence['schema']) is int and evidence['schema'] == 1 and evidence['source'] == manifest['source']
            and evidence['images'] == manifest['images'], 'acceptance evidence targets different artifacts')
    exact_fields(evidence['gates'], GATES, 'acceptance gates')
    for name in GATES:
        gate = evidence['gates'][name]
        exact_fields(gate, ('status', 'scope', 'source', 'images', 'report_sha256'), name)
        require(gate['status'] == 'PASS', name + ' is not PASS; FAIL/INCOMPLETE/NOT RUN cannot be packaged')
        require(gate['source'] == manifest['source'] and gate['images'] == manifest['images'],
                name + ' targets different source/images')
        require(gate['scope'] == ('actual-runtime' if name in RUNTIME_GATES else 'exact-artifact'),
                name + ' lacks the required execution scope')
        require(isinstance(gate['report_sha256'], str) and re.fullmatch(SHA, gate['report_sha256']),
                name + ' needs a reviewed report checksum')


def git(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, timeout=60)
    require(result.returncode == 0, 'could not read the selected Git source')
    return result.stdout


def check_source_files(archive, prefix):
    require(len(archive) <= MAX_ARCHIVE, 'source archive exceeds the 128 MiB safety limit')
    essential = {'setup.sh', 'pb', 'scripts/onboard.py', 'docker-compose.yml',
                 'startup-guard.sh', 'local-app-post-rules.txt', 'check-local-app-policy.py',
                 'maintenance.conf', 'ci/pins/compose.yml', 'launch.sh', 'update.sh',
                 'verify.sh', 'probe/checks.sh', 'ci/checks.mjs', 'ci/creep-baseline.json',
                 'Dockerfile.firefox', 'gluetun-patched/Dockerfile', 'gluetun-patched/go.mod',
                 'gluetun-patched/go.sum', '.env.example', 'QUICKSTART.md', 'VALIDATION.md',
                 'RELEASING.md', 'LICENSE'}
    names, all_paths = set(), set()
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as source:
        for member in source:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and '..' not in path.parts and path.parts[0] == prefix,
                    'source archive has an unsafe path')
            require(member.isdir() or member.isfile(), 'source archives must not contain links or special files')
            canonical = str(path)
            require(member.name == canonical or (member.isdir() and member.name == canonical + '/'),
                    'source archive has a noncanonical path')
            require(canonical not in all_paths and len(all_paths) < 10000,
                    'duplicate source path or excessive archive members')
            all_paths.add(canonical)
            relative = PurePosixPath(*path.parts[1:])
            require(not any(part in ('.git', '.env', 'webauth-htpasswd', 'gluetun', 'creepjs',
                                     '.private-browser-release') for part in relative.parts),
                    'source archive contains private runtime files')
            require(not any(part.startswith(('.pb-secret-', '.env', 'webauth-htpasswd')) and part != '.env.example'
                            for part in relative.parts), 'source archive contains a potential credential backup')
            require(not (relative.suffix in ('.key', '.pem', '.p12', '.pfx', '.ovpn')
                         or str(relative).endswith('.conf.wg')
                         or (relative.suffix == '.conf' and str(relative) not in ('maintenance.conf', 'nginx-8080.conf'))),
                    'source archive contains a potential private provider/credential file')
            if member.isfile():
                require(str(relative) not in names, 'duplicate source archive file')
                names.add(str(relative))
        require(essential <= names, 'source archive lacks required runtime files')


def compose_recipe(source, images):
    """Replace only builds/image selection; reject unfamiliar source layouts."""
    text = source.decode('utf-8')
    for service in SERVICES:
        pattern = r'(?ms)^  ' + service + r':\n.*?(?=^  [A-Za-z0-9_-]+:|\Z)'
        blocks = list(re.finditer(pattern, text))
        require(len(blocks) == 1, 'expected one known Compose service')
        block = blocks[0].group()
        block, count = re.subn(r'(?m)^    build:\n(?:^      [^\n]*\n)+', '', block)
        require(count == 1, 'unfamiliar Compose build layout; review source before release')
        block, count = re.subn(r'(?m)^    image: [^\n]*$', '    image: ' + images[service], block)
        require(count == 1, 'unfamiliar Compose image layout')
        block, count = re.subn(r'(?m)^    pull_policy: [^\n]*$', '    pull_policy: missing', block)
        if not count:
            block = block.replace('    image: ' + images[service] + '\n',
                                  '    image: ' + images[service] + '\n    pull_policy: missing\n', 1)
        require(count <= 1, 'duplicate pull policy')
        text = text[:blocks[0].start()] + block + text[blocks[0].end():]
    # The optional CreepJS tester remains source-built and disabled by default.
    return text


def normalized(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def notes(manifest):
    measured = manifest['measurements']
    return ('# Private Browser ' + manifest['version'] + '\n\n'
            'Platform: Linux/amd64. Source: `' + manifest['source'] + '`.\n\n'
            'This candidate records reviewed evidence for the exact image digests in\n'
            '`release.json`; inspect the retained reports and advisory dispositions.\n'
            'Checksums establish file integrity, not publisher authenticity or proof\n'
            'that the reported tests occurred. Verify the publisher/provenance before use.\n\n'
            'Measured clean install: ' + str(measured['install_seconds']) + ' seconds, '
            + str(measured['peak_memory_mib']) + ' MiB peak memory, '
            + str(measured['disk_mib']) + ' MiB disk. These measurements describe the\n'
            'reviewed test host, not a guarantee for every machine.\n\n'
            'The source archive preserves source builds. `docker-compose.release.yml`\n'
            'selects prebuilt VPN/Firefox images while retaining the source policy,\n'
            'startup, login and maintenance mounts. The optional CreepJS image is\n'
            'still source-built. This tooling does not install or update a running\n'
            'stack. Release-aware installation, update and rollback acceptance must\n'
            'be complete before advertising this bundle to end users.\n').encode()


def prepare(manifest_path, evidence_path, output):
    manifest, evidence = read_json(manifest_path), read_json(evidence_path)
    validate_manifest(manifest)
    validate_evidence(manifest, evidence)
    # Read the immutable source commit, never the worktree or private local files.
    revision = git('rev-parse', '--verify', manifest['source'] + '^{commit}').decode().strip()
    require(revision == manifest['source'], 'source revision did not resolve exactly')
    prefix = 'private-browser-' + manifest['version']
    archive = git('archive', '--format=tar', '--prefix=' + prefix + '/', revision)
    check_source_files(archive, prefix)
    recipe = git('show', revision + ':docker-compose.yml')
    compose = compose_recipe(recipe, manifest['images']).encode()
    require(not output.exists() and not output.is_symlink(), 'output must be a new directory')
    output.mkdir(mode=0o700)
    payloads = {'release.json': normalized(manifest), 'evidence.json': normalized(evidence),
                'docker-compose.release.yml': compose, 'RELEASE-NOTES.md': notes(manifest),
                'source.tar.gz': gzip.compress(archive, mtime=0)}
    for name, data in payloads.items():
        (output / name).write_bytes(data)
    checksums = ''.join(digest(payloads[name]) + '  ' + name + '\n' for name in sorted(payloads))
    (output / 'SHA256SUMS').write_text(checksums)
    verify(output)


def verify(bundle):
    require(bundle.is_dir() and not bundle.is_symlink(), 'bundle must be a regular directory')
    require({p.name for p in bundle.iterdir()} == FILES, 'bundle has missing or unexpected files')
    require(all(p.is_file() and not p.is_symlink() for p in bundle.iterdir()), 'bundle files must be regular files')
    require(all(p.stat().st_size <= MAX_ARCHIVE for p in bundle.iterdir()), 'bundle file exceeds safety limit')
    require((bundle / 'SHA256SUMS').stat().st_size <= 4096, 'checksum inventory exceeds safety limit')
    lines = (bundle / 'SHA256SUMS').read_text().splitlines()
    expected = FILES - {'SHA256SUMS'}
    require(len(lines) == len(expected), 'checksum inventory is incomplete')
    seen = set()
    for line in lines:
        match = re.fullmatch('(' + SHA + r')  ([A-Za-z0-9.-]+)', line)
        require(match is not None, 'malformed checksum inventory')
        checksum, name = match.groups()
        require(name in expected and name not in seen, 'unexpected or duplicate checksum path')
        require(digest((bundle / name).read_bytes()) == checksum, 'bundle checksum mismatch')
        seen.add(name)
    manifest, evidence = read_json(bundle / 'release.json'), read_json(bundle / 'evidence.json')
    validate_manifest(manifest)
    validate_evidence(manifest, evidence)
    # Enforce archive safety even when a caller has regenerated the checksums.
    with gzip.open(bundle / 'source.tar.gz', 'rb') as compressed:
        raw = compressed.read(MAX_ARCHIVE + 1)
    prefix = 'private-browser-' + manifest['version']
    check_source_files(raw, prefix)
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as source:
        recipe = source.extractfile(prefix + '/docker-compose.yml').read()
    require((bundle / 'docker-compose.release.yml').read_text() == compose_recipe(recipe, manifest['images']),
            'release Compose differs from the protected source transformation')
    require((bundle / 'RELEASE-NOTES.md').read_bytes() == notes(manifest), 'release notes differ from reviewed metadata')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare_parser = sub.add_parser('prepare', help='prepare a local bundle from reviewed acceptance records')
    prepare_parser.add_argument('--manifest', type=Path, required=True)
    prepare_parser.add_argument('--evidence', type=Path, required=True)
    prepare_parser.add_argument('--output', type=Path, required=True)
    verify_parser = sub.add_parser('verify', help='verify local bundle consistency and checksums, not publisher authenticity')
    verify_parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            prepare(args.manifest, args.evidence, args.output)
        else:
            verify(args.bundle)
    except (Invalid, OSError, ValueError, UnicodeError, EOFError, KeyError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print('RELEASE NOT VERIFIED: ' + (str(exc) if isinstance(exc, Invalid) else 'input unavailable or malformed'), file=sys.stderr)
        return 1
    print('PASS: offline bundle consistency checks. No publication or installation was performed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
