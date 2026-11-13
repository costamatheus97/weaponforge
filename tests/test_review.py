"""The review's figures on a synthetic case whose answers are known (review.figures; about five seconds):

    blender -b --factory-startup --python-exit-code 1 --python tests/test_review.py
    tests/review.sh                     runs this, test_critic.py, test_review_definition.py and the launcher's paths

Two flat plates 10 x 10 cm side by side, face on to a camera 60 cm away, with two 1 cm screws behind the left one and a 1 cm
button on its own behind the right one:

  * the left plate (part Body) has 0.5 x 0.5 of the sheet: 0.5 * 2048 / 10 = 102.4 px/cm; the right (part Plate) 0.125 x 0.125:
    25.6 px/cm. Half the weapon's pixels are at 80 px/cm or more; the mean (root mean square) is 74.6 px/cm
  * the ID map gives the left plate one kind, the left half of the right plate another and nothing under the rest: shares
    0.5, 0.25 and 0.25 none; two kinds over 2 %; the right plate's right half (2 triangles) and the button (12, its UVs on a
    blank texel) have no kind
  * hardware: the two screws (pieces of Body); the button is a whole part on its own and is not counted; nor are the plates
  * with nothing baked on them each plate is a bare stretch of about (10 - 2 x 1 cm) squared; with detail everywhere none is
  * held(): a figure under its limit is a miss, a weapon's review_limits moves the limit, one that was not measured is a miss

Saves nothing. Exits 1 when a case fails.
"""
import math
import os
import sys

import bpy
import numpy as np

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge import review as RV, uv as U, weapon as W  # noqa: E402

failed = []
SIZE = 2048
N = 256                     # the synthetic maps' size: the figures read them by UV, whatever their size


def result(label, ok, detail=''):
    print('review: %s %s%s' % ('ok  ' if ok else 'FAIL', label, (' -> ' + str(detail)[:170]) if detail != '' else ''), flush=True)
    if not ok:
        failed.append(label)


def near(a, b, tol):
    return a is not None and abs(a - b) <= tol


def part(name, quads, uvs):
    """An object of quads (4 corners each, cm, weapon frame) with one UV per corner; corners in the same place are one vertex,
    as in a modelled part (a cube is one piece, not six)."""
    verts, faces, loops, index = [], [], [], {}
    for q, u in zip(quads, uvs):
        face = []
        for p in q:
            key = tuple(round(float(c), 6) for c in p)
            if key not in index:
                index[key] = len(verts)
                verts.append(key)
            face.append(index[key])
        faces.append(tuple(face))
        loops += list(u)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    layer = me.uv_layers.new(name=U.UV_NAME)
    for k, uv in enumerate(loops):
        layer.data[k].uv = uv
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def plate(x0, x1, z0, z1, y=0.0):
    return [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]


