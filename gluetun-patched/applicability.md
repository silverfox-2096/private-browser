# Finding-by-finding applicability and remediation

All 31 original HIGH package matches are retained below. These are package/version findings, not proof of exploitation. The refreshed Trivy 0.70.0 and 0.76.0 reports reproduce all 31, including the same fix versions; no additions/removals or CRITICAL findings. Full refreshed scans also retain lower severities omitted from the historical filtered JSON.

Source analysis uses the exact v3.41.3 commit and Go 1.25.11, Linux/amd64, the cmd/gluetun entry point and default build tags. Paths below are conservative static call paths across all program modes, not demonstrated live-configuration reachability. For example, provider-updater and optional proxy paths may be disabled by configuration. No exploit was exercised.

Both shipped binaries are stripped (`-s -w`). govulncheck v1.9.0 internal/vulncheck/binary.go lines 107–113 explicitly falls back to module-level precision when symbols are absent. Its synthesized function findings MUST NOT be reported as actual recovered binary symbols or runtime calls. Actual build metadata and matching-source dependency closure are separate evidence.

| CVE | Component | Installed → scanner fix | Matching-source evidence | Primary advisory |
|---|---|---|---|---|
| CVE-2026-14456 | libcrypto3 | 3.5.7-r0 → 3.5.8-r0 | Alpine OpenSSL libraries installed. Advisory requires an OpenSSL QUIC server listener; Go binary has CGO_ENABLED=0. No such listener established by this task; update packages regardless. | [OpenSSL advisory index](https://openssl-library.org/news/vulnerabilities/) |
| CVE-2026-14456 | libssl3 | 3.5.7-r0 → 3.5.8-r0 | Alpine OpenSSL libraries installed. Advisory requires an OpenSSL QUIC server listener; Go binary has CGO_ENABLED=0. No such listener established by this task; update packages regardless. | [OpenSSL advisory index](https://openssl-library.org/news/vulnerabilities/) |
| CVE-2026-39828 | golang.org/x/crypto | v0.45.0 → 0.52.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5014) |
| CVE-2026-39829 | golang.org/x/crypto | v0.45.0 → 0.52.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5018) |
| CVE-2026-39830 | golang.org/x/crypto | v0.45.0 → 0.52.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5017) |
| CVE-2026-39831 | golang.org/x/crypto | v0.45.0 → 0.52.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5019) |
| CVE-2026-39832 | golang.org/x/crypto | v0.45.0 → 0.52.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5006) |
| CVE-2026-39835 | golang.org/x/crypto | v0.45.0 → 0.52.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5015) |
| CVE-2026-42508 | golang.org/x/crypto | v0.45.0 → 0.52.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5021) |
| CVE-2026-46595 | golang.org/x/crypto | v0.45.0 → 0.52.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5023) |
| CVE-2026-46597 | golang.org/x/crypto | v0.45.0 → 0.52.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5013) |
| CVE-2026-56854 | golang.org/x/crypto | v0.45.0 → 0.55.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6303) |
| CVE-2026-25681 | golang.org/x/net | v0.47.0 → 0.55.0 | Source call path to affected symbol; internal/updater/html.Fetch:32 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5029) |
| CVE-2026-27136 | golang.org/x/net | v0.47.0 → 0.55.0 | Source call path to affected symbol; internal/updater/html.Fetch:32 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5030) |
| CVE-2026-33814 | golang.org/x/net | v0.47.0 → 0.53.0 | Affected package imported; no affected-symbol call path reported | [Go advisory](https://pkg.go.dev/vuln/GO-2026-4918) |
| CVE-2026-39821 | golang.org/x/net | v0.47.0 → 0.55.0 | Source call path to affected symbol; internal/healthcheck.Check:32, internal/vpn.onTunnelUp:25 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5026) |
| CVE-2026-46600 | golang.org/x/net | v0.47.0 → 0.56.0 | Affected package imported; no affected-symbol call path reported | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5942) |
| CVE-2026-78669 | golang.org/x/net | v0.47.0 → 0.60.0 | Source call path to affected symbol; internal/cli.ClientKey:22, cmd/gluetun.main:115 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6611) |
| CVE-2026-56851 | golang.org/x/text | v0.31.0 → 0.41.0 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6629) |
| CVE-2026-56852 | golang.org/x/text | v0.31.0 → 0.39.0 | Source call path to affected symbol; internal/cli.addProviderFlag:31 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5970) |
| CVE-2026-33818 | stdlib | v1.25.11 → 1.25.13, 1.26.6, 1.27.0-rc.3 | Source call path to affected symbol; cmd/gluetun.init:17 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5972) |
| CVE-2026-39821 | stdlib | v1.25.11 → 1.25.13, 1.26.6, 1.27.0-rc.3 | Source call path to affected symbol; internal/healthcheck.Check:32, internal/vpn.onTunnelUp:25 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-5026) |
| CVE-2026-39822 | stdlib | v1.25.11 → 1.25.12, 1.26.5, 1.27.0-rc.2 | Affected package imported; no affected-symbol call path reported | [Go advisory](https://pkg.go.dev/vuln/GO-2026-4970) |
| CVE-2026-56853 | stdlib | v1.25.11 → 1.25.13, 1.26.6, 1.27.0-rc.3 | Source call path to affected symbol; internal/healthcheck.Run:34, internal/httpserver.Run:60 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6089) |
| CVE-2026-56858 | stdlib | v1.25.11 → 1.25.13, 1.26.6, 1.27.0-rc.3 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6091) |
| CVE-2026-56859 | stdlib | v1.25.11 → 1.25.13, 1.26.6, 1.27.0-rc.3 | No affected-package import or symbol call reported in matching-source closure | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6088) |
| CVE-2026-56860 | stdlib | v1.25.11 → 1.25.13, 1.26.6, 1.27.0-rc.3 | Source call path to affected symbol; internal/healthcheck.Check:32 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6218) |
| CVE-2026-56862 | stdlib | v1.25.11 → 1.25.13, 1.26.6, 1.27.0-rc.3 | Source call path to affected symbol; internal/cli.ClientKey:22, internal/httpserver.Run:60 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6090) |
| CVE-2026-78667 | stdlib | v1.25.11 → 1.26.9, 1.27.2 | Affected package imported; no affected-symbol call path reported | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6609) |
| CVE-2026-78669 | stdlib | v1.25.11 → 1.26.9, 1.27.2 | Source call path to affected symbol; internal/cli.ClientKey:22, cmd/gluetun.main:115 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6611) |
| CVE-2026-97031 | stdlib | v1.25.11 → 1.26.9, 1.27.2 | Source call path to affected symbol; internal/httpserver.Run:60, cmd/gluetun.main:126 | [Go advisory](https://pkg.go.dev/vuln/GO-2026-6607) |

The ten x/crypto SSH findings have no SSH import in this executable's matching-source dependency closure. This is stronger than inference from WireGuard use, but is not an independently recovered binary-symbol result. x/net/html is imported and affected HTML parsing calls are reported for provider update paths. The HTTP/TLS/ASN.1/URL findings have source call paths where shown; authentication does not eliminate pre-handler HTTP parsing exposure, and TLS is used for DNS and health checks. No finding is suppressed or labeled false positive.

The OpenSSL advisory rates CVE-2026-14456 LOW; Trivy's selected vendor severity is HIGH. We preserve both descriptions. Its condition is a QUIC server listener receiving Initial packets. Installed libssl/libcrypto establish library presence, not a configured QUIC listener. OpenVPN and wget are native clients; using WireGuard does not remove their installed libraries. The Go executable is statically built, so apk upgrades cannot patch its Go libraries.

Remediation: Alpine package refresh fixes libcrypto3/libssl3. Rebuilding with Go 1.27.2 fixes stdlib; replacing x/net with v0.60.0, x/crypto with v0.57.0 and x/text with v0.42.0 fixes the remaining HIGH matches. Module resolution also raises x/sys v0.48.0, x/mod v0.41.0, x/sync v0.23.0 and x/tools v0.49.0, and go.mod's minimum Go version to 1.26.0. CIRCL v1.6.3 additionally addresses the original candidate's LOW finding. No application-source edits were needed. See exact go.mod/go.sum diff.
