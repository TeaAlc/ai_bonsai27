# PTQ1_0 optimization implementation and acceptance plan

Status: plan only, October 3, 2026. Kernel changes and the gates below have not
been executed. This plan builds on the [source review](../data/research/pq2-0-mtp-20261003/kernel-review.json)
and [complete packing comparison](../data/research/pq2-0-mtp-20261003/packing-full-comparison.json).

## 1. Objective and non-negotiable acceptance contract

Reduce PTQ1_0 prompt processing time, especially at long context, and reduce
decode overhead where possible. Preserve model quality, memory safety, progress
and compatibility on the project's Ampere SM86, Ada SM89 and Blackwell SM120
targets. Only Blackwell hardware is available for measurement. Ampere and Ada
are qualified through native compilation and explicit theoretical review; safe
shared optimizations should apply there without requiring unavailable hardware.
Blackwell timings are never presented as Ampere/Ada performance measurements.

The release policy is **zero tolerance for a quality regression, a memory safety
defect, a leak or a deadlock**. A faster candidate does not compensate for a
failure. Preserve the reference implementation as the fallback and leave an
unproven specialization disabled. Statistical average accuracy alone does not
satisfy the quality requirement: improvements on some tasks cannot hide losses
on others. A finite test corpus cannot prove behavior for every possible prompt;
the design therefore also needs explicit invariants, arithmetic equivalence and
reviewable ownership/dependency arguments.

Changes must retain:

- The pinned PTQ1_0 MTP Lean weights, tokenizer, chat template and BF16 projector.
- CUDA0 residency for all language weights, embeddings, MTP, KV and recurrent
  state; CPU BF16 vision; no automatic or tiered host offload.
- Context default exactly 32000; explicit medium reasoning; MTP draft maximum 2;
  Flash Attention; main/draft q8_0 K/V; batch/ubatch defaults 2048/512.
- Current invariant arithmetic. Do not obtain speed by lowering precision,
  omitting rotation/state operations, changing thinking effort, truncating input
  or completion, or turning off `GGML_CUDA_BATCH_INVARIANT`.
- Existing GPU access checks, model pins, published fallback bundles and licenses.

Required outcomes for each enabled architecture (executed model/tool/memory/progress
checks apply to Blackwell; Ampere/Ada require the corresponding reviewed contracts):

| Gate | Required result |
| --- | --- |
| Identity | Exact frozen reference/candidate build inputs, model hashes, actual GPU, executable and library inventories, arguments and request identities |
| Arithmetic | Blackwell: bit-identical differential results. Ampere/Ada: reviewed equality of operand bytes, exact operations/rounding and reduction order against their reference paths; zero introduced precision changes |
| Model behavior | Blackwell: zero token/logit differences under identical settings and no lost semantic case. Ampere/Ada: arithmetic equivalence plus preserved graph/state semantics; runtime quality remains unmeasured |
| Tool protocol | Same valid tool decisions/arguments/results; no new malformed JSON, missing call IDs, loops or erroneous finish reasons |
| Memory | Zero invalid accesses/races/uninitialized reads; no outstanding unowned resources or unbounded retained memory |
| Progress | Zero hangs or timeout regressions; every failure/cancellation reaches a defined cleanup or termination state |
| Performance | Blackwell: reproducible improvement without required-workload regression. Ampere/Ada: demonstrably removed work, bounded resources and conservative dispatch; actual throughput remains unmeasured |
| Coverage | Blackwell: runtime, quality, safety and performance gates. Ampere/Ada: native build, source/SASS/resource review, host tests and explicit arithmetic/ownership/progress proofs; compilation alone is insufficient |

If the reference is nondeterministic in a selected comparison, first identify
and isolate the cause. Do not replace exact comparisons with an arbitrary
tolerance to make a candidate pass. Record existing model/protocol failures;
keep them in the comparison and separate their remediation from optimization.
An existing memory safety defect blocks the affected experiment until it is
resolved separately; do not suppress it as baseline noise.

## 2. Freeze the baseline and make modifications reproducible

1. Record a clean source snapshot for each architecture, including source archive
   SHA256, compiler-image digest, CMake configuration, patch inventory, CUDA and
   driver versions for the available Blackwell device, image digest, executable
   and dependent-library hashes. Ampere/Ada hardware/driver fields remain
   explicitly unavailable; their compiler/target identities must still be exact. The
   existing Ada and Blackwell profiles use different upstream revisions; compare
   each candidate against its own architecture's exact reference. Aligning those
   revisions is a separate change with its own baseline/acceptance gates.
2. Verify the model hashes and GGUF type 143. The packing audit established that
   the selected PQ2 profile has the same decoded weights, but this optimization
   campaign uses PTQ1 as both reference and candidate.
