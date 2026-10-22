#!/usr/bin/env python3
"""Local onboarding. Never source provider files or display Docker configuration."""
import argparse
import base64
import configparser
import contextlib
import fcntl
import getpass
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
NAMES = ('gluetun-proton', 'private-firefox', 'creepjs-server')
LOCK_FD = None
SECRET_KEYS = ('WIREGUARD_PRIVATE_KEY', 'WIREGUARD_ADDRESSES', 'GLUETUN_API_KEY')
DOCKER_HELP = 'Start Docker, then retry. Installation help: https://docs.docker.com/engine/install/'


def project_name():
    return 'private-browser-' + hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]


def releases():
    spec = importlib.util.spec_from_file_location('pb_release_mode', ROOT / 'scripts' / 'release_mode.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Releases(SimpleNamespace(**globals()))


def compose_path():
    if any(path.exists() or path.is_symlink() for path in (ROOT / '.pb-release.json', ROOT / 'docker-compose.release.yml')):
        releases().state()
        return ROOT / 'docker-compose.release.yml'
    return ROOT / 'docker-compose.yml'


class Problem(Exception):
    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


class OperationRunning(Problem):
    """A mutating child is still live and retains the operation lock."""


def run(args, *, data=None, timeout=30, env=None, managed=False):
    """Capture output; errors never echo arbitrary tool output or input secrets."""
    if managed:
        if data is not None:
            raise Problem('Managed lifecycle commands do not accept secret input.')
        return subprocess.CompletedProcess(args, managed_process(args, timeout=timeout, env=env), '', '')
    try:
        return subprocess.run(args, cwd=ROOT, input=data, text=True,
                              capture_output=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Problem('A required command was unavailable or timed out. Run ./pb doctor.') from exc


def docker(*args, timeout=30):
    result = run(['docker', *args], timeout=timeout)
    if result.returncode:
        raise Problem('Docker could not complete an observation. ' + DOCKER_HELP, 3)
    return result.stdout


def prerequisites():
    if sys.version_info < (3, 10):
        raise Problem('Python 3.10 or newer is required.')
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise Problem('Guided setup currently targets Linux x86-64. Other platforms are not validated; see QUICKSTART.md.')
    if os.geteuid() == 0:
        raise Problem('Run guided setup as your normal user, with Docker access; do not run the whole wizard as root.')
    for tool in ('docker', 'bash', 'curl', 'readlink', 'timeout'):
        if not shutil.which(tool):
            raise Problem('Missing required tool: ' + tool + '. See QUICKSTART.md.')
    # Environment/context overrides can redirect binds and lifecycle operations.
    # Refuse ambiguity rather than quietly talking to a different daemon/project.
    for key in ('COMPOSE_FILE', 'COMPOSE_PROJECT_NAME', 'COMPOSE_ENV_FILES', 'COMPOSE_PROFILES',
                'COMPOSE_DISABLE_ENV_FILE', 'DOCKER_HOST', 'DOCKER_CONTEXT'):
        if os.environ.get(key):
            raise Problem('Unset ' + key + ' in this terminal before using guided setup.')
    try:
        context = docker('context', 'show').strip()
        endpoint = json.loads(docker('context', 'inspect', context,
                                    '--format', '{{json .Endpoints.docker.Host}}'))
        info = json.loads(docker('info', '--format', '{{json .}}'))
    except (ValueError, KeyError, TypeError) as exc:
        raise Problem('Docker information is incomplete. ' + DOCKER_HELP, 3) from exc
    if not isinstance(endpoint, str) or not endpoint.startswith('unix://'):
        raise Problem('Guided setup requires a local Unix-socket Docker engine.')
    if not isinstance(info, dict):
        raise Problem('Docker information is incomplete. ' + DOCKER_HELP, 3)
    if info.get('OSType') != 'linux' or info.get('Architecture') not in ('x86_64', 'amd64'):
        raise Problem('Guided setup requires a Linux x86-64 Docker engine.')
    if 'docker desktop' in str(info.get('OperatingSystem', '')).lower():
        raise Problem('Docker Desktop has not been validated for this initial guided path.')
    security = info.get('SecurityOptions')
    if not isinstance(security, list) or not all(isinstance(x, str) for x in security):
        raise Problem('Docker security-mode information is incomplete.', 3)
    if any('rootless' in x for x in security):
        raise Problem('Rootless Docker has not been validated for this VPN/firewall setup.')
    if not Path('/dev/net/tun').exists():
        raise Problem('The Linux TUN device is missing. See QUICKSTART.md; setup will not change the host.')
    if run(['docker', 'compose', 'version']).returncode:
        raise Problem('Docker Compose v2 or newer is required. See QUICKSTART.md.')
    return info


def private_file(path):
    """Refuse links, special files and loose permissions; never print contents."""
    try:
        meta = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
        raise Problem(path.name + ' must be a regular file, not a link or directory.')
    if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) & 0o077:
        raise Problem(path.name + ' must belong to you and be private. Review it, then use chmod 600 ' + path.name + '.')
    return True


def create_private(path, content):
    """Publish a complete 0600 file without replacing an existing path."""
    name = None
    try:
        fd, name = tempfile.mkstemp(prefix='.pb-secret-', dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(name, path)  # atomic, refuses existing files and symlinks
    except FileExistsError as exc:
        raise Problem(path.name + ' appeared during setup. Existing data was preserved; rerun setup.') from exc
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def valid_key(value):
    try:
        return len(base64.b64decode(value, validate=True)) == 32 and len(value) == 44
    except (ValueError, TypeError):
        return False


def valid_addresses(value):
    try:
        addresses = value.split(',')
        return bool(addresses) and all('/' in x and ipaddress.ip_interface(x).version == 4 for x in addresses)
    except ValueError:
        return False


def country(value):
    if not re.fullmatch(r'[A-Za-z][A-Za-z ]{1,63}', value):
        raise Problem('Use a country name containing letters and spaces, for example Singapore.')
    return value


def import_wireguard(path):
    """Import only the Proton interface credentials; never copy provider hooks."""
    try:
        if path.stat().st_size > 65536:
            raise Problem('The selected configuration is too large; choose a WireGuard .conf file.')
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.read_string(path.read_text(encoding='utf-8'))
        if parser.sections() != ['Interface', 'Peer'] or parser.defaults():
            raise ValueError('unexpected sections')
        supported = {'Interface': {'privatekey', 'address', 'dns', 'mtu'},
                     'Peer': {'publickey', 'presharedkey', 'allowedips', 'endpoint', 'persistentkeepalive'}}
        for section in parser.sections():
            if set(parser[section]) - supported[section]:
                raise Problem('This config contains unsupported options or hooks. Nothing was executed; use a standard Proton WireGuard config.')
        key = parser['Interface']['PrivateKey'].strip()
        address = ','.join(x.strip() for x in parser['Interface']['Address'].split(','))
        if not valid_key(key) or not valid_addresses(address):
            raise ValueError('invalid interface credentials')
        return key, address
    except (OSError, UnicodeError, ValueError, KeyError, configparser.Error) as exc:
        raise Problem('Could not import valid IPv4 WireGuard credentials. Choose an unmodified Proton .conf file; its contents were not printed.') from exc


def environment():
    path = ROOT / '.env'
    if not private_file(path):
        return None
    values = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, sep, value = line.partition('=')
            if not sep or key in values or key not in (*SECRET_KEYS, 'VPN_SERVICE_PROVIDER', 'SERVER_COUNTRIES'):
                raise ValueError('unsupported syntax')
            # Deliberately support only simple literal dotenv values. Never source.
            if value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            if any(x in value for x in ('$', '`', '\\', '"', "'", '\x00')):
                raise ValueError('nonliteral value')
            values[key] = value
        if not valid_key(values.get('WIREGUARD_PRIVATE_KEY')) or not valid_addresses(values.get('WIREGUARD_ADDRESSES', '')):
            raise ValueError('invalid credentials')
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', values.get('GLUETUN_API_KEY', '')):
            raise ValueError('invalid control key')
        if values.get('VPN_SERVICE_PROVIDER', 'protonvpn') != 'protonvpn':
            raise Problem('The wizard currently supports Proton only. Existing configuration was preserved; use the manual guide for other providers.')
        country(values.get('SERVER_COUNTRIES', 'Singapore'))
    except (ValueError, OSError, UnicodeError) as exc:
        raise Problem('Existing .env needs review. It was preserved and not printed; see QUICKSTART.md for supported values.') from exc
    for key in (*SECRET_KEYS, 'VPN_SERVICE_PROVIDER', 'SERVER_COUNTRIES'):
        if key in os.environ:
            raise Problem('Unset ' + key + ' in this terminal so it cannot override the local .env.')
    return values


def login_exists():
    path = ROOT / 'webauth-htpasswd'
    if not private_file(path):
        return False
    try:
        content = path.read_text()
    except (OSError, UnicodeError) as exc:
        raise Problem('Cannot read the existing login file; it was preserved.') from exc
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}:\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}\n?', content):
        raise Problem('Existing login file needs review. Expected one bcrypt login; it was preserved.')
    return True


