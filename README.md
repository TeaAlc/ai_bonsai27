![Unicorns grazing in a sunny fairyland meadow with a rainbow and castle](assets/fairyland-unicorns-1080p.png)

# Bonsai 2 27B with Vision in Podman

Run **`Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf`**, a Bonsai 2 model based on Qwen3.8-27B, with a Bonsai-compatible `llama-server` and its OpenAI-compatible API. The language model, MTP head, KV caches, and recurrent state run on the NVIDIA GPU. The separate **BF16 vision encoder/projector runs on CPU and system RAM** to save VRAM.

The server uses MTP with `n_max=2`, Flash Attention, and `q8_0` K/V caches for both the main model and MTP draft. The default context window is **16,384 tokens**, configurable through `BONSAI_CTX_SIZE`. The API is published on localhost only.

## Requirements

- x86-64 Linux or WSL2, Bash, rootless Podman, Git, `curl`, `tar`, and `sha256sum`. Python 3 is needed for the tests. The coding test also pulls `python:3.12-slim` if it is not cached.
- A discrete NVIDIA GPU with compute capability **8.6 or 8.9** (the bundled Ampere/Ada backend) or **12.0** (Blackwell backend). Other compute capabilities are rejected by `run.sh`. The first GPU reported by `nvidia-smi` is selected as CUDA0.
- Enough free VRAM for the entire language model and its 16k runtime state. The tested 12 GB laptop GPU worked with this configuration. Approximately 8 GB of free VRAM is a practical starting point, but usage varies by host and workload. Memory pressure causes startup to fail; the configuration does not silently offload language-model weights to CPU.
- **Native Linux:** a working NVIDIA driver and NVIDIA Container Toolkit with CDI already configured, so `--device nvidia.com/gpu=all` works. Native Linux execution has not been tested in this project.
- **WSL2:** a working NVIDIA Windows driver, `/dev/dxg`, and `/usr/lib/wsl/lib/nvidia-smi`. `run.sh` mounts `/usr/lib/wsl` read-only so the container can access the host driver libraries. Do not install a separate Linux NVIDIA driver in WSL2 for this setup.

The scripts themselves do not require `sudo`. Host driver and CDI installation, if needed, are outside their scope.

## Prepare, build, and run

Run all commands below from the project directory inside Linux or WSL2.

### Start the published image

Pull the image and start the container with an explicit persistent model cache:

```bash
podman pull ghcr.io/teaalc/ai_bonsai27:latest
BONSAI_IMAGE=ghcr.io/teaalc/ai_bonsai27:latest \
BONSAI_MODEL_DIR="$HOME/bonsai-models" \
BONSAI_CTX_SIZE=16384 \
BONSAI_REASONING_EFFORT=medium \
BONSAI_PORT=8080 \
./run.sh
```

**Required:** the GPU prerequisites above, an available image, an unused
container name `bonsai2-27b`, and enough disk space in a writable model cache.
Missing language-model and BF16 vision files are downloaded by the container
from pinned revisions and SHA256-verified before llama-server starts. The first
start therefore needs internet access; later starts reuse nonempty readable
files without downloading or rechecking their checksum. To use the published
image, set `BONSAI_IMAGE` as shown; otherwise `run.sh` selects the local build.
The other four variables are optional and are shown explicitly for clarity.
GPU devices, driver mounts, model mounts, and backend selection are configured
automatically by `run.sh`; no additional GPU flags are needed.

The container starts in the background. Follow its startup logs, then check
readiness once model loading has completed:

```bash
podman logs -f bonsai2-27b
# Press Ctrl+C to stop following logs; the container keeps running.
curl --fail http://localhost:8080/health
./simple_request.sh localhost:8080
```