3. Use immutable source/compiler-helper snapshots. The native builder currently
   re-extracts its verified upstream archive: editing temporary source files is
   not a reproducible build workflow. Add a reviewed, pinned patch-input mechanism
   or pin a source revision that contains the change. Bind base archive, ordered
   patch hashes, resulting tree identity and build configuration in provenance.
   Never alter a verified published bundle in place.
4. Extend compilation/packaging to a native SM86 profile if required. Today the
   source-profile tooling allowlists Ada and Blackwell; the published Ampere/Ada
   bundle provides SM86 support. A new Ampere source profile needs explicit
   allowlists, verification, packaging and selection tests before it can be used.
5. Build experimental images exclusively through `image_build.sh`, under separate
   PTQ candidate tags using a reviewed extension to that script. Keep working
   reference tags and runtimes available. Pin all runs by immutable image ID;
   copy each receipt into the experiment evidence directory.
6. Preserve reachable version history and semrel version calculation. Builds do
   not create release tags or publish images. Update native-build, packaging,
   snapshot, configuration and GPU-selection fixtures as affected.
7. Freeze benchmark clients, test corpus and auditors before runs. Do not edit
   their imports or test definitions while a run is active. A changed corpus gets
   a new identity and reruns both reference and candidate.

Baseline artifacts belong in `results/ptq-optimization/<campaign>/<architecture>/`.
Commit the plan, corpus/oracle definitions, source changes and compact research
summaries; exclude model files, compiler output, credentials and raw local results.
Use `/tmp/bonsai27/` and Python without bytecode for temporary work.

## 3. Architecture and workload matrix

| Target | Available evidence | Particular checks |
| --- | --- | --- |
| Ampere SM86 | Native compile and theoretical review; no device measurements | Supported instructions; resource bounds; ordinary stream dependencies; preserved arithmetic/layout; conservative crossover |
| Ada SM89 | Native compile and theoretical review; no device measurements | Same proof obligations plus existing matvec/MMQ dispatch and register/shared-memory contracts |
| Blackwell SM120 | Existing RTX 5070 Ti Laptop 12 GB | Full differential/model/safety tests; PDL, graph reuse, native code generation, memory envelope and clock/power variation |

This campaign does not depend on acquiring SM86/SM89 devices. Classify paths as
shared architecture-safe improvements or Blackwell-specific measured tuning.
An architecture-safe improvement can be enabled on Ampere/Ada after the review
package below passes. A new tile/occupancy/crossover value justified only by
Blackwell measurements stays SM120-only; preserve the older thresholds elsewhere.
Do not label any Ampere/Ada change as runtime-tested or measurably faster.

### Ampere/Ada theoretical qualification package

For **each** SM86 and SM89 specialization, attach these artifacts before enabling:

1. **Native reference/candidate builds:** compile all relevant template instances
   for the exact target with the same pinned compiler and flags. Build the server,
   kernel harness and fallback path. Compilation can run in the compiler container
   using the available Blackwell driver check; it does not execute SM86/SM89
   kernels or establish their runtime results. Inventory cubins/PTX and ensure
   the intended native images are present.
2. **Instruction and numerical review:** inspect generated PTX/SASS and compiler
   resource reports. Prove the same operand bytes and scale bits reach the same
   integer dots and ordered floating-point operations. Review rounding mode,
   FMA contraction, intermediate F16/F32 materialization, FTZ/fast-math options,
   signed/unsigned conversion and overflow bounds. Algebraic equality is not
   enough when floating-point association or a stored rounding boundary changes.
   Use exhaustive finite codec tests and host-reference layout/size tests, plus
   native code review; these support rather than replace the device semantics
   argument.
3. **Resources and layout:** derive global/shared-memory offsets for all threads,
   tiles and tails. Map writes to unique owners and prove all read locations are
   initialized. Review register count, spills, static/dynamic shared memory,
   launch bounds and alignment. Check capacity before launch using actual device
   properties at runtime; retain fallback when a bound is not met. Do not assume
   the Blackwell occupancy or shared-memory budget applies to older targets.
4. **Dependencies and forward progress:** annotate producer/reader edges, barriers
   and lifetime endpoints. Prove an acyclic wait graph; preserve the ordinary
   stream path for SM86/SM89. No SM90+ PDL, unsupported intrinsic, new global spin
   barrier or assumption of simultaneous CTA residency may enter those targets.
   Review every conditional/early exit against collective participation.
5. **Host/dispatch coverage:** exercise all capability/feature/resource/shape
   branches with synthetic property inputs in isolated host tests. This is unit
   testing of selection logic, never a fake GPU capability override for inference.
   Include feature off, unsupported shape, insufficient resources, capture/update,
   buffer reuse, allocation failure and fallback selection.
6. **Performance rationale:** identify work removed (identical quantizations,
   launches, reloads or host construction), and any extra registers, allocations,
   barriers or dispatch overhead. Retain existing geometry unless its safe benefit
   can be argued without hardware measurements. A lower operation count is not
   a promise of higher throughput; prefer the least intrusive shared change.
