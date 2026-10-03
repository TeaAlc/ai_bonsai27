# Bonsai 2 research and measurement index

## Planned PTQ1 optimization campaign — October 3, 2026

The [implementation and acceptance plan](docs/ptq1-optimization-plan.md) orders
isolated changes to host overhead, MMQ scale reuse, activation preparation,
Hadamard fusion and matvec activation loads. It requires exact numerical and
model-behavior preservation, realistic short/long analysis/tool/coding cases,
sanitisers, explicit ownership/dependency contracts, fault injection and soaks.
Only Blackwell hardware is available: Ampere/Ada paths are qualified by native
compilation, generated-code/resource inspection and theoretical equivalence and
progress review, with conservative fallback. Their runtime performance and
quality are not measured. No kernel has been changed by preparing this plan.

## Packing recheck and PTQ kernel review — October 3, 2026

The local model profiles were **not swapped**: PTQ1_0 Lean is GGUF type 143,
6,297,658,848 bytes, SHA256 `1e33c571a5ce7a9a3e42474d66192923d5a6d77da7fb3a22986dc809522b5685`;
PQ2_0 MTP is type 142, 7,557,178,656 bytes, SHA256
`78df4279d40ebebdccfd2dae0e9d4847afee52e94f48f3542ae9437220dbd847`.
These hashes agree with all six checksum-verified recorded benchmark selections
([identity recheck](data/research/pq2-0-mtp-20261003/identity-recheck.json)). The pinned backend
enum explicitly maps 142 to PQ2_0 and 143 to PTQ1_0.

