# Repository audit and implementation plan

Audit date: 2026-09-30. Audited source: `845d89edac88094f65009d874b243d20024cf7ac`.
The audit findings below are historical. Implementation status and fresh
validation are recorded in the following section; remaining hardware and registry
publication checks are explicitly pending. P1 means address before the next published
release; P2 means follow-up reliability or maintainability work.

## Implementation status (2026-09-30)

Items 1–9 have been implemented with regression checks. Item 10 is complete for
available WSL2 hardware and documentation, with other deployment rows pending.
The detailed original findings below explain why the changes were needed.

| Item | Implementation and validation |
| --- | --- |
| 1 | Atomic build receipt; exact image selection/import; clean/source/tag checks; remote conflict and rollback guards; exact manifest promotion and digest verification. Isolated engine and registry fixtures pass. Live new publication is pending. |
| 2 | Shared project lock; committed source/backend snapshots; final label verification; contradictory tag aliases rejected; semrel retained. Version/release/tag/snapshot/concurrency fixtures pass. |
| 3 | Wrapper configures GPU access; container selects CUDA device 0 and validates overrides. CUDA detection/override fixtures and WSL2 inference pass. |
| 4 | Disappearing lock retry; supervised download workers; configurable waits/timeouts; conservative stale-lock policy. Signal/Range/timeout fixtures and real container stop/read-only-cache checks pass. |
| 5 | Offline verified archive reuse; clean staged extraction; exact inventory verification; coordinated replacement and recovery. Tiny bundle preparation and snapshot fixtures pass. |
| 6 | Explicit --verify/--repair; old file preserved until verified replacement; complete partial-file reuse and Range fallback. Cache/transfer fixtures pass. |
| 7 | Context 512–262144, host port 1–65535, bounded decimal parsing, allowed reasoning/backend values validated before GPU work. Configuration fixtures and real 8k/16k API checks pass. |
| 8 | Common endpoint/deadline handling; per-suite identity and model hashes; checksum-bound logs; reject mixed/stale/empty evidence; trusted coding completion and timeout cleanup; simple-request fixtures. Fresh 18/18 QA audit and live vision/coding tests pass. |
| 9 | Pinned Ubuntu digest; dependency/package/input inventory in receipt; documented refresh procedure and official driver references. Both bundled runtimes pass dependency checks. Apt resolution is inventoried, not frozen; no vulnerability scan claimed. |
| 10 | WSL2 cold pinned-model download, warm-cache offline API and full suite, actual 16k/8k API, CPU vision, GPU LLM, MTP/FA/q8 evidence, and coding completed. Native/CDI, actual Ada/shared Windows mounts, Desktop, Hyper-V guest, and post-publication anonymous pull remain pending. |

Development runtime evidence: `results/runs/20260930T152810Z-495703/`, image ID
`ce3dda017fddc4c8e421bb698873c060aa1da4038bee96bdcfb4283975c591e2`, explicitly
marked dirty. Fresh model files downloaded into the ignored validation cache
were SHA256-verified. The suite recorded 18 passing QA checks, 23 coding
assertions, two vision shapes, the full unicorn image, and a related 8k context
run. Final clean builds are recorded separately by `results/last-build.json`.
Final clean verification also passed: version **1.4.0**, local tag `v1.4.0`,
source `de4b8edccb4940c9d005f89a77ae199fa142c5a8`, image
`f39b06302ab6b70df04157cc8729a121eb4adf31f0dec52af31701b376f81c6b`.
Evidence `results/runs/20260930T154315Z-510298/` passed 18/18 QA checks and all
23 coding assertions, with actual 16k/8k, vision, MTP/FA/q8/GPU-only allocation
checks. Both backend dependencies, real download stop/read-only-cache behavior,
restricted coding failure handling, and warm-cache offline API startup passed.
The successful build receipt records the exact release identity and 109 package
rows. The code and available-host acceptance work are complete; the environment
and live-publication checks below remain open.

### Outstanding environment checks

- [ ] Actual RTX 4070 Ti Super inference and restart/download behavior on the
  reported Windows/shared filesystem.
