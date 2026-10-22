# Versioned distribution and rollback

Status22October2026: offline packaging/verification implemented; no prebuilt release is published.
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
publisher authentication, release-aware installation/update/rollback, and real
acceptance remain required before distribution to end users. No existing release
or registry digest is implied by the schema's expected repository names.

The tool reproduces source bundles from immutable Git input within the tested
runtime. The existing Firefox recipe still fetches moving APT packages; bit-for-bit
binary reproduction is **not established**. Record and preserve exact dependency
materials/snapshots in the release build process before claiming that property.

## Candidate acceptance

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

## Updates and rollback

The existing manual updater rebuilds Firefox from source and does not implement a
prebuilt release update. Do not route release users through it without adding and
testing an explicit release-aware path.

A release update must retain the prior manifest/digests and local credential files,
close the viewer, use the maintained maintenance/viewer checks, install the new
manifest and verify readiness, policy and network/browser recovery. A failed or
INCOMPLETE acceptance restores the previous images/configuration and verifies
recovery before clearing maintenance. Only report UPDATED after success. Rollback
restores software; browser-session data erased by a restart is not recoverable.

Do not promise unattended VPN updates. Existing live immutable pins, overrides and
accepted dispositions remain separate from public release assets.
