# Research and implementation: Bonsai 2 27B

Research conducted on 28–29 September 2026; local validation updated on 30 September 2026. Published benchmark numbers below are reported by model or fork authors unless identified as measurements from this notebook.

Host diagnosis on 1 October 2026: native Linux Mint 22.3 with an RTX 4070 Ti
SUPER and NVIDIA driver 595.91.07 passed host `nvidia-smi`. Starting the existing
`bonsai2-27b` Podman container failed before application startup with
`unresolvable CDI devices nvidia.com/gpu=all`; the host lacked `nvidia-ctk`,
NVIDIA Container Toolkit packages, and CDI specifications. The new
`install_nvidia_container_toolkit.sh --check` reproduced the missing-toolkit
diagnosis without changing the host. Installation and native Linux container
inference have not been validated. The installer follows
[NVIDIA's CDI guidance](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html),
including the base-package option for machines using CDI exclusively.

Follow-up after toolkit installation: Toolkit 1.20.1 generated CDI 0.7.0 in
`/var/run/cdi/nvidia.yaml`; Podman 4.9.3 debug logs rejected it with
`json: unknown field "additionalGids"`. NVIDIA's supported
`no-additional-gids-for-device-nodes` feature flag generated CDI 0.5.0 successfully
in `/tmp/bonsai27/`. The host specification has not been replaced and inference
has not been tested. The installer now offers `--repair-cdi` and persists that
flag for Podman 4 refreshes. Existing APT sources offer only Podman 4.9.3.

## Model and versions

[PrismML's Bonsai 2 GGUF model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) identifies **Qwen3.8-27B** as the base model. Its GGUF architecture identifier remains `qwen35`; that identifier does not mean the wrong generation was selected. The architecture combines transformer attention with linear/recurrent layers. Model metadata advertises up to 262,144 tokens; this project defaults to 16,384.

The official PTQ1_0 and PQ2_0 variants differ in weight packing and kernel path. Weight packing and KV-cache quantization are independent: the requested `q_8` cache maps to llama.cpp's **`q8_0`** type here. Earlier Bonsai/Ternary-Bonsai 27B releases are different model generations. MLX packages target Apple Silicon.

The official model card warns that its PTQ1_0/PQ2_0 files need Bonsai-specific runtime support. A seemingly loadable generic Q2_0 file can produce incorrect output without the required transformations. Generic generated installation hints on Hugging Face do not supersede that warning.

## MTP variants considered

MTP requires actual `nextn` weights in the GGUF. A server flag alone cannot add a missing head. In this setup `n=2` means `--spec-draft-n-max 2`: the draft head may propose up to two tokens before verification by the main model. It does not mean two additional trained heads.

| Variant | Relevant property | Assessment |
| --- | --- | --- |
| [sudoingx PTQ1_0 MTP](https://huggingface.co/sudoingx/Ternary-Bonsai-2-27B-PTQ1_0-MTP-GGUF) | Restored Qwen3.8 MTP head; fat and lean files | **Lean selected** for the 12 GB GPU; requires the backend Hadamard fix |
| [ProCreations MTP](https://huggingface.co/ProCreations/Ternary-Bonsai-2-27B-MTP) | PQ2_0 body with a further-trained Bonsai-adapted head | Larger body; published n=2 measurements are on other hardware |
| [decent-jawfish](https://huggingface.co/decent-jawfish/bonsai-2-27b-mtp) | PQ2_0 MTP graft mentioned by sudoingx | No independent performance claim adopted |
| [BoldingBuilds](https://huggingface.co/BoldingBuilds/Ternary-Bonsai-2-27B-Abliterated-PQ2_0-MTP-GGUF) | Abliterated PQ2_0 MTP derivative | Changes model behavior; not selected |
| [matrixoar](https://huggingface.co/matrixoar/Bonsai-2-27B-PTQ1_0-MTP-Uncensored-Ready-GGUF) | PTQ1_0 with ProCreations Q8_0 head; optional separate LoRA | Alternative with documented n=2 benchmarks; LoRA is not part of this deployment |
| [signalnine q27](https://huggingface.co/signalnine/Bonsai-2-27B-q27) | Different q27 format with MTP variants | Not a drop-in GGUF/llama-server model |

matrixoar reports 91.178 generated tokens/s on a short prompt and 69.140 tokens/s after 17,531 prompt tokens on an RTX 4070 SUPER. These are external measurements, not predictions for this laptop.

## Server fork and reasoning settings

[PrismML-Eng/llama.cpp](https://github.com/PrismML-Eng/llama.cpp) is the Bonsai-specific reference. [sudoingX/bonsai2-small-gpu](https://github.com/sudoingX/bonsai2-small-gpu) documents its optimized [bonsai2 branch](https://github.com/sudoingX/llama.cpp/tree/bonsai2), including a PTQ1_0 matvec kernel, the Hadamard correction, and RTX-50 fixes for programmatic dependent launch and Flash Attention. The selected prebuilt binary is pinned to commit `ff414120c343e6e6cb868013c99f1dde52b27e70`; the container does not compile llama.cpp from source.

Published RTX 3060 tests compare 26.32 and 40.47 tokens/s without MTP. The same source reports 50.1 tokens/s at n=1 and 45.4 at n=2; n=2 can lose to no MTP on long contexts. Consequently, this project uses the requested n=2 without claiming it is always optimal. Stock llama.cpp and generic CUDA/MTP forks without demonstrated PTQ1_0 and Hadamard support were not selected.

The [official Bonsai 2 model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) and [known-issues page](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/main/KNOWN_ISSUES.md) say its chat template accepts `low`, `medium`, and `xhigh` reasoning effort. `xhigh` is the model default; `medium` is recommended for shorter reasoning. `low` is syntactically accepted but does not reliably shorten reasoning and may behave near `xhigh`; `high` causes HTTP 500. `run.sh` therefore validates the three accepted values and defaults to `medium`, preserving the previously tested server behavior. Clients may also set `reasoning_effort` per request; the scripts' short-answer tests disable thinking through the request template parameters.

## Pinned artifacts and data layout

| Artifact | Revision or SHA256 |
| --- | --- |
| sudoingx model repository revision | `f04a3bd22b7b482675663e99efaba6719347b419` |
| `Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf` | `1e33c571a5ce7a9a3e42474d66192923d5a6d77da7fb3a22986dc809522b5685` |
| CUDA 12.8 sm120 bundle, `ff41412` | `74e1cf451d41e1435d15ef93e76007219cdf28fd1eb59bf335d1f3d31bfbc4da` |
| CUDA 12.4 sm86/sm89 bundle, `285542d` | `46b0bc960f00352267ed34246b7cb5010fa64618077158647e5d2bbcf0fb60fe` |
| Official vision repository revision | `b072e1d3b35a0a630cece372c2127528e0994386` |
| `Ternary-Bonsai-2-27B-mmproj-BF16.gguf` | `e287342d92332fa3577ed1d42e921dac9370c08da58ba9337fa450f6cc76cfd7` |

`prepare.sh` downloads and verifies these files. CUDA archives and extracted libraries reside under `data/backends/blackwell/` and `data/backends/ampere-ada/`; retained source/metadata are under `data/research/`. `image_build.sh` rechecks internal backend checksums and creates the image. GGUF files stay in `BONSAI_MODEL_DIR` on the host (default: the caller’s current directory) and are mounted read/write at `/models` by `run.sh`. The container downloads missing files using the shared pins in `data/models/download.sh`; `download_models.sh` provides the same download on the host. Downloads are locked, resumable, and SHA256-verified before atomic publication; existing nonempty readable files are reused without re-verification. License files for the prebuilt backends are copied into the image under `/opt/bonsai/<backend>/LICENSES/`.

## GPU placement and platform behavior

Validation host: Ubuntu 26.04 in WSL2, rootless Podman 5.7.0, 16 GB RAM, NVIDIA RTX 5070 Ti Laptop GPU with 12,227 MiB VRAM. The Windows driver was 617.14. Under WSL2, `/dev/dxg` and `/usr/lib/wsl` expose the Windows driver to the container, consistent with [NVIDIA's WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html). Native Linux uses a preconfigured NVIDIA CDI device. Native Linux and the sm86/sm89 bundle are packaged but not runtime-tested here.

`--override-tensor .*=CUDA0` forces all language-model tensors, including input embeddings, onto CUDA0. `--n-gpu-layers all`, `--fit off`, and `--cache-ram 0` prevent silent model or prompt-cache fallback. Before the override, approximately 265 MiB of embeddings remained in a CPU mapping. Afterward, the log reported **66/66 GPU layers**, a CUDA0 model buffer of **5,995.31 MiB**, and CUDA0 main/MTP KV buffers of approximately **544/34 MiB**. The recurrent state also resides on CUDA. CPU control and output buffers are not offloaded model weights.

Vision uses the official **BF16** mmproj (931,145,856 bytes) with `--no-mmproj-offload`. The log reports `CLIP using CPU backend` and a roughly 248 MiB CPU compute buffer. This saves VRAM versus GPU-side vision but costs CPU time and RAM; the resulting image embeddings still enter the CUDA language model. Vision does not imply zero additional GPU work or memory.

## Validation and observed speed

The final WSL2/sm120 run used a 16,384-token context, MTP n_max=2, Flash Attention, and q8_0 K/V for both main and draft contexts. `tests/test-api.py` confirmed the model list, a chat calculation, and retrieval of a marker after **15,009 prompt tokens**. The long request took **24.17 s** overall, with **629.0 prompt tokens/s** prefill. Its 13-token response is too short for a useful decode benchmark. A separate 8,192-token container start was verified through `/props`.

| API coding task | Executed assertions | Result | Generated tokens/s after vision integration |
| --- | ---: | --- | ---: |
| Prime test | 10 | Passed | 60.5 |
| Merge intervals | 6 | Passed | 57.8 |
| Balanced brackets | 7 | Passed | 54.8 |

Generated code was executed in separate Python containers without networking, with a read-only filesystem and resource limits. All **23 assertions** passed. `tests/test-vision.py` sent two PNG fixtures through the OpenAI chat endpoint: the red square and blue circle were identified correctly, with 3.00 s and 2.90 s API wall time respectively. A later combined-shape image test correctly identified both colors, shapes, and positions. These are basic function/quality checks, not a broad vision benchmark.

The saved `tests/qa.py` audit reported **14/14 checks passed**. It reads recorded results and a saved server log, so it does not replace a fresh runtime test on another host. A GPU snapshot after vision integration showed **9,078/12,227 MiB** in use, including the desktop and other processes; it is not an isolated VRAM benchmark. Results are under the local, Git-ignored `results/` directory.

## Local image versioning added on 30 September 2026

Image builds now calculate their project version through the pinned [greatliontech/semrel 0.7.0](https://github.com/greatliontech/semrel/releases/tag/0.7.0) binary, installed and cached under `tools/`. This project version is separate from the fixed Bonsai CUDA backend commits. `image_build.sh` labels the image with its version and source revision, tags it as `localhost/bonsai2-27b:<version>`, and updates the local `latest` alias after success. `run.sh` defaults to that alias and accepts `BONSAI_IMAGE` for a specific tag.

The version wrapper supports annotated and lightweight stable tags by dereferencing tag objects in a temporary local snapshot before invoking semrel. Versioning tests confirmed initial version `1.0.0`, patch/minor/major changes, no bump for docs-only changes, rejection of shallow history, and exclusion of tags on unrelated branches. Version calculation and image building create no Git release tags and perform no remote publication. See [tools/README.md](tools/README.md) for the policy and checksummed artifacts.

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

[TODO_PLAN.md](TODO_PLAN.md) records the audit of source revision
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

The follow-up audit's implementation is tracked in [TODO_PLAN.md](TODO_PLAN.md).
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

## 2026-10-01: RTX 4070 Ti SUPER performance investigation

These are new measurements on an RTX 4070 Ti SUPER (16,376 MiB, SM89), driver
595.91.07, in a Linux Mint KVM guest with eight Ryzen 9 5950X vCPUs and about
16 GB of RAM. They do not replace the earlier WSL2 laptop measurements.
The original default GHCR image was preserved by immutable image ID
`ece87f5e0e34f91c5b77f9d333578922a6973403031a49469928f450ee5fc461`
(version 1.4.2). No registry tags or model weights were changed.

All speed trials used the unchanged `simple_text_benchmark.sh`: ten exchanges,
full history, thinking disabled, greedy generation, and approximately 16k
**cumulative** API usage tokens. The longest individual prompt is only about
2.7k tokens. This measures repeated short conversation performance, not decoding
against an already filled 16k or 128k context. First runs start with an empty
prompt cache; second runs retain it. Decode rates use API decoding timings;
wall time also includes prefill, sampling, and request overhead. Do not combine
warm/cold figures or compare output throughput directly with decode throughput.

### Versions, builds, and patches

The existing Ada bundle uses `285542d98d37d0f07f491cd206aefa31f1848f33` with CUDA
12.4; the newer sudoingX head remains `ff414120c343e6e6cb868013c99f1dde52b27e70`
and its available bundle targets SM120. It is not an Ada binary upgrade. Prism's
latest tagged release checked here, `prism-b10743-adfffbe` dated September 25,
predates several useful changes.

The tested source revision is
[`88c4bc60b9c9578f134385be9535e853f2db9b9f`](https://github.com/PrismML-Eng/llama.cpp/commit/88c4bc60b9c9578f134385be9535e853f2db9b9f).
It includes the September 29 merge of
[PR #221](https://github.com/PrismML-Eng/llama.cpp/pull/221): hybrid Ada PTQ1
kernels, native q4_0/q8_0 Flash Attention, and MTP catch-up/gather improvements.
PR #218 is still open as a standalone proposal; #215 was closed without a merge.
Their relevant work was integrated through #221, so stacking these patches again
would duplicate changes. Stock upstream llama.cpp is not a verified replacement
for this PTQ1 Bonsai image.

The optional build uses CUDA 12.8.1, native SM89 machine code, CUDA graphs and
Flash Attention, portable AVX2/FMA/F16C CPU support, and no model quantization
changes. Source archive and compiler image pins, dependency/license packaging,
and complete runtime inventories are recorded by the new preparation tool and
image receipt. Native q8_0 attention is relevant to the eventual larger context
because it avoids temporary F16 KV copies. The larger
[ada-surgery fork](https://github.com/professorpalmer/bonsai-ada-surgery) also
changes memory placement and generation behavior; its CPU-tiered caches and
reasoning changes were not adopted in this GPU-only, quality-preserving setup.

### Measured speed results

The following rows show cold/warm runs. Main and draft K/V stay q8_0, Flash
Attention stays enabled, and the LLM stays on CUDA0. BF16 vision stays on CPU.

| Variant | Decode tokens/s, cold / warm | Wall seconds, cold / warm |
| --- | ---: | ---: |
| Original image, MTP=2 | 84.03 / 84.38 | 16.134 / 15.793 |
| Original repeat, MTP=2 | 84.05 / 84.03 | 16.139 / 15.928 |
| Original MTP=1 | 80.90 / 85.30 | 18.197 / 16.299 |
| Original MTP=3 | 77.04 / 77.16 | 16.869 / 16.575 |
| Original without speculation | 69.71 / 69.72 | 18.019 / 17.705 |
| Prism source, MTP=2 | 87.30 / 87.91 | 15.904 / 15.507 |
| Prism source repeat, MTP=2 | 87.01 / 87.56 | 15.886 / 15.577 |
| Built optional image, MTP=2 | 87.43 / 87.86 | 16.041 / 15.455 |
| Prism source, MTP=1 | 88.79 / 89.53 | 16.408 / 15.805 |
| Prism source, MTP=3 | 80.63 / 80.22 | 16.395 / 15.882 |
| Prism source without speculation | 73.51 / 73.65 | 17.383 / 17.203 |
| DFlash1 Q4_K_M, n=3 | 73.93 / 75.79 | 19.536 / 17.299 |
| DFlash1 Q4_K_M, n=7 | 54.95 / 56.03 | 22.659 / 20.546 |
| DFlash2 ProCreations Q8_0, n=3 | 76.41 / 78.07 | 17.756 / 16.623 |
| DFlash2 ProCreations Q8_0, n=7 | 63.97 / 64.97 | 19.351 / 18.309 |
| DFlash2 NakliTechie Q4_K_M, n=3 | 79.09 / 80.77 | 18.020 / 16.952 |
| DFlash2 NakliTechie Q4_K_M, n=7 | 63.16 / 62.99 | 20.849 / 21.251 |

MTP=1 improves the new backend's isolated decode rate but loses on this
benchmark's total wall time. MTP=2 remains the project default. The source
backend gives approximately 4% higher decoding throughput than the original,
with a smaller end-to-end benefit. Its ten benchmark answers, and those of both
MTP depths, are byte-identical to the original. This is a measured small gain,
not evidence for the much larger speedups reported on other setups.

Actual API draft counters help explain the result: MTP=2 accepted 378 of 858
proposed tokens (44.1%). DFlash2 Q4_K_M accepted 434/1,104 at n=3 (39.3%),
but only 464/2,387 at n=7 (19.4%). More proposed work produced few additional
accepted tokens in these conversations. DFlash also spent more time in prefill.
These counters support the measured result on this workload; acceptance can
change substantially for longer coding or math responses.

Other trials included threads=1/2, polling=0, ubatch=128/256/1024, draft sampling
on CPU, draft probability thresholds 0.25/0.5, CUDA graph optimization, main GPU
sampling, and disabled batch invariance. None gave a convincing improvement in
total wall time. Some altered greedy responses. Main GPU sampling on the new
backend caused an illegal CUDA memory access during the third benchmark
exchange; its partial timing is invalid and the option was rejected. Disabling
batch invariance did not rescue DFlash performance, so the default remains 1.
All repetitions, cache states, transcript comparisons, and failures are retained
in `data/research/performance-20261001/measurements.json`; raw API reports,
container inspections, and server logs are local evidence in
`results/performance/`.

The new backend also started successfully with `BONSAI_CTX_SIZE=131072`, all
LLM state on CUDA0, and completed this same short-history benchmark at
86.61/86.91 decode tokens/s. This checks 128k allocation/startup only. It does
**not** validate 128k recall, latency at a filled window, or DFlash VRAM headroom
at that context. The shipped default stays 16,384.

### DFlash model compatibility and reported experience

[DFlash1](https://huggingface.co/z-lab/Qwen3.5-27B-DFlash) and
[DFlash2](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2) are different draft
architectures. Prism uses `--spec-type draft-dflash` for both; model metadata
selects the DFlash2 candidate-selector path. Merely using that flag does not
make a DFlash2 trial a DFlash1 trial. Repeating `--spec-type` appends strategies
in this backend, so the experiments explicitly removed the entrypoint's MTP
strategy before selecting DFlash. Appending a DFlash override to `run.sh` alone
would leave both selected and fail to initialize the draft as an MTP model.

The first-generation spiritbuun GGUF used architecture `dflash-draft`, which
Prism cannot load. The pinned
[Anbeeld Q4_K_M conversion](https://huggingface.co/Anbeeld/Qwen3.5-27B-DFlash-GGUF)
ran successfully. Its draft was trained for Qwen3.5, not specifically Bonsai2;
this is a compatibility/performance experiment, not an optimal Bonsai drafter.
Both tested DFlash2 drafts were Bonsai-specific:
[ProCreations Q8_0](https://huggingface.co/ProCreations/Ternary-Bonsai-2-27B-DFlash2)
and [NakliTechie Q4_K_M](https://huggingface.co/naklitechie/Qwen3.8-27B-DFlash2-ternary-bonsai2).
Pinned revisions, SHA256s, and model configurations are retained under
`data/research/performance-20261001/`. The target remains our original PTQ1
model; no PQ2 target or alternative fine-tune was substituted.

The most useful controlled firsthand report is
[NakliTechie's L4 comparison](https://github.com/ggml-org/llama.cpp/discussions/29387):
approximately 2.15–2.22x for code/math but 1.37x for conversation, against a
no-speculation baseline. It used a PQ2 target and a different GPU. It also
reports small accuracy changes in greedy batched verification and warns that
reasoning loops can inflate tokens/s. Those details explain why its headline
is not a promised gain over our already fast PTQ1+MTP backend.

Consumer reports are mixed. The author's
[RTX 4060 hobby benchmark](https://www.reddit.com/r/LocalLLM/comments/1wlsaoq/ternary_bonsai_2_27b_near_top_performance_while/)
found good results with thinking disabled, while comments describe repetitions,
hallucinations, and weaker practical rule following. An earlier
[launch discussion](https://www.reddit.com/r/LocalLLM/comments/1wk6982/bonsai_2_27b_quantized_38_27b_98_intelligence_of/)
contains useful coding and long-context anecdotes alongside very different
throughput figures. Many omit backend revision, quantization, offload, cache
state, or exact prompts, so they are leads for experiments rather than controlled
comparisons. The
[reconstruction/retrieval post](https://www.reddit.com/r/LocalLLaMA/comments/1wkwz69/ternarybonsai227bpq2_0_is_not_completely/)
explicitly describes an informal test, not a general quality score. These
reports motivated paired coding, recall, instruction, tool, and reasoning
checks against the original image instead of judging quality by tokens/s.

### Final paired quality evaluation

Quality probes were run after all speed sweeps, against the exact original
GHCR image and fourteen other configurations: original MTP=1/3, the optional
image with MTP=2, Prism MTP=1/3, DFlash1 n=3/7, both DFlash2 drafts n=3/7, and
Prism/DFlash2 batch-invariance controls. Each configuration passed:

- Nine added reasoning, JSON/extraction, instruction-following, updated-fact,
  unknown-fact, and tool-call probes. Three tasks explicitly enable thinking
  with the unchanged `medium` reasoning effort.
- All three coding tasks and their 23 trusted assertions, executed only in the
  existing restricted Python container harness.
- Both CPU BF16 vision fixtures, arithmetic chat, and recall from a prompt with
  15,009 actual API prompt tokens in the 16,384-token window.

All compared answer and reasoning text fields across sixteen responses per
configuration were identical to the original on these probes. Tool-call names and parsed arguments
were also correct; randomly generated call IDs are not compared. Some n=7
DFlash benchmark conversations diverged from the original library plan. A
qualitative review found alternative valid design/activity suggestions rather
than a clear quality improvement; this does not establish equal quality beyond
the checked cases. The controlled external DFlash2 report also documents small
accuracy losses from near-tied greedy choices. DFlash is therefore not selected
as a performance or quality upgrade here.

The selected MTP=2 image also preserved all ten benchmark answers byte for byte.
No response-quality deterioration or improvement was observed in these tests.
This is a small regression evaluation, not a broad statistical assessment or a
guarantee about future questions. Machine-readable paired results and limits are
in `data/research/performance-20261001/quality-comparison.json`; the identified
responses, runtime hashes, command/mount provenance, and checksummed logs remain
in `results/performance/quality-final/`.

The actual 15k recall probe took 10.523 seconds on the original and 10.087 seconds
on the selected backend. API prefill rates were 1,445.83 versus 1,509.87 tokens/s;
the reply is too short to use its decode rate as a speed benchmark. Final speed
verification uses the unchanged text benchmark instead.

The evidence auditor was corrected to decode verbose token-byte fragments only
for text checks while hashing the original log bytes, and to recognize both
published and current MTP initialization messages. Fixtures cover these formats,
missing initialization, and tampered log bytes. The upstream bundles and saved
logs were not edited to satisfy the audit.

Fresh complete `tests/run-qa.sh` suites passed for the exact original image in
`results/runs/20261001T191508Z-89813` and the selected image in
`results/runs/20261001T191716Z-96420`. Both suites created owned 16k and 8k
containers, used the existing unicorn image asset, and passed every checksum-bound
QA audit check. The offline regression suite and actual CUDA dependency / missing
driver runtime checks also passed. A default image build without the source
option and the restored optional image build both succeeded.

### Final simple_text_benchmark verification and running state

The quality-validated optional image is running as `bonsai2-27b` on
`http://localhost:8080`, at the unchanged 16,384-token context with MTP=2.
Its immutable image ID is
`5f327fa98e1474285f8e943f20eb9ca3d497b3d79f6d3261949db25d9deae6c0`.
The stopped original container is preserved as `bonsai2-27b-original-20261001`.
The image is a local development build; no image was published and no release
or existing Git tag was moved. Existing unrelated installer work was preserved.

Final verification used the unchanged `simple_text_benchmark.sh` twice:

| Final run | Decode tokens/s | Wall seconds | Output tokens / wall second | Cache hits |
| --- | ---: | ---: | ---: | ---: |
| Cold first conversation | 87.57 | 15.806 | 50.99 | 87.09% |
| Warm repeated conversation | 87.92 | 15.436 | 52.22 | 89.94% |

Both runs completed all ten exchanges / twenty messages, with 15,162 prompt,
806 completion, and 15,968 cumulative API usage tokens. All answers matched the
original exactly. The cold run had zero cached tokens on the first exchange,
13,205 cached prompt tokens overall, and 1,957 processed prompt tokens. The
warm run started with 431 cached tokens; these figures must not be compared as
if both runs started cold.

Against the user's supplied 84.49 decode tokens/s and 16.069 seconds, the final
cold run improves decode throughput by 3.6% and lowers wall time by 1.6%. Against
the freshly measured cold baseline of 84.03 and 16.134 seconds, the improvements
are 4.2% and 2.0%. The remaining end-to-end cost includes prompt processing and
request overhead; the decode gain does not translate directly into the same
percentage wall-time reduction.

Raw reports are `results/performance/final-simple-text-benchmark-cold.json` and
`results/performance/final-simple-text-benchmark-warm.json`, with final container
inspection/log evidence beside them. Their SHA256 identities and compact
measurements are retained in the research JSON. `results/last-build.json`
identifies the exact built image and all three backend inventories.

## 2026-10-02: official Z Lab Qwen3.8 DFlash2 test

At the user's request, this test uses the exact official
[z-lab/Qwen3.8-27B-DFlash2](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2)
checkpoint, revision `50307d4c4cde6860d4eee73e2547cd786fe8e8a4`. It is the
Qwen3.8 target drafter described by its authors, without Bonsai-specific
re-fitting. It is distinct from the two community Bonsai-adapted drafts tested
on October 1. The authors' published numbers use a full Qwen target on H200 and
SGLang; they are not measurements of this PTQ1 Bonsai container.

Actual CUDA driver access was verified before downloading the 3,848,817,896-byte
Safetensors file. Its pinned SHA256 is
`67fc76d68dc5a9415511a4f394ef744d67510cd20e93b37cc2cc7d28e4bab65c`.
The repository does not supply a GGUF. Conversion used the already tested Prism
source revision `88c4bc60b9c9578f134385be9535e853f2db9b9f`, and the matching
Qwen tokenizer at `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
Tokenizer inputs were checked against their upstream Git blob or LFS identities.
The converter ran with Python bytecode disabled inside an isolated Python
container, with recorded package versions. No host-wide tools or drivers were
installed. Configurations and conversion provenance are retained under
`data/research/zlab-dflash2-20261002/`.

Two conversions were tested: BF16, preserving the draft weights without
quantization, and Q8_0. Both contain 81 tensors and use the same source checkpoint.
Their GGUF SHA256s are respectively
`8b91284fe4a90dd1d6736f3c3ed73be0cc091770d555b5902d970ff5bd0cfd5f`
and `1c6b30af5cfcb9ee42059b18eea4e175dc70d67a1aa44f753b9b7727905e249e`.
The target PTQ1 model, its original tokenizer/chat template, medium reasoning
default, CPU BF16 vision, main/draft q8_0 KV caches, Flash Attention, batch
invariance, and CUDA0-only LLM placement were preserved. The experiment explicitly
removed the default MTP strategy before selecting `draft-dflash`; main and draft
both remained on CUDA0, with no automatic CPU offloading.

### Fresh, uncontended simple_text_benchmark measurements

A fresh MTP=2 baseline and each draft/depth pair received two runs: cold prompt
cache followed by a warm repeated conversation. All used the unchanged
`simple_text_benchmark.sh`, with ten exchanges, twenty messages, and about 16k
cumulative API usage in the 16,384-token window. These are short-conversation
measurements, not a filled 16k context or a long coding workload. Initial Q8_0
exploratory runs overlapped converter/artifact I/O; they were retained locally
but excluded from the comparison below. All listed runs took place after that
work completed, without a competing GPU container.

| Variant | Decode tokens/s, cold / warm | Wall seconds, cold / warm | Cold draft acceptance |
| --- | ---: | ---: | ---: |
| Existing Prism backend, MTP=2 | 87.21 / 87.64 | 15.952 / 15.549 | 44.06% |
| Official DFlash2 Q8_0, n=3 | 71.95 / 73.45 | 19.362 / 18.097 | 35.48% |
| Official DFlash2 Q8_0, n=7 | 56.95 / 57.95 | 22.275 / 21.064 | 16.14% |
| Official DFlash2 BF16, n=3 | 66.16 / 67.33 | 20.214 / 19.013 | 35.83% |
| Official DFlash2 BF16, n=7 | 49.83 / 50.46 | 24.253 / 23.184 | 16.71% |

The official checkpoint loads and drafts successfully, but neither precision nor
depth accelerates this workload. BF16 does not resolve the performance deficit.
The best official variant, Q8_0 n=3, is about 17.5% slower in decode throughput
and takes about 21.4% longer end to end than the fresh cold MTP=2 baseline.
Increasing draft depth sharply reduces acceptance and increases total work.
This result applies to the unchanged Bonsai PTQ1 target and this GPU/backend;
it does not contradict speedups measured with a full-precision Qwen target.

The n=3 variants retain all ten benchmark answers exactly. The n=7 variants
change conversation answers, as seen in the previous batched verification
experiments. The final paired correctness evaluation follows these speed tests.

### Final quality comparison

After the complete speed sweep, fresh identified tests were run on the exact
original GHCR image, the existing optimized MTP=2 image, and all four official
draft configurations. All six configurations passed nine reasoning / instruction
/ JSON / tool-call probes, three coding tasks with 23 restricted-container
assertions, two CPU BF16 vision fixtures, arithmetic chat, and recall from a
15,009-token actual API prompt. All compared answer and reasoning text fields
across the sixteen responses matched the original. Tool names and parsed
arguments were independently checked; random tool-call IDs were excluded.
Verbose server logs also confirmed no CPU model buffers. Runtime command/mount
provenance and checksummed raw logs are retained alongside the responses.

No improvement or degradation was observed on these paired quality probes.
They remain a small regression evaluation, not a general proof of unchanged
quality. The official n=7 benchmark conversations diverge. The earlier controlled
[DFlash2 report](https://github.com/ggml-org/llama.cpp/discussions/29387) documents
near-tied greedy choices in batched verification; token margins were not measured
for the divergences here. Identical target weights alone do not establish
byte-identical answers for every batch shape. The official model did not improve speed on this
host; the existing MTP=2 service is retained. The final verification below uses
`simple_text_benchmark.sh` again after the quality evaluation.

### Final unchanged benchmark and restored service

After quality evaluation, the best official variant (Q8_0, n=3) was checked
again with the unchanged `simple_text_benchmark.sh`: cold/warm decode rates
71.84/73.43 tokens/s and wall times 19.260/18.072 seconds. Both conversations
matched the MTP baseline exactly. The existing `bonsai2-27b` MTP=2 container was
then restarted on localhost:8080 at 16,384 tokens. Its final cold benchmark
measured 87.21 decode tokens/s and 16.191 seconds, with all ten exchanges,
15,162 prompt tokens, 806 completion tokens, 15,968 cumulative usage tokens,
87.09% cache hits, and zero cached tokens on the first exchange. The official
Q8_0 n=3 cold verification was 17.6% slower in decoding and took 19.0% longer
end to end than that restored-service verification.

No serving defaults or runtime binaries were changed. The converter container
was removed. Raw reports, converter inventories, and identified quality responses
remain under `results/performance/`; compact measurements, checksums, pins,
and quality results are retained in `data/research/zlab-dflash2-20261002/`.
The final MTP control report is
`results/performance/zlab-official/final-mtp2.json`.

## 2026-10-02: three repeated MTP comparisons

The unchanged `simple_text_benchmark.sh` was run three times each for MTP=1,
MTP=2, and no speculative decoding on the existing optimized image. Every run
used a fresh container and cold prompt cache. Block orders were 1/2/off,
2/off/1, and off/1/2, with one GPU container at a time. All used the same
Prism runtime binary, CUDA0 placement, 16,384-token context, q8_0 caches,
Flash Attention, CPU BF16 vision, and batch invariance. Each completed ten
exchanges with 15,162 prompt and 806 completion tokens (15,968 cumulative
usage). All nine full conversations were identical. Off runs had no MTP
strategy in the actual process arguments and zero proposed draft tokens.

An initial preliminary series mistakenly selected the older backend for two
off runs through an obsolete temporary entrypoint. That entire series was
excluded and all nine measurements were repeated after correcting the
entrypoint. Recorded process arguments and executable hashes verify that
the following runs all use the identical optimized backend.

| Variant | Wall time runs (s) | Mean wall time ± sample SD (s) | Mean decode ± sample SD (tokens/s) | 95% t interval for mean wall time (s) |
| --- | --- | ---: | ---: | --- |
| MTP=1 | 16.052, 16.091, 16.145 | 16.096 ± 0.047 | 89.13 ± 0.07 | 15.980–16.212 |
| MTP=2 | 15.805, 15.850, 15.900 | 15.852 ± 0.048 | 87.32 ± 0.09 | 15.734–15.970 |
| No speculation | 17.381, 17.401, 17.372 | 17.385 ± 0.015 | 73.49 ± 0.06 | 17.348–17.422 |

MTP=2 has the shortest mean total wall time: approximately 1.5% less than
MTP=1 and 8.8% less than no speculation. MTP=1 has about 2.1% higher decode
throughput, but this does not offset its other request work in this benchmark.
MTP=2 remains the serving default. These confidence intervals use Student
t with two degrees of freedom, assuming independent approximately normal
measurements. Three repeated runs of one deterministic conversation provide
evidence of repeatability here, not statistical certainty or generalization
to other prompts, sustained workloads, or 128k context.

The restored MTP=2 service on localhost:8080 passed a separate final unchanged
benchmark (87.26 decode tokens/s, 15.861 seconds); it is
excluded from the three-run means. No serving defaults or runtime binaries
changed. Reports and logs are in `results/performance/mtp-triplicate-20261002/`;
compact measurements, statistics, and evidence hashes are retained in
`data/research/mtp-triplicate-20261002/measurements.json`.

## 2026-10-02: unified native Linux NVIDIA installer

`install_nvidia.sh` consolidates the driver and Podman Toolkit/CDI installers.
The old installer scripts have been removed; use `install_nvidia.sh`. NVIDIA's official
[toolkit requirements](https://github.com/NVIDIA/nvidia-container-toolkit) state
that a host NVIDIA driver is required, while the host CUDA development toolkit
is not required for container execution. The project keeps CUDA runtime
libraries in its image and installs the CDI base package on the Podman host.
The [CDI guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html)
and [troubleshooting guidance](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/troubleshooting.html)
cover refresh services and the Podman 4 feature flag retained by the installer.

A fresh `--check --verify-container` completed successfully on Linux Mint 22.3,
kernel 7.0.0-38-generic, RTX 4070 Ti SUPER (CUDA capability 8.9), driver
595.91.07, Podman 6.1.2/rootless/crun/cgroup v2, and Toolkit 1.20.1. The actual
CDI spec was `/var/run/cdi/nvidia.yaml`, version 0.7.0. The isolated, networkless
container probe returned 8.9, and all three packaged backend dependency checks
passed against image `5f327fa98e1474285f8e943f20eb9ca3d497b3d79f6d3261949db25d9deae6c0`.
The private diagnostic log is retained in
`results/nvidia-setup/20261002T125728Z-195453.log`; its checksum and source links
are retained in `data/research/nvidia-setup-20261002/verification.json`. Earlier installation/CDI failure notes above describe
the historical October 1 state, not this current verified setup.

No host packages or CDI configuration were modified during this check.
Installation, driver/reboot handling, Podman 4 compatibility, failed CDI
generation, and error propagation are checked through isolated command fixtures;
this does not claim a fresh real driver installation was tested. The offline
regression runner includes `tests/test-nvidia-setup.py`.

The final unchanged `simple_text_benchmark.sh` completed all ten exchanges
(15,968 cumulative tokens, context 16,384) at 87.47 decode tokens/s and
15.633 seconds. Its report and checksum are recorded in the verification JSON.

## Local repository integration — 2026-10-02

Eight commits from the supplied `other_repo/ai_bonsai27` checkout were imported
by fast-forward, from `e6e37a4` through `b875b68`, preserving their original
history. They add the optional pinned SM89 backend, performance and DFlash
research, extracted documentation guides, unified NVIDIA setup diagnostics,
and the renamed `image_build.sh` entry point. No tracked source files were
missing after integration. The source checkout's uncommitted differences were
executable-bit losses from copying; committed executable modes were preserved.
Local repository copies are now ignored, including during build snapshots.

The supplied optional Ada runtime passed `tools/verify-ada-source.py` before
and after local import. Its inventory SHA256 is
`2a29849cac102e76591f82a9b1b93515bd14f0fab9dbb0003ca93e16112ac921`.
These binaries remain excluded from Git; the default image still uses the
original published bundles. Imported Ada measurements describe the other
host's recorded runs, not fresh measurements on this WSL2 notebook.

The complete offline regression runner and all tracked shell/Python syntax
checks passed. A fresh standard development build produced local `1.5.0` and
`latest`, image ID
`021a4cadbe75a1cd685b46c30d74aa53577af7ac16add8777b8d34baf01c0b43`,
source `b875b68e1915c3c5c1b8de3e87cb30f8bdb24821`, marked dirty because the
integration documentation and ignore rule were added locally. Both packaged
backend dependency checks passed with real CUDA access. Negative startup
checks confirmed that missing GPU access fails before downloads, and invalid
settings or a read-only model cache fail before GPU detection. No release tags
were created or moved and no images were published.

Fresh identified GPU/API QA on this RTX 5070 Ti Laptop WSL2 host passed all
18 audit checks, both vision fixtures, all 23 coding assertions, the unicorn
image description, and 16k/8k context verification. Evidence is retained in
`results/runs/20261002T143103Z-1520949/`. Logs verified 66/66 layers and all
language-model buffers on CUDA0, main/draft Flash Attention and q8_0 caches,
MTP=2 with positive draft/accepted API counters, and CPU BF16 vision.
The 15,009-token input measured 653.2 prompt tokens/s; the three coding
responses measured 63.0, 62.2, and 62.2 generated tokens/s. These are fresh
standard-backend measurements, separate from the imported Ada experiments.

## Native Blackwell and DFlash experiments, October 2, 2026

The notebook comparison uses an RTX 5070 Ti Laptop GPU (12 GB), WSL2, rootless
Podman, and the pinned PTQ1_0 MTP Lean target with CPU BF16 vision. Both native
Ada and native Blackwell runtimes are now packaged in the same image, alongside
the original two published bundles. Ada's prepared runtime inventory remains
unchanged (`2a29849cac102e76591f82a9b1b93515bd14f0fab9dbb0003ca93e16112ac921`).
Selection is automatic: native Ada on CUDA capability 8.9, native Blackwell on
12.0, and the published Ampere bundle on 8.6. No automatic CPU model offload
was added.

The Blackwell source is Prism revision
`f13265492743209a0fbedc2a2781af3f5f0eab13`, verified source archive SHA256
`0368b7a5aa02215cafd72b590162ae6b87ca1690be18445c9af7a53145d4c2d5`, compiled
with the same digest-pinned CUDA 12.8 image as Ada, native `120-real`, CUDA
Graphs and Flash Attention enabled. Actual CMake options, binaries, runtime
libraries, licenses, and complete SHA256 inventory are recorded and verified.
The prepared Blackwell inventory is
`f2df852338b092c190435bdedabef291740812245719d5522f4b38a2b4d86be3`.
The imported Ada files had lost executable permission bits during Windows
filesystem transfer. Container installation restores executable modes for
backend binaries without changing their bytes or SHA256 inventory. Otherwise
the executable-based optional selection would silently skip the prepared Ada
backend. The final image dependency check covers all four installed runtimes.

The two commits after the Ada source pin concern SYCL and WebGPU, not an
additional CUDA optimization. The older published Blackwell bundle was already
compiled for SM120; this comparison therefore measures a newer fork/kernel/MTP
implementation as well as the source build, rather than attributing every gain
to an architecture flag. Source revision metadata is retained under
`data/research/blackwell-20261002/`.

[Prism PR221](https://github.com/PrismML-Eng/llama.cpp/pull/221) integrates hybrid
PTQ1_0 kernel dispatch, native quantized-KV Flash Attention, and MTP catch-up
changes. The prepared source is unchanged upstream code. Compiler scripts are
snapshotted before compilation, real CUDA access is checked inside the compiler
container, and WSL driver paths are supplied for linking. Driver import stubs
are not packaged as runtime drivers. Failed Blackwell builds retain their work
for a verified resume; source files are re-extracted from the checksum-verified
archive. Image preparation checks temporary space before copying the four
runtime inventories, addressing a real small `/tmp` tmpfs failure encountered
during development.

### DFlash compatibility and failure diagnosis

DFlash2 support is present in the pinned Prism source. The merged
[Prism PR261](https://github.com/PrismML-Eng/llama.cpp/pull/261) implements the
local convolution/candidate selector and reports end-to-end Bonsai tests on
RTX 5090, including PTQ1_0. The prerequisite borrowed-embedding/output Hadamard
handling comes from [PR210](https://github.com/PrismML-Eng/llama.cpp/pull/210).
Consequently neither missing DFlash2 support nor a general lack of Blackwell
support explains these local failures. Published L4/5090 measurements concern
other hardware, different memory headroom, workloads, and sometimes PQ2_0;
they are not measurements from this notebook.

The [Bonsai-specific r3 draft](https://huggingface.co/naklitechie/Qwen3.8-27B-DFlash2-ternary-bonsai2)
is trained on the ternary target's own features/generations. Its block size is
8, so depth 7 follows its documented configuration. The original z-lab Qwen3.8
DFlash2 draft was also tested as Q8_0. The older Qwen3.5 DFlash draft uses a
16-token block and different feature taps/mask token; it is a cross-version
comparison rather than a model-specific recommended drafter. Draft revisions,
files, SHA256 values, and the local conversion provenance are recorded in
`measurements.json`; no unpinned draft download was added to production startup.

**The draft-load exception is reproducible from the actual memory report.**
The failed DFlash2 startup logs show 11,026 MiB free before loading the target,
then **0 MiB free** immediately before loading the draft. In pinned
`src/llama-model.cpp:1586–1631`, an unspecified tensor split is calculated from
free memory. The special fallback handles `free=0,total=0`, but not
`free=0,total>0`. With one GPU, the split normalization becomes `0/0` (NaN),
`upper_bound` returns index 1, and `devices.at(1)` throws the recorded
`vector::_M_range_check` exception. The retained minimal C++ reproducer produces
the same index and exception; an explicit split of 1 produces CUDA device 0.
`entrypoint.sh` therefore fixes `--split-mode none --tensor-split 1`, consistent
with the existing CUDA0-only requirement. This avoids the indexing bug; it does
not create VRAM or justify CPU offloading.

Verbose buffer records show approximately 5,660.57 MiB of target weights,
544 MiB of target KV, 1,197 MiB recurrent state, and 150.28 MiB initial target
compute scratch. The r3 Q4_K_M draft adds 1,079.61 MiB weights, 26.56 MiB KV,
and 558.51 MiB compute scratch. Their sum is about 9.0 GiB, before driver
contexts, graph/pool allocations, temporary peaks, and other GPU applications.
These buffer sizes are allocations, not a complete physical-residency audit.
The user subsequently confirmed a GPU-intensive background application during
the first experiment series. That makes memory contention a concrete confounder,
not evidence that DFlash itself cannot run on a 12 GB Blackwell notebook.

**The initial inference timeouts are not established kernel deadlocks.**
One timed-out verbose run logged 431 prompt tokens processed in 60.09 seconds
(7.17 tokens/s), then emitted its first token at 145.72 seconds after server
start. Cancellation occurred at 150.92 seconds after start when the client's
120-second conversation deadline expired. Startup/initialization is separate
from the request deadline; these timestamps establish slow progress, not a
permanent CUDA kernel deadlock. Memory/load pressure can therefore explain a
failed client test without proving a hung kernel. Windows/WSL driver paging is a plausible
contributor but was not directly profiled; no CPU LLM offload was enabled.
NVIDIA documents limits to WSL memory/NVML behavior in the
[CUDA on WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

A historical Blackwell PDL race in the PTQ1_0 consumer is documented in
[the published kernel notes](https://github.com/sudoingX/bonsai2-small-gpu/blob/main/kernel/blackwell.md).
The pinned source already calls `ggml_cuda_pdl_sync()` before the first load in
`mmvq-ptq1_0.cuh`, and the GDN path also contains its wait. The documented
q4_0 vector-kernel stack issue does not explain these q8_0 cache tests.
Disabling PDL alone did not prevent all initial timeouts. Clean runs with PDL
on/off are used below to distinguish memory contention from that older bug;
no unverified kernel patch is applied to a verified upstream bundle.

The first timing series is retained as **contaminated historical evidence** in
`data/research/blackwell-20261002/measurements.json`, including failed trials.
Its initial 31.31→38.02 tokens/s comparison must not be used as the final speedup
claim. GPU telemetry, identified logs, completed API counters, and fresh-server
repetitions after the background application stopped are recorded separately.

### Clean repetitions after competing GPU load stopped

The user confirmed the competing application had been removed before these
repetitions. Initial global GPU telemetry reported 845 MiB used, 1% utilization,
and 58°C. Baseline/native runs were alternated, with a fresh server and prompt
cache every time. All modes retained 16k allocated context, q8_0 main/draft
caches, Flash Attention, CPU BF16 vision, medium template reasoning effort, and
greedy thinking-disabled conversation requests. Usage is cumulative over ten
exchanges, not a filled 16k context. Timestamped startup/inference GPU telemetry,
image/container IDs, actual executable paths, per-request draft/cache counters,
and report/log SHA256 identities are summarized in
`data/research/blackwell-20261002/clean-measurements.json`; raw evidence stays
under `results/blackwell-clean-20261002/`.

| Mode | Repetitions | Mean decode tokens/s | Mean wall seconds | Prompt-cache hit rate |
| --- | ---: | ---: | ---: | ---: |
| Published Blackwell, MTP=2 | 3 | 39.91 | 34.708 | 87.37% |
| Native SM120 Prism, MTP=2 | 3 | 43.34 | 32.934 | 87.37% |
| Native + Qwen3.5 DFlash, depth 3, PDL on | 3 | 34.99 | 39.650 | 87.39% |
| Native + Bonsai DFlash2, depth 3, PDL on | 3 | 31.41 | 41.172 | 87.36% |
| Native + Bonsai DFlash2, depth 7, PDL on | 3 | 30.34 | 43.109 | 87.50% |

The clean MTP comparison yields **8.6% higher decode throughput** and **5.1%
less conversation wall time**. All three paired native runs beat their baseline
run. The initial contaminated 21.4% result is superseded. MTP and DFlash1 runs
used 15,949 cumulative tokens / 823 output tokens. DFlash2 depth 7 used 15,951
cumulative tokens / 841 outputs; near-tied greedy choices can differ between
single-row and batched verification, as upstream PR261 documents. Rates use
actual server decode timings and are distinct from output/wall throughput.

All three clean DFlash1 runs and all six clean DFlash2 runs completed without
load exceptions or client timeouts, with **PDL enabled**. Each draft mode passed
nine quality probes and three restricted coding tasks / 23 assertions. A
separate verbose PDL-disabled DFlash2 diagnostic also completed. Its draft-load
log reports **3444 MiB free**, versus **0 MiB** in the contaminated failures.
This controlled change, the exact split-error reproducer, and the earlier
slow-progress log identify memory/load contention plus the upstream split bug
as the supported explanation, rather than an inherent DFlash2/Blackwell
incompatibility. No Windows paging profile or compute-sanitizer trace was
captured, so a specific driver-paging mechanism is not claimed as proven.

DFlash performance depends strongly on workload. Actual conversation counters
show 43.12% draft-token acceptance for MTP, 35.58% for the Qwen3.5 draft, and
19.65% for Bonsai DFlash2 depth 7. The latter pays drafting/verification costs
for mostly rejected prose tokens. On its three small coding tasks it instead
accepted 80.95–91.84% of drafts and decoded at 119.75, 104.69, and 119.80 tokens/s;
all generated functions passed execution assertions. A separate clean native
MTP coding diagnostic reached 65.35, 63.07, and 70.11 tokens/s on the same three
tasks. Its arithmetic/modular
thinking probes achieved 105.99/100.83 tokens/s, versus native MTP's
69.67/69.46 on the final clean paired backend run. These are individual probes,
not a broad coding benchmark. The older Qwen3.5 draft gave 63.08–67.54 tokens/s
on coding and provides no clear advantage over MTP here.

The source dispatch sends PTQ1_0 verification up to four columns through MMVQ
and five or more through MMQ, with the threshold documented as Ada-tuned.
Depth 7 can use a different verify kernel than depth 3. This is a plausible
performance contributor, not a profiled cause of failure; no unmeasured kernel
threshold patch is introduced. DFlash2 metadata contains its convolution and
selector, and the source detects DFlash2 by a positive selector top-k. Both
DFlash generations correctly use the same `draft-dflash` server strategy name.

The recommended default remains native MTP=2, preserving the existing runtime
contract. DFlash2 is useful for predictable code/math on this notebook, but the
conversation evidence does not support making it the default. Test helpers
replace MTP rather than accidentally append both strategies, keep target/draft
weights and caches on CUDA0, validate depth/PDL controls, and preserve partial
evidence on failure. No CPU LLM fallback or production draft-model download is
added.

### Final image validation

A fresh suite `20261002T161853Z-1675445` on the final combined runtime passed
18/18 audited checks: CUDA-only language-model/draft buffers and state, main
and draft q8_0/Flash Attention, MTP depth 2 with actual API draft counters,
15,009-token recall, model identity, 16k and environment-selected 8k context,
CPU BF16 vision, two shape/color vision probes, the unicorn-image request, and
three generated functions with 23 restricted execution assertions. All four
packaged backends passed the dependency check with real CUDA attached. The
nonexecutable-server negative test and pre-download missing-CUDA failures also
passed, as did the complete offline regression suite. No Python bytecode
caches were found. Compact identified validation metadata is retained in
`final-validation.json`. Benchmark image IDs remain bound to their actual
measured development builds; no measurement is relabeled as a future image.

## Blackwell MTP depth comparison — October 2, 2026

Measured MTP maximum draft depths **1, 2, and 4** on the same native SM120
Blackwell backend (`f13265492743209a0fbedc2a2781af3f5f0eab13`), using image
`sha256:63f0fab88587e1a3d3f2e111191d27db47168427545cf90a038eff46e97bf4bf`
from clean project commit `9a7de448a37d828b02782014f79704b6cc484806`.
This is a new comparison with a fresh MTP=2 control, separate from the earlier
published/native backend and DFlash measurements.

Each depth ran three times in a fresh container, with block orders **1/2/4,
2/4/1, 4/1/2**. The image entrypoint was extracted and its single
`--spec-draft-n-max` value changed in a read-only mounted copy, together with
its status text. Saved `/proc/1/cmdline` confirms the requested value; all
other server arguments are identical after normalizing that one value.
All nine runs used the native Blackwell executable. Nonzero API `draft_n`
and `draft_n_accepted` counters prove speculation actually occurred.
The maximum depth controls recursive drafting; it does not add separate
physical MTP heads to the model.

Settings: 16,384-token context, one slot, CUDA0 language model and draft,
main/draft q8_0 K/V caches, Flash Attention, BF16 vision on CPU/RAM, medium
reasoning configuration. The conversation requests disable thinking and use
greedy sampling. Each benchmark retains ten exchanges / twenty messages and
approximately 16k cumulative API usage tokens, rather than filling a unique
16k context. Initial prompt cache is empty in each fresh container.

| MTP maximum depth | Decode repetitions (tokens/s) | Mean decode ± sample SD | Mean wall time | Prompt cache hits | Draft acceptance |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | 49.69 / 47.09 / 48.30 | 48.36 ± 1.30 | 30.919 s | 87.33% | 60.71% |
| 2 | 42.42 / 44.54 / 43.51 | 43.49 ± 1.06 | 32.640 s | 87.37% | 43.12% |
| 4 | 32.28 / 31.41 / 32.26 | 31.98 ± 0.50 | 36.409 s | 86.83% | 25.20% |

Cache-hit percentages are token-weighted actual API counters across all three
runs, including the first request's zero hits. Draft acceptance is total
accepted draft tokens divided by total drafted tokens. Decode speed uses API
decode timings; it excludes prefill and request overhead. End-to-end output
throughput was respectively **26.62, 25.21, and 20.42 tokens/s**.
MTP=1 improved mean decode speed by **11.2%** over MTP=2; MTP=4 decreased it
by **26.5%**. More drafting was counterproductive for this conversation.

MTP=1 and MTP=2 produced 823 output tokens and 15,949 cumulative tokens per
run. MTP=4 produced 743 output tokens and 15,934 cumulative tokens, with
changed answers. Each depth's assistant responses were identical across its
three repetitions. Wall times therefore compare different output lengths.
The PTQ1_0 backend selects MMVQ for up to four columns and MMQ beyond that;
MTP=4 can verify five rows. Different batched numerical rounding at near-tied
greedy choices is a plausible explanation for changed text, but kernel
selection and the exact cause were not profiled in this experiment.

Nine quality probes were run once per depth after the third benchmark,
including arithmetic, modular arithmetic, and logic with thinking enabled.
All **27/27** passed. This small check does not establish broad quality
equivalence, and no additional coding or vision suite was run for this
depth-only comparison. The existing project default remains MTP=2.

One-second GPU telemetry was retained for every run. Before startup GPU
utilization was 1–4%, memory usage 1,271–1,350 MiB, and temperature 51–66°C.
This supports low competing load at startup, not exclusive ownership of the
GPU. Rotated orders reduce systematic temperature/order bias; the three-run
sample remains small. An earlier controller preflight stopped before any
benchmark request and is excluded from these nine successful measurements.

Raw evidence is in `results/blackwell-mtp-20261002-171334/` (ignored). The
committed [measurement record](data/research/blackwell-mtp-20261002/measurements.json)
contains per-run counters, actual normalized arguments, quality outcomes,
and SHA256 bindings to benchmark, process, container, server-log, and GPU
telemetry evidence. No image defaults or backend binaries were changed.

### Additional control with MTP disabled

At the user's request, three further fresh-container trials followed the
rotated depth series, using the same immutable image, model, API workload,
and GPU telemetry. The only argument changes versus MTP=2 were
`--spec-type none` and `--spec-draft-n-max 0`; the pinned backend's `none`
implementation does not create a speculative decoder. Saved API timings
contain no draft counters, consistent with disabled speculation.

Decode rates were **43.03, 42.40, and 41.85 tokens/s**, giving a mean of
**42.43 ± 0.59 tokens/s** (sample SD). Mean conversation time was **31.935 s**,
and end-to-end output throughput was **25.78 tokens/s**. Each conversation
produced 823 output tokens and 15,949 cumulative API tokens. Token-weighted
prompt cache hits were **87.30%**, including the initial zero-hit request.
The disabled mode also passed **9/9** quality probes, bringing the complete
four-mode check to **36/36**.

Relative to disabled MTP, MTP=1 improved decode by **14.0%**, MTP=2 by **2.5%**,
and MTP=4 decreased it by **24.6%**. MTP=1 shortened the complete conversation
by only **3.2%**; decode improvement does not translate directly to wall time
because prefill and request overhead remain. MTP=2's small decode advantage
coincided with a slightly longer conversation wall time than disabled MTP.
No general MTP=2 advantage is established by this small workload.
These three disabled trials were consecutive rather than interleaved with
the earlier modes, so additional timing/order drift cannot be excluded.
The same MTP Lean GGUF was retained; unused MTP weights were not removed,
and this test makes no claim of reducing VRAM usage.

Additional raw evidence is in `results/blackwell-mtp-off-20261002-172323/`.
The same committed measurement record includes the disabled mode, counters,
quality outcomes, and evidence checksums. Defaults remain unchanged.

## Blackwell MTP with reasoning enabled — October 2, 2026

The missing full-conversation reasoning benchmarks were run once each for
MTP=1 and MTP=2, using the same native SM120 image and source as the preceding
depth comparison. Previously completed block-1 runs supply the disabled
comparison; no redundant disabled trials were run. These four entries are
single measurements, not means or a contemporaneously interleaved experiment.

The same ten library-planning questions and retained final-answer history
were used. `/apply-template` and `/v1/chat/completions` both received
`enable_thinking=true`; chat also explicitly requested the accepted model
reasoning effort `medium`. Every response was saved in full. All twenty
responses contained nonempty `reasoning_content`, nonempty final content,
and `finish_reason=stop`. The two depths produced **identical reasoning and
final-answer text** on all ten turns. Reasoning was not replayed as assistant
history, consistent with ordinary chat usage.

The temporary benchmark variant increased the completion cap from 128 to
4,096, reserved 512 output tokens in adaptive padding, and retained the
original 228-token estimate for visible-history growth. Natural reasoning
exceeded that estimate: both runs completed ten exchanges but used **20,352
cumulative API tokens**, so the approximate 16k ±5% usage target was **not
met**. The first wrapper exited after saving its complete report because of
this budget check; this was not a failed request or truncated response. The
second wrapper explicitly warned about the budget deviation and preserved
its actual usage. The original project benchmark script was not modified.
An earlier controller permission preflight failed before any API benchmark
request and is excluded.

The context remained **16,384** as configured. Thinking runs had a maximum
input of 1,254 tokens and maximum actual input plus completion of 3,774 tokens.
The user authorized 32k if necessary, but increasing it was unnecessary.
GPU-only language/MTP weights and caches, main/draft q8_0, Flash Attention,
and CPU BF16 vision remained unchanged; saved process arguments bind the
actual MTP depth to each run.

| MTP | Thinking | Decode tokens/s | Wall seconds | Input tokens | Output tokens incl. thinking | Prompt cache hits | Draft acceptance |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Off, earlier block 1 | 49.69 | 30.678 | 15,126 | 823 | 87.33% | 60.71% |
| 2 | Off, earlier block 1 | 42.42 | 32.827 | 15,126 | 823 | 87.37% | 43.12% |
| 1 | On, medium | 55.78 | 259.639 | 6,600 | 13,752 | 80.45% | 89.73% |
| 2 | On, medium | 60.98 | 237.738 | 6,600 | 13,752 | 80.45% | 83.50% |

Thinking favors MTP=2 in this single-run comparison: **9.3% faster decoding**
and **8.4% less conversation time** than MTP=1. Draft acceptance is much
higher than in the non-thinking conversation. Acceptance percentage alone
is not throughput: a depth of two can accept more tokens per verification
step despite a smaller fraction of its drafts being accepted. Neither mode
is universally faster based on these limited workload-specific observations.

Decode rates count all API decode tokens, including hidden reasoning;
end-to-end output throughput was 52.97 tokens/s for MTP=1 and 57.85 tokens/s
for MTP=2. Comparing thinking against disabled thinking changes completion
limits, adaptive prompt padding, output volume, and response text. It is not
a controlled comparison of identical token sequences. In particular, longer
wall time with thinking does not imply a lower token decoding rate.

### VRAM measurement

GPU memory was sampled every second through NVIDIA-SMI, then restricted to
the benchmark's start/end interval. The device reports **12,227 MiB total**.
Values below are total GPU usage, including Windows/desktop/other processes;
idle subtraction is an approximation, not per-container accounting. Short
transient peaks between samples may be missed.

| MTP | Thinking | Idle before (MiB) | Mean during benchmark (MiB) | Peak (MiB) | Peak minus idle (MiB) |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Off, earlier | 1,350 | 8,769.1 | 8,773 | 7,423 |
| 2 | Off, earlier | 1,350 | 8,867.5 | 9,001 | 7,651 |
| 1 | On | 1,271 | 8,682.2 | 8,688 | 7,417 |
| 2 | On | 1,276 | 8,900.1 | 8,938 | 7,662 |

MTP=2 with thinking peaked 250 MiB above MTP=1 with thinking. Peaks above
idle were similar between thinking on/off at the same depth; the different
absolute baselines do not prove a thinking-related memory saving. Both
completed without a CUDA allocation error at 16k context. A 32k configuration
would require a separate capacity test and has not been measured here.

Raw reasoning evidence is in `results/blackwell-mtp-reasoning-20261002-173400/`
and `results/blackwell-mtp-reasoning-20261002-173904/`. The committed
[reasoning comparison](data/research/blackwell-mtp-20261002/reasoning-comparison.json)
retains per-run memory statistics, actual usage, cache/draft counters, and
SHA256 bindings to reports, full responses, runtime arguments, logs, and GPU
telemetry. This is a benchmark and response-integrity check, not a new full
coding/vision quality suite. Container defaults remain unchanged.

### DFlash2 draft depth 4 with reasoning

One additional fresh-container benchmark replaced MTP with `draft-dflash`,
maximum depth **4**, using the Bonsai-specialized
`Qwen3.8-27B-DFlash2-r3-Q4_K_M.gguf` from the earlier experiments, SHA256
`6c11956fde5f52867e3255991b30405ae931d205a35caf3fc87a2c3865aa6530`.
CUDA PDL was enabled. Actual process arguments confirm `draft-dflash`, depth
4, the separate draft model, draft tensor override to CUDA0, and the unchanged
GPU-only target, q8_0 cache, Flash Attention, and CPU-vision settings. MTP was
not combined with DFlash. The same reasoning benchmark variant, questions,
completion cap, and adaptive-padding algorithm were used.

| Mode, medium reasoning | Decode tokens/s | Wall seconds | Output tokens incl. thinking | Mean GPU memory (MiB) | Peak GPU memory (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| MTP=1 | 55.78 | 259.639 | 13,752 | 8,682.2 | 8,688 |
| MTP=2 | 60.98 | 237.738 | 13,752 | 8,900.1 | 8,938 |
| DFlash2 depth 4 | 56.13 | 221.643 | 11,782 | 10,464.6 | 10,470 |

DFlash2 was **8.0% slower in decode** than MTP=2 and used **1,532 MiB more
peak total GPU memory**. Its idle baseline was 1,348 MiB, giving 9,122 MiB
peak above idle. There were 221 one-second samples within the benchmark
interval. As before, total VRAM includes other processes and sampling can
miss shorter peaks. The measured peak leaves 1,757 MiB of the device's
12,227 MiB capacity; this does not establish capacity at a 32k context.

All ten replies had nonempty reasoning and final content and ended with
`stop`. No response was truncated. However, DFlash2 produced different text
and fewer output tokens than the MTP runs: **11,782 output plus 6,316 input
= 18,098 cumulative tokens**. Its shorter wall time is therefore not evidence
of faster token decoding. The approximate 16k cumulative budget was exceeded
and reported explicitly; the context remained 16k. Actual token-weighted
prompt-cache hits were **79.69%**, and draft acceptance was **75.09%**.

This single-run reasoning workload favors MTP=2 for decode speed and VRAM.
It does not establish a universal ranking or quality equivalence; no new
coding/vision suite was run for this additional benchmark. Container defaults
remain unchanged. Raw evidence is in
`results/blackwell-dflash2-reasoning-20261002-174558/`; the committed
[DFlash2 reasoning record](data/research/blackwell-mtp-20261002/dflash2-reasoning.json)
contains actual counters, response-integrity evidence, and memory statistics.

## Standard policy and 32,000-token validation — October 2, 2026

The project standard is now explicitly **MTP maximum depth 2 on every
supported architecture** (Ampere 8.6, Ada 8.9, Blackwell 12.0), including native
and published backends. The common runtime argument group already applied
that setting to all backends and remains unchanged. Alternative strategies
are explicit experiments. Performance benchmarks now always enable thinking
at **medium** effort, both in template rendering and chat requests. Short
functional QA probes retain their task-specific settings.

Exactly **32,000 context tokens** is the new default in the Containerfile,
entrypoint fallback, run.sh, shared settings validation, and backend benchmark
helper. The context remains configurable through BONSAI_CTX_SIZE. It is
32,000, not 32,768. Explicit 16k/8k QA allocations remain unchanged.

The conversation benchmark permits 4,096 completion tokens, rejects missing
reasoning/final content and abnormal completion, and warns rather than fails
when complete reasoning exceeds the approximate cumulative 16k usage target.
The backend helper allows 600 seconds per conversation. Full responses and
interval-filtered total GPU memory statistics are saved alongside reports.

Thinking tokens are counted per exchange and in total. Actual
`usage.completion_tokens_details.reasoning_tokens` is preferred. This pinned
server does not provide that counter, so `/tokenize` counts returned
`reasoning_content` with special tokens disabled. Decoded-text boundaries may
differ from original generated tokens, so this method is explicitly marked
as an **estimate**, with its source recorded. Unavailable counts remain null,
and an incomplete set yields an unknown aggregate. Thinking tokens must not
be added to completion usage a second time.

The new image was built through image_build.sh and verified via actual API
properties and `/proc/1/cmdline`: context 32,000, draft-mtp depth 2, medium
reasoning, CUDA0, Flash Attention, and q8_0. Both specialized Ada and Blackwell
runtimes remain included. A fresh Blackwell benchmark completed all ten
exchanges / twenty messages:

| Metric | Result |
| --- | ---: |
| Decode tokens/s | 62.77 |
| Conversation wall time | 231.195 s |
| End-to-end output tokens/s | 59.48 |
| Input / completion tokens | 6,600 / 13,752 |
| Cumulative API tokens | 20,352 |
| Thinking tokens, retokenized estimate | 12,800 |
| Cached / processed prompt tokens | 5,310 / 1,290 |
| Token-weighted prompt-cache hits | 80.45% |
| Mean / peak total GPU memory | 9,504.85 / 9,516 MiB |
| Memory samples during benchmark | 231 |
| Post-benchmark quality probes | 9/9 passed |

The VRAM peak is **9.29 GiB** on a GPU reporting 12,227 MiB total. It includes
desktop and other processes; one-second samples can miss transient peaks.
The same library questions produce 20,352 cumulative tokens, so the usage
budget deviation is visible rather than hidden. This conversation does not
fill the allocated context, and the run does not prove full-32k recall or
worst-case capacity. It is one measurement, not an averaged comparison with
earlier 16k measurements.

All offline regression fixtures passed, including reasoning-counter preference,
retokenization fallback, unknown thinking counts, missing/truncated reasoning,
cumulative-budget deviations, and GPU-memory interval filtering. An earlier
intermediate validation was not accepted because the development script
changed while its wrapper was running; its timings are excluded from the
final 32,000-token result.

The committed [validation record](data/research/blackwell-32000-20261002/validation.json)
identifies the exact development image used for measurement and binds saved
API, runtime, quality, and memory evidence by SHA256. Raw evidence remains
under `results/blackwell-32000-medium-validation/`, excluded from Git.
Historical thinking-disabled comparisons are explicitly labeled in README;
Ada reasoning-medium performance has not been remeasured here.
