# syntax=docker/dockerfile:1
# checkov:skip=CKV_DOCKER_2:Final stage inherits the pinned Gluetun connectivity healthcheck
# checkov:skip=CKV_DOCKER_3:Gluetun init must configure interfaces and firewall as root
# checkov:skip=CKV_DOCKER_4:ADD fetches the exact remote stable-source archive with SHA256 verification; COPY cannot fetch URLs
FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS source
ADD --checksum=sha256:5f382f180780632afe57d9cba03978bc0524e469c8288f72e0f416a7749ac62c https://codeload.github.com/passteque/gluetun/tar.gz/3d1e20c5551e9cae1f9d938dc7b7214a6987f27e /tmp/upstream.tar.gz
WORKDIR /src
RUN tar -xzf /tmp/upstream.tar.gz --strip-components=1
COPY go.mod go.sum ./
RUN go mod download && go mod verify

FROM source AS test
# Disposable compiler tools are refreshed for tests; they are absent from the image.
# hadolint ignore=DL3018
RUN apk add --no-cache build-base
# Keep test execution separate from compiler installation for readable failures.
# hadolint ignore=DL3059
COPY tests/configfile-diagnostics.patch /tmp/configfile-diagnostics.patch
COPY tests/auth_contract_test.go internal/server/middlewares/auth/pb_contract_test.go
COPY tests/local_policy_contract_test.go internal/firewall/pb_local_policy_contract_test.go
# Only test diagnostics change. Pin the original test to fail on source drift.
RUN printf '%s\n' "bb1e76ed06d4b8b92467595ec18c2c85f37f8df31e55ec4c1583e40dbecc76d6  internal/server/middlewares/auth/configfile_test.go" > /tmp/upstream-test.sha256 \
    && sha256sum -c /tmp/upstream-test.sha256 \
    && patch -p1 -F 0 < /tmp/configfile-diagnostics.patch \
    && CGO_ENABLED=1 go test -race -count=1 ./...

FROM source AS build
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w -X main.version=v3.41.3-pb1 -X main.created=2026-10-18 -X main.commit=3d1e20c5551e9cae1f9d938dc7b7214a6987f27e" -o /entrypoint cmd/gluetun/main.go
# Retain build metadata separately from the compiled binary.
# hadolint ignore=DL3059
RUN go version -m /entrypoint > /buildinfo.txt

FROM qmcgaw/gluetun:v3.41.3@sha256:fa19cc76b2af13d57a8d3dc3066f2ada061b1c761b8aecf989b3877c0486e027 AS candidate
# Refresh Alpine packages, independently of the statically linked Go binary.
RUN apk upgrade --no-cache && apk info -vv > /package-versions.txt
COPY --from=build /entrypoint /gluetun-entrypoint
COPY --from=build /buildinfo.txt /buildinfo.txt
LABEL org.opencontainers.image.version="v3.41.3-pb1" \
      org.opencontainers.image.title="Private Browser patched Gluetun stable candidate" \
      org.opencontainers.image.source="https://github.com/silverfox-2096/private-browser" \
      org.opencontainers.image.revision="3d1e20c5551e9cae1f9d938dc7b7214a6987f27e+pb1" \
      org.opencontainers.image.created="2026-10-18"
