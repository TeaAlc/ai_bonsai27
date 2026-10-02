#!/usr/bin/env bash
# Compatibility alias; all installation logic lives in install_nvidia.sh.
set -euo pipefail
script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# Explicit diagnostic/repair modes supersede the old installer selection.
case "${1:-}" in
    --check|--repair-cdi|--help|-h) exec "$script_directory/install_nvidia.sh" "$@" ;;
    *) exec "$script_directory/install_nvidia.sh" --driver-only "$@" ;;
esac
