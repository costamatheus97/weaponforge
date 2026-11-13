"""weaponforge: the automatic checks, measured on the meshes themselves (not on the numbers they were built from).

    report = check.run(weapon, lp_objs, game, cover)      # [{'check', 'ok', 'detail'}]

The generic checks are here; a weapon adds its own in Weapon.checks(c) and feeds three hooks: brief + measure (the design brief),
moves (parts that must travel clear), socket_targets (where the mesh says a socket should be).

A failed check is a finding to report, not something to tune away: the pistol ships with two known misses, both explained in its
plan (PLAYBOOK.md, "Checks").
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import bake as B
from . import rig as R
from . import uv as U
from .weapon import SOCKET_PREFIX

TOL = 0.2                 # cm: 2 mm, the tolerance of every size check
TOUCH = 0.02              # cm: parts that only touch may read as this deep in each other
REST_MAX = 0.05           # cm: deeper than this at rest is not touching: one part is modelled into another
ENGINE_AREA = 5.0e-5      # cm2: Unreal's FBX import skips a smaller triangle as degenerate (mesh.AREA_MIN keeps a margin over it)
INWARD_MAX = 0.05         # share of the drawn texels whose baked normal may point into the game mesh. Faces hidden against
#                           another part do (a butt under its pad, a tube's end in its socket): 0 to 2.5 % on the weapons so
#                           far. A slide, inside out, was 19 %
MISSED_MAX = 0.02         # share of the drawn texels whose bake ray may find no detail (holes too deep to reach are the usual ones)
BARE_REACH = 1.0          # cm: a point of a flat face is bare when nothing is modelled within this far of it (a square reach)
BARE_AREA = 12.0          # cm2 of bare face in one flat stretch that is worth saying (a plain patch of 4 by 8 cm)
BARE_COVER = 0.8          # cm: a point with another surface this close in front of it is covered (a frame under its grip)
BARE_FLAT = 6.0           # degrees: faces within this of the first one are the same flat stretch
BARE_GRID = 1024          # the sheet is looked at this many texels across

LAST_FIGURES = None       # the review figures the last run() measured (review.figures), or None: stages.export puts them in the spec


# ------------------------------------------------------------------------------------------------------------- measuring
def bounds(objs):
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


# ------------------------------------------------------------------------- asking the solid, not its vertices
# A per-weapon check that picks vertices by position ("the points within 0.01 of this plane") breaks the day the part is built
# another way (a loft with a ring more, a boolean that put its vertices elsewhere). These ask the solid itself: a ray from a
# point meets the skin from inside or it does not; a connected piece has bounds whatever vertices it was made of.
SIX = ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, -1.0))
SIX_NAMES = ('front', 'back', 'left', 'right', 'up', 'down')       # +X, -X, +Y, -Y, +Z, -Z in the weapon frame


def ray(obj, origin, direction):
    """The first place a ray from `origin` along `direction` (both in the weapon frame) meets the object's skin, and the skin's
    normal there along the ray: (distance, point, normal) in the weapon frame, or None for a miss. A normal with a positive dot
    with `direction` means the ray met the skin from INSIDE. The ray runs in the object's own space, so a part that is turned
    or moved is measured as it stands."""
    inv = obj.matrix_world.inverted()
    d = Vector(direction).normalized()
    ok, loc, nrm, _index = obj.ray_cast(inv @ Vector(origin), (inv.to_3x3() @ d).normalized())
    if not ok:
        return None
    point = obj.matrix_world @ loc
    normal = (obj.matrix_world.to_3x3().inverted().transposed() @ nrm).normalized()
    return (point - Vector(origin)).length, point, normal


def reach(obj, point, directions=SIX):
    """How far from `point` the skin is along each direction, met from inside: {label: cm or None}. None when that ray met no
    skin or met it from outside (the point is not inside the solid that way). The six directions are named front (+X), back,
    left (+Y), right, up, down; other directions are labelled by their tuple."""
    out = {}
    for i, d in enumerate(directions):
        label = SIX_NAMES[SIX.index(tuple(d))] if tuple(d) in SIX else tuple(d)
        hit = ray(obj, point, d)
        out[label] = hit[0] if hit and hit[2].dot(Vector(d).normalized()) > 0.0 else None
    return out


def inside(obj, point, within=None, directions=SIX):
    """True when `point` is inside the object's closed solid: a ray from it meets the skin from inside in every one of the
    `directions` (the six axes by default; none that meets nothing, or meets the skin from outside). within: also each such
    ray's skin must be nearer than that many cm (a point in the grip's middle, not anywhere in a long barrel). The object must
    be a closed solid with faces looking outward, which every part the pipeline builds is (check 'mesh: closed')."""
    seen = reach(obj, point, directions).values()
    return all(v is not None and (within is None or v <= within) for v in seen)


def pieces(obj):
    """The separate connected pieces of the object's mesh, each as (lo, hi, vertex_count) with the bounds in the weapon frame,
    biggest first. A part made of joined solids (a cover and its screws that were not unioned) has one piece for each."""
    mesh = obj.data
    n = len(mesh.vertices)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for e in mesh.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    groups = {}
    for v in mesh.vertices:
        groups.setdefault(find(v.index), []).append(obj.matrix_world @ v.co)
    out = []
    for pts in groups.values():
        out.append((Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
                    Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))), len(pts)))
    return sorted(out, key=lambda t: -t[2])


def piece_bounds(obj, near):
    """The bounds (lo, hi) in the weapon frame of the connected piece of `obj` that lies nearest the point `near` (a button on a
    plate, one rod of a hairpin): the extent of a named piece, whatever vertices it happens to be built of. None when the object
    has no vertices. A point inside a piece's bounds is nearest to it (distance 0)."""
    best, best_d = None, 1.0e30
    near = Vector(near)
    for lo, hi, _n in pieces(obj):
        d = Vector([max(lo[i] - near[i], 0.0, near[i] - hi[i]) for i in range(3)]).length
        if d < best_d:
            best, best_d = (lo, hi), d
    return best


