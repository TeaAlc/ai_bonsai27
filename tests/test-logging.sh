#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
mkdir -p /tmp/bonsai27
work=$(mktemp -d /tmp/bonsai27/logging-test.XXXXXX)
trap 'rm -rf -- "$work"' EXIT
# A trapped failure preserves its status and identifies the current operation.
# It must not echo the command, which could carry credentials.
set +e
bash -c 'source data/logging.sh; set -euo pipefail; bonsai_init_logging fixture; bonsai_step registry-login "Testing failure context."; bash -c "exit 17" secret-fixture-token' > "$work/output" 2> "$work/error"
status=$?
set -e
[[ "$status" == 17 ]]
[[ $(< "$work/error") == *'[fixture] [registry-login] [ERROR] Step failed (exit=17,'* ]]
[[ $(< "$work/error") != *'secret-fixture-token'* ]]
[[ ! -s "$work/output" ]]
# Logs from functions used in command substitutions never corrupt stdout.
value=$(bash -c 'source data/logging.sh; bonsai_init_logging fixture; bonsai_step version "Calculating."; echo 1.2.3' 2> "$work/info")
[[ "$value" == 1.2.3 && $(< "$work/info") == *'[version] [INFO]'* ]]
echo 'Passed stage logging, original exit status, stdout separation, and secret redaction checks.'
