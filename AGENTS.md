# Working in this repository

## Purpose and runtime requirements

This project runs Bonsai 2 27B PTQ1_0 MTP Lean with BF16 vision through a
Bonsai-compatible llama-server in rootless Podman. Preserve these defaults:

- All language-model weights, embeddings, MTP weights, KV caches, and recurrent
  state run on CUDA0. Do not introduce automatic CPU offloading.
- The separate BF16 vision encoder/projector runs on CPU and system RAM through
  `--no-mmproj-offload`.
- MTP uses `draft-mtp` with `n_max=2`; Flash Attention is enabled; main and draft
  K/V cache types are `q8_0`.
- Context defaults to 16,384 tokens. The API model ID is `bonsai2-27b`, and the
  host API is published only on localhost, port 8080 by default.
- Native Linux uses NVIDIA CDI. WSL2 uses `/dev/dxg` and a read-only mount of
  `/usr/lib/wsl`. No sudo rights are available; host drivers are prerequisites.
- Bundled backends support compute capabilities 8.6/8.9 and 12.0. Only WSL2 with
  an RTX 5070 Ti Laptop GPU has been runtime-tested here.

## Layout and workflow

- `prepare.sh`: download pinned models and backend bundles, verify SHA256, and
  extract backends. Do not build the image here.
- `build.sh`: verify extracted backend files and build the image using
  `Containerfile`. Determine the image version through `tools/version.sh` and
  semrel, then tag the successful build with its SemVer version and `latest`.
  Keep image creation in this script.
- `image_push.sh`: publish the last built image to the project GHCR package
  under its version and `latest` tags. Prefer Podman and support Docker fallback.
  Prompt for a token unless `--token` was supplied, use password-stdin, and clean
  up temporary credential files. Never commit credentials.
- `run.sh`: validate startup settings, prepare GPU access, and start the container.
- `data/models/download.sh`: shared pinned model metadata and locked, resumable,
  SHA256-verified downloads for missing model files. Keep pins shared with
  `prepare.sh`. Existing nonempty readable model files are reused.
- `data/gpu/detect.sh`: detect CUDA device 0 through the bundled libcuda probe,
  with nvidia-smi as a fallback; map
  8.6/8.9 to ampere-ada and 12.0 to blackwell. An explicit BONSAI_GPU_BACKEND
  overrides detection. Fail clearly on query errors or unsupported GPUs.
- `entrypoint.sh`: detect the backend, validate settings, download missing models into the writable
  cache, and assemble readable, commented
  argument groups before replacing itself with llama-server using `exec`.
- `download_models.sh`: download missing models on the host with the shared helper.
- `BONSAI_MODEL_DIR`: writable persistent model cache, defaulting to the caller’s
  current directory; resolve relative paths before changing directories. GGUF,
  partial-download, and model lock files are excluded from Git.
- `data/backends/<backend>/`: downloaded archives and runtime binaries/libraries.
  Put additional project-supplied build/runtime dependencies in suitable `data/`
  subdirectories. Do not recreate a top-level `vendor/` directory.
- `data/research/`: retained research metadata and source inputs.
- `tools/`: all project-supplied build tooling, including the pinned semrel
  installer, binary cache, license, and version policy. Host GPU runtime
  dependencies remain under `data/`. Do not install build tools globally.
- `assets/`: committed assets, including `fairyland-unicorns-1080p.png`.
- `tests/`: test scripts. The single top-level request example is
  `simple_request.sh`, which sends the existing image asset and prints indented
  JSON; it must not generate an image.
- `results/`: local test evidence, excluded from Git.
- Use `/tmp/bonsai27/` for temporary work. Build scripts honor the standard
  `TMPDIR` variable, defaulting to that directory.

## Configuration and readability

Write documentation, code comments, prompts, and user-facing script messages in
English. Keep shell scripts readable: consistent indentation, descriptive names,
short functions, commented option groups, and Bash arrays for argument lists.
Quote variables and preserve the boundaries of forwarded arguments.