def parts_bounds(by_name, *names):
    """The bounds (lo, hi) of the named parts together (`c.by_name` is the dict): bounds() by name, with a clear message when a
    part is not there."""
    missing = [n for n in names if n not in by_name]
    if missing:
        raise KeyError('no part named %s (parts: %s)' % (', '.join(missing), ', '.join(sorted(by_name))))
    return bounds([by_name[n] for n in names])


def _world_bm(obj, matrix=None):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform((matrix or Matrix.Identity(4)) @ obj.matrix_world)
    bm.normal_update()
    return bm


def _joined(objs, matrix=None):
    out = bmesh.new()
    for obj in objs:
        tmp = _world_bm(obj, matrix)
        mesh_verts = {v.index: out.verts.new(v.co) for v in tmp.verts}
        for f in tmp.faces:
            try:
                out.faces.new([mesh_verts[v.index] for v in f.verts])
            except ValueError:
                pass
        tmp.free()
    out.normal_update()
    out.verts.ensure_lookup_table()
    out.faces.ensure_lookup_table()
    return out


def _depth_inside(points, bm):
    """How deep the deepest of `points` sits inside the closed mesh bm (0 when none is inside)."""
    tree = BVHTree.FromBMesh(bm)
    worst = 0.0
    where = None
    for p in points:
        loc, normal, _index, dist = tree.find_nearest(p)
        if loc is None or dist < 1.0e-6:
            continue
        if (p - loc).dot(normal) < 0.0:
            # inside by the nearest face; confirm with a ray count, which a thin wall cannot fool
            hits = 0
            origin = p.copy()
            direction = Vector((0.137, 0.613, 0.778)).normalized()
            for _ in range(64):
                hit, _n, _i, _d = tree.ray_cast(origin, direction)
                if hit is None:
                    break
                hits += 1
                origin = hit + direction * 1.0e-5
            if hits % 2 == 1 and dist > worst:
                worst = dist
                where = p.copy()
    return worst, where


def penetration(a_objs, b_objs, a_matrix=None):
    """Deepest a vertex of one group sits inside the other, both ways, with a_objs moved by a_matrix. (cm, where, overlapping pairs)"""
    a = _joined(a_objs, a_matrix)
    b = _joined(b_objs)
    d1, w1 = _depth_inside([v.co for v in a.verts], b)
    d2, w2 = _depth_inside([v.co for v in b.verts], a)
    pairs = len(BVHTree.FromBMesh(a).overlap(BVHTree.FromBMesh(b)))
    a.free()
    b.free()
    return max(d1, d2), (w1 if d1 >= d2 else w2), pairs


def uv_density(obj, size):
    """(px / cm at `size`, UV area, surface area) of one part."""
    mesh = obj.data
    layer = mesh.uv_layers[U.UV_NAME].data
    uv_area = 0.0
    area = 0.0
    for poly in mesh.polygons:
        idx = list(poly.loop_indices)
        a = layer[idx[0]].uv
        for i, j in zip(idx[1:-1], idx[2:]):
            b, c = layer[i].uv, layer[j].uv
            uv_area += abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) * 0.5
        area += poly.area
    return (math.sqrt(uv_area / area) * size if area > 0.0 else 0.0), uv_area, area


def _face_uv_areas(obj):
    """The UV area of each face (numpy)."""
    mesh = obj.data
    n = len(mesh.polygons)
    uv = np.empty(len(mesh.loops) * 2, dtype=np.float64)
    mesh.uv_layers[U.UV_NAME].data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2)
    starts = np.empty(n, dtype=np.int64)
    totals = np.empty(n, dtype=np.int64)
    mesh.polygons.foreach_get('loop_start', starts)
    mesh.polygons.foreach_get('loop_total', totals)
    out = np.zeros(n)
    for k in range(1, int(totals.max()) - 1 if n else 0):
        ok = totals > k + 1
        a, b, c = uv[starts[ok]], uv[starts[ok] + k], uv[starts[ok] + k + 1]
        out[ok] += 0.5 * np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
    return out


