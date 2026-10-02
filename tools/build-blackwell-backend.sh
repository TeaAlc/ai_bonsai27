#!/usr/bin/env bash
# Compatible entry point; the shared builder preserves this profile's policy.
set -euo pipefail
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/build-native-backend.sh" blackwell "$@"
