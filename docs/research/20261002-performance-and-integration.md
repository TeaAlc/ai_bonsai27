# 20261002 Performance And Integration

[Current research index](../../RECHERCHE.md) · [Current operation](../../README.md)

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
committed [measurement record](../../data/research/blackwell-mtp-20261002/measurements.json)
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
[reasoning comparison](../../data/research/blackwell-mtp-20261002/reasoning-comparison.json)
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
[DFlash2 reasoning record](../../data/research/blackwell-mtp-20261002/dflash2-reasoning.json)
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

The committed [validation record](../../data/research/blackwell-32000-20261002/validation.json)
identifies the exact development image used for measurement and binds saved
API, runtime, quality, and memory evidence by SHA256. Raw evidence remains
under `results/blackwell-32000-medium-validation/`, excluded from Git.
Historical thinking-disabled comparisons are explicitly labeled in README;
Ada reasoning-medium performance has not been remeasured here.
