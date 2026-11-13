"""What review does with two builds whose textures differ in size (docs/review.md): the size is read from a PNG's header, the
difference goes in compare.json as a warning, and the warning says what to do about it. Plain Python, no Blender:

    python3 tests/test_review_textures.py
"""
import os
import struct
import sys
import tempfile
import zlib

import numpy as np

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge import review as RV  # noqa: E402

failed = []


def case(label, ok, detail=''):
    print('%s %s%s' % ('ok  ' if ok else 'FAIL', label, (' -> ' + str(detail)[:200]) if detail != '' else ''))
    if not ok:
        failed.append(label)


def png(path, w, h):
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(3 * w) for _ in range(h))
    with open(path, 'wb') as fh:
        fh.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw))
                 + chunk(b'IEND', b''))


with tempfile.TemporaryDirectory() as tmp:
    a = os.path.join(tmp, 'a.png')
    png(a, 64, 32)
    case('a PNG\'s size is read from its header', RV.png_size(a) == (64, 32), RV.png_size(a))
    case('a file that is not there has no size', RV.png_size(os.path.join(tmp, 'none.png')) is None)
    junk = os.path.join(tmp, 'junk.png')
    with open(junk, 'wb') as fh:
        fh.write(b'not a picture at all, not a picture at all')
    case('a file that is not a PNG has no size', RV.png_size(junk) is None)

    class Build:
        tex_dir = tmp
        tex_prefix = 'a'
    os.replace(a, os.path.join(tmp, 'a_BC.png'))
    case('texture_px reads the BC texture of a build', RV.texture_px(Build) == 64, RV.texture_px(Build))

info, warn = RV.texture_notes(4096, 4096, 4096)
case('the same size: nothing to say', info['differ'] is False and not warn, (info, warn))
info, warn = RV.texture_notes(4096, 1024, 4096)
case('different sizes: said, with both sizes and --size', info['differ'] is True and len(warn) == 1 and '4096' in warn[0]
     and '1024' in warn[0] and '--size 1024' in warn[0], (info, warn))
case('different sizes are pictured as each is', info['pictured'] == {'this': 4096, 'against': 1024}, info['pictured'])
info, warn = RV.texture_notes(4096, 1024, 1024)
case('different sizes under one --size: both pictured alike, and the figures still differ', info['differ'] is True
     and info['pictured'] == {'this': 1024, 'against': 1024} and 'same' not in warn[0] and 'each build\'s own size' in warn[0], (info, warn))
info, warn = RV.texture_notes(4096, None, 4096)
case('an unknown size is said and is not a difference', info['differ'] is None and len(warn) == 1 and 'not known' in warn[0], (info, warn))
case('the warning wraps to the sheet\'s width', all(len(l) <= 190 for l in RV._wrap(' '.join(['word'] * 200))), RV._wrap('a b')[:1])

img = np.zeros((10, 10, 4), dtype=np.uint8)
img[...] = (50, 50, 55, 255)
img[2:6, 2:8] = (210, 210, 210, 255)
case('the silhouette is the grey on the dark', int(RV.silhouette(img).sum()) == 24, int(RV.silhouette(img).sum()))

if failed:
    print('review textures: %d FAILED: %s' % (len(failed), ', '.join(failed)))
    sys.exit(1)
print('review textures: PASS')
