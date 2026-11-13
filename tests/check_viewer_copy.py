#!/usr/bin/env python3
"""The viewer copy must show what the game gets: its textures are the game's own, at their size and without loss.

    python3 tests/check_viewer_copy.py <the .glb> <the weapon's textures folder> <Name>

A copy with smaller or JPEG textures is blurred, and JPEG leaves a grainy halo round engraved lettering in the normal and
roughness maps that polished steel shows at once; judged by such a copy a weapon looks blurry and granulated
where the game's textures are clean (PLAYBOOK "Rig and export", item 8). Needs Pillow and numpy.
"""
import io
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def images(path):
    """{'colour' | 'normal' | 'orm': (mime type, PIL image)} of the first material of a .glb."""
    data = open(path, 'rb').read()
    if data[:4] != b'glTF':
        raise SystemExit('%s is not a .glb' % path)
    size, _kind = struct.unpack('<II', data[12:20])
    doc = json.loads(data[20:20 + size])
    start = 20 + size
    length, _kind = struct.unpack('<II', data[start:start + 8])
    blob = data[start + 8:start + 8 + length]
    mat = doc['materials'][0]
    pbr = mat['pbrMetallicRoughness']
    out = {}
    for key, tex in (('colour', pbr['baseColorTexture']), ('normal', mat['normalTexture']), ('orm', pbr['metallicRoughnessTexture'])):
        img = doc['images'][doc['textures'][tex['index']]['source']]
        view = doc['bufferViews'][img['bufferView']]
        raw = blob[view.get('byteOffset', 0):view.get('byteOffset', 0) + view['byteLength']]
        out[key] = (img.get('mimeType'), Image.open(io.BytesIO(raw)))
    return out


def main():
    glb, tex_dir, name = sys.argv[1:4]
    wrong = []
    for key, (mime, img) in images(glb).items():
        game = Image.open(os.path.join(tex_dir, 'T_%s_%s.png' % (name, {'colour': 'BC', 'normal': 'N', 'orm': 'ORM'}[key])))
        if mime != 'image/png':
            wrong.append('%s is %s, not a lossless PNG' % (key, mime))
        if img.size != game.size:
            wrong.append('%s is %d px, the game texture is %d px' % (key, img.size[0], game.size[0]))
            continue
        a = np.asarray(img.convert('RGB'), dtype=np.int16)
        b = np.asarray(game.convert('RGB'), dtype=np.int16)
        worst = int(np.abs(a - b).max())
        if worst > 1:
            wrong.append('%s differs from the game texture by up to %d of 255' % (key, worst))
    if wrong:
        print('check_viewer_copy: FAIL  %s: %s' % (glb, '; '.join(wrong)))
        return 1
    print('check_viewer_copy: PASS  %s carries the three game textures at their size, unchanged' % os.path.basename(glb))
    return 0


if __name__ == '__main__':
    sys.exit(main())
