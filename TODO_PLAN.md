# Repository optimization and acceptance plan

Status: **implementation and runtime acceptance complete; final clean-build verification pending**. Date: 2026-10-02.
Reviewed baseline: `33013d2818ddff8cf197d397666b63154ca2490d`.
The earlier audit remains available as
[the September 30 audit](docs/history/repository-audit-20260930.md).
This plan covers the October 2 cleanup findings and their combined acceptance;
it does not mark earlier hardware/publication checks as completed.

## Objective and boundaries

Reduce duplicated maintenance, make benchmark evidence reliable and portable,
and separate current operation from historical research. Preserve the current
inference configuration and the existing user-facing commands. Implement the
work in small, independently reviewable steps, followed by one integrated
acceptance against a newly built image.

The current clean local image is
`sha256:12a4ea5443376e64d67eb576b9cf9c97ea1c467d21d827a7cd978e962fae8cc7`.
The recorded 32,000-token single run measured 62.77 decode tokens/s, 9,516 MiB
peak total GPU memory, and 12,800 retokenized thinking tokens. This is historical
baseline evidence, **not a performance threshold or a fresh acceptance run**.

### Requirements that must remain true

- MTP `draft-mtp`, maximum depth 2, on Ampere, Ada, and Blackwell by default.
- Exact default context: 32,000 tokens; configurable through BONSAI_CTX_SIZE,
  with bounds 512–262144 checked before Bash arithmetic. Preserve normalization
  of leading zeros and rejection of oversized values.
- Main weights, embeddings, MTP weights, KV caches and recurrent state stay on
  CUDA0. Flash Attention and main/draft q8_0 K/V remain enabled. No CPU fallback.
- BF16 vision remains on CPU/RAM through `--no-mmproj-offload`.
- Actual CUDA access is checked before downloads even with a backend override.
  Native Linux/CDI and WSL2 driver injection retain their existing behavior.
- Native SM89 and SM120 backends remain in the standard image alongside the
  original Ampere/Ada and Blackwell bundles. Selection rules remain unchanged.
- Performance benchmarks use explicit thinking and reasoning effort `medium`.
  Keep ten exchanges / twenty messages and distinguish cumulative usage from
  unique context, decode speed from wall throughput, and estimated thinking
  tokens from actual API counters. Functional QA keeps its task-specific settings.
- Missing measurements remain null. Thinking tokens are already part of API
  completion usage; never add them to completion tokens again.
- Preserve source/compiler/model pins, licenses, published bundle bytes,
  checksum verification, directory-based model locks, and immutable snapshots.
- Keep semrel, existing release/publication policy, atomic build receipts and
  the shared project lock. Do not move Git tags or implicitly publish images.
- Preserve existing root commands, environment names, caller-relative model
  paths, forwarded argument boundaries, and localhost API publication.
- Do not remove retained research, model caches, user containers, or imported
  repository copies. Retention/deletion is outside this cleanup.
- English documentation/messages; no Python bytecode caches; temporary work
  under /tmp/bonsai27/ with existing TMPDIR support; no global installs or sudo.

## Work order and dependencies

| Step | Work package | Dependencies | Completion gate |
| --- | --- | --- | --- |
| 0 | Capture baseline and protect interfaces | None | Baseline manifest and interface checklist saved |
| 1 | Robust, timezone-aware GPU telemetry | Step 0 | Malformed/unknown/timezone fixtures pass |
| 2 | Shared runtime defaults | Step 0 | Host, image and direct-start defaults agree |
| 3 | Extract the benchmark client | Steps 1–2 | Existing CLI and report compatibility preserved |
| 4 | Unified benchmark evidence and audit | Steps 1–3 | Success, failure and tamper cases audited |
| 5 | Shared native-backend build tooling | Step 0; Step 2 if defaults are consumed | Existing bundles and fresh compiler path verified |
| 6 | Documentation and active-plan consolidation | Steps 1–5 contracts settled | Current commands and historical links checked |
| 7 | Integrated offline and live acceptance | Steps 1–6 | Acceptance matrix and final clean image pass |

