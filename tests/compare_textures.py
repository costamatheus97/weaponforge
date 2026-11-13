"""Compare two sets of game textures on the texels the mesh uses (run inside Blender), e.g. a rebuild against a kept reference build:

    blender -b --factory-startup --python-exit-code 1 --python compare_textures.py -- <reference dir> <new dir> <Name> <cover.npy>

The textures come out of a path-traced bake, so two runs are never identical. What must hold: on the mesh's own texels the mean
difference stays under MEAN (in 8-bit steps) and fewer than SHARE of them move by more than BIG steps. The island padding
outside the mesh is not compared (that is where nearly all of the large differences sit, and nothing samples it).
"""
import os
import sys

import bpy
import numpy as np

MEAN, BIG, SHARE = 0.5, 8.0, 0.01


def load(path):
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = 'Non-Color'            # the stored values, not a colour-managed reading of them
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[:, :, :3] * 255.0


def main(argv):
    ref_dir, new_dir, name, cover_path = argv
    cover = np.load(cover_path) > 0.5
    bad = 0
    for suffix in ('BC', 'N', 'ORM'):
        fname = 'T_%s_%s.png' % (name, suffix)
        a, b = load(os.path.join(ref_dir, fname)), load(os.path.join(new_dir, fname))
        if a.shape != b.shape:
            print('DIFF %s: size %s -> %s' % (fname, a.shape[:2], b.shape[:2]))
            bad += 1
            continue
        mask = cover
        if mask.shape != a.shape[:2]:                     # a cover map baked at another size: take every n-th texel of it
            step = mask.shape[0] // a.shape[0]
            mask = mask[::step, ::step] if step >= 1 and mask.shape[0] % a.shape[0] == 0 else np.ones(a.shape[:2], dtype=bool)
        d = np.abs(a - b).max(axis=2)[mask]
        mean, share = float(d.mean()), float((d > BIG).mean())
        ok = mean <= MEAN and share <= SHARE
        bad += 0 if ok else 1
        print('%s %s: mean difference %.3f of 255, %.3f%% of the mesh texels differ by more than %d' % ('ok  ' if ok else 'DIFF', fname, mean, share * 100.0, BIG))
    print('compare_textures: %s' % ('%d textures differ' % bad if bad else 'the textures agree'))
    return bad


if __name__ == '__main__':
    if main(sys.argv[sys.argv.index('--') + 1:]):
        sys.exit(1)