7. **Explicit review verdict:** record enable/reference-only per optimization and
   architecture, with assumptions, proof references and unresolved questions.
   Perform a separate skeptical review after implementation, tracing actual code
   and generated instances rather than accepting the author's intent. Any missing
   equivalence, memory or progress argument keeps that particular specialization
   on the reference path. Other proven shared optimizations can still apply.

Blackwell tests exercise the shared algorithm and buffer contracts, including
conservative host-dispatch configurations, but do not replace architecture review.
Use the words **theoretically reviewed, native-compiled, runtime-unmeasured** for
Ampere/Ada in the final report. Absolute behavior on unavailable hardware is not
experimentally established; retain correctness through equivalent operations and
conservative fallback rather than weakening acceptance to an accuracy tolerance.

Core context matrix distinguishes **configured window** from **occupied tokens**:

| Band | Window | Actual prompt/history occupancy | Purpose |
| --- | ---: | --- | --- |
| Short | 4096 and 32000 | 64–512 tokens | Launch overhead and short analysis/tool/code behavior |
| Medium | 8192 | Approximately 4096 tokens, with completion headroom | Dispatch changes and conversation reuse |
| Long | 16384 and 32000 | Approximately 12000–15000, then 26000 tokens | Recall, reasoning, tool history, repository tasks |
| Near limit | 32000 | 30000 file tokens; record actual rendered count | Full prefill, tails, admission and tight headroom |

Keep the existing 16k/8k QA checks and add the new matrix. A configured 32k window
with a 100-token prompt is not a long-context test. Count the actual rendered
prompt with the pinned server tokenizer. For near-limit tests, use bounded answers
that demonstrably fit the remaining window: the existing 30000-token file renders
to 30009 tokens and leaves 1991 tokens. Use 26000-token histories for tasks needing
the full 4096-token completion budget. Overflow or unfinished reasoning is a failed
test, not a fast completion.

Extended windows above 32000 are a separate qualification tier, only where the
unchanged all-CUDA q8_0 configuration fits. Fill the claimed occupancy and verify
completion headroom. Never silently lower KV precision or offload to make a tier
fit; mark unsupported resource envelopes explicitly.

## 4. Profile before changing kernel arithmetic or memory layout

Establish fresh reference measurements, not just the earlier 55.209-second
long-prompt result. Start with the existing 30000-token prompt, then real analysis,
tool-history and code-context fixtures.

Capture separate cold full prefill (`cache_prompt: false`) and warm/common-prefix
requests (`cache_prompt: true`) under the same checkpoint settings. Record actual
cached/processed counters and recurrent checkpoint restore events; do not infer
cache hits from elapsed time. Test exact repeats, appended turns, changed suffixes
and changed leading text. Client history must preserve normal tool messages and
exclude echoed historical reasoning consistently for both arms.

Use container-bundled, pinned profiling tools. Start with a timeline to identify:

- PTQ MMQ and small-batch matvec time and launch count;
- Hadamard transforms and activation quantization, including redundant consumers;
- Flash Attention, recurrent/GDN work and checkpoint/state copies;
- host graph preparation/capture/update versus graph replay;
- temporary allocations, transfers and synchronization gaps.

Then inspect only material kernels for register spills, achieved occupancy,
shared-memory bank conflicts, instruction mix and memory transactions. Profiling
can perturb scheduling; collect production timing again with instrumentation off.
Use the measured operation share as the upper bound on possible benefit.

Freeze a short written hypothesis for each experiment: affected shapes/path,
expected eliminated work, arithmetic invariant, ownership/dependency contract,
success metric and fallback. Reject speculative tuning without a testable cause.

## 5. Implementation sequence: one independently revertible change at a time

### A. Remove DGX-only host work on other architectures

Location: `ggml-cuda.cu`, `ggml_cuda_graph_evaluate_and_capture`, construction of
`gb10_shared_q8_consumer_counts` before the capture/replay conditional.

- Trace every read of the table. Construct it only if an enabled feature can
  consume it on the actual device. Current consumers require DGX Spark capability
  1210; project Blackwell is 1200. Keep the DGX path functional even though it is
  outside this campaign's supported device set.
- First implement architecture/feature gating, not a persistent cache. This
  avoids introducing mutable cross-request state or invalidation bugs.
- Prove unchanged GPU operations/dependencies for SM86/SM89 by guard/dataflow
  review; verify unchanged launch/output traces on SM120. Add fixture coverage for DGX conditions and disabled feature
  combinations so a false guard cannot remove required preparation.
- Measure host time and request latency separately. This does not establish a
  GPU matmul improvement and may be small for a single long prefill.

### B. Reuse the PTQ MMQ scale already loaded during unpacking

Location: `mmq-load-tiles.cuh`, `ggml_cuda_mmq_load_tiles_ptq1_0`.

- The existing branch-free trit loop must stay branch-free in its hot path. Word
  6 contains qh and the FP16 scale; the later scale loop reloads the scale.