Steps 1 and 2 can be developed independently. Step 5 must not be mixed into
benchmark behavior changes. Freeze scripts and their imported helpers before
starting any long build or measurement; use owned immutable copies where
concurrent editing could otherwise change a running Bash script.

## Step 0 — Capture the baseline

- Record Git revision/cleanliness, image ID, build receipt, backend manifest
  identities and build.json records. Save them under an identified ignored
  results/optimization/<suite-id>/ directory.
- Retain immutable copies of baseline benchmark scripts/helpers as well as the
  image. Preserve actual request options so the future comparison does not
  silently use the candidate client for both sides.
- Inventory public CLI entry points and relevant configuration defaults.
  In particular retain image_build.sh, create_realease.sh, run.sh,
  simple_text_benchmark.sh and the current backend build wrappers.
- Record available GPU, driver, platform and model cache. Do not stop unrelated
  user containers or install host drivers.
- Before replacing a local latest image, retain the baseline by immutable image
  ID and protect it with a temporary local reference if required. Do not move
  versioned Git refs, publish registry tags, or prune images during acceptance.
- Verify the baseline is actually runnable; record unavailable hardware rather
  than inventing results. Use the same physical GPU and driver for comparisons.

Acceptance: the baseline can be selected independently of mutable latest and
all subsequent evidence states which immutable image it used.

## Step 1 — GPU memory parsing and portable timestamps

Affected code: tests/summarize-gpu-memory.py, tests/benchmark-backends.sh and
memory-summary fixtures. A separate small telemetry helper may live in tests/.

- Fix the reproduced AttributeError when a CSV row lacks memory.used. Validate
  field presence and type before parsing; handle empty rows, truncated rows,
  repeated headers, N/A, malformed numbers and unsupported counters.
- Record sampling start/end and an explicit timezone/UTC offset at acquisition.
  Prefer UTC-normalized sample timestamps. Never interpret copied telemetry
  according to the analysis machine's current local timezone.
- Preserve raw CSV bytes. For older timezone-less evidence require explicit
  recorded timezone information or a clearly identified legacy input option;
  ambiguous times must be reported, not silently guessed.
- Associate samples with the benchmark's explicit interval. Do not mix startup,
  quality probes, or shutdown into inference averages. Save startup peaks
  separately if useful and label their scope.
- Save GPU identity, total capacity, sample interval, usable/skipped samples,
  mean/minimum/peak global memory and before-start idle usage when available.
  Idle subtraction remains an approximation, not process-level accounting.
- No valid samples means null metrics and a diagnostic status. Real zero is
  distinct from missing data. Monitoring failure must not turn a valid inference
  into a claimed zero-VRAM result.

Acceptance fixtures: missing column; short row; empty/N/A/invalid field; repeated
header; zero usage; absent samples; samples outside the interval; copied data
with a different host timezone; explicit offset/DST handling. Verify the current
retained 32k telemetry still yields 9,516 MiB when its timezone is supplied.

## Step 2 — One shell-default source, checked image defaults

Proposed source: data/config.sh; integrate with data/gpu/settings.sh, run.sh,
entrypoint.sh and tests/benchmark-backends.sh.

- Put shared runtime fallback values and bounded validation policy in a small
  sourceable module. Resolve it relative to the script, not the caller's CWD.
- Preserve the current unset/empty-variable semantics, valid overrides, and
  separate reasoning policy: startup accepts low/medium/xhigh, while performance
  benchmarks explicitly use medium even if an endpoint has another default.
- Preserve caller-relative BONSAI_MODEL_DIR resolution before changing directory.
- Copy the configuration module into the image and its immutable build snapshot.
  Keep dependency loading explicit so direct Desktop starts work without host files.
- Keep Containerfile ENV visible and explicit for Desktop inspection. Validate
  its overlapping defaults against the common module through regression tests;
  do not add a fragile generated Containerfile or a second configuration parser.
