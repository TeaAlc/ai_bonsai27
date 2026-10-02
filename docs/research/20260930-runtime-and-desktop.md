# 20260930 Runtime And Desktop

[Current research index](../../RECHERCHE.md) · [Current operation](../../README.md)

## Local image versioning added on 30 September 2026

Image builds now calculate their project version through the pinned [greatliontech/semrel 0.7.0](https://github.com/greatliontech/semrel/releases/tag/0.7.0) binary, installed and cached under `tools/`. This project version is separate from the fixed Bonsai CUDA backend commits. `image_build.sh` labels the image with its version and source revision, tags it as `localhost/bonsai2-27b:<version>`, and updates the local `latest` alias after success. `run.sh` defaults to that alias and accepts `BONSAI_IMAGE` for a specific tag.

The version wrapper supports annotated and lightweight stable tags by dereferencing tag objects in a temporary local snapshot before invoking semrel. Versioning tests confirmed initial version `1.0.0`, patch/minor/major changes, no bump for docs-only changes, rejection of shallow history, and exclusion of tags on unrelated branches. Version calculation and image building create no Git release tags and perform no remote publication. See [tools/README.md](../../tools/README.md) for the policy and checksummed artifacts.

## Model-cache startup validation (2026-09-30)

The image was rebuilt with curl, CA certificates, util-linux, and the shared
model download helper. Container startup using the existing host GGUF cache
passed; a small container-local fixture exercised actual curl transfer, SHA256
verification, atomic publication, and offline reuse. Host fixtures verified
checksum failure, concurrent download locking, and caller-relative directories.
The large models were reused, rather than downloaded again during this check.
Fresh API checks passed: the 1080p unicorn scene was described correctly, the
16k context test processed 15,009 prompt tokens at 666.3 tokens/s, and all three
coding tasks passed their assertions at 58.6–62.5 decoded tokens/s. These are
measurements from the same WSL2 notebook; other hosts remain untested.

## Automatic container backend selection (2026-09-30)

The entrypoint now selects a backend from GPU 0's compute capability when
BONSAI_GPU_BACKEND is unset or empty. The image no longer sets a fixed backend
default. Fixture checks cover sm86, sm89, sm120, explicit overrides, unsupported
capabilities, and query failures. A rebuilt image was started directly through
Podman on the test WSL2 notebook without any backend environment variable:
startup reported `Selected GPU backend: blackwell` and `/health` returned OK.
Ampere/Ada and Desktop runtimes remain fixture-tested or documented only.

## CUDA detection without nvidia-smi (2026-09-30)

Detection now queries libcuda.so.1 directly before falling back to nvidia-smi.
The small C probe uses cuInit, cuDeviceGet, and cuDeviceGetAttribute with the
public compute-capability attribute IDs 75/76, following
[NVIDIA's Driver API guidance](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/compute-capabilities.html).
It is compiled in an Ubuntu build stage; the compiler is absent from the final
image. Fake-driver tests cover capability lookup and initialization failure.
On the actual WSL2 notebook, the probe reported 12.0 with PATH set to a directory
containing no nvidia-smi. GPU driver libraries and passthrough remain required.
The direct-start test container selected blackwell without a backend override,
returned OK from /health, and answered the API arithmetic check with 42.

## Runtime dependency and CUDA preflight audit (2026-09-30)

Both CUDA bundles were checked with ldd on llama-server and every packaged
shared library. With the WSL host driver mounted, all dependencies resolved.
The image explicitly installs bash, coreutils, curl, CA certificates, util-linux,
libc-bin, libstdc++6, and libgcc-s1. Build-time checks allow only libcuda.so.1 to
be absent; runtime checks allow none. The NVIDIA runtime capability request is
compute,utility. Driver search paths include the WSL directory and conventional
/usr/local/nvidia/lib and lib64 directories. The real CUDA probe runs before
model downloads even with an explicit backend override. A no-GPU test failed
with a clear message and left its empty model mount untouched. A GPU-enabled
test returned OK from /health and answered the arithmetic API check with 42.
Docker/Desktop driver injection itself remains untested on this notebook.

## Podman Hyper-V GPU feasibility (2026-09-30)

### Findings and primary sources

- [Podman Desktop GPU access](https://podman-desktop.io/docs/podman/gpu):
  Windows NVIDIA GPU support requires WSL2; the documented prerequisites
  explicitly exclude Hyper-V. Installing NVIDIA Container Toolkit in a VM
  does not itself assign a physical GPU to that VM.
- [Microsoft Hyper-V GPU troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/windows-server/virtualization/troubleshoot-hyper-v-gpu-assignment-partitioning-passthrough-issues):
  supported DDA deployments require Windows Server 2016 or later; GPU-P
  deployments require Windows Server 2025 or later. Microsoft excludes
  desktop-class hardware and Windows 10/11 client hosts from supported
  DDA/GPU-P deployments. GPU-P has specific supported GPU, driver, guest,
  and licensing requirements. WSL2's GPU virtualization is a separate path.
- [Microsoft GPU acceleration planning](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/plan/plan-for-gpu-acceleration-in-windows-server):
  DDA can give Linux guests GPU acceleration subject to support; both
  assignment methods can expose CUDA where the vendor configuration supports it.
- [NVIDIA GPU passthrough guide](https://docs.nvidia.com/vgpu/latest/grid-vgpu-user-guide/using-gpu-pass-through.html):
  Hyper-V passthrough is documented through DDA on supported Windows Server
  versions. Hardware and guest-driver compatibility must be established
  outside the application container.

### Image implications and supported boundary

The regular Podman Desktop Hyper-V provider cannot be claimed as a supported
CUDA deployment from these sources. A separately GPU-provisioned Hyper-V
Linux guest can use this Linux image through NVIDIA CDI, conditional on its
CUDA probe and full dependency checks passing. This is an architectural
inference, not a measured Hyper-V test. No Hyper-V environment is available
in this session; the only live GPU checks were on WSL2.

The image's CUDA runtime/cuBLAS, llama/ggml/OpenMP, C/C++ libraries, HTTPS
download tools, and CUDA probe are already present and audited. A Hyper-V
Linux guest additionally needs a compatible GPU assignment, a working Linux
NVIDIA guest driver, and NVIDIA Container Toolkit/CDI in the guest OS. These
are VM/kernel/runtime prerequisites, not files to install in this image.
A bundled host driver or CUDA stub would not create GPU access. The WSL
libcuda projection and /dev/dxg mounts do not apply to an ordinary Hyper-V VM.

README now includes guest-level nvidia-smi/CDI checks and container-level
shared-library and CUDA-probe checks. Existing pre-download CUDA validation
prevents downloading models into a guest without usable GPU compute access.
No unsupported VM modifications, driver installation, or CPU offloading were
introduced. For Windows client notebooks, the documented working alternatives
remain WSL2-backed Podman or a remote GPU-enabled Linux engine.

## Model-mount flock failure (2026-09-30)

The user reported `flock: 9: Function not implemented` while starting the
Ampere/Ada backend on an RTX 4070 Ti Super system. File descriptor 9 came from
our shared model-download lock, not GPU initialization. ENOSYS indicates that
the lock operation is unavailable; the exact filesystem on that host has not
been inspected. Shared/virtual filesystems are a plausible cause.

[Linux flock documentation](https://man7.org/linux/man-pages/man2/flock.2.html)
describes filesystem-dependent locking behavior. A
[Hugging Face upstream report](https://github.com/huggingface/huggingface_hub/issues/2399)
records the same ENOSYS failure when downloading to storage without flock
support. The downloader now serializes using atomic directory creation,
relying on mkdir's existing-directory exclusion instead of a flock syscall.
See [mkdir documentation](https://man7.org/linux/man-pages/man2/mkdir.2.html).

The directory lock is shared by containers mounting the same cache; putting
a lock only in each container's /tmp would not provide that protection.
Normal exit and handled signals remove the owned lock. Waiters time out after
600 seconds; crashed-owner locks must be removed after downloads are stopped.
Cross-container PIDs are not used to guess stale ownership. Interrupted .part
files remain resumable, and SHA256 verification precedes atomic publication.
Regression fixtures deliberately make flock fail with ENOSYS and check
download success, concurrent serialization, waiting, and lock cleanup.
The user's actual Windows/shared filesystem is not available for live tests.
The regression fixtures passed on the host and inside the rebuilt image;
a WSL2 GPU container also passed /health and the arithmetic API check (42).

## Follow-up repository audit (2026-09-30)

[September 30 audit](../../docs/history/repository-audit-20260930.md) records the audit of source revision
`845d89edac88094f65009d874b243d20024cf7ac`, including reproduced edge cases and
prioritized acceptance criteria. Both pinned backend archives and extracted
checksum manifests passed verification. The existing clean 1.3.1 image passed
both backend dependency checks with the WSL driver mounted and rejected startup
without GPU access before downloading models. Eight script regression suites
and tracked Bash/Python syntax checks also passed.

Additional isolated fixtures exposed a lock-release race, conflicting bare and
v-prefixed release tags in the older tag helper, and context integer overflow.
Existing nonempty model files were confirmed to bypass checksum verification,
as currently documented. Registry publication safeguards, GPU selection
consistency, preparation concurrency, and QA evidence provenance need further
work described in the plan. This audit did not repeat inference, vision,
throughput, or coding generation tests; earlier measurements above remain
historical and do not validate another host or GPU backend.


## Hardening implementation and validation (2026-09-30)

The follow-up audit's implementation is tracked in the
[archived September 30 audit](../../docs/history/repository-audit-20260930.md).
Release/build/preparation/push operations now share a checkout-local lock;
committed sources and verified backend trees are snapshotted before building.
A successful build atomically records its exact image ID, source, semrel version,
cleanliness, pinned inputs, Containerfile/base digest, and apt package inventory.
The initial push policy required matching release tags and rejected dirty builds,
remote conflicts, and rollback. That policy was superseded by the user's request
that every successful build must be pushable; see the follow-up below. The current
workflow selects the receipt's exact image across Podman/Docker stores and updates
both registry aliases. Live publication is separate.
The manifest promotion follows the
[Distribution HTTP API V2](https://distribution.github.io/distribution/spec/api/)
manifest PUT operation. Config and child-manifest digests are validated before
using remote labels. Isolated tests cover both engines, stale Docker storage,
credential cleanup and exact manifest promotion. The follow-up fixtures replace
the original conflict/rollback rejection tests with successful overwrite cases.

GPU generation is selected inside the container using CUDA device 0; an override
must match it. Configuration checks reject context overflow and accept 512–262144
(the upper bound documented in the
[official model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)).
The GPU-only allocation policy is unchanged. Shared-cache downloads retry the
lock-release race, supervise children and stop signals, preserve resumable
partials, and support explicit host verification/repair of pinned caches.
Preparation reuses verified archives offline and replaces only complete checked
runtime trees. A real Podman stop during an injected slow transfer exited 143,
removed its directory lock, and retained the partial file. A read-only cache
failed before transfer; generated-code early exit and timeout were rejected by
the separate restricted-container harness. All offline regression suites passed.

The base is pinned to Ubuntu 24.04 digest
`sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3`.
Apt package versions remain resolved at build time and inventoried; this is not
a claim of deterministic builds. The Blackwell bundle recommends driver 570+.
[CUDA 12.8 release notes](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html)
list toolkit drivers 570.26 (Linux) / 570.65 (Windows), while
[CUDA 12.4 release notes](https://docs.nvidia.com/cuda/archive/12.4.0/cuda-toolkit-release-notes/index.html)
list 550.54.14 / 551.61. The broader CUDA 12.x minor-compatibility floor is not
proof of Blackwell compatibility: NVIDIA documents
[feature/PTX restrictions](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html).
The measured host reports RTX 5070 Ti Laptop, compute capability 12.0, driver
617.14. Driver matrices on other actual GPUs remain pending.

### Fresh development-image API evidence

The cold-cache container downloaded both pinned artifacts into
`results/validation-model-cache/`; subsequent runs reused them. The passing
identified suite is `results/runs/20260930T152810Z-495703/`, image ID
`ce3dda017fddc4c8e421bb698873c060aa1da4038bee96bdcfb4283975c591e2`, marked
**dirty during development**. It passed 18/18 QA checks: GPU-only language-model
buffers, both main/draft Flash Attention and q8 caches, MTP n_max=2, CPU BF16
vision, exact pinned model hashes, 16k context and 15,009-token prompt recall,
related 8k /props, vision fixtures, and all 23 coding assertions. The included
1920x1080 unicorn image was sent through the API and described correctly.
Generation tests ran on host port 18080. A separate warm-cache container with `--network none` started at 8k and answered the arithmetic OpenAI API request correctly, without any model transfer. API timings expose actual MTP draft and
acceptance counters, beyond merely showing its startup configuration.

| Measurement | Fresh development run |
| --- | --- |
| Long prompt processing | 696.1 tokens/s for 15,009 prompt tokens |
| Prime generation | 61.4 tokens/s; 68 of 72 draft tokens accepted |
| Interval generation | 68.6 tokens/s; 76 of 88 draft tokens accepted |
| Bracket generation | 59.4 tokens/s; 66 of 78 draft tokens accepted |

These measurements are individual observations, not portable performance
promises. The final clean build and subsequent suite are separately identified
in local receipts/results. Native Linux/CDI, real Ampere/Ada inference, the
reported Windows shared mount, Docker Desktop GPU execution, a provisioned
Hyper-V guest, and live publication/anonymous pull remain explicit pending rows.


### Final clean release verification

The online `create_realease.sh` workflow reconciled public release history,
created local `v1.4.0`, and called `image_build.sh` successfully for both version/latest
tags. The release image is
`f39b06302ab6b70df04157cc8729a121eb4adf31f0dec52af31701b376f81c6b`, source
`de4b8edccb4940c9d005f89a77ae199fa142c5a8`, `io.bonsai.git.dirty=false`.
Its receipt inventories 109 installed package rows and the pinned inputs.
`results/runs/20260930T154315Z-510298/` passed 18/18 QA checks, both vision shapes,
the full-size unicorn image, 23 coding assertions, the 16k long-context request,
and a related 8k /props request. Coding generation measured 67.0, 66.9, and 64.6
tokens/s; the 15,009-token prompt measured 703.9 prompt tokens/s. Actual MTP draft
counters again recorded 68/72, 76/88, and 66/78 accepted/drafted coding tokens.
Both bundled dependency checks, real PID 1 cancellation and read-only-cache
checks, coding harness early-exit/timeout checks, and warm-cache offline API
startup passed on this clean image. Test containers were removed afterward.

No new image or Git tag was published remotely. A read-only anonymous metadata
check found the existing public latest release at 1.2.1, source
`ceb9aa25a94a834f213c85777d84e94371a836d2`; this is separate from the local 1.4.0
build. Live publication/pull validation and the unavailable hardware rows remain
pending. Later documentation commits retain the release image's actual source
revision and do not manufacture another semrel version.


## Publishable rebuilds (2026-09-30 follow-up)

A standalone build at documentation commit
`e18216113fd9bc394ec9579c358ad6cebb40cac3` correctly retained version `1.4.0`
while the Git release tag still identified
`de4b8edccb4940c9d005f89a77ae199fa142c5a8`. The recorded image ID was
`sha256:9b032691b79578c938796713c71d48bac87bc56690e5a879a47c7e5c712c3094`.
The former tag correspondence check incorrectly blocked publication of this build.

The revised policy permits every successful project build, including dirty builds
and builds without matching release tags. Pushing always replaces the version
tag and `latest`; Git release refs remain unchanged. Receipt/image label checks,
exact Podman-to-Docker transfer, post-push image identity verification, exact
manifest promotion, and private temporary credentials remain in place. Isolated
engine and registry fixtures validate these paths, including documentation
rebuilds, dirty builds, absent tags, and replacement of older or newer `latest`.
These fixture results do not establish a fresh live GHCR publication. Runtime
settings are unchanged, so previous GPU/API measurements remain historical.


## Desktop GPU option placement (2026-09-30 follow-up)

The supplied inspect for container `7634af6d4207` (image version `1.4.1`) records
`Config.Cmd` and process arguments as `["--device", "nvidia.com/gpu=all"]`. Its
only bind mount is the model cache; CUDA reports that `libcuda.so.1` cannot be
loaded. This shows that the GPU flag was supplied as an application argument
instead of an engine creation option. It does not prove that the engine has a
working GPU/CDI setup; that must still be checked independently.

[Podman's official run syntax](https://docs.podman.io/en/latest/markdown/podman-run.1.html)
places engine options before the image and container arguments after it.
[Podman Desktop's official GPU instructions](https://podman-desktop.io/docs/podman/gpu)
configure NVIDIA Container Toolkit/CDI in the Podman machine and pass
`--device nvidia.com/gpu=all` to `podman run`. On Windows the documented route
requires WSL2 and excludes Hyper-V. The README now distinguishes Desktop command
fields from device configuration and provides a CLI recreation example.
This is documentation validation against supplied inspect evidence and official
references, not a new runtime test on the reported remote machine.


## Podman Desktop device form verification (2026-09-30 follow-up)

The previous suggestion that CLI creation was necessary was incomplete. The
[upstream RunImage form](https://github.com/podman-desktop/podman-desktop/blob/main/packages/renderer/src/lib/image/RunImage.svelte)
has **Advanced → Devices** with Host Device, Container Device, and Read/Write/Mknod
fields. It sends `PathOnHost`, `PathInContainer` (defaulting to the host value),
and `CgroupPermissions` in `HostConfig.Devices`.

[Podman's API mapping helper](https://github.com/containers/podman/blob/main/pkg/api/handlers/utils/docker_device.go)
recognizes qualified CDI names and returns the selector alone when the container
path is empty or equal to the host selector. Thus the UI recipe is Host Device
`nvidia.com/gpu=all`, Container Device empty, and Read/Write/Mknod enabled. Basic
Command remains empty. The README now gives these field-level instructions.
This verifies the upstream source path, not runtime compatibility of an unknown
installed Desktop/engine version or GPU availability in the user's machine.
NVIDIA Container Toolkit/CDI and a supported GPU-enabled engine remain required.


## CDI API failure and WSL device mapping (2026-09-30 follow-up)

The user's subsequent HTTP 500 `stat nvidia.com/gpu=all` shows that their
container-create path treats the CDI selector as a filesystem device. The
previous main-branch source check did not establish support in their installed
engine. Upstream commit
[`f374f2c95bc8c7642a5a47d03298fe036f0f77c0`](https://github.com/containers/podman/commit/f374f2c95bc8c7642a5a47d03298fe036f0f77c0),
authored 2026-04-13, replaces unconditional colon-separated DeviceMapping
conversion with the CDI-aware helper. The symptom is consistent with that
conversion issue; the remote engine version and presence of the fix are unknown.

For WSL2, the GUI can send `/dev/dxg` as both host and container device with
`rwm` permissions and bind `/usr/lib/wsl` read-only at the same path. This uses
real filesystem paths rather than CDI names. The upstream form concatenates
source and target with a colon, so target `/usr/lib/wsl:ro` supplies the
read-only bind option when no separate toggle exists. A fresh local check sent these
settings through a temporary Docker-compatible Podman API service at
`/v1.41/containers/create`, then ran the actual image's `select_gpu_backend`.
With image
`sha256:0ce2f85384dd6e061c88f00bb9d018f371205faa404971610e4e186398cad3fb`,
the detection exited 0 and returned `blackwell` on this WSL2 host.
The probe container was removed afterward.

An initial standalone probe bypassed the detection wrapper and failed because
it did not set the WSL library search path; the successful check used the
image's real wrapper, which supplies that path. This validates device/library
access through the API, not a new inference benchmark or the Windows Desktop UI.
The remote engine must itself expose `/dev/dxg` and `/usr/lib/wsl`; the settings
do not provision GPU passthrough for a stock Hyper-V machine.


## Simpler Desktop GPU configuration (2026-09-30 follow-up)

Released-source checks of Podman **v6.0.0** and **v6.1.1** confirmed both the
CDI-aware `DockerDeviceMappingString` helper and its call from the Docker-compatible
container-create handler. For example, see the
[v6.0.0 helper](https://github.com/containers/podman/blob/v6.0.0/pkg/api/handlers/utils/docker_device.go)
and [v6.0.0 handler](https://github.com/containers/podman/blob/v6.0.0/pkg/api/handlers/compat/containers_create.go).
This establishes released versions containing the fix, without claiming the
first fixed release or diagnosing the unknown remote engine version conclusively.

The preferred Desktop route is therefore a fixed engine plus working NVIDIA
Toolkit/CDI: one Host Device selector `nvidia.com/gpu=all`, blank Container Device,
and an empty Basic Command. CDI supplies the GPU device and driver-library mounts.
Manual `/dev/dxg` and WSL driver mounts are a fallback, not an intrinsic application
requirement. Updating the Windows client alone does not update the Linux service
inside an existing Podman machine, nor does an engine upgrade configure CDI.
No new Desktop runtime test was performed for this source verification.


## Startup stages and failure diagnostics (2026-09-30 follow-up)

The supplied machine diagnostics establish that both Windows client and server
are Podman 6.0.2, the machine is WSL2, and its projected `nvidia-smi` sees the
GPU. `nvidia-ctk` is not available through its shell. This supersedes the earlier
suggestion that upgrading an old server would necessarily fix this machine.
The user's exact Desktop create-path failure is not reproduced here; usable
CUDA inside the application container still requires GPU/driver injection.

Container startup now validates settings, checks cache paths and write access
for missing models, checks actual CUDA access/backend selection, checks selected
server dependencies, prepares pinned models, then starts llama-server. An
explicit backend remains subject to actual GPU validation. The incorrect
suggestion that setting BONSAI_GPU_BACKEND repairs missing CUDA was removed.
Missing CUDA deliberately stops before model transfers; downloading first would
not make GPU inference possible. Host prefetch remains available independently.

The shared logger emits UTC timestamps, component, stage, and severity to stderr.
Host preparation/build/release/run/download/push scripts use the same format.
Unexpected command failures include exit status and line without logging command
text or credentials. Model logs identify reuse, lock acquisition, transfer,
checksum verification, and readiness. A first build caught the new logger being
excluded by the build-context allowlist; adding the explicit exception fixed it.

Validation: the complete offline regression runner passed. Rebuilt development
image `sha256:2c86832ab20c948a17ec152fe817a662157b3979e081d41c3663278bf84d1a28`
(version 1.4.1, dirty label true) passed real missing-CUDA checks for auto,
blackwell, and ampere-ada, pre-GPU invalid configuration/read-only-cache checks,
both backend dependency checks, download stop/lock cleanup, and retained partial
checks. Fresh API evidence at `results/runs/20260930T173438Z-564966/` passed all
18 QA checks: 16k long-context, 8k configuration, GPU-only language inference,
CPU BF16 vision, Flash Attention, q8 main/draft cache, active MTP, both vision
fixtures, unicorn image request, and three coding tasks. These are measurements
on this WSL2 host; Desktop/CDI on the remote machine remains untested. A separate
16k start with explicit `BONSAI_GPU_BACKEND=blackwell` also passed an actual
OpenAI API request (answer `42`); its local evidence is
`results/startup-override.log` and `results/startup-override-response.json`.
No GHCR publication was performed.

### Confirmed remote image selection (2026-10-01)

`run.sh` now checks Podman image availability before GPU routing. A missing
selected local image prompts for a remote reference, defaulting to
`ghcr.io/teaalc/ai_bonsai27:latest`; Enter confirms it and another answer replaces
it. Engine errors, EOF, invalid input, and failed pulls stop startup. Container
creation uses `--pull=never` to prevent an additional implicit pull.

Validation: `tests/test-run-image.sh` exercises cached images, both prompt
answers, forwarded arguments, and failure cases using a mock engine. The full
offline regression suite passed. An actual WSL2 GPU container started through
`run.sh` with the existing local image, a 16,384-token context, and closed stdin;
its OpenAI-compatible API correctly answered 19 + 23 with 42. The owned test
container was removed. Logs are saved locally in
`/tmp/bonsai27/run-image-regressions.log` and `/tmp/bonsai27/run-image-api.log`.
The remote download branches were fixture-tested; no fresh registry download
or publication was performed. These changes affect the host launcher only;
the existing image was reused without rebuilding the container runtime.

### Text conversation benchmark (2026-10-01)

Added `simple_text_benchmark.sh`. It sends ten sequential
OpenAI-compatible chat requests, giving twenty user/assistant messages, and
retains the complete history. Neutral planning notes are budgeted using the
pinned server's template/tokenizer endpoints. The endpoint contract was checked
against the [pinned backend server documentation](https://github.com/sudoingX/llama.cpp/blob/ff414120c343e6e6cb868013c99f1dde52b27e70/tools/server/README.md).
The target is 16,000 cumulative chat API usage tokens, including repeatedly
submitted history; template/tokenizer calls are not added to that usage total.
Thinking is disabled, prompt caching enabled, and answers limited to 128 tokens.

Fresh runtime validation used the existing local image on the RTX 5070 Ti Laptop
GPU, context 16,384, and an owned container on port 18083, removed after the run:

- Twenty messages completed, with 15,126 input and 823 output tokens: 15,949 total.
- Wall time including budgeting requests: 33.091 seconds.
- Generation throughput from summed server decode timing: 39.81 tokens/s.
- Output throughput over wall time: 24.87 tokens/s.
- Last request input: 2,654 tokens. This benchmark does not fill a 16k context.

Local evidence: `results/text-benchmark/validation-20261001.json` contains the
transcript, API usage and per-request timings; console output is retained in
`/tmp/bonsai27/text-benchmark-api.log`. This standalone benchmark report is not
an identified QA-suite audit. The container runtime was reused without a rebuild.
Five HTTP-fixture tests cover history, token budgeting, endpoint overrides,
context rejection, invalid hosts, and failed inference with a partial report.

### Explicit prompt-cache metrics (2026-10-01)

The text benchmark now reports reused and newly processed prompt tokens and a
cache hit rate per exchange and in its summary. The pinned server documentation
above defines `timings.cache_n` as reused input tokens; the benchmark uses that
counter and falls back to `usage.prompt_tokens_details.cached_tokens` when it
is absent. The total rate is `100 * sum(cached tokens) / sum(prompt tokens)`,
including the first request and excluding generated tokens. Missing/invalid
counters remain unknown (`null`); incomplete coverage suppresses aggregate
cache totals and rates. The counter source and number of measured exchanges
are recorded explicitly.

A new real API run through all twenty messages produced:

- Input tokens: 15,126; output tokens: 823; combined: 15,949.
- Cached prompt tokens: 13,215; newly processed prompt tokens: 1,911.
- Token-weighted cache hit rate: 87.37%; valid counters in all ten exchanges.
- Wall time: 34.464 seconds; decoding: 38.81 tokens/s; output over wall time:
  23.88 tokens/s.

Evidence is in `results/text-benchmark/validation-cache-20261001.json` and
`/tmp/bonsai27/text-benchmark-cache-api.log`. This fresh measurement used the
existing local image, RTX 5070 Ti Laptop GPU, and 16,384-token context; the owned
container was removed. It supplements, rather than edits, the earlier recorded
benchmark. Eight HTTP-fixture tests cover weighted aggregation, real zero hits,
fallback counters, missing/partial/invalid counters, and the previous benchmark
behaviors. Cache totals were also checked against the fresh API timing records.