- Derive the correspondence between loaded blocks and every `x_df` tile entry
  for all instantiated J/I/tile sizes, fallback rows and K iterations before
  writing code. Document unique writer and complete coverage for each entry.
- Preserve exact scale bits and FP16-to-F32 conversion; preserve the unpacked
  integer tile and multiplication/reduction ordering. Do not reinterpret the
  scale bits as weight codes or change alignment assumptions.
- Verify the fallback clamp, final partial tile, shared-memory offset calculations,
  non-overlapping stores and visibility at the existing consumer barrier. No
  lane-dependent early exit before a CTA-wide barrier.
- Compare old/new tile contents byte-for-byte in a focused harness before matmul
  tests. Run racecheck, initcheck and synccheck on Blackwell for each supported
  shape family; review SM86/SM89 tile ownership and barriers explicitly.
- On Blackwell, require a measured benefit. On Ampere/Ada, apply only after the
  numerical/layout/resource review proves safe scale reuse without an unsupported
  launch change or an unexplained resource increase; preserve their geometry.

### C. Reuse identical MMQ activation quantization across projections

Locations: `ggml-cuda.cu` shared-Q8 path and `mmq.cu` `external_q8` interface.

- Existing sharing is gated to DGX Spark and Q1/Q2/PQ2. Extend only after verifying
  PTQ MMQ's activation layout and each consumer's size/padding requirements.
- Build a compatibility key from graph generation, source/view identity and
  current data version, device, stream, weight/activation layout, shape/strides,
  padded K, quantizer configuration and consumer semantics. A pointer or shape
  alone is insufficient; allocator reuse can make stale data appear compatible.
- Share only immutable activations with exactly compatible consumers. Gate/RMS
  fused quantizers, different views, expert IDs, different devices or concurrent
  streams need separate handling; keep the existing path when not proven safe.
- Prefer reuse within one graph execution and one stream before any cross-stream
  sharing. Each execution computes its own activation data even on graph replay;
  replay may retain buffer storage but never stale quantized values.
- Calculate buffer size using the same allocator helper as the consumer, including
  tail/padding slack. Keep pooling within the reference memory envelope. Do not
  reuse a pool block until all consumers have finished reading it.
- Preserve each quantized byte and scale. Prove that the changed path removes
  repeated identical work rather than changes normalization or quantization.
- Test partially eligible consumer groups: an extra F32 reader or incompatible
  view must not lose its materialized input or accidentally consume packed bytes.

### D. Fuse Hadamard and MMQ activation quantization for large prefill

Locations: `ggml_cuda_try_fwht_q8`, `fwht.cu`, MMQ quantization/dispatch.

- Current fusion is limited to eligible MMVQ consumers. MMQ's layout is not an
  interchangeable copy of the small-batch PT layout: define a distinct validated
  output contract instead of passing an MMVQ buffer into MMQ.
- Preserve sign application, butterfly order, intermediate precision, quantizer
  block boundaries, scale calculation and rounding. A fused result must match the
  reference Hadamard-then-quantize bytes exactly, including half-way cases.
- Check all consumer uses through reshape/view aliases. If an F32 consumer still
  needs the output, either retain the F32 representation correctly or decline
  fusion before launching. Do not remove a live graph value.
- Retain the existing overlap guard. If input/signs overlap the output allocation,
  allocate an owned non-overlapping scratch buffer; one CTA must never overwrite
  input another CTA has not read. Track partial overlap, not just equal pointers.
- Explicitly check padded sizes and checked arithmetic before allocation. Keep
  all padded bytes read by downstream vector/tile loads initialized as reference.
- Begin with one consumer/one stream, then integrate with accepted sharing from C.
  Keep unsupported n/K/stride/batch cases on the reference path. Test dispatch
  borders as well as normal 512-token microbatches.

### E. Share activation loads in the fused main/gate matvec

Location: `mmvq-ptq1_0.cuh`, `has_gate` calls to `ptq1_0_pt_block_dot`.

- Treat primary and gate rows as independent dot products sharing the same
  activation loads. Preserve each int32 dot, exact activation-sum correction,
  fold sequence and FMA/multiply operations.
- Preserve bias/GLU application and the invariant warp epilogue. Do not replace
  it with the faster four-accumulator reduction: that changes floating-point
  association and is documented to alter near-tie continuations.
- Check register lifetime and spills with fused and unfused cases; keep existing
  launch bounds, shared-memory capacity checks and tail-row correctness until
  separate measured tuning proves a better equivalent configuration.
- Qualify the actual supported fusion-column counts; do not broaden a one-column
  assertion merely to make MTP verification use it. Additional column support is
  another independently tested change.

### F. Architecture tuning and optional graph-analysis caching

Only after A–E individually pass their applicable gates:

