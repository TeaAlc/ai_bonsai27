# Compile a small runtime GPU probe; no compiler or CUDA toolkit in the final image.
FROM docker.io/library/ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS gpu-probe-build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY data/gpu/compute-capability.c /src/compute-capability.c
RUN gcc -O2 -Wall -Wextra -Werror /src/compute-capability.c -ldl -o /cuda-compute-capability

FROM docker.io/library/ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
# HTTPS downloads are needed only when a mounted model file is missing.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash coreutils curl ca-certificates util-linux libc-bin libstdc++6 libgcc-s1 \
    && rm -rf /var/lib/apt/lists/*
COPY data/backends/blackwell/runtime/ /opt/bonsai/blackwell/
COPY data/backends/ampere-ada/runtime/ /opt/bonsai/ampere-ada/
COPY data/backends/ada-source/runtime/ /opt/bonsai/ada-source/
COPY data/backends/blackwell-source/runtime/ /opt/bonsai/blackwell-source/
COPY data/config.sh /opt/bonsai/config.sh
COPY data/logging.sh /opt/bonsai/logging.sh
COPY entrypoint.sh /usr/local/bin/bonsai-server
COPY data/models/download.sh /opt/bonsai/download-models.sh
COPY data/gpu/settings.sh /opt/bonsai/settings.sh
COPY data/gpu/detect.sh /opt/bonsai/detect-gpu.sh
COPY data/gpu/check-runtime.sh /opt/bonsai/check-runtime.sh
COPY --from=gpu-probe-build /cuda-compute-capability /opt/bonsai/cuda-compute-capability
ENV BONSAI_CTX_SIZE=32000 BONSAI_REASONING_EFFORT=medium BONSAI_MODEL=/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf GGML_CUDA_BATCH_INVARIANT=1
# Docker's NVIDIA runtime must inject CUDA compute libraries, not just NVML tools.
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
# Copies through Windows filesystems can lose executable permission bits.
# Restore installation modes in the image without changing verified file bytes.
RUN find /opt/bonsai -type f -path "*/bin/*" -exec chmod 0755 {} +
# Builds have no GPU driver mount. Every other runtime dependency must resolve.
RUN bash /opt/bonsai/check-runtime.sh --allow-missing-driver
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/bonsai-server"]