def owned_containers(expected_recipe=None):
    """Inspect labels only; no Config.Env, logs or credentials in diagnostics."""
    names = set(docker('ps', '-a', '--format', '{{.Names}}').splitlines())
    owned = []
    for name in NAMES:
        if name not in names:
            continue
        try:
            labels = json.loads(docker('inspect', '--format', '{{json .Config.Labels}}', name)) or {}
        except (ValueError, TypeError) as exc:
            raise Problem('Container ownership could not be read; no changes made.', 3) from exc
        if not isinstance(labels, dict):
            raise Problem('Container ownership could not be read; no changes made.', 3)
        workdir = labels.get('com.docker.compose.project.working_dir', '')
        configs = labels.get('com.docker.compose.project.config_files', '')
        if (workdir != str(ROOT) or configs != str(expected_recipe or compose_path())
                or labels.get('com.docker.compose.project') != project_name()):
            raise Problem('An existing Private Browser container belongs to another checkout or uses overrides. No changes made; use its original installation.')
        owned.append(name)
    return owned


def port_available():
    try:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 7814))
    except OSError as exc:
        raise Problem('Port 7814 is already occupied. Close the other application or use its existing installation.') from exc


def compose_environment():
    result = os.environ.copy()
    # Never accept shell-injected provider credentials in the guided path.
    for key in (*SECRET_KEYS, 'VPN_SERVICE_PROVIDER', 'SERVER_COUNTRIES'):
        if key in result:
            raise Problem('Unset ' + key + ' in this terminal before continuing.')
    result['COMPOSE_PROJECT_NAME'] = project_name()
    return result