- Measure dispatch thresholds for 1/2/3/4/5/8/9 columns and normal prefill batches
  on Blackwell. Keep Ampere/Ada reference crossover/geometry unless the separate
  theoretical review supports a change. Preserve operation order in any geometry
  change; exact output identity on Blackwell and the architecture proof elsewhere
  are mandatory. Preserve the reference for resource/shape tails.
- Choose launch/tile specializations using actual resource limits. An SM120
  specialization must not leak instructions or launch attributes into SM86/SM89.
- If graph analysis remains material, cache a validated plan, not activation
  contents. Key it by a monotonic graph generation and full eligibility inputs;
  invalidate on topology, views, layout, device, stream and allocation changes.
  Bound cache entries and retained allocation bytes; destruction waits for replay
  ownership to finish. Mutable caches have a higher safety burden than A's guard.
- Benchmark combined changes as a new candidate; individual speedups cannot be
  added arithmetically or assumed to compose without a regression.

## 6. Kernel and numerical quality assurance

Implement a Blackwell differential harness that runs frozen-reference and
candidate kernels on byte-identical inputs. The SM86/SM89 builds carry the same
case definitions for compile/host-contract coverage and theoretical review; no
device execution is claimed there. The existing `test-backend-ops` CPU comparisons remain
required, but tolerance-based CPU agreement alone is not the acceptance oracle.

### Required input coverage

- Extract all real PTQ main-model projection shapes from the pinned GGUF; include
  embeddings/head consumers when their path is affected. Add MTP high-precision
  projection shapes and BF16 small-row dispatch interactions.
- Include K=128 multiples, the actual K=5120 and K=17408 families, large head
  shapes, minimum supported sizes and row counts immediately around CTA/tile
  boundaries. Invalid alignment/stride cases must use the established fallback
  or error path, never an undefined optimized load.
- Columns: 1, 2, 3, 4, 5, 8, 9, 16, 31, 32, 33, 127, 128, 129, 511, 512, 513
  and larger legal microbatches. The max+1 cases verify rejection/fallback when
  the server's configured batch capacity does not permit execution.
- Contiguous inputs, legitimate view/reshape aliases, different legal strides,
  mixed eligible/ineligible consumers, partial rows, non-square shapes and
  fallback tiles. Test actual allocation size and padded size separately.
- Adversarial trit byte patterns, qh tails, all legal trits, zero/tiny/large scales,
  activation extrema, zeros/signed zeros, alternating signs, cancellation and
  half-way quantization values. Handle non-finite/invalid data according to the
  reference contract rather than introducing unchecked conversions.
- Use real weight/activation snapshots plus at least 1000 frozen randomized
  valid cases per changed kernel specialization, and exhaustive codec/short-tail
  cases where feasible. Record seeds and actual instantiated-path coverage.

### Exact comparison chain

1. Compare Hadamard outputs when relevant; compare quantized bytes, scales,
   padding and unpacked shared-memory tile fixtures.
2. Compare changed matmul outputs as bits against the same-GPU reference. Check
   finite/non-finite classification explicitly. Compare recurrent state/KV at
   selected checkpoints if any changed path can influence their construction.
3. Feed identical token sequences with teacher forcing. Compare full next-token
   logits or their bitwise digest at every captured position, not just top-1 or
   top-k. Save full tensors only for a mismatch and diagnostic positions.
4. Run generation under fixed settings and compare token IDs, reasoning, visible
   output and deterministic tool transcripts. Ignore only explicitly identified
   nondeterministic metadata such as timing/request IDs, not substantive content.

Baseline and candidate need not produce identical bytes across different GPU
architectures. Executed exact comparisons are Blackwell candidate versus its
frozen Blackwell reference; SM86/SM89 equivalence is established by the separate
compile/semantics review, not by invented runtime results. Likewise, do not require MTP-on to match MTP-off where the
reference already differs; require candidate-on versus reference-on and
candidate-off versus reference-off independently.

Test graph capture/update/replay, PDL enabled/disabled where supported, invariant
mode and the normal fallback arithmetic. Alternate column counts in one process,
not just separate fresh processes. Diagnostic snapshots must not replace the
separate asynchronous safety tests or be used for performance timing.

## 7. Model-level corpus: analysis, tools and coding

Freeze prompts, planted facts, repositories, tool schemas/responses and trusted
oracles before implementation. Execute this model-level corpus on Blackwell;
Ampere/Ada receive the arithmetic/graph equivalence qualification described above. Instructions and harness messages are English.
Include explicit requests for German answers to check expression. Each fixture
has a reference outcome, token budget, expected finish condition and provenance.

Start with a 12-case smoke suite (four per major family) at short and long
occupancy after each change. Final acceptance uses at least:

| Family | Minimum scenarios | Required checks |
| --- | ---: | --- |
| Analysis | 12 | Exact factual/arithmetic claims, contradictions, chronology, source attribution, instructions and structured output |
| Tool calling | 12 | Valid schemas/arguments, routing, no unnecessary calls, multi-turn recovery, transcript integrity and bounded progress |
| Coding | 12 | Trusted hidden assertions, boundary cases, file-scope constraints and executable behavior |
| Coding agents | 8 | Inspect–edit–test–repair loops in a frozen small repository; final tests and exact allowed diff scope |

