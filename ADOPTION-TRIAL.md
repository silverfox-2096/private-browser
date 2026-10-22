# First installation and usability trial

Status: **NOT RUN**. This is a blank trial worksheet, not passing evidence.
Use it with [the quick-start](QUICKSTART.md) and [release gates](RELEASING.md).
Keep the completed raw worksheet outside the repository; publish only a reviewed,
credential-free summary. Do not turn blank fields into release receipts.

## Prepare the trial

A facilitator supplies a disposable Linux x86-64 host with a local rootful Docker
Engine, Compose v2, Python 3.10+, the documented tools and working TUN device.
Record whether prerequisites were already installed: the guided installer does
not install them. The host must have no existing Private Browser installation.
Use a separate unused Proton WireGuard configuration. Keep its contents, the
browser password and internal API key out of recordings, screenshots and reports.
Do not use the maintainer's running installation for this trial.

Ask a person unfamiliar with the repo to follow only the quick-start. Record
questions and intervention; do not silently coach them and call the run unassisted.
They may stop whenever they are uncertain. The facilitator handles access and
measurement without changing the participant's instructions.

Record before starting:

| Field | Actual observation |
|---|---|
| Date, trial identifier and facilitator | NOT RECORDED |
| Participant familiarity; consent to any recording | NOT RECORDED |
| Host OS/version, architecture, CPU, RAM and available disk | NOT RECORDED |
| Docker, Compose and Python versions | NOT RECORDED |
| Exact source commit and quick-start revision | NOT RECORDED |
| Source build or reviewed bundle version/digests | NOT RECORDED |
| Prerequisites already present; preparation time | NOT RECORDED |
| Confirmation: separate unused VPN configuration | NOT RECORDED |

## Observe the first installation

1. Start timing immediately before acquisition from the quick-start. Record
   download, configuration, build/pull and readiness milestones separately.
2. Let the participant obtain the source and run `./setup.sh`. Observe whether
   they can find their provider file, choose a country and create a login without
   exposing or manually editing a secret. Record the exact failing step/error,
   with credential values removed, if setup stops.
3. Stop installation timing only at an actual `READY` result. A failed or
   interrupted attempt remains recorded even if a later attempt succeeds.
4. Let the participant handle the certificate warning themselves after checking
   the documented local address. Record confusion or abandonment. Capture the
   actual local login screen and an empty/disposable browser session only after
   that step; no provider/account page, password entry or private tabs.
5. Before browsing, have them follow the documented `./pb verify` and separate
   browser WebRTC/DNS checks. Retain each real result and its scope; `READY` alone
   does not establish these results. Record the exact running image identities.
6. Have them find `status` and `doctor`, then explain what closing the viewer
   does versus stopping the stack. Ask them to stop and start again only after
   they acknowledge that browser-session data is erased. Confirm that setup
   credentials are preserved, without copying their contents into the report.

Record resource use on this otherwise disposable host with a documented sampler
and interval. Include Docker daemon/build workers in the measurement boundary;
timing only the CLI process does not measure their memory. State whether memory
is total host usage or an attributable increase and whether disk is allocated or
logical usage. Record idle baseline, peak memory, end disk growth and sampler
coverage. Mark missing or ambiguous measurements INCOMPLETE rather than guessing.

## Record the outcome

| Observation | Result / evidence reference |
|---|---|
| Acquisition, configuration, build/pull, READY and total durations | NOT RECORDED |
| Resource method, interval, baseline, peak memory and disk growth | NOT RECORDED |
| Runtime source/image identities and tested platform | NOT RECORDED |
| Setup, actual network/browser/policy/recovery checks | NOT RUN |
| Actual login/browser screenshots; redaction review | NOT RECORDED |
| Unassisted completion; questions, errors and coaching | NOT RUN |
| Rerun and credential preservation; stop/start expectations | NOT RUN |
| Remaining friction, owner and proposed correction | NOT RECORDED |
| Reviewer, retained failures and final PASS/FAIL/INCOMPLETE scope | NOT RECORDED |

An assisted run is useful feedback, not an unassisted usability pass. Fix the
specific friction, then repeat the affected acceptance steps; use another
unfamiliar participant for a new unassisted trial. A successful installation does
not establish support for other platforms or guarantee a duration for all hosts.

## Additional prebuilt lifecycle acceptance

Before advertising prebuilt downloads, use the same disposable-host boundaries
to exercise actual bundle installation, compatible image update, normal rollback
and interrupted/failed update recovery. Record both source revisions/bundle
identities, the exact images before/after, original failure verdict and observed
maintenance, policy, network and login recovery results. Follow
[the existing recovery procedure](RELEASING.md#guided-prebuilt-installation-updates-and-rollback)
and preserve its gate/journal when recovery is INCOMPLETE. Do not improvise failure
injection on production. Local simulated lifecycle tests do not fill these fields.

Review actual reports before making the exact-artifact/runtime receipts required
by the packager. Report hashes establish consistency; they do not authenticate
the publisher or prove an observation occurred. Keep the original private evidence
under the facilitator's control and link only its reviewed public summary.
