# Versioned distribution and rollback

Status22October2026: offline packaging and compatible-controller release lifecycle implemented; no prebuilt release is published.
The default remains local source builds. Never advertise a tag or digest before
its exact artifacts have passed the declared checks.

## Offline maintainer tooling

`ci/release.py` prepares a local, reviewable bundle. It never starts Docker,
installs software, contacts a registry or publishes anything:

```bash
python3 ci/release.py prepare --manifest reviewed-release.json \
  --evidence reviewed-evidence.json --output /path/to/new-candidate-directory
python3 ci/release.py verify /path/to/new-candidate-directory
python3 ci/test-release.py
```

The bundle contains a frozen Git source archive, a full Compose recipe selecting
immutable VPN/Firefox image digests, normalized release/evidence records, scoped
release notes and `SHA256SUMS`. Only image/build selection changes in the generated
recipe; existing policy, namespace, startup, login and maintenance settings remain.
Tests resolve both Compose recipes and compare every other field. The source
archive comes from the selected commit, not the worktree; links, unsafe paths and
private runtime/credential filenames are rejected. Output must be a new directory.
If interrupted, the incomplete directory is not verified; choose a new output path.

The manifest schema has exactly `schema` (1), `version` (`vX.Y.Z` or `vX.Y.Z-rc.N`),
`source` (full40-character Git commit), `platform` (`linux/amd64`), `created` (UTC
ISO timestamp), `images`, `provenance` and `measurements`. Image keys are `gluetun`
and `firefox`, using only `ghcr.io/silverfox-2096/private-browser-SERVICE@sha256:…`.
Each provenance receipt records the matching `source`, `image` and reviewed
provenance-document `sha256`. Measurements record positive integer
`install_seconds`, `peak_memory_mib` and `disk_mib` from the actual clean-host trial.

The evidence schema has exactly `schema` (1), `source`, `images` and `gates`.
Each gate records `status`, `scope`, matching `source`/`images`, and the reviewed
report's `report_sha256`. Required gates: upstream-contracts, startup-guard,
policy-network, fingerprint, network, browser, recovery, vulnerability-scan,
advisory-disposition, clean-install and novice-trial. All must be PASS. Network,
browser, recovery, clean-install and novice-trial require `actual-runtime` scope;
other gates require `exact-artifact`. INCOMPLETE, missing, synthetic-scope or
mismatched records cannot produce a candidate. Do not invent passing records to
obtain a package. The regression tests use explicitly synthetic records only.

**These are consistency checks, not independent proof of the reports, publisher
identity, signatures or a GitHub attestation.** Review the actual reports and
provenance before generating records; hashes alone cannot prove a test occurred.
Checksums sent with a bundle do not establish authenticity. Registry publication,
publisher authentication and real installation/update/rollback
acceptance remain required before distribution to end users. No existing release
or registry digest is implied by the schema's expected repository names.

The tool reproduces source bundles from immutable Git input within the tested
runtime. The existing Firefox recipe still fetches moving APT packages; bit-for-bit
binary reproduction is **not established**. Record and preserve exact dependency
materials/snapshots in the release build process before claiming that property.

## Candidate acceptance

Use the [installation and usability worksheet](ADOPTION-TRIAL.md) to record real
observations, resource measurement methods, coaching and retained failed attempts.
Its blank fields are not evidence and cannot substitute for reviewed reports.

1. Select a reviewed source commit after the protected CI/companion checks pass.
   Record OS/architecture, source revision, toolchain, observed build inputs,
   Firefox/package versions and image identities. Build the patched VPN's `test`
   target as well as its `candidate` runtime; run the full upstream/contracts.
2. Build once for the initially supported Linux/amd64 platform. Scan those exact
   Firefox and VPN artifacts with a dated vulnerability database. Publish the
   complete findings and scoped dispositions. The maintainer's earlier Firefox
   retention decision is not automatic acceptance of a new release image.
3. Exercise startup guard, real policy controls and browser fingerprint tests
   against those same artifacts. Run clean-host onboarding and isolated real-VPN
   network/browser/recovery checks using a separate provider configuration. Do
   not reuse active production credentials concurrently or disturb the live stack.
4. Record failing attempts and INCOMPLETE results. Missing checks cannot become
   PASS. Measure first-install duration, disk and memory rather than guessing.
   Capture only disposable login/browser screens and a credential-free walkthrough.
5. Run an unfamiliar-user trial from the proposed quick-start; fix the steps where
   the person needs coaching, then repeat the affected acceptance checks.

## Package and publish