Run each scenario at short, medium, long and near-limit occupancy where its output
fits; document why any near-limit task uses a shorter answer instead of dropping
it silently. The baseline and candidate use exactly the same documents and task.

### Analysis cases

Place essential facts at the start, middle and end of realistic long documents.
Include distractors, similar identifiers, late corrections and facts that must be
combined across distant sections. Test numerical reconciliation and units,
dependency/risk analysis, evidence-backed conclusions, omitted information that
must remain unknown, and an instruction embedded in quoted task data. Use trusted
fact tables and explicit output schemas, not subjective impressions of a summary.
Add concise and detailed German answers with explicit completeness/style rules.

Check nonempty reasoning for thinking cases, correctness and nonempty visible
answers, no unsupported facts, no lost decisive evidence and normal completion.
Track reasoning tokens without double-counting completion usage. Exact unchanged
generation is the strongest preservation evidence; an LLM judge can triage
differences but cannot override an exactness or objective-test failure.

### Tool calling cases

Use deterministic local tool fixtures. Generated tool calls invoke an allowlisted
test tool runner, never arbitrary host commands or external services.

- Required, auto and named tool selection; a task that needs no tool.
- Nested objects, arrays, numbers, enums, required/optional fields and empty
  argument objects. Validate JSON against the actual schema and expected values.
- Multiple tool choices and multi-step dependent calls. Preserve call IDs and
  matching tool messages, then require the correct final answer.
- Not-found, recoverable tool error, malformed fixture response and an explicit
  correction; require sensible bounded recovery rather than repeated calls.
- Long history with similar old IDs and updated facts; detect stale argument use.
- Streaming tool-call fragments, cancellation mid-call, client reconnection and
  the following fresh request; validate the assembled transcript.
- A repeated-history/prefix case to test cache restoration and recurrent state;
  compare cached and uncached continuations under identical checkpoint settings.

Keep one valid leading system message as required by the template. Define a
maximum of eight tool actions for normal fixtures; label stress loops separately.
Detect repeated identical calls without new information and missing progress.
Record every intermediate call and argument, not just final success. Do not replay
reasoning into later history on one arm while omitting it on the other.

### Coding and agent cases

Retain existing prime/interval/bracket smoke tests, then add parsing, data
transformations, Unicode, large inputs, mutable-state bugs, exception behavior,
algorithmic boundaries and concurrency primitives in small trusted fixtures.
Long contexts include multiple files, distractor implementations and a distant
API contract; successful compilation alone is insufficient.

Agent tasks cover a bug spanning two files, an API change with callers, a failing
test requiring a repair, a configuration/schema migration and an irrelevant file
that must stay unchanged. Check final hidden tests, termination, allowed changed
files, forbidden dependency additions, unintended input mutation and hardcoded
fixture answers. A test failure returned by a tool is part of the conversation.

Execute generated code only through the restricted container mechanism used by
`tests/coding_runner.py`: no network or host credentials, limited resources,
owned processes and bounded execution. Add equivalent isolated fixture runners
for any new language before adding its generated programs to the corpus.

### Repetition and scoring

For deterministic acceptance, first repeat the baseline three times to establish
stability, then run three matched candidate repetitions per scenario/context.
Preserve temperature=0, supported seed settings, medium effort and fixed request
bytes. Use a 4096 completion cap for the new thinking campaign. Keep the existing
QA's deliberate nonthinking settings in their separate smoke checks.

Add three frozen seed pairs at the recommended thinking sampling settings as a
robustness tier. Seed equality alone is not proof of determinism; verify raw
generated behavior and probability/logit traces. Every previously passed paired
case must remain passed; no aggregate-score tradeoffs. Report known baseline
failures and all repetitions, including timeouts, without cherry-picking.

## 8. Memory ownership, graph lifetime and synchronization

Each change has a written ownership table: allocation owner, size computation,
writer, readers, stream/event dependencies, last use, graph ownership, normal
release, cancellation release and error release. Every introduced buffer/event/
graph/cache entry needs an explicit bounded lifetime.

Mandatory invariants:

- The activation compatibility key includes data version; no stale quantization
  across requests, context reuse, graph updates or allocator-address reuse.
- A shared buffer stays alive until all readers finish. Captured graph pointers
  remain valid until graph destruction/update and completion of outstanding
  replays. A CPU RAII scope ending is not by itself evidence of GPU completion.
- Respect the CUDA VMM scratch pool's stack discipline: release allocations in
  global reverse allocation order, including buffers owned by different feature
  lists. Do not independently free per-feature lists in a different order.
- Buffer size arithmetic is checked before multiplication/addition and padding;
  vector loads and last tiles cannot cross allocation boundaries. Initialize
  every location a consumer can read, including tails and padded rows.
