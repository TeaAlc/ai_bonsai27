# Bonsai 2 27B with Vision in Podman

Run **`Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf`**, a Bonsai 2 model based on Qwen3.8-27B, with a Bonsai-compatible `llama-server` and its OpenAI-compatible API. The language model, MTP head, KV caches, and recurrent state run on the NVIDIA GPU. The separate **BF16 vision encoder/projector runs on CPU and system RAM** to save VRAM.

The server uses MTP with `n_max=2`, Flash Attention, and `q8_0` K/V caches for both the main model and MTP draft. The default context window is **16,384 tokens**, configurable through `BONSAI_CTX_SIZE`. The API is published on localhost only.

## Requirements

- x86-64 Linux or WSL2, Bash, rootless Podman, Git, `curl`, `tar`, and `sha256sum`. Python 3 is needed for the tests. The coding test also pulls `python:3.12-slim` if it is not cached.
- A discrete NVIDIA GPU with compute capability **8.6 or 8.9** (the bundled Ampere/Ada backend) or **12.0** (Blackwell backend). Other compute capabilities are rejected by `run.sh`. The first GPU reported by `nvidia-smi` is selected as CUDA0.
- Enough free VRAM for the entire language model and its 16k runtime state. The tested 12 GB laptop GPU worked with this configuration. Approximately 8 GB of free VRAM is a practical starting point, but usage varies by host and workload. Memory pressure causes startup to fail; the configuration does not silently offload language-model weights to CPU.
- **Native Linux:** a working NVIDIA driver and NVIDIA Container Toolkit with CDI already configured, so `--device nvidia.com/gpu=all` works. Native Linux execution has not been tested in this project.
- **WSL2:** a working NVIDIA Windows driver, `/dev/dxg`, and `/usr/lib/wsl/lib/nvidia-smi`. `run.sh` mounts `/usr/lib/wsl` read-only so the container can access the host driver libraries. Do not install a separate Linux NVIDIA driver in WSL2 for this setup.

The scripts themselves do not require `sudo`. Host driver and CDI installation, if needed, are outside their scope.

## Prepare, build, and run

Run all commands below from the project directory inside Linux or WSL2.

### Start the published image

Prepare the model files, pull the image, and start the container with explicit
settings:

```bash
./prepare.sh
podman pull ghcr.io/teaalc/ai_bonsai27:latest
BONSAI_IMAGE=ghcr.io/teaalc/ai_bonsai27:latest \
BONSAI_CTX_SIZE=16384 \
BONSAI_REASONING_EFFORT=medium \
BONSAI_PORT=8080 \
./run.sh
```

**Required:** the GPU prerequisites above, both GGUF files in `models/`, an
available image, and an unused container name `bonsai2-27b`. To use the published
image, set `BONSAI_IMAGE` as shown; otherwise `run.sh` selects the local build.
The other three variables are optional and are shown explicitly for clarity.
GPU devices, driver mounts, model mounts, and backend selection are configured
automatically by `run.sh`; no additional GPU flags are needed.

The container starts in the background. Follow its startup logs, then check
readiness once model loading has completed:

```bash
podman logs -f bonsai2-27b
# Press Ctrl+C to stop following logs; the container keeps running.
curl --fail http://localhost:8080/health
./simple_request.sh localhost:8080
```

If you change `BONSAI_PORT`, use that port in the health check and request.
The model files are not included in the image; `prepare.sh` also downloads
backend bundles used for local builds.

### Build and start locally

```bash
./prepare.sh
./build.sh
./run.sh
```

No environment variables are mandatory for a local build: `run.sh` defaults to
`localhost/bonsai2-27b:latest`, a 16,384-token context, `medium` reasoning, and
host port `8080`.

`prepare.sh` downloads and SHA256-verifies the PTQ1_0 MTP Lean model, the official BF16 vision projector, and both CUDA backend bundles. The GGUF files stay in `models/`. Backend archives and extracted binaries live under `data/backends/{blackwell,ampere-ada}/`; research inputs live under `data/research/`. The downloads and image need several gigabytes of disk space.

