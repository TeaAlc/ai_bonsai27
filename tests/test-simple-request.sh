#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p /tmp/bonsai27
work=$(mktemp -d /tmp/bonsai27/request-test.XXXXXX)
trap 'rm -rf -- "$work"' EXIT
mkdir "$work/bin"
cat > "$work/bin/python3" <<'SH'
#!/usr/bin/env bash
[[ "$1" == -B ]] || exit 1
cat >/dev/null
[[ -r "$BONSAI_IMAGE_PATH" ]] || exit 1
printf '%s\n' "$BONSAI_BASE_URL"
SH
chmod +x "$work/bin/python3"
export PATH="$work/bin:$PATH"
unset BONSAI_BASE_URL
[[ $("$project/simple_request.sh") == http://localhost:8080 ]]
[[ $("$project/simple_request.sh" notebook) == http://notebook:8080 ]]
[[ $("$project/simple_request.sh" notebook:8081) == http://notebook:8081 ]]
[[ $(BONSAI_BASE_URL=http://example:9000 "$project/simple_request.sh") == http://example:9000 ]]
[[ $(BONSAI_BASE_URL=http://example:9000 "$project/simple_request.sh" notebook) == http://notebook:8080 ]]
for argument in host:0 host:65536 host:abc http://host; do
    if "$project/simple_request.sh" "$argument"; then exit 1; fi
done
echo 'Passed request host/port defaults, override, existing image, and validation.'