- [ ] Native Linux/CDI and actual sm86/sm89 GPU inference.
- [ ] Docker Desktop GPU inference; engine fallback/import already covered by
  isolated fixtures.
- [ ] Independently GPU-provisioned Hyper-V guest, only when such a host is
  available. Stock Podman Desktop Hyper-V is not claimed as supported.
- [ ] Live authorized publication and anonymous pull of both new GHCR tags;
  current registry guards/promotion are covered by isolated tests. Serialize
  independent publishers because registry preflight is not a global transaction.

## Scope and results

Reviewed startup, GPU detection, download/cache locking, packaged libraries,
preparation, image builds, semrel/version tags, release creation, registry
publication, request/QA scripts, and their documentation.

The earlier fixes are present: CUDA detection without `nvidia-smi` inside the
container, a CUDA access check before model downloads, directory-based model
locks instead of `flock`, and release baseline recovery from published metadata.
The current semrel result is **1.3.1**. Reusing a version for documentation-only
changes or an unchanged release baseline is expected; the remaining concern is
allowing different image contents to replace the same published version.

Fresh checks performed for this audit:

| Check | Result |
| --- | --- |
| Syntax of tracked Bash and Python files | Passed; Python parsed without writing bytecode |
| `tests/test-version.sh` | Passed |
| `tests/test-create-release.sh` | Passed |
| `tests/test-release-tag.sh` | Passed |
| `tests/test-model-download.sh` | Passed |
| `tests/test-gpu-backend.sh` | Passed |
| `tests/test-cuda-probe.sh` | Passed |
| `tests/test-image-push.py` | Passed |
| `tests/test-published-release.py` | Passed |
| Both backend archive SHA256 pins | Matched |
| Both extracted backend `SHA256SUMS` manifests | Passed |
| `tests/test-runtime.sh` against the existing local image | Both backend dependency checks and failure before downloads without GPU access passed |

The checked image was `localhost/bonsai2-27b:latest`, version **1.3.1**, source
revision matching the audited commit, with `io.bonsai.git.dirty=false` and image
ID `fc5533d63d04e5dcdd963e5a8bac94208b35af02af34a0733b8f8448ed872c20`.
No image was rebuilt or published and no project release tag was changed.
Additional fault reproductions used temporary repositories and mocked commands
under `/tmp/bonsai27/audit/`.

### Packaged libraries and platform boundary

Both bundles contain CUDA runtime, cuBLAS/cuBLASLt, ggml/llama, multimodal, and
OpenMP libraries, together with upstream license files. The final image adds
C/C++ runtime dependencies, download tools, CA certificates, and the CUDA probe.
No unresolved shared-library dependency was found with this host's WSL driver
mounted. `libcuda.so.1` remains a host-driver dependency; copying a stub or an
unrelated host driver into the image would not provide GPU passthrough.

Resolving dependencies does **not** validate CUDA kernels on another GPU,
minimum driver versions, or every dynamically loaded execution path. This audit
did not rerun inference, vision quality, coding generation, throughput, or a
vulnerability scan. Previous API measurements remain historical evidence.
Native Linux/CDI, actual Ampere/Ada inference, Docker Desktop, and the reported
Windows/shared filesystem still need real environment tests. The previously
researched Hyper-V limitation remains documented in `RECHERCHE.md`; this audit
does not establish support for a stock Podman Desktop Hyper-V GPU machine.

## P1 — Before the next published release

### 1. Protect published versions and select the correct image store

- [x] Harden `image_push.sh` before its first registry mutation.

**Finding (code inspection):** only the local image's version is validated.
Dirty builds, wrong source/revision labels, and a different image under an
already published version are not rejected. The Docker path imports from Podman
only when Docker lacks `localhost/bonsai2-27b:latest`; an older copy already in
Docker can therefore be published instead of the latest Podman build.

