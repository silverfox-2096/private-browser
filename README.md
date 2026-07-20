# Private Browser (VPN-tunneled, fingerprint-hardened)

Firefox in a Docker container whose only network path is a WireGuard VPN tunnel.
If the tunnel drops, the browser has no route anywhere, not even to your LAN. The
profile lives in RAM and is wiped every time you stop the stack.

Built from three existing images: [Gluetun](https://github.com/qdm12/gluetun) for
the VPN and kill switch, [jlesage/firefox](https://github.com/jlesage/docker-firefox)
for Firefox over a VNC web UI, and Firefox's own `resistFingerprinting`.

> Last verified: 2026-07-20 (Firefox 151, Gluetun v3.40). This is a security
> tool; if that date looks old, treat it as unverified.

## No application code to audit

This repository has no application code to audit or trust. It is a Docker Compose
file that wires together three existing, independently maintained images (Gluetun,
jlesage/firefox, and nginx), plus a short Dockerfile that installs a few fonts and
two small shell scripts. None of it runs custom logic on your data, opens a service
written for this project, or parses untrusted input.

That is deliberate, and it removes the usual worry about quickly assembled or
AI-assisted repos: the common failure modes (vulnerable auth code, injection,
insecure endpoints) cannot exist here, because there is no such code. The whole risk surface
is the configuration, meaning how secrets are handled, which ports are exposed, and
whether the kill switch holds. That surface is small, it is all visible in
`docker-compose.yml`, and an independent security review found no vulnerabilities.
You do not have to take that on faith. Read the compose file, and run the checks
under [Verify it works](#verify-it-works) yourself.

## What it does and doesn't do

It gives you privacy. Your ISP, your LAN, and the sites you visit cannot see your
real IP or link your traffic to your connection.

It does not give you anonymity. Your VPN provider can still see your traffic and
could be compelled to log it. If you need an identity that nobody, including your
VPN, can trace back to you, use Tor instead.

It does not protect you from a compromised host. The container shields your host
from the browser (exploit containment), but not the browser from the host. A
keylogger on your machine sees everything before it reaches Firefox.

## How it works

Firefox has no network interface of its own. It shares Gluetun's network namespace
(`network_mode: service:gluetun`). Gluetun holds the WireGuard tunnel and a firewall
kill switch (`FIREWALL_OUTBOUND_SUBNETS: ""`) that drops all non-tunnel traffic. The
kill switch is part of the network layout, so it cannot silently fail the way a
toggle might: if Gluetun is not up, there is no route.

Because the containers share one namespace, all ports are published on the gluetun
service, and everything binds to `127.0.0.1`. Nothing is exposed to your LAN.

## Requirements

- Docker and Docker Compose
- A WireGuard config from any
  [Gluetun-supported provider](https://github.com/qdm12/gluetun/wiki). This example
  uses Proton VPN.

## Setup

1. Create your `.env` from the template and lock it down:
   ```
   cp .env.example .env
   chmod 600 .env
   ```
   Fill in `WIREGUARD_PRIVATE_KEY` and `WIREGUARD_ADDRESSES` from your provider's
   WireGuard config file, and choose a strong `VNC_PASSWORD`.
2. Optionally, set `SERVER_COUNTRIES` in `docker-compose.yml` to your preferred exit
   country.
3. Build and start:
   ```
   ./launch.sh
   ```
   (or `docker compose up -d`)
4. Open https://127.0.0.1:7814, accept the self-signed cert, and enter your
   `VNC_PASSWORD`.

## Daily use

Start the stack with `./launch.sh` and stop it with `docker compose down`. Stopping
wipes the profile (bookmarks, logins, history, cookies) by design; downloads survive
in `./firefox-downloads/`. The tunnel stays up whenever the stack runs, so remove
`restart: unless-stopped` from the services if you want it to run only on demand.

## Verify it works

Do not trust the config; test it:

```
# tunnel up, exiting the country you expect
docker exec gluetun-proton wget -qO- https://ipinfo.io/json

# kill switch: stop the tunnel, the browser must lose all connectivity
docker stop gluetun-proton      # UI shows "Reconnecting..."
docker compose up -d
```

In the container browser, also confirm there is no WebRTC leak (browserleaks.com/webrtc
should report "No Leak" with a blank local IP) and no DNS leak (the extended test at
dnsleaktest.com should show your DoT resolver, never your ISP).

## Optional: self-hosted fingerprint test (CreepJS)

The `creepjs` service is disabled by default. To use it, put a CreepJS build in
`./creepjs/docs/` and start the `test` profile:

```
docker compose --profile test up -d creepjs
# then browse to http://localhost:8080 in the container browser
```

Only the official CreepJS is trustworthy: <https://github.com/abrahamjuliot/creepjs>.
Some sites impersonating it are honeypots that harvest fingerprints, so self-hosting
keeps your fingerprint on your own machine.

## Design decisions worth understanding first

Changing any of these without reading can break the stack or weaken it.

| Setting | Why it is set this way |
|---|---|
| `BLOCK_MALICIOUS: "off"` | Turning it on can push Gluetun's DNS resolver into a restart loop on some providers, so DNS stops resolving. Your provider's own malware blocking already covers this. |
| `FIREWALL_OUTBOUND_SUBNETS: ""` | Blocks LAN access too, which is what makes the kill switch total. |
| Ports on `gluetun`, `127.0.0.1:` prefix | They have to live on Gluetun (shared namespace) and stay loopback-bound, never exposed to the LAN. |
| `SECURE_CONNECTION: 1` and `VNC_PASSWORD` | TLS and authentication on the VNC web UI. |
| `/config` as a quoted tmpfs, `mode=0755` | Ephemeral profile. Keep the quotes: YAML otherwise strips the leading zero from `0755` and the container will not start. |
| `webgl.disabled=true` | Removes an identifying WebGL hash. Breaks 3D sites and web maps. |
| Gluetun pinned to `v3.40` | Update deliberately. In v3.41+ the control-server route `/v1/openvpn/status` becomes `/v1/vpn/status`, so update the healthcheck if you bump the version. |
| Firefox built locally | Adds fonts so you do not stand out with a near-empty font set. One consequence: `docker compose pull` will not update Firefox, so use `./update.sh`. |
| `FF_OPEN_URL: about:blank` | No third-party call on launch. Set it to `https://ipinfo.io/json` if you want an exit-IP check each start. |

## Maintenance

This is a security tool, and a stale one gives false confidence. Set a monthly
reminder:

```
./update.sh          # rebuilds Firefox from the latest base and updates nginx
```

After any update, re-run the verification checks above (and the CreepJS test if you
use it), then update the "Last verified" line at the top of this README.

## Optional hardening (defense-in-depth)

The defaults are already sound; an independent security review found no
vulnerabilities. If you want to go further, you can add `mem_limit` and `pids_limit`
to the services, pin the Firefox base image by digest instead of `:latest`, and pin
the `apk` package versions in `Dockerfile.firefox` for reproducible builds.

## Related projects

This stack combines well-known parts, and several projects overlap with pieces of it.
None that I found combine the whole set: a namespace-level kill switch, fingerprint
hardening, a profile wiped every session, and a self-hosted fingerprint test. How the
closest ones compare:

| Project | Browser in container | VPN | Kill switch | Fingerprint hardening | Ephemeral profile | Self-hosted FP test |
|---|---|---|---|---|---|---|
| this repo | yes | WireGuard | namespace | RFP | tmpfs | optional |
| [Staubgeborener gist](https://gist.github.com/Staubgeborener/7899ad152cf39a2dda24e7c45272ea34) | yes | Gluetun | yes | no | no | no |
| [mtzanidakis/vpnbrowser](https://github.com/mtzanidakis/vpnbrowser) | yes | WireGuard | unclear | no | no (persistent) | no |
| [oseiskar/docker-vpn-browser](https://github.com/oseiskar/docker-vpn-browser) | yes (X11) | OpenVPN | no | no | yes | no |
| [Nickguitar/VPNTabs](https://github.com/Nickguitar/VPNTabs) | yes | VPN or Tor | yes (proxy) | no | no | no |
| [codeterrayt/Disposify](https://github.com/codeterrayt/Disposify) | yes (noVNC) | no (cloud IP) | no | no | yes | no |

Anti-detect browsers such as CloakBrowser, Camoufox, and BotBrowser are a different
category. They spoof and rotate fingerprints to defeat bot-detection for scraping and
automation. `resistFingerprinting` tries to make you look like every other
resistFingerprinting user, while an anti-detect browser tries to look like a
convincing, unique person. Those are opposite goals, so the two are not
interchangeable.

## License

MIT. See the `LICENSE` file. CreepJS is a separate project under its own license.
