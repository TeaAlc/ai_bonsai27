#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
source data/gpu/settings.sh
for value in 512 8192 16384 32000 262144 000016384; do BONSAI_CTX_SIZE=$value validate_bonsai_settings; done
for value in 0 -1 ' 16384' 511 262145 18446744073709552128; do
    if BONSAI_CTX_SIZE=$value validate_bonsai_settings; then exit 1; fi
done
for value in low medium xhigh; do BONSAI_REASONING_EFFORT=$value validate_bonsai_settings; done
if BONSAI_REASONING_EFFORT=high validate_bonsai_settings; then exit 1; fi
for value in 0 65536 abc 18446744073709552128; do
    if validate_decimal BONSAI_PORT "$value" 1 65535; then exit 1; fi
done
echo 'Passed bounded context, port, and reasoning validation.'
