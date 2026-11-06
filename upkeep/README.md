# Image housekeeping

The Firefox updater keeps the active `private-firefox:mozilla` image and one
rollback under `private-firefox:prev`. After a successful build, verification and
stack recovery, it attempts to remove only the image displaced from `:prev`.
It preserves images with another tag or registry digest. Removal never uses
force or prunes parent images; Docker can refuse removal if a container or
child image still needs the old image. Cleanup failure does not invalidate the
successful update. Failed updates and failed recovery do not run cleanup.

For older Firefox leftovers from manual or fingerprint builds, review the
matching dangling images, then prune each project/service separately:

```bash
docker image ls --filter dangling=true \
  --filter label=com.docker.compose.project=private-browser \
  --filter label=com.docker.compose.service=firefox
docker image prune \
  --filter label=com.docker.compose.project=private-browser \
  --filter label=com.docker.compose.service=firefox \
  --filter until=168h

docker image ls --filter dangling=true \
  --filter label=com.docker.compose.project=pbfp \
  --filter label=com.docker.compose.service=firefox
docker image prune \
  --filter label=com.docker.compose.project=pbfp \
  --filter label=com.docker.compose.service=firefox \
  --filter until=168h
```

Tag any deliberately retained audit specimen before pruning, or keep a verified
image archive bound to the recorded immutable identity. Historical reports and
test logs remain retained; citing an image ID does not require a duplicate Docker
copy once the required specimen is safely archived. Do not prune private archives.

Future Gluetun source/test/build images have dedicated labels. The runtime
candidate starts from a different base and does not inherit these labels:

```bash
docker image ls --filter dangling=true \
  --filter label=io.private-browser.project=private-browser \
  --filter label=io.private-browser.role=gluetun-build
docker image prune \
  --filter label=io.private-browser.project=private-browser \
  --filter label=io.private-browser.role=gluetun-build \
  --filter until=168h
```

Labels do not retroactively classify existing images. Run this periodically
after finished experiments; tagged test images remain until explicitly retired.

BuildKit cache is separate from these image objects. Inspect the selected builder
with `docker buildx du --builder default --verbose`. On a shared builder, use
reviewed cache-record ID filters with `docker buildx prune --builder default
--filter id=RECORD_ID`; unfiltered pruning also drops other projects' build cache.
Shared cache sizes are not additional reclaimable image storage. Build-stage
image labels do not provide a project-label filter for BuildKit cache.