- Keep MTP=2 common to all backend selections. Do not introduce a user-facing
  speculative-depth override or automatically choose a depth from benchmark results.
- Keep explicit 16k/8k QA contexts; those are test scenarios, not stale defaults.

Acceptance: no override gives 32000 in run.sh, image ENV, actual /props and
actual process arguments; valid overrides remain effective; invalid values fail
before GPU/download operations; common configuration is copied into snapshots
and present in direct-start images. Backend selection and CPU-vision fixtures
remain unchanged.

## Step 3 — A readable benchmark wrapper and Python client

Keep simple_text_benchmark.sh as the public command. Move its Python body into
one focused implementation under tests/, for example tests/text_benchmark.py.
Share only helpers with real reuse; do not create a general application framework.

- The Bash wrapper retains hostname/hostname:port validation, localhost:8080,
  BONSAI_BASE_URL precedence, BONSAI_BENCHMARK_RESULT, English messages, and
  python3 -B. Locate the module through an absolute project-relative path.
- Separate named Python functions for HTTP transport, template/token budgeting,
  response validation, cache/thinking metrics, and final report persistence.
- Keep thinking enabled at medium effort in template and chat requests, 4096
  completion cap, full visible-answer history and normal-stop requirements.
- Keep approximate 16k cumulative usage as a target, not a hard reasoning budget.
  Preserve explicit within_5_percent=false warnings for complete conversations
  outside the target. No automatic truncation to make accounting pass.
- Prefer real API thinking-token counters; otherwise use the server tokenizer
  and mark boundary uncertainty as an estimate. Unknown remains null, including
  incomplete aggregates. Preserve source and estimate fields per exchange.
- Preserve current flat JSON metrics and full-response file layout. Add schema
  metadata without breaking callers reading existing keys. Never overwrite
  another run's responses when a result filename is reused unintentionally.
- Persist reports atomically, including partial evidence on HTTP errors,
  missing reasoning, truncation and cancellation. Distinguish completed,
  failed, cancelled and timed-out states; do not infer success from file existence.
- Use bounded request/readiness timeouts and retain the conversation deadline.
  Follow normal KeyboardInterrupt/SIGTERM shutdown without swallowing errors.

Acceptance: current hostname/cache/token fixtures still pass; add tests for
missing/truncated reasoning, API counter preference, tokenizer failure, true
zero versus unknown, interruption after successful exchanges, atomic result
replacement and duplicate-output protection. Inspect emitted requests to verify
medium reasoning rather than trusting report labels.

## Step 4 — An identified benchmark evidence index

Keep this separate from tests/qa.py's existing 16k/8k functional QA envelope.
Reuse identity/transport primitives only where their semantics match. Do not
rewrite the QA evidence format as part of a benchmark refactor.

Proposed artifacts:

- benchmark-index.json: versioned schema, suite ID, run IDs, ordered repetitions,
  statuses and paths relative to the evidence directory.
- identity.json per run: actual image ID, image labels/source state, container ID,
  actual executable and argv, API /props/context, GPU capability/driver, effective
  settings and verified model/draft/projector identities where obtainable.
- Existing benchmark reports, raw responses, telemetry, memory summaries,
  untouched logs and quality reports, referenced by path and SHA256.
- A small benchmark audit command under tests/ which verifies the index and
  measurements without relying on mutable latest or the current working tree.

Implementation requirements:

- Capture setup identity before inference and finalized log/response checksums
  after completion. Publish final index updates atomically; retain a readable
  running/partial status if interrupted before finalization.
- Each repetition gets its own evidence directory. Containers and run identifiers
  must not be reused across repetitions or unrelated suites.
- Finalize evidence in cleanup on success and failure. Record primary failure,
  exit status and stage without allowing a cleanup error to replace the original
  failure. Stop only the monitor and container owned by this run.
