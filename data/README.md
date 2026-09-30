# Local runtime data

`backends/blackwell/` holds the CUDA 12.8 bundle for sm120; `backends/ampere-ada/` holds the CUDA 12.4 bundle for sm86/sm89. Each directory contains a downloaded archive and its SHA256-verified contents under `runtime/`. Only `runtime/` is copied into the container image.

`research/` contains metadata and source files retained from the original investigation. Downloaded binaries and archives are excluded by `.gitignore` and can be restored with `./prepare.sh`. `./build.sh` verifies the extracted backends again before building the image. NVIDIA host drivers are not stored here: native Linux uses CDI for GPU access, while WSL2 mounts installed driver files from `/usr/lib/wsl` when `run.sh` starts the container.
