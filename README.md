![Unicorns grazing in a sunny fairyland meadow with a rainbow and castle](assets/fairyland-unicorns-1080p.png)

# Bonsai 2 27B with Vision in Podman

Run **`Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf`**, a Bonsai 2 model based on Qwen3.8-27B, with a Bonsai-compatible `llama-server` and its OpenAI-compatible API. The language model, MTP head, KV caches, and recurrent state run on the NVIDIA GPU. The separate **BF16 vision encoder/projector runs on CPU and system RAM** to save VRAM.

The server uses MTP with `n_max=2`, Flash Attention, and `q8_0` K/V caches for both the main model and MTP draft. The default context window is **16,384 tokens**, configurable through `BONSAI_CTX_SIZE`. The API is published on localhost only.

## Requirements

- x86-64 Linux or WSL2, Bash, rootless Podman, Git, `curl`, `tar`, and `sha256sum`. Python 3 is needed for builds, release tooling, and tests. `flock` is needed on the local build-tool filesystem; model mounts use directory locks. The coding test also pulls `python:3.12-slim` if it is not cached.
- A discrete NVIDIA GPU with compute capability **8.6 or 8.9** (the bundled Ampere/Ada backend) or **12.0** (Blackwell backend). Other compute capabilities are rejected by the container before downloads. Backend selection uses CUDA device 0 inside the container; `run.sh` does not require `nvidia-smi`. An explicit backend override must match that device.
- Enough free VRAM for the entire language model and its 16k runtime state. The tested 12 GB laptop GPU worked with this configuration. Approximately 8 GB of free VRAM is a practical starting point, but usage varies by host and workload. Memory pressure causes startup to fail; the configuration does not silently offload language-model weights to CPU.
- **Native Linux:** a working NVIDIA driver and NVIDIA Container Toolkit with CDI already configured, so `--device nvidia.com/gpu=all` works. Native Linux execution has not been tested in this project.
- **WSL2:** a working NVIDIA Windows driver, `/dev/dxg`, and the projected CUDA driver libraries under `/usr/lib/wsl/lib`. `run.sh` mounts `/usr/lib/wsl` read-only so the container can access the host driver libraries. Do not install a separate Linux NVIDIA driver in WSL2 for this setup.

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
through this directory. Use `download_models.sh --verify` to check pinned cache contents, or `--repair` to replace damaged pinned files after a verified download. Custom model paths are not automatically checked against these pins.
`prepare.sh` remains available for preparing models and backends on the host.

A shared Windows/network model mount can reject `flock` with “Function not
implemented”. Model downloads now use directory locks instead. Waiting for
another download defaults to ten minutes (`BONSAI_DOWNLOAD_WAIT_SECONDS`); retry or raise the limit if that transfer is still running. Each HTTP attempt defaults to a one-hour limit (`BONSAI_DOWNLOAD_TIMEOUT`), with a 30-second connection timeout and a stalled-transfer limit. Normal exits and handled stop signals cancel the download child and release the owned lock. After a forced container/VM shutdown,
a stale `<filename>.lock.d` may remain: remove that directory and its temporary status file only once all downloads using the cache have stopped, then restart. Existing `.part`
files are retained for resumable transfers. Old `.lock` files from previous
images are not used by the new downloader. Stop old `flock`-based containers before sharing their cache with directory-lock versions; the two locking protocols do not coordinate.

### Download models separately

The host download script uses the same pinned artifacts as the container and
requires Bash, `curl`, `sha256sum`, and standard coreutils:

```bash
./download_models.sh                      # save in the current directory
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./download_models.sh
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./download_models.sh --verify
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./download_models.sh --repair
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

`build.sh` installs the pinned `semrel` build tool locally under `tools/` if needed, calculates a version from Git history, checks the extracted backend files again, and builds `localhost/bonsai2-27b:<version>`. Every successful build produces both the calculated version tag and `localhost/bonsai2-27b:latest` from the same image; `run.sh` uses that alias by default. The calculated version is independent of the pinned llama-server backend commit. Backend runtime files, `entrypoint.sh`, the shared download helper, and a small CUDA driver probe are copied into the image; model files are mounted read/write as a persistent download cache when the container starts. The Bash entrypoint groups and comments model, server, GPU, MTP, and generation options, validates its settings before loading, and uses `exec` so the server receives container stop signals. Clean builds use a committed Git snapshot; development builds overlay local files and are marked dirty. Both backend snapshots are checked against pinned manifest identities, with additional files and symlinks rejected. `prepare.sh`, build, release, tag, and push operations share a local checkout lock. Preparation reuses verified archives offline and replaces runtime trees only after extraction and validation. Temporary build files use `/tmp/bonsai27` by default (or an explicitly set `TMPDIR`). See [data/README.md](data/README.md) for the directory layout and [RECHERCHE.md](RECHERCHE.md) for pinned revisions and checksums.

`run.sh` creates the model cache directory, detects WSL2 versus native Linux, leaves backend detection to CUDA device 0 inside the container, and starts the `bonsai2-27b` container in the background. Its default API base URL is **`http://127.0.0.1:8080/v1`**, with model ID **`bonsai2-27b`**. No API key is configured for local access.

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
| `BONSAI_CTX_SIZE` | `16384` | No | Context window in tokens; integer 512–262144 (VRAM permitting) |
| `BONSAI_REASONING_EFFORT` | `medium` | No | Reasoning effort: `low`, `medium`, or `xhigh` |
| `BONSAI_PORT` | `8080` | No | Available host TCP port, 1–65535; bound to localhost |
| `BONSAI_IMAGE` | `localhost/bonsai2-27b:latest` | For the GHCR image | Image to start; a versioned tag pins a build |
| `BONSAI_GPU_BACKEND` | Automatic | No | Empty, `blackwell` (12.0), or `ampere-ada` (8.6/8.9); override must match CUDA device 0 |
| `BONSAI_CONTAINER_NAME` | `bonsai2-27b` | No | Container name; select a unique name for independent instances |
| `BONSAI_DOWNLOAD_WAIT_SECONDS` | `600` | No | Shared-cache lock wait, integer 1–86400 seconds |
| `BONSAI_DOWNLOAD_TIMEOUT` | `3600` | No | Per-attempt HTTP limit, integer 1–86400 seconds |

`BONSAI_CTX_SIZE` must be a decimal integer from 512 to 262144. Leading zeros are normalized; oversized integers are rejected before arithmetic. The upper bound follows the model's supported context and does not guarantee available VRAM. `BONSAI_REASONING_EFFORT` accepts `low`, `medium`, or `xhigh` (default: `medium`). The official model default is `xhigh`; `medium` gives shorter reasoning. The model accepts `low` but it may behave much like `xhigh`; `high` is invalid and can cause an HTTP 500. Larger contexts need more VRAM; 32k has not been validated on the test notebook. See the [official model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) and [known issues](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/main/KNOWN_ISSUES.md).

Optional positional arguments passed to `run.sh` are forwarded to `llama-server`, for example `./run.sh --log-verbose`. Additional server flags can override the defaults, so preserve the GPU-only language-model and CPU vision settings. `BONSAI_BASE_URL` configures request scripts; it does not change the container binding. `BONSAI_GPU_BACKEND` is forwarded when supplied and validated against the detected device; `BONSAI_MODEL` and `BONSAI_MMPROJ` are container entrypoint settings and are not forwarded from the host environment by `run.sh`. For status and logs, use `podman ps` and `podman logs -f bonsai2-27b`.

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
| Backend | Automatically detected; optional `BONSAI_GPU_BACKEND=blackwell` or `BONSAI_GPU_BACKEND=ampere-ada` | Allowed override values: `blackwell` (compute capability 12.0), `ampere-ada` (8.6/8.9); must match CUDA device 0. Unset or empty enables automatic detection |
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

### Podman Desktop: configure the GPU entirely in the UI

The simplest GPU setup is a single CDI device selector in **Advanced → Devices**;
NVIDIA Container Toolkit/CDI supplies the driver mounts automatically. The
selected engine must support CDI selectors in its Docker-compatible API. This
was verified in released source for **Podman 6.0.0 and 6.1.1**. Update the actual
engine inside the Podman machine, not only the Windows client or Desktop app,
when the device form fails with `stat nvidia.com/gpu=all`. The CDI form below
then needs no manual WSL driver/device mounts, provided the engine's NVIDIA
Toolkit/CDI setup is already working. Upgrading does not itself install or
configure that setup. The reported engine version remains unknown.