def compose(*args, timeout=1800):
    result = run(['docker', 'compose', '--project-directory', str(ROOT),
                  '-f', str(compose_path()), *args],
                 timeout=timeout, env=compose_environment(), managed=True)
    if result.returncode:
        raise Problem('The build or container operation failed. Your credentials were preserved. Run ./pb doctor; retry ./setup.sh after resolving the cause.', result.returncode if result.returncode in (3, 130) else 1)
    return result


@contextlib.contextmanager
def setup_lock():
    global LOCK_FD
    path = ROOT / '.pb-setup.lock'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Problem('Setup lock is not a regular file.')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Problem('Another setup or lifecycle command is running; wait for it to finish.') from exc
        LOCK_FD = fd
        yield
    finally:
        LOCK_FD = None
        os.close(fd)


def confirm(message):
    if not sys.stdin.isatty():
        raise Problem('Use an interactive terminal for setup and destructive operations. Secrets are never accepted as command arguments.')
    return input(message + ' [y/N] ').strip().lower() in ('y', 'yes')


def helper_image():
    # The standard-library reader deliberately accepts only the pinned Official
    # httpd 2.4 helper. Dependabot maintains its reference in the shared manifest.
    try:
        references = re.findall(r'^    image: (httpd:2\.4(?:\.\d+)?-alpine@sha256:[0-9a-f]{64})$',
                                (ROOT / 'ci' / 'pins' / 'compose.yml').read_text(), re.MULTILINE)
    except (OSError, UnicodeError) as exc:
        raise Problem('The login-helper pin is missing; restore ci/pins/compose.yml from the repository.') from exc
    if len(references) != 1:
        raise Problem('The login-helper pin needs review; expected one digest-pinned official httpd 2.4 image.')
    return references[0]


