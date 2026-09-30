#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p /tmp/bonsai27
work_dir=$(mktemp -d /tmp/bonsai27/cuda-probe-test.XXXXXX)
trap 'rm -rf -- "$work_dir"' EXIT

# Test the actual dynamically loaded Driver API calls using a tiny fake driver.
# A host C compiler is required for this test; no CUDA toolkit or GPU is needed.
cc -O2 -Wall -Wextra -Werror "$project_dir/data/gpu/compute-capability.c" \
    -ldl -o "$work_dir/probe"
cat > "$work_dir/driver.c" <<'C'
#include <stdlib.h>
int cuInit(unsigned int flags) { (void)flags; return getenv("FAIL_CUDA") ? 100 : 0; }
int cuDeviceGet(int *device, int ordinal) { *device = ordinal; return 0; }
int cuDeviceGetAttribute(int *value, int attribute, int device) {
    if (device != 0) return 101;
    if (attribute == 75) *value = 12;
    else if (attribute == 76) *value = 0;
    else return 1;
    return 0;
}
C
cc -shared -fPIC -Wall -Wextra -Werror "$work_dir/driver.c" -o "$work_dir/libcuda.so.1"
[[ $(LD_LIBRARY_PATH="$work_dir" "$work_dir/probe") == 12.0 ]]
if FAIL_CUDA=1 LD_LIBRARY_PATH="$work_dir" "$work_dir/probe"; then
    echo 'Error: failed CUDA initialization was accepted.' >&2
    exit 1
fi
echo 'Passed CUDA capability query and driver error handling.'
