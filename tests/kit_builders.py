"""The shared builders from scratch, on a weapon defined here and nowhere else (tests/kit_builders.sh runs it; under a minute):

    blender -b --factory-startup --python-exit-code 1 --python tests/kit_builders.py -- <scratch root>

KitGun is a short receiver skinned over a faceted section that changes along it (forms.section_loft over sections.facet_ring),
a flute pressed into each side and a boss round a takedown pin (forms.pocket, forms.boss), socket-head screws, selector
pictograms, ejector-pin marks and a parting line found on its surface (fittings), a riveted data plate in a recess, a rail with
both iron sights clamped on it (sights.rear_aperture, sights.front_post: every dimension left to its default), and a barrel with
a castellated nut, a gas block and a flash hider (barrels). The sights and the barrel's parts are AssaultG3's own designs and
are imported from weapons/assault_g3 (sights.py, barrels.py); the loft, the fittings and the kit are the shared builders under
test. It passes when:

  * every builder runs and leaves tagged parts (the stage "model"), and every check that can be measured on the grey parts
    passes: the brief, the sockets measured against the mesh (the front post's tip, the rear aperture's centre, the muzzle),
    no part inside out
  * after the stage "uv" (which finishes the game mesh), the mesh checks pass as well: closed, all triangles, no triangle
    Unreal would skip, in budget, texel density
  * the game part and the bake source of every builder agree in silhouette: their bounds within 0.05 cm
  * the sights' and the barrel's round parts have the side counts their docstrings promise on the game mesh

Writes only under the scratch root (the UV layout picture). Saves no .blend. Nothing here is one of the weapons in weapons/.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge import check as CHK, fittings as F, forms as FM, kit as K, sections as S, stages  # noqa: E402
from weapons.assault_g3 import barrels as BR, sights as SI  # noqa: E402   (AssaultG3's own designs, not shared code)
from weaponforge.weapon import Weapon  # noqa: E402

root = sys.argv[sys.argv.index('--') + 1]
failed = []


def result(label, ok, detail=''):
    print('kit: %s %s%s' % ('ok  ' if ok else 'FAIL', label, (' -> ' + detail[:220]) if detail else ''), flush=True)
    if not ok:
        failed.append(label)


# ------------------------------------------------------------------------------------------------------------- the numbers
SEAT = 0.02
BZ = 6.00                                   # the bore
X0, X1 = -12.00, 18.00                      # the receiver, rear to front
BOT, TOP_Z = 2.00, 8.00                     # its underside and its top land
OUTLINE = [(X0, BOT, 0.8), (X1, BOT, 0.5), (X1, TOP_Z, 0.3), (X0, TOP_Z, 0.8)]
HW_TABLE = [(X0, 1.50), (-9.0, 1.50), (-7.0, 1.80), (12.0, 1.80), (14.0, 1.62), (X1, 1.62)]   # half width: two ramps with crisp ends
_hw = S.lin(HW_TABLE)
SECTION_K = (3, 4)                          # chords in each crease: game mesh, bake source
LP_Q = 3.4


def seg(hp, lo, hi):
    return hi if hp else max(1, int(lo * LP_Q + 0.5))


def facets(x, lo, hi):
    """The left half's sharp corners, underside to top: a tucked lower facet, a side with a little draft, a 45 degree shoulder."""
    w = _hw(x)
    return [(w - 0.35, lo, 0.20), (w, lo + 0.60, 0.17), (w - 0.05, hi - 0.90, 0.17), (w - 0.65, hi, 0.17)], (0.0, hi)


def ring(x, lo, hi, k):
    v, top = facets(x, lo, hi)
    return S.facet_ring(v, lo, top, k)


def side_y(x, z):
    if not (X0 <= x <= X1 and BOT <= z <= TOP_Z):
        return None
    v, top = facets(x, BOT, TOP_Z)
    return S.facet_y(v, BOT, top, z)