The following manual mount setup is a **WSL2 fallback for engines affected by
that API conversion issue**, not the preferred setup. The device fields are
under **Advanced**, not the **Basic** tab shown in the screenshot. Use:

| Tab / field | WSL2 value |
| --- | --- |
| Basic → Command | Leave empty |
| Basic → Volumes: driver source / container path | `/usr/lib/wsl` → `/usr/lib/wsl:ro` (the `:ro` suffix sets read-only access) |
| Basic → Volumes: model source / container path | Your writable model directory → `/models` |
| Advanced → Devices → Host Device | `/dev/dxg` |
| Advanced → Devices → Container Device | `/dev/dxg` |
| Advanced → Devices → Permissions | Enable **Read**, **Write**, and **Mknod** |
| Security → Security options | `label=disable` |

These paths must exist in the Linux environment of the engine selected in
Desktop. The driver mount source is that engine's `/usr/lib/wsl`, not a Windows
folder selected through the file picker. Enter the paths manually. In the form
with only source/target fields, the target `/usr/lib/wsl:ro` produces the bind
string `/usr/lib/wsl:/usr/lib/wsl:ro`; do not enable read-only for the whole
container root filesystem or for the model cache. Keep the default entrypoint; it adds
the WSL driver library search path automatically. Do not also add the CDI
selector for this route. This API mapping and the image's CUDA backend detection
were tested here on WSL2; the Windows Desktop application itself was not tested.
If `/dev/dxg` is missing, the selected engine does not have this WSL GPU route.
A stock Hyper-V machine cannot use it; select a GPU-enabled WSL2 machine.

For **native Linux/CDI**, or a WSL2 engine with working CDI API support, use:

| Tab / field | Value |
| --- | --- |
| Basic → Entrypoint | Keep `/usr/local/bin/bonsai-server` |
| Basic → Command | Leave empty |
| Basic → Volumes | Host model directory accessible to the engine → `/models`, writable |
| Basic → Port mapping | Host port `8080` → container port `8080` |
| Basic → Environment variables | Optional `BONSAI_CTX_SIZE=16384`, `BONSAI_REASONING_EFFORT=medium`; backend detection is automatic |
| Advanced → Devices → Host Device | `nvidia.com/gpu=all` — enter only this selector, without `--device` |
| Advanced → Devices → Container Device | Leave empty; the UI uses the host value |
| Advanced → Devices → Permissions | Enable **Read**, **Write**, and **Mknod** |
| Security → Security options | `label=disable` when needed for the CDI/SELinux configuration |

Click **Start Container** after configuring all tabs. No console `podman run`
is required. Device access is a creation setting; recreate an incorrectly
configured container rather than just restarting it. If the port dialog does
not provide a host-address field, its port binding may expose the API on all
host interfaces; inspect the created port binding and restrict host access as
needed. The CLI examples below explicitly bind to localhost.

