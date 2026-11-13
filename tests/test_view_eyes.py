"""One truth for the player's eye (view.eye_shots, stages.eyes): the grey sheet of what the hip and aiming eyes see is taken with the
cameras `hero` takes its `fp` and `ads` pictures and the review its figures from, from the model alone, and the sheets' "fp" views
look from the hip eye's side. About fifteen seconds:

    blender -b --factory-startup --python-exit-code 1 --python tests/test_view_eyes.py -- <scratch folder>

Builds the template's model under the scratch folder (nothing else is touched). Exits 1 when a case fails.
"""
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge import hero, review as RV, stages, view as V, weapon as W  # noqa: E402

failed = []


def result(label, ok, detail=''):
    print('eyes: %s %s%s' % ('ok  ' if ok else 'FAIL', label, (' -> ' + str(detail)[:200]) if detail != '' else ''), flush=True)
    if not ok:
        failed.append(label)


root = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
w = W.load('_template', root=root)
stages.model(w, quiet=True)
lp = stages.parts(w, 'LP')

rig, centre = stages.eyes(w, lp)
cams = RV.eye_cameras(w, RV.length_m(RV._mesh(lp)))
result('the eyes are the review figures\' own (%s)' % ', '.join(sorted(rig)), set(rig) == set(cams) and 'fp' in rig, sorted(cams))
same = all(np.allclose(list(rig[k][0]), cams[k]['loc'], atol=1e-6) and np.allclose(list(rig[k][1].normalized()), cams[k]['fwd'], atol=1e-6)
           for k in rig)
result('every eye and its way of looking are the same numbers', same, {k: (list(rig[k][0]), cams[k]['loc']) for k in rig})

hip = rig['fp'][0] - centre
fp_dir = stages._sided(['fp', 'left'], (rig, centre))
result('"fp" turns into the direction from the model to the hip eye, "left" stays', fp_dir[1] == 'left' and
       np.allclose(fp_dir[0], list(hip), atol=1e-9), fp_dir)
result('which is on the weapon\'s left (+Y), where hero\'s hip camera is, not where the old fixed "fp" view was',
       fp_dir[0][1] > 0.0 and V.VIEW['fp'][1] > 0.0, (fp_dir[0], V.VIEW['fp']))
result('without a rig the name stays and means the fixed view', stages._sided(['fp'], None) == ['fp'])

paths = stages.render(w, what=['eyes'], res=(320, 200))
names = sorted(os.path.basename(p) for p in paths)
result('"eyes" writes the two sheets and nothing else', names == ['grey_game_parts_eyes.png', 'grey_high_detail_eyes.png'], names)
img = bpy.data.images.load(paths[0])
tile = (stages.EYES_W, stages.EYES_W * 9 // 16)
result('a tile is 16:9, one above the other, one a camera', img.size[0] == tile[0] and img.size[1] == tile[1] * len(rig),
       (tuple(img.size), tile, len(rig)))
px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
img.pixels.foreach_get(px)
px = px.reshape(img.size[1], img.size[0], 4)[..., :3]
top = px[img.size[1] - tile[1]:]                       # image rows run bottom-up: the first camera is the top tile
result('the model is in the first picture', float((np.abs(top - top[2, 2]).max(axis=2) > 0.05).mean()) > 0.003,
       float((np.abs(top - top[2, 2]).max(axis=2) > 0.05).mean()))

if failed:
    print('eyes: %d FAILED: %s' % (len(failed), ', '.join(failed)))
    sys.exit(1)
print('eyes: PASS')
