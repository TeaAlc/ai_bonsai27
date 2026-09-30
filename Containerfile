# Compile a small runtime GPU probe; no compiler or CUDA toolkit in the final image.
FROM docker.io/library/ubuntu:24.04 AS gpu-probe-build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY data/gpu/compute-capability.c /src/compute-capability.c
RUN gcc -O2 -Wall -Wextra -Werror /src/compute-capability.c -ldl -o /cuda-compute-capability

FROM docker.io/library/ubuntu:24.04
# HTTPS downloads are needed only when a mounted model file is missing.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates util-linux && rm -rf /var/lib/apt/lists/*
COPY data/backends/blackwell/runtime/ /opt/bonsai/blackwell/
COPY data/backends/ampere-ada/runtime/ /opt/bonsai/ampere-ada/
COPY entrypoint.sh /usr/local/bin/bonsai-server
COPY data/models/download.sh /opt/bonsai/download-models.sh
COPY data/gpu/detect.sh /opt/bonsai/detect-gpu.sh
COPY --from=gpu-probe-build /cuda-compute-capability /opt/bonsai/cuda-compute-capability
ENV BONSAI_CTX_SIZE=16384 BONSAI_MODEL=/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf GGML_CUDA_BATCH_INVARIANT=1
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/bonsai-server"]
