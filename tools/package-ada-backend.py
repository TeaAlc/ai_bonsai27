#!/usr/bin/env -S python3 -B
"""Compatibility entry point for the common runtime packager."""
import sys
sys.dont_write_bytecode = True
import runpy
from pathlib import Path
sys.argv.append('ada')
runpy.run_path(str(Path(__file__).with_name('package-backend.py')), run_name='__main__')
