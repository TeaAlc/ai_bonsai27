#!/usr/bin/env -S python3 -B
"""Fail before compilation when the real injected CUDA driver cannot initialize."""
import sys
sys.dont_write_bytecode = True
import ctypes

try:
    driver = ctypes.CDLL('libcuda.so.1')
    status = driver.cuInit(0)
    if status != 0:
        raise RuntimeError(f'cuInit returned {status}')
except (OSError, RuntimeError) as error:
    raise SystemExit(f'Error: compiler CUDA driver preflight failed: {error}')
print('Compiler CUDA driver preflight passed.', flush=True)
