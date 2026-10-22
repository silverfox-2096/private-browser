# Versioned distribution and rollback

Status22October2026: release path specified; no prebuilt release is published.
The default remains local source builds. Never advertise a tag or digest before
its exact artifacts have passed the declared checks.

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
