#!/usr/bin/env python3
"""Record the actual configure-only CLI using synthetic credentials and discovery/port fixtures.

No actual Docker command runs. Requires Linux /dev/net/tun and host htpasswd.
The rendered transcript and asciinema recording are illustrations, not VPN evidence.
"""
import base64
import errno
import html
import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'onboarding'
OUT.mkdir(parents=True, exist_ok=True)
if not shutil.which('htpasswd') or not Path('/dev/net/tun').exists():
    sys.exit('Recording needs host htpasswd and /dev/net/tun; no host changes were made.')
with tempfile.TemporaryDirectory(prefix='pb-onboarding-demo-') as temp:
    base = Path(temp)
    repo = base / 'private-browser'
    repo.mkdir()
    shutil.copytree(ROOT / 'scripts', repo / 'scripts')
    shutil.copy2(ROOT / 'setup.sh', repo / 'setup.sh')
    (repo / 'docker-compose.yml').write_text('services: {}\n')
    config = base / 'provider.conf'
    key = base64.b64encode(bytes(range(32))).decode()
    config.write_text('[Interface]\nPrivateKey=' + key + '\nAddress=10.2.0.2/32\n[Peer]\nPublicKey=' + key + '\nEndpoint=example.invalid:51820\nAllowedIPs=0.0.0.0/0\n')
    binary = base / 'bin'
    binary.mkdir()
    fake = binary / 'docker'
    fake.write_text('''#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]
if args==['context','show']: print('default')
elif args[:2]==['context','inspect']: print(json.dumps('unix:///var/run/docker.sock'))
elif args[0]=='info': print(json.dumps({'OSType':'linux','Architecture':'amd64','SecurityOptions':['name=seccomp'],'OperatingSystem':'Synthetic discovery fixture'}))
elif args[:2]==['compose','version']: print('Docker Compose discovery fixture')
elif args[:2]==['ps','-a']: pass
else: sys.exit('Unexpected Docker call in configuration-only demo')
''')
    fake.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('COMPOSE_', 'DOCKER_')) and k not in ('WIREGUARD_PRIVATE_KEY', 'WIREGUARD_ADDRESSES', 'GLUETUN_API_KEY', 'SERVER_COUNTRIES', 'VPN_SERVICE_PROVIDER')}
    env['PATH'] = str(binary) + ':' + os.environ['PATH']
    driver = base / 'demo-driver.py'
    driver.write_text('import importlib.util,sys\ns=importlib.util.spec_from_file_location("onboard",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nm.port_available=lambda:None\nsys.argv=[sys.argv[1],"setup","--configure-only"]\nsys.exit(m.main())\n')
    master, slave = pty.openpty()
    proc = subprocess.Popen([sys.executable, str(driver), str(repo / 'scripts' / 'onboard.py')], cwd=repo, env=env, stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    intro = 'CONFIGURATION-ONLY DEMO — synthetic credentials; Docker discovery/port checks simulated.\r\n$ ./setup.sh --configure-only\r\n'
    events = [[0.0, 'o', intro]]
    transcript = intro
    prompts = [('Is this a Proton VPN configuration?', 'y\n'), ('Path to your WireGuard', str(config) + '\n'), ('Exit country', 'Singapore\n'), ('Browser login username', 'browser\n'), ('Browser password (hidden', 'synthetic-demo-password\n'), ('Repeat browser password', 'synthetic-demo-password\n')]
    index = 0
    since = ''
    started = time.monotonic()
    deadline = started + 20
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([master], [], [], .2)
            if readable:
                try:
                    data = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno == errno.EIO: break
                    raise
                if not data: break
                chunk = data.decode('utf-8')
                transcript += chunk
                since += chunk
                events.append([round(time.monotonic() - started, 3), 'o', chunk])
                if index < len(prompts) and prompts[index][0] in since:
                    # Pause for playback readability; hidden password input is never recorded.
                    time.sleep(.6)
                    os.write(master, prompts[index][1].encode())
                    index += 1
                    since = ''
            elif proc.poll() is not None: break
        rc = proc.wait(timeout=3)
        if rc or index != len(prompts) or 'Nothing was built or started.' not in transcript:
            raise RuntimeError('Demonstration did not complete: ' + transcript)
        if key in transcript or 'synthetic-demo-password' in transcript:
            raise RuntimeError('Secret unexpectedly appeared in captured output')
    finally:
        os.close(master)
        if proc.poll() is None: proc.kill(); proc.wait()
    (OUT / 'setup.cast').write_text(json.dumps({'version': 2, 'width': 120, 'height': 32, 'title': 'Synthetic configuration-only demonstration; no VPN started', 'env': {'TERM':'xterm-256color'}}) + '\n' + ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events))
    (OUT / 'setup-transcript.txt').write_text('\n'.join(line.rstrip() for line in transcript.replace('\r', '').splitlines()) + '\n')
    # Code-native SVG renders the captured terminal text; no browser screenshot is implied.
    import textwrap
    lines = []
    for line in transcript.replace('\r', '').splitlines(): lines.extend(textwrap.wrap(line, width=112, replace_whitespace=False) or [''])
    height = 112 + len(lines) * 22
    content = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="' + str(height) + '" viewBox="0 0 1280 ' + str(height) + '"><rect width="100%" height="100%" rx="16" fill="#101923"/><text x="32" y="38" font-family="sans-serif" font-size="18" fill="#8ed1be">Private Browser · recorded configuration-only demonstration</text><text x="32" y="65" font-family="sans-serif" font-size="15" fill="#b4c1ce">Synthetic credentials · Docker discovery/port checks simulated · no VPN started</text>'
    for i, line in enumerate(lines[1:]): content += '<text x="32" y="' + str(103 + i * 22) + '" font-family="monospace" font-size="17" fill="#e6edf3">' + html.escape(line) + '</text>'
    (OUT / 'setup.svg').write_text(content + '</svg>\n')
    print('PASS: actual wizard prompts recorded in a discovery/port fixture, passwords hidden, no Docker lifecycle call; synthetic demo assets saved.')