RAIL_Z = TOP_Z + 0.80
RAIL_HALF = [(0.80, TOP_Z + SEAT), (0.80, TOP_Z + 0.22), (1.06, TOP_Z + 0.42), (1.06, TOP_Z + 0.62), (0.88, RAIL_Z)]
MOUNT = SI.Mount(RAIL_Z, 1.06, 1.30, RAIL_Z - 0.62, SEAT)
SIGHT_Z = RAIL_Z + 2.60
REAR_X, FRONT_X = (-9.50, -5.80), (12.50, 15.20)
PIN = (-4.0, 4.6)                           # a takedown pin through the receiver, with a boss round it each side
BOSS_R, BOSS_H = 0.62, 0.22
PLATE = ((-1.6, 1.4), (2.6, 3.6), 0.13)     # the data plate's recess: x, z, depth at its low edge
SCREWS = ((-10.4, 6.9, 1.0), (8.0, 6.9, 1.0), (8.0, 6.9, -1.0))
NUT, GAS = (X1 + SEAT, 19.45, 1.35), (21.00, 22.50, 1.16)
BARREL_END = 29.60
HIDER = (BARREL_END + SEAT, BARREL_END + SEAT + 4.40)


# ---------------------------------------------------------------------------------------------------------------- builders
PLACED = []             # (what, cutters) for every ray-placed fitting on the bake source: [] means its ray missed the part


def _placed(what, cuts):
    PLACED.append((what, len(cuts)))
    return cuts


def receiver(coll, hp=False):
    sg = lambda lo, hi: seg(hp, lo, hi)
    side = K.round_poly(OUTLINE, 6 if hp else 3)
    k = SECTION_K[1 if hp else 0]
    body = FM.section_loft('Receiver', side, lambda x, lo, hi: ring(x, lo, hi, k), coll, X0, X1, 3.0 if hp else 6.0, 0.04 if hp else 0.15,
                           knots=S.knots(HW_TABLE))
    K.boolean(body, [FM.boss(side_y, PIN[0], PIN[1], BOSS_R, BOSS_H, s, coll, sg) for s in (1.0, -1.0)], 'UNION')
    flute = S.densify(K.round_poly(S.rect(-8.0, -2.0, 2.9, 3.5, 0.3), 6 if hp else 4), 0.5 if hp else 1.0)
    K.boolean(body, [FM.pocket(side_y, flute, s, 0.20, 0.15, coll, name='flute') for s in (1.0, -1.0)])
    (px0, px1), (pz0, pz1), sink = PLATE
    K.boolean(body, [F.plate_recess(px0, px1, pz0, pz1, side_y((px0 + px1) / 2, pz0) - sink, coll),
                     F.qd_cup(6.0, 3.4, side_y(6.0, 3.4) - 0.35, -1.0, coll, sg(8, 32))])
    K.cleanup(body)
    if hp:
        marks = []
        for x, z, s in SCREWS:
            marks += _placed('fastener at x %.1f' % x, F.fastener(body, *F.side_ray(x, z, s), coll))
        marks += _placed('safe mark', F.safe_mark(body, *F.side_ray(1.0, 6.4, 1.0), coll))
        marks += _placed('fire mark', F.fire_mark(body, *F.side_ray(1.0, 6.4, -1.0), coll))
        marks += _placed('lock mark', F.lock_mark(body, *F.side_ray(PIN[0], PIN[1] + 1.25, 1.0), coll))
        marks += _placed('qd cup marks', F.qd_cup_marks(body, 6.0, 3.4, side_y(6.0, 3.4) - 0.35, -1.0, coll))
        for y in (0.8, -0.8):
            marks += _placed('witness at y %.1f' % y, F.witness(body, (-6.0, y, -3.0), (0.0, 0.0, 1.0), coll))
        marks += _placed('parting line', F.parting_line(body, -11.0, -6.0, False, coll))
        marks += _placed('date clock', F.date_clock(body, *F.side_ray(-10.0, 3.6, -1.0), coll))
        K.boolean(body, marks)
    return K.tag(K.shade(body, 30.0, flats=True), 'Grip_Bone', mat='polymer')