If you change `BONSAI_PORT`, use that port in the health check and request.
The model files are not included in the image. `BONSAI_MODEL_DIR` defaults to
the caller’s current directory and is mounted read/write at `/models`. Downloads use
`.part` files, resume after interruption, and are renamed only after checksum
verification; atomic per-file `.lock.d` directories prevent simultaneous
downloads without requiring `flock` support on the model filesystem. An invalid
download is deleted and startup fails. Existing files can also be supplied
through this directory; remove a corrupt cached file to download it again.
`prepare.sh` remains available for preparing models and backends on the host.

A shared Windows/network model mount can reject `flock` with “Function not
implemented”. Model downloads now use directory locks instead. Waiting for
another download is limited to ten minutes; retry if that transfer is still
running. Normal exits release the lock. After a forced container/VM shutdown,
a stale `<filename>.lock.d` may remain: remove that empty directory only once
all downloads using the cache have stopped, then restart. Existing `.part`
files are retained for resumable transfers. Old `.lock` files from previous
images are not used by the new downloader.

### Download models separately

The host download script uses the same pinned artifacts as the container and
requires Bash, `curl`, `sha256sum`, and standard coreutils:

```bash
./download_models.sh                      # save in the current directory
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./download_models.sh
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./run.sh
```

Use the same `BONSAI_MODEL_DIR` for download and startup. Relative paths are
resolved against the directory from which you invoke the scripts, even when
the scripts themselves are elsewhere. The directory can contain previously
downloaded files with these exact names:

- `Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf`
- `Ternary-Bonsai-2-27B-mmproj-BF16.gguf`

### Build and start locally

```bash
./prepare.sh
./build.sh
./run.sh
```

No environment variables are mandatory for a local build: `run.sh` defaults to
`localhost/bonsai2-27b:latest`, a 16,384-token context, `medium` reasoning, and
host port `8080`.

`prepare.sh` downloads missing PTQ1_0 MTP Lean and official BF16 vision files with SHA256 verification, reuses existing model files, and downloads and verifies both CUDA backend bundles. The GGUF files stay in `BONSAI_MODEL_DIR`, defaulting to the caller’s current directory; existing files are reused. Backend archives and extracted binaries live under `data/backends/{blackwell,ampere-ada}/`; research inputs live under `data/research/`. The downloads and image need several gigabytes of disk space.

`build.sh` installs the pinned `semrel` build tool locally under `tools/` if needed, calculates a version from Git history, checks the extracted backend files again, and builds `localhost/bonsai2-27b:<version>`. Every successful build produces both the calculated version tag and `localhost/bonsai2-27b:latest` from the same image; `run.sh` uses that alias by default. The calculated version is independent of the pinned llama-server backend commit. Backend runtime files, `entrypoint.sh`, the shared download helper, and a small CUDA driver probe are copied into the image; model files are mounted read/write as a persistent download cache when the container starts. The Bash entrypoint groups and comments model, server, GPU, MTP, and generation options, validates its settings before loading, and uses `exec` so the server receives container stop signals. Temporary build files use `/tmp/bonsai27` by default (or an explicitly set `TMPDIR`). See [data/README.md](data/README.md) for the directory layout and [RECHERCHE.md](RECHERCHE.md) for pinned revisions and checksums.

`run.sh` creates the model cache directory, detects WSL2 versus native Linux, selects the backend from the first GPU's compute capability, and starts the `bonsai2-27b` container in the background. Its default API base URL is **`http://127.0.0.1:8080/v1`**, with model ID **`bonsai2-27b`**. No API key is configured for local access.

To change the context size or host port, stop and remove the existing named container before starting another:

```bash
podman stop bonsai2-27b
podman rm bonsai2-27b
BONSAI_CTX_SIZE=32768 BONSAI_PORT=8081 ./run.sh
```

### Parameters for `run.sh`

These are all environment variables read by `run.sh`:

| Variable | Default | Required? | Purpose |
| --- | --- | --- | --- |
| `BONSAI_MODEL_DIR` | Caller’s current directory | No | Host directory mounted read/write at `/models`; created if missing |
| `BONSAI_CTX_SIZE` | `16384` | No | Context window in tokens; integer ≥ 512 |
| `BONSAI_REASONING_EFFORT` | `medium` | No | Reasoning effort: `low`, `medium`, or `xhigh` |
| `BONSAI_PORT` | `8080` | No | Available host TCP port, 1–65535; bound to localhost |
| `BONSAI_IMAGE` | `localhost/bonsai2-27b:latest` | For the GHCR image | Image to start, e.g. `ghcr.io/teaalc/ai_bonsai27:latest`; use a versioned tag to pin a build |

`BONSAI_CTX_SIZE` must be an integer of at least 512. `BONSAI_REASONING_EFFORT` accepts `low`, `medium`, or `xhigh` (default: `medium`). The official model default is `xhigh`; `medium` gives shorter reasoning. The model accepts `low` but it may behave much like `xhigh`; `high` is invalid and can cause an HTTP 500. Larger contexts need more VRAM; 32k has not been validated on the test notebook. See the [official model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) and [known issues](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/main/KNOWN_ISSUES.md).

Optional positional arguments passed to `run.sh` are forwarded to `llama-server`, for example `./run.sh --log-verbose`. Additional server flags can override the defaults, so preserve the GPU-only language-model and CPU vision settings. `BONSAI_BASE_URL` configures request scripts; it does not change the container binding. `BONSAI_GPU_BACKEND` is detected automatically; `BONSAI_MODEL` and `BONSAI_MMPROJ` are container entrypoint settings and are not forwarded from the host environment by `run.sh`. For status and logs, use `podman ps` and `podman logs -f bonsai2-27b`.

## Start directly with Docker Desktop or Podman Desktop

No repository scripts are needed to start the image directly. Use
`ghcr.io/teaalc/ai_bonsai27:latest`, keep the image entrypoint, and configure the
following runtime settings in the container creation dialog or equivalent CLI.
The download behavior below requires an image built with the model-cache
feature; older published images require both GGUF files to exist already.

### Required runtime settings

| Setting | Value | Requirement |
| --- | --- | --- |
| Image | `ghcr.io/teaalc/ai_bonsai27:latest` or a versioned tag | Required |
| GPU access | Docker: `--gpus all`; Podman with CDI: `--device nvidia.com/gpu=all` | Required; environment variables alone do not enable GPU access |
| Models volume | Writable host directory or named volume mounted at `/models` | Required for persistent downloads; an empty writable directory is sufficient |
| Published port | Host `127.0.0.1:8080` → container `8080/tcp` | Required for the documented host API access; choose another free host port if needed |
| Backend | Automatically detected; optional `BONSAI_GPU_BACKEND=blackwell` or `BONSAI_GPU_BACKEND=ampere-ada` | Allowed override values: `blackwell` (compute capability 12.0), `ampere-ada` (8.6/8.9). Unset or empty enables automatic detection |
| Entrypoint | Keep the image default | Required for downloads and configured server startup |

Missing models are downloaded before the API becomes ready. Provide internet
access and enough disk space on first start; a populated cache supports offline
startup. In a Desktop application's **Volumes** section, enter your absolute
host model directory as the source, `/models` as the destination, and enable
write access. Alternatively, use a named volume as in the examples below.
Host bind paths must be accessible to the selected engine/VM. A named volume
belongs to that engine and avoids host-path sharing issues.

In **Environment variables**, use the container variables below. Configure
ports, volumes, and GPU devices separately. If the creation dialog cannot
express GPU access or the localhost binding, use the CLI command with the
Desktop application's engine selected, then manage the resulting container in
Desktop. These Desktop configurations have not been runtime-tested here;
the tested configuration is direct Podman inside WSL2.

### Hyper-V: GPU passthrough is a VM prerequisite

