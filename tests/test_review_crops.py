"""The review's crops are cut from the picture straight from the side a thing is on (review.crop_plan; about five seconds):

    blender -b --factory-startup --python-exit-code 1 --python tests/test_review_crops.py

A synthetic gun: a body 24 cm long, 4 wide and 8 high (+Y is the weapon's left), a lever on its left wall (part LeverL), one on its
right (LeverR), a mark lying on each wall, the left one larger. Cameras stand straight from each side, and a "front" camera on the
right-hand side as the old front picture was on the SMG. Saves nothing. Exits 1 when a case fails.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge import review as RV, uv as U  # noqa: E402

failed = []


def result(label, ok, detail=''):
    print('crops: %s %s%s' % ('ok  ' if ok else 'FAIL', label, (' -> ' + str(detail)[:200]) if detail != '' else ''), flush=True)
    if not ok:
        failed.append(label)


def box(name, lo, hi, bone, mat='steel'):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    p = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(p, [], faces)
    me.update()
    bm = bmesh.new()                                     # cut into small faces: a part is seen by the middles of its triangles
    bm.from_mesh(me)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.uv_layers.new(name=U.UV_NAME)
    ob = bpy.data.objects.new(name, me)
    ob['bone'], ob['mat'] = bone, mat
    bpy.context.scene.collection.objects.link(ob)
    return ob


def camera(eye, look, res=(800, 600), angle=math.radians(50)):
    """A recorded hero shot: the matrix of a camera at `eye` looking along `look` (Blender cameras look down -Z)."""
    look = Vector(look).normalized()
    m = look.to_track_quat('-Z', 'Y').to_matrix().to_4x4()
    m.translation = Vector(eye)
    return {'camera': [list(r) for r in m], 'angle': angle, 'res': list(res), 'lens': 50.0}


class Gun:
    sockets = []
    props = []

    def with_children(self, bones):
        return bones


bpy.ops.wm.read_factory_settings(use_empty=True)
body = box('Body', (-12, -2, -4), (12, 2, 4), 'Root')
lever_l = box('LeverL', (-1, 2.0, -1), (1, 3.0, 1), 'LeverBoneL')
lever_r = box('LeverR', (-1, -3.0, -1), (1, -2.0, 1), 'LeverBoneR')
mesh = RV._mesh([body, lever_l, lever_r])
tree = RV._tree(mesh)


def quad(y, x0, x1, z0, z1):
    return np.array([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], dtype=np.float64)


marks = [('MarkL', quad(2.0, -9, 0, -3, 3)), ('MarkR', quad(-2.0, 4, 8, -2, 2))]
record = {'to_world': [list(r) for r in Matrix.Identity(4)], 'shots': {
    '_left': camera((0, 60, 0), (0, -1, 0)), '_right': camera((0, -60, 0), (0, 1, 0)),
    '': camera((70, -40, 5), (-1, 0.6, -0.05)),                  # the front picture on the right-hand side
    '_rear': camera((-70, -40, 5), (1, 0.6, -0.05)),
    '_outline': {'camera': [list(r) for r in Matrix.Identity(4)], 'type': 'ORTHO', 'ortho_scale': 0.4, 'res': [1200, 800]}}}

result('an orthographic shot has no camera to project with', RV.shot_camera(record, '_outline') is None)
result('a perspective one has', RV.shot_camera(record, '_left') is not None)

plan, notes = RV.crop_plan(Gun(), mesh, tree, record, marks)
by = {c['name']: c for c in plan}
names = sorted(by)
result('plan: %s' % ', '.join(names), True)
result('the lever on the left is cropped from the left picture', by.get('control_leverl', {}).get('shot') == '_left', by.get('control_leverl'))
result('the lever on the right is cropped from the right picture', by.get('control_leverr', {}).get('shot') == '_right',
       by.get('control_leverr'))
result('the largest mark (on the left) is cropped from the left picture', by.get('marks', {}).get('shot') == '_left', by.get('marks'))
result('the right one gets a crop of its own, from the right picture', by.get('marks_right', {}).get('shot') == '_right', by.get('marks_right'))
result('the left one is not cropped twice', 'marks_left' not in by, names)
result('the body\'s wall on each side is cropped from that side', by.get('wall_left_body', {}).get('shot') == '_left'
       and by.get('wall_right_body', {}).get('shot') == '_right', [by.get('wall_left_body'), by.get('wall_right_body')])
result('the side outline is the whole outline picture', by.get('side_outline', {}).get('box') == [0, 0, 1200, 800], by.get('side_outline'))
result('nothing was left out that should be there', not [n for n in notes if n.startswith(('control_', 'marks', 'wall_', 'side_outline'))], notes)

# the old way: the front picture alone (on the right-hand side): the left lever is not seen in it
old = {k: v for k, v in record['shots'].items() if k in ('', '_rear')}
plan2, notes2 = RV.crop_plan(Gun(), mesh, tree, {'to_world': record['to_world'], 'shots': old}, marks)
result('with only the front and rear pictures the left lever has no crop, which is what the side pictures are for',
       'control_leverl' not in {c['name'] for c in plan2} and any(n.startswith('control_leverl') for n in notes2), notes2)

# a wide wall is split, side by side, and never cut round its middle
pieces = RV._pieces([100.0, 50.0, 2000.0, 400.0])
result('a wall 1900 px wide is three crops side by side', len(pieces) == 3 and pieces[0][0] == 100.0 and pieces[-1][2] == 2000.0
       and all(abs((p[2] - p[0]) - 1900.0 / 3) < 1e-6 for p in pieces), pieces)
result('a narrow one is one', len(RV._pieces([0.0, 0.0, 500.0, 300.0])) == 1)
result('the side of a thing is by its middle off the weapon\'s middle plane (+Y the left)',
       RV._side_of(np.array([[0, 2.0, 0], [0, 3.0, 0]])) == '_left' and RV._side_of(np.array([[0, -2.0, 0]])) == '_right'
       and RV._side_of(np.array([[0, 0.1, 0]])) is None)

if failed:
    print('crops: %d FAILED: %s' % (len(failed), ', '.join(failed)))
    sys.exit(1)
print('crops: PASS')
