#!/usr/bin/env bash
# Compatibility entry point; compile flags live in the shared helper.
set -euo pipefail
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/compile-backend.sh" blackwell