A standard **Podman Desktop Hyper-V machine does not provide supported NVIDIA
GPU access**. Podman Desktop's Windows GPU instructions explicitly require
WSL2 and exclude Hyper-V. Installing additional CUDA libraries inside this
container does not expose the Windows GPU to its Linux VM. See
[Podman Desktop's GPU prerequisites](https://podman-desktop.io/docs/podman/gpu).

The same image can be used in an independently configured **Hyper-V Linux
VM with working NVIDIA CUDA passthrough**. This is conditional compatibility,
not a tested Podman Desktop Hyper-V configuration. Hyper-V GPU assignment is
configured outside the image: Windows host → Linux guest GPU/driver → NVIDIA
Container Toolkit/CDI → container. Windows driver DLLs cannot replace Linux
`libcuda.so.1`, and a normal Hyper-V guest does not use the WSL `/dev/dxg` mount.

Microsoft documents DDA/GPU-P for qualifying Windows Server configurations;
DDA/GPU-P are not supported on desktop-class hardware or Windows 10/11 client
hosts in that documented deployment. Linux guest support, GPU models, drivers,
and licensing depend on the selected assignment method. Do not assume that
a GeForce laptop GPU qualifies. See
[Microsoft's GPU passthrough prerequisites](https://learn.microsoft.com/en-us/troubleshoot/windows-server/virtualization/troubleshoot-hyper-v-gpu-assignment-partitioning-passthrough-issues)
and [NVIDIA's Hyper-V passthrough guidance](https://docs.nvidia.com/vgpu/latest/grid-vgpu-user-guide/using-gpu-pass-through.html).

For a GPU-provisioned Podman machine, check the guest before starting the model
(these commands work from PowerShell or a Linux shell):

```bash
podman machine list
podman machine ssh nvidia-smi
podman machine ssh nvidia-ctk cdi list
podman run --rm --device nvidia.com/gpu=all --entrypoint bash ghcr.io/teaalc/ai_bonsai27:latest /opt/bonsai/check-runtime.sh
podman run --rm --device nvidia.com/gpu=all --entrypoint /opt/bonsai/cuda-compute-capability ghcr.io/teaalc/ai_bonsai27:latest
```

Use an image containing the runtime checks. For a separate Linux VM rather
than a Podman-managed machine, execute the guest checks inside that VM and the
container checks against its Podman engine. All dependency checks must pass,
and the CUDA probe must report 8.6, 8.9, or 12.0. Then use the CDI start command
below with a persistent named model volume. If the guest has no CUDA GPU,
switch Podman Desktop to a WSL2-backed machine or connect to a GPU-enabled Linux
engine. Host/guest driver and passthrough setup requires administrator access
and is not performed by this project.

The image already includes both CUDA backend runtimes, C/C++ runtime libraries,
CUDA detection, model downloads, HTTPS certificates, and dependency checks.
No additional Hyper-V-specific library inside the application image replaces
the missing VM GPU assignment. Hyper-V execution has not been tested here.

### Container environment variables

| Variable | Default in image/entrypoint | Required to set? | Meaning |
| --- | --- | --- | --- |
| `BONSAI_GPU_BACKEND` | Automatic GPU detection | No | `blackwell` for 12.0; `ampere-ada` for 8.6/8.9. Other capabilities are unsupported |
| `BONSAI_CTX_SIZE` | `16384` | No | Context tokens; integer ≥ 512. Larger values need more VRAM |
| `BONSAI_REASONING_EFFORT` | `medium` | No | Official accepted values: `low`, `medium`, `xhigh`; `high` is invalid |
| `BONSAI_MODEL` | `/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf` | No | Language-model path **inside** the container |
| `BONSAI_MMPROJ` | `/models/Ternary-Bonsai-2-27B-mmproj-BF16.gguf` | No | BF16 vision-projector path **inside** the container |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` | No; keep `compute` enabled | NVIDIA runtime driver features; CUDA needs `compute`, GPU tools need `utility` |
| `GGML_CUDA_BATCH_INVARIANT` | `1` | No | Preserve the bundled CUDA batch-invariant setting |

Supported GPU families and examples:

| Backend | Compute capability | Architecture | Supported GPU examples |
| --- | --- | --- | --- |
| `ampere-ada` | **8.6** | Ampere | GeForce RTX **30 series**, e.g. RTX 3060, 3080, 3090; professional RTX A2000, A4000, A5000, A6000 |
| `ampere-ada` | **8.9** | Ada Lovelace | GeForce RTX **40 series**, e.g. RTX 4060, 4070, 4090; professional RTX 2000 Ada, RTX 4000 Ada, RTX 6000 Ada |
| `blackwell` | **12.0** | Blackwell | GeForce RTX **50 series**, e.g. RTX 5060, 5070 Ti, 5090; professional RTX PRO 4000 Blackwell, RTX PRO 6000 Blackwell |

See [NVIDIA's official compute-capability list](https://developer.nvidia.com/cuda/gpus)
for your exact GPU. Architecture support does not guarantee enough VRAM for
this model and context size. The tested GPU is an RTX 5070 Ti Laptop GPU.
Other compute capabilities are unsupported by the bundled backends, including
the A100 (8.0), H100 (9.0), and B200 (10.0).

When `BONSAI_GPU_BACKEND` is unset or empty, the entrypoint queries CUDA device 0
through a bundled driver probe using `libcuda.so.1`; `nvidia-smi` is not required.
If that query fails, it tries `nvidia-smi` as a fallback. It selects
`ampere-ada` for 8.6/8.9 and `blackwell` for 12.0 before downloading models.
Missing driver libraries, unavailable GPU access, or an unsupported capability
causes startup to fail with
an error. An explicit `blackwell` or `ampere-ada` value bypasses detection; it
must match your GPU. Detection selects a backend, not GPU passthrough: the GPU
runtime/device configuration above remains required. Older images may retain
a fixed backend default; rebuild or pull a release containing this feature.

Normally keep both model paths unchanged and mount your selected host directory
at `/models`. A missing file at an overridden path receives the same pinned
artifact, not a different model chosen by its filename.

`BONSAI_MODEL_DIR`, `BONSAI_PORT`, and `BONSAI_IMAGE` are **host `run.sh` settings**,
not container settings. Setting them in a Desktop environment-variable dialog
will not create a mount, publish a port, or select an image. `BONSAI_BASE_URL`
only configures request clients. The container listens on `0.0.0.0:8080`;
restrict access by publishing it on host `127.0.0.1` as shown.

MTP (`n_max=2`), Flash Attention, `q8_0` main/draft K/V caches, GPU-only language
model placement, and CPU/RAM vision are already configured by the entrypoint.
They require no extra environment variables. Optional container command
arguments are appended to llama-server, for example `--log-verbose`; preserve
the default entrypoint and the project's GPU/vision settings.

### CUDA driver access errors

`libcuda.so.1: cannot open shared object file` means the host CUDA driver is
missing from the container or outside its library search path. Successful
model downloads or `nvidia-smi` output alone do not prove CUDA compute access.
The image includes both CUDA runtime bundles (CUDA runtime, cuBLAS/cuBLASLt,
llama/ggml, OpenMP), the C/C++ runtime, download tools, CA certificates, and the
GPU probe. Builds check every backend shared library and llama-server for
missing dependencies, allowing only the host-provided CUDA driver to be absent.
The image requests `NVIDIA_DRIVER_CAPABILITIES=compute,utility` and searches
standard NVIDIA runtime and WSL driver directories. It checks CUDA access
before downloading models, including when a backend is explicitly selected.

For Docker, recreate the container with `--gpus all` and keep
`NVIDIA_DRIVER_CAPABILITIES=compute,utility`; for Podman, use the CDI device or
the WSL device/driver mounts shown below. These settings must be applied at
container creation. A backend override cannot enable GPU access. Do not copy a
CUDA stub library into the image. Existing downloaded GGUF files can be reused
through the same model mount. See
[NVIDIA's driver capability documentation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html).

### Docker Desktop: direct start

Docker Desktop's NVIDIA GPU support requires **Windows with the WSL2 backend**.
Enable it and install a compatible Windows NVIDIA driver following
[Docker's GPU documentation](https://docs.docker.com/desktop/features/gpu/).
For a native Linux Docker Engine, NVIDIA Container Toolkit must already be
configured; this is a separate setup from Docker Desktop.

The following single-line command works in PowerShell or a Linux/WSL2 shell.
It uses a persistent named volume; the container detects the GPU backend:

```bash
docker volume create bonsai-models
docker run -d --name bonsai2-27b --gpus all -e NVIDIA_DRIVER_CAPABILITIES=compute,utility -p 127.0.0.1:8080:8080 --mount type=volume,source=bonsai-models,target=/models -e BONSAI_CTX_SIZE=16384 -e BONSAI_REASONING_EFFORT=medium ghcr.io/teaalc/ai_bonsai27:latest
docker logs -f bonsai2-27b
```

For a host directory,
replace the volume mount with
`--mount "type=bind,source=/absolute/path/to/models,target=/models"` (use your
actual Windows or Linux path). Create the directory first. Docker's GPU runtime
supplies driver access; the manual WSL driver mount used by `run.sh` is not
part of this Docker command.

### Podman Desktop: direct start with CDI

GPU access must be configured in the engine used by Podman Desktop. On Windows,
use a WSL2-backed Podman machine with NVIDIA Container Toolkit and a generated
CDI specification as described in
[Podman Desktop's GPU documentation](https://podman-desktop.io/docs/podman/gpu).
On native Linux, use the host's configured NVIDIA CDI setup.

```bash
podman volume create bonsai-models
podman run -d --name bonsai2-27b --device nvidia.com/gpu=all --security-opt label=disable -p 127.0.0.1:8080:8080 --mount type=volume,source=bonsai-models,target=/models -e BONSAI_CTX_SIZE=16384 -e BONSAI_REASONING_EFFORT=medium ghcr.io/teaalc/ai_bonsai27:latest
podman logs -f bonsai2-27b
```

A bind mount can replace
the named volume, using a source path accessible to the Podman engine.

For **Podman installed directly in your WSL2 distribution**, the tested GPU
access route uses `/dev/dxg` and the WSL driver directory instead of CDI. Run
this Bash command inside that distribution; it mounts the current directory
as the persistent model cache:

```bash
podman run -d --name bonsai2-27b \
  --device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro \
  --security-opt label=disable \
  -p 127.0.0.1:8080:8080 -v "$PWD:/models:rw" \
  -e BONSAI_CTX_SIZE=16384 -e BONSAI_REASONING_EFFORT=medium \
  ghcr.io/teaalc/ai_bonsai27:latest
```

After loading completes, check `http://localhost:8080/health` and send API
requests to `http://localhost:8080/v1` using model ID `bonsai2-27b`. Stop and
remove an existing container before creating another with the same name;
keep its model volume/directory to reuse the downloads.

## Image versions and build tools

Versions are calculated by the pinned [greatliontech/semrel](https://github.com/greatliontech/semrel) tool. Without a release tag the first version is `1.0.0`. After a reachable stable release tag, `fix` and `perf` commits increment the patch version, `feat` increments the minor version, and breaking changes increment the major version. Documentation and maintenance commits alone retain the existing version. Both lightweight and annotated tags such as `v1.2.3` are supported.

```bash
./tools/version.sh                  # print the calculated version
./tests/test-version.sh             # check version rules using isolated Git fixtures
BONSAI_IMAGE=localhost/bonsai2-27b:1.0.0 ./run.sh
```

Version calculation uses committed history and locally available stable tags. Builds do not fetch, create Git tags, push, or publish a release. Use a full Git checkout with release tags; shallow checkouts are rejected. Repeated builds can reuse the same version until release history changes, and uncommitted changes do not influence semrel's version calculation. OCI labels record the calculated version and source commit; `io.bonsai.git.dirty` identifies builds that include uncommitted project changes. The `latest` alias tracks the last successful local build.

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
an existing release is rejected rather than overwriting its versioned image.
The script does not manufacture patch bumps for non-releasable commits.

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

The pinned executable, cached download, installer, release policy, and tool license all live in [tools/](tools/README.md). Subsequent builds use the verified cached binary without downloading again. Git, Podman, and basic shell utilities remain host prerequisites. Downloaded tool files are excluded from Git and the container image.

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
label of the actual local image. Both remote tags use the same source image;
the version tag is pushed first, followed by `latest`.

```bash
./build.sh
./image_push.sh                          # ask for the token with hidden input
./image_push.sh --token 'YOUR_GHCR_TOKEN' # alternatively pass the token explicitly
```

The script prefers a working Podman with the local build and falls back to a
working Docker daemon. You can select an engine explicitly with
`BONSAI_PUSH_ENGINE=podman` or `BONSAI_PUSH_ENGINE=docker`. When Docker is selected
and only Podman holds the image, the script exports a temporary Docker archive
and loads it into Docker before publishing.

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

## API examples

Text chat:

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"bonsai2-27b","messages":[{"role":"user","content":"What is 19 + 23?"}],"max_tokens":128,"chat_template_kwargs":{"enable_thinking":false}}'
```

Vision uses the same endpoint and an OpenAI-style `image_url` content block. This standard-library Python example sends a local PNG as a data URL:

```python
import base64
import json
import urllib.request
from pathlib import Path

image = base64.b64encode(Path("image.png").read_bytes()).decode("ascii")
payload = {
    "model": "bonsai2-27b",
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": "Describe this image briefly."},
        {"type": "image_url", "image_url": {
            "url": "data:image/png;base64," + image
        }},
    ]}],
    "max_tokens": 256,
    "chat_template_kwargs": {"enable_thinking": False},
}
request = urllib.request.Request(
    "http://127.0.0.1:8080/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=600) as response:
    result = json.load(response)
print(result["choices"][0]["message"]["content"])
```

The short examples disable thinking so their output limits leave room for an answer. For reasoning requests, omit that override and provide a larger `max_tokens` allowance within the available context; reasoning tokens count toward that limit. PNG and JPEG data URLs are supported. `--no-mmproj-offload` keeps the BF16 vision weights and encoder computation on CPU; the language model processes the resulting image tokens on CUDA. The projector file is 931,145,856 bytes, and the observed CPU compute buffer was about 248 MiB. Image size also affects runtime and memory use.

## Quick vision request

Run `./simple_request.sh` to send the included [1920×1080 fairyland image](assets/fairyland-unicorns-1080p.png) to the local API with the question “What is visible in this image?” and print the complete response as indented JSON. The image shows grazing unicorns on a green meadow, bright sunshine, green trees, a rainbow, and a distant fairy-tale castle. The full-size image was tested successfully: the model identified the unicorns, rainbow, castle, and surrounding landscape. The script needs Python 3 but no extra Python packages. An optional `hostname[:port]` argument selects the API server. The default host is `localhost` and the default port is `8080`:

```bash
./simple_request.sh                    # localhost:8080
./simple_request.sh notebook           # notebook:8080
./simple_request.sh notebook:8081      # notebook:8081
```

An explicit argument overrides `BONSAI_BASE_URL`; without an argument, the environment variable remains supported. Remote access requires the server's API to be reachable from your machine; `run.sh` binds to localhost by default.

## Tests and measured performance

With the server running on the default port:

```bash
python3 -B tests/test-api.py       # model list, chat, and ~15k-token prompt
python3 -B tests/test-vision.py    # two known-shape image requests
python3 -B tests/test-coding.py    # three Python tasks, 23 assertions
./tests/test-model-download.sh    # cache, integrity, locking, and directory fixtures
./tests/test-gpu-backend.sh       # backend detection and overrides
./tests/test-cuda-probe.sh        # driver probe fixtures; requires a host C compiler
./tests/test-runtime.sh           # both backend dependencies and early CUDA failure; needs Podman/GPU
```

`tests/test-api.py` accepts `BONSAI_BASE_URL` and `BONSAI_CTX_SIZE`; its long-context test requires a window of at least 16k. The vision and coding scripts currently use port 8080. The coding script executes generated programs in restricted, network-disabled Python containers. Outputs are written to the local, Git-ignored `results/` directory. Project test scripts disable Python bytecode caching, and `simple_request.sh` invokes Python with `-B`, so these entry points do not create `__pycache__` directories. Use `python3 -B` or `PYTHONDONTWRITEBYTECODE=1` for any additional Python commands in the project; avoid `py_compile` and `compileall`, which explicitly write bytecode files.

`python3 -B tests/qa.py` checks **previously saved** runtime evidence, including `results/server.log`, the API and vision/coding results, and `results/context-env-8192.json` from a separate 8k-context run. It is an audit of the completed validation, not a fresh end-to-end test of the current container. Capture a current server log with `podman logs bonsai2-27b > results/server.log` after running the API tests; the 8k artifact requires a separate 8k start and a saved `/props` response.

On **WSL2 with an RTX 5070 Ti Laptop GPU (12 GB)**, the 16k API test, both vision function tests, and all 23 coding assertions passed. The saved QA audit reported **14/14 checks passed**. A 15,009-token prompt was processed at **629 prompt tokens/s**. Three coding generations measured **60.5, 57.8, and 54.8 generated tokens/s**. These are individual measurements on this notebook, not guaranteed throughput elsewhere. MTP `n_max=2` was active; it is not necessarily the fastest setting for every prompt.

A separate [vision quality check](results/vision/quality-check.json) sent [this synthetic image](results/vision/quality-check.png) through `/v1/chat/completions`. The model correctly described a red square at the upper left and a blue circle at the lower right. This verifies a simple image request, not general photo understanding or OCR. The linked results are local test artifacts and are excluded from Git.

The recorded server log showed **66/66 language-model layers on CUDA0**, a 5,995.31 MiB CUDA0 model buffer, `q8_0` K/V caches for main and draft contexts, Flash Attention, and `CLIP using CPU backend` for vision. A later GPU snapshot showed **9,078 of 12,227 MiB** in use, including other processes; it is not an isolated model-only VRAM measurement.

## Moving to another computer

On the target system, copy the project and run `./prepare.sh`, `./build.sh`, and `./run.sh`. Alternatively, export the built image and transfer it alongside `run.sh`. For offline startup, also transfer **both** GGUF files into a model directory:

```bash
podman save -o bonsai2-27b.tar localhost/bonsai2-27b:latest
# On the target system:
podman load -i bonsai2-27b.tar
BONSAI_MODEL_DIR=/path/to/models BONSAI_CTX_SIZE=16384 ./run.sh
```

The target still needs working NVIDIA GPU access and a supported compute capability. WSL2 with sm120 was tested; native Linux and sm86/sm89 are packaged but have not had runtime validation here. The image contains CUDA runtime libraries and Bonsai-compatible binaries, while NVIDIA driver libraries come from the target host. See [RECHERCHE.md](RECHERCHE.md) for model variants, server forks, and the choice of artifacts.

## Repository conventions

See [TODO_PLAN.md](TODO_PLAN.md) for the 2026-09-30 repository audit, fresh
validation results, remaining defects, and the prioritized implementation plan.
Its TODOs describe planned work, not features already implemented.

See [AGENTS.md](AGENTS.md) for the project workflow and validation rules. Keep
documentation, script comments, and messages in English; use `BONSAI_` for
project configuration variables. Keep temporary work under `/tmp/bonsai27/`
and Python bytecode caches out of the project. Completed changes use English
Conventional Commit messages compatible with semantic-release and end with
`(by Codex)`.
