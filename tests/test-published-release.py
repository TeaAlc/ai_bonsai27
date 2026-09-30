#!/usr/bin/env -S python3 -B
"""Validate registry labels without making network requests."""
import sys
sys.dont_write_bytecode = True

import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'published_release', Path(__file__).resolve().parents[1] / 'tools/published-release.py',
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class PublishedReleaseTests(unittest.TestCase):
    def setUp(self):
        self.labels = {
            'org.opencontainers.image.version': '1.2.1',
            'org.opencontainers.image.revision': 'a' * 40,
            'io.bonsai.git.dirty': 'false',
            'org.opencontainers.image.source': release.SOURCE,
        }

    def query(self, labels, indexed=False):
        responses = [{'token': 'fixture-secret'}]
        if indexed:
            responses.append({'manifests': [{
                'digest': 'fixture-manifest',
                'platform': {'os': 'linux', 'architecture': 'amd64'},
            }]})
        responses.extend([
            {'config': {'digest': 'fixture-config'}},
            {'config': {'Labels': labels}},
        ])
        output = io.StringIO()
        with patch.object(release, 'get_json', side_effect=responses):
            with contextlib.redirect_stdout(output):
                release.main()
        self.assertNotIn('fixture-secret', output.getvalue())
        return output.getvalue().strip()

    def test_manifest_and_index(self):
        for indexed in (False, True):
            self.assertEqual(self.query(self.labels, indexed), '1.2.1 ' + 'a' * 40)

    def test_reject_invalid_release_labels(self):
        for name, value in [
            ('org.opencontainers.image.version', 'bad'),
            ('org.opencontainers.image.revision', 'bad'),
            ('io.bonsai.git.dirty', 'true'),
            ('org.opencontainers.image.source', 'other'),
        ]:
            with self.subTest(label=name), self.assertRaises(ValueError):
                self.query(dict(self.labels, **{name: value}))


if __name__ == '__main__':
    unittest.main()
