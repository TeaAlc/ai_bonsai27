# Build versions, releases, and publication

[Back to README](../README.md). Run project commands from the repository root.

Versions are calculated by the pinned [greatliontech/semrel](https://github.com/greatliontech/semrel) tool. Without a release tag the first version is `1.0.0`. After a reachable stable release tag, `fix` and `perf` commits increment the patch version, `feat` increments the minor version, and breaking changes increment the major version. Documentation and maintenance commits alone retain the existing version. Both lightweight and annotated tags such as `v1.2.3` are supported.

```bash
./tools/version.sh                  # print the calculated version
./tests/test-version.sh             # check version rules using isolated Git fixtures
BONSAI_IMAGE=localhost/bonsai2-27b:1.0.0 ./run.sh
```

Version calculation uses committed history and locally available stable tags. Builds do not fetch, create Git tags, push, or publish a release. Use a full Git checkout with release tags; shallow checkouts are rejected. Repeated builds can reuse the same version until release history changes, and uncommitted changes do not influence semrel's version calculation. OCI labels record the calculated version and source commit; `io.bonsai.git.dirty` identifies builds that include uncommitted project changes. The `latest` alias tracks the last successful local build. A successful build
atomically records `results/last-build.json`: immutable image ID, engine, source
revision, version, cleanliness, backend manifest/archive pins, model and semrel
pins, the Containerfile/base digest, and installed package versions. Every successful
build can be published, including development builds; their dirty label is
preserved. Different `vX.Y.Z` and `X.Y.Z` source commits are rejected before semrel analysis.

A published registry image does not automatically create a Git release tag.
Record each published release with its source commit and push that Git tag;
otherwise semrel keeps calculating the same pending release version. For
example, after `v1.2.0` exists, subsequent `fix` commits produce `1.2.1`.
Documentation commits alone do not increase it. Keep release tags available
in every checkout that builds images.

### Create a release and build its images

Use the release script instead of a standalone build when preparing a release:

```bash
./create_realease.sh
```

The filename intentionally follows the project's `create_realease.sh` spelling.
A clean working tree, complete Git history, Git, Python 3, curl, sha256sum,
flock, and a working Podman build environment are required. Prepare backend
bundles with `prepare.sh` beforehand. The online workflow:

1. Fetches public project Git tags over HTTPS without overwriting conflicts.
2. Reads the published GHCR `latest` image's OCI labels without downloading its
   layers, restoring a missing release tag at the image's actual source commit.
3. Uses the pinned semrel tool to calculate the next version from Git history.
4. Creates an annotated local release tag at HEAD, then calls `build.sh` as its
   final action to build the versioned image and `latest`.

If the build fails, the newly created release tag is removed; recovered tags
for already published releases remain. Existing tags are never moved. Repeating
at the same release commit rebuilds the same version. A docs-only commit after
an existing release is rejected because it cannot create a new Git release tag
at the same version. To build and publish that commit anyway, use `./build.sh`
and `./image_push.sh`. The release script does not manufacture patch bumps for
non-releasable commits.

A network/authentication error or a conflict between Git tags and registry
metadata stops the online workflow. The image must have valid project source,
version, revision, and clean-build labels; its source must be an ancestor of
HEAD. For intentionally offline work, use `./create_realease.sh --offline`;
that mode relies only on local release tags and cannot verify registry history.

Publication remains explicit. After the script succeeds, publish both the
image and the printed Git release tag so other checkouts get the same baseline:

```bash
./image_push.sh
git push origin v1.3.0             # substitute the version printed by the script
```

`tools/tag-release.sh` remains available for tagging an already built clean
local image from its OCI labels. It rejects dirty builds and conflicting tags.
Neither release helper creates a GitHub Release page or pushes automatically.
Run `./tests/test-create-release.sh` to check bumps, rollback, baseline recovery,
and rejection of dirty or docs-only release attempts with isolated fixtures.

The pinned executable, cached download, installer, release policy, and tool license all live in [tools/](../tools/README.md). Subsequent builds use the verified cached binary without downloading again. Git, Podman, and basic shell utilities remain host prerequisites. Downloaded tool files are excluded from Git and the container image.

## Publishing to GitHub Container Registry

The published image is available at
[ghcr.io/teaalc/ai_bonsai27](https://ghcr.io/teaalc/ai_bonsai27).
For a public package, pull the latest image without authentication:

```bash
podman pull ghcr.io/teaalc/ai_bonsai27:latest
```

For a private package, first log in with your GitHub username and a personal
access token (classic) with `read:packages` permission. Your account must have
read access to the package. Enter the token at the password prompt:

```bash
podman login ghcr.io --username YOUR_GITHUB_USERNAME
podman pull ghcr.io/teaalc/ai_bonsai27:latest
```

An `unauthorized` or `invalid username/password` error can mean the package is
private, credentials are missing or expired, or the account lacks access.
Run `podman login` again to replace stale credentials. Publication through
`image_push.sh` uses temporary credentials and does not log in future pulls.

To allow anonymous pulls, the package owner can open
[the package page](https://github.com/users/TeaAlc/packages/container/package/ai_bonsai27),
select **Package settings**, and set **Change visibility** to **Public**.
Package visibility is separate from repository visibility. See
[GitHub's package access documentation](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

`./image_push.sh` publishes the last successful local build as both
`ghcr.io/teaalc/ai_bonsai27:<version>` and
`ghcr.io/teaalc/ai_bonsai27:latest`. The version comes from the semrel-generated
label of the actual local image. The source is pinned by `results/last-build.json`, independently of mutable
`latest` aliases or newer Git commits. Every successful project build can be
published, including uncommitted development builds and rebuilds whose source
commit differs from the existing Git release tag. No Git release tag is required
or changed by pushing.

Each push updates both the version tag and `latest`, replacing any existing
images under those tags. Documentation-only changes can retain the same SemVer;
this does not prevent publication. The selected engine pushes the recorded image,
then the script verifies the published version's image ID and source labels,
copies its exact manifest to `latest`, and verifies both remote manifest digests.
Retry after a failed promotion; the already pushed version remains available.
Use a registry digest when you need an immutable image reference. Serialize
publication across machines because the two tag updates are separate operations.

```bash
./build.sh                              # build the image to publish
./image_push.sh                          # ask for the token with hidden input
./image_push.sh --token 'YOUR_GHCR_TOKEN' # alternatively pass the token explicitly
```

The script prefers a working Podman with the local build and falls back to a
working Docker daemon. You can select an engine explicitly with
`BONSAI_PUSH_ENGINE=podman` or `BONSAI_PUSH_ENGINE=docker`. When Docker is selected
and lacks the exact recorded image ID, the script exports a temporary Docker archive
and loads it into Docker before publishing. An older Docker `latest` alias is ignored.

The login user defaults to `TeaAlc`; set `BONSAI_GHCR_USER` if your token belongs
to another authorized GitHub user. The token needs the `write:packages` scope.
For local CLI authentication, GitHub documents a personal access token
(classic). The OCI source label links the package to this project. See
[GitHub's Container Registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

Authentication uses `--password-stdin` and a temporary, restricted credential
configuration under `/tmp/bonsai27/`, removed when the script exits. Tokens are
never saved in the repository or permanent Podman/Docker configuration. Prefer
the hidden prompt if you want to keep the token out of shell history and process
arguments; an explicit `--token` parameter may be visible there.

GitHub initially creates packages as private. Access for other users depends on
the package's configured visibility and permissions. Once authorized, another
machine can run the published image with:

```bash
podman pull ghcr.io/teaalc/ai_bonsai27:latest
BONSAI_IMAGE=ghcr.io/teaalc/ai_bonsai27:latest ./run.sh
```

The GPU host setup remains required; missing GGUF files are downloaded at startup. Run
`python3 -B tests/test-image-push.py` to check engine selection, prompt and token
parameter handling, Docker import, and failure behavior without publishing.
