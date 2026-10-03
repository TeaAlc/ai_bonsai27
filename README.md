![Unicorns grazing in a sunny fairyland meadow with a rainbow and castle](assets/fairyland-unicorns-1080p.png)

# Bonsai 2 27B with Vision in Podman

Run Bonsai 2, based on Qwen3.8-27B, through a Bonsai-compatible `llama-server`
and its OpenAI-compatible API. The language model, embeddings, MTP head, KV
caches, and recurrent state stay on CUDA0. The separate BF16 vision encoder
and projector run on CPU and system RAM.

Defaults: **32,000-token context, MTP=2, Flash Attention, q8_0 main/draft KV
caches**, and API model ID **`bonsai2-27b`**. MTP=2 is the standard on
**Ampere, Ada, and Blackwell**, including both published and native backends.
Performance benchmarks always enable thinking with **`medium`** reasoning.
The host API binds to all IPv4 interfaces (`0.0.0.0`) by default.
Set `BONSAI_BIND_ADDRESS=127.0.0.1` for local-only access.

- [Quick start](#quick-start)
- [GPU requirements and host setup](#gpu-requirements-and-host-setup)
- [Configuration](#configuration)
- [Model cache](#model-cache)
- [Local builds](#local-builds)
- [API examples](#api-examples)
- [Text benchmark](#text-conversation-benchmark)
- [Performance and validation](#performance-and-validation)
- [Desktop setup](docs/desktop.md), [releases and publication](docs/releases.md), [validation details](docs/validation.md)

## Quick start

Run from the project directory inside Linux or WSL2, with working GPU access:

```bash
podman pull ghcr.io/teaalc/ai_bonsai27:latest
BONSAI_IMAGE=ghcr.io/teaalc/ai_bonsai27:latest \
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./run.sh
podman logs -f bonsai2-27b
```

Press Ctrl+C to stop following logs; the container keeps running. Once loading
finishes, check readiness and send the included vision example:

```bash
curl --fail http://localhost:8080/health
./simple_request.sh
```

Missing models are downloaded from pinned revisions and SHA256-verified on first
start. The image does not contain the model files. Later starts reuse the
persistent cache. Internet access is needed for uncached images and models.

`run.sh` configures GPU access and mounts automatically. Its default image is
`localhost/bonsai2-27b:latest`, the last successful local build. If the selected
image is absent, it prompts for a remote reference; Enter accepts
`ghcr.io/teaalc/ai_bonsai27:latest`. A failed pull or closed stdin stops startup.
For unattended use, pre-pull the selected image as shown above.

The default container name must be unused, and port 8080 must be available.
To change creation settings, recreate the container while retaining its cache:

```bash
podman stop bonsai2-27b
podman rm bonsai2-27b
BONSAI_IMAGE=ghcr.io/teaalc/ai_bonsai27:latest \
BONSAI_MODEL_DIR="$HOME/bonsai-models" \
BONSAI_CTX_SIZE=16384 BONSAI_PORT=8081 ./run.sh
BONSAI_BIND_ADDRESS=127.0.0.1 ./run.sh  # Explicit local-only access
```

## GPU requirements and host setup

Use x86-64 Linux or WSL2, Bash, rootless Podman, Git, `curl`, `tar`, and
`sha256sum`. Python 3.11 or newer is needed for build and evidence tooling, request scripts,
and tests. Local build tooling uses `flock`; model-cache locks do not.

| GPU family | Compute capability | Image backend |
| --- | --- | --- |
| Ampere, e.g. RTX 30 series | 8.6 | Pinned Ampere/Ada bundle |
| Ada, e.g. RTX 40 series | 8.9 | Pinned Ampere/Ada bundle; optional optimized Ada build |
| Blackwell, e.g. RTX 50 series | 12.0 | Native SM120 Prism build when included; pinned Blackwell bundle otherwise |

Other compute capabilities are rejected before model downloads. These support
limits do not include every GPU marketed under those architecture names.
All three supported capabilities remain available in an image containing both
specialized backends: Ada source is selected only on 8.9, Blackwell source
only on 12.0, and Ampere 8.6 keeps its published bundle.

Enough VRAM is required for the entire LLM and context state: memory pressure
fails startup rather than automatically offloading to CPU. A 32,000-token allocation and medium-reasoning benchmark passed on a 12 GB
RTX 5070 Ti Laptop GPU, with 9,516 MiB peak total GPU memory. Earlier 16k
setups were tested on that GPU and a 16 GB RTX 4070 Ti SUPER.
Larger context windows need additional memory; support limits do not guarantee
that a requested window fits your GPU.

- **Native Linux:** working NVIDIA host drivers and NVIDIA Container Toolkit/CDI.
  Podman uses `--device nvidia.com/gpu=all`.
- **WSL2:** working NVIDIA Windows drivers, `/dev/dxg`, and `/usr/lib/wsl`.
  `run.sh` mounts the driver directory read-only. Do not install a separate
  Linux NVIDIA driver for this WSL2 route.
- **Desktop engines:** GPU access must exist in the selected engine/VM.
  Stock Podman Desktop Hyper-V does not provide the documented NVIDIA GPU
  route. An independently GPU-provisioned Linux guest is conditional and
  untested. See [Desktop and direct-engine setup](docs/desktop.md).

### Native Linux setup and diagnostics

Use one installer for NVIDIA drivers, Podman, and Toolkit/CDI on Linux Mint,
Ubuntu, or Debian. Run it as your normal user; package/configuration changes
prompt through `sudo`, and APT retains its confirmation prompts:

```bash
./install_nvidia.sh
./install_nvidia.sh --check --verify-container
./run.sh
```

The default mode keeps a working NVIDIA driver and existing Podman. If the
host driver is missing or broken, Mint/Ubuntu use the distribution-recommended
package; Debian uses `nvidia-driver` and requires administrator-enabled
contrib/non-free/non-free-firmware sources. A driver install exits with status
3: reboot, complete Secure Boot/MOK enrollment if requested, and rerun. The
script never reboots automatically. WSL and other distributions are rejected.

For rootless Podman, the installer uses NVIDIA's signed production APT
repository and `nvidia-container-toolkit-base` (CDI CLI/hooks). No host CUDA
SDK/development toolkit is needed: the image provides CUDA runtime libraries,
while the host supplies the driver. See [NVIDIA's toolkit requirements](https://github.com/NVIDIA/nvidia-container-toolkit)
and [CDI support](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html).
Docker daemon configuration is outside this Podman installer.

```bash
./install_nvidia.sh --check                  # diagnostics; no host changes
./install_nvidia.sh --repair-cdi             # refresh CDI, no package downloads
./install_nvidia.sh --check --image localhost/bonsai2-27b:latest
./install_nvidia.sh --check --log /tmp/nvidia-diagnostics.log
```

Logs are private files under `results/nvidia-setup/`, or the selected new
`--log` path. They capture OS/kernel, NVIDIA PCI devices, Secure Boot/module
status, GPU/driver/VRAM/capability, installed packages, actual Podman/rootless
runtime, Toolkit version, CDI paths/permissions/checksums, refresh-service
status/recent journal, image identity, and CUDA verification errors. Commands
and credentials are not dumped. `--check` writes its log and may run temporary
probe containers, but does not modify host packages or configuration.

With a cached project image, checks run its actual CUDA probe and dependency
validator through CDI, without networking, model mounts, or inference. No image
is pulled implicitly. Without that image, ordinary checks explicitly report
container CUDA as unverified; `--verify-container` requires verification and
fails if the image is missing. Root execution tests root's Podman store rather
than the normal user's rootless setup, so prefer running as your normal user.

CDI regeneration backs up an existing spec and avoids conflicting copies in
`/etc/cdi` and `/var/run/cdi`. For Podman 4, the supported
`no-additional-gids-for-device-nodes` compatibility flag is persisted for the
CDI refresh service. It omits supplementary device groups: if your host relies
on those permissions, upgrade Podman. Existing conflicting refresh flags or
duplicate CDI specs stop setup for manual review. All setup logic lives in
`install_nvidia.sh`; the previous installer scripts have been removed.

## Configuration

### Host startup variables

These are all environment variables read by `run.sh`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BONSAI_MODEL_DIR` | Caller’s current directory | Host directory mounted read/write at `/models`; created if missing |
| `BONSAI_CTX_SIZE` | `32000` | Context window in tokens; integer 512–262144 (VRAM permitting) |
| `BONSAI_REASONING_EFFORT` | `medium` | Reasoning effort: `low`, `medium`, or `xhigh` |
| `BONSAI_PORT` | `8080` | Available host TCP port, 1–65535 |
| `BONSAI_BIND_ADDRESS` | `0.0.0.0` | Host IPv4 bind address: all interfaces by default; `127.0.0.1` for local-only access, or a specific host IPv4 address |
| `BONSAI_IMAGE` | `localhost/bonsai2-27b:latest` | Preferred local image; if missing, prompts for a remote reference (default `ghcr.io/teaalc/ai_bonsai27:latest`) |
| `BONSAI_GPU_BACKEND` | Automatic | Empty, `blackwell` (12.0), or `ampere-ada` (8.6/8.9); override must match CUDA device 0 |
| `BONSAI_CONTAINER_NAME` | `bonsai2-27b` | Container name; select a unique name for independent instances |
| `BONSAI_DOWNLOAD_WAIT_SECONDS` | `600` | Shared-cache lock wait, integer 1–86400 seconds |
| `BONSAI_DOWNLOAD_TIMEOUT` | `3600` | Per-attempt HTTP limit, integer 1–86400 seconds |

`BONSAI_CTX_SIZE` must be a decimal integer from 512 to 262144. Leading zeros are normalized; oversized integers are rejected before arithmetic. The upper bound follows the model's supported context and does not guarantee available VRAM. `BONSAI_REASONING_EFFORT` accepts `low`, `medium`, or `xhigh` (default: `medium`). The official model default is `xhigh`; `medium` gives shorter reasoning. The model accepts `low` but it may behave much like `xhigh`; `high` is invalid and can cause an HTTP 500. Larger contexts need more VRAM. A 128k allocation/startup check passed on the Ada host, but filled-window performance and recall have not been validated. See the [official model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) and [known issues](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/main/KNOWN_ISSUES.md).

Optional positional arguments passed to `run.sh` are forwarded to `llama-server`, for example `./run.sh --log-verbose`. Additional server flags can override the defaults, so preserve the GPU-only language-model and CPU vision settings. `BONSAI_BASE_URL` configures request scripts; it does not change the container binding. `BONSAI_GPU_BACKEND` is forwarded when supplied and validated against the detected device; `BONSAI_MODEL` and `BONSAI_MMPROJ` are container entrypoint settings and are not forwarded from the host environment by `run.sh`. For status and logs, use `podman ps` and `podman logs -f bonsai2-27b`.

### Container-only settings and client settings

| Variable | Default | Scope / purpose |
| --- | --- | --- |
| `BONSAI_MODEL` | `/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf` | Container LLM path |
| `BONSAI_MMPROJ` | `/models/Ternary-Bonsai-2-27B-mmproj-BF16.gguf` | Container vision-projector path |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` | NVIDIA runtime; keep CUDA compute enabled |
| `GGML_CUDA_BATCH_INVARIANT` | `1` | Container CUDA batch invariance |
| `BONSAI_BASE_URL` | `http://localhost:8080` | Request/test client endpoint; does not publish ports |
| `BONSAI_BENCHMARK_RESULT` | Unique file under `results/text-benchmark/` | Text benchmark output path |

The startup table's context, reasoning, backend, and download-limit settings are
passed into the container by `run.sh`; model directory, image, port, and container
name configure the host engine. In a Desktop dialog, mount `/models`, publish port 8080 on the desired host interface,
and enable GPU devices separately. Keep the image entrypoint. Missing files at
custom container model paths receive the same pinned artifacts, not models
selected by filename. CUDA device 0 is checked through the bundled driver probe,
with `nvidia-smi` as a fallback; an explicit backend must match the actual GPU.

## Model cache

`BONSAI_MODEL_DIR` is a writable persistent host directory, defaulting to the
caller's current directory and mounted at `/models`. Relative paths resolve
against the invoking directory. Reuse the same directory for downloads and runs:

```bash
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./download_models.sh
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./download_models.sh --verify
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./download_models.sh --repair
```

The shared host/container downloader uses these pinned files:

- `Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf`
- `Ternary-Bonsai-2-27B-mmproj-BF16.gguf`

Existing nonempty readable files are reused without automatic checksum checks.
`--verify` explicitly checks pinned cache contents; `--repair` replaces damaged
pinned files after a verified download. Custom paths are not checked against
those pins automatically.

Downloads resume `.part` files and rename them after checksum verification.
Atomic `.lock.d` directory locks support shared filesystems without `flock`.
Each attempt has a 30-second connection timeout, a stalled-transfer limit, and
the configurable HTTP timeout. Handled stop signals cancel the download worker
and release its owned lock. After a forced shutdown, remove a stale lock and
its temporary status file only after all downloads sharing the cache have
stopped. Keep `.part` files for resumption. Old `.lock` files are unused; stop
old flock-based containers before sharing their cache with this downloader.

## Local builds

```bash
./prepare.sh
./image_build.sh
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./run.sh
```

Use the same `BONSAI_MODEL_DIR` for `prepare.sh` if downloading models there.
Preparation downloads and verifies model pins and both published backend
bundles; image creation belongs to `image_build.sh`. Models remain outside the image.
The build verifies immutable source/backend snapshots, records dependency
inventories in `results/last-build.json`, and tags the result with its calculated
SemVer and `localhost/bonsai2-27b:latest`. Development builds retain a dirty label.

The pinned semrel tool lives under `tools/`; version calculation uses complete
local Git history and reachable stable tags. Builds never tag Git or publish
implicitly. See [release and publication procedures](docs/releases.md),
[data layout](data/README.md), and [dependency pins](RECHERCHE.md).
The imported changes passed fresh GPU/API QA on this WSL2 notebook: 18/18
checks, vision, coding, and 16k/8k context verification. See the
[dated integration validation](docs/validation.md#local-integration-verification--2026-10-02).

The build entry point is now `image_build.sh` (formerly `build.sh`). Local
repository copies under `other_repo/` are excluded from Git and build snapshots.
Preparation, build, release, tag, and push share a checkout lock. Temporary build
files use `/tmp/bonsai27/`, or the standard `TMPDIR` override.

## Optional Ada source backend

Prepared source backends are included automatically by `image_build.sh`; this
preserves the specialized Ada runtime during subsequent builds. Without a
prepared source runtime, the corresponding published bundle remains available.
An Ada source build of
PrismML's fork at `88c4bc60b9c9578f134385be9535e853f2db9b9f` includes the merged
Ada PTQ1, MTP, and native quantized Flash Attention changes researched on
2026-10-01. Prepare it separately, then create the image through the usual build
workflow (run `./prepare.sh` first if the published bundles are missing):

```bash
./tools/build-ada-backend.sh
./image_build.sh --ada-source
./run.sh
```

The compiler image and source archive are pinned by digest/SHA256. Compilation
runs inside Podman and requires working CUDA injection for linking, Internet
access for compiler packages, approximately 8 GB of temporary build space, and
several minutes. `BONSAI_BUILD_JOBS` accepts 1–64 and defaults to 8; reduce it on
hosts with little RAM. The prepared runtime, licenses, complete file inventory,
and build provenance stay under `data/backends/ada-source/runtime/` and are
excluded from Git. The build receipt includes the optional runtime identity and
compiler inventory. An ordinary `./image_build.sh` rebuild retains all prepared
source runtimes. Use `--published-only` explicitly to build the two original
bundles without either specialized runtime.

The optional image selects this backend only on compute capability 8.9. The
original Ampere 8.6 and Blackwell 12.0 bundles remain available. Runtime testing
of this optional build was performed only on an RTX 4070 Ti SUPER in a native
Linux KVM guest with NVIDIA CDI. GPU-only language-model placement, CPU BF16
vision, 32,000-token default context, MTP=2, q8_0 caches, and batch invariance
remain unchanged.
## Specialized Blackwell source backend

Build the native SM120 Prism runtime alongside the existing Ada runtime:

```bash
./prepare.sh
./tools/build-ada-backend.sh       # skip if its verified runtime is already prepared
./tools/build-blackwell-backend.sh
./image_build.sh --ada-source --blackwell-source
./run.sh
```

The explicit image flags require both source runtimes to be present. Subsequent
ordinary builds automatically retain prepared runtimes. The image also keeps
both published bundles for Ampere support and compatibility builds. GPU detection
selects `/opt/bonsai/ada-source` on 8.9 and `/opt/bonsai/blackwell-source` on 12.0;
`BONSAI_GPU_BACKEND` continues to accept only `ampere-ada` or `blackwell`.

Blackwell source revision, archive SHA256, CUDA compiler image digest, native
architecture, complete runtime inventory, licenses, and actual CMake settings
are verified and recorded. Files remain under
`data/backends/blackwell-source/runtime/`, excluded from Git. The build requires
Internet access, working GPU injection, temporary disk space, and several
minutes; `BONSAI_BUILD_JOBS` accepts 1–64 (default 8). The host needs no CUDA SDK
or sudo. Default inference retains MTP=2, main/draft q8_0, Flash Attention,
32,000-token context, GPU-only LLM placement, and BF16 vision on CPU.

A failed native Blackwell compilation retains its temporary directory and logs
its path. Resume that exact pinned build with
`./tools/build-blackwell-backend.sh --resume /tmp/bonsai27/blackwell-source.XXXXXX`.
Successful preparation removes its temporary sources and objects. Both native
builders snapshot their compiler scripts before a long build. Image creation
checks `TMPDIR` space before copying runtime snapshots; a small `/tmp` RAM
filesystem may require freeing temporary files or selecting a larger `TMPDIR`.
The standard default remains `/tmp/bonsai27/`.

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

An explicit argument overrides `BONSAI_BASE_URL`; without an argument, the environment variable remains supported. Remote access requires the server's API to be reachable from your machine; `run.sh` publishes on all IPv4 interfaces by default; `BONSAI_BIND_ADDRESS=127.0.0.1` restricts access to the host.
## Text conversation benchmark

Both example clients connect directly, ignoring inherited HTTP(S) proxy variables. Connection errors list failures for every resolved IPv4/IPv6 address. For a remote hostname, the server must publish port 8080 on its LAN interface and the firewall must allow access. The project’s `run.sh` publishes on `0.0.0.0` by default. Use the server’s LAN hostname/address in clients, not `0.0.0.0`. A refused IPv4 connection followed by unreachable IPv6 addresses indicates server/network configuration, not an invalid hostname argument.

With a running server, run `simple_text_benchmark.sh`:

```bash
./simple_text_benchmark.sh                 # localhost:8080
./simple_text_benchmark.sh notebook        # notebook:8080
./simple_text_benchmark.sh notebook:8081   # notebook:8081
```

It simulates **20 messages: 10 user prompts and 10 assistant answers**, retaining
all previous user prompts and final answers in each request. The conversation
develops a community library plan. It uses `/v1/chat/completions` with model
`bonsai2-27b`, temperature zero, **thinking enabled**, explicit **`medium`**
reasoning, prompt caching, and up to **4,096 output tokens per answer**, including
reasoning. It verifies nonempty `reasoning_content`, a final answer, and normal
completion for every exchange. Python 3 is the only client dependency.

The target is approximately **16,000 cumulative input + output tokens**, measured
from the API's `usage` fields across the ten requests. Repeated history counts
again on every request. This is not 16k distinct conversation tokens or a test
that fills the entire context window. The script applies the server's chat
template and tokenizer to budget neutral planning notes, adjusts after each
response, and checks that the prompt plus completion allowance fits the
advertised context. Full reasoning and retained history can exceed the target;
a total outside ±5% prints a warning and sets `within_5_percent=false`. Actual
usage is preserved. Failed inference, missing reasoning, empty answers, or
truncation still fail the benchmark and preserve partial evidence.

The standard is exactly **32,000 context tokens** in the image, `run.sh`,
and backend benchmarks. Increase it only when the individual
request needs more room, and check VRAM capacity first. A cumulative total above
16k across ten requests does not itself require a 32k context.

The terminal shows every answer and each request's usage, followed by an
indented summary. `decode_tokens_per_second` uses the server's generation
timings, when available, including reasoning and final-answer tokens;
`output_tokens_per_wall_second` includes HTTP,
template/tokenizer requests, and prompt processing. Missing decode timings
produce `null`, rather than an estimated generation speed.

Thinking-token counts are reported per exchange and in the JSON summary as
`reasoning_tokens`. The script prefers the API's
`usage.completion_tokens_details.reasoning_tokens`. If absent, it uses the
server tokenizer on returned `reasoning_content` without special tokens.
This fallback is marked `reasoning_tokens_are_estimated=true` because decoded
text boundaries may differ from the original generation. Each exchange records
`reasoning_tokens_source`; missing counts remain `null`, including the aggregate
if any exchange lacks a count. Completion-token usage already includes thinking;
do not add `reasoning_tokens` to the usage total again.

Prompt-cache results are printed per exchange and in the JSON summary.
Each exchange prints one compact statistics line, highlighted in bold cyan on
terminals (unless `NO_COLOR` is set); redirected output contains no ANSI escapes.
Message labels use bold yellow for the user and bold green for the assistant;
message text retains the normal terminal color.
For example: `Tokens: 37 in | 85 out (+1483 (est.) reasoning) | Cache: 33 cached + 4 processed; hit rate 89.19% | 12.16s`.
The displayed `out` count excludes reasoning: API completion tokens minus reasoning
tokens. `(est.)` marks retokenized reasoning, so the answer-token difference is
also estimated. If reasoning is unavailable or exceeds completion usage, `out`
is `unknown`. JSON completion usage retains the original API count, including reasoning.
`cached_prompt_tokens` counts reused input tokens, `processed_prompt_tokens`
counts input tokens that required processing, and `cache_hit_rate_percent`
expresses the reused fraction. The total rate is token-weighted:
`100 × sum(cached_prompt_tokens) / sum(prompt_tokens)`, including the first
request. Output tokens are excluded; this is not the percentage of requests
with a cache hit. The server's `timings.cache_n` supplies the counter, with
`usage.prompt_tokens_details.cached_tokens` as a fallback. Each exchange records
`cache_metrics_source`. Missing or invalid counters produce `null`; an
incomplete set of counters also produces a `null` aggregate rather than a
misleading partial rate. `cache_metrics_exchanges` shows how many completed
requests provided valid counters.

`BONSAI_BASE_URL` can select the endpoint (with or without `/v1`); an explicit
hostname argument overrides it. The full transcript, per-request timing and
usage, and summary are saved to a unique JSON file under
`results/text-benchmark/`. Set `BONSAI_BENCHMARK_RESULT=/path/report.json` to
choose the output file. Full API responses, including reasoning, are saved
beside that file under `<report-name>/responses/`, with actual chat requests
under `<report-name>/requests/`. The Python implementation is in
`tests/text_benchmark.py`; the public command stays unchanged. Existing report
paths are rejected rather than overwritten. Reports include a schema version
and `completed`, `failed`, `cancelled`, or `timed-out` status. Failed inference saves the completed exchanges as a
partial report. Start the server separately and wait for `/health` to return
HTTP 200 before benchmarking.

`longcontext.msg` contains exactly 30,000 tokens according to the tested
backend's `/tokenize` endpoint (`add_special=false`, `parse_special=false`),
not 30,000 characters. It is 135,577 characters; the medium-thinking chat
template produces 30,009 API prompt tokens. Each fresh measurement container
verified both counts before inference.

On this WSL2 RTX 5070 Ti Laptop host, three fresh-container runs using image
1.5.0 processed the full prompt in 55.21 ± 0.89 seconds with backend defaults
(batch 2048, microbatch 512). Three further runs adding
`./run.sh --batch-size 4096 --ubatch-size 2048` took 58.85 ± 1.53 seconds
(sample SD): 6.60% longer mean prompt-processing time in this test.
Sampled global VRAM peaks rose from 10,715 to 11,333 MiB (+618 MiB).
All runs retained 32,000 context, MTP=2, medium thinking, a 4096-token completion
cap, CPU BF16 vision and `GGML_CUDA_BATCH_INVARIANT=1`; each had zero cached
input tokens. Only 1,991 context tokens remained for completion, but all six
answers stopped normally without truncation or context overflow.

Times are server prompt-processing timings, excluding answer generation.
See the [corrected measurement record](data/research/longcontext-30k-tokens-20261003.json).
Local raw requests, responses, tokenizer outputs, container identities,
checksums, server logs, the frozen benchmark driver, and concurrent GPU samples
are under `results/longcontext-30k-tokens-20261003T170547Z/`.
GPU sampling targeted 200 ms plus query overhead and includes other host GPU
memory; short peaks may be missed. Baseline runs preceded candidate runs,
so this is a scoped single-prompt comparison, not a general performance claim.
The [earlier 30,000-character measurement](data/research/longcontext-batch-20261003.json)
is retained as historical evidence; its prompt snapshot is in the earlier
raw-results directory, rather than the current `longcontext.msg`.

## Performance and validation

**Current policy:** MTP=2 on every supported architecture; performance
benchmarks enable thinking at `medium` with exactly 32,000 context tokens.
The reason for this choice and older Ada/Blackwell/DFlash comparisons are in
[historical performance](docs/history/performance-20261002.md).

### Fresh cleanup acceptance — October 2, 2026

Three baseline and three candidate runs alternated on the RTX 5070 Ti Laptop
GPU (12 GB, WSL2). Each used a fresh container, MTP=2, medium reasoning, q8_0
main/draft caches, Flash Attention, and CPU BF16 vision. Values after ± are
sample standard deviations across three runs, not confidence intervals.

| Metric | Baseline | Refactored candidate |
| --- | ---: | ---: |
| Decode tokens/s, mean ± SD | 61.91 ± 0.57 | **61.73 ± 0.61** |
| Conversation seconds, mean ± SD | 233.718 ± 1.807 | 234.864 ± 2.782 |
| Mean total GPU memory across runs | 9,547.61 MiB | 9,554.26 MiB |
| Highest observed GPU memory | 9,562 MiB | **9,583 MiB (9.36 GiB)** |
| Thinking tokens per conversation | 12,800 estimated | 12,800 estimated |
| Token-weighted prompt-cache hits | 80.45% | 80.45% |
| Independent quality probes | 27/27 passed | 27/27 passed |

The observed decode difference is **−0.30%**; the highest memory peak increased
by **21 MiB**, below the plan's practical review triggers. All six runs sent
identical chat payloads and produced identical visible conversations. Each
used 6,600 input + 13,752 output = 20,352 cumulative API tokens, so the approximate
16k usage target was exceeded explicitly. Thinking is included in completion
usage and was counted through the server tokenizer as an estimate.

Memory includes the desktop and other processes and is sampled once per
second. Initial GPU activity was 1–4%, with temperatures of 63–71°C; thermal
state was not strictly fixed. This conversation does not fill the 32k window.
The candidate includes initial health/props requests in its client wall interval;
the baseline starts that interval after them. Decode rates use server timings.
Fresh functional QA passed all **18 checks**, including CPU vision, a 15,009-token
prompt and **23 executed coding assertions**. Corrected parent-stop cleanup and
an additional complete conversation passed. The clean image also passed actual
default 32000/medium/MTP=2 API and unicorn-vision checks, with runtime content
matching the measured candidate.

These are three observations on one host, not a throughput guarantee or a
full-window capacity test. Cleanup acceptance uses locally built images;
registry publication and anonymous-pull validation remain separate release checks. See the
[identified cleanup measurement](data/research/repository-optimization-20261002/acceptance.json).

To reproduce independent cold-cache runs of an existing local image:

```bash
BONSAI_MODEL_DIR="$HOME/bonsai-models" \
  ./tests/benchmark-backends.sh native localhost/bonsai2-27b:latest 3
```

The helper owns its containers on localhost port 18084 (`BONSAI_PORT` overrides
it), uses a 32,000-token window and explicitly enabled medium reasoning. It saves image
identity, executable, API timing/cache counters, timestamped GPU telemetry,
`run-<n>/gpu-memory.json` with mean/peak total VRAM during the measured interval,
logs, and nine quality probes under `results/`. Unknown memory counters remain
`null`; one-second sampling can miss transient peaks.
Each repetition has a unique container and `run-<n>/` directory. Its
`benchmark-index.json` binds identity, actual argv and /props, model hashes,
requests/responses, UTC-bound telemetry, server log, and separate quality probes.
Audit a completed run with:

```bash
python3 -B tests/benchmark_evidence.py audit results/backend-benchmarks/SUITE/run-1
```

API-only runs do not prove local image identity. Failed or cancelled runs keep
partial indexes and cannot pass acceptance. Legacy GPU CSVs require an explicit
timezone when using `tests/summarize-gpu-memory.py`; unknown VRAM remains null.
`BONSAI_TEST_RUN_DIR` selects the evidence directory. Set
`BONSAI_EXPERIMENT_CODING=1` to add the restricted coding tests after each
run. Optional server arguments follow the repetition count.

For experimental DFlash, set `BONSAI_EXPERIMENT_DRAFT_MODEL` to an existing
compatible GGUF and `BONSAI_EXPERIMENT_DRAFT_N_MAX` to 1–15 (default 3).
The helper replaces MTP rather than combining strategies and pins the draft to
CUDA0; it does not download draft models or permit CPU fallback. Draft trials use
`GGML_CUDA_PDL=1`; `BONSAI_EXPERIMENT_PDL` accepts `0` (disabled) or `1`
(enabled, default) for controlled comparisons. Successful startup does not establish draft
stability or sufficient memory for every prompt. Benchmark requests have a
600-second overall deadline per conversation; failed runs preserve partial evidence.

| Platform | Runtime evidence |
| --- | --- |
| Direct Podman / WSL2 / RTX 5070 Ti Laptop, 12.0 | Identified 16k/8k API, vision, coding, GPU placement, and offline startup checks |
| Rootless Podman / Linux Mint KVM guest / NVIDIA CDI / RTX 4070 Ti SUPER, 8.9 | Actual inference, MTP/DFlash comparisons, paired quality probes, repeated text benchmarks |
| Ampere 8.6 | Backend packaged and detection/dependency checks; no actual GPU inference test here |
| Docker/Podman Desktop applications | Setup documented; application GPU route not runtime-tested here |
| Independently GPU-provisioned Hyper-V Linux guest | Conditional; untested |

A 128k startup/allocation check passed on Ada with GPU-only LLM state. It did
not fill that window or validate 128k recall, latency, or DFlash memory headroom.
The shared Windows model-filesystem scenario still needs host-specific live
validation. Historical notebook measurements and exact saved run identities
remain in [validation details](docs/validation.md).

Run a fresh identified API/vision/coding suite or offline regression fixtures:

```bash
BONSAI_MODEL_DIR="$HOME/bonsai-models" ./tests/run-qa.sh
./tests/run-regressions.sh
```

The live suite owns its 16k/8k containers and saves checksum-bound evidence under
`results/runs/<suite-id>/`. Coding runs only in restricted containers. Auditing
saved evidence with `python3 -B tests/qa.py results/runs/<suite-id>` does not prove
a fresh live test passed. See [validation details](docs/validation.md) for
individual test settings and runtime/failure-path checks.

## Troubleshooting

Watch `podman logs -f bonsai2-27b`. Timestamped startup stages are configuration,
model-cache, gpu-access, runtime-dependencies, models, and server. The API is
ready only when `/health` returns HTTP 200.

| Symptom | Check |
| --- | --- |
| `libcuda.so.1` missing or CUDA query fails | Host driver and engine GPU injection; backend overrides cannot expose a GPU. CUDA checks run before downloads |
| `unresolvable CDI devices` | Toolkit/CDI configuration in the selected engine; use the native Linux helper or [Desktop guide](docs/desktop.md) |
| Podman 4 rejects `additionalGids` | `./install_nvidia.sh --repair-cdi`; see the compatibility note above |
| Cache lock wait or interrupted download | Shared-cache users, timeout settings, and stale-lock procedure in [Model cache](#model-cache) |
| Port/name already used | Stop/remove the old container or choose another port/name; recreating is required to change settings |
| GHCR authentication fails | For a private package, `podman login ghcr.io --username YOUR_GITHUB_USERNAME` with authorized `read:packages` credentials |

Successful downloads or `nvidia-smi` alone do not prove container CUDA access.
The image includes CUDA runtime libraries; actual NVIDIA driver libraries come
from the host. Keep `NVIDIA_DRIVER_CAPABILITIES=compute,utility`, and do not add a
CUDA stub to bypass driver errors. Detailed engine diagnostics are in the
[Desktop guide](docs/desktop.md).

## Moving to another computer

Transfer the image and both GGUF files for offline startup, or pull/build and
allow pinned downloads on the target:

```bash
podman save -o bonsai2-27b.tar localhost/bonsai2-27b:latest
# On the target system:
podman load -i bonsai2-27b.tar
BONSAI_MODEL_DIR=/path/to/models ./run.sh
```

The target needs a supported GPU and working NVIDIA access. Host driver setup
is separate from the image. For direct-engine volumes and remote engines, see
[Desktop and direct-engine setup](docs/desktop.md).

## Maintenance and repository conventions

The Ubuntu base digest, model revisions, backend archives, and source/compiler
inputs are pinned. Apt package versions are recorded at build time; builds are
auditable but not promised to be bit-for-bit reproducible. Refresh pins
intentionally, retain licenses, rebuild, inspect the inventory, and rerun live
checks. Never alter verified upstream bundles to make a check pass. Driver
compatibility notes and upstream references are in [RECHERCHE.md](RECHERCHE.md).

See [AGENTS.md](AGENTS.md) for project rules and [TODO_PLAN.md](TODO_PLAN.md) for
the detailed optimization plan and acceptance checklist. The original
[September 30 audit](docs/history/repository-audit-20260930.md) is archived.
Documentation and script messages are English;
project configuration uses `BONSAI_`. Keep local test evidence in `results/`,
temporary work in `/tmp/bonsai27/`, and downloaded models/binaries out of Git.
Run Python with `python3 -B`; do not create bytecode caches. Completed changes
use English Conventional Commits ending with `(by Codex)`.
