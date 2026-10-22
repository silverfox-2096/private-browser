#!/usr/bin/env python3
"""Real pinned-helper test; synthetic password only, no production mounts or VPN."""
import importlib.util
from pathlib import Path
import subprocess
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('onboard', Path(__file__).resolve().parents[1] / 'scripts' / 'onboard.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
password = 'synthetic-test-password-only'
with patch.object(m.shutil, 'which', return_value=None):
    record = m.hash_password('fixture', password)
# Verify the actual generated hash against stdin, with only a disposable tmpfs.
command = ['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only',
           '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
           '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=1m', '--entrypoint', 'sh',
           m.helper_image(), '-c', 'IFS= read -r record; printf "%s\\n" "$record" > /tmp/login; htpasswd -vi /tmp/login fixture']
for supplied, expected in ((password, 0), ('wrong-synthetic-password', 3)):
    result = subprocess.run(command, input=record + supplied + '\n', text=True, capture_output=True, timeout=60)
    assert result.returncode == expected, 'helper password verification did not match the expected outcome'
print('PASS: pinned helper bcrypt accepts the correct synthetic password and rejects the wrong one; network disabled, no host mounts.')