def hash_password(username, password):
    if shutil.which('htpasswd'):
        command = ['htpasswd', '-nBi', username]
    else:
        helper = helper_image()
        print('Preparing the pinned login helper (no host files are mounted).', flush=True)
        if run(['docker', 'pull', helper], timeout=300).returncode:
            raise Problem('Could not download the login helper. Retry, or install apache2-utils; see QUICKSTART.md.')
        command = ['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only',
                   '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                   '--entrypoint', 'htpasswd', helper, '-nBi', username]
    result = run(command, data=password + '\n', timeout=60)
    if result.returncode or not re.fullmatch(re.escape(username) + r':\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}\s*', result.stdout):
        raise Problem('Could not create the bcrypt login. No password was printed or saved.')
    return result.stdout.strip() + '\n'


def setup(configure_only=False, release_bundle=None):
    prerequisites()
    owned = owned_containers()
    if (ROOT / 'maintenance' / 'active').exists():
        raise Problem('A maintenance gate is active. Use the existing installation recovery guide.')
    # Rerun is configuration-preserving and never recreates a running container.
    if owned:
        if not environment():
            raise Problem('This installation already has containers but .env is missing; restore it before continuing.')
        if not login_exists():
            raise Problem('This installation already has containers but its login file is missing; restore it before continuing.')
        print('Existing installation preserved. Use ./pb status or ./pb doctor; setup did not restart it.')
        return 0
    if release_bundle is not None:
        releases().candidate(release_bundle)
    port_available()
    values = environment()
    has_login = login_exists()
    if not values or not has_login:
        if not sys.stdin.isatty():
            raise Problem('Run ./setup.sh in an interactive terminal. Do not paste secrets into commands.')
        print('Private Browser setup — Proton VPN on Linux x86-64.\n'
              'Your VPN credentials stay on this machine. Stopping erases the browser session.\n'
              'Existing files will be preserved. No host settings will be changed.')
    pending = {}
    if not values:
        print('Use a Proton WireGuard config downloaded from your own account.\n'
              'Only its private key and IPv4 address are imported; DNS, peers and hooks are not applied.\n'
              'The VPN server is selected by country using Gluetun’s Proton integration.')
        if not confirm('Is this a Proton VPN configuration?'):
            raise Problem('Nothing changed. Other providers use the manual setup guide.')
        path = Path(input('Path to your WireGuard .conf file (keep it outside this repo): ').strip()).expanduser().resolve()
        if path == ROOT or ROOT in path.parents:
            raise Problem('Keep the provider file outside this repository so it cannot enter a commit or image build.')
        key, address = import_wireguard(path)
        selected = country(input('Exit country [Singapore]: ').strip() or 'Singapore')
        values = {'WIREGUARD_PRIVATE_KEY': key, 'WIREGUARD_ADDRESSES': address,
                  'GLUETUN_API_KEY': secrets.token_hex(32), 'VPN_SERVICE_PROVIDER': 'protonvpn',
                  'SERVER_COUNTRIES': selected}
        compose_environment()
        pending['.env'] = '# Created locally by setup. Never share or commit this file.\n' + ''.join(k + "='" + v + "'\n" for k, v in values.items())
    if not has_login:
        username = input('Browser login username [browser]: ').strip() or 'browser'
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}', username):
            raise Problem('Use 1–32 letters, numbers, dots, underscores or hyphens; start the username with a letter, number or underscore.')
        password = getpass.getpass('Browser password (hidden; at least 12 characters): ')
        again = getpass.getpass('Repeat browser password: ')
        if password != again or len(password) < 12 or len(password.encode('utf-8')) > 72 or any(x in password for x in ('\n', '\r', '\x00')):
            raise Problem('Passwords must match, contain at least 12 characters and fit bcrypt’s 72-byte limit. Nothing was saved.')
        pending['webauth-htpasswd'] = hash_password(username, password)
        del password, again
    for name, content in pending.items():
        create_private(ROOT / name, content)
    if release_bundle is not None:
        releases().stage(release_bundle)
    print('Local configuration is ready. Existing credentials were preserved.', flush=True)
    if configure_only:
        print('Nothing was built or started. Next: ./pb start')
        return 0
    if not confirm('Build and start now? The first build downloads images and packages and may take several minutes.'):
        print('Configuration saved. Start later with ./pb start.')
        return 0
    return start(build=True)