- Failed/time-out/cancelled runs remain inspectable and are excluded from success
  averages. Unknown timing/cache/thinking/VRAM metrics stay null.
- Separate benchmark from subsequent quality status: valid timings do not imply
  the quality suite passed. A complete acceptance run requires both to pass.
- Require matching image/container/suite identity and explicit relationships for
  related quality results. Do not mix reports solely because paths look similar.
- Keep reports portable: relative paths, timezone metadata, schema version, and
  content hashes. Reject path traversal and references outside the evidence root.
- Legacy results remain intact. Add a documented legacy read/import path only
  if needed, mark it as legacy, and never fabricate missing provenance.
- Plain API-only simple_text_benchmark.sh runs can lack local engine/model
  inspection. Mark them as API-only; they cannot claim local image identity or
  satisfy the fully identified container acceptance gate.

Acceptance: reject altered response/log/telemetry, wrong image/container IDs,
stale timestamps, mixed suites, duplicate repetitions and escaped paths.
Reject incomplete evidence as acceptance while retaining its diagnostic value.
Recompute token-weighted cache hits, thinking totals, timing throughput and GPU
interval statistics; confirm they agree with recorded totals and known nulls.

## Step 5 — Shared native-backend tooling, separate pinned profiles

Proposed files: tools/backend-profiles.json plus common build, compile, package
and verify helpers. Keep tools/build-ada-backend.sh and
tools/build-blackwell-backend.sh as compatible thin entry points.

- Profiles hold each existing source revision/SHA256, compiler image digest,
  native architecture, required compiler flags and licenses. Preserve Ada
  88c4bc6... / 89-real and Blackwell f132654... / 120-real exactly.
- Move duplicated compilation/package/verification operations into common
  helpers. Pass a validated profile name; never interpolate arbitrary build
  commands from an environment variable or relax checksum checks.
- Preserve Blackwell --resume semantics, source re-verification, re-extraction,
  retained failed objects, immutable compiler-helper copies and logging. Preserve
  current Ada failure/cleanup behavior unless explicitly covered as a separate change.
- Snapshot the profile and every consumed helper before a long compile. Include
  them in build provenance/receipts where they become build inputs.
- Keep build.json and SHA256SUMS compatible with existing recorded runtimes.
  Verify shared compiler options for both profiles, including actual CMake
  architecture, CUDA, Flash Attention and CUDA Graphs. Ada currently has weaker
  checks than Blackwell; tighten it without modifying verified runtime bytes.
- First verify both existing inventories against the stricter profile contract.
  Missing historical metadata is a documented incompatibility to resolve;
  do not rewrite a build.json or manifest to make verification pass.
- Preserve CUDA preflight, WSL/CDI injection, project lock, staged installation,
  rollback/recovery and licenses. Source compilation remains separate from image creation.
- Preserve auto-inclusion and all image_build.sh flags and receipt fields used
  by image_push.sh. A refactor must not omit either specialized backend or
  confuse their architecture/source identities.
- Fresh compilation is not promised to produce identical bytes: apt versions
  are inventoried, not frozen. Compare pins, flags, required files, licenses and
  runtime behavior; never claim bit-for-bit reproducibility without proof.

Acceptance: both existing runtime inventories pass unmodified; negative tests
reject swapped profiles, altered source/compiler pins, incorrect CMake flags,
missing licenses and changed files. Snapshot tests cover profile/helper edits
mid-build. Run the common compiler path for a fresh Blackwell build when available;
Ada profile/packaging fixtures and inventory checks do not substitute for Ada
GPU inference. Record actual Ada/Linux/other-platform tests as pending if absent.

## Step 6 — Documentation and plan structure

- README: current defaults, supported prerequisites, quick start, mandatory and
  optional parameters, API/benchmark commands, current measurements, and links.
- docs/desktop.md, docs/releases.md, docs/validation.md: focused workflows;
  move long historical performance tables into a dedicated linked page.