`build.sh` installs the pinned `semrel` build tool locally under `tools/` if needed, calculates a version from Git history, checks the extracted backend files again, and builds `localhost/bonsai2-27b:<version>`. Every successful build produces both the calculated version tag and `localhost/bonsai2-27b:latest` from the same image; `run.sh` uses that alias by default. The calculated version is independent of the pinned llama-server backend commit. Only backend runtime files and `entrypoint.sh` are copied into the image; model files are mounted read-only when the container starts. The Bash entrypoint groups and comments model, server, GPU, MTP, and generation options, validates its settings before loading, and uses `exec` so the server receives container stop signals. Temporary build files use `/tmp/bonsai27` by default (or an explicitly set `TMPDIR`). See [data/README.md](data/README.md) for the directory layout and [RECHERCHE.md](RECHERCHE.md) for pinned revisions and checksums.

`run.sh` checks both GGUF files, detects WSL2 versus native Linux, selects the backend from the first GPU's compute capability, and starts the `bonsai2-27b` container in the background. Its default API base URL is **`http://127.0.0.1:8080/v1`**, with model ID **`bonsai2-27b`**. No API key is configured for local access.

To change the context size or host port, stop and remove the existing named container before starting another:

```bash
podman stop bonsai2-27b
podman rm bonsai2-27b
BONSAI_CTX_SIZE=32768 BONSAI_PORT=8081 ./run.sh
```

### Startup parameters

These are all environment variables read by `run.sh`:

| Variable | Default | Required? | Purpose |
| --- | --- | --- | --- |
| `BONSAI_CTX_SIZE` | `16384` | No | Context window in tokens; integer ≥ 512 |
| `BONSAI_REASONING_EFFORT` | `medium` | No | Reasoning effort: `low`, `medium`, or `xhigh` |
| `BONSAI_PORT` | `8080` | No | Available host TCP port, 1–65535; bound to localhost |
| `BONSAI_IMAGE` | `localhost/bonsai2-27b:latest` | For the GHCR image | Image to start, e.g. `ghcr.io/teaalc/ai_bonsai27:latest`; use a versioned tag to pin a build |

`BONSAI_CTX_SIZE` must be an integer of at least 512. `BONSAI_REASONING_EFFORT` accepts `low`, `medium`, or `xhigh` (default: `medium`). The official model default is `xhigh`; `medium` gives shorter reasoning. The model accepts `low` but it may behave much like `xhigh`; `high` is invalid and can cause an HTTP 500. Larger contexts need more VRAM; 32k has not been validated on the test notebook. See the [official model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) and [known issues](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/main/KNOWN_ISSUES.md).

Optional positional arguments passed to `run.sh` are forwarded to `llama-server`, for example `./run.sh --log-verbose`. Additional server flags can override the defaults, so preserve the GPU-only language-model and CPU vision settings. `BONSAI_BASE_URL` configures request scripts; it does not change the container binding. `BONSAI_GPU_BACKEND` is detected automatically; `BONSAI_MODEL` and `BONSAI_MMPROJ` are container entrypoint settings and are not forwarded from the host environment by `run.sh`. For status and logs, use `podman ps` and `podman logs -f bonsai2-27b`.

## Image versions and build tools

