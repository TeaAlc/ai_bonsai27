# Bonsai 2 research and measurement index

## Corrected 30,000-token batch comparison — October 3, 2026

`longcontext.msg` now contains exactly 30,000 tokens verified with the actual
backend `/tokenize` endpoint, using `add_special=false` and `parse_special=false`.
The 135,577-character ledger was calibrated through tokenization/detokenization;
its medium-thinking chat template yields 30,009 API prompt tokens. These counts
were rechecked in each of six fresh measurement containers.

| Setting | Prompt seconds, three runs | Mean ± sample SD | Mean prompt tokens/s | Sampled global peak VRAM |
|---|---|---|---|---|
| Defaults: batch 2048 / microbatch 512 | 54.965 / 54.468 / 56.193 | 55.209 ± 0.888 s | 543.65 | 10,715 MiB |
| Batch 4096 / microbatch 2048 | 59.268 / 60.129 / 57.163 | 58.853 ± 1.526 s | 510.13 | 11,333 MiB |

The larger-batch variant took 6.60% longer on average and used 618 MiB more
sampled peak global VRAM. Three baseline runs preceded three candidate runs;
they were not interleaved. This result concerns one full 30,000-token prompt
on this WSL2 RTX 5070 Ti Laptop host and does not establish general performance.

All six runs used the same image 1.5.0, native Blackwell executable, model hashes,
and request payload, retaining 32,000 context, MTP=2, medium thinking, CPU BF16
vision, q8_0 caches, Flash Attention and `GGML_CUDA_BATCH_INVARIANT=1`. The
completion cap remained 4096, while the prompt left 1,991 context tokens; all
responses stopped normally without truncation or overflow. Every run processed
all 30,009 prompt tokens with zero cached input. The three ledger risks and
plausible mitigations appeared in every final answer. This scoped check does
not replace general functional QA.

Prompt times come from API `timings.prompt_ms`, corroborated by server logs.
HTTP wall times including generation were 69.40–77.16 seconds. Concurrent global
GPU telemetry targeted 200 ms plus query duration (per-run median 243–254 ms).
It includes other host GPU memory and may miss short-lived peaks.

The [corrected retained record](data/research/longcontext-30k-tokens-20261003.json)
contains image/executable/model identities, tokenizer verification, arguments,
all six timings, completion checks and per-run evidence checksums. Raw data,
generation code and frozen benchmark driver are stored locally under
`results/longcontext-30k-tokens-20261003T170547Z/`. The earlier character-based
measurement below remains historical; runtime defaults are unchanged.

## Earlier 30,000-character batch comparison — October 3, 2026

The earlier prompt snapshot contained exactly 30,000 characters and produced
6,547 API prompt tokens. That snapshot remains in the raw evidence directory;
`longcontext.msg` has since been corrected to 30,000 tokenizer tokens. Six fresh
containers used the same image 1.5.0,
native Blackwell executable, model hashes and request payload, with 32,000
context, MTP=2, medium thinking, 4096 completion tokens maximum, CPU BF16
vision and batch invariance enabled. All six returned nonempty reasoning and
answers with `finish_reason=stop`; no input tokens were cached.

| Setting | Prompt seconds, three runs | Mean ± sample SD | Mean prompt tokens/s | Sampled global peak VRAM |
|---|---|---|---|---|
| Defaults: batch 2048 / microbatch 512 | 14.862 / 14.639 / 15.048 | 14.850 ± 0.205 s | 440.94 | 10,612 MiB |
| Batch 4096 / microbatch 2048 | 14.761 / 14.502 / 15.219 | 14.827 ± 0.363 s | 441.72 | 11,211 MiB |

The observed mean processing-time reduction was 0.15%, smaller than run
variation, with 599 MiB more peak global VRAM. This single prompt provides no
material evidence of a speed gain. Baseline runs preceded candidate runs;
they were not interleaved. These are new measurements from the WSL2 RTX
5070 Ti Laptop host, not other platforms or a 30,000-token context test.
Prompt times come from API `timings.prompt_ms`, corroborated by server logs;
HTTP wall times including generation were 29.64–30.51 seconds. Global GPU
telemetry ran concurrently, targeting 200 ms plus query duration, and does
not attribute all memory to the container or guarantee capture of brief peaks.

The [retained record](data/research/longcontext-batch-20261003.json) includes
image, executable and model identities, arguments, timings and per-run
evidence checksums. Raw data and the frozen benchmark driver are stored
locally under `results/longcontext-20261003T163345Z/`. This scoped measurement
does not replace the general functional QA suite. Runtime defaults are unchanged.

Current runtime policy: GPU-only language model/MTP/cache, CPU BF16 vision,
Flash Attention, q8_0 main/draft caches, MTP depth 2, exactly 32,000 context
tokens, and medium reasoning for benchmarks. See [README.md](README.md) for
current operation and [TODO_PLAN.md](TODO_PLAN.md) for cleanup acceptance.
Historical settings and measurements below retain their original scope; they
are not new measurements or proof of untested platforms. Source citations,
artifact hashes and caveats remain in the dated pages and data/research/.

The [original research context](docs/research/original-context.md) preserves
the initial research dates and host diagnosis.

The headings below preserve previous research anchors as links to their new
locations. The September 30 audit is [archived](docs/history/repository-audit-20260930.md).

## Model and versions