- Use an acyclic producer–consumer dependency graph. Each wait has a reachable
  producer, correctly recorded event and defined stream ownership. No host lock
  is held while waiting for GPU completion if a completion path needs that lock.
- All participating CTA threads reach collective barriers. No early return or
  conditional barrier based on row/lane validity; mask loads/stores instead.
- PDL is architecture gated. It is available from compute capability 9.0, so
  SM86/SM89 use the ordinary supported dependency path. On SM120, preserve the
  required producer launch-completion signals and consumer dependency sync before
  any dependent read. Never assume concurrent residency for forward progress.
- Do not introduce device-wide synchronization or CPU waits inside graph capture.
  Do not replace proper stream dependencies with a broad synchronization that
  hides races in tests and penalizes runtime behavior.
- Decline an optimized path before mutating inputs/state or submitting unsafe
  work. After a CUDA memory error or potentially poisoned recurrent state, stop
  that request/context cleanly; do not retry on a fallback with corrupted state.

The [NVIDIA PDL guide](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/programmatic-dependent-launch.html)
defines producer/consumer signaling and device support. Review these rules against
the pinned CUDA toolkit as well as the runtime wrappers before implementation.

### Sanitizers and diagnostic builds

Use a pinned diagnostic compiler container compatible with the actual device;
retain release-like code generation with line information. Keep these images
separate from performance builds. Validate available command options against
the bundled toolkit rather than assuming the latest online CLI exists.

Run independently:

```text
compute-sanitizer --tool memcheck --leak-check full --error-exitcode 99 <harness>
compute-sanitizer --tool racecheck --error-exitcode 99 <harness>
compute-sanitizer --tool initcheck --error-exitcode 99 <harness>
compute-sanitizer --tool synccheck --error-exitcode 99 <harness>
```

Memcheck covers invalid accesses/leaks; racecheck covers shared-memory hazards;
initcheck covers uninitialized global reads; synccheck covers invalid collective
synchronization. They do not collectively prove the absence of every cross-stream
race or deadlock. Track allocations/dependencies directly, run asynchronous stress
and use an external watchdog. Do not use forced blocking launches as the sole
validation because serialization can hide races. Where supported, add memcheck's
stream-ordered allocation race tracking. Its allocation padding does not cover
CUDA VMM allocations; use explicit canaries/unmapped guard ranges in a focused
VMM harness when compatible. Treat sanitizer internal OOM or unsupported tracing
as missing coverage, not a passing run. These distinctions follow the
[Compute Sanitizer documentation](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html).

Also run host ASan/UBSan builds for the changed ownership/size/graph code. Add
targeted host concurrency tests where a shared mutable cache is introduced.
Document unsupported sanitizer modes and supply an independent focused harness;
do not broadly suppress a report to qualify a candidate.

### Stress and fault injection

Run the following on Blackwell. For Ampere/Ada, mirror the corresponding
lifecycle/dependency scenarios in host tests and the theoretical review; do not
record sanitizer/soak runs as passed on hardware that was not available:

- 1000 alternating short requests and at least 100 long/near-limit requests in
  one server process, exercising different suffixes, batch tails and checkpoint
  restores. Include graph reuse and graph updates in both directions.
- A minimum four-hour mixed analysis/tool/coding soak, then a repeat cycle. Keep
  trusted completion checks active; successful HTTP status alone is insufficient.
- Twenty create/destroy cycles of the isolated backend/context harness, verifying
  that allocations, events and graph handles return to their initial ownership
  counts after destruction. Server restarts also check process/container cleanup.
- Multiple clients on the normal single-slot server: queued requests, disconnects,
  cancellations and streaming. Exercise internally legal multi-stream and
  multi-sequence paths in the focused backend harness without changing production
  defaults. Assert no state/output contamination between requests.
- Forced allocation failure at each new allocation site, graph capture/update
  failure, insufficient scratch/shared memory and injected launch failures.
  Reject before launch where possible; otherwise follow the defined cleanup and
  fail state. A subsequent fresh request must succeed if the CUDA context remains
  valid, or the process must terminate/restart cleanly if it is poisoned.
- SIGINT/SIGTERM, deadline expiry and client abort during prefill, tool-response
  ingestion and decode. Remove only owned test processes/containers. Keep model
  downloads and existing benchmark-worker stop/cleanup tests intact.

An external controller monitors heartbeats/progress and enforces a finite
per-case deadline fixed from baseline timings before candidate runs. Start with
the project's 600-second conversation deadline; declare instrumented-tool
deadlines separately to accommodate instrumentation. Preserve timeout evidence
and classify it as failed/incomplete. Increasing a timeout to hide a hang is not
acceptance. Use repeated runs without artificial synchronization to catch races.

### Leak and memory acceptance

