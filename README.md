# Private Browser (VPN-tunneled, fingerprint-hardened)

![CI](https://github.com/silverfox-2096/private-browser/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/github/license/silverfox-2096/private-browser)
![Last commit](https://img.shields.io/github/last-commit/silverfox-2096/private-browser)

Firefox in a Docker container whose only network path is a WireGuard VPN tunnel.
If the tunnel drops, the browser has no route anywhere, not even to your LAN. The
profile lives in RAM and is wiped every time you stop the stack.

Built from two existing images: [Gluetun](https://github.com/qdm12/gluetun) for
the VPN and kill switch and jlesage's [GUI base image](https://github.com/jlesage/docker-baseimage-gui)
for a VNC web UI, with Firefox installed from Mozilla's own APT repository and
hardened with Firefox's own `resistFingerprinting`.

> Docs & config verified: 2026-09-24 (Firefox 156, Gluetun v3.41.3).
> Runtime & leak-tested: 2026-09-24. This is a security tool; if either date
> looks old, treat it as unverified.

## What this is, and what it isn't

Three things to know before you start:

- Privacy, not anonymity. Sites you visit see the VPN's exit IP, not yours. Your ISP and your LAN see that you use a VPN and when, but not where this browser goes or what it sends. Your VPN provider sees both your real IP and your destinations. If you need to be untraceable, use Tor instead. Details per observer: [What it does and doesn't do](#what-it-does-and-doesnt-do).
- Not a one-click app. It needs Docker and a paid WireGuard VPN (this example uses Proton).
- Closing it erases everything. Bookmarks, logins, history, cookies, and downloads all live in RAM and are wiped every time you stop the stack, by design. There is no persistent folder, so save anything you want to keep somewhere off the browser (a cloud drive, email) before you stop it.

## No custom service code

Nothing written for this project runs as a service. The stack is a Docker Compose
file that wires together three existing, independently maintained images (Gluetun,
jlesage's GUI base, and nginx), plus a Dockerfile that installs Mozilla's Firefox
and a few fonts.

The repository does contain code of its own, all of it tooling that you or CI run
from outside the browser:

- three host scripts: `launch.sh`, `update.sh` and `verify.sh`;
- the CI scripts `ci/fingerprint.sh` and `ci/test-scripts.sh`;
- the browser checks `ci/checks.mjs` and their test, `ci/test-checks.mjs`.

Some of it parses untrusted input: `verify.sh` reads JSON from ipinfo.io, and
`checks.mjs` reads JSON from ipinfo.io and bash.ws.

The configuration, scripts and documentation were written with Claude Code (AI) and reviewed by me.

The risk surface is the configuration (how secrets are handled, which ports are
exposed, whether the kill switch holds), the images it runs, and these scripts. The
configuration is all visible in `docker-compose.yml`. The automated reviews listed
under [About the security review](#about-the-security-review) are not a
third-party audit, so do not take them on faith. Read the compose file, and run the
checks under [Verify it works](#verify-it-works) yourself.

## Continuous checks

Every push, pull request, and a weekly schedule run a CI pipeline you can inspect
yourself under the Actions tab. It is not a one-time review:

- **ShellCheck** on `launch.sh`, `update.sh`, `verify.sh`, `ci/fingerprint.sh` and
  `ci/test-scripts.sh`.
- **Failure-path tests.** `ci/test-scripts.sh` runs the four shell scripts against
  simulated `docker` and `curl`, and `ci/test-checks.mjs` runs `ci/checks.mjs` against a
  simulated browser and DNS-test API. They prove each script reports FAIL or INCOMPLETE,
  with the matching exit code, when a step fails or its evidence is missing.
- **Hadolint** on `Dockerfile.firefox`.
- **Checkov** on `Dockerfile.firefox`. The findings that are deliberate design choices
  (no HEALTHCHECK, no build-time `USER` — the base image drops
  privileges at runtime) are suppressed inline with a comment citing the reason, so the
  pass is honest rather than silent.
- **KICS** on `docker-compose.yml` — the compose file is the actual risk surface here,
  so it is machine-scanned too (Checkov has no docker-compose support). It currently
  passes with no high-severity findings.
- **Trivy** builds the image and scans it for CVEs. It fails only on *fixable*
  High/Critical vulnerabilities, so a red badge means a patchable CVE is present.
  `./update.sh` rebuilds from the current base image and the current Mozilla
  release. A badge that stays red after a rebuild means the fix has not reached
  jlesage's base image or Debian yet, and nothing in this repo can close it. All
  findings, fixable or not, are published to the repository's Security tab.
- **Fingerprint** builds the image, starts it without the VPN, and drives a headless
  copy of the browser against a self-hosted, pinned CreepJS. It fails if the user agent
  stops matching the installed Firefox, the time zone is not the one
  `resistFingerprinting` reports, WebGL comes back, the Safe Browsing prefs are not
  off, or CreepJS's font list, WebGL, time zone or CPU-core fields drift from
  `ci/creep-baseline.json`. It compares those fields one by one, never the overall
  fingerprint ID, which also moves with headless mode and window size. A missing or
  empty baseline fails; a new one is recorded only on request (`RECORD=1`). Run it
  locally with `bash ci/fingerprint.sh`.
- **Dependabot** opens weekly pull requests for the pinned versions: the Actions
  SHAs, the two jlesage images in `Dockerfile.firefox`, the Gluetun digest, and the CI
  tools listed in `ci/pins/`. Nothing merges automatically, because green CI does not
  include the leak tests. For Gluetun only patch releases are proposed; minor
  versions are bumped by hand (see Design decisions). The CreepJS commit is bumped
  by hand, with a re-recorded baseline.

Two honesty notes. CI scans an image built *at scan time*, so your
locally built image is only as fresh as your last `./update.sh` — a green badge tracks
the upstream base, not your machine. And CI cannot run `verify.sh`, and the fingerprint job runs without a tunnel: the leak tests need
a live VPN key and a running tunnel, neither of which belongs in a public runner, so
they stay a local step you run yourself (see [Verify it works](#verify-it-works)).

## What it does and doesn't do

It gives you privacy. What each observer sees:

- **Websites** see the VPN's exit IP, not your real one.
- **Your ISP and your LAN**, for traffic this browser sends through its tunnel, see
  that you use a VPN and when, but not the destinations or the content. Other traffic
  from your machine, and the timing and volume of the tunnel traffic, are outside
  that promise.
- **Your VPN provider** sees your real IP and your destinations.
- **Logins and behaviour** link your sessions to each other, whatever happens to the
  profile. A wiped profile does not unlink an account you sign in to.

It does not give you anonymity. Your VPN provider could be compelled to log what it
sees. If you need an identity that nobody, including your VPN, can trace back to you,
use Tor instead.

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
   WireGuard config file.
2. Create the web-login credential. The web UI is protected by an HTTPS login page
   backed by a bcrypt htpasswd file. Generate it on the host (you are prompted for a
   password; nothing is written to your shell history):
   ```
   docker run --rm -it -v $PWD:/w -w /w httpd:alpine htpasswd -cB webauth-htpasswd myuser
   sudo chown $USER:$USER webauth-htpasswd && chmod 600 webauth-htpasswd
   ```
   The `chown` is needed because the container creates the file as root. It holds only
   a bcrypt hash and is gitignored; keep it out of version control.
3. Optionally, set `SERVER_COUNTRIES` in `docker-compose.yml` to your preferred exit
   country.
4. Build and start:
   ```
   ./launch.sh
   ```
   Use `./launch.sh` rather than `docker compose up -d` directly: it checks that the
   credential file from step 2 exists first. If you skip that check and the file is
   missing, Docker creates an empty directory in its place and the web login breaks.
5. Open https://127.0.0.1:7814, accept the self-signed cert, and log in with the
   username (`myuser`) and the password you set above.

## Daily use

Start the stack with `./launch.sh` and stop it with `docker compose down`. Stopping
wipes the whole profile (bookmarks, logins, history, cookies, and downloads) by
design, since it all lives in RAM. Nothing is written to a host folder, so upload
anything you download to a cloud drive or email before you stop the stack. The tunnel
stays up whenever the stack runs, so remove `restart: unless-stopped` from the
services if you want it to run only on demand.

## Troubleshooting

If Gluetun restarts or reconnects (a crash, a `docker restart`, or an image update),
the Firefox container stays attached to the old, now-dead network namespace. The
symptom is that the web UI at `https://127.0.0.1:7814` becomes unreachable and the
browser cannot load anything. This is the kill switch doing its job, Firefox fails
closed so nothing leaks during the gap, but it does not self-heal, because Firefox
keeps running and its own restart policy never fires. Reattach it to the live tunnel:

```
docker restart private-firefox
```

An auto-restart companion (such as `deunhealth` or `autoheal`) could do this
automatically, but it would need access to the Docker socket, a larger attack surface
than this rare, fail-closed event warrants. It is left out on purpose.

## Verify it works

Do not trust the config; test it:

```
# tunnel up, exiting the country you expect
docker exec gluetun-proton wget -qO- https://ipinfo.io/json

# kill switch: stop the tunnel, the browser must lose all connectivity
docker stop gluetun-proton      # UI shows "Reconnecting..."
docker compose up -d            # bring the tunnel back
docker restart private-firefox  # reattach Firefox to the new namespace
```

The `docker restart private-firefox` at the end is required: after Gluetun comes
back it holds a fresh network namespace, and Firefox stays bound to the dead one
until it is restarted (see [Troubleshooting](#troubleshooting)). Without it the
browser stays stuck on "Reconnecting...".

In the container browser, also confirm there is no WebRTC leak (browserleaks.com/webrtc
should report "No Leak" with a blank local IP) and no DNS leak (the extended test at
dnsleaktest.com should show your DoT resolver, never your ISP).

The container-network checks above are automated in `verify.sh` (exit-IP, DNS resolver,
and a two-sided kill-switch test). The kill-switch test briefly stops the tunnel and
restarts Firefox, so run it between browsing sessions, not during one. On the host with
the stack up:

```
./verify.sh          # or ./verify.sh SG to also assert the exit country
```

Each check ends `PASS`, `FAIL` or `INCOMPLETE`. INCOMPLETE means the evidence could not
be collected (for example, the host's public IPv4 address could not be looked up). It is
not a pass: treat it like a failure in anything you automate. Exit codes: 0 = every
check passed, 1 = at least one FAIL, 3 = no FAIL but at least one INCOMPLETE, 2 = the
stack is not ready.

The exit-IP check compares the tunnel's exit with the host's *current* public IPv4
address. If the host itself is behind a VPN, that is not your real IP; give the script
the address your ISP assigns, `REAL_IP=a.b.c.d ./verify.sh` (no leading zeros; anything
else is INCOMPLETE). It is used only for the comparison and never printed. By default the
script prints no IP address at all: until the comparison succeeds, the exit address could
be the host's own. `SHOW_EXIT_IP=1` prints the exit address, and only on a PASS.

If you interrupt the script (Ctrl+C) while it has the tunnel stopped, it restores the
stack first and then exits with code 130. Each Docker step it takes while the tunnel is
down has a time limit.

It cannot test in-browser WebRTC or the browser-side DNS-leak page — those need a real
browser and stay manual, above. A recent run is recorded in `VERIFY-OUTPUT.md`.

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

Changing any of these without reading can break the stack or weaken it. You will not find a long `user.js` here. The hardening is this short list of preferences plus Firefox's `resistFingerprinting`, and that is deliberate; the reasoning is under [Design notes](#design-notes-and-anticipated-questions).

| Setting | Why it is set this way |
|---|---|
| `BLOCK_MALICIOUS: "off"` | Turning it on can push Gluetun's DNS resolver into a restart loop on some providers, so DNS stops resolving. Your provider's own malware blocking already covers this. |
| `FIREWALL_OUTBOUND_SUBNETS: ""` | Blocks LAN access too, which is what makes the kill switch total. |
| Ports on `gluetun`, `127.0.0.1:` prefix | They have to live on Gluetun (shared namespace) and stay loopback-bound, never exposed to the LAN. |
| `SECURE_CONNECTION: 1` and `WEB_AUTHENTICATION: 1` | TLS plus an HTTPS login page for the web UI. Credentials are a bcrypt hash in a host-mounted `webauth-htpasswd` file, so they are not plaintext and not readable via `docker inspect`. This replaces the older `VNC_PASSWORD` (capped at 8 characters, exposed via `docker inspect`). The file is mounted read-write because the image's init sets its permissions at startup; note this is the one host file the browser container can write, so a compromised container could rewrite the hash (worst case: lock you out, or persist its own login to the loopback UI) — a minor channel an attacker already inside the container gains little from. |
| `/config` as a quoted tmpfs, `mode=0755` | Ephemeral profile. Keep the quotes: YAML otherwise strips the leading zero from `0755` and the container will not start. |
| `webgl.disabled=true` | Removes an identifying WebGL hash. Breaks 3D sites and web maps. |
| Gluetun pinned by digest | Update deliberately. Minor versions can rename settings (v3.41 renamed the `DOT*` DNS options), so they are bumped by hand; change the tag and digest together, then re-run the leak tests. The image runs its own healthcheck (it tests tunnel connectivity), so there is no custom healthcheck to maintain. |
| Firefox built locally | Installs Firefox from Mozilla's own APT repository (the signing key is checked against Mozilla's published fingerprint at build time) and adds fonts so you do not stand out with a near-empty font set. One consequence: `docker compose pull` will not update Firefox, so use `./update.sh`. |
| Safe Browsing, built-in VPN, sponsored New Tab off | Mozilla's own build ships Google Safe Browsing keys, a built-in VPN button, and sponsored New Tab content. All three are switched off in `docker-compose.yml`; see the design notes. |
| `FF_OPEN_URL: about:blank` | No third-party call on launch. Set it to `https://ipinfo.io/json` if you want an exit-IP check each start. |

## Maintenance

This is a security tool, and a stale one gives false confidence. Set a monthly
reminder:

```
./update.sh          # rebuilds with the current Firefox release and base image, updates nginx
```

After any update, re-run the verification checks above (and the CreepJS test if you
use it), then update the two "verified" dates at the top of this README: bump
"Docs & config verified" for wording or config changes, and "Runtime & leak-tested"
only after re-running the leak and runtime checks.

Dependabot pull requests that change `Dockerfile.firefox` or `docker-compose.yml`
get the same treatment: check out the branch, run `./update.sh` and `./verify.sh`,
and merge only if both pass. Pull requests that only touch CI tooling (`.github/`,
`ci/pins/`) can merge on green CI.

## Optional hardening (defense-in-depth)

The defaults are already sound, and the automated review noted above reported no
vulnerabilities within its scope. If you want to go further, you can add
`mem_limit` and `pids_limit`
to the services, pin the base images by digest, and pin the package versions in
`Dockerfile.firefox` for reproducible builds. These are left optional on purpose. A
memory limit on a browser can kill tabs under load, and pinning would hold back the
security patches and Firefox releases each rebuild pulls in. Add them when your
situation calls for it.

## Design notes and anticipated questions

These are the questions a careful reviewer tends to raise. Where a setting looks unusual there is a measured reason, and where a claim can be checked the checks are under [Verify it works](#verify-it-works).

### Why is there no `user.js` with hundreds of tweaks?

The protections that matter come from the architecture rather than a long preference list. The profile is wiped every session (tmpfs), all traffic is forced through the VPN's network namespace, and Firefox's `resistFingerprinting` (RFP) handles most fingerprint normalization. A full arkenfox-style `user.js` was considered and set aside as largely redundant here, since its highest-value settings for disk avoidance, DNS handling, and WebRTC are already delivered by tmpfs, the VPN container, and the shared namespace. Fewer knobs means less to misconfigure or let fall out of date. The prefs that are set (RFP, letterboxing, telemetry off, and turning off link prefetch, speculative connections, and search suggestions) each add something the architecture does not. The rest switch off features Mozilla's own build adds: Google Safe Browsing, the built-in VPN button, and sponsored New Tab content.

### Why are only about 3 fonts detected?

Three is the target. A container with almost no fonts stands out, so the image installs Noto (including emoji and CJK), Liberation, FreeFont, and DejaVu to look like an ordinary Linux desktop. It reports about 3 of the 51 fonts a common probe checks. Debian's Noto package adds four rarer script families that the probe also lists (Canadian Aboriginal, Gunjala Gondi, Masaram Gondi, Yezidi), so the Dockerfile removes them; with them the probe saw 7. The other 48 are Windows and macOS families that no Debian package provides, and installing lookalikes would create inconsistency signals worse than the gap.

### Why is Safe Browsing off?

Mozilla's own Firefox build ships Google Safe Browsing keys, so with the defaults it talks to Google in three ways: it downloads Google's malware and phishing lists, it asks Google for the full hashes when a page's address matches a prefix on those lists, and it can send details of some downloaded files to Google for a verdict. Those requests would still go through the VPN, but they are a standing connection to Google that this stack otherwise does not make. They are switched off, and that is an accepted trade-off rather than an oversight: you lose the built-in phishing and malware blocklist. If you want that protection back, remove the three `FF_PREF_SB_*` lines from `docker-compose.yml`.

### Why is WebGL disabled? Doesn't hiding WebGL make you more unique?

This was tested rather than assumed, because it is a real trade-off.

With RFP on and WebGL enabled, Firefox masks the renderer string to a generic `Mozilla` value, so the underlying software renderer such as `llvmpipe` never leaks, and it randomizes the canvas readback each session. That is the case for leaving WebGL on.

Enabling it also exposes the WebGL capability set, meaning dozens of parameters and extension names, as a stable hash that does not change between sessions. This container renders in software because it has no GPU, so that capability set reflects the software graphics stack and is more likely to differ from a typical hardware-GPU user than to blend in. RFP normalizes the renderer string but leaves this capability list alone.

Disabling WebGL removes that surface. A browser with no WebGL is also a normal posture among privacy-conscious users, since it is what the Tor Browser's "Safer" security level does. A browser running RFP is already identifiable as an RFP browser, so the realistic crowd to blend into is other RFP users, and WebGL-off is common there. Given the choice between a masked renderer that still carries a stable software-capability fingerprint and no WebGL surface at all, disabling exposes less. The cost is that 3D sites and web maps will not render, which is acceptable for this browser.

### Does the container leak your locale or timezone?

No. RFP reports the language as `en-US` and spoofs the timezone to UTC no matter where you are. The container's own locale is set to `en_US.UTF-8`, so the operating-system locale and the browser-reported one agree and your real regional settings never reach a page. A normal host browser often leaks here even with RFP on, because its system locale differs from what RFP reports.

### Why send DNS to Cloudflare instead of the VPN's own resolver?

The property that matters is encrypted DNS that never touches your ISP, and that holds: queries leave over DNS-over-TLS from inside the tunnel. Routing DNS to the VPN's own resolver would put everything with one provider, which sounds cleaner, but the VPN is already your exit and can see the TLS SNI of the sites you visit, so it learns the destinations either way. The difference is smaller than it looks, and this setup avoids the resolver-restart problems seen with other configurations. If you prefer your provider's resolver, it is a one-line change; re-run the DNS-leak check afterward.

### Is it really amnesic?

The profile, yes, when you stop the stack with `docker compose down`. The entire browser profile, meaning cookies, history, logins, cache, and downloads, lives in a RAM-backed tmpfs and is discarded with the container. There is no persistent downloads folder by design, so anything you fetch is wiped too; save it off the browser first if you need to keep it. Places outside the profile (container logs, and traces on your own machine such as a clipboard manager) have not yet been checked for browsing data, so this answer covers the profile only.

One honest caveat: tmpfs pages can be pushed to swap under memory pressure, and on a host with unencrypted swap those fragments can touch disk. If that matters to you, encrypt your swap or turn it off. On a host with encrypted swap this is already covered.

### Doesn't the clipboard bridge weaken the isolation?

A little, and it is worth being precise about. Clipboard sharing is a built-in feature of jlesage's web UI, not something this stack adds, and there is no environment variable to turn it off. Two paths exist: a manual clipboard box in the control panel, and automatic synchronization that activates in Chromium-based viewers served over HTTPS. Both are bidirectional, container to host as well as host to container, so treat the clipboard as a real channel in both directions. It is reachable only over the loopback-bound web UI, so nothing on your LAN can touch it. If that channel matters to you, do not paste through the control panel, and view the UI in a browser that does not trigger the automatic sync.

### About the security review

The configuration was checked with an automated security review, Claude Code's `/security-review`, run in a separate session over the files in this repository. It reported no vulnerabilities within that scope. This is not a third-party human audit or a runtime penetration test. No automated review is a guarantee: a later review of these docs caught claims this one missed, an environment variable that did nothing and a downloads folder that did not actually persist, both since corrected. Treat it as one input, not a seal of approval, and check the design yourself: there is no custom service code, the risk surface is the configuration, the images and the scripts, and all of it is here to read alongside the verification steps.

A later review, on 24 September 2026, was also by an AI reviewer: first the README alone, then the source. The source pass covered the files of the Gluetun v3.41.3 release (compose files, Dockerfile, the three host scripts, `ci/fingerprint.sh`, `ci/checks.mjs` and its baseline, the CI workflow, Dependabot config, README, `VERIFY-OUTPUT.md`, license). It had no Git metadata, so it is tied to that release's content, not a commit. It ran syntax checks, parsed the compose files, and ran the scripts against simulated `docker` and `curl`. It did not run the stack, a VPN or a browser. Its main finding was that the checks reported more confidence than their results justified; the scripts now report PASS, FAIL or INCOMPLETE with matching exit codes, and the wording above has been corrected. Its points about local-network reachability, behaviour while the tunnel changes state, and data outside the profile need runtime tests that have not been run yet. The statements that depend on them (no route to your LAN, the kill switch during reconnects, what survives outside the profile) are unchanged until those tests confirm or correct them.

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

- 2026-09-24: Three fixes to `verify.sh` from the reviewer's check of the previous release. The earlier entry's "never prints the host IP" was not true: when the comparison could not be made, the script printed the exit address, which is the host's own IP if the tunnel is not working. It now prints no address unless `SHOW_EXIT_IP=1` is set, and then only on a PASS. IPv4 addresses with leading zeros (`203.000.113.009`) are rejected instead of being compared as text, which could report a false PASS. A Ctrl+C while the script restores the tunnel no longer abandons the restore, and every Docker step while the tunnel is down has a time limit. The failure-path tests cover all three.
- 2026-09-24: Acted on a fourth review (see [About the security review](#about-the-security-review)). The scripts no longer report success they have not earned. `verify.sh` reports PASS, FAIL or INCOMPLETE with exit codes 0, 1 and 3; it compares IPv4 with IPv4, takes an optional `REAL_IP` for hosts behind a VPN, never prints the host IP, re-checks connectivity after restoring the tunnel, and restarts `creepjs-server` too. `update.sh` prints `UPDATED` only after the new image is running, Gluetun is healthy, Firefox reports a version and the web UI answers. `launch.sh` stops if `docker compose up` fails and waits for the web UI with one 30-second deadline. In the fingerprint job, a missing or empty CreepJS baseline now fails, the CreepJS download is re-fetched when its pinned commit changes, and `ci/fingerprint.sh` keeps the INCOMPLETE exit code. The DNS check in `ci/checks.mjs` now judges the resolver's identity (its network, AS13335 for Cloudflare) instead of its country, and reports INCOMPLETE when the test service returns no resolver. New failure-path tests (`ci/test-scripts.sh`, `ci/test-checks.mjs`) run in CI. The README now says what each observer sees, lists the scripts and the untrusted input they parse, limits the amnesia claim to the profile, and describes Safe Browsing's three connections to Google.
- 2026-09-24: Updated Gluetun from v3.40.4 to v3.41.3, pinned by digest. v3.41 renamed the DNS settings, so `DOT` and `DOT_PROVIDERS` are now `DNS_SERVER` and `DNS_UPSTREAM_RESOLVERS` (the old names still work in v3.41). Removed `HEALTH_VPN_DURATION_INITIAL`, which v3.41 no longer reads. Dependabot now proposes Gluetun patch releases; minor versions stay manual. Re-ran the leak battery (exit IP, WebRTC, DNS leak, kill switch): all passing.
- 2026-09-21: Added Dependabot (`.github/dependabot.yml`): weekly, grouped pull requests for GitHub Actions, the Dockerfile base images, the compose images, and the CI tool versions, which moved into `ci/pins/` so Dependabot can read them. No auto-merge. Corrected the CodeQL action's version comment from `v3` to `v3.37.2` so updates rewrite it.
- 2026-09-21: Added a CI fingerprint job (`ci/fingerprint.sh`): headless Firefox against a pinned, self-hosted CreepJS, compared field by field with a recorded baseline, plus a check that the Safe Browsing prefs are off. It needs no VPN key, so it runs on every push and on the weekly schedule; the leak tests still run only locally.
- 2026-09-21: Firefox now comes from Mozilla. The previous base image, `jlesage/firefox`, pins Alpine's Firefox package, which Alpine's stable branch had left at 151.0.3 while Mozilla shipped 156. The image is now built on jlesage's Debian GUI base with Firefox from Mozilla's own APT repository; the build refuses to continue unless Mozilla's signing key matches its published fingerprint. jlesage's launcher and `FF_PREF_*` handling are copied from a pinned `jlesage/firefox` release, so the environment variables and web UI are unchanged. Mozilla's build brings Google Safe Browsing, a built-in VPN button, and sponsored New Tab content, all switched off in the compose file. Added system FFmpeg (without it, Firefox's answers to media-type probes changed between page loads) and removed four Noto font families that raised the detected font count from 3 to 7. `update.sh` now rebuilds without the layer cache so new Firefox releases are actually picked up. Re-ran the leak battery (exit IP, WebRTC, DNS leak, kill switch) and the CreepJS audit: all passing, fonts back to 3 of 51.
- 2026-09-07: The weekly scan went red on fourteen fixable High-severity issues in the util-linux libraries `libblkid` and `libmount`, inherited from the same base image that has not been rebuilt since July. The 1 September approach — naming each affected package in `Dockerfile.firefox` — would need a fresh commit for every future CVE, so the build now upgrades every installed package instead. Hadolint's rule against `apk upgrade` is suppressed inline with its reason: that rule protects a pinned base image, and this one is deliberately unpinned. Checked locally before pushing — both scanners pass, the scan reports zero findings, and the upgraded image still starts. Also corrected a stale note claiming the image inherits a HEALTHCHECK from its base; it does not, and the stack has always gated on Gluetun's healthcheck instead.
- 2026-09-01: Monthly upkeep. Re-ran the leak battery (exit IP, WebRTC, DNS leak, kill switch), all passing, and moved the runtime verification date. Trivy then failed on five fixable High-severity CVEs in `openssl` and `libexpat`, all denial-of-service issues, inherited from a base image that had not been rebuilt since Alpine published the fixes. Running `./update.sh` did not clear them, so `Dockerfile.firefox` now upgrades `openssl` and `libexpat` explicitly with `apk add --upgrade`. A plain `apk add` was tried first and did nothing: apk treats an already-installed package as satisfied and skips it. Corrected the CI section, which described a base-image refresh as the only remedy for a red Trivy badge.
- 2026-07-21: Added a CI pipeline (ShellCheck, Hadolint, Checkov on the Dockerfile, KICS on the compose file, Trivy image CVE scan) that runs on every push and weekly, with a status badge. Deliberate scanner findings are suppressed inline with their rationale. Simplified `Dockerfile.firefox` to build as the base image's default root user, removing an explicit `USER 0` that failed under strict container runtimes. Added `verify.sh`, which automates the container-network verification checks, and published a sample run in `VERIFY-OUTPUT.md`.
- 2026-07-21: Replaced the VNC password with jlesage's `WEB_AUTHENTICATION`, an HTTPS login page backed by a bcrypt htpasswd file that you generate on the host and that is gitignored. This removes the 8-character RFB cap and keeps the credential out of `docker inspect`. Dropped `VNC_PASSWORD` (the web login is the only prompt now), mounted the credential file read-write (the image chmods it on startup), and added a `launch.sh` guard that refuses to start if the file is missing.
- 2026-07-21: Housekeeping after a follow-up review. Verified the pinned Gluetun digest against the official image on Docker Hub. Removed two dead directories from `.gitignore`, corrected the VNC password note to reflect its 8-character limit, and made `launch.sh` fail with a clear message instead of opening a broken page if the stack does not come up. Split the verification stamp into separate "docs & config" and "runtime & leak-tested" dates.
- 2026-07-21: Corrected several claims after a documentation review. Removed a non-functional `ENABLE_CLIPBOARD` variable and rewrote the clipboard note (sharing is a built-in, bidirectional web-UI feature with no off-switch). Made downloads honestly ephemeral by removing the non-working persistence mount. Dropped the custom Gluetun healthcheck in favour of the stronger built-in one, removed the unused `:8080` host publish from the default, and pinned Gluetun by digest. Added a troubleshooting note for recovering after a Gluetun restart, a swap caveat on the amnesia claim, and honest wording on the VNC password and the security review's limits.
- 2026-07-21: Added the design notes section, covering the WebGL choice (tested enabled against disabled), locale handling, and why the optional hardening settings are not defaults. Described the security review accurately, as an automated `/security-review` in a separate session rather than a third-party audit.
- 2026-07-20: First public release.

## License

MIT. See the `LICENSE` file. CreepJS is a separate project under its own license.