**Changes:** record the successful build's immutable image ID, source revision,
version, and engine in a local ignored receipt. Validate clean/source/revision
labels and their release-tag correspondence. Select or import that exact build,
not whichever engine happens to own a `latest` alias. Before pushing, inspect
the remote version: allow an identical publication and reject a conflicting
one. Compare registry manifest digests using a consistent transport format;
local image IDs and registry manifest digests are not interchangeable. Prevent
accidental rollback of `latest`; document recovery after a partial push. Verify
both remote tags after publication for Docker as well as Podman. Preserve hidden
token prompting, the requested `--token` option, password-stdin, and cleanup.

**Acceptance:** extend `tests/test-image-push.py` for dirty/wrong-project images,
conflicting published versions, idempotent retries, stale Docker storage,
`latest` rollback, and failure after the version push. No conflicting case may
mutate the registry. Live publication remains a separate authorized action.

### 2. Make release/build provenance consistent across all entry points

- [x] Align `create_realease.sh`, `build.sh`, `tools/tag-release.sh`, and
  `tools/version.sh` around one release validation policy.

**Finding (reproduced):** `tools/tag-release.sh` accepts an existing bare `1.2.0`
tag at one commit and creates `v1.2.0` at a different commit. The newer release
script checks both spellings, but the older helper does not.

**Finding (code inspection):** only release creation takes a lock. Its initial
cleanliness/HEAD snapshot precedes that lock; `build.sh` later reads the live
working tree independently. Concurrent edits or builds can invalidate recorded
provenance. A build may also assign a stable version to uncommitted contents.

**Changes:** reject contradictory SemVer tag aliases consistently. Establish
the source snapshot after acquiring the release lock and build release contents
from an immutable snapshot. Include verified backend artifact identities in
the build record. Coordinate scripts that mutate release/build state; a lock
alone cannot prevent an editor from modifying the working tree. After the
build, verify image version/revision/cleanliness against the intended release
before declaring success. Keep development builds possible but ineligible for
release publication. Continue to use semrel exclusively for version analysis;
do not force a bump for every commit. Preserve existing release refs and rollback
only a newly created, unpublished tag when the build fails.

**Acceptance:** extend version/release/tag fixtures with conflicting aliases,
concurrent invocations, HEAD/worktree changes during a delayed build, and
mismatched final labels. Original published tags must never move. Confirm a
`fix` or `feat` after a tagged baseline produces the expected patch/minor bump.

### 3. Use the container's CUDA device for backend selection

- [x] Remove duplicate GPU-generation selection from `run.sh`; share validation
  between `data/gpu/detect.sh` and `entrypoint.sh`.

**Finding (code inspection):** direct container starts can detect CUDA without
`nvidia-smi`, but `run.sh` still requires it, selects its first reported GPU,
and passes that backend explicitly. This can disagree with CUDA-visible device
ordering. An explicit backend currently checks driver availability but not
whether its kernels match the detected compute capability.

**Changes:** let `run.sh` configure GPU access and let the container select its
backend from CUDA device 0. Forward an optional `BONSAI_GPU_BACKEND` override
and validate it against actual capability before downloads. Keep the allowed
values `blackwell` (12.0) and `ampere-ada` (8.6/8.9). Explain conflicting overrides
and unsupported GPUs without introducing CPU fallback. Update the README's
first-GPU wording and distinguish wrapper settings from container settings.

**Acceptance:** fixtures for CUDA access without `nvidia-smi`, differing host
and CUDA device order, whitespace in fallback output, supported overrides,
wrong overrides, and unsupported capabilities. Follow with real WSL2 API tests
and an RTX 4070 Ti Super test when that machine is available.

### 4. Finish download locking and shutdown handling

- [x] Improve `data/models/download.sh` and startup download process handling.

**Finding (reproduced with injected interleaving):** if `mkdir` fails because a
lock exists and its owner removes the directory before the subsequent `-d`
check, the waiter exits with a misleading write-access error. The writable
test cache reproduced exit status 2 without a download attempt.

**Additional gap (not runtime-reproduced):** signal traps live in the downloader
subshell while the entrypoint waits for it. Clean cancellation during `curl`
and container PID 1 signal forwarding need dedicated tests. Forced shutdown can
leave a directory lock, and waiters have a fixed 600-second deadline.

