#!/usr/bin/env -S python3 -B
"""Read the public GHCR image's release labels without downloading its layers."""
import sys
sys.dont_write_bytecode = True

import json
import re
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = 'teaalc/ai_bonsai27'
REGISTRY = 'https://ghcr.io/v2/' + REPOSITORY + '/'
SOURCE = 'https://github.com/TeaAlc/ai_bonsai27'
ACCEPT = ', '.join([
    'application/vnd.oci.image.manifest.v1+json',
    'application/vnd.docker.distribution.manifest.v2+json',
    'application/vnd.oci.image.index.v1+json',
    'application/vnd.docker.distribution.manifest.list.v2+json',
])


def get_json(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    query = urllib.parse.urlencode({
        'service': 'ghcr.io', 'scope': f'repository:{REPOSITORY}:pull',
    })
    token = get_json('https://ghcr.io/token?' + query)['token']
    headers = {'Authorization': 'Bearer ' + token, 'Accept': ACCEPT}
    try:
        manifest = get_json(REGISTRY + 'manifests/latest', headers)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return
        raise

    # Also accept a multi-platform publication containing this project's image.
    if 'manifests' in manifest:
        matches = [item for item in manifest['manifests']
                   if item.get('platform', {}).get('os') == 'linux'
                   and item.get('platform', {}).get('architecture') == 'amd64']
        if len(matches) != 1:
            raise ValueError('published index has no unique linux/amd64 image')
        manifest = get_json(REGISTRY + 'manifests/' + matches[0]['digest'], headers)
    config = get_json(REGISTRY + 'blobs/' + manifest['config']['digest'], headers)
    labels = config.get('config', {}).get('Labels', {})
    version = labels.get('org.opencontainers.image.version', '')
    revision = labels.get('org.opencontainers.image.revision', '')
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('published image has no stable release version')
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('published image has no valid source revision')
    if labels.get('io.bonsai.git.dirty') != 'false':
        raise ValueError('published image was not built from a clean commit')
    if labels.get('org.opencontainers.image.source') != SOURCE:
        raise ValueError('published image belongs to a different source repository')
    print(version, revision)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not print authenticated requests or token data in error messages.
        print(f'Error: cannot verify the published GHCR release: {error}', file=sys.stderr)
        sys.exit(2)
