# Validation and recorded measurements

[Back to README](../README.md). Run project commands from the repository root.

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
## Historical WSL2 measurements

These recorded runs are separate from the current Ada comparison in
[RECHERCHE.md](../RECHERCHE.md). They are not fresh measurements of the current image.

The following performance figures were recorded before the original hardening work:

On **WSL2 with an RTX 5070 Ti Laptop GPU (12 GB)**, the 16k API test, both vision function tests, and all 23 coding assertions passed. The saved QA audit reported **14/14 checks passed**. A 15,009-token prompt was processed at **629 prompt tokens/s**. Three coding generations measured **60.5, 57.8, and 54.8 generated tokens/s**. These are individual measurements on this notebook, not guaranteed throughput elsewhere. MTP `n_max=2` was active; it is not necessarily the fastest setting for every prompt.

A separate vision quality check (`results/vision/quality-check.json`) sent a synthetic image (`results/vision/quality-check.png`) through `/v1/chat/completions`. The model correctly described a red square at the upper left and a blue circle at the lower right. This verifies a simple image request, not general photo understanding or OCR. These historical artifacts are local evidence, excluded from Git, and may not exist in another checkout.

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

## Current quality and speed checks

`python3 -B tests/test-quality.py` adds nine reasoning, instruction, JSON, and
tool-call probes. Use the same identified `BONSAI_TEST_*` settings as the other
API tests. Final performance verification uses `./simple_text_benchmark.sh`:
thinking is always enabled at explicit `medium` effort, with a 4096-token
completion cap. Missing reasoning or truncated answers fail validation. The
approximate 16k cumulative usage target may be exceeded by complete reasoning;
that deviation is recorded and warned about, rather than classified as failed
inference. Functional QA probes retain their own task-specific settings.

Repeated performance runs use `tests/benchmark-backends.sh`, with a 600-second
deadline per conversation and interval-filtered GPU memory summaries beside
the timestamped telemetry. Report total VRAM usage as a global measurement,
not a container allocation. All architectures default to MTP=2; alternative
draft strategies remain explicit experiments. Image, run.sh, and benchmark
defaults use exactly 32,000 context tokens; the owned long-context QA suite
still explicitly tests 16k/8k windows. Thinking-token totals prefer actual API
counters, with clearly labeled server-retokenization estimates as a fallback. Historical benchmarks with
thinking disabled are labeled and do not represent the current policy.
The October 1–2 Ada experiments and paired comparisons against the original
GHCR image are documented in [RECHERCHE.md](../RECHERCHE.md). Small regression
probes do not establish general model quality.

## Local integration verification — 2026-10-02

After importing the eight commits through `b875b68` from the supplied local
checkout, a fresh standard development image passed the complete offline
regression runner, syntax checks, real CUDA dependency/failure checks, and
18/18 identified API QA checks on the RTX 5070 Ti Laptop WSL2 host. Both vision
fixtures, all 23 coding assertions, the unicorn image request, and 16k/8k
context checks passed. The run used local image `1.5.0`, marked dirty during
integration; it is not a published release. Evidence:
`results/runs/20261002T143103Z-1520949/`. See the integration section in
[RECHERCHE.md](../RECHERCHE.md) for the image identity and measured throughput.
The supplied optional Ada runtime was inventory/provenance-verified locally;
its imported native-Linux performance results are separate host measurements.

## Portable benchmark evidence

`simple_text_benchmark.sh` delegates to `tests/text_benchmark.py` and produces
an API-only report. `tests/benchmark-backends.sh` starts owned fresh containers
and produces identified evidence under `run-<n>/`. Run
`python3 -B tests/benchmark_evidence.py audit PATH/run-1` to verify checksums,
identity, actual medium-reasoning requests, usage/cache/thinking totals,
decode throughput, interval VRAM, and separate quality probes. A partial or
failed index is diagnostic evidence and cannot satisfy acceptance.

GPU telemetry is acquired with TZ=UTC, recorded in telemetry.json, and scoped
to the conversation's measured interval. Memory includes the desktop and other
processes; one-second samples can miss brief peaks. Retained older CSV data
requires an explicit timezone argument to summarize-gpu-memory.py. Ambiguous
DST wall timestamps and missing counters are skipped rather than guessed.

The benchmark harness uses tests/benchmark-worker.sh to supervise its owned
timeout process group. A parent INT/TERM is forwarded immediately to the client;
cleanup stops the worker and monitor, removes only the owned container, and
finalizes a cancelled/partial index without replacing the primary exit status.
Direct-parent signal fixtures and a real container cancellation check cover the
nested-timeout escape discovered during cleanup acceptance.