The UI sends these fields as `HostConfig.Devices`. Engines containing the
upstream CDI mapping fix recognize a qualified selector when the container-device
field is empty or equal to the host selector. A creation error such as
`stat nvidia.com/gpu=all: no such file or directory` means this path treated the
selector as a file; changing the container's backend or adding image libraries
cannot repair that API conversion. On WSL2, use the real-device settings above;
otherwise update the engine to a version containing the
[upstream CDI API fix](https://github.com/containers/podman/commit/f374f2c95bc8c7642a5a47d03298fe036f0f77c0)
and verify its CDI setup. Released-source checks confirm the fix and handler
call in Podman 6.0.0 and 6.1.1; this is not a claim that 6.0.0 was the first
release or that an unknown installed engine contains it. See the official
[Desktop device form](https://github.com/podman-desktop/podman-desktop/blob/main/packages/renderer/src/lib/image/RunImage.svelte)
and [Podman CDI mapping helper](https://github.com/containers/podman/blob/main/pkg/api/handlers/utils/docker_device.go).
This recipe was checked against upstream source; it has not been runtime-tested
in Desktop here. Older Desktop/engine versions may differ. A working NVIDIA
CDI specification must already exist in the selected engine. On Windows, use
the documented WSL2 GPU route; entering a selector does not add GPU passthrough
to a stock Hyper-V machine.

### Desktop command fields do not configure GPU devices

Do not put `--device nvidia.com/gpu=all` or `--gpus all` in the Desktop
**Command/Arguments** field. That field becomes the container's `Config.Cmd`
and is passed to the image entrypoint. It cannot configure Podman or Docker
GPU access. Leave it empty for normal startup. Podman Desktop exposes device
mappings in the **Advanced** tab; configure GPU access there as described above.

For example, this inspect output indicates misplaced runtime options:

```json
"Cmd": ["--device", "nvidia.com/gpu=all"]
```

The CLI syntax is `podman run [PODMAN OPTIONS] IMAGE [CONTAINER ARGUMENTS]`.
Place the GPU flag, port, volume, and environment options **before the image**.
For a GPU-enabled CDI engine with models at `/mnt/g/models_podman`, create a
new container with the following single-line command (PowerShell or Bash):

```bash
podman run -d --name bonsai2-27b-cdi --device=nvidia.com/gpu=all --security-opt label=disable -p 127.0.0.1:8080:8080 --mount type=bind,source=/mnt/g/models_podman,target=/models -e BONSAI_CTX_SIZE=16384 -e BONSAI_REASONING_EFFORT=medium ghcr.io/teaalc/ai_bonsai27:latest
podman logs -f bonsai2-27b-cdi
```

The source directory must exist in the engine's Linux environment; substitute
its actual path or use the named-volume example below. Stop an old container
first if it still occupies port 8080. Restarting the old container does not
change its creation settings. With this command `Config.Cmd` should be empty;
verify actual GPU access using the CUDA probe below rather than relying solely
on `HostConfig.Devices`, whose representation can vary with CDI and Podman.
An `unresolvable CDI devices` error now comes from Podman before the container
starts: check NVIDIA Container Toolkit and the CDI specification in that engine.
See [Podman's run syntax](https://docs.podman.io/en/latest/markdown/podman-run.1.html)
and [Podman Desktop's GPU setup](https://podman-desktop.io/docs/podman/gpu).

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
| `BONSAI_GPU_BACKEND` | Automatic GPU detection | No | `blackwell` for 12.0; `ampere-ada` for 8.6/8.9. Other capabilities are unsupported; overrides are checked against the actual GPU |
| `BONSAI_CTX_SIZE` | `16384` | No | Context tokens; integer 512–262144, subject to available VRAM. Larger values need more VRAM |
| `BONSAI_REASONING_EFFORT` | `medium` | No | Official accepted values: `low`, `medium`, `xhigh`; `high` is invalid |
| `BONSAI_MODEL` | `/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf` | No | Language-model path **inside** the container |
| `BONSAI_MMPROJ` | `/models/Ternary-Bonsai-2-27B-mmproj-BF16.gguf` | No | BF16 vision-projector path **inside** the container |
| `BONSAI_DOWNLOAD_WAIT_SECONDS` | `600` | No | Lock wait: integer 1–86400 seconds |
| `BONSAI_DOWNLOAD_TIMEOUT` | `3600` | No | Per-attempt HTTP timeout: integer 1–86400 seconds |
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
an error. An explicit `blackwell` or `ampere-ada` value is checked against the
actual CUDA device before downloads. Detection selects a backend, not GPU passthrough: the GPU
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

Run a fresh identified suite against its own containers on port 18080:

```bash
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./tests/run-qa.sh
```

The suite starts a 16k server, checks the API, two vision fixtures, three coding
problems with 23 assertions, and the included unicorn image. It then starts the
same image with an 8k context and records `/props`. Containers are removed on
exit, and the model cache is retained. `BONSAI_PORT` can select another free port;
`BONSAI_IMAGE` can pin the image under test. `BONSAI_TEST_READY_SECONDS` bounds readiness waiting (default 600, allowed 1–3600 seconds), with per-health-call timeouts of at most three seconds. The API tests all use
`BONSAI_BASE_URL`. The 16k test requires a context of at least 16384 tokens.

Evidence is saved under `results/runs/<suite-id>/`, with image/container IDs,
source revision, model hashes, GPU capability/backend, context, timestamps,
responses, timings, and a checksum-bound server log. QA rejects empty summaries,
wrong answers, mismatched runs/images, and altered logs. To inspect a saved run:

```bash
python3 -B tests/qa.py results/runs/<suite-id>
```

For individual tests against an existing local Podman container, explicitly set
`BONSAI_TEST_CONTAINER`, `BONSAI_TEST_SUITE_ID`, `BONSAI_TEST_RUN_DIR`,
`BONSAI_BASE_URL`, and `BONSAI_CTX_SIZE`. Keep those settings shared across its
API/vision/coding tests. Passing saved-evidence QA does not prove a new live run.
Coding programs run in restricted containers without network access; a separate
harness must complete its assertions, and timed-out containers are removed.

Offline regression fixtures can be run with:

```bash
./tests/run-regressions.sh
./tests/test-runtime.sh             # real GPU dependency checks; needs Podman
python3 -B tests/test-coding-runner.py # real restricted-container failure checks
./tests/test-container-download.sh  # real PID 1 stop/lock cleanup; needs Podman
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./tests/test-offline-start.sh
```

Python entry points disable bytecode caching. Use `python3 -B` for extra commands;
avoid `py_compile` and `compileall`. All local evidence remains excluded from Git.
The following performance figures were recorded before this hardening work:

On **WSL2 with an RTX 5070 Ti Laptop GPU (12 GB)**, the 16k API test, both vision function tests, and all 23 coding assertions passed. The saved QA audit reported **14/14 checks passed**. A 15,009-token prompt was processed at **629 prompt tokens/s**. Three coding generations measured **60.5, 57.8, and 54.8 generated tokens/s**. These are individual measurements on this notebook, not guaranteed throughput elsewhere. MTP `n_max=2` was active; it is not necessarily the fastest setting for every prompt.

A separate [vision quality check](results/vision/quality-check.json) sent [this synthetic image](results/vision/quality-check.png) through `/v1/chat/completions`. The model correctly described a red square at the upper left and a blue circle at the lower right. This verifies a simple image request, not general photo understanding or OCR. The linked results are local test artifacts and are excluded from Git.

The recorded server log showed **66/66 language-model layers on CUDA0**, a 5,995.31 MiB CUDA0 model buffer, `q8_0` K/V caches for main and draft contexts, Flash Attention, and `CLIP using CPU backend` for vision. A later GPU snapshot showed **9,078 of 12,227 MiB** in use, including other processes; it is not an isolated model-only VRAM measurement.

A new development-image run on **2026-09-30** passed **18/18 identified QA
checks**, both vision shapes, the unicorn description, and all 23 coding
assertions. It processed 15,009 prompt tokens at **696.1 prompt tokens/s**;
the coding responses measured **61.4, 68.6, and 59.4 generated tokens/s**.
MTP counters were **68/72, 76/88, and 66/78 accepted/drafted tokens** for those
coding requests. Detailed logs verified GPU allocation, main/draft Flash
Attention and q8 caches, and CPU vision. Evidence:
`results/runs/20260930T152810Z-495703/`, image
`ce3dda017fddc4c8e421bb698873c060aa1da4038bee96bdcfb4283975c591e2`
(marked dirty during development). These observations are separate from the
older measurements above and from a later clean release verification.

The final **clean 1.4.0 release image** also passed **18/18 QA checks**, all 23
coding assertions, vision and the unicorn image, 16k/8k context verification,
both backend dependency checks, download stop/read-only-cache tests, and a
warm-cache OpenAI request with networking disabled. Its source is
`de4b8edccb4940c9d005f89a77ae199fa142c5a8`, with local release tag `v1.4.0`;
image ID `f39b06302ab6b70df04157cc8729a121eb4adf31f0dec52af31701b376f81c6b`.
Evidence: `results/runs/20260930T154315Z-510298/`. It measured **703.9 prompt
tokens/s** on 15,009 tokens and **67.0, 66.9, and 64.6 generated tokens/s** on the
three coding cases. The release workflow built both `1.4.0` and `latest` locally;
GHCR publication of this release remains a separate step. Subsequent documentation
commits do not change this built image's source identity or release tag.

## Moving to another computer

On the target system, copy the project and run `./prepare.sh`, `./build.sh`, and `./run.sh`. Alternatively, export the built image and transfer it alongside `run.sh`. For offline startup, also transfer **both** GGUF files into a model directory:

```bash
podman save -o bonsai2-27b.tar localhost/bonsai2-27b:latest
# On the target system:
podman load -i bonsai2-27b.tar
BONSAI_MODEL_DIR=/path/to/models BONSAI_CTX_SIZE=16384 ./run.sh
```

The target still needs working NVIDIA GPU access and a supported compute capability. WSL2 with sm120 was tested; native Linux and sm86/sm89 are packaged but have not had runtime validation here. The image contains CUDA runtime libraries and Bonsai-compatible binaries, while NVIDIA driver libraries come from the target host. See [RECHERCHE.md](RECHERCHE.md) for model variants, server forks, and the choice of artifacts.

## Dependency refresh and platform validation

The Ubuntu 24.04 base is pinned by digest in both Containerfile stages. Apt
packages are resolved during a build and recorded in its receipt; builds are
therefore auditable but not promised to be bit-for-bit reproducible. Refresh the
base digest intentionally, rebuild, review package/bundle/license inventories,
and rerun both dependency checks and the live suite before a release. Never
modify verified upstream bundles to make checks pass.

The Blackwell bundle documents driver 570 or newer. NVIDIA's CUDA 12.8 release
notes list toolkit drivers ≥570.26 (Linux) / ≥570.65 (Windows); CUDA 12.4 GA lists
≥550.54.14 / ≥551.61. These toolkit driver rows differ from the broader CUDA
12.x minor-compatibility floor, which has feature restrictions and does not
establish Blackwell support. Use a driver that supports the actual GPU and the
bundle. See [CUDA 12.8 release notes](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html),
[CUDA 12.4 release notes](https://docs.nvidia.com/cuda/archive/12.4.0/cuda-toolkit-release-notes/index.html),
and [minor compatibility limits](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html).

| Deployment | Status | Remaining verification |
| --- | --- | --- |
| Direct Podman / WSL2 / RTX 5070 Ti Laptop, sm120 | Cold download and fresh 16k/8k API, vision, coding, MTP/FA/cache allocation checks passed | Warm-cache startup also passed with networking disabled; every run records its image/source identity |
| Native Linux / CDI / sm86 or sm89 | Packaged; library resolution checked here | Real GPU inference and mount behavior on that host |
| RTX 4070 Ti Super / shared Windows model mount | Backend packaged; ENOSYS/race fixes covered by fixtures | Repeat downloads, restart, and live API checks on the reported filesystem |
| Docker Desktop / WSL2 GPU route | Documented; engine fallback tested with isolated stores | Real Desktop GPU inference |
| Independently GPU-provisioned Hyper-V Linux guest | Conditional; no test host available | Guest driver, CDI, CUDA probe, then full API suite |
| Stock Podman Desktop Hyper-V GPU machine | Unsupported by the documented upstream route | Use WSL2 or a GPU-enabled remote Linux engine |

Downloads and model loading happen before `/health` is ready. Inspect container
logs to distinguish waiting for a cache lock, transferring files, loading model
weights, and serving requests. Warm-cache starts use no model-download network
access. Driver/passthrough failures happen before model downloads.

## Repository conventions

See [TODO_PLAN.md](TODO_PLAN.md) for the 2026-09-30 repository audit, fresh
validation results, remaining defects, and the prioritized implementation plan.
Its status table records implemented changes and the hardware/publication checks still pending.

See [AGENTS.md](AGENTS.md) for the project workflow and validation rules. Keep
documentation, script comments, and messages in English; use `BONSAI_` for
project configuration variables. Keep temporary work under `/tmp/bonsai27/`
and Python bytecode caches out of the project. Completed changes use English
Conventional Commit messages compatible with semantic-release and end with
`(by Codex)`.