def open_edges(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    n = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return n


def tiny(obj, area=ENGINE_AREA):
    """The count of faces under the area Unreal's FBX import keeps."""
    return sum(1 for p in obj.data.polygons if p.area < area)


def section(obj, z):
    """Where the object's edges cross the plane at height z: the points of its cut there, in world space.

    For measuring a shape that has no vertices where the question is: a rounded strap between two outline rings, say."""
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    out = []
    for e in obj.data.edges:
        a, b = pts[e.vertices[0]], pts[e.vertices[1]]
        if (a.z - z) * (b.z - z) < 0.0:
            out.append(a.lerp(b, (z - a.z) / (b.z - a.z)))
    return out


def section_mid_x(obj, z, max_y):
    """Middle (in x) of the object's cut through the plane at height z, looking only at |y| <= max_y."""
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = []
    for e in obj.data.edges:
        a, b = pts[e.vertices[0]], pts[e.vertices[1]]
        if (a.z - z) * (b.z - z) < 0.0:
            p = a.lerp(b, (z - a.z) / (b.z - a.z))
            if abs(p.y) <= max_y:
                xs.append(p.x)
    return (min(xs) + max(xs)) / 2 if xs else None


def face_centre(obj, axis, sign=1.0, band=0.005):
    """The middle of the object's outermost face along an axis (0, 1, 2), e.g. a muzzle (axis 0) or a button's outer face."""
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    far = max(p[axis] * sign for p in pts)
    face = [p for p in pts if p[axis] * sign > far - band]
    return sum(face, Vector()) / len(face)


def inside_out(obj):
    """How many of the mesh's closed pieces have their faces turned inward (a negative volume). Such a piece looks right in
    grey; the bake takes its normals as pointing INTO the part, and it is black in any light."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    seen = set()
    turned = 0
    for start in bm.faces:
        if start.index in seen:
            continue
        seen.add(start.index)
        stack, piece, closed = [start], [], True
        while stack:
            f = stack.pop()
            piece.append(f)
            for e in f.edges:
                if len(e.link_faces) != 2:
                    closed = False
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        if not closed:
            continue
        volume = 0.0
        for f in piece:
            v = [w.co for w in f.verts]
            for i in range(1, len(v) - 1):
                volume += v[0].dot(v[i].cross(v[i + 1]))
        if volume / 6.0 < -1.0e-7:
            turned += 1
    bm.free()
    return turned


def _near(mask, r):
    """True where a True of `mask` lies within r texels (a square reach)."""
    h, w = mask.shape
    total = np.zeros((h + 1, w + 1), dtype=np.int32)
    total[1:, 1:] = np.cumsum(np.cumsum(mask.astype(np.int32), axis=0), axis=1)
    ys, xs = np.arange(h), np.arange(w)
    y0, y1 = np.clip(ys - r, 0, h), np.clip(ys + r + 1, 0, h)
    x0, x1 = np.clip(xs - r, 0, w), np.clip(xs + r + 1, 0, w)
    return (total[y1][:, x1] - total[y0][:, x1] - total[y1][:, x0] + total[y0][:, x0]) > 0


def bare_faces(parts, masks, idm=None, marks=None, kinds=None, skip=('wood',), every=False):
    """Flat faces with a wide stretch that has nothing modelled on it: [(part, which way it faces, bare cm2, the flat
    stretch's cm2, its surface kind or None)], the barest first.

    What separates a game weapon that reads as made from one that reads as a block is mostly how much is ON its big faces:
    a screw, a pin, a panel line, a rib, a recess, a line of lettering. This measures the lack of it. A flat stretch is a
    run of game-mesh faces that lie within BARE_FLAT degrees of each other; a texel of it is bare when the bake found no
    edge, groove or lettering within BARE_REACH cm of it and the stretch itself goes on that far all round, so a narrow
    face is never bare however plain. Curved faces (a barrel, a lofted stock) are not looked at, a point with another
    surface right in front of it is covered and not counted (a frame under its grip panel, a butt under its pad), and a
    kind in `skip` is left out: wood carries its figure in the grain.

    parts: the game parts, with their UVs. masks: the bake's masks (bake/masks.npy: G convex edges, B cavities), idm: its
    ID map (bake/id.npy), marks: its lettering mask (bake/marks.npy) or None, kinds: the weapon's surface kinds.
    every=True returns each flat stretch that was big enough to be measured, bare or not (for looking into a result)."""
    size = masks.shape[0]
    f = max(1, size // BARE_GRID)
    n = size // f

    def pool(a):
        return a[:n * f, :n * f].reshape(n, f, n, f).any(axis=(1, 3))
    detail = pool((masks[..., 1] > 64) | (masks[..., 2] > 64))
    if marks is not None:
        detail |= pool(marks[..., :3].max(axis=2) > 64)
    names = {tuple(int(c > 0.5) for c in k.code): name for name, k in (kinds or {}).items()}
    cos_flat = math.cos(math.radians(BARE_FLAT))
    whole = _joined(parts)
    tree = BVHTree.FromBMesh(whole)
    out = []
    for obj in parts:
        if U.UV_NAME not in obj.data.uv_layers:
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        bm.normal_update()
        layer = bm.loops.layers.uv[U.UV_NAME]
        seen = set()
        for start in sorted(bm.faces, key=lambda face: -face.calc_area()):
            if start in seen:
                continue
            normal = start.normal.copy()
            stretch, stack = [], [start]
            seen.add(start)
            while stack:
                face = stack.pop()
                stretch.append(face)
                for e in face.edges:
                    for g in e.link_faces:
                        if g not in seen and g.normal.dot(normal) >= cos_flat:
                            seen.add(g)
                            stack.append(g)
            area = sum(face.calc_area() for face in stretch)
            if area < BARE_AREA + (2.0 * BARE_REACH) ** 2:
                continue
            uv_area = 0.0
            tris = []
            for face in stretch:
                uv = [l[layer].uv for l in face.loops]
                for i in range(1, len(uv) - 1):
                    a, b, c = uv[0], uv[i], uv[i + 1]
                    uv_area += abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) * 0.5
                    tris.append((a.x * n, a.y * n, b.x * n, b.y * n, c.x * n, c.y * n,
                                 face.loops[0].vert.co, face.loops[i].vert.co, face.loops[i + 1].vert.co))
            if uv_area <= 0.0:
                continue
            per_cm = math.sqrt(uv_area / area) * n
            reach = max(1, int(round(BARE_REACH * per_cm)))
            lo_x = max(0, int(min(min(t[0], t[2], t[4]) for t in tris)))
            hi_x = min(n - 1, int(max(max(t[0], t[2], t[4]) for t in tris)) + 1)
            lo_y = max(0, int(min(min(t[1], t[3], t[5]) for t in tris)))
            hi_y = min(n - 1, int(max(max(t[1], t[3], t[5]) for t in tris)) + 1)
            if hi_x - lo_x < 2 * reach or hi_y - lo_y < 2 * reach:
                continue
            inside = np.zeros((hi_y - lo_y + 1 + 2 * reach, hi_x - lo_x + 1 + 2 * reach), dtype=bool)      # a rim of "not this face" all round
            lift = normal * 0.02
            for ax, ay, bx, by, cx, cy, pa, pb, pc in tris:
                x0, x1 = max(lo_x, int(min(ax, bx, cx))), min(hi_x, int(max(ax, bx, cx)) + 1)
                y0, y1 = max(lo_y, int(min(ay, by, cy))), min(hi_y, int(max(ay, by, cy)) + 1)
                d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
                if abs(d) < 1.0e-12 or x1 < x0 or y1 < y0:
                    continue
                gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
                l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d
                hit = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
                for iy, ix in zip(*np.nonzero(hit)):          # a texel with another surface right in front of it is covered
                    u, v = float(l1[iy, ix]), float(l2[iy, ix])
                    point = pa * u + pb * v + pc * (1.0 - u - v) + lift
                    if tree.ray_cast(point, normal, BARE_COVER)[0] is not None:
                        hit[iy, ix] = False
                inside[y0 - lo_y + reach:y1 - lo_y + reach + 1, x0 - lo_x + reach:x1 - lo_x + reach + 1] |= hit
            busy = ~inside
            busy[reach:-reach, reach:-reach] |= detail[lo_y:hi_y + 1, lo_x:hi_x + 1]
            bare = inside & ~_near(busy, reach)
            bare_cm2 = float(bare.sum()) / (per_cm * per_cm)
            if bare_cm2 < BARE_AREA and not every:
                continue
            kind = None
            if idm is not None and names and bare.any():
                ys, xs = np.nonzero(bare)
                code = idm[(ys - reach + lo_y) * f + f // 2, (xs - reach + lo_x) * f + f // 2, :3] > 96
                votes = {}
                for key in map(tuple, code[::max(1, len(code) // 500)].astype(int)):
                    votes[key] = votes.get(key, 0) + 1
                kind = names.get(max(votes, key=votes.get))
            if kind in skip:
                continue
            axis = max(range(3), key=lambda i: abs(normal[i]))
            way = (('the front', 'the rear'), ('the left side', 'the right side'), ('the top', 'the underside'))[axis][0 if normal[axis] > 0 else 1]
            out.append((obj.name, way if abs(normal[axis]) > 0.94 else 'a slanted face', bare_cm2, area, kind))
        bm.free()
    whole.free()
    return sorted(out, key=lambda row: -row[2])


def loose_verts(obj):
    return sum(1 for v in obj.data.vertices if len(v.groups) != 1 or abs(v.groups[0].weight - 1.0) > 1.0e-6)


# --------------------------------------------------------------------------------------------------------------- checker
class Checker:
    def __init__(self, weapon, lp_objs, game=None, cover=None, log=print, bake=None):
        self.weapon = weapon
        self.bake = bake
        self.parts = list(lp_objs)
        self.game = game
        self.cover = cover
        self.log = log
        self.out = []
        self.by_name = {o.name: o for o in self.parts}
        self.by_bone = {}
        for o in self.parts:
            self.by_bone.setdefault(o.get('bone'), []).append(o)
        known = {n for n, _p, _pos in weapon.bones}
        self.untagged = {o.name: o.get('bone') for o in self.parts if o.get('bone') not in known}

    def add(self, name, ok, detail):
        self.out.append({'check': name, 'ok': bool(ok), 'detail': detail})
        self.log('%-4s %-30s %s' % ('ok' if ok else 'MISS', name, detail))

    def note(self, name, detail):
        """Something that cannot be measured yet because its stage has not run: said, not counted. Only while the rig does not
        exist (a file being worked on); once there are game meshes, a stage that was skipped is a miss."""
        self.log('%-4s %-30s %s' % ('--', name, detail))

    def advise(self, name, detail):
        """Something measured that is a matter of looks, for the modeller to weigh: said, not counted, and
        never a reason an export stops."""
        self.log('%-4s %-30s %s' % ('note', name, detail))

    @property
    def unfinished(self):
        """The parts have not been through the stage "uv" (which also makes them clean triangle meshes), and nothing is rigged."""
        return self.game is None and any(U.UV_NAME not in o.data.uv_layers for o in self.parts)

    def on(self, *bones):
        """The game parts on these bones."""
        return [o for b in bones for o in self.by_bone.get(b, [])]

    def off(self, *bones):
        """The game parts on any other bone."""
        return [o for o in self.parts if o.get('bone') not in bones]

    # ---- the generic checks
    def tags(self):
        """Said only when it is wrong: a part on a bone the weapon does not define cannot be rigged."""
        if self.untagged:
            self.add('parts: bone tags', False, 'parts tagged for a bone the weapon does not define (kit.tag in the builder, '
                                                'or the bones list): %s' % self.untagged)

    def brief(self):
        w = self.weapon
        if not w.brief:
            return
        measured = w.measure(self.by_name)
        for key, (a, b) in w.brief.items():
            if key not in measured:
                self.add('brief: ' + key, False, 'Weapon.measure() does not return it')
                continue
            v = measured[key]
            self.add('brief: ' + key, a - TOL <= v <= b + TOL, '%.2f cm (design brief %.1f to %.1f)' % (v, a, b))

    def pivots(self):
        if self.game is None:
            self.note('parts: pivots on bones', 'not measured yet: the stage "rig" puts each part\'s origin on its bone')
            return
        pos = self.weapon.bone_pos
        placed = [o for o in self.parts if o.name not in self.untagged]
        off = max((o.matrix_world.translation - pos[o['bone']]).length for o in placed) if placed else 0.0
        self.add('parts: pivots on bones', off < 1.0e-4 and not self.untagged,
                 '%d separate parts, largest pivot error %.5f cm' % (len(self.parts), off))

    def moves(self):
        for move in self.weapon.moves:
            bones = self.weapon.with_children(move.bones)       # what hangs on a moving bone moves with it
            moving = self.on(*bones)
            fixed = self.off(*bones)
            if not moving or not fixed:
                self.add('moving: ' + move.name, False, 'no part on %s' % ', '.join(move.bones) if not moving
                         else 'every part is on %s: nothing for it to clear' % ', '.join(bones))
                continue
            rest, _where, _pairs = penetration(moving, fixed)
            steps = [(amount, penetration(moving, fixed, Matrix(move.matrix(amount)))[0]) for amount in move.steps]
            inside = [d for amount, d in steps if abs(amount) <= abs(move.limit) + 1.0e-6]
            worst = max(inside) if inside else 0.0
            text = '; '.join('%g %s %.3f' % (amount, move.unit, d) for amount, d in steps)
            # moving must not make it worse than at rest, and at rest the part may touch its neighbours but not sit inside them
            self.add('moving: ' + move.name, worst <= max(rest, TOUCH) + 0.01 and rest <= REST_MAX,
                     '%sdeepest overlap at rest %.3f cm%s; moved by %s' % (move.note + '; ' if move.note else '', rest,
                                                                         '' if rest <= REST_MAX else ' (over %.2f: the part is modelled into its neighbour)' % REST_MAX, text))

    def sockets(self):
        w = self.weapon
        sock = {n: Vector(pos) for n, _bone, pos, _rot, _means in w.sockets}
        if not sock:
            return
        bones = {n for n, _p, _pos in w.bones}
        orphans = [n for n, bone, _pos, _rot, _means in w.sockets if bone not in bones]
        targets = w.socket_targets(self.by_name) or {}
        errs = {n: (sock[n] - Vector(t)).length for n, t in targets.items() if n in sock}
        unknown = [n for n in targets if n not in sock]
        worst = max(errs, key=errs.get) if errs else None
        detail = '%d defined (%s)' % (len(sock), ', '.join(sock))
        if worst:
            detail += '; against the mesh the largest difference is %.3f cm (%s) over %d measured' % (errs[worst], worst, len(errs))
        else:
            detail += '; none measured against the mesh (Weapon.socket_targets)'
        if orphans or unknown:
            detail += '; on a bone that does not exist: %s; measured but not defined: %s' % (orphans, unknown)
        self.add('sockets', not orphans and not unknown and (worst is None or errs[worst] <= TOL), detail)

    def mesh(self):
        w, parts = self.weapon, self.parts
        detail = bpy.data.collections.get(w.coll('HP'))
        every = list(parts) + ([o for o in detail.objects if o.type == 'MESH'] if detail else [])
        turned = {o.name: n for o, n in ((o, inside_out(o)) for o in every) if n}
        self.add('mesh: no part is inside out', not turned, 'the faces of all %d game and detail parts look outward' % len(every)
                 if not turned else 'closed pieces with their faces turned inward: %s. They look right in grey and are black in any '
                 'light; rebuild the part (a boolean can hand a solid back turned)' % turned)
        if self.unfinished:
            rough = sum(len(p.vertices) - 2 for o in parts for p in o.data.polygons)
            self.note('mesh: triangles', 'about %d before cleanup (budget %d to %d); counted, with "closed" and "no degenerate triangles", '
                                         'once the stage "uv" has finished the mesh' % (rough, w.budget[0], w.budget[1]))
            return
        tris = sum(len(o.data.polygons) for o in parts)
        self.add('mesh: triangles', w.budget[0] <= tris <= w.budget[1], '%d (budget %d to %d)' % (tris, w.budget[0], w.budget[1]))
        not_tri = sum(1 for o in parts for p in o.data.polygons if len(p.vertices) != 3)
        bad = {o.name: n for o, n in ((o, open_edges(o)) for o in parts) if n}
        self.add('mesh: closed', not bad and not_tri == 0, 'every edge has two faces on all %d parts; all triangles' % len(parts)
                 if not bad and not not_tri else 'open edges %s, faces that are not triangles %d' % (bad, not_tri))
        small = {o.name: n for o, n in ((o, tiny(o)) for o in parts) if n}
        self.add('mesh: no degenerate triangles', not small, 'no triangle under %.0e cm2, the size Unreal\'s FBX import skips' % ENGINE_AREA
                 if not small else 'triangles under %.0e cm2, which Unreal\'s FBX import skips: %s' % (ENGINE_AREA, small))

    def uv(self):
        w, parts = self.weapon, self.parts
        if self.unfinished:
            self.note('uv', 'not laid out yet: run the stage "uv"')
            return
        if any(U.UV_NAME not in o.data.uv_layers for o in parts):
            self.add('uv: laid out', False, 'parts without a UV map (run the stage "uv"): %s'
                     % [o.name for o in parts if U.UV_NAME not in o.data.uv_layers])
            return
        size = w.texture_size
        dens = {o: uv_density(o, size) for o in parts}
        uv_sum = sum(d[1] for d in dens.values())
        if U.declares(w):
            self.texel_zones(dens, uv_sum, size)
        else:
            target = math.sqrt(uv_sum / sum(d[2] for d in dens.values())) * size
            spread = {o.name: dens[o][0] / (target * w.density.get(o.get('builder', ''), 1.0)) - 1.0 for o in parts}
            lo_k, hi_k = min(spread, key=spread.get), max(spread, key=spread.get)
            self.add('uv: texel density', max(abs(v) for v in spread.values()) <= 0.10, '%.1f px/cm at %d; parts from %+.1f%% (%s) to %+.1f%% (%s)'
                     % (target, size, spread[lo_k] * 100, lo_k, spread[hi_k] * 100, hi_k))
        if self.cover is not None:
            cover = np.asarray(self.cover)
            drawn = float(cover.mean())
            slack = 0.004 * 4096.0 / cover.shape[0]          # the bake draws whole texels: a smaller sheet rounds more
            self.add('uv: no overlaps', abs(drawn - uv_sum) <= slack, 'the islands add up to %.2f%% of the sheet and the bake drew on %.2f%%'
                     % (uv_sum * 100, drawn * 100))
        if self.bake is not None and 'missed' in self.bake:
            missed = float(self.bake['missed'])
            text = '%.2f%% of the drawn texels found no high-detail surface (at most %.0f%%)' % (missed * 100, MISSED_MAX * 100)
            if missed > MISSED_MAX:
                text += ('; detail more than %.2f cm proud of the game mesh or more than %.2f cm under it is not reached, and those '
                         'texels take the base look: see bake/preview_missed.png'
                         % (self.bake.get('extrusion_cm', 0.02), self.bake.get('max_ray_cm', 0.25)))
                worst = self.bake.get('missed_by_part') or []
                if worst:
                    text += '; worst parts: ' + ', '.join('%s %d texels' % (n, c) for n, c in worst[:4])
            self.add('bake: rays find the detail', missed <= MISSED_MAX, text)
        if self.bake is not None and self.bake.get('inward') is not None:
            inward = float(self.bake['inward'])
            text = '%.2f%% of the drawn texels took a normal that points into the game mesh (at most %.0f%%; faces that lie hidden ' \
                   'against another part do, and are never seen)' % (inward * 100, INWARD_MAX * 100)
            if inward > INWARD_MAX:
                text += ('; that much is a detail part turned inside out or standing inside another, and it is black in any light: '
                         'it is the patch with no blue in it in bake/preview_normal.png')
            self.add('bake: detail faces outward', inward <= INWARD_MAX, text)
        uvs = np.concatenate([np.array([d.uv[:] for d in o.data.uv_layers[U.UV_NAME].data], dtype=np.float32) for o in parts])
        self.add('uv: inside the sheet', float(uvs.min()) >= 0.0 and float(uvs.max()) <= 1.0, 'from %.4f to %.4f' % (float(uvs.min()), float(uvs.max())))

    def texel_zones(self, dens, uv_sum, size, spread_max=0.10):
        """The texel density of a weapon that spends its texels by place (Weapon.texel_zones, .texel_hidden; uv.face_weights):
        the declared weight of every face is worked out again from the definition (not read back from the UVs) and
        `base`, the density a face of weight 1 gets, is sqrt(UV area / sum of 3D area x weight^2) x size. Every part is held
        to within 10 % of base x the rms of its faces' weights, exactly as an undeclared weapon's parts are held to its
        mean: a part with no declared face (weight 1) to base itself. A second check holds every island to base x its weight
        and misses a zone that matches no face (a box typed wrong); its text says which parts are dense or sparse by
        intent, with their numbers."""
        w, parts = self.weapon, self.parts
        weights, classes, _lines = U.face_weights(w, parts)
        rows = []                                        # (part, island area 3D, island uv area, island weight)
        by_class = {}                                    # class: [3D area, uv area]
        for o in parts:
            ids, per = U.island_weights(o, weights[o.name])
            count = len(per)
            area = np.empty(len(o.data.polygons), dtype=np.float64)
            o.data.polygons.foreach_get('area', area)
            uv = _face_uv_areas(o)
            a3, au = np.bincount(ids, area, count), np.bincount(ids, uv, count)
            rows += [(o.name, a3[k], au[k], per[k]) for k in range(count)]
            for k in np.unique(classes[o.name]):
                m = classes[o.name] == k
                got = by_class.setdefault(int(k), [0.0, 0.0])
                got[0] += float(area[m].sum())
                got[1] += float(uv[m].sum())
        base = math.sqrt(uv_sum / sum(a * wt * wt for _n, a, _u, wt in rows)) * size
        mean = math.sqrt(uv_sum / sum(d[2] for d in dens.values())) * size
        spread, asked = {}, {}
        for o in parts:
            mine = [(a, wt) for n, a, _u, wt in rows if n == o.name]
            rms = math.sqrt(sum(a * wt * wt for a, wt in mine) / max(sum(a for a, _wt in mine), 1.0e-12))
            asked[o.name] = rms
            spread[o.name] = dens[o][0] / (base * rms) - 1.0
        lo_k, hi_k = min(spread, key=spread.get), max(spread, key=spread.get)
        self.add('uv: texel density', max(abs(v) for v in spread.values()) <= spread_max,
                 '%.1f px/cm at %d for a face of weight 1 (the sheet\'s mean %.1f); parts from %+.1f%% (%s) to %+.1f%% (%s) of what '
                 'their declared weights ask (the same 10 %%)' % (base, size, mean, spread[lo_k] * 100, lo_k, spread[hi_k] * 100, hi_k))
        off = [(n, math.sqrt(u / a) * size / (base * wt) - 1.0) for n, a, u, wt in rows if a > 1.0e-6]
        worst = max(off, key=lambda r: abs(r[1])) if off else ('-', 0.0)
        zones = list(w.texel_zones or ())
        empty = [z.note or str(k) for k, z in enumerate(zones) if by_class.get(k, [0.0])[0] <= 0.0]
        labels = U.class_names(w)
        names = {k: v[0] for k, v in labels.items()}
        wt_of = {k: v[1] for k, v in labels.items()}
        cls_txt = '; '.join('%s%s %.0f cm2 at %.1f px/cm' % (names[k], ' x%.2f' % wt_of[k] if wt_of[k] is not None else '', a, math.sqrt(u / a) * size)
                            for k, (a, u) in sorted(by_class.items(), key=lambda kv: -kv[1][0]) if a > 0.0)
        dense = sorted((n for n in asked if asked[n] > 1.05), key=lambda n: -asked[n])
        sparse = sorted((n for n in asked if asked[n] < 0.95), key=lambda n: asked[n])
        part_txt = 'dense by intent: %s; sparse by intent: %s' % (
            ', '.join('%s %.1f px/cm (x%.2f)' % (n, dens[self.by_name[n]][0], asked[n]) for n in dense) or 'none',
            ', '.join('%s %.1f px/cm (x%.2f)' % (n, dens[self.by_name[n]][0], asked[n]) for n in sparse) or 'none')
        self.add('uv: texel zones', abs(worst[1]) <= spread_max and not empty,
                 '%d islands each within %+.1f%% of base x its weight (the worst on %s)%s; %s; %s'
                 % (len(rows), worst[1] * 100, worst[0], '; zones that match no face: %s' % empty if empty else '', cls_txt, part_txt))

    def look(self):
        """Said, not counted: the flat faces with a wide stretch that has nothing modelled on it (bare_faces). It needs the
        bake, so it is silent before one exists."""
        folder = self.weapon.bake_dir
        paths = {key: os.path.join(folder, key + '.npy') for key in ('masks', 'id', 'marks')}
        if self.unfinished or any(U.UV_NAME not in o.data.uv_layers for o in self.parts) or not os.path.isfile(paths['masks']):
            return
        try:
            rows = bare_faces(self.parts, np.load(paths['masks']), np.load(paths['id']) if os.path.isfile(paths['id']) else None,
                              np.load(paths['marks']) if os.path.isfile(paths['marks']) else None, B.kinds_of(self.weapon))
        except Exception as err:          # a note about looks must never stop a check run or an export
            self.advise('look: bare faces', 'could not be measured: %r' % (err,))
            return
        if not rows:
            self.advise('look: bare faces', 'no flat face has more than %.0f cm2 with nothing modelled within %.1f cm of it'
                        % (BARE_AREA, BARE_REACH))
            return
        self.advise('look: bare faces', '%d flat face%s with a plain stretch (nothing modelled within %.1f cm) of over %.0f cm2: %s. '
                    'A screw, a pin, a panel line, a rib, a recess or a line of lettering there goes into the detail model only '
                    'and costs no triangles (PLAYBOOK "Modelling" item 64)'
                    % (len(rows), '' if len(rows) == 1 else 's', BARE_REACH, BARE_AREA,
                       '; '.join('%s, %s, %.0f of its %.0f cm2%s' % (name, way, bare, area, ' (%s)' % kind if kind else '')
                                 for name, way, bare, area, kind in rows[:6])))

    def review(self):
        """The review figures (review.figures: what the player's eyes and the front picture see), said for every weapon and
        held as checks only for one that sets Weapon.review (each figure against review.LIMITS). They need the bake, so they
        are silent before one exists (a weapon that opts in is told so, not failed)."""
        global LAST_FIGURES
        from . import review as RV
        held = getattr(self.weapon, 'review', None)
        if self.unfinished or any(U.UV_NAME not in o.data.uv_layers for o in self.parts):
            return
        try:                              # a note about looks must never stop a check run; a weapon that holds them misses
            maps = RV.load_maps(os.path.dirname(self.weapon.bake_dir), self.weapon.tag)
            if maps is None:
                if held:
                    self.note('review: figures', 'not measured yet: they need the stage "bake"')
                return
            marks = bpy.data.collections.get(self.weapon.coll('MARKS'))
            figs = RV.figures(self.weapon, self.parts, maps, marks=list(marks.objects) if marks else None)
            lines = RV._summary_lines(None, figs)
        except Exception as err:
            if held:
                self.add('review: figures', False, 'could not be measured: %r' % (err,))
            else:
                self.advise('review: figures', 'could not be measured: %r' % (err,))
            return
        LAST_FIGURES = figs
        for line in lines:
            self.advise('review: figures', line)
        if held:
            for key, ok, value, limit, what in RV.held(self.weapon, figs):
                self.add('review: ' + key, ok, '%s %s (%s; review %s)' % (RV._fmt(value), what, limit, held))

    def rig(self):
        w, game = self.weapon, self.game
        if game is None:
            return
        skm, arm = game['skm'], game['armature']
        real = [b for b in arm.data.bones if not b.name.startswith(SOCKET_PREFIX)]
        got = {b.name: (b.parent.name if b.parent else None) for b in real}          # by name and parent: Blender lists bones
        want = {n: p for n, p, _pos in w.bones}                                      # depth first, not in the weapon's order
        names = [n for n in want if n in got] + sorted(set(got) - set(want))
        ident = all(max(abs(b.matrix_local[i][j] - (1.0 if i == j else 0.0)) for i in range(3) for j in range(3)) < 1.0e-6 for b in real)
        wrong = sorted(n for n in set(got) | set(want) if got.get(n, '?') != want.get(n, '?'))
        self.add('rig: bones', not wrong and ident and arm.name == R.ARMATURE_NAME,
                 '%d bones (%s); rest axes identity; armature object "%s"%s'
                 % (len(names), ', '.join(names), arm.name, '' if not wrong else '; missing, extra or on the wrong parent: %s' % ', '.join(wrong)))
        self.add('rig: skinning', loose_verts(skm) == 0, 'every vertex on one bone at full weight (%d groups)' % len(skm.vertex_groups)
                 if loose_verts(skm) == 0 else '%d vertices are not on exactly one bone at full weight' % loose_verts(skm))
        wrong = []
        for n, parent, pos, rot, _means in w.sockets:
            b = arm.data.bones.get(SOCKET_PREFIX + n)
            if b is None or b.parent is None or b.parent.name != parent or b.children or b.use_deform:
                wrong.append(n)
                continue
            got = b.matrix_local.to_3x3()
            target = R.ue_rotation(*rot)
            turn = max(abs(got[i][j] - target[i][j]) for i in range(3) for j in range(3))
            if (b.head_local - Vector(pos)).length > 1.0e-4 or turn > 1.0e-5:
                wrong.append(n)
        if w.sockets:
            self.add('rig: socket joints', not wrong, '%d leaf joints named %s<socket>, each on its bone at the spec position and rotation'
                     % (len(w.sockets), SOCKET_PREFIX) if not wrong else 'wrong: %s' % wrong)
        lods = game['lods']
        if lods:
            parts = []
            ok = True
            for obj, (_index, ratio) in zip(lods, w.lods):
                share = len(obj.data.polygons) / float(len(skm.data.polygons))
                groups = {g.name for g in obj.vertex_groups} == {g.name for g in skm.vertex_groups}
                ok = ok and abs(share - ratio) < 0.05 and loose_verts(obj) == 0 and groups
                parts.append('%s %d triangles (%.0f%%)' % (obj.name, len(obj.data.polygons), share * 100))
            self.add('rig: LODs', ok, '; '.join(parts) + '; same bones, every vertex still on one bone')
        meshes = R.exported(game)
        small = {o.name: n for o, n in ((o, tiny(o)) for o in meshes) if n}
        whole = [game['skm'], game['static']] + list(game['props'].values())
        leaks = {o.name: n for o, n in ((o, open_edges(o)) for o in whole) if n}
        tris = sum(len(o.data.polygons) for o in self.parts)
        self.add('rig: game meshes', len(skm.data.polygons) == tris and len(game['static'].data.polygons) == tris and not leaks and not small,
                 '%s triangles; all closed; %s' % (', '.join('%s %d' % (o.name, len(o.data.polygons)) for o in whole),
                                                 'none of the %d exported meshes has a triangle Unreal would skip' % len(meshes))
                 if not leaks and not small else 'open edges %s; triangles Unreal would skip %s; the parts have %d triangles and %s has %d'
                 % (leaks, small, tris, skm.name, len(skm.data.polygons)))
        slots = {o.name: [m.name if m else None for m in o.data.materials] for o in meshes}
        odd = {k: v for k, v in slots.items() if v != [w.mat_game]}
        self.add('rig: one material', not odd, 'every exported mesh has the single slot %s' % w.mat_game if not odd else 'slots: %s' % odd)


def run(weapon, lp_objs, game=None, cover=None, log=print, bake=None):
    """Returns [{'check', 'ok', 'detail'}]. cover: the bake's coverage mask (bool, sheet-sized), for the UV overlap check."""
    global LAST_FIGURES
    LAST_FIGURES = None
    c = Checker(weapon, lp_objs, game, cover, log, bake)
    c.tags()
    c.brief()
    weapon.checks(c)
    c.pivots()
    c.moves()
    c.sockets()
    c.mesh()
    c.uv()
    c.look()
    c.review()
    c.rig()
    return c.out


def summary(report):
    failed = [r['check'] for r in report if not r['ok']]
    return '%d of %d checks pass%s' % (len(report) - len(failed), len(report), '' if not failed else '; missed: ' + ', '.join(failed))
