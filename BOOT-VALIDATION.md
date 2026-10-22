# Actual guarded boot observation — 21 October 2026

The bounded actual-boot question in [issue #33](https://github.com/silverfox-2096/private-browser/issues/33)
has supporting execution evidence: on one authorized host boot, the real startup
guard withheld initialization while local VPN health was unavailable, then started
`/init` and Firefox after its readiness branch. Network/browser recovery passed.
This is a guard-barrier finding, not a test of browser requests executed without a
tunnel or a guarantee for every future boot.

## Observed startup sequence

A new, separately authorized root observer used a private kernel trace instance.
Its notify unit became ready before Docker, recorded process creation/exec and
namespace identities, and sampled actual IPv4/IPv6 policy, tunnel presence and
local health. It did not bypass the guard, remove protection, inject an unprotected
browser request, run another VPN or rerun the completed historical collector.

| Seconds on this boot's monotonic clock | Observation |
|---|---|
| 16.322791 | Observer ready; admitted image/configuration hashes match |
| 21.673683 | Docker engine exec observed |
| 26.059174 / 26.153773 | Browser container process creation / configured shell guard exec |
| 27.145–31.904 | Shared namespace, tunnel and ordered policy present; sampled local health still unsuccessful; no `/init` or Firefox exec |
| 31.904109 | Last complete pre-init policy/tunnel/namespace observation |
| approximately 32.21466 | Verified guard's readiness message, before the same process execs `/init` |
| 32.215188 | `/init` exec in that process and shared namespace |
| 32.272943 | First completed independent successful local-health snapshot |
| 38.100535 | First Firefox exec, followed by its actual browser executable |

Before `/init`, only the configured shell and its readiness-loop helpers were
observed in the browser container. Boot-time hashes match the admitted read-only
[startup guard](startup-guard.sh), Compose/override and policy. Both original image
identities and the shared network were preserved. The guard message is emitted
only after its exact local HTTP200 and tunnel-presence checks; it is evidence of
that verified branch, not an independent HTTP packet capture.

The guard's retained stdout timestamp was correlated with same-boot journal
realtime/monotonic pairs spanning the guard-to-Firefox interval. The 1,006 pairs
have an observed offset spread of 8 microseconds; timestamp quantization was
included when checking order. The resulting message interval precedes `/init` by
about 0.5 milliseconds. A later approximately 445-millisecond wall-clock step was
identified outside that startup calibration segment; a single offset was not used
across it. Relative kernel timestamps remain the primary process timeline. This
clock correlation has normal measurement limits, not a universal timing guarantee.

## Original INCOMPLETE result and supplementary review

The installed analyzer's result remains **INCOMPLETE**, unchanged and retained.
Two limitations required supplementary review:

- The independent successful health snapshot finished about 58 milliseconds after
  `/init`, so it alone cannot prove readiness before init. The additionally retained
  readiness stdout, verified guard source/branch and clock correlation establish
  that ordering; successful independent health precedes actual Firefox startup.
- The 64MiB recording budget ended collection around boot second752, roughly
  12 minutes after observation began. A full 15-minute recording is not claimed.
  The startup sequence above is retained well before this boundary. All 32 CPU
  overrun/commit-overrun/drop counters and final unread-tail counters are zero;
  there were no trace parser/reader errors. The explicit late budget marker is
  preserved, rather than turned into a successful whole-recording verdict.

The supplementary assessment checks these additional sources and the original
trace without modifying the installed collector/analyzer or replacing its verdict.
A positive control and seven faults (missing/late readiness message, absent/wrong-
boot/discontinuous clock metadata, early recording cutoff and kernel loss) verify
that missing evidence cannot support this finding. Source, original output,
clock pairs, captures and reproducible assessment stay private; no credentials,
browser data or private topology are published.

There were no sampled tunnel-absent operations and no forced unprotected request.
Their absence is **NOT TESTED**, not a packet-negative containment result. This
bounded barrier observation closes the selected actual-boot claim; runtime outage,
IPv6/local-address and relay evidence retain their separately documented scopes.
No residual boot uncertainty was silently accepted on the operator's behalf.

## Recovery and final operating state

After collection shutdown was verified by its boot/PID-bound completion record,
the authorized recovery held the existing maintenance safeguards and checked:

- maintained read-only source/shared namespace/ordered IPv4+IPv6 policy assertions;
- network4/4, including a controlled tunnel stop and verified recovery;
- browser7/7, normal public HTTPS/DNS, and API unauthenticated401/authenticated200;
- HTTPS viewer302 to `/login/` before releasing maintenance;
- original container/image/network/configuration identities and optional-service state.

The viewer is restored, the updater's original enabled/active timer states are
restored, and the new observer is stopped, disarmed and removed. Its source and
evidence are retained privately; removal did not restart the browser or VPN. During this21October boot/recovery work, no running image, Compose, policy or startup guard was replaced; no new
recurring collector or timer remains enabled. The old collector was left untouched.

The [current status register](FOLLOW-UP-PLAN.md#current-status-register) records the
assessment round. Retained advisory findings and the explicit time-bounded R1
operator disposition are separate from this boot finding.

The separately approved22October [VPN security replacement](gluetun-patched/README.md)
passed isolated and live runtime controls after this boot observation. It does
not retroactively change the identities in the21October trace or constitute
an actual-boot test of the new image. The startup guard/policy are unchanged.