- Publish the accepted images to the repository owner's registry namespace with
  immutable digests and version tags; retain the exact tested artifacts instead
  of rebuilding them between testing and publication.
- Generate a release manifest containing source commit, platform, both registry
  digests, build provenance, checksums and links to exact-artifact reports.
- Prepare a source archive, an explicit digest-pinned Compose distribution file,
  checksums, install/update/rollback instructions and scoped release notes. The
  distribution path must retain the same policy, startup guard and login mounts.
- Validate that the installer consumes this manifest and checks the target
  platform before pulling. Do not treat mutable `latest` tags as verification.
- Review the complete candidate and retained advisory dispositions before marking
  the release ready. Publish a normal versioned release; preserve branch protection
  and existing security gates. Never embed provider keys, login hashes or raw
  private captures in archives, images, provenance or release assets.

## Guided prebuilt installation, updates and rollback

The CLI has a prebuilt path, tested with simulated Docker/VPN operations and real
filesystem transitions. It is not yet validated on a clean real-VPN installation.
No release bundle is currently advertised or published. Source installation stays
the normal quick-start until the actual acceptance and publication gates pass.

Use an authenticated, reviewed bundle and the matching controller source from its
`source.tar.gz`. Verify its publisher/provenance separately; the local verifier
checks consistency and integrity only. The guided installer compares executable
controller/configuration/pin files against the frozen source before selecting the
bundle. It does not execute or extract code from the bundle automatically.

```bash
./setup.sh --release /absolute/path/to/reviewed-bundle
# Or save the credentials and release selection without downloads or startup:
./setup.sh --configure-only --release /absolute/path/to/reviewed-bundle
./pb start

# Close the viewer and save work before either transition:
./pb update --release /absolute/path/to/new-reviewed-bundle
./pb rollback
```

This first lifecycle supports image updates with compatible controller files.
It refuses executable/controller changes and requires a separate reviewed source
migration for those changes. It preserves a running source installation instead
of silently converting it. Docs may be annotated, but controller files and pins
must remain as reviewed. The usual fixed names permit one installation per engine.

The installer privately records `.pb-release.json` and
`docker-compose.release.yml`; these are local state, excluded from Git and builds.
Rerunning the same selection preserves it. A recipe-only interrupted selection
can be completed by rerunning setup with the same bundle; it cannot silently
fall back to source building. Starts reuse available immutable images and pull
missing Linux/amd64 images, verify actual running image identities and the normal
login redirect, then open the browser. Ordinary `./pb update` refuses to rebuild
a pinned installation: supply the next bundle explicitly.

A release update downloads missing images before maintenance. It verifies this
checkout's container ownership, creates the maintenance gate, checks the mounted
flag/nginx include and actual HTTP503 response, then requires independently
readable IPv4 and IPv6 socket tables with zero connected viewers. A nonzero or
unreadable observation aborts before container recreation. It records prior
immutable image IDs, selected metadata and optional-service running state in a
private `.pb-release-transaction.json` before changing the selection.

The transition recreates the namespace-sharing services with the original policy,
startup/login/maintenance mounts, confirms exact images/readiness, runs the
maintained policy and disruptive network verifier, and restores the optional
service's running state. Only then does it clear its own gate and require the
normal unauthenticated HTTP302 login redirect. A missing redirect re-enables
maintenance and retains the transaction instead of reporting UPDATED. Browser
WebRTC/DNS page checks remain separate; installed network checks do not claim
seven browser results or a new actual-boot observation.

FAIL, INCOMPLETE or interruption triggers restoration of the previous selection,
images and verified policy/network/login recovery. The original unsuccessful
verdict remains unsuccessful after verified rollback. Failed recovery retains
maintenance and the transaction and reports INCOMPLETE. `./pb rollback` can retry
that recorded recovery after the viewer is closed, including when the failed
transition removed the viewer container. If an operation times out but its child
is still running, no competing rollback is started: the child keeps the operation
lock, and recovery must wait until it finishes. Do not bypass the lock.

Without an interrupted transaction, `./pb rollback` selects the recorded previous
compatible release under the same admission and recovery controls. Credentials
are never replaced by a transition. Software rollback does not restore erased
browser-session data. Keep prior accepted images available; do not prune them
before acceptance. Missing/malformed metadata, changed gate ownership, changed
controller files or foreign container ownership require manual review rather
than guessing which services or files to replace. Never blindly delete the gate
or transaction file to force an operation through.

The existing source updater remains separate. No scheduler, unattended VPN update,
production migration, registry upload or release publication is added by these
commands. The release lifecycle tests use nonexistent image references and
synthetic receipts, not actual deployment success.