def start(build=False):
    owned = owned_containers()
    if not environment() or not login_exists():
        raise Problem('Setup is incomplete. Run ./setup.sh first.')
    if (ROOT / 'maintenance' / 'active').exists():
        raise Problem('Private Browser is under maintenance. See the recovery guide before changing the gate.')
    if not owned:
        port_available()
    release = releases() if (ROOT / '.pb-release.json').exists() else None
    identities = None
    if release:
        print('Preparing the selected immutable release images…', flush=True)
        identities = release.pull(release.state()['active'])
    else:
        print('Building images. Progress is captured locally; credentials are never printed.', flush=True)
    # Initial build explicitly includes the locally patched VPN, whose pull policy
    # is never. On subsequent starts Compose reuses existing images.
    if not release and (build or not owned):
        compose('build', 'gluetun', 'firefox')
    print('Starting and checking the VPN, browser and firewall policy…', flush=True)
    # Existing launch.sh owns readiness and trusted policy verdicts. Explicit
    # compose flags here and sanitized environment prevent implicit overrides.
    env = compose_environment()
    env['COMPOSE_FILE'] = str(compose_path())
    env['PB_NO_OPEN'] = '1'
    result = run(['bash', str(ROOT / 'launch.sh')], timeout=180, env=env, managed=True)
    if result.returncode:
        code = result.returncode if result.returncode in (1, 3) else 3
        raise Problem('Startup or firewall verification did not complete successfully. Run ./pb doctor; do not treat this as a successful privacy check.', code)
    if release:
        release.assert_images(identities)
        if release.http_status() != '302':
            raise Problem('The release login redirect did not verify. The browser was not opened; run ./pb doctor and review RELEASING.md.', 3)
    open_browser()
    print('READY: VPN health, browser response and local-app policy passed.\n'
          'Open https://127.0.0.1:7814 and use your browser login.\n'
          'The local HTTPS certificate is self-signed; see QUICKSTART.md.\n'
          'Real-VPN leak verification is separate: save your work, close the viewer, then ./pb verify.')
    return 0


def open_browser():
    if shutil.which('xdg-open'):
        try:
            run(['xdg-open', 'https://127.0.0.1:7814'], timeout=10)
        except Problem:
            pass  # Readiness succeeded; the printed URL remains usable.


def managed_process(args, *, timeout, env):
    """Keep the mutation lock and allow child recovery after Ctrl+C/timeouts."""
    try:
        process = subprocess.Popen(args, cwd=ROOT, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   pass_fds=(() if LOCK_FD is None else (LOCK_FD,)))
        try:
            process.wait(timeout=timeout)
        except KeyboardInterrupt:
            previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                # The terminal also delivers SIGINT to the child. Its existing
                # verify.sh trap restores the tunnel; wait without killing it.
                print('\nWaiting for the operation’s restoration steps. Do not start another command.', flush=True)
                process.wait(timeout=180)
            finally:
                signal.signal(signal.SIGINT, previous)
            return 130
        return process.returncode
    except subprocess.TimeoutExpired as exc:
        raise OperationRunning('The operation is taking too long and may still be running. It was not killed. Do not start another operation; inspect the original process before recovery.', 3) from exc


def lifecycle(script):
    """Let existing restoration traps finish after Ctrl+C; never kill them."""
    env = compose_environment()
    env['COMPOSE_FILE'] = str(compose_path())
    return managed_process(['bash', str(ROOT / script)], timeout=1800, env=env)


def status():
    owned = owned_containers()
    if not owned:
        print('STOPPED: no containers from this installation are present. Start with ./pb start.')
        return 0
    for name in owned:
        raw = docker('inspect', '--format', '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}', name).strip()
        # Accept known vocabulary only, not arbitrary output in diagnostics.
        if not re.fullmatch(r'[a-z]+(?: [a-z]+)?', raw):
            raise Problem('Container state is unreadable.', 3)
        print(name + ': ' + raw)
    print('Status is an observation, not a VPN leak-test result.')
    return 0


