FROM docker.io/library/ubuntu:24.04
COPY data/backends/blackwell/runtime/ /opt/bonsai/blackwell/
COPY data/backends/ampere-ada/runtime/ /opt/bonsai/ampere-ada/
COPY entrypoint.sh /usr/local/bin/bonsai-server
ENV BONSAI_CTX_SIZE=16384 BONSAI_MODEL=/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf GGML_CUDA_BATCH_INVARIANT=1
ENV BONSAI_GPU_BACKEND=blackwell
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/bonsai-server"]
