"""How much two PNG pictures differ, without Pillow: python3 tests/png_diff.py A.png B.png [MIN_SHARE]

Prints the share of pixels in which a channel moved by more than 12 of 255 (review.DIFF_LEVEL) and exits 1 when it is under MIN_SHARE
(default 0.0: never), 2 when the pictures cannot be compared. Reads 8-bit, non-interlaced PNGs of any colour type Blender writes."""
import struct
import sys
import zlib

import numpy as np


def read(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('%s is not a PNG' % path)
    pos, idat, head = 8, b'', None
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b'IHDR':
            head = struct.unpack('>IIBBBBB', body)
        elif kind == b'IDAT':
            idat += body
        pos += 12 + n
    w, h, depth, ctype, _c, _f, interlace = head
    if depth != 8 or interlace:
        raise ValueError('%s: only 8-bit, non-interlaced PNGs' % path)
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = np.frombuffer(zlib.decompress(idat), dtype=np.uint8).reshape(h, 1 + w * ch)
    rows = np.zeros((h, w * ch), dtype=np.int32)
    for y in range(h):
        f, line = raw[y, 0], raw[y, 1:].astype(np.int32)
        up = rows[y - 1] if y else np.zeros(w * ch, dtype=np.int32)
        if f == 0:
            cur = line
        elif f == 2:
            cur = (line + up) & 255
        else:                                           # 1 (sub), 3 (average) and 4 (Paeth) depend on the pixel to the left
            cur = np.zeros(w * ch, dtype=np.int32)
            for x in range(w * ch):
                a = cur[x - ch] if x >= ch else 0
                b = up[x]
                c = up[x - ch] if x >= ch else 0
                if f == 1:
                    pred = a
                elif f == 3:
                    pred = (a + b) // 2
                else:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
                cur[x] = (line[x] + pred) & 255
        rows[y] = cur
    return rows.reshape(h, w, ch)[..., :3]


if __name__ == '__main__':
    try:
        a, b = read(sys.argv[1]), read(sys.argv[2])
    except (ValueError, KeyError, OSError) as err:
        print('png_diff: %s' % err)
        sys.exit(2)
    if a.shape != b.shape:
        print('png_diff: %s against %s' % (a.shape, b.shape))
        sys.exit(2)
    share = float((np.abs(a - b).max(axis=2) > 12).mean())
    print('png_diff: %.4f of the pixels differ' % share)
    sys.exit(1 if share < float(sys.argv[3] if len(sys.argv) > 3 else 0.0) else 0)