Project-specific environment variables use the `BONSAI_` prefix:
`BONSAI_CTX_SIZE`, `BONSAI_REASONING_EFFORT`, `BONSAI_MODEL_DIR`, `BONSAI_PORT`, and
`BONSAI_BASE_URL`, `BONSAI_IMAGE`, `BONSAI_GHCR_USER`, and
`BONSAI_PUSH_ENGINE`. Container settings also include `BONSAI_GPU_BACKEND`,
`BONSAI_MODEL`, and `BONSAI_MMPROJ`. Keep standard external variables such as
`TMPDIR`, `LD_LIBRARY_PATH`, and `GGML_CUDA_BATCH_INVARIANT` under their official
names.

Bonsai 2's template accepts reasoning values `low`, `medium`, and `xhigh`.
The project default is `medium`; the model's official default is `xhigh`.
`low` may behave like `xhigh`, and `high` is invalid. Document the accepted values
in the startup script comments. Verify model-specific changes against official
model documentation and the pinned backend, not generic llama.cpp assumptions.

## Image versioning

Use the pinned semrel binary through `tools/version.sh`; do not implement a
second commit parser or hardcode the llama-server commit as the image version.
The wrapper normalizes annotated tags in a temporary snapshot because the
pinned tool compares tag hashes against commit hashes. Original Git refs must
remain unchanged. Version calculation is local, rejects shallow history, and
uses reachable stable SemVer tags. Build both the version and `latest` tags.
Use `tools/tag-release.sh` for explicitly requested local release tagging from
a clean built image; never move published release tags.
Keep Git tagging and publication disabled for builds; use `image_push.sh` for
authorized registry publication. Determine the push version from the built
image label, not newly committed but unbuilt changes. Test push logic with
`tests/test-image-push.py`; Docker fallback needs separate storage or an import.
Run `tests/test-version.sh` when changing versioning or build-tool behavior.
Run `tests/test-model-download.sh` when changing model downloads or cache paths.
Run `tests/test-gpu-backend.sh` when changing backend detection.
`BONSAI_IMAGE` pins a runtime image; its default is the last successful local
build through `localhost/bonsai2-27b:latest`.

## Python: never create bytecode caches

Do not create `__pycache__` directories or `.pyc` files anywhere in this project.
Run Python with `python3 -B` or `PYTHONDONTWRITEBYTECODE=1`. Keep
`sys.dont_write_bytecode = True` before other imports in the test entry points,
so invoking them through ordinary `python3` also disables import caching.
Do not use `py_compile` or `compileall`: they explicitly write bytecode even when
ordinary import caching is disabled. For syntax checks use `ast.parse` with
`python3 -B`; use `bash -n` for shell scripts.

## Validation and documentation

Run checks appropriate to the change. For runtime changes, build through
`./build.sh`, then use the actual OpenAI-compatible API to validate behavior.
Use outside-sandbox access when needed and authorized by the active session.
Do not install host drivers or rely on sudo.

The API tests are `tests/test-api.py`, `tests/test-vision.py`, and
`tests/test-coding.py`. The API test supports `BONSAI_BASE_URL` and
`BONSAI_CTX_SIZE`; the other two currently use port 8080. The long-context test
requires at least a 16k window. Execute generated code only in the existing
restricted Python container setup.

`tests/qa.py` audits saved evidence, including a server log and an earlier 8k
`/props` response. Passing that audit does not prove a fresh runtime test passed.
Clearly distinguish recorded measurements, new measurements, and untested
platforms. Do not present external benchmarks as measurements from this host.

Preserve pinned download revisions, checksums, and upstream license files.
Do not modify verified upstream bundle contents just to make a check pass.
Update `README.md` after workflow or configuration changes; keep model/backend
research and measured evidence in `RECHERCHE.md` current. Both are English.

## Commits

After completing requested work and updating the documentation, create a commit.
Use an English Conventional Commit subject compatible with semantic-release,
for example `feat: add GPU inference container (by Codex)`. Choose the type
that describes the change (`feat`, `fix`, `docs`, `refactor`, or `chore`).
End the complete commit message with the exact attribution `(by Codex)`;
if a body is included, put the attribution at the end of that body.
Inspect staged changes before committing and exclude downloaded binaries,
models, bytecode caches, credentials, and local test outputs.