def hardware(coll, hp=False):
    sg = lambda lo, hi: seg(hp, lo, hi)
    face = S.boss_top(side_y, PIN[0], PIN[1], BOSS_R, BOSS_H) + SEAT
    parts = F.takedown_pin(PIN[0], PIN[1], face, coll, sg)
    (px0, px1), (pz0, pz1), sink = PLATE
    plate, rivets, at = F.data_plate(px0, px1, pz0, pz1, side_y((px0 + px1) / 2, pz0) - sink, coll, sg)
    parts.append(plate)
    parts.append(F.sling_loop(X1 - 2.6, X1 - 1.2, BOT - 1.1, BOT + 0.4, coll, sg))
    obj = K.join('Hardware', parts + ([] if hp else rivets), coll)
    if hp:
        K.boolean(obj, F.takedown_pin_cuts(PIN[0], PIN[1], face, coll) + [F.plate_text(at, 'KG 000123', coll)])
        obj = K.join('Hardware', [obj] + rivets, coll)             # the rivets after the cuts (F.data_plate)
    return K.tag(K.shade(obj, 30.0, flats=hp), 'Grip_Bone')


def rail(coll, hp=False):
    full = list(RAIL_HALF) + [(-p[0], p[1]) for p in reversed(RAIL_HALF)]
    body = K.prism('Rail', full, 'YZ', -10.0, 16.0, coll)
    return K.tag(K.shade(body, 30.0, flats=hp), 'Grip_Bone')


def sights(coll, hp=False):
    sg = lambda lo, hi: seg(hp, lo, hi)
    rear = SI.rear_aperture('SightRear', REAR_X[0], REAR_X[1], coll, sg, hp, MOUNT, SIGHT_Z)
    front = SI.front_post('SightFront', FRONT_X[0], FRONT_X[1], coll, sg, hp, MOUNT, SIGHT_Z)
    return [K.tag(K.shade(rear, 30.0, flats=hp), 'Grip_Bone'), K.tag(K.shade(front, 30.0, flats=hp), 'Grip_Bone')]


def barrel(coll, hp=False):
    sg = lambda lo, hi: seg(hp, lo, hi)
    n0, n1, rn = NUT
    g0, g1, rg = GAS
    obj = K.lathe('Barrel', [(n0, 0.0), (n0, rn), (n1 - 0.25, rn), (n1, rn - 0.25), (n1, 0.95), (g0 - 0.02, 0.95)] + BR.gas_ring(g0, g1, rg)
                  + [(g1 + 0.02, 0.90), (BARREL_END - 0.6, 0.85), (BARREL_END - 0.6, 0.74), (BARREL_END, 0.74), (BARREL_END, 0.0)],
                  (0.0, 0.0, BZ), (1.0, 0.0, 0.0), sg(12, 48), coll, start=FM.DOWN)
    BR.gas_block(obj, g0, g1, rg, BZ, coll, sg)
    BR.castellate(obj, n1, rn, BZ, coll)
    if hp:
        K.boolean(obj, BR.gas_block_cuts(g0, g1, rg, BZ, coll))
    K.cleanup(obj, keep=FM.bore_seam(BZ))
    hider = BR.flash_hider('FlashHider', HIDER[0], HIDER[1], BZ, coll, sg, hp)
    return [K.tag(K.shade(obj), 'Grip_Bone'), K.tag(K.shade(hider), 'Grip_Bone')]