**Changes:** retry disappearance of a contended lock while still bounding real
write failures. Explicitly manage download children and forward stop signals;
clean up only an owned lock after the child stops. Define configurable bounded
wait/network behavior and report which cache is blocked. Retain resumable
`.part` files and checksum-before-rename. Provide conservative stale-lock
recovery instructions; elapsed time or a PID from another container is not
proof that a lock can be deleted. Document that old `flock`-based and new
directory-lock images must not download concurrently into the same cache.

**Acceptance:** extend `tests/test-model-download.sh` for the release race,
TERM/INT during a slow download, a killed owner, read-only mounts, a slow active
owner, failed resume, and checksum failure. Test actual `podman stop` during a
controlled download. Repeat on the user's affected shared filesystem; keep the
existing ENOSYS fixture and never put the shared-cache lock in container-local
`/tmp`.

## P2 — Reliability, reproducibility, and validation

### 5. Prepare backend bundles without exposing partial state

- [x] Refactor archive preparation and build input verification.

**Finding (code inspection):** `prepare.sh` resumes directly into the archive
path and extracts over an existing runtime directory. Preparation is not
serialized against another preparation/build. Manifest verification checks
listed files but does not reject leftover extra files, which `Containerfile`
copies into the image.

**Changes:** reuse a verified cached archive without network access; download
into a staging file, verify the pin, and extract into a clean temporary
directory. Verify manifest completeness, file types, and intended contents.
Publish the prepared tree with coordinated readers so a build cannot see a
partial replacement. Preserve verified upstream contents and licenses.

**Acceptance:** tests for offline reuse, interrupted/corrupt downloads, failed
extraction, unexpected old files, and concurrent prepare/build. Failure must
leave the last verified runtime usable; successful builds must consume exactly
the verified set.

### 6. Offer explicit verification of an existing model cache

- [x] Add an opt-in cache verification/repair workflow to the shared downloader
  and document it in `download_models.sh` and the README.

**Finding (reproduced; existing documented policy):** a readable nonempty file
containing `not a GGUF file` is reused successfully without hashing. This is a
startup-speed choice, not a regression in the new download integrity check.

**Changes:** preserve fast normal reuse but offer full verification against the
pinned model/projector SHA256 values. Clearly distinguish custom model paths
from pinned contents. Repair only on explicit request under the same lock;
do not silently delete user-supplied models. Cover a complete `.part` file and
HTTP servers refusing Range requests in the resume policy.

**Acceptance:** corrupt/truncated cache rejection in verification mode, custom
file handling, valid offline reuse, and interrupted repair without losing the
last good file.

### 7. Bound numeric input and validate configuration before GPU work

- [x] Harden context and port validation in `run.sh` and `entrypoint.sh`.

**Finding (reproduced):** `BONSAI_CTX_SIZE=18446744073709552128` passes the current
minimum check because Bash arithmetic wraps. `BONSAI_PORT` lacks wrapper-side
validation. Entry-point GPU detection happens before syntax validation.

**Changes:** validate decimal length/range before arithmetic, normalize leading
zeros, and define a documented upper bound supported by the pinned model and
backend. Do not treat that bound as a promise that every GPU has enough VRAM.
Validate host ports in 1–65535 and reject invalid settings before downloads or
GPU initialization. Keep reasoning values `low`, `medium`, and `xhigh`.

**Acceptance:** zero, negatives, whitespace, leading zeros, enormous integers,
boundary values, invalid reasoning, and invalid ports. Valid 8k/16k settings
must still reach the API unchanged.

### 8. Tie QA evidence to one image and make failures trustworthy

- [x] Refactor API, vision, coding, and saved-evidence tests under `tests/`.

**Finding (code inspection):** only `test-api.py` supports `BONSAI_BASE_URL`;
vision/coding hardcode port 8080. QA combines fixed-path artifacts from different
runs, including a separate 8k response. The health retry loop uses a 1,800-second
per-call timeout. Coding success uses the generated program's exit code alone;
an early `sys.exit(0)` can bypass appended assertions. A timed-out Podman client
also needs explicit container cleanup rather than relying on `--rm`.

