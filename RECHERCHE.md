# Research and implementation: Bonsai 2 27B

Research conducted on 28–29 September 2026; local validation updated on 30 September 2026. Published benchmark numbers below are reported by model or fork authors unless identified as measurements from this notebook.

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

`prepare.sh` downloads and verifies these files. CUDA archives and extracted libraries reside under `data/backends/blackwell/` and `data/backends/ampere-ada/`; retained source/metadata are under `data/research/`. `build.sh` rechecks internal backend checksums and creates the image. GGUF files stay in `BONSAI_MODEL_DIR` on the host (default: the caller’s current directory) and are mounted read/write at `/models` by `run.sh`. The container downloads missing files using the shared pins in `data/models/download.sh`; `download_models.sh` provides the same download on the host. Downloads are locked, resumable, and SHA256-verified before atomic publication; existing nonempty readable files are reused without re-verification. License files for the prebuilt backends are copied into the image under `/opt/bonsai/<backend>/LICENSES/`.

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

Image builds now calculate their project version through the pinned [greatliontech/semrel 0.7.0](https://github.com/greatliontech/semrel/releases/tag/0.7.0) binary, installed and cached under `tools/`. This project version is separate from the fixed Bonsai CUDA backend commits. `build.sh` labels the image with its version and source revision, tags it as `localhost/bonsai2-27b:<version>`, and updates the local `latest` alias after success. `run.sh` defaults to that alias and accepts `BONSAI_IMAGE` for a specific tag.

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
created local `v1.4.0`, and called `build.sh` successfully for both version/latest
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
