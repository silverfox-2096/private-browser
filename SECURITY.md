# Security results and vulnerability reporting

## Where to see the results

| View | What it contains | Access |
|---|---|---|
| [Code scanning alerts](https://github.com/silverfox-2096/private-browser/security/code-scanning) | Trivy's full Firefox image findings, including unfixed and lower-severity findings | Sign in with repository alert access; the anonymous public view does not show the owner's alert list |
| [Main CI workflow](https://github.com/silverfox-2096/private-browser/actions/workflows/ci.yml) | Firefox image scan, configuration/script checks and isolated fingerprint/startup tests | Public workflow/job summaries; artifact downloads may require sign-in |
| [Companion image workflow](https://github.com/silverfox-2096/private-browser/actions/workflows/companion-images.yml) | Patched Gluetun, optional CreepJS and pinned login-helper build/scan results, full JSON artifacts, source-aware module report | Public workflow/job summaries; artifact downloads may require sign-in |
| [Dependabot alerts](https://github.com/silverfox-2096/private-browser/security/dependabot) | GitHub's supported dependency-advisory matches | Sign in with repository alert access; a newly enabled scan may need indexing time |

GitHub restricts security alert visibility even for public repositories. See
[GitHub's access rules](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-security-and-analysis-settings-for-your-repository).
An empty public overview is not proof of a clean scan. The companion JSON reports
are kept in Actions; they are not currently uploaded to the Code scanning list.

### What a green check means

The vulnerability gate fails on fixable HIGH/CRITICAL findings. Full findings are
retained separately, including advisories with no fixed version in the configured
package repositories. A green check does not mean zero advisories, an independent
audit, a proven exploit-free image, or a scan of the image running on your laptop.
Every CI build has its own observed image identity.

The full Firefox scan can contain many unfixed findings even while the fixable gate
passes. Distribution severity and scanner severity can differ. Keep the advisory
visible and review applicability/upstream fixes; do not dismiss it merely to make
the page or badge look clean. Patched Gluetun has its own scan and evidence, not
the same result set as Firefox.

## Exact deployed images and retained findings

[The dated image assessment](IMAGE-ASSESSMENT.md) records current exact-artifact
scan scope, prioritized package/path evidence and unresolved decisions. It also
provides a manual archive-scanning pattern; routine recipe CI is separate. No
alert is dismissed by that assessment, and residual risk is not silently accepted.

## Repository protection settings

Verified 19 October 2026: dependency vulnerability alerts and Dependabot security-fix
proposals are enabled. Scheduled manifest-only Go version PRs remain paused;
security proposals still need source-aware review. No PR merges automatically,
and no proposal replaces the operator's pinned running VPN image. Secret scanning
and push protection are enabled. Private vulnerability reporting is enabled.
These are repository settings; the workflow files alone do not establish their state.

Verified 19 October 2026: `main` requires pull requests and an up-to-date branch
with all eight required GitHub Actions checks: `shellcheck`, `hadolint`, `checkov`,
`kics`, `trivy`, `fingerprint`, `scan (gluetun)` and `scan (creepjs)`. Each required
check is bound to the GitHub Actions app. These rules also apply to administrators;
force pushes and branch deletion are blocked, and review conversations must be
resolved. No second-person approval is required for this single-maintainer project.
Issues is enabled for sanitized bugs/tasks; sensitive reports use the private route.

## Report a vulnerability privately

Use [Report a vulnerability](https://github.com/silverfox-2096/private-browser/security/advisories/new)
on GitHub while signed in. Private reporting is enabled for this public repository.
Do not post credentials or raw private captures in a public issue or pull request.

Include the relevant commit/image identity, affected behavior and a small sanitized
reproduction. Distinguish a demonstrated defect from missing evidence. Never send
WireGuard keys, API/login/notification secrets, browser profiles or unrelated traffic.
There is no guaranteed response time or vulnerability bounty.

## Scope and deployment

The current main branch is the maintenance target; published recipes and an
individual installation can differ. Keep the exact image identity with any report.
Review [test coverage](README.md#what-has-been-tested) and the
[current remediation register](FOLLOW-UP-PLAN.md#current-status-register), including
retained-advisory assessment and maintained local-app policy gates. Boot timing,
arbitrary local relays,
IPv6 regeneration and independent socket attribution have explicit limits.
Replacing a live VPN image needs separate validation and a maintenance window;
repository alerts or a green public build do not perform that deployment.
