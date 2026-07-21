# Private Browser (VPN-tunneled, fingerprint-hardened)

Firefox in a Docker container whose only network path is a WireGuard VPN tunnel.
If the tunnel drops, the browser has no route anywhere, not even to your LAN. The
profile lives in RAM and is wiped every time you stop the stack.

Built from three existing images: [Gluetun](https://github.com/qdm12/gluetun) for
the VPN and kill switch, [jlesage/firefox](https://github.com/jlesage/docker-firefox)
for Firefox over a VNC web UI, and Firefox's own `resistFingerprinting`.

> Last verified: 2026-07-20 (Firefox 151, Gluetun v3.40). This is a security
> tool; if that date looks old, treat it as unverified.

## What this is, and what it isn't

Three things to know before you start:

- Privacy, not anonymity. Your ISP, your LAN, and the sites you visit cannot see your real IP, but your VPN provider still can. If you need to be untraceable, use Tor instead.
- Not a one-click app. It needs Docker and a paid WireGuard VPN (this example uses Proton).
- Closing it erases everything. Bookmarks, logins, history, and cookies live in RAM and are wiped every time you stop the stack, by design. Downloads are kept.

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
`docker-compose.yml`, and an independent review of the configuration found no
vulnerabilities within its scope (the five files in this repo; no runtime
penetration testing). You do not have to take that on faith. Read the compose file, and run the checks
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

The defaults are already sound; an independent review of the configuration found
no vulnerabilities within its scope. If you want to go further, you can add
`mem_limit` and `pids_limit`
to the services, pin the Firefox base image by digest instead of `:latest`, and pin
the `apk` package versions in `Dockerfile.firefox` for reproducible builds.

## Design notes and anticipated questions

These are the questions a careful reviewer tends to raise. Where a setting looks unusual there is a measured reason, and where a claim can be checked the checks are under [Verify it works](#verify-it-works).

### Why is there no `user.js` with hundreds of tweaks?

The protections that matter come from the architecture rather than a long preference list. The profile is wiped every session (tmpfs), all traffic is forced through the VPN's network namespace, and Firefox's `resistFingerprinting` (RFP) handles most fingerprint normalization. A full arkenfox-style `user.js` was considered and set aside as largely redundant here, since its highest-value settings for disk avoidance, DNS handling, and WebRTC are already delivered by tmpfs, the VPN container, and the shared namespace. Fewer knobs means less to misconfigure or let fall out of date. The prefs that are set (RFP, letterboxing, telemetry off, and turning off link prefetch, speculative connections, and search suggestions) each add something the architecture does not.

### Why are only about 3 fonts detected?

Three is the target. A container with almost no fonts stands out, so the image installs Noto (including emoji and CJK), Liberation, FreeFont, and DejaVu to look like an ordinary Linux desktop. It reports about 3 of the 51 fonts a common probe checks. The other 48 are Windows and macOS families that no Alpine package provides, and installing lookalikes would create inconsistency signals worse than the gap.

### Why is WebGL disabled? Doesn't hiding WebGL make you more unique?

This was tested rather than assumed, because it is a real trade-off.

With RFP on and WebGL enabled, Firefox masks the renderer string to a generic `Mozilla` value, so the underlying software renderer such as `llvmpipe` never leaks, and it randomizes the canvas readback each session. That is the case for leaving WebGL on.

Enabling it also exposes the WebGL capability set, meaning dozens of parameters and extension names, as a stable hash that does not change between sessions. This container renders in software because it has no GPU, so that capability set reflects the software graphics stack and is more likely to differ from a typical hardware-GPU user than to blend in. RFP normalizes the renderer string but leaves this capability list alone.

Disabling WebGL removes that surface. A browser with no WebGL is also a normal posture among privacy-conscious users, since it is what the Tor Browser's "Safer" security level does. A browser running RFP is already identifiable as an RFP browser, so the realistic crowd to blend into is other RFP users, and WebGL-off is common there. Given the choice between a masked renderer that still carries a stable software-capability fingerprint and no WebGL surface at all, disabling exposes less. The cost is that 3D sites and web maps will not render, which is acceptable for this browser.

### Why send DNS to Cloudflare instead of the VPN's own resolver?

The property that matters is encrypted DNS that never touches your ISP, and that holds: queries leave over DNS-over-TLS from inside the tunnel. Routing DNS to the VPN's own resolver would put everything with one provider, which sounds cleaner, but the VPN is already your exit and can see the TLS SNI of the sites you visit, so it learns the destinations either way. The difference is smaller than it looks, and this setup avoids the resolver-restart problems seen with other configurations. If you prefer your provider's resolver, it is a one-line change; re-run the DNS-leak check afterward.

### Is it really amnesic if the downloads folder persists?

Yes. The browser profile, meaning cookies, history, logins, and cache, lives in a RAM-backed tmpfs and is gone the moment you stop the stack. The only things that persist are files you download, in a clearly named folder, and the VPN container's own state, which holds tunnel data rather than browsing. Nothing from the profile is written to disk.

### Doesn't the clipboard bridge weaken the isolation?

A little, and it is a deliberate convenience trade-off. Clipboard sharing is host-to-container only and bound to localhost. To drop it, set `ENABLE_CLIPBOARD: 0`.

### About the independent review

The review covered the configuration in this repository, meaning the compose file, Dockerfile, and scripts, and found no vulnerabilities within that scope. It was not a runtime penetration test. You can check the design yourself: there is no application code, the risk surface is the configuration, and all of it is here to read alongside the verification steps.

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

## Changelog

- 2026-07-21: Added the design notes section. Documented the WebGL choice after testing it enabled against disabled. Reworded the security-review note to state its scope.
- 2026-07-20: First public release.

## License

MIT. See the `LICENSE` file. CreepJS is a separate project under its own license.