- RECHERCHE.md becomes a current research summary and index. Move chronological
  sections into dated research pages under docs/research/, retaining original
  source citations, measurements, caveats and related data/research/ JSON.
- Add redirects/link maps for relocated headings referenced by existing documents.
  Do not silently replace historical measurements with current policy descriptions.
- Keep current cleanup TODOs separate from the archived September 30 audit and
  outstanding environment/publication checks. Update AGENTS.md and data/tools
  README files for actual new paths and the agreed evidence/configuration contracts.
- Check every local Markdown target and heading. Verify command examples refer
  to existing entry points and accepted environment values. Label hardware and
  benchmarks as measured, historical, fixture-only or unavailable.

Acceptance: README leads to a working Linux/WSL/direct-Desktop setup, a current
medium-reasoning 32000 benchmark, clear thinking-token estimation rules and VRAM
scope; historical citations/data and the old QA workflow remain reachable.

## Step 7 — Integrated acceptance

### Offline gate

Run syntax checks without bytecode creation, then the complete updated
`./tests/run-regressions.sh`. Add only tests which cover meaningful boundaries
and changed behavior; do not add tests that merely mirror implementation names.
All existing version/release/push/model-download/GPU/build-snapshot/QA fixtures
must remain green, together with the new configuration, benchmark-index,
telemetry/timezone and benchmark-client tests. Verify no credentials, downloaded
binaries/models, raw results or bytecode caches are staged.

### Build and available-host runtime gate

1. Verify all four retained runtime inventories and their profile/pin identities.
2. Build through `./image_build.sh` with both native source backends included.
   Check the receipt and actual image ENV/defaults, not just source text.
3. Run `./tests/test-runtime.sh` for dependency checks and missing-CUDA-before-
   download behavior. Retain override validation, no-driver and no-CPU-fallback
   fixtures.
4. Start an owned container using default settings with no context override.
   Prove /props and argv show 32000, draft-mtp depth 2, medium, q8_0, Flash
   Attention and CUDA0. Also test an explicit alternate context setting.
5. Run the actual default ten-exchange reasoning benchmark and its new evidence
   audit. Confirm all thinking/usage/cache/VRAM metrics and response checksums.
6. Run `tests/run-qa.sh` on owned 16k/8k containers and audit the fresh suite.
   Require the existing identified API/long-context checks, CPU vision fixtures
   and unicorn example, three restricted coding tasks/23 assertions, and GPU
   placement checks. A successful saved-evidence audit alone is not a live test.
7. Exercise failed/cancelled benchmark cleanup on a disposable owned container.
   Verify a partial index, correct status, released resources and untouched user
   containers. Use local HTTP fixtures for injected HTTP/tokenizer failures.
8. Commit reviewed code/docs in Conventional Commit format ending `(by Codex)`.
   Rebuild the final clean image and verify its receipt points to that commit.
   Test its default-context API and bind equivalence to previously tested runtime
   inputs; rerun affected live checks if runtime content changed.

### Performance and VRAM comparison gate

- Run each side with its immutable client/helper snapshot. Verify the effective
  template/chat options match and report any request/history differences.
- Compare the protected baseline and candidate with identical 32000 context,
  MTP=2, thinking medium, completion cap, questions, GPU and monitoring protocol.
- Run three fresh containers per image in alternating order, without concurrent
  GPU workloads. Record temperature, idle load and global VRAM, not only speed.
- Report per-run values and arithmetic means/sample spread for decode speed and
  wall time; cache totals remain token-weighted. Include thinking counts and
  response identity/output-length differences, if any.
- A mean decode decrease greater than 10% or unexplained peak-memory increase
  greater than 256 MiB triggers investigation and blocks acceptance until
  explained or corrected. These are practical review triggers, not statistical
  confidence claims. Repeated heavy competing load invalidates comparison.
- For unchanged runtime/configuration, expect semantic equality in deterministic
  functional cases. Different greedy text in batched verification is explicitly
  documented, not automatically treated as broad quality equivalence.