[Retained research and sources](docs/research/model-and-runtime.md#model-and-versions).

## MTP variants considered

[Retained research and sources](docs/research/model-and-runtime.md#mtp-variants-considered).

## Server fork and reasoning settings

[Retained research and sources](docs/research/model-and-runtime.md#server-fork-and-reasoning-settings).

## Pinned artifacts and data layout

[Retained research and sources](docs/research/model-and-runtime.md#pinned-artifacts-and-data-layout).

## GPU placement and platform behavior

[Retained research and sources](docs/research/model-and-runtime.md#gpu-placement-and-platform-behavior).

## Validation and observed speed

[Retained research and sources](docs/research/model-and-runtime.md#validation-and-observed-speed).

## Local image versioning added on 30 September 2026

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#local-image-versioning-added-on-30-september-2026).

## Model-cache startup validation (2026-09-30)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#model-cache-startup-validation-2026-09-30).

## Automatic container backend selection (2026-09-30)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#automatic-container-backend-selection-2026-09-30).

## CUDA detection without nvidia-smi (2026-09-30)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#cuda-detection-without-nvidia-smi-2026-09-30).

## Runtime dependency and CUDA preflight audit (2026-09-30)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#runtime-dependency-and-cuda-preflight-audit-2026-09-30).

## Podman Hyper-V GPU feasibility (2026-09-30)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#podman-hyper-v-gpu-feasibility-2026-09-30).

## Model-mount flock failure (2026-09-30)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#model-mount-flock-failure-2026-09-30).

## Follow-up repository audit (2026-09-30)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#follow-up-repository-audit-2026-09-30).

## Hardening implementation and validation (2026-09-30)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#hardening-implementation-and-validation-2026-09-30).

## Publishable rebuilds (2026-09-30 follow-up)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#publishable-rebuilds-2026-09-30-follow-up).

## Desktop GPU option placement (2026-09-30 follow-up)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#desktop-gpu-option-placement-2026-09-30-follow-up).

## Podman Desktop device form verification (2026-09-30 follow-up)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#podman-desktop-device-form-verification-2026-09-30-follow-up).

## CDI API failure and WSL device mapping (2026-09-30 follow-up)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#cdi-api-failure-and-wsl-device-mapping-2026-09-30-follow-up).

## Simpler Desktop GPU configuration (2026-09-30 follow-up)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#simpler-desktop-gpu-configuration-2026-09-30-follow-up).

## Startup stages and failure diagnostics (2026-09-30 follow-up)

[Retained research and sources](docs/research/20260930-runtime-and-desktop.md#startup-stages-and-failure-diagnostics-2026-09-30-follow-up).

## 2026-10-01: RTX 4070 Ti SUPER performance investigation

[Retained research and sources](docs/research/20261002-performance-and-integration.md#2026-10-01-rtx-4070-ti-super-performance-investigation).

## 2026-10-02: official Z Lab Qwen3.8 DFlash2 test

[Retained research and sources](docs/research/20261002-performance-and-integration.md#2026-10-02-official-z-lab-qwen38-dflash2-test).

## 2026-10-02: three repeated MTP comparisons

[Retained research and sources](docs/research/20261002-performance-and-integration.md#2026-10-02-three-repeated-mtp-comparisons).

## 2026-10-02: unified native Linux NVIDIA installer

[Retained research and sources](docs/research/20261002-performance-and-integration.md#2026-10-02-unified-native-linux-nvidia-installer).

## Local repository integration — 2026-10-02

[Retained research and sources](docs/research/20261002-performance-and-integration.md#local-repository-integration--2026-10-02).

## Native Blackwell and DFlash experiments, October 2, 2026

[Retained research and sources](docs/research/20261002-performance-and-integration.md#native-blackwell-and-dflash-experiments-october-2-2026).

## Blackwell MTP depth comparison — October 2, 2026

[Retained research and sources](docs/research/20261002-performance-and-integration.md#blackwell-mtp-depth-comparison--october-2-2026).

## Blackwell MTP with reasoning enabled — October 2, 2026

[Retained research and sources](docs/research/20261002-performance-and-integration.md#blackwell-mtp-with-reasoning-enabled--october-2-2026).

## Standard policy and 32,000-token validation — October 2, 2026

[Retained research and sources](docs/research/20261002-performance-and-integration.md#standard-policy-and-32000-token-validation--october-2-2026).

## Repository cleanup acceptance — October 2, 2026

Three alternating baseline/candidate pairs measured 61.91 ± 0.57 versus
61.73 ± 0.61 decode tokens/s (sample SD), an observed −0.30% difference.
Highest global memory was 9,562 versus 9,583 MiB. All six conversations sent
identical chat payloads, used 32,000 context tokens with MTP=2/medium reasoning,
and counted 12,800 estimated thinking tokens each. Cache hits were 80.45%.
All 54 subsequent quality probes passed. Fresh 16k/8k functional QA passed
18 checks, including CPU vision and 23 restricted coding assertions.

The common compiler path rebuilt native Blackwell from the same pinned source,
compiler digest and package versions; Ada and both published bundles remain
included. CMake options/licenses/inventories are checked for both native profiles.
Three ELF library hashes changed on recompilation; byte reproducibility is not
claimed. Shared configuration, extracted benchmark client, portable UTC telemetry,
checksum-bound evidence, atomic reports and failure cleanup are covered by the
updated offline fixtures. Recorded numbers are from this WSL2 notebook, not
other platforms or a filled 32k window. See the
[measurement and identity record](data/research/repository-optimization-20261002/acceptance.json)
and [validation workflow](docs/validation.md).