def doctor():
    prerequisites()
    print('PASS: supported host prerequisites and local Docker access.')
    if not environment() or not login_exists():
        raise Problem('Setup is incomplete. Run ./setup.sh first.')
    print('PASS: private configuration and bcrypt login are present (contents hidden).')
    if (ROOT / '.pb-release-transaction.json').exists() or (ROOT / '.pb-release-transaction.json').is_symlink():
        raise Problem('A release transaction needs recovery. Let any running operation finish, close the viewer, then use ./pb rollback.', 3)
    if (ROOT / 'maintenance' / 'active').exists():
        raise Problem('Maintenance gate is active. See QUICKSTART.md before recovery.', 3)
    owned = owned_containers()
    if not owned:
        port_available()
        print('STOPPED: configuration is ready; run ./pb start. No containers were started or changed.')
        return 0
    status()
    result = run([sys.executable, str(ROOT / 'check-local-app-policy.py')], timeout=150)
    if result.returncode:
        raise Problem('Local-app policy did not pass. Avoid browsing and consult LOCAL-APP-POLICY.md.', 1 if result.returncode == 1 else 3)
    print('PASS: maintained local-app policy check. No containers were restarted.\n'
          'Doctor does not perform the disruptive VPN leak checks.')
    return 0


def main():
    parser = argparse.ArgumentParser(description='Private Browser: setup, daily commands and private diagnostics.')
    parser.add_argument('command', choices=('setup', 'start', 'status', 'doctor', 'stop', 'update', 'verify', 'rollback'))
    parser.add_argument('--configure-only', action='store_true', help='setup: save credentials without building or starting')
    parser.add_argument('--release', type=Path, help='setup/update: local verified prebuilt release bundle (publisher/provenance must be reviewed)')
    args = parser.parse_args()
    if args.configure_only and args.command != 'setup':
        parser.error('--configure-only is only valid with setup')
    if args.release is not None and args.command not in ('setup', 'update'):
        parser.error('--release is only valid with setup or update')
    try:
        if args.command == 'status':
            prerequisites()
            return status()
        if args.command == 'doctor':
            return doctor()
        with setup_lock():
            if ((ROOT / '.pb-release-transaction.json').exists() or (ROOT / '.pb-release-transaction.json').is_symlink()) and args.command != 'rollback':
                raise Problem('A release transition is incomplete. Preserve maintenance and run ./pb rollback after closing the viewer.')
            if args.command == 'setup':
                return setup(args.configure_only, args.release)
            prerequisites()
            if args.command == 'rollback':
                if not environment() or not login_exists():
                    raise Problem('Restore the original private configuration before rollback.')
                if not confirm('Have you saved your work and closed the viewer? Rollback restarts the browser and erases its current session.'):
                    print('Cancelled. Nothing changed.')
                    return 0
                return releases().recover()
            if args.command == 'start':
                return start()
            owned = owned_containers()
            if not owned:
                raise Problem('This installation is stopped. Start it with ./pb start.')
            if not environment() or not login_exists():
                raise Problem('Configuration is incomplete. Restore the original private files before continuing.')
            if (ROOT / 'maintenance' / 'active').exists():
                raise Problem('A maintenance gate is active. Finish existing maintenance first.')
            message = {'stop': 'Stop Private Browser and erase its bookmarks, downloads, logins and history?',
                       'update': 'Have you saved your work and closed the viewer? Updating interrupts the browser.',
                       'verify': 'Have you saved your work and closed the viewer? Verification stops the VPN and restarts Firefox.'}[args.command]
            if not confirm(message):
                print('Cancelled. Nothing changed.')
                return 0
            if args.command == 'update' and args.release is not None:
                return releases().update(args.release)
            if args.command == 'update' and (ROOT / '.pb-release.json').exists():
                raise Problem('This is a pinned release installation. Use ./pb update --release BUNDLE; source rebuilding was refused.')
            if args.command == 'stop':
                compose('down', timeout=180)
                print('STOPPED. The browser session was erased; local VPN and login credentials were preserved.')
                return 0
            script = 'update.sh' if args.command == 'update' else 'verify.sh'
            rc = lifecycle(script)
            if rc:
                raise Problem('The operation did not pass. Run ./pb doctor. No success is claimed.', rc if rc in (1, 2, 3, 130) else 3)
            print('UPDATED: maintained update/readiness/policy checks passed.' if args.command == 'update'
                  else 'PASS: maintained network checks passed. Browser WebRTC/DNS checks remain separate; see QUICKSTART.md.')
            return 0
    except Problem as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled. Existing files were preserved. Rerun ./setup.sh or ./pb doctor to inspect any partial setup.', file=sys.stderr)
        return 130
    except (OSError, UnicodeError):
        print('A local file or command could not be accessed. Existing files were preserved; run ./pb doctor.', file=sys.stderr)
        return 3


if __name__ == '__main__':
    sys.exit(main())