**Changes:** share endpoint/timeout handling, use a bounded readiness deadline,
and create per-run evidence with image ID, source revision, context, GPU,
backend, model hashes, and timestamps. Link the separate 8k/16k runs explicitly.
Reject missing, empty, stale, or mixed evidence. Check completion of the trusted
coding harness as well as exit status, and clean up named test containers on
timeout in `finally`. Keep generated code isolated without network access.
Treat coding checks as functional samples, not a security proof. Add focused
fixtures for `simple_request.sh` host/port defaults and its existing image use.

**Acceptance:** a wrong-answer response, empty summaries, mixed image evidence,
early successful exit, and a timed-out generated program must fail reliably.
Run all live API tests on a nondefault port. Fresh logs must substantiate GPU-only
LLM allocation, CPU vision, Flash Attention, both q8 caches, and MTP n_max=2;
where exposed, retain draft/acceptance counters from actual requests.

### 9. Record reproducible dependency and driver evidence

- [x] Pin and inventory release inputs without altering upstream bundles.

**Finding (code inspection):** model/backend/semrel artifacts are pinned, but
both Ubuntu base stages and installed apt packages are mutable. The two GPU
bundles use different backend commits and CUDA versions. Passing `ldd` on this
host does not establish minimum driver support on all target machines.

**Changes:** pin the base image digest and define a deliberate refresh policy.
Record apt package versions, bundle/archive hashes, backend commits, CUDA
versions, retained licenses, and the final image digest in release evidence.
Verify documented driver requirements against the appropriate official NVIDIA
release documentation and actual target drivers. Review image contents for
unneeded tools only after proving the full runtime dependency set; keep the
CPU backend required by vision. If adding scanners or inventory tooling, keep
project-supplied tools under `tools/` and runtime dependencies under `data/`.

**Acceptance:** a release manifest identifies every input; a base refresh is
reviewable. Both backend dependency checks pass after refresh. Do not describe
an unscanned image as vulnerability-free or dependency resolution as inference
validation.

### 10. Complete a small, explicit deployment matrix

- [ ] Validate the supported routes and refresh README/RECHERCHE evidence.

**Test rows:** WSL2/Blackwell (regression baseline), native Linux/CDI on an
Ampere or Ada GPU, RTX 4070 Ti Super on the reported shared model mount, and
Docker Desktop with its supported GPU path. Treat an independently configured
Hyper-V Linux guest as conditional and untested until GPU access is actually
available; do not promise to solve missing passthrough by adding image files.

**For each available row:** cold cache download, warm-cache offline startup,
stop/restart during download, automatic and explicit backend selection, 16k API
request, a separately recorded smaller context, vision request, coding checks,
and logged GPU/CPU allocation. Record generation and prompt throughput separately.
Confirm anonymous GHCR pull after an authorized publication, with both version
and `latest` resolving to the intended release. Mark unavailable rows as pending.

**Documentation changes:** keep a concise matrix of tested versus packaged or
conditional support, allowed values/defaults for every startup variable, and
copyable Desktop/direct-engine commands. Explain download/loading/readiness
states and safe cache recovery. Cross-link one canonical release workflow;
retain `create_realease.sh` for compatibility with the requested filename.

## Implementation order and completion criteria

1. Fix release safety and image selection (1–2), with isolated regression tests.
2. Fix startup selection and download lifecycle (3–4), then input validation (7).
3. Harden backend/cache preparation (5–6) and test evidence (8).
4. Record build inputs and execute available platform tests (9–10).
5. Update README and RECHERCHE with actual results and remaining untested rows;
   commit each cohesive change using Conventional Commits ending `(by Codex)`.

Runtime changes must be built through `build.sh` and validated against the real
OpenAI-compatible API. Retain GPU-only LLM/MTP/cache allocation, CPU BF16 vision,
MTP n_max=2, Flash Attention, q8_0 caches, and the 16k default throughout. A plan
item is complete only when its regression checks and applicable runtime checks
pass; unavailable hardware must remain an explicit limitation.
