# Adoption plan

Recorded 22 October 2026, Asia/Kolkata. The user requested that this plan be saved,
set as the active goal, and implemented. This is a new adoption workstream after
the completed R1–R4 remediation round. It does not reopen accepted findings or
authorize interrupting the current browser, changing its images, or rebooting.

## Goal

A person unfamiliar with Docker should be able to obtain a tested version, run one
setup command, provide their VPN configuration and browser login locally, and
understand whether setup succeeded and what to do next. Preserve the existing
VPN/firewall/startup/authentication boundaries and honest PASS/FAIL/INCOMPLETE
reporting. Never publish credentials or raw private runtime evidence.

## Ordered deliverables

1. **Guided setup** (`./setup.sh`): check the supported host, Docker/Compose access,
   local daemon and required tools; explain missing prerequisites; import a
   WireGuard file strictly as data; select the supported provider and exit country;
   create credentials; build; check readiness and the maintained policy before
   opening the browser. Do not execute imported hooks, install Docker silently,
   change host permissions, overwrite existing secrets or disturb another stack.
2. **Local credential handling**: generate the internal Gluetun API key; prompt
   privately for the browser password; keep keys/passwords out of command-line
   arguments, logs and shell history. Write private files safely, exclude them
   from Git and Docker build contexts, and handle interrupted/repeated setup.
3. **Visual quick-start**: complete copy-paste acquisition/setup instructions,
   explicit tested platforms, actual login/browser screenshots and a short setup
   recording; measured install time/resources; explain ephemeral browser data.
   Never label illustrative screens as actual runtime evidence. Platform support,
   timing and novice usability must be measured, not invented.
4. **Everyday commands and diagnostics** (`./pb start|status|doctor|stop|update`):
   concise outcomes and actionable errors; doctor is read-only and redacts secrets;
   make destructive stop/update and disruptive verification explicit; preserve
   existing setup on rerun. Scope operations to this checkout's own containers.
5. **Readable validation summary**: one dated table with source/image identities,
   installation, network/browser/policy/startup and vulnerability evidence; link
   detailed existing reports, retained findings and limits. Preserve historical
   samples and original INCOMPLETE results. Add reproducible onboarding tests for
   clean setup, invalid inputs, missing dependencies, interruption and reruns.
6. **Versioned distribution**: establish tested release images pinned by digest,
   checksums/provenance, release notes and rollback; retain source builds. Publish
   only images whose exact artifacts passed the declared gates. Releases/tags were
   previously deferred; this adoption request authorizes preparing this path, not
   claiming a release exists before artifacts and validation do. Registry access,
   clean-host real-VPN trials and unfamiliar-user trials remain explicit evidence
   requirements, not results inferred from mocks or the maintainer's live stack.

## Acceptance and evidence

- Isolated tests exercise malformed configurations, ignored/rejected hooks,
  missing/unusable Docker, secret redaction, safe file permissions, collisions,
  reruns, partial writes, failed builds and FAIL/INCOMPLETE propagation.
- CI runs the new regression suite alongside existing policy/script gates.
- Use disposable fixtures and uniquely scoped containers, never the production VPN
  credentials concurrently. Read-only observations do not require interruption.
- Actual install/runtime results record tested OS/architecture, date, source and
  exact image IDs. Synthetic tests are labelled synthetic. A working Docker socket
  on the maintainer's existing machine is not a clean-host installation test.
- Commit and submit reviewable changes; preserve protected branch checks. Keep a
  checkpoint with tests, publication stage and outstanding external dependencies.

## Progress

- Plan saved and active goal created: DONE.
- Isolated branch `feat/guided-adoption`, based on main `013165c`: CREATED.
- Guided setup, local credential handling and scoped daily commands: IMPLEMENTED,
  awaiting complete installation acceptance. The initial wizard targets Proton
  on Linux x86-64; other providers/platforms remain manual/unvalidated.
- Automated onboarding controls: PASS40; maintained scripts PASS75; policy and
  Compose mutations PASS; real pinned helper accepts/rejects synthetic passwords.
- Quick-start, validation summary and synthetic configuration-only prompt
  recording: CREATED. The recording simulates discovery/port checks and is not
  real-VPN or browser evidence.
- Login/browser screenshots: PENDING human continuation past the local browser's
  self-signed certificate warning. No warning was bypassed automatically.
- Deliverable6: offline candidate packaging/consistency verification IMPLEMENTED,
  including digest-pinned Compose, frozen source archive, evidence/provenance
  records and checksums. PASS17 packaging/mutation/Compose-equivalence tests.
  These check receipt consistency, not report truth or publisher authenticity.
  Compatible-controller release selection/start/update/rollback and interrupted
  recovery are IMPLEMENTED with PASS34 isolated lifecycle tests. Actual image
  identity, maintenance/viewer admission, rollback verdict preservation, live-child
  timeout handling and credential preservation are covered by simulated Docker
  operations plus real private state files. No real release acceptance is inferred.
  Real exact-artifact deployment acceptance, authenticated publication and
  reproducible binary build materials remain NOT COMPLETE. Controller-source
  migration is explicitly separate from supported compatible image updates.
- Real clean-host / unfamiliar-user acceptance and measurements: NOT RUN. A
  separate unused VPN config and disposable supported host have been requested.
- Production installation: UNCHANGED; guided setup's foreign-container refusal
  was verified without reading its credentials or changing services.
- Draft publication and protected CI: next checkpoint records PR/exact revision.
  Keep this goal active until the remaining acceptance/distribution work is done.