Instrument live allocation bytes/counts, pool-reserved bytes, graph/cache entries,
event handles and held scratch buffers. Distinguish bounded reusable pool capacity
from lost ownership. Compare identical request cycles after warm-up: no new
unbounded high-water marks and no unexplained growth at equivalent idle states.
After context/graph destruction, live owned counters must return exactly to zero
apart from explicitly bounded process-global baseline resources.

Record host RSS and CUDA free-memory telemetry as corroboration, not ownership
proof. GPU telemetry is global on this host. The optimized default must fit the
same all-CUDA memory envelope and should not increase peak live scratch bytes;
any extra retained allocation blocks acceptance until the ownership and resource
budget are explicitly resolved. No hidden offload or retry allocation loophole.

## 9. Performance acceptance after all quality/safety gates pass

On Blackwell, use at least five paired, alternating reference/candidate rounds,
changing the initial order between rounds. Ampere/Ada have no measured performance
acceptance table; attach the removed-work/resource rationale instead. Use fresh containers for cold
prefill and controlled same-process histories for cache/decode tests. Recheck model
selection, loaded backend, all-CUDA residency and complete normal answers.

Measure:

- Prompt processing seconds and processed tokens/s from actual server counters;
- time to first visible answer token, reasoning time and whole-request latency;
- decode tokens/s with identical generated-token workload where achievable;
- tool-step and full agent-task latency, cache-hit rate and reprocessed tokens;
- live/peak scratch memory and global VRAM, host overhead, clock/power/temperature;
- MTP drafted/accepted counts and completion token counts, without confusing
  cumulative API usage with occupied context.

Do not report a kernel microbenchmark win as an end-to-end prefill win. Reject
contaminated runs under predeclared criteria and report them, then rerun the pair.
Keep instrumentation off. Add warmed, sustained notebook measurements to avoid
thermal/power transients masquerading as an architecture improvement.

Predeclare the minimum practical improvement after baseline variance is measured.
Require a confidence interval supporting an actual gain in the target workload;
if results are inconclusive, leave the path experimental. Quality has a zero-loss
margin. For other required performance workloads, investigate any repeated
slowdown and reject a specialization that causes a reproducible regression.
The same specialization need not win everywhere: dispatch to the unchanged
reference in losing architecture/shape regions.

## 10. Integration, release and evidence gates

| Stage | Deliverable | Stop condition |
| --- | --- | --- |
| G0 | Frozen references, Blackwell hardware, SM86/SM89 compile/review matrix, fixed corpus/oracles, safety contracts | Missing identity, unstable Blackwell reference, unaddressed safety bug |
| G1 | Profile and one scoped optimization hypothesis | No material removable work or no arithmetic/lifetime argument |
| G2 | Blackwell exact differential tests; Ampere/Ada native compile and equivalence/resource review | Any mismatch, unsupported-path break or missing theoretical proof |
| G3 | Blackwell sanitizers/stress; all-target host tests and ownership/progress arguments | Any defect or unresolved lifetime/synchronization argument |
| G4 | Blackwell full short/long analysis/tool/coding corpus and soaks | Any lost baseline pass, new divergence, hang or unbounded memory |
| G5 | Blackwell paired performance; Ampere/Ada removed-work/resource verdict | No credible Blackwell gain, regression, or unjustified older-target resource change |
| G6 | Combined-image QA, audited evidence and rollback verification | Wrong loaded path, combined regression, missing architecture qualification |

Run offline regression fixtures for changed build/profile/packaging/detection
contracts. Then build the actual image and run `tests/test-runtime.sh`, fresh
`tests/run-qa.sh`, explicit identified `tests/test-quality.py`, the new context
matrix and coding-agent suite against that exact image. `run-qa.sh` currently
covers 16k/8k and three simple coding tasks; it is not a substitute for the added
long-context/tool/agent coverage. Run the combined candidate's quality and safety
gates again even if each individual patch passed.

Every result carries campaign/case/seed/context/architecture IDs, UTC times,
reference/candidate source and image identities, executable/library/model hashes,
rendered token counts, flags, raw requests/responses/tool transcripts, selected
kernel path, quality outcomes, timings and resource diagnostics. Finalize checksum
manifests only after collectors stop. Audit rejects missing runs, unfinished
answers, wrong binaries, changed inputs and failed runs counted as completed.

Enable a specialization only for its measured Blackwell or theoretically
qualified Ampere/Ada device/shape/resource envelope;
retain the reference for all other cases. Verify fallback selection and local
rollback to the retained immutable reference image. Update README, validation
documentation and RECHERCHE with measured results and platform limits. Create
reviewable Conventional Commits ending `(by Codex)`. Publication/release tagging
remains a separate requested operation.

The final review package must include the arithmetic equivalence argument,
ownership table, producer/consumer dependency graph, actual path-coverage matrix,
all Blackwell quality differences (including zero), leak/soak/fault results and
interleaved performance evidence, plus the explicit SM86/SM89 proof/review
verdicts. An unresolved quality or safety question means the old implementation
remains active for that particular optimization/architecture.
