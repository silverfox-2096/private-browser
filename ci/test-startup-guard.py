#!/usr/bin/env python3
"""Exercise the real startup guard with controlled tunnel-presence and HTTP inputs.
Docker + a prebuilt Firefox image required. Network is disabled except loopback.
The /sys/class/net fixture models interface presence; separate kernel/tunnel tests
are needed for real startup/path coverage. No production containers or VPN key used.
Usage: python3 ci/test-startup-guard.py [Firefox image, default private-firefox:ci]
"""
import json
import os
from pathlib import Path
import re
import subprocess as sp
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
image = sys.argv[1] if len(sys.argv) > 1 else 'private-firefox:ci'
node = re.search(r'image: (node:\S+)', (root/'ci/pins/compose.yml').read_text())[1]
fixture_code = r'''
const fs=require('node:fs'), http=require('node:http');
http.createServer((req,res)=>{
 const c=JSON.parse(fs.readFileSync('/fixture/config.json'));
 if(c.offline){req.socket.destroy();return;}
 res.writeHead(c.status,c.status===302?{Location:'http://127.0.0.1:19999/forbidden'}:{});res.end();
}).listen(9999,'127.0.0.1');
http.createServer((req,res)=>{
 fs.appendFileSync('/fixture/forbidden','request\n');res.end();
}).listen(19999,'127.0.0.1');
'''

def docker(*args, check=True):
    return sp.run(['docker', *args], check=check, capture_output=True, text=True)

with tempfile.TemporaryDirectory(prefix='pb-startup-test-') as tmp:
    out = Path(tmp)
    fake_net = out/'net'; fake_net.mkdir()
    (out/'fixture.cjs').write_text(fixture_code)
    (out/'init').write_text('#!/bin/sh\necho initialized > /fixture/initialized\n')
    (out/'init').chmod(0o755)
    names = ['pb-guard-fixture-'+str(os.getpid()), 'pb-guard-consumer-'+str(os.getpid())]
    def config(status=200, offline=False):
        # Replace atomically so the server never reads a partially written file.
        (out/'config.next').write_text(json.dumps(dict(status=status, offline=offline)))
        (out/'config.next').replace(out/'config.json')
    def blocked(label):
        time.sleep(2.2)
        assert not (out/'initialized').exists(), label
        assert not (out/'forbidden').exists(), label+' followed redirect or proxy'
        assert docker('inspect','-f','{{.State.Running}}',names[1]).stdout.strip()=='true', label
        print('PASS '+label, flush=True)
    try:
        config()
        docker('run','-d','--name',names[0],'--network','none','-v',f'{out}:/fixture',
               node,'node','/fixture/fixture.cjs')
        docker('run','-d','--name',names[1],'--network','container:'+names[0],
               '--user',f'{os.getuid()}:{os.getgid()}','--cap-drop','ALL','--read-only',
               '-e','http_proxy=http://127.0.0.1:19999','-e','HTTP_PROXY=http://127.0.0.1:19999',
               '-v',f'{fake_net}:/sys/class/net:ro','-v',f'{root}/startup-guard.sh:/guard:ro',
               '-v',f'{out}/init:/init:ro','-v',f'{out}:/fixture',
               '--entrypoint','/bin/sh',image,'/guard')
        blocked('HTTP200 without tunnel presence blocks initialization')
        config(500); (fake_net/'tun0').touch()
        blocked('HTTP500 blocks initialization')
        config(302); blocked('redirect blocks initialization without target request')
        config(204); blocked('HTTP204 cannot substitute for exact200')
        config(offline=True); blocked('unavailable HTTP response blocks initialization')
        config()
        end=time.monotonic()+8
        while not (out/'initialized').exists() and time.monotonic()<end: time.sleep(.1)
        assert (out/'initialized').read_text().strip()=='initialized'
        assert not (out/'forbidden').exists()
        assert docker('wait',names[1]).stdout.strip()=='0'
        print('PASS exact200 and tunnel presence initialize; proxy variables ignored',flush=True)
        docker('rm',names[1]); (out/'initialized').unlink(); (fake_net/'tun0').unlink()
        docker('run','-d','--name',names[1],'--network','none','--user',f'{os.getuid()}:{os.getgid()}',
               '--cap-drop','ALL','--read-only','-v',f'{fake_net}:/sys/class/net:ro',
               '-v',f'{root}/startup-guard.sh:/guard:ro','-v',f'{out}/init:/init:ro',
               '-v',f'{out}:/fixture','--entrypoint','/bin/sh',image,'/guard')
        result=sp.run(['docker','wait',names[1]],capture_output=True,text=True,timeout=90,check=True)
        assert result.stdout.strip()=='1' and not (out/'initialized').exists()
        print('PASS persistent missing readiness exits1 without initialization',flush=True)
    except BaseException:
        print(docker('logs',names[1],check=False).stdout, file=sys.stderr)
        print(docker('logs',names[1],check=False).stderr, file=sys.stderr)
        raise
    finally:
        for name in names: docker('rm','-f',name,check=False)
