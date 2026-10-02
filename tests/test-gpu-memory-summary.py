#!/usr/bin/env -S python3 -B
"""Verify benchmark interval filtering and unknown GPU memory counters."""
import sys
sys.dont_write_bytecode = True
import datetime
import runpy
import unittest
from pathlib import Path

summarize = runpy.run_path(str(Path(__file__).with_name('summarize-gpu-memory.py')))['summarize']


class MemorySummaryTests(unittest.TestCase):
    def test_filters_startup_and_preserves_real_samples(self):
        end = datetime.datetime.now().astimezone()
        report = {'recorded_at': end.isoformat(), 'wall_seconds': 3}
        rows = ['timestamp, memory.used [MiB]']
        for offset, memory in ((-5, '9999 MiB'), (-2, '1200 MiB'),
                               (-1, '1400 MiB'), (1, '8888 MiB')):
            instant = end + datetime.timedelta(seconds=offset)
            rows.append(f'{instant:%Y/%m/%d %H:%M:%S.%f}, {memory}')
        result = summarize(report, '\n'.join(rows))
        self.assertEqual(result['samples'], 2)
        self.assertEqual(result['mean_used_mib'], 1300)
        self.assertEqual(result['peak_used_mib'], 1400)

    def test_unknown_memory_is_null(self):
        report = {'recorded_at': datetime.datetime.now().astimezone().isoformat(), 'wall_seconds': 3}
        result = summarize(report, 'timestamp, memory.used [MiB]\ninvalid, N/A')
        self.assertEqual(result['samples'], 0)
        self.assertIsNone(result['peak_used_mib'])
        self.assertIsNone(result['mean_used_mib'])


if __name__ == '__main__':
    unittest.main()
