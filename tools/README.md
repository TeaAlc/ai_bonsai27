# Local build tools

`install.sh` installs the pinned Linux x86-64 binary of
[greatliontech/semrel](https://github.com/greatliontech/semrel) **0.7.0** into
`semrel/bin/semrel`. It verifies both the official archive and the extracted
binary against the SHA256 values in `semrel/artifacts.sh`. Downloaded archives
are kept in `semrel/downloads/`. These generated directories are excluded from
Git and from the container build context. No global tool installation, Go,
Node.js, or sudo is required; the host still supplies Git, Bash, curl, tar,
sha256sum, and Podman.

`version.sh` installs the tool if necessary and prints only the calculated
stable image version on stdout. Build scripts call it automatically. Run it
manually with `./tools/version.sh`; an optional repository path is supported
for the isolated tests.

Release policy is in `semrel/config.yaml`: the first version is `1.0.0`, `fix`
and `perf` cause a patch bump, `feat` causes a minor bump, and breaking changes
cause a major bump. Other commit types do not bump the version. The highest
stable SemVer tag reachable from HEAD is the baseline; both `v1.2.3` and
`1.2.3`, lightweight and annotated, are supported. Prerelease and non-SemVer
tags do not serve as release baselines.

The pinned tool compares tag object hashes with commit hashes. To support
annotated release tags, `version.sh` creates a temporary local Git snapshot,
dereferences reachable stable tags there, and supplies the tool configuration
from this directory. The upstream binary is unchanged, and semrel performs
the actual commit analysis and version calculation. The original repository
is not modified. Temporary directories are removed on exit and live under
`/tmp/bonsai27/` by default, or the standard `TMPDIR` when supplied.

Only committed local history is analyzed. Obtain full history and release
tags before building a clone; shallow checkouts are rejected. A build does not
fetch remote history, create release tags, push, or publish a release. Repeated
builds without new releasable commits return the same version. Adding a release
tag is a separate release action, not part of this installer or image build.

Validate the version behavior with `./tests/test-version.sh`. It uses temporary
repositories and checks ordinary commits, breaking changes, lightweight and
annotated tags, unrelated branch tags, and shallow-checkout rejection.

The upstream Apache 2.0 license is retained in `semrel/LICENSE`.

`tag-release.sh` creates an annotated local release tag from the latest built
Podman image's OCI version and source revision labels. Override the image with
BONSAI_IMAGE. The image must come from a clean commit present in this checkout.
Existing tags are never moved; a conflicting source revision is an error.
The helper does not build, push, or publish. Tag the completed build before
starting work on the next release so semrel has the correct baseline.

The root `create_realease.sh` orchestrates release creation before its final
`image_build.sh` invocation. `published-release.py` reads public GHCR manifest/config
metadata, validates the project's source labels, and reports the latest release
version and source commit without downloading image layers. Python runs with
bytecode disabled. Online releases recover missing published baseline tags;
offline releases rely only on existing local tags. Build failures roll back
only the new release tag, and existing release tags are never moved.

## Verified builds and publication

`project.sh` provides one checkout-local lock shared by preparation, build,
release, tagging, and publication. Release/build snapshots are established after
locking. `backend-artifacts.sh` pins archives and manifest identities;
`verify-backend.py` rejects extra files, symlinks, and checksum mismatches.
`build-receipt.py` writes `results/last-build.json` atomically after inspecting a
successful build and collecting its installed package inventory. Source snapshots
and temporary backend copies live under `/tmp/bonsai27/` (or `TMPDIR`).

`registry.py` validates that receipt, verifies the newly pushed version against
its exact image ID and source labels, and promotes the exact manifest to `latest`.
Every successful build is publishable, including dirty builds and builds without
matching Git release tags. Every push replaces the version and `latest` aliases;
existing registry contents do not block publication. Git refs remain unchanged.
Credentials come from a private temporary file, never
from command arguments to this helper. Registry checks do not constitute a
transaction across independent publishing machines; publication must be
serialized. `image_push.sh` imports the receipt's exact Podman image into Docker
when needed, independently of Docker's `latest` alias.

Run `tests/run-regressions.sh` for isolated version, release, publication,
preparation, cache, signal, configuration, and evidence regressions. No fixture
publishes to GHCR. Real GPU/API validation uses `tests/run-qa.sh`.
