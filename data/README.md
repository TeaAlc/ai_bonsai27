# Local runtime data

`backends/blackwell/` holds the CUDA 12.8 bundle for sm120; `backends/ampere-ada/` holds the CUDA 12.4 bundle for sm86/sm89. Each directory contains a downloaded archive and its SHA256-verified contents under `runtime/`. Backend `runtime/` directories are copied into the container image.

`research/` contains metadata and source files retained from the original investigation. Downloaded binaries and archives are excluded by `.gitignore` and can be restored with `./prepare.sh`. `./build.sh` verifies the extracted backends again before building the image. NVIDIA host drivers are not stored here: native Linux uses CDI for GPU access, while WSL2 mounts installed driver files from `/usr/lib/wsl` when `run.sh` starts the container.

Project-supplied build tools, including semrel, live separately under [tools/](../tools/README.md). Keep CUDA backend libraries and other container runtime dependencies in this `data/` directory.

`models/download.sh` contains shared pinned GGUF metadata and the download helper
used by `download_models.sh`, `prepare.sh`, and the container entrypoint. The
container also installs curl, CA certificates, and util-linux through its base
distribution package manager. GGUF files are stored outside `data/` in the
configured `BONSAI_MODEL_DIR`, defaulting to the caller’s current directory.

`gpu/detect.sh` selects the CUDA backend inside the container through
the CUDA driver probe compiled from `gpu/compute-capability.c`, with
`nvidia-smi` as a fallback; an explicit `BONSAI_GPU_BACKEND` overrides detection.

`gpu/check-runtime.sh` verifies download tools, HTTPS certificates, and all
shared-library dependencies of both backends. Image builds permit only
libcuda.so.1 to be absent; the GPU-enabled runtime check permits no missing
libraries. Distribution runtime packages are explicitly installed in the image.
The host's CUDA driver is injected through Docker GPU support, NVIDIA CDI, or
the WSL driver mount rather than bundled with a mismatched kernel driver.
