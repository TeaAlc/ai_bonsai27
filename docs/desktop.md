# Desktop and direct-engine setup

[Back to README](../README.md). Run project commands from the repository root.

No repository scripts are needed to start the image directly. Use
`ghcr.io/teaalc/ai_bonsai27:latest`, keep the image entrypoint, and configure the
following runtime settings in the container creation dialog or equivalent CLI.
The download behavior below requires an image built with the model-cache
feature; older published images require both GGUF files to exist already.

## Required runtime settings

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

In **Environment variables**, use the shared configuration reference below. Configure
ports, volumes, and GPU devices separately. If the creation dialog cannot
express GPU access or the localhost binding, use the CLI command with the
Desktop application's engine selected, then manage the resulting container in
Desktop. These Desktop configurations have not been runtime-tested here;
direct Podman has been tested inside WSL2 and on native Linux with NVIDIA CDI.

## Podman Desktop: configure the GPU entirely in the UI

The simplest GPU setup is a single CDI device selector in **Advanced → Devices**;
NVIDIA Container Toolkit/CDI supplies the driver mounts automatically. The
selected engine must support CDI selectors in its Docker-compatible API. This
was verified in released source for **Podman 6.0.0 and 6.1.1**. Update the actual
engine inside the Podman machine, not only the Windows client or Desktop app,
when the device form fails with `stat nvidia.com/gpu=all`. The CDI form below
then needs no manual WSL driver/device mounts, provided the engine's NVIDIA
Toolkit/CDI setup is already working. Upgrading does not itself install or
configure that setup. Check the version of the selected engine when diagnosing device-form errors.

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

## Desktop command fields do not configure GPU devices

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

## Hyper-V: GPU passthrough is a VM prerequisite

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

## Shared configuration

Use the [configuration reference](../README.md#configuration) for container
variables, supported GPUs, defaults, and the distinction between host and
container settings. GPU devices, port publication, and volumes must be
configured through the engine, not environment variables or Command fields.

## Startup stages and diagnostics

The container logs timestamped messages with component, stage, and severity:

```text
[2026-09-30T17:30:00Z] [startup] [gpu-access] [INFO] Checking CUDA device 0...
[2026-09-30T17:30:00Z] [startup] [gpu-access] [ERROR] CUDA driver/GPU access is unavailable...
```

Startup follows this order:

1. **configuration** — validate context, reasoning, backend, and download limits.
2. **model-cache** — report reusable files and check write access for missing files.
3. **gpu-access** — report requested backend, visible GPU/WSL paths, check CUDA,
   and validate the selected bundle against the actual GPU.
4. **runtime-dependencies** — check the server executable and shared libraries.
5. **models** — reuse cached models or download missing pinned artifacts with
   locking, resumability, and checksum verification.
6. **server** — print inference settings and replace the entrypoint with llama-server.

The API becomes ready only when `/health` returns HTTP 200. View the container's
**Logs** tab in Desktop to find the last stage and its error. Host preparation,
build, release, download, start, and push scripts use the same log format;
failed commands identify the stage and exit status without printing secrets.

`BONSAI_GPU_BACKEND=blackwell` or `ampere-ada` selects a backend, and does not
supply `libcuda.so.1` or expose a GPU. It is checked against the actual device.
Startup deliberately fails before downloading several gigabytes when CUDA
access is missing. Earlier builds that downloaded first could still fail when
loading the server; download progress did not establish a working GPU setup.
Use `download_models.sh` to prepare models independently of container GPU access.

The updated image passed fresh WSL2 API, 16k/8k, vision, coding, and failure-path
checks, including a working explicit `blackwell` override. The measured build
was a development image; see [RECHERCHE.md](../RECHERCHE.md) for its exact identity
and evidence. This does not validate GPU injection on another Desktop machine.

## CUDA driver access errors

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

## Docker Desktop: direct start

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

## Podman Desktop: direct start with CDI

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