def cube(c, s=1.0):
    """The 6 faces of a cube of side s round c."""
    x, y, z = c
    h = s / 2.0
    p = [(x + dx * h, y + dy * h, z + dz * h) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    idx = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return [[p[i] for i in f] for f in idx]


def square(u0, v0, s):
    return [(u0, v0), (u0 + s, v0), (u0 + s, v0 + s), (u0, v0 + s)]


bpy.ops.wm.read_factory_settings(use_empty=True)
w = W.load('_template')
codes = RV.kind_codes(w)
result('the template\'s kinds have codes and none is all off (all off is "no kind")',
       len(codes) >= 2 and (0, 0, 0) not in codes, codes)
(code1, kind1), (code2, kind2) = sorted(codes.items())[:2]

# the left plate with two screws behind it (one part), the right plate as two halves (one piece), a button alone
screw_uv = [square(0.1, 0.1, 0.0)] * 6
body = part('Body', [plate(-10, 0, -5, 5)] + cube((-7, 5, 0)) + cube((-3, 5, 0)), [square(0.0, 0.0, 0.5)] + screw_uv * 2)
right = part('Plate', [plate(0, 5, -5, 5), plate(5, 10, -5, 5)],
             [[(0.5, 0.0), (0.5625, 0.0), (0.5625, 0.125), (0.5, 0.125)],
              [(0.5625, 0.0), (0.625, 0.0), (0.625, 0.125), (0.5625, 0.125)]])
button = part('Button', cube((5, 5, 0)), [square(0.9, 0.9, 0.0)] * 6)
objs = [body, right, button]

ident = np.zeros((N, N, 4), dtype=np.uint8)          # row 0 is v = 0, as the bake writes bake/id.npy
ident[:N // 2, :N // 2, :3] = np.array(code1) * 255
ident[:N // 8, N // 2:N * 9 // 16, :3] = np.array(code2) * 255
blank = {'id': ident, 'masks': np.zeros((N, N, 4), dtype=np.uint8), 'marks': None}

cam = {'loc': [0.0, -60.0, 0.0], 'right': [1.0, 0.0, 0.0], 'up': [0.0, 0.0, 1.0], 'fwd': [0.0, 1.0, 0.0],
       'tan': math.tan(math.radians(30.0)), 'res': [600, 300]}
cams = {'fp': cam, 'ads': cam, 'front': cam}
f = RV.figures(w, objs, blank, cams=cams, size=SIZE, marks=['m1', 'm2', 'm3'])

rms = math.sqrt((102.4 ** 2 + 25.6 ** 2) / 2.0)
result('hip view px/cm: the root mean square of 102.4 and 25.6', near(f['fp_px_cm'], rms, 0.02 * rms), f['fp_px_cm'])
result('hip view: half the pixels at 80 px/cm or more', near(f['fp_sharp_share'], 0.5, 0.02), f['fp_sharp_share'])
result('aiming view: the same camera, the same figures', f['ads_px_cm'] == f['fp_px_cm'] and f['ads_sharp_share'] == f['fp_sharp_share'])
shares = f['fp_kind_shares']
result('kind shares 0.5 %s, 0.25 %s, 0.25 none' % (kind1, kind2),
       near(shares.get(kind1), 0.5, 0.02) and near(shares.get(kind2), 0.25, 0.02) and near(shares.get('none'), 0.25, 0.02), shares)
result('two kinds over 2 % in the hip view (none is not a kind)', f['fp_kinds'] == 2 and f['front_kinds'] == 2,
       (f['fp_kinds'], f['front_kinds']))
result('the share of what the views see with no kind', near(f['no_kind_seen'], 0.25, 0.02), f['no_kind_seen'])
result('faces with no kind: the right half of Plate (2) and the button (12)',
       f['no_kind_tris'] == 14 and f['no_kind_by_part'] == {'Plate': 2, 'Button': 12}, (f['no_kind_tris'], f['no_kind_by_part']))
result('surface: two plates of 100 cm2 and three 1 cm cubes', near(f['surface_cm2'], 218.0, 1e-6), f['surface_cm2'])
result('hardware: the two screws of Body, not the button on its own, not the plates',
       f['pieces'] == 2 and f['pieces_by_part'] == {'Body': 2}, (f['pieces'], f['pieces_by_part']))
result('hardware and marks per 100 cm2', near(f['pieces_per_100cm2'], 200.0 / 218.0, 1e-9) and f['marks'] == 3
       and near(f['marks_per_100cm2'], 300.0 / 218.0, 1e-9), (f['pieces_per_100cm2'], f['marks_per_100cm2']))
result('bare: a plate less 1 cm round its outline, about 8 x 8 cm2', 50.0 < f['fp_bare_cm2'] < 72.0,
       (f['fp_bare_cm2'], f['fp_bare_part']))

busy = dict(blank, masks=np.full((N, N, 4), 255, dtype=np.uint8))
g = RV.figures(w, objs, busy, cams=cams, size=SIZE)
result('bare: none where the bake found detail everywhere', g['fp_bare_cm2'] == 0.0 and g['front_bare_cm2'] == 0.0,
       (g['fp_bare_cm2'], g['front_bare_cm2']))
result('marks are not counted when none are given', 'marks' not in g and 'marks_per_100cm2' not in g)

# ---- held(): what a weapon that opts in is held to
rows = {k: ok for k, ok, _v, _l, _w in RV.held(w, f)}
result('held: every figure in LIMITS is a row', set(rows) == set(RV.LIMITS), sorted(rows))
result('held: 0.5 of the hip view sharp is under 0.60, a miss; 2 kinds under 3, a miss',
       rows['fp_sharp_share'] is False and rows['fp_kinds'] is False)
result('held: 0.92 hardware and 1.38 marks per 100 cm2 pass', rows['pieces_per_100cm2'] and rows['marks_per_100cm2'])


class Looser:
    review = 'first_person'
    review_limits = {'fp_sharp_share': 0.4, 'fp_kinds': 2}


rows = {k: (ok, lim) for k, ok, _v, lim, _w in RV.held(Looser(), f)}
result('held: review_limits moves a limit', rows['fp_sharp_share'] == (True, 'at least 0.4') and rows['fp_kinds'] == (True, 'at least 2'),
       rows)
rows = {k: (ok, lim) for k, ok, _v, lim, _w in RV.held(w, g)}
result('held: a figure that was not measured (no marks) is a miss', rows['marks_per_100cm2'][0] is False, rows['marks_per_100cm2'])

if failed:
    print('review: %d FAILED: %s' % (len(failed), ', '.join(failed)))
    sys.exit(1)
print('review: PASS')
