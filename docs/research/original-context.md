# Research and implementation: Bonsai 2 27B

Research conducted on 28–29 September 2026; local validation updated on 30 September 2026. Published benchmark numbers below are reported by model or fork authors unless identified as measurements from this notebook.

Host diagnosis on 1 October 2026: native Linux Mint 22.3 with an RTX 4070 Ti
SUPER and NVIDIA driver 595.91.07 passed host `nvidia-smi`. Starting the existing
`bonsai2-27b` Podman container failed before application startup with
`unresolvable CDI devices nvidia.com/gpu=all`; the host lacked `nvidia-ctk`,
NVIDIA Container Toolkit packages, and CDI specifications. The new
`install_nvidia_container_toolkit.sh --check` reproduced the missing-toolkit
diagnosis without changing the host. Installation and native Linux container
inference have not been validated. The installer follows
[NVIDIA's CDI guidance](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html),
including the base-package option for machines using CDI exclusively.

Follow-up after toolkit installation: Toolkit 1.20.1 generated CDI 0.7.0 in
`/var/run/cdi/nvidia.yaml`; Podman 4.9.3 debug logs rejected it with
`json: unknown field "additionalGids"`. NVIDIA's supported
`no-additional-gids-for-device-nodes` feature flag generated CDI 0.5.0 successfully
in `/tmp/bonsai27/`. The host specification has not been replaced and inference
has not been tested. The installer now offers `--repair-cdi` and persists that
flag for Podman 4 refreshes. Existing APT sources offer only Podman 4.9.3.