- Preserve low-load and single-run limitations; do not extrapolate to filled
  32k performance or another architecture. A full-window capacity/recall test is
  separate from this cleanup's performance acceptance.

### Acceptance matrix

| Area | Required evidence | Pass condition |
| --- | --- | --- |
| Interfaces/configuration | CLI fixtures, image ENV, actual /props/argv | Defaults/overrides compatible; exactly 32000 default |
| Inference placement | Fresh logs, real CUDA checks, QA | GPU-only LLM/MTP/cache; CPU BF16 vision; FA/q8_0 preserved |
| Thinking/accounting | Actual requests/responses and fixtures | Medium enabled; valid thinking counts/sources; no double counting |
| VRAM | Raw timezone-bound samples and recomputed summary | Malformed input safe; mean/peak interval correct; unknown stays null |
| Evidence | Index audit and negative fixtures | No stale/mixed/tampered data accepted; partial runs identifiable |
| Backend tooling | Pins, inventories, compiler flags, build/snapshot fixtures | Both native profiles retained; licenses/checks intact |
| Functional QA | Fresh identified 16k/8k API/vision/coding suite | All existing mandatory QA checks and 23 coding assertions pass |
| Performance | Three baseline plus three candidate runs | No unexplained regression beyond review triggers |
| Build/release/push | Existing fixture suites, receipt and final image | Semrel/publishable-image behavior preserved; no implicit publication |
| Documentation | Local link/example checks and status table | Current workflow clear; historical evidence preserved |

### Hardware and publication limits

Live acceptance is possible here on WSL2 with the RTX 5070 Ti Laptop GPU.
Native Linux/CDI, actual Ampere/Ada inference, Docker Desktop, and a separately
GPU-provisioned Hyper-V guest require those environments. Mark unavailable
rows **pending**, not passed. Stock Podman Desktop Hyper-V CUDA support is
not claimed. Registry logic is tested with fixtures; real publication and
anonymous pull remain separate explicitly authorized actions.

### Completion and recovery

Acceptance output is an identified results/optimization/<suite-id>/acceptance.json
listing each gate as passed, failed or pending with evidence references, image
IDs and observed limitations. Add a concise committed summary without raw data.
Update this plan's checklist and current documentation only after each gate
actually passes. If a gate fails, retain evidence, fix the isolated change and
repeat affected checks. The protected baseline image and existing verified
backends remain available for recovery; no rollback moves a published Git tag.

## Execution checklist

- [x] Baseline/interface capture complete.
- [x] Telemetry parser and explicit timezone contract implemented and tested.
- [x] Shared defaults and image consistency checks implemented and tested.
- [x] Benchmark Python module extracted with compatible public wrapper.
- [x] Identified success/failure evidence index and audit implemented and tested.
- [x] Shared native backend tooling and stricter Ada verification completed.
- [x] Documentation split with historical links preserved.
- [x] Complete offline regression suite passed.
- [x] Actual 32000 reasoning benchmark and fresh 16k/8k functional QA passed.
- [x] Alternating baseline/candidate performance and VRAM comparison completed.
- [ ] Final clean image, acceptance summary and Conventional Commit completed.
- [x] Unavailable hardware/publication rows explicitly recorded as pending.

## Execution record

Fresh evidence is under results/optimization/20261002-cleanup/acceptance.json;
the compact measurement is committed under
[data/research](data/research/repository-optimization-20261002/acceptance.json).
All offline fixtures, native Blackwell compilation, four runtime inventories,
missing-CUDA checks, six alternating comparisons, 18 functional QA checks,
23 coding assertions, corrected cancellation, and the final full benchmark
harness passed. Baseline/candidate means were 61.91/61.73 tokens/s and the
highest global memory was 9,562/9,583 MiB. The initial image-ID normalization
probe and failed cancellation attempt are retained as diagnostics, excluded
from performance averages. Unavailable environments remain explicitly pending.
The final clean image is built and checked after the implementation commit.
