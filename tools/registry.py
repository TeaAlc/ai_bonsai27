#!/usr/bin/env -S python3 -B
"""Verify a GHCR publication and promote the exact version manifest to latest."""
import sys
sys.dont_write_bytecode = True
import argparse
import base64
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request

SOURCE = 'https://github.com/TeaAlc/ai_bonsai27'
REPOSITORY = 'teaalc/ai_bonsai27'
ACCEPT = ', '.join(('application/vnd.oci.image.manifest.v1+json',
                    'application/vnd.docker.distribution.manifest.v2+json',
                    'application/vnd.oci.image.index.v1+json',
                    'application/vnd.docker.distribution.manifest.list.v2+json'))


def stable_version(value):
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value):
        raise ValueError('invalid stable image version')
    return tuple(map(int, value.split('.')))


def validate_receipt(receipt):
    stable_version(receipt['version'])
    if (not isinstance(receipt.get('dirty'), bool) or receipt.get('source') != SOURCE
            or not re.fullmatch(r'[0-9a-f]{40}', receipt.get('revision', ''))
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', receipt.get('image_id', ''))):
        raise ValueError('publication requires a project build receipt with valid source, cleanliness metadata, and image ID')


class Registry:
    def __init__(self, credentials):
        with open(credentials) as stream:
            login = json.load(stream)
        basic = base64.b64encode((login['username'] + ':' + login['token']).encode()).decode()
        query = urllib.parse.urlencode({'service': 'ghcr.io',
                                        'scope': f'repository:{REPOSITORY}:pull,push'})
        request = urllib.request.Request('https://ghcr.io/token?' + query,
                                         headers={'Authorization': 'Basic ' + basic})
        with urllib.request.urlopen(request, timeout=30) as response:
            self.token = json.load(response)['token']
        self.root = f'https://ghcr.io/v2/{REPOSITORY}/'

    def request(self, path, data=None, content_type=None):
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': ACCEPT}
        if content_type: headers['Content-Type'] = content_type
        request = urllib.request.Request(self.root + path, data=data, headers=headers,
                                         method='PUT' if data is not None else 'GET')
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404 and data is None: return None
            raise

    def image(self, tag):
        raw = self.request('manifests/' + tag)
        if raw is None: return None
        manifest = json.loads(raw)
        selected = manifest
        if 'manifests' in manifest:
            candidates = [entry for entry in manifest['manifests']
                          if entry.get('platform', {}).get('os') == 'linux'
                          and entry.get('platform', {}).get('architecture') == 'amd64']
            if len(candidates) != 1: raise ValueError('registry index has no unique linux/amd64 image')
            child_raw = self.request('manifests/' + candidates[0]['digest'])
            if 'sha256:' + hashlib.sha256(child_raw).hexdigest() != candidates[0]['digest']:
                raise ValueError('registry child manifest digest mismatch')
            selected = json.loads(child_raw)
        config_id = selected['config']['digest']
        config_raw = self.request('blobs/' + config_id)
        if 'sha256:' + hashlib.sha256(config_raw).hexdigest() != config_id:
            raise ValueError('registry image config digest mismatch')
        labels = json.loads(config_raw).get('config', {}).get('Labels', {})
        if labels.get('org.opencontainers.image.source') != SOURCE or labels.get('io.bonsai.git.dirty') not in ('false', 'true'):
            raise ValueError('remote image is not a project build')
        version = labels.get('org.opencontainers.image.version', '')
        stable_version(version)
        revision = labels.get('org.opencontainers.image.revision', '')
        if not re.fullmatch(r'[0-9a-f]{40}', revision): raise ValueError('invalid remote source revision')
        return {'raw': raw, 'manifest': manifest, 'image_id': config_id,
                'version': version, 'revision': revision,
                'digest': 'sha256:' + hashlib.sha256(raw).hexdigest()}

    def promote(self, receipt):
        # Validate the image that was actually pushed, then copy its manifest.
        # Existing version/latest contents impose no publication policy gates.
        validate_receipt(receipt)
        version = self.image(receipt['version'])
        if not version: raise ValueError('version publication is missing')
        if any(version[key] != receipt[key] for key in ('version', 'revision', 'image_id')):
            raise ValueError('published image does not match the build just pushed')
        self.request('manifests/latest', version['raw'], version['manifest']['mediaType'])
        latest = self.image('latest')
        if latest['digest'] != version['digest']: raise ValueError('remote version/latest digests differ')
        return latest['digest']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('promote',))
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--credentials', required=True)
    args = parser.parse_args()
    try:
        with open(args.receipt) as stream: receipt = json.load(stream)
        validate_receipt(receipt)
        registry = Registry(args.credentials)
        print(getattr(registry, args.action)(receipt))
    except Exception as error:
        # Never include authenticated request objects or credentials in errors.
        message = f'HTTP {error.code}' if isinstance(error, urllib.error.HTTPError) else str(error)
        print(f'Error: registry publication check failed: {message}', file=sys.stderr)
        sys.exit(2)