Versions are calculated by the pinned [greatliontech/semrel](https://github.com/greatliontech/semrel) tool. Without a release tag the first version is `1.0.0`. After a reachable stable release tag, `fix` and `perf` commits increment the patch version, `feat` increments the minor version, and breaking changes increment the major version. Documentation and maintenance commits alone retain the existing version. Both lightweight and annotated tags such as `v1.2.3` are supported.

```bash
./tools/version.sh                  # print the calculated version
./tests/test-version.sh             # check version rules using isolated Git fixtures
BONSAI_IMAGE=localhost/bonsai2-27b:1.0.0 ./run.sh
```

Version calculation uses committed history and locally available stable tags. Builds do not fetch, create Git tags, push, or publish a release. Use a full Git checkout with release tags; shallow checkouts are rejected. Repeated builds can reuse the same version until release history changes, and uncommitted changes do not influence semrel's version calculation. OCI labels record the calculated version and source commit; `io.bonsai.git.dirty` identifies builds that include uncommitted project changes. The `latest` alias tracks the last successful local build.

The pinned executable, cached download, installer, release policy, and tool license all live in [tools/](tools/README.md). Subsequent builds use the verified cached binary without downloading again. Git, Podman, and basic shell utilities remain host prerequisites. Downloaded tool files are excluded from Git and the container image.

## Publishing to GitHub Container Registry

The published image is available at
[ghcr.io/teaalc/ai_bonsai27](https://ghcr.io/teaalc/ai_bonsai27).
For a public package, pull the latest image without authentication:

```bash
podman pull ghcr.io/teaalc/ai_bonsai27:latest
```

For a private package, first log in with your GitHub username and a personal
access token (classic) with `read:packages` permission. Your account must have
read access to the package. Enter the token at the password prompt:

```bash
podman login ghcr.io --username YOUR_GITHUB_USERNAME
podman pull ghcr.io/teaalc/ai_bonsai27:latest
```

An `unauthorized` or `invalid username/password` error can mean the package is
private, credentials are missing or expired, or the account lacks access.
Run `podman login` again to replace stale credentials. Publication through
`image_push.sh` uses temporary credentials and does not log in future pulls.

To allow anonymous pulls, the package owner can open
[the package page](https://github.com/users/TeaAlc/packages/container/package/ai_bonsai27),
select **Package settings**, and set **Change visibility** to **Public**.
Package visibility is separate from repository visibility. See
[GitHub's package access documentation](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

`./image_push.sh` publishes the last successful local build as both
`ghcr.io/teaalc/ai_bonsai27:<version>` and
`ghcr.io/teaalc/ai_bonsai27:latest`. The version comes from the semrel-generated
label of the actual local image. Both remote tags use the same source image;
the version tag is pushed first, followed by `latest`.

```bash
./build.sh
./image_push.sh                          # ask for the token with hidden input
./image_push.sh --token 'YOUR_GHCR_TOKEN' # alternatively pass the token explicitly
```

The script prefers a working Podman with the local build and falls back to a
working Docker daemon. You can select an engine explicitly with
`BONSAI_PUSH_ENGINE=podman` or `BONSAI_PUSH_ENGINE=docker`. When Docker is selected
and only Podman holds the image, the script exports a temporary Docker archive
and loads it into Docker before publishing.

The login user defaults to `TeaAlc`; set `BONSAI_GHCR_USER` if your token belongs
to another authorized GitHub user. The token needs the `write:packages` scope.
For local CLI authentication, GitHub documents a personal access token
(classic). The OCI source label links the package to this project. See
[GitHub's Container Registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

Authentication uses `--password-stdin` and a temporary, restricted credential
configuration under `/tmp/bonsai27/`, removed when the script exits. Tokens are
never saved in the repository or permanent Podman/Docker configuration. Prefer
the hidden prompt if you want to keep the token out of shell history and process
arguments; an explicit `--token` parameter may be visible there.

GitHub initially creates packages as private. Access for other users depends on
the package's configured visibility and permissions. Once authorized, another
machine can run the published image with:

```bash
podman pull ghcr.io/teaalc/ai_bonsai27:latest
BONSAI_IMAGE=ghcr.io/teaalc/ai_bonsai27:latest ./run.sh
```

The two GGUF files and GPU host setup remain required. Run
`python3 -B tests/test-image-push.py` to check engine selection, prompt and token
parameter handling, Docker import, and failure behavior without publishing.

## API examples

Text chat:

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"bonsai2-27b","messages":[{"role":"user","content":"What is 19 + 23?"}],"max_tokens":128,"chat_template_kwargs":{"enable_thinking":false}}'
```

Vision uses the same endpoint and an OpenAI-style `image_url` content block. This standard-library Python example sends a local PNG as a data URL:

```python
import base64
import json
import urllib.request
from pathlib import Path

image = base64.b64encode(Path("image.png").read_bytes()).decode("ascii")
payload = {
    "model": "bonsai2-27b",
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": "Describe this image briefly."},
        {"type": "image_url", "image_url": {
            "url": "data:image/png;base64," + image
        }},
    ]}],
    "max_tokens": 256,
    "chat_template_kwargs": {"enable_thinking": False},
}
request = urllib.request.Request(
    "http://127.0.0.1:8080/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=600) as response:
    result = json.load(response)
print(result["choices"][0]["message"]["content"])
```

The short examples disable thinking so their output limits leave room for an answer. For reasoning requests, omit that override and provide a larger `max_tokens` allowance within the available context; reasoning tokens count toward that limit. PNG and JPEG data URLs are supported. `--no-mmproj-offload` keeps the BF16 vision weights and encoder computation on CPU; the language model processes the resulting image tokens on CUDA. The projector file is 931,145,856 bytes, and the observed CPU compute buffer was about 248 MiB. Image size also affects runtime and memory use.

## Quick vision request

Run `./simple_request.sh` to send the included [1920×1080 fairyland image](assets/fairyland-unicorns-1080p.png) to the local API with the question “What is visible in this image?” and print the complete response as indented JSON. The image shows grazing unicorns on a green meadow, bright sunshine, green trees, a rainbow, and a distant fairy-tale castle. The full-size image was tested successfully: the model identified the unicorns, rainbow, castle, and surrounding landscape. The script needs Python 3 but no extra Python packages. An optional `hostname[:port]` argument selects the API server. The default host is `localhost` and the default port is `8080`:

```bash
./simple_request.sh                    # localhost:8080
./simple_request.sh notebook           # notebook:8080
./simple_request.sh notebook:8081      # notebook:8081
```

An explicit argument overrides `BONSAI_BASE_URL`; without an argument, the environment variable remains supported. Remote access requires the server's API to be reachable from your machine; `run.sh` binds to localhost by default.

## Tests and measured performance

With the server running on the default port:

```bash
python3 -B tests/test-api.py       # model list, chat, and ~15k-token prompt
python3 -B tests/test-vision.py    # two known-shape image requests
python3 -B tests/test-coding.py    # three Python tasks, 23 assertions
```

`tests/test-api.py` accepts `BONSAI_BASE_URL` and `BONSAI_CTX_SIZE`; its long-context test requires a window of at least 16k. The vision and coding scripts currently use port 8080. The coding script executes generated programs in restricted, network-disabled Python containers. Outputs are written to the local, Git-ignored `results/` directory. Project test scripts disable Python bytecode caching, and `simple_request.sh` invokes Python with `-B`, so these entry points do not create `__pycache__` directories. Use `python3 -B` or `PYTHONDONTWRITEBYTECODE=1` for any additional Python commands in the project; avoid `py_compile` and `compileall`, which explicitly write bytecode files.

`python3 -B tests/qa.py` checks **previously saved** runtime evidence, including `results/server.log`, the API and vision/coding results, and `results/context-env-8192.json` from a separate 8k-context run. It is an audit of the completed validation, not a fresh end-to-end test of the current container. Capture a current server log with `podman logs bonsai2-27b > results/server.log` after running the API tests; the 8k artifact requires a separate 8k start and a saved `/props` response.

On **WSL2 with an RTX 5070 Ti Laptop GPU (12 GB)**, the 16k API test, both vision function tests, and all 23 coding assertions passed. The saved QA audit reported **14/14 checks passed**. A 15,009-token prompt was processed at **629 prompt tokens/s**. Three coding generations measured **60.5, 57.8, and 54.8 generated tokens/s**. These are individual measurements on this notebook, not guaranteed throughput elsewhere. MTP `n_max=2` was active; it is not necessarily the fastest setting for every prompt.

A separate [vision quality check](results/vision/quality-check.json) sent [this synthetic image](results/vision/quality-check.png) through `/v1/chat/completions`. The model correctly described a red square at the upper left and a blue circle at the lower right. This verifies a simple image request, not general photo understanding or OCR. The linked results are local test artifacts and are excluded from Git.

The recorded server log showed **66/66 language-model layers on CUDA0**, a 5,995.31 MiB CUDA0 model buffer, `q8_0` K/V caches for main and draft contexts, Flash Attention, and `CLIP using CPU backend` for vision. A later GPU snapshot showed **9,078 of 12,227 MiB** in use, including other processes; it is not an isolated model-only VRAM measurement.

## Moving to another computer

On the target system, copy the project and run `./prepare.sh`, `./build.sh`, and `./run.sh`. Alternatively, export the built image and transfer it alongside `run.sh` and **both** GGUF files in `models/`:

```bash
podman save -o bonsai2-27b.tar localhost/bonsai2-27b:latest
# On the target system:
podman load -i bonsai2-27b.tar
BONSAI_CTX_SIZE=16384 ./run.sh
```

The target still needs working NVIDIA GPU access and a supported compute capability. WSL2 with sm120 was tested; native Linux and sm86/sm89 are packaged but have not had runtime validation here. The image contains CUDA runtime libraries and Bonsai-compatible binaries, while NVIDIA driver libraries come from the target host. See [RECHERCHE.md](RECHERCHE.md) for model variants, server forks, and the choice of artifacts.

## Repository conventions

See [AGENTS.md](AGENTS.md) for the project workflow and validation rules. Keep
documentation, script comments, and messages in English; use `BONSAI_` for
project configuration variables. Keep temporary work under `/tmp/bonsai27/`
and Python bytecode caches out of the project. Completed changes use English
Conventional Commit messages compatible with semantic-release and end with
`(by Codex)`.