def _world(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


class KitGun(Weapon):
    id, name, tag = 'kit_gun', 'KitGun', 'KG'
    design = 'a test piece for the shared builders (tests/kit_builders.py); not a weapon of the game'
    budget = (4000, 40000)
    lods = ()
    bones = [('Root_Bone1', None, (0.0, 0.0, 0.0)), ('Grip_Bone', 'Root_Bone1', (0.0, 0.0, 0.0))]
    sockets = [('Muzzle', 'Grip_Bone', (HIDER[1], 0.0, BZ), (0.0, 0.0, 0.0), 'the muzzle'),
               ('SightFront', 'Grip_Bone', ((FRONT_X[0] + 0.85 + FRONT_X[0] + 1.85) / 2, 0.0, SIGHT_Z), (0.0, 0.0, 0.0), 'the post\'s tip'),
               ('SightRear', 'Grip_Bone', (REAR_X[0] + 1.685 + 0.265, 0.0, SIGHT_Z), (0.0, 0.0, 0.0), 'the aperture\'s centre: the mean of its two rings')]
    brief = {'overall length': (45.5, 46.5), 'height': (10.5, 11.5)}

    def builders(self):
        return {'receiver': receiver, 'hardware': hardware, 'rail': rail, 'sights': sights, 'barrel': barrel}

    def surface(self, s):
        raise NotImplementedError('the test stops before the textures')

    def measure(self, parts):
        lo, hi = CHK.bounds(list(parts.values()))
        return {'overall length': hi.x - lo.x, 'height': hi.z - lo.z}

    def socket_targets(self, parts):
        post = [p for p in _world(parts['SightFront']) if abs(p.y) < 0.09 + 0.01]
        top = max(p.z for p in post)
        tip = [p for p in post if p.z > top - 0.01]
        hole = [p for p in _world(parts['SightRear']) if math.hypot(p.y, p.z - SIGHT_Z) < 0.13 + 0.02]
        out = {'Muzzle': CHK.face_centre(parts['FlashHider'], 0, 1.0, band=0.01), 'SightFront': sum(tip, Vector()) / len(tip)}
        if hole:
            out['SightRear'] = sum(hole, Vector()) / len(hole)
        return out


# ------------------------------------------------------------------------------------------------------------------- run it
w = KitGun()
result('the definition is sound', not w.validate(), '; '.join(w.validate()))
w.root = root
bpy.ops.wm.read_factory_settings(use_empty=True)
K.setup_scene()
try:
    stages.model(w, quiet=True)
    result('every builder ran', True)
except Exception as e:  # noqa: BLE001 (the stage names every builder that failed)
    result('every builder ran', False, str(e))
    print('kit: FAIL: %s' % '; '.join(failed), flush=True)
    sys.exit(1)

lp = {o.name: o for o in bpy.data.collections[w.coll('LP')].objects}
hp = {o.name: o for o in bpy.data.collections[w.coll('HP')].objects}
result('the parts', sorted(lp) == ['Barrel', 'FlashHider', 'Hardware', 'Rail', 'Receiver', 'SightFront', 'SightRear'], str(sorted(lp)))
for name, obj in sorted(lp.items()):
    twin = hp.get(name + '_HP')
    if twin is None:
        result('%s: has a bake source' % name, False)
        continue
    (a0, a1), (b0, b1) = CHK.bounds([obj]), CHK.bounds([twin])
    off = max(max(abs(a0[i] - b0[i]), abs(a1[i] - b1[i])) for i in range(3))
    result('%s: game and detail agree in silhouette' % name, off <= 0.05, 'bounds within %.3f cm (%d and %d triangles)'
           % (off, sum(len(p.vertices) - 2 for p in obj.data.polygons), sum(len(p.vertices) - 2 for p in twin.data.polygons)))

# the round part the eye is close to: the main aperture's countersunk rim on the game mesh (10 x LP_Q sides). The countersink's
# cone meets the arm's eye-side face at the aperture's radius plus the countersink's width (0.13 + 0.08), a ring of one point a side
missed = [what for what, n in PLACED if n == 0]
marks = bpy.data.collections.get(w.coll('MARKS'))
result('every ray-placed fitting found the surface', len(PLACED) == 11 and not missed,
       '%d placed, %d cutters, %d paint marks kept; missed: %s' % (len(PLACED), sum(n for _w, n in PLACED),
                                                                   len(marks.objects) if marks else 0, ', '.join(missed) or 'none'))

rear = lp['SightRear']
ring_pts = [p for p in _world(rear) if abs(math.hypot(p.y, p.z - SIGHT_Z) - (0.13 + 0.08)) < 2.0e-3]
result('the rear aperture is round in the game mesh', len(ring_pts) >= seg(False, 10, 32), '%d points on its countersink\'s rim (%d sides asked for)'
       % (len(ring_pts), seg(False, 10, 32)))

report = stages.check(w)
measured = {r['check'] for r in report}
want = {'brief: overall length', 'brief: height', 'sockets', 'mesh: no part is inside out'}
result('model: the checks that can be measured on the grey parts', want <= measured and all(r['ok'] for r in report),
       CHK.summary(report))

stages.uv(w)
report = stages.check(w)
measured = {r['check'] for r in report}
want |= {'mesh: triangles', 'mesh: closed', 'mesh: no degenerate triangles', 'uv: texel density'}
result('uv: the mesh checks on the finished game mesh', want <= measured and all(r['ok'] for r in report), CHK.summary(report))


# ------------------------------------------------------------------------------------- the helpers and warnings of the kit
import contextlib  # noqa: E402
import io  # noqa: E402
from mathutils import Matrix  # noqa: E402

scratch = K.collection('kit_scratch')


def _extent(obj):
    lo, hi = CHK.bounds([obj])
    return hi - lo


# lettering with a width: the letters stretch along the line, the height and depth do not, the plane the paint mask follows stays
t1 = K.text_solid('t1', 'MODEL', 0.5, (1.0, 2.0, 3.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.03, scratch, ink=1)
t2 = K.text_solid('t2', 'MODEL', 0.5, (1.0, 2.0, 3.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.03, scratch, ink=1, wide=1.6)
e1, e2 = _extent(t1), _extent(t2)
result('text_solid: wide stretches along the line only', abs(e2.x / e1.x - 1.6) < 0.01 and abs(e2.z - e1.z) < 1e-4 and abs(e2.y - e1.y) < 1e-4
       and list(t1['mark']) == list(t2['mark']), 'width x%.3f, height x%.3f, depth x%.3f, same plane: %s'
       % (e2.x / e1.x, e2.z / e1.z, e2.y / e1.y, list(t1['mark']) == list(t2['mark'])))
t3 = K.text_solid('t3', 'MODEL', 0.5, (1.0, 2.0, 3.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.03, scratch, wide=1.0)
result('text_solid: wide=1 is the same lettering as before', [tuple(round(c, 6) for c in v.co) for v in t1.data.vertices]
       == [tuple(round(c, 6) for c in v.co) for v in t3.data.vertices])

# `wide` is what the newcomer's wide() helper did (K.transform of a stretch about the text's x): the same cutter, vertex for vertex
for ex, origin_x in (((1.0, 0.0, 0.0), 3.5), ((-1.0, 0.0, 0.0), 6.5)):
    ref = K.text_solid('ref', 'FIRE 07', 0.4, (origin_x, 1.9, 5.0), ex, (0.0, 0.0, 1.0), 0.03, scratch, spacing=1.08)
    ref = K.transform(ref, Matrix.Translation((origin_x, 0.0, 0.0)) @ Matrix.Scale(1.6, 4, (1.0, 0.0, 0.0)) @ Matrix.Translation((-origin_x, 0.0, 0.0)))
    new = K.text_solid('new', 'FIRE 07', 0.4, (origin_x, 1.9, 5.0), ex, (0.0, 0.0, 1.0), 0.03, scratch, spacing=1.08, wide=1.6)
    same_v = sorted(tuple(round(c, 5) for c in v.co) for v in ref.data.vertices) == sorted(tuple(round(c, 5) for c in v.co) for v in new.data.vertices)
    ex_ = abs(ex[0])
    # the old helper stretched along world X; text_solid stretches along the text's own direction: the same line when it reads along X
    result('text_solid: wide=1.6 is the old wide() helper (reading %s X)' % ('along +' if ex[0] > 0 else 'along -'),
           same_v and abs(ex_) == 1.0, '%d against %d vertices, same set: %s' % (len(ref.data.vertices), len(new.data.vertices), same_v))

# a rivet with a radius: the default is the old rivet vertex for vertex; a bigger one is a bigger copy
r0 = F.rivet((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), scratch, 8)
r1 = F.rivet((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), scratch, 8, r=0.11)
r2 = F.rivet((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), scratch, 8, r=0.22)
x0_, x2_ = _extent(r0), _extent(r2)
result('rivet: r=0.11 is the old rivet; r=0.22 is twice the size', [tuple(v.co) for v in r0.data.vertices] == [tuple(v.co) for v in r1.data.vertices]
       and abs(x0_.x - 0.22) < 1e-4 and abs(x2_.x - 0.44) < 1e-4 and abs(x2_.z / x0_.z - 2.0) < 1e-3,
       'diameter %.3f -> %.3f, height %.3f -> %.3f' % (x0_.x, x2_.x, x0_.z, x2_.z))

# asking the solid: a ray from inside meets the skin from inside; a piece has bounds whatever vertices it is made of
bx = K.box('bx', (0.0, 0.0, 0.0), (4.0, 2.0, 2.0), scratch)
bx2 = K.box('bx2', (10.0, 0.0, 0.0), (11.0, 1.0, 1.0), scratch)
two = K.join('two', [bx, bx2], scratch)
r = CHK.reach(two, (1.0, 1.0, 1.0))
result('check.inside: a point in the solid is, one outside and one in a hollow\'s way are not',
       CHK.inside(two, (1.0, 1.0, 1.0)) and CHK.inside(two, (10.5, 0.5, 0.5)) and not CHK.inside(two, (6.0, 1.0, 1.0))
       and not CHK.inside(two, (1.0, 1.0, 5.0)) and not CHK.inside(two, (1.0, 1.0, 1.0), within=0.5)
       and abs(r['front'] - 3.0) < 1e-6 and abs(r['left'] - 1.0) < 1e-6 and abs(r['down'] - 1.0) < 1e-6, str({k: round(v, 3) for k, v in r.items()}))
turned = K.box('turned', (0.0, 0.0, 0.0), (4.0, 2.0, 2.0), scratch)
turned.matrix_world = Matrix.Translation((20.0, 0.0, 0.0)) @ Matrix.Rotation(math.radians(90.0), 4, 'Z')
result('check.inside: a part that is moved and turned is measured as it stands', CHK.inside(turned, (19.0, 1.0, 1.0)) and not CHK.inside(turned, (21.0, 3.0, 1.0)))
lo, hi = CHK.piece_bounds(two, (10.4, 0.4, 0.4))
lo2, hi2 = CHK.piece_bounds(two, (0.5, 0.5, 0.5))
result('check.piece_bounds: the piece nearest a point', hi.x - lo.x == 1.0 and lo.x == 10.0 and hi2.x == 4.0 and len(CHK.pieces(two)) == 2,
       'pieces %s' % [(round(a.x, 2), round(b.x, 2)) for a, b, _n in CHK.pieces(two)])

# the exact solver's failure hint: a cutter face lying in the plane of a face of the target is found and named
host = K.box('host', (0.0, 0.0, 0.0), (4.0, 2.0, 2.0), scratch)
flat = K.box('flat', (1.0, 0.5, 1.0), (2.0, 1.5, 3.0), scratch)                   # its low face at z = 1.0 is inside; the top of host is z = 2
level = K.box('level', (1.0, 0.5, 0.5), (2.0, 1.5, 2.0), scratch)                  # its top face lies in the host's top face (z = 2)
off = K.box('off', (1.0, 0.5, 0.5), (2.0, 1.5, 2.03), scratch)                    # 0.03 above it: not coplanar
found = K.coplanar_faces(host.data, host.matrix_world, level)
result('boolean: a cutter face in the plane of a target face is found and named',
       len(found) == 1 and abs(found[0][0].z - 2.0) < 1e-6 and not K.coplanar_faces(host.data, host.matrix_world, off)
       and not K.coplanar_faces(host.data, host.matrix_world, flat), '%d found: %s' % (len(found), K._say_face(found[0][0], found[0][2]) if found else ''))

# a twisted facet in a section loft is said, with its facet, its rings and the amount; a flat one is not
SQ = [(-1.0, 0.0), (1.0, 0.0), (1.0, 2.0), (-1.0, 2.0)]


def _flat(x, lo, hi):
    return list(SQ)


def _twisted(x, lo, hi):
    return [(-1.0, 0.0), (1.0, 0.0), (1.0, 2.0 + 0.30 * (x > 3.0)), (-1.0, 2.0)]


for label, fn, want in (('a flat section', _flat, False), ('a section with a corner raised at its far ring', _twisted, True)):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        FM.section_loft('Twist', [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 2.0)], fn, scratch, 0.0, 6.0, 6.0, 0.5, knots=(0.0, 6.0))
    text = buf.getvalue()
    said = 'section_loft Twist: facet' in text and 'twisted by' in text
    result('section_loft: %s %s' % (label, 'is warned about' if want else 'is not'), said == want, text.strip()[:200])

print('kit: %s' % ('PASS' if not failed else 'FAIL: ' + '; '.join(failed)), flush=True)
sys.exit(1 if failed else 0)