A deeper search found conflicting first-person reports in
[CPU kernel PR #206](https://github.com/PrismML-Eng/llama.cpp/pull/206) and
[model discussion #12](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/discussions/12):
roughly 0.89% PQ2 codes reportedly represent +2, making PTQ packing lossy.
The PQ2 codec can represent +2, so that possibility required checking the actual
files rather than relying on the ternary wording of the model card.

Two independent local scans resolve this for **our exact pins**. A NumPy scan
counts all 26,869,760,000 main weight codes: 9,042,815,129 minus-one,
8,802,946,533 zero, 9,023,998,338 plus-one, **zero plus-two**. A separate native
C++ comparison decodes all 402 main tensors: **zero different codes and zero
different FP16 scale blocks** between PQ2 and PTQ. All 464 remaining tensor
stored spans, tokenizer metadata, Hadamard metadata and architecture metadata
also match. This establishes stored inference-weight equivalence for these files,
including MTP; it does not guarantee identical floating-point kernel outputs.

If the PQ2 scale bytes are incorrectly treated as 2-bit weights, they yield
242,976,534 apparent code-3 values. This demonstrates a possible counting trap,
but does not reproduce the reported 229,633,025 count or establish the cause of
that upstream report. We have not scanned its exact original artifact, which is
not identified there by a SHA256; no general claim about all PQ2 checkpoints follows.
[Full comparison](data/research/pq2-0-mtp-20261003/packing-full-comparison.json),
[independent histogram and sample](data/research/pq2-0-mtp-20261003/packing-audit.json).

Reproduce the full comparison using the already downloaded model cache and a
local C++ compiler; it does not run inference, download models or change backends:

```bash
python3 -B data/research/pq2-0-mtp-20261003/audit-packing.py \
  --model-dir "$PWD" --output /tmp/bonsai27/packing-recheck.json
```

### Why the prefill comparison changed

The earlier answer overstated the relevance of the model card's PQ2 prefill lead.
Merged [PR #214](https://github.com/PrismML-Eng/llama.cpp/pull/214) removes divergent
PTQ unpacking and enables wider MMQ tiles. Its author reports PTQ pp512 rising
from 630 to 1304 tok/s on RTX 4070, approximately matching PQ2. A later reviewer
reports PTQ pp512 1881 to 3962 on RTX 5090. These are external kernel-development
measurements, not local tests. Our pinned source `f13265492743209a0fbedc2a2781af3f5f0eab13`
contains the branch-free loader and wide tile entries. The old short-prompt table
therefore cannot establish a persistent PQ2 speed advantage on this backend.
This is a concrete reason the local near-parity is plausible, rather than evidence
of reversed labels; it is not a diagnosis of the measured 4.15% difference.

For long context and MTP, numerical equivalence still needs care: upstream
[PR #285](https://github.com/PrismML-Eng/llama.cpp/pull/285) reports prompt-dependent
changes between draft-on and draft-off greedy continuations as Flash Attention
batching changes its reduction split. Its tiered host KV proposal is not part of
our CUDA0-only configuration. Neither allocating a large window nor matching one
continuation proves accuracy across that entire window.

### Further optimization candidates without changing model precision

Static review of the pinned PTQ source identifies these candidates, **not measured
speedups**. No runtime or kernel has been changed.

| Priority | Candidate | Reason and exactness condition |
| --- | --- | --- |
| 1, prefill | Fuse Hadamard and MMQ-compatible activation quantization; reuse prepared activations across compatible consumers | Existing FWHT/Q8 fusion is gated to MMVQ, so it excludes large prefill batches. Shared MMQ Q8 reuse exists for DGX Spark/Q1/Q2/PQ2 but excludes our SM120/PTQ profile. Preserve transform/quantizer arithmetic, padding/layout, alias safety and graph lifetimes; first trace whether repeated preparation is material. |
| 2, prefill | Reuse the scale already fetched by the PTQ tile unpacker | Word 6 contains the FP16 scale; a separate loop loads scale entries again. Populate the same tile with identical scale conversion and synchronization, avoiding new divergent work or shared-memory races. |
| 3, decode | Reuse activation loads across the fused main/gate dot products | The `has_gate` path calls the block-dot helper twice with the same activations. Combine independent row sets while preserving each output's integer dots, fold order, FMA and invariant epilogue. Increased registers may cancel any benefit. |
| 4, graph preparation | Precompute validated consumer/alias relationships | FWHT eligibility scans all later nodes for each candidate. Cache only for a stable graph generation with correct invalidation. CUDA graph replay already avoids this work, limiting the possible gain. |
| 5, host overhead | Skip DGX-only consumer-map construction on SM120 | `gb10_shared_q8_consumer_counts` is built before the capture/replay conditional on every call; all consumers are gated to DGX Spark (1210), while our GPU is 1200. Architecture gating can preserve exactly the same GPU work. Measure the host-cost share before expecting a material speedup. |

Wide tiles, branch-free unpacking, exact activation sums, eligible FWHT/Q8 fusion
and CUDA graph reuse are already present. Turning off the invariant flag or
changing reduction association is not an established quality-free optimization:
the source itself documents changed near-tie continuations with the faster
four-accumulator epilogue. Retain precision and current arithmetic when testing
memory/launch optimizations. Before implementation, profile the 30k workload to
separate PTQ matmul from attention, recurrent state and preparation. Then validate
exact affected-kernel outputs and representative logits, followed by identified
interleaved timing and fresh API/vision/coding QA. No percentage improvement is
promised without measurement.
[Source locations and review](data/research/pq2-0-mtp-20261003/kernel-review.json).

## PTQ1_0 versus PQ2_0: research and local test — October 3, 2026

“PQ1” here means the existing **PTQ1_0 MTP Lean** profile. PQ2_0 is
an optional image; PTQ1_0 remains the default.

### Representation, quality and external performance

Both packs represent ternary weights with FP16 scales per 128 weights and the
same Hadamard rotation. PTQ1_0 uses dense trits; PQ2_0 uses 2-bit slots.
Consequently, extra storage does not imply extra numerical precision. Inference:
packing alone should not improve coding, recall or prose; different kernels can
still produce numerical differences. Official base sizes are 5.95 versus 7.21 GB.
Prism reports these short-prompt results, **not measurements on this host**:

| GPU | PTQ1_0 PP512 tok/s | PQ2_0 PP512 tok/s | PTQ1_0 TG128 tok/s | PQ2_0 TG128 tok/s |
| --- | ---: | ---: | ---: | ---: |
| RTX 5090 | 1805 | 3893 | 120.5 | 129.9 |
| RTX 4090 | 1645 | 3124 | 91.1 | 81.2 |
| H100 | 1237 | 2830 | 86.9 | 113.9 |

Cheap unpacking favors PQ2 prefill; lower weight traffic can favor PTQ1 decode.
PP512 is not a 30k-context server/MTP benchmark. The common backbone advertises
262K context. Its coding average is 89.42 and BFCL v3 tool calling 74.92; these
are model-level results, not a packing comparison or a repository-agent evaluation.
[Primary model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf).
No controlled packing-specific long-context, agentic coding or German prose
comparison was found in the reviewed primary sources.

### Local 30,000-token measurements

Three fresh PQ2 containers used the identical request, native Blackwell executable
and flags as the earlier PTQ baseline, apart from the model path. Defaults remain
batch 2048 / microbatch 512, context 32000, q8_0 main/draft KV, Flash Attention,
MTP depth 2 and medium thinking. The file has exactly 30000 tokenizer tokens;
the rendered chat has 30009. All requests had zero cached tokens and completed
normally with reasoning, 450 completion tokens and a correct risk summary.

| Profile | Prefill runs (s) | Mean ± sample SD (s) | Mean tok/s | Global VRAM peak (MiB) |
| --- | --- | --- | ---: | ---: |
| Earlier PTQ1_0 baseline | 54.965 / 54.468 / 56.193 | 55.209 ± 0.888 | 543.65 | 10715 |
| New PQ2_0 MTP | 56.608 / 58.929 / 56.959 | 57.499 ± 1.251 | 522.07 | 11398 |

PQ2 took **4.15% longer** in this workload. The baseline was recorded earlier,
not rerun or interleaved. VRAM is global GPU usage, includes other processes,
and sampling can miss brief peaks; the observed difference is 683 MiB, not an
isolated model allocation. This is insufficient to diagnose the cause or claim a
general PQ2 slowdown. Long prefill also contains attention/recurrent-state work,
so packing throughput alone cannot predict end-to-end performance.
[Measurements and identities](data/research/pq2-0-mtp-20261003/measurements.json).

The selected 7,557,178,656-byte model is pinned to revision
`5edf5f552d45e40b81f0255a8bb443af35850722`, SHA256
`78df4279d40ebebdccfd2dae0e9d4847afee52e94f48f3542ae9437220dbd847`.
The [upstream card](https://huggingface.co/decent-jawfish/bonsai-2-27b-mtp)
identifies an unchanged official PQ2 body with an added MTP head. Our GGUF
inventory independently confirms identical tokenizer metadata and byte-identical
stored spans for all 15 MTP tensors compared with PTQ1_0 Lean. Both have 866
tensors; 402 main tensors change packing type 143 to 142. The subsequent full
codec audit now verifies every main weight code and FP16 scale, plus all other tensor spans and runtime metadata (see recheck above).
[Inventory](data/research/pq2-0-mtp-20261003/gguf-inventory.json).

The image `localhost/bonsai2-27b-pq2-0:1.5.1` is built locally from a dirty
immutable development snapshot, with model pins in its labels/receipt and all
four backend profiles retained. PTQ image tags are preserved. Offline regressions,
real CUDA runtime checks and fresh 16k/8k API QA passed, including 15k recall,
CPU BF16 vision and three coding tasks in the restricted Python container.
All 18 final audit checks passed. An earlier audit rejected the PQ hash because
it only recognized PTQ; it is retained as failed evidence. The updated audit
checks shared known pins and rejects unknown/mismatched profiles.
[Fresh validation](data/research/pq2-0-mtp-20261003/validation.json).
These functional probes do not establish comparative agent quality or fluency.

### Long context, agent loops and language

Prism documents malformed or looping tool calls as a model limitation. It also
reports cache misses when earlier reasoning or tool calls are re-rendered; omitting
past reasoning from subsequent requests is its workaround. Output limits include
thinking, and exhaustion can appear as poor non-English output. Medium effort
shortens reasoning; the packing change does not fix these behaviors.
[Known issues](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/b072e1d3b35a0a630cece372c2127528e0994386/KNOWN_ISSUES.md).

Prefix reuse, checkpoint restoration of hybrid state, RAM prompt-cache storage
and cache shifting are distinct mechanisms. The official cache guide recommends
checking actual processed-token counts and checkpoint logs, with a full-prefill
control; its suggested speculative-disabled experiment cannot simply be assumed
to work with our MTP settings. We retain the authorized runtime defaults.
[Prompt-cache guide](https://github.com/PrismML-Eng/Bonsai-demo/blob/main/PROMPT-CACHE.md).

For this 12 GB notebook and long prompts, retain PTQ1_0 and default batches:
the measured PQ2 profile provides no prefill benefit and less observed memory
headroom. For agent workloads, the next useful experiment is an identified
multi-turn tool conversation measuring cached versus processed tokens and
end-to-end latency, followed by interleaved packing runs. No format-specific
advantage in long-context accuracy, agent reliability or expression is established.


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
