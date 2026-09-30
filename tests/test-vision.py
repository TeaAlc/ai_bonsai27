#!/usr/bin/env -S python3 -B
"""Identify two known shapes through the actual vision API."""
import sys
sys.dont_write_bytecode = True
import base64
import json
import struct
import time
import zlib
from api_support import call, save, RUN_DIR, identity


def png_chunk(kind, content):
    return (struct.pack('!I', len(content)) + kind + content
            + struct.pack('!I', zlib.crc32(kind + content) & 0xffffffff))


def image_fixture(name):
    width = height = 384
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            if name == 'red-square':
                inside = 90 <= x < 294 and 90 <= y < 294
                color = (230, 20, 20)
            else:
                inside = (x - 192)**2 + (y - 192)**2 < 105**2
                color = (20, 40, 230)
            row.extend(color if inside else (255, 255, 255))
        rows.append(b'\x00' + row)
    return (b'\x89PNG\r\n\x1a\n'
            + png_chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
            + png_chunk(b'IDAT', zlib.compress(b''.join(rows)))
            + png_chunk(b'IEND', b''))


identity()
output = RUN_DIR / 'vision'
output.mkdir(parents=True, exist_ok=True)
summary = []
for name, expected in [('red-square', ('red', 'square')), ('blue-circle', ('blue', 'circle'))]:
    png = image_fixture(name)
    (output / (name + '.png')).write_bytes(png)
    data = {
        'model': 'bonsai2-27b',
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'Identify the single colored shape in this image. Answer in English with just its color and shape.'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(png).decode()}},
        ]}],
        'temperature': 0, 'max_tokens': 128,
        'chat_template_kwargs': {'enable_thinking': False},
    }
    started = time.monotonic()
    response = call('/v1/chat/completions', data)
    save('vision/' + name, response)
    answer = response['choices'][0]['message']['content']
    item = {'fixture': name, 'answer': answer,
            'passed': all(word in answer.lower() for word in expected),
            'wall_seconds': time.monotonic() - started, 'timings': response.get('timings')}
    summary.append(item)
    print(json.dumps(item), flush=True)
save('vision/summary', summary)
assert all(item['passed'] for item in summary), 'Vision test failed'
