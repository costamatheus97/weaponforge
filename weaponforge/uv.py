"""weaponforge: lay the finished game parts out on one shared UV sheet.

Every hard edge becomes a UV seam, so each smooth patch is its own island (a hard edge without a UV split bakes badly), and
the weapon may name more (Weapon.seams). A patch that still will not flatten cleanly (a closed band such as a barrel with no
seam down it) is cut up by angle instead.
"""
import math

import bmesh
import bpy
import numpy as np

from . import mesh as M
from .ops import only, run

UV_NAME = 'UVMap'
STRETCH_LIMIT = 1.8          # a patch whose triangles differ by more than this in texel area is cut up by angle


def _patches(bm):
    """Groups of faces joined through edges that are not seams."""
    seen = set()
    out = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack = [f]
        seen.add(f.index)
        group = []
        while stack:
            g = stack.pop()
            group.append(g)
            for e in g.edges:
                if e.seam:
                    continue
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        out.append(group)
    return out


def _tri_uv_area(f, uv):
    pts = [l[uv].uv for l in f.loops]
    a = pts[0]
    return sum(abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) * 0.5 for b, c in zip(pts[1:-1], pts[2:]))


def _weight_seams(bm, weights, split_min=None):
    """Opt-in (texel zones): the faces' weights evened out inside each patch (a run of one weight under SPLIT_MIN_CM2 takes the
    weight of the neighbour it shares the longest edge with, so no sliver becomes an island of its own), then a seam on every
    edge between two weights. Returns (the evened weights, the count of seam edges added). split_min: SPLIT_MIN_CM2 unless
    given."""
    split_min = SPLIT_MIN_CM2 if split_min is None else split_min
    w = np.asarray(weights, dtype=np.float64).copy()
    area = np.array([f.calc_area() for f in bm.faces])
    for _ in range(6):
        comp = np.full(len(w), -1)
        sizes = []
        for f in bm.faces:
            if comp[f.index] >= 0:
                continue
            k = len(sizes)
            comp[f.index] = k
            stack, total = [f], 0.0
            while stack:
                g = stack.pop()
                total += area[g.index]
                for e in g.edges:
                    if e.seam:
                        continue
                    for h in e.link_faces:
                        if comp[h.index] < 0 and w[h.index] == w[f.index]:
                            comp[h.index] = k
                            stack.append(h)
            sizes.append(total)
        sizes = np.array(sizes)
        border = {}
        for e in bm.edges:
            if e.seam or len(e.link_faces) != 2:
                continue
            a, b = e.link_faces[0].index, e.link_faces[1].index
            if comp[a] != comp[b]:
                length = e.calc_length()
                for p, q in ((comp[a], comp[b]), (comp[b], comp[a])):
                    border.setdefault(p, {}).setdefault(q, 0.0)
                    border[p][q] += length
        new = {}
        for k in np.nonzero(sizes < split_min)[0]:
            nbr = border.get(int(k))
            if not nbr:
                continue
            big = {q: v for q, v in nbr.items() if sizes[q] >= split_min} or nbr
            new[int(k)] = max(big, key=lambda q: (big[q], sizes[q]))
        if not new:
            break
        rep = {k: int(np.nonzero(comp == k)[0][0]) for k in set(new.values())}
        target = w.copy()
        for k, q in new.items():
            target[comp == k] = w[rep[q]]
        if np.array_equal(target, w):
            break
        w = target
    added = 0
    for e in bm.edges:
        if not e.seam and len(e.link_faces) == 2 and w[e.link_faces[0].index] != w[e.link_faces[1].index]:
            e.seam = True
            added += 1
    return w, added


def unwrap(obj, extra=None, weights=None, split_min=None):
    """Seams on every hard edge and on the edges extra(edge, mid, direction) picks, unwrap, then cut up the patches that came
    out stretched. Returns (patches, recut, edges extra picked, [where each recut patch is]).

    weights (opt-in, texel zones): the weight of each face; the islands are also cut where it changes (_weight_seams) and a
    stretched patch is recut one weight at a time, so that no island holds two. Then the tuple has a fifth item, the count of
    edges cut for it. split_min: the smallest run of one weight that keeps it (_weight_seams)."""
    mesh = obj.data
    if UV_NAME not in mesh.uv_layers:
        mesh.uv_layers.new(name=UV_NAME)
    mesh.uv_layers.active = mesh.uv_layers[UV_NAME]
    only([obj])
    run(bpy.ops.object.mode_set, mode='EDIT')
    try:
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        picked = 0
        for e in bm.edges:
            e.seam = (not e.smooth) or len(e.link_faces) != 2
            if extra is not None and not e.seam:
                a, b = e.verts[0].co, e.verts[1].co
                if extra(e, (a + b) / 2, (b - a).normalized()):
                    e.seam = True
                    picked += 1
        split = None
        if weights is not None:
            weights, split = _weight_seams(bm, weights, split_min)
        for f in bm.faces:
            f.select = True
        bmesh.update_edit_mesh(mesh)
        run(bpy.ops.mesh.select_all, action='SELECT')
        run(bpy.ops.uv.unwrap, method='ANGLE_BASED', margin=0.0)

        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        uv = bm.loops.layers.uv.active
        groups = _patches(bm)
        bad, where = [], []
        for group in groups:
            ratios = []
            for f in group:
                a3 = f.calc_area()
                if a3 > 1.0e-7:
                    ratios.append(_tri_uv_area(f, uv) / a3)
            if not ratios:
                continue
            ratios.sort()
            lo = ratios[int(len(ratios) * 0.05)]
            hi = ratios[min(len(ratios) - 1, int(len(ratios) * 0.95))]
            if lo <= 1.0e-12 or hi / lo > STRETCH_LIMIT:
                bad.append(group)
                pts = [v.co for f in group for v in f.verts]
                where.append('%d faces, x %.1f to %.1f, y %.1f to %.1f, z %.1f to %.1f, stretch %s' % (
                    len(group), min(p.x for p in pts), max(p.x for p in pts), min(p.y for p in pts), max(p.y for p in pts),
                    min(p.z for p in pts), max(p.z for p in pts), '%.1f' % (hi / lo) if lo > 1.0e-12 else 'without end'))
        if bad and weights is None:
            for f in bm.faces:
                f.select = False
            for group in bad:
                for f in group:
                    f.select = True
            bm.select_flush(True)
            bmesh.update_edit_mesh(mesh)
            run(bpy.ops.uv.smart_project, angle_limit=math.radians(60.0), island_margin=0.0, area_weight=0.0, correct_aspect=True,
                 scale_to_bounds=False)
        elif bad:
            # smart project ignores seams: one weight at a time, so that an island it makes never spans two
            todo = [f.index for group in bad for f in group]
            for value in sorted({float(weights[i]) for i in todo}):
                bm = bmesh.from_edit_mesh(mesh)
                bm.faces.ensure_lookup_table()
                for f in bm.faces:
                    f.select = False
                for i in todo:
                    if float(weights[i]) == value:
                        bm.faces[i].select = True
                # (no select_flush: it would also select a face of another weight whose corners are all on selected faces)
                bmesh.update_edit_mesh(mesh)
                run(bpy.ops.uv.smart_project, angle_limit=math.radians(60.0), island_margin=0.0, area_weight=0.0, correct_aspect=True,
                     scale_to_bounds=False)
        if weights is not None:
            return len(groups), len(bad), picked, where, split
        return len(groups), len(bad), picked, where
    finally:
        run(bpy.ops.object.mode_set, mode='OBJECT')


def pack(objs, margin=0.0024, density=None, how=None, weights=None, log=None):
    """One shared sheet for all of objs: equal texel density (times density[builder], default 1), then pack.

    Opt-in: weights {part: weight of each face} scales each island by its weight (island_weights) instead of by its
    builder; how='tight' packs with pack_tight instead of Blender's packer."""
    density = density or {}
    only(objs)
    run(bpy.ops.object.mode_set, mode='EDIT')
    try:
        run(bpy.ops.mesh.select_all, action='SELECT')
        run(bpy.ops.uv.select_all, action='SELECT')
        run(bpy.ops.uv.average_islands_scale)
    finally:
        run(bpy.ops.object.mode_set, mode='OBJECT')
    for obj in objs:
        if weights is not None:
            ids, per = island_weights(obj, weights[obj.name])
            layer = obj.data.uv_layers[UV_NAME]
            arr = np.empty(len(layer.data) * 2, dtype=np.float32)
            layer.data.foreach_get('uv', arr)
            starts, totals = _loops(obj.data)
            scale = np.repeat(per[ids], totals).astype(np.float32)
            layer.data.foreach_set('uv', (arr.reshape(-1, 2) * scale[:, None]).ravel())
            continue
        w = density.get(obj.get('builder', ''), 1.0)
        if w != 1.0:
            layer = obj.data.uv_layers[UV_NAME]
            arr = np.empty(len(layer.data) * 2, dtype=np.float32)
            layer.data.foreach_get('uv', arr)
            layer.data.foreach_set('uv', arr * w)
    if how == 'tight':
        pack_tight(objs, margin, log=log)
        return stats(objs)
    only(objs)
    run(bpy.ops.object.mode_set, mode='EDIT')
    try:
        run(bpy.ops.mesh.select_all, action='SELECT')
        run(bpy.ops.uv.select_all, action='SELECT')
        props = bpy.ops.uv.pack_islands.get_rna_type().properties
        kw = dict(margin=margin)
        if 'rotate' in props:
            kw['rotate'] = True
        if 'rotate_method' in props:
            kw['rotate_method'] = 'AXIS_ALIGNED'
        if 'scale' in props:
            kw['scale'] = True
        if 'margin_method' in props:
            kw['margin_method'] = 'FRACTION'
        if 'shape_method' in props:
            kw['shape_method'] = 'CONCAVE'
        if 'merge_overlap' in props:
            kw['merge_overlap'] = False
        run(bpy.ops.uv.pack_islands, **kw)
    finally:
        run(bpy.ops.object.mode_set, mode='OBJECT')
    return stats(objs)


def stats(objs):
    """Coverage of the 0..1 square, texel density at 4K (px / cm), and anything outside the square."""
    uv_area = 0.0
    area3 = 0.0
    lo, hi = [9.0, 9.0], [-9.0, -9.0]
    for obj in objs:
        mesh = obj.data
        layer = mesh.uv_layers[UV_NAME]
        uvs = np.empty(len(layer.data) * 2, dtype=np.float32)
        layer.data.foreach_get('uv', uvs)
        uvs = uvs.reshape(-1, 2)
        lo = [min(lo[0], float(uvs[:, 0].min())), min(lo[1], float(uvs[:, 1].min()))]
        hi = [max(hi[0], float(uvs[:, 0].max())), max(hi[1], float(uvs[:, 1].max()))]
        for poly in mesh.polygons:
            idx = list(poly.loop_indices)
            a, b, c = uvs[idx[0]], uvs[idx[1]], uvs[idx[2]]
            uv_area += abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) * 0.5
            area3 += poly.area
    density = 4096.0 * math.sqrt(uv_area / area3) if area3 > 0 else 0.0
    return dict(coverage=round(float(uv_area), 3), px_per_cm_4k=round(density, 1), surface_cm2=round(area3, 1),
                uv_min=[round(v, 4) for v in lo], uv_max=[round(v, 4) for v in hi])


def layout(objs, margin=0.0024, density=None, seams=None, how=None, weapon=None, log=None):
    """Finish, unwrap and pack. seams(obj) gives a part's extra seam test or None. Returns ({part: (patches, recut, extra seam
    edges, [where each recut patch is], open edges)}, stats).

    Opt-in: how='tight' (Weapon.uv_pack) packs with pack_tight; a weapon that declares texel zones (declares(weapon)) has its
    faces weighed (face_weights) after they are finished, its islands cut where the weight changes, and each island scaled by
    its weight."""
    report = {}
    if weapon is None or not declares(weapon):
        for obj in objs:
            bad = M.finish(obj)
            report[obj.name] = unwrap(obj, seams(obj) if seams else None) + (bad,)
        return report, pack(objs, margin, density, how, log=log)
    bad = {obj.name: M.finish(obj) for obj in objs}
    weights, _classes, summary = face_weights(weapon, objs)
    for line in summary:
        (log or print)('texels: %s' % line)
    for obj in objs:
        got = unwrap(obj, seams(obj) if seams else None, weights[obj.name],
                     VIEW_SPLIT_MIN_CM2 if getattr(weapon, 'texel_view', False) else None)
        report[obj.name] = got[:4] + (bad[obj.name],)
        if got[4]:
            (log or print)('%-16s %4d seam edges where the texel weight changes' % (obj.name, got[4]))
    return report, pack(objs, margin, density, how, weights, log=log)


# ------------------------------------------------------------------------------------------------ opt-in: texels by place
COVER_CM = 0.3               # a face with another surface this close straight in front of it is covered (a rail's foot on the shell)
HEMI = 48                    # rays a face sends over its side of the sky; none of them leaving the weapon: the face is shut in
HIDDEN_REACH = 0.75          # hidden_faces tests the centre and points this far from it toward each corner: all must be hidden
SPLIT_MIN_CM2 = 1.0          # a run of one weight smaller than this inside a patch goes with its neighbour (no island for a sliver)
FACING_COS = 0.5             # TexelZone.facing: within 60 degrees
AXES = {'+X': (1, 0, 0), '-X': (-1, 0, 0), '+Y': (0, 1, 0), '-Y': (0, -1, 0), '+Z': (0, 0, 1), '-Z': (0, 0, -1)}


VIEW_REACH = 0.75            # view_demand tests the centre and points this far toward each corner: the best seen one counts
VIEW_UNSEEN = 0.9            # the weight of a face neither eye sees in any pose (the right side, the underside, the muzzle's face)
VIEW_LADDER = (1.4, 1.75, 2.2)              # the weights a seen face can take (few, so few seams: see view_level)
VIEW_FROM = 25.0             # screen px per cm of surface from which a seen face gets the ladder's second step
VIEW_STEP = 2.5              # how much more screen density each further step needs (25, then 62 px/cm)
VIEW_SPLIT_MIN_CM2 = 2.0     # with texel_view, a run of one weight smaller than this inside a patch goes with its neighbour
VIEW_WHOLE_CM2 = 90.0        # a seen part with less than this not hidden takes one step for all of it (face_weights)
VIEW_WHOLE_SEEN = 0.25       # ... when the eyes see at least this share of what is not hidden of it,
VIEW_WHOLE_REST_CM2 = 20.0   # ... or what they do not see of it is under this (a pistol's barrel seen 1 % in one pose is not)


def declares(weapon):
    """True when the weapon spends its texels by place (Weapon.texel_zones, .texel_hidden or .texel_view)."""
    return (bool(getattr(weapon, 'texel_zones', None)) or getattr(weapon, 'texel_hidden', None) is not None
            or bool(getattr(weapon, 'texel_view', False)))


def _loops(mesh):
    starts = np.empty(len(mesh.polygons), dtype=np.int64)
    totals = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get('loop_start', starts)
    mesh.polygons.foreach_get('loop_total', totals)
    return starts, totals


def islands(obj):
    """The UV island of each face (an index per polygon), and how many: faces are in one island when they share a corner
    with the same UV there, which is what Blender's packer moves as one piece."""
    mesh = obj.data
    n = len(mesh.polygons)
    vi = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get('vertex_index', vi)
    uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    mesh.uv_layers[UV_NAME].data.foreach_get('uv', uvs)
    starts, totals = _loops(mesh)
    face = np.repeat(np.arange(n), totals)
    key = np.empty(len(vi), dtype=[('v', np.int64), ('u', np.uint32), ('w', np.uint32)])
    key['v'] = vi
    pair = uvs.reshape(-1, 2).copy().view(np.uint32)
    key['u'], key['w'] = pair[:, 0], pair[:, 1]
    _uniq, group = np.unique(key, return_inverse=True)
    parent = np.arange(n)

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root
    order = np.argsort(group.ravel(), kind='stable')
    g = group.ravel()[order]
    f = face[order]
    for i in np.nonzero(g[1:] == g[:-1])[0]:
        a, b = find(int(f[i])), find(int(f[i + 1]))
        if a != b:
            parent[b] = a
    roots = np.array([find(i) for i in range(n)])
    _u, ids = np.unique(roots, return_inverse=True)
    return ids.ravel(), int(ids.max()) + 1 if n else 0


def island_weights(obj, weights):
    """(island of each face, weight of each island): an island takes the weight that most of its surface has (the larger one
    on a tie). The islands are cut where the weight changes (unwrap), so this is the weight of all of it but for slivers."""
    ids, count = islands(obj)
    area = np.empty(len(obj.data.polygons), dtype=np.float64)
    obj.data.polygons.foreach_get('area', area)
    weights = np.asarray(weights, dtype=np.float64)
    per = np.ones(count)
    best = np.full(count, -1.0)
    for value in np.unique(weights):
        got = np.bincount(ids, area * (weights == value), count)
        take = got >= best
        per[take] = value
        best[take] = got[take]
    return ids, per


def _world_faces(obj, matrix=None):
    """Centres and normals of the faces in the weapon frame (moved by matrix, a pose)."""
    mesh = obj.data
    n = len(mesh.polygons)
    c = np.empty(n * 3, dtype=np.float64)
    nr = np.empty(n * 3, dtype=np.float64)
    mesh.polygons.foreach_get('center', c)
    mesh.polygons.foreach_get('normal', nr)
    m = np.array(matrix @ obj.matrix_world if matrix is not None else obj.matrix_world)
    c = c.reshape(n, 3) @ m[:3, :3].T + m[:3, 3]
    nr = nr.reshape(n, 3) @ m[:3, :3].T
    length = np.linalg.norm(nr, axis=1, keepdims=True)
    return c, np.where(length > 1.0e-9, nr / np.maximum(length, 1.0e-12), 0.0)


def _hemisphere(k=HEMI):
    """k fixed directions over the half of the sky round +Z, cosine weighted (the same every run)."""
    i = np.arange(k) + 0.5
    r = np.sqrt(i / k)
    phi = i * math.pi * (3.0 - math.sqrt(5.0))
    return np.stack([r * np.cos(phi), r * np.sin(phi), np.sqrt(1.0 - r * r)], axis=1)


def _local(objs):
    """{part: (vertex positions in its own frame, [vertex indices of each face])}."""
    local = {}
    for o in objs:
        mesh = o.data
        co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get('co', co)
        vi = np.empty(len(mesh.loops), dtype=np.int64)
        mesh.loops.foreach_get('vertex_index', vi)
        starts, totals = _loops(mesh)
        local[o.name] = (co.reshape(-1, 3), [vi[s:s + t].tolist() for s, t in zip(starts, totals)])
    return local


def _posed_scenes(weapon, objs, local):
    """For rest and each of Weapon.poses that moves something: (a BVH tree of all of objs as posed, {part: its pose matrix})."""
    from mathutils import Matrix
    from mathutils.bvhtree import BVHTree

    from .stages import _posed
    for moves in [{}] + [m for m in weapon.poses.values() if m]:
        where = _posed(weapon, moves)
        verts, polys, base = [], [], 0
        mats = {}
        for o in objs:
            m = where.get(o.get('bone'), Matrix.Identity(4)) if moves else Matrix.Identity(4)
            mats[o.name] = m
            co, faces = local[o.name]
            full = np.array(m @ o.matrix_world)
            verts += (co @ full[:3, :3].T + full[:3, 3]).tolist()
            polys += [[base + i for i in f] for f in faces]
            base += len(co)
        yield BVHTree.FromPolygons(verts, polys), mats


def hidden_faces(weapon, objs):
    """{part: bool per face}: the faces nobody sees in ANY of the weapon's poses (rest and Weapon.poses, which open the bolt and
    drop the magazine). Hidden in a pose is covered (another surface within COVER_CM straight in front of it: the faces between
    parts) or shut in (none of HEMI rays over its side of the sky leaves the weapon: the bore, the inside of the well and the
    tunnel, the rounds inside the magazine, the bolt inside the shell), at the centre and at HIDDEN_REACH toward every corner.
    A part scaled to nothing in a pose is hidden there."""
    from mathutils import Vector

    sky = _hemisphere()
    hidden = {o.name: np.ones(len(o.data.polygons), dtype=bool) for o in objs}
    local = _local(objs)
    for tree, mats in _posed_scenes(weapon, objs, local):

        def open_at(p, n, bx, by):
            """Neither covered nor shut in at p (just off the face)."""
            if tree.ray_cast(p, n, COVER_CM)[0] is not None:
                return False                                   # covered
            for d in sky:
                if tree.ray_cast(p, bx * d[0] + by * d[1] + n * d[2], 200.0)[0] is None:
                    return True                                # seen from somewhere in this pose
            return False                                       # shut in
        for o in objs:
            todo = np.nonzero(hidden[o.name])[0]
            if not len(todo):
                continue
            c, nr = _world_faces(o, mats[o.name])
            co, faces = local[o.name]
            full = np.array(mats[o.name] @ o.matrix_world)
            wco = co @ full[:3, :3].T + full[:3, 3]
            for i in todo:
                n = Vector(nr[i])
                if n.length < 0.5:
                    continue                                   # scaled to nothing: hidden in this pose
                t = Vector((1.0, 0.0, 0.0)) if abs(n.x) < 0.9 else Vector((0.0, 1.0, 0.0))
                bx = n.cross(t).normalized()
                by = n.cross(bx)
                # the centre, then points HIDDEN_REACH of the way to each corner: the face is hidden in this pose only when
                # every one is covered or shut in (a big face whose middle is under a lip but whose ends show is seen)
                for q in [c[i]] + [c[i] + HIDDEN_REACH * (wco[v] - c[i]) for v in faces[i]]:
                    if open_at(Vector(q) + n * 0.004, n, bx, by):
                        hidden[o.name][i] = False
                        break
    return hidden


def _length_m(objs):
    """The weapon's length in m along its longer horizontal axis, as hero.make measures it (the parts are in cm)."""
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for o in objs:
        co, _f = _local([o])[o.name]
        m = np.array(o.matrix_world)
        w = co @ m[:3, :3].T + m[:3, 3]
        lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
    return float(max(hi[0] - lo[0], hi[1] - lo[1])) / 100.0


def view_demand(weapon, objs):
    """({part: per face, the most screen px per cm of its surface either eye gets in any pose; 0: neither eye sees it},
    {part: per face, which eyes see it: 1 fp, 2 ads}, {'fp': eye, 'ads': eye}).

    The eyes are the hero pictures' (hero.player_eyes): their frame is 60 degrees across and 16:9, at hero.FP_RES. A point of
    a face (the centre, and VIEW_REACH of the way to each corner) is seen when it is in the frame, faces the eye, and the
    line to the eye meets nothing. Seen at distance d with the line at angle a to the face's normal, a cm of its surface
    covers F x sqrt(cos a) / d px on the screen (F: the frame's focal length in px; sqrt: the mean of the stretch along and
    across the line of sight), and the face takes the most any of its points gets."""
    from mathutils import Vector

    from . import hero
    eyes = hero.player_eyes(weapon, _length_m(objs))
    half_w = math.tan(math.radians(hero.FP_FOV) / 2.0)
    half_h = half_w * hero.FP_RES[1] / hero.FP_RES[0]
    focal = hero.FP_RES[0] / 2.0 / half_w
    demand = {o.name: np.zeros(len(o.data.polygons)) for o in objs}
    seen_by = {o.name: np.zeros(len(o.data.polygons), dtype=np.int64) for o in objs}
    local = _local(objs)
    for tree, mats in _posed_scenes(weapon, objs, local):
        for bit, name in ((1, 'fp'), (2, 'ads')):
            if name not in eyes:
                continue
            eye, look = eyes[name]
            fwd = np.array(look.normalized())
            right = np.cross(fwd, (0.0, 0.0, 1.0))
            right /= np.linalg.norm(right)
            up = np.cross(right, fwd)
            e = np.array(eye)
            for o in objs:
                c, nr = _world_faces(o, mats[o.name])
                co, faces = local[o.name]
                full = np.array(mats[o.name] @ o.matrix_world)
                wco = co @ full[:3, :3].T + full[:3, 3]
                owner = np.concatenate([np.full(1 + len(f), i) for i, f in enumerate(faces)])
                pts = np.concatenate([np.vstack([c[i], c[i] + VIEW_REACH * (wco[f] - c[i])]) for i, f in enumerate(faces)])
                n = nr[owner]
                to_eye = e - pts
                dist = np.linalg.norm(to_eye, axis=1)
                cos = np.einsum('ij,ij->i', n, to_eye) / np.maximum(dist, 1.0e-9)
                rel = -to_eye
                z = rel @ fwd
                ok = (cos > 0.02) & (z > 1.0) & (np.abs(rel @ right) <= z * half_w) & (np.abs(rel @ up) <= z * half_h)
                ok &= np.linalg.norm(n, axis=1) > 0.5
                s = focal * np.sqrt(np.clip(cos, 0.0, 1.0)) / np.maximum(dist, 1.0e-9)
                best = demand[o.name]
                for k in np.nonzero(ok)[0][np.argsort(-s[ok], kind='stable')]:
                    i = owner[k]
                    if s[k] <= best[i] and seen_by[o.name][i] & bit:
                        continue                               # this face is already seen as well from this eye
                    p = Vector(pts[k] + n[k] * 0.004)
                    if tree.ray_cast(p, Vector(to_eye[k] / dist[k]), float(dist[k]) - 0.01)[0] is None:
                        best[i] = max(best[i], s[k])
                        seen_by[o.name][i] |= bit
    return demand, seen_by, {k: tuple(v[0]) for k, v in eyes.items()}


def view_level(demand):
    """The weight on VIEW_LADDER for a face seen at `demand` screen px/cm (0: not seen: VIEW_UNSEEN). Any seen face gets at
    least the ladder's first step; the next steps start at VIEW_FROM and are VIEW_STEP apart in demand, so a face seen
    close and square-on gets the most, and the few steps (each about 1.25 times the last) keep the seams few. Chosen on
    AssaultG3 (PLAYBOOK "UVs" 9): every seen face gets 1.4 whatever its demand, because the hip eye meets the cover at a
    grazing angle (20 to 40 screen px/cm) and a weight by demand alone left the cover near the base."""
    if demand <= 0.0:
        return VIEW_UNSEEN
    if demand < VIEW_FROM:
        return VIEW_LADDER[0]
    k = 1 + int(math.log(demand / VIEW_FROM) / math.log(VIEW_STEP))
    return VIEW_LADDER[min(k, len(VIEW_LADDER) - 1)]


def view_weights(weapon, objs):
    """({part: the weight of each face by what the eyes see (view_level)}, {part: its class: -3 neither eye sees it, -10 - k
    the k-th step of VIEW_LADDER}, lines to log)."""
    demand, seen_by, eyes = view_demand(weapon, objs)
    weights, classes = {}, {}
    area_by, eye_by = {}, {}
    for o in objs:
        lv = np.array([view_level(float(s)) for s in demand[o.name]])
        cls = np.array([-3 if s <= 0.0 else -10 - VIEW_LADDER.index(v) for s, v in zip(demand[o.name], lv)], dtype=np.int64)
        weights[o.name], classes[o.name] = lv, cls
        area = np.empty(len(o.data.polygons), dtype=np.float64)
        o.data.polygons.foreach_get('area', area)
        for k in np.unique(cls):
            area_by[int(k)] = area_by.get(int(k), 0.0) + float(area[cls == k].sum())
        for bit in (1, 2, 3):
            eye_by[bit] = eye_by.get(bit, 0.0) + float(area[seen_by[o.name] == bit].sum())
    lines = ['eyes: %s; seen from the hip only %.0f cm2, down the sights only %.0f, from both %.0f, by neither %.0f' % (
        ', '.join('%s (%.1f, %.1f, %.1f)' % ((k,) + tuple(v)) for k, v in eyes.items()), eye_by[1], eye_by[2], eye_by[3],
        area_by.get(-3, 0.0))]
    return weights, classes, lines


def class_names(weapon):
    """{class: (what it is, its weight or None)} for the classes face_weights gives."""
    out = {-1: ('undeclared', None), -2: ('hidden in every pose', getattr(weapon, 'texel_hidden', None)),
           -3: ('seen by neither eye', VIEW_UNSEEN)}
    out.update({-10 - k: ('seen', v) for k, v in enumerate(VIEW_LADDER)})
    out.update({k: ('zone "%s"' % (z.note or k), z.weight) for k, z in enumerate(getattr(weapon, 'texel_zones', None) or ())})
    return out


def _in_zone(zone, c, nr, builder):
    if zone.builders and builder not in zone.builders:
        return np.zeros(len(c), dtype=bool)
    m = np.ones(len(c), dtype=bool)
    if zone.lo is not None:
        m &= np.all((c >= np.array(zone.lo)) & (c <= np.array(zone.hi)), axis=1)
    if zone.facing:
        m &= np.any(np.stack([nr @ np.array(AXES[s], dtype=np.float64) >= FACING_COS for s in zone.facing]), axis=0)
    return m


def face_weights(weapon, objs):
    """({part: weight of each face}, {part: class of each face: -1 none, -2 hidden, k the k-th TexelZone}, [lines to log]).
    A face's weight is Weapon.density's for its builder (1), then what the eyes see of it (view_weights, with
    Weapon.texel_view), then the last TexelZone it lies in, then Weapon.texel_hidden when it is hidden in every pose
    (hidden_faces). The check "uv: texel density" asks the same function, so it tests what the weapon declares, not a copy."""
    zones = list(getattr(weapon, 'texel_zones', None) or ())
    hid_w = getattr(weapon, 'texel_hidden', None)
    hidden = hidden_faces(weapon, objs) if hid_w is not None else {}
    view_w, view_c, lines = view_weights(weapon, objs) if getattr(weapon, 'texel_view', False) else ({}, {}, [])
    whole, not_whole = [], []
    weights, classes = {}, {}
    area_by = {}
    for o in objs:
        builder = o.get('builder', '')
        c, nr = _world_faces(o)
        area = np.empty(len(o.data.polygons), dtype=np.float64)
        o.data.polygons.foreach_get('area', area)
        w = np.full(len(c), float(weapon.density.get(builder, 1.0)))
        cls = np.full(len(c), -1, dtype=np.int64)
        if o.name in view_w:
            w, cls = view_w[o.name].copy(), view_c[o.name].copy()
            # a small part that an eye sees takes one step for all of it but its hidden faces: the step most of its seen
            # surface has (the larger on a tie). Its patches are small, and steps by face cut them into islands of a few cm2.
            # Not when the eyes see only a glimpse of a bigger part: that would lift all of it for a few faces
            open_ = ~hidden[o.name] if o.name in hidden else np.ones(len(c), dtype=bool)
            seen = open_ & (cls <= -10)
            a_open, a_seen = float(area[open_].sum()), float(area[seen].sum())
            if seen.any() and a_open < VIEW_WHOLE_CM2:
                if a_seen >= VIEW_WHOLE_SEEN * a_open or a_open - a_seen < VIEW_WHOLE_REST_CM2:
                    step = max(set(cls[seen].tolist()), key=lambda k: (area[seen & (cls == k)].sum(), -k))
                    w[open_], cls[open_] = VIEW_LADDER[-10 - step], step
                    whole.append('%s x%.2f' % (o.name, VIEW_LADDER[-10 - step]))
                else:
                    not_whole.append('%s (%.0f %% seen)' % (o.name, 100.0 * a_seen / max(a_open, 1e-9)))
        for k, zone in enumerate(zones):
            m = _in_zone(zone, c, nr, builder)
            w[m] = zone.weight
            cls[m] = k
        if o.name in hidden:
            w[hidden[o.name]] = float(hid_w)
            cls[hidden[o.name]] = -2
        weights[o.name], classes[o.name] = w, cls
        for k in np.unique(cls):
            area_by[int(k)] = area_by.get(int(k), 0.0) + float(area[cls == k].sum())
    total = sum(area_by.values()) or 1.0
    if view_w:                                   # what is left to each step once the zones and the hidden faces took theirs
        lines.append('seen by neither eye x%.2f: %.0f cm2' % (VIEW_UNSEEN, area_by.get(-3, 0.0)))
        for k, v in enumerate(VIEW_LADDER):
            lo = VIEW_FROM * VIEW_STEP ** (k - 1)
            lines.append('seen x%.2f (%s screen px/cm): %.0f cm2' % (
                v, 'under %.0f' % VIEW_FROM if k == 0 else '%.0f and up' % lo if k == len(VIEW_LADDER) - 1
                else '%.0f to %.0f' % (lo, lo * VIEW_STEP), area_by.get(-10 - k, 0.0)))
        lines.append('weighed whole (seen, under %.0f cm2 not hidden): %s%s' % (
            VIEW_WHOLE_CM2, ', '.join(whole) or 'none', '; by face, too little of it seen: ' + ', '.join(not_whole) if not_whole else ''))
    if hid_w is not None:
        lines.append('hidden in every pose x%.2f: %.0f cm2 (%.0f %% of the surface)' % (hid_w, area_by.get(-2, 0.0), 100.0 * area_by.get(-2, 0.0) / total))
    for k, zone in enumerate(zones):
        lines.append('zone "%s" x%.2f: %.1f cm2%s' % (zone.note or k, zone.weight, area_by.get(k, 0.0), '' if area_by.get(k) else ' (MATCHES NO FACE)'))
    return weights, classes, lines


# --------------------------------------------------------------------------------------------- opt-in: the tight packer
TIGHT_CELL = 2               # sheet texels at 4096 per cell of the tight packer's grid
TIGHT_GRID = 4096            # the packer works in texels of a 4096 sheet whatever the texture size (the margin is a fraction)


def _raster(us, vs, w, h):
    """Every texel of an h x w grid that the triangles (us, vs: (n, 3) texel coordinates, >= 0) touch at all: the corners
    and middle of each texel tested against each triangle, and its edges walked at a quarter texel."""
    mask = np.zeros((h, w), dtype=bool)
    # the edges, all triangles at once
    a = np.stack([us, vs], axis=2)                          # (n, 3, 2)
    b = np.roll(a, -1, axis=1)
    p, q = a.reshape(-1, 2), b.reshape(-1, 2)
    steps = np.maximum(2, (np.abs(q - p).max(axis=1) * 4.0).astype(np.int64) + 2)
    which = np.repeat(np.arange(len(p)), steps)
    t = (np.arange(len(which)) - np.repeat(np.cumsum(steps) - steps, steps)) / np.repeat(steps - 1, steps)
    pts = p[which] + (q[which] - p[which]) * t[:, None]
    ix = np.clip(pts[:, 0].astype(np.int64), 0, w - 1)
    iy = np.clip(pts[:, 1].astype(np.int64), 0, h - 1)
    mask[iy, ix] = True
    # the inside of the triangles big enough to have one: the small ones all at once on a SMALL x SMALL grid each, the rest one by one
    x0, y0 = us.min(axis=1).astype(np.int64), vs.min(axis=1).astype(np.int64)
    x1, y1 = us.max(axis=1).astype(np.int64), vs.max(axis=1).astype(np.int64)
    d = (vs[:, 1] - vs[:, 2]) * (us[:, 0] - us[:, 2]) + (us[:, 2] - us[:, 1]) * (vs[:, 0] - vs[:, 2])
    big = (x1 - x0 >= 2) & (y1 - y0 >= 2) & (np.abs(d) >= 1.0e-12)
    SMALL = 12
    few = big & (x1 - x0 < SMALL) & (y1 - y0 < SMALL)
    if few.any():
        k = np.nonzero(few)[0]
        off = np.arange(SMALL) + 0.5
        gx = x0[k][:, None, None] + off[None, None, :]
        gy = y0[k][:, None, None] + off[None, :, None]
        (ax, bx, cx), (ay, by, cy) = us[k].T[:, :, None, None], vs[k].T[:, :, None, None]
        dd = d[k][:, None, None]
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / dd
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / dd
        hit = (l1 >= 0.0) & (l2 >= 0.0) & (l1 + l2 <= 1.0)
        t, iy, ix = np.nonzero(hit)
        mask[np.minimum(y0[k][t] + iy, h - 1), np.minimum(x0[k][t] + ix, w - 1)] = True
    for i in np.nonzero(big & ~few)[0]:
        (ax, bx, cx), (ay, by, cy) = us[i], vs[i]
        gx, gy = np.meshgrid(np.arange(x0[i], x1[i] + 1) + 0.5, np.arange(y0[i], y1[i] + 1) + 0.5)
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d[i]
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d[i]
        mask[y0[i]:y1[i] + 1, x0[i]:x1[i] + 1] |= (l1 >= 0.0) & (l2 >= 0.0) & (l1 + l2 <= 1.0)
    return mask


def _grow(mask, r):
    """mask grown by r texels in every direction (a square reach), with r texels of border added round it."""
    h, w = mask.shape
    out = np.zeros((h + 2 * r, w + 2 * r), dtype=bool)
    out[r:r + h, r:r + w] = mask
    for axis in (0, 1):
        c = np.cumsum(out, axis=axis, dtype=np.int32)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
        n = out.shape[axis]
        out = (np.take(c, np.minimum(np.arange(n) + r + 1, n), axis=axis) - np.take(c, np.maximum(np.arange(n) - r, 0), axis=axis)) > 0
    return out


def _cells(mask, cell):
    h, w = mask.shape
    H, W = -(-h // cell), -(-w // cell)
    big = np.zeros((H * cell, W * cell), dtype=bool)
    big[:h, :w] = mask
    return big.reshape(H, cell, W, cell).any(axis=(1, 3))


def _runs(mask):
    """(column, first row, length) of every vertical run of True: the shape, exactly, as the packer tests it."""
    pad = np.zeros((mask.shape[1], mask.shape[0] + 2), dtype=np.int8)
    pad[:, 1:-1] = mask.T
    d = np.diff(pad, axis=1)
    cs, st = np.nonzero(d == 1)                      # row-major over the transposed: by column, then by row, as the ends are
    _ce, en = np.nonzero(d == -1)
    out = np.stack([cs, st, en - st], axis=1).astype(np.int64).reshape(-1, 3)
    return out[np.argsort(-out[:, 2], kind='stable')]


class _Grid:
    """The sheet as cells, with for every cell the count of free cells from it upward and from it to the right (so a run of an
    island fits at a place when that count is at least the run's length)."""

    def __init__(self, n, border):
        self.n = n
        self.occ = np.zeros((n, n), dtype=bool)
        if border > 0:
            self.occ[:border, :] = self.occ[-border:, :] = True
            self.occ[:, :border] = self.occ[:, -border:] = True
        self.free = self._free(self.occ)
        self.across = self._free(self.occ.T).T
        self.widest = self.across.max(axis=1)            # the longest free stretch across each row: rows too narrow are skipped

    @staticmethod
    def _free(occ):
        n = occ.shape[0]
        idx = np.where(occ, np.arange(n)[:, None], n)
        return (np.minimum.accumulate(idx[::-1], axis=0)[::-1] - np.arange(n)[:, None]).astype(np.int32)

    def find(self, runs, wide, h, w, band=48, budget=4000000, dense=12):
        """The lowest, then leftmost, cell where an island of these runs fits; None when it fits nowhere. Only rows with a free
        stretch as wide as the island's widest row (wide: its row, first column, length) are looked at; there the first
        (longest) run, the widest row and a dozen runs spread over the island pick the candidates as whole slices, a band of
        rows at a time, and the other runs are tested on those in growing batches. Exact: the order of the tests changes the
        time, not the answer."""
        n = self.n
        if h > n or w > n:
            return None
        top = n - h + 1
        cols = n - w + 1
        b, i0, lh = wide
        rows = np.nonzero(self.widest[b:top + b] >= lh)[0]
        rest = runs[1:]
        if len(rest) > 2:
            rest = rest[np.random.default_rng(len(rest)).permutation(len(rest))]
        first, rest = np.concatenate([runs[:1], rest[:dense]]), rest[dense:]
        i = 0
        while i < len(rows):
            y0 = int(rows[i])
            y1 = min(top, y0 + band)
            ok = self.across[y0 + b:y1 + b, i0:i0 + cols] >= lh
            for j, a, length in first:                   # the longest run and a dozen spread ones, as whole slices
                if not ok.any():
                    break
                ok &= self.free[y0 + a:y1 + a, j:j + cols] >= length
            if not ok.any():
                i = int(np.searchsorted(rows, y1))
                continue
            ys, xs = np.nonzero(ok)
            ys = ys + y0
            k, step = 0, 4
            while len(ys) and k < len(rest):
                part = rest[k:k + max(1, min(step, budget // len(ys)))]
                ok = (self.free[ys[:, None] + part[:, 1], xs[:, None] + part[:, 0]] >= part[:, 2]).all(axis=1)
                ys, xs = ys[ok], xs[ok]
                k += len(part)
                step = min(step * 4, 1024)
            if len(ys):
                best = np.lexsort((xs, ys))[0]
                return int(ys[best]), int(xs[best])
            i = int(np.searchsorted(rows, y1))
        return None

    def put(self, mask, y, x):
        h, w = mask.shape
        self.occ[y:y + h, x:x + w] |= mask
        self.free[:, x:x + w] = self._free(self.occ[:, x:x + w])
        self.across[y:y + h, :] = self._free(self.occ[y:y + h, :].T).T
        self.widest[y:y + h] = self.across[y:y + h, :].max(axis=1)


def _turn(fu, fv, h, w, turns):
    """Texel coordinates in a raster of h rows and w columns turned by quarter turns as np.rot90(raster, -turns) turns it."""
    for _ in range(turns):
        fu, fv = h - fv, fu
        h, w = w, h
    return fu, fv


def _try(isles, scale, r, cell):
    """Place every island at `scale` (texels of the 4096 sheet per UV unit of the input): biggest first, each where it sits
    lowest, in whichever of its four quarter turns sits lowest. Returns ({island: (turns, ox, oy, h, w, x, y)}, the share of
    the sheet's height used) or (None, the island that found no place)."""
    n = TIGHT_GRID // cell
    grid = _Grid(n, 0)
    todo = sorted(range(len(isles)), key=lambda k: -isles[k][2] * scale * scale)
    out = {}
    used = 0
    for k in todo:
        us, vs = isles[k][0] * scale, isles[k][1] * scale
        ox, oy = math.floor(us.min()), math.floor(vs.min())
        fu, fv = us - ox, vs - oy
        w, h = int(math.floor(fu.max())) + 1, int(math.floor(fv.max())) + 1
        if max(w, h) + 2 * r > TIGHT_GRID:
            return None, k
        grown = _grow(_raster(fu, fv, w, h), r)
        best = None
        half = np.array_equal(grown, grown[::-1, ::-1])  # the same after a half turn: turns 2 and 3 are 0 and 1 again
        for turns in range(2 if half else 4):
            m = _cells(np.rot90(grown, -turns), cell)
            across = _runs(m.T)                         # (row, first column, length) of the rows' runs: the widest first
            pos = grid.find(_runs(m), tuple(across[0]), *m.shape)
            if pos is not None and (best is None or (pos[0] + m.shape[0], pos[1]) < best[0]):
                best = ((pos[0] + m.shape[0], pos[1]), pos, m, turns)
        if best is None:
            return None, k
        _key, (y, x), m, turns = best
        grid.put(m, y, x)
        used = max(used, y + m.shape[0])
        out[k] = (turns, ox, oy, h, w, x * cell + r, y * cell + r)
    return out, used / float(n)


def pack_tight(objs, margin=0.0024, log=None, tries=8):
    """Pack the islands of objs (as they are scaled now) onto the sheet as large as they will go, with `margin` of the sheet
    round every island, as Blender's packer reads it (0.0024: 10 texels at 4096 round each island, so 20 between two and 10
    to the sheet's edge). Blender's packer leaves channels and the hollows of curved and L-shaped islands empty
    (AssaultG3: 46 % of the sheet covered); this lays each island, biggest first, at the lowest place its exact outline
    (grown by the margin, on a grid of TIGHT_CELL texels at 4096) fits, in the best of its four quarter turns, so the small
    ones fall into the hollows, and tries the scale up until a try fails. Islands are moved and turned, never mirrored,
    scaled apart or bent, so the bake and the normal map see the same surface."""
    say = log or print
    r = int(math.ceil(margin * TIGHT_GRID - 1.0e-6))               # texels round each island: two islands are 2 r apart at least
    isles, where = [], []
    for o in objs:
        mesh = o.data
        ids, count = islands(o)
        starts, totals = _loops(mesh)
        loop_island = np.repeat(ids, totals)
        uvs = np.empty(len(mesh.loops) * 2, dtype=np.float64)
        mesh.uv_layers[UV_NAME].data.foreach_get('uv', uvs)
        uvs = uvs.reshape(-1, 2)
        area = np.zeros(count)
        for k in range(count):
            loops = np.nonzero(loop_island == k)[0]
            fs = np.nonzero(ids == k)[0]
            corners = np.array([(starts[f], starts[f] + i, starts[f] + i + 1) for f in fs for i in range(1, totals[f] - 1)], dtype=np.int64)
            u, v = uvs[corners, 0], uvs[corners, 1]
            area[k] = 0.5 * np.abs((u[:, 1] - u[:, 0]) * (v[:, 2] - v[:, 0]) - (u[:, 2] - u[:, 0]) * (v[:, 1] - v[:, 0])).sum()
            isles.append((u - u.min(), v - v.min(), area[k]))
            where.append((o, loops, u.min(), v.min()))
    total = sum(i[2] for i in isles)
    # a first scale from the islands' area (55 % of the sheet covered); then up while it fits, down when not, halving the step
    scale = TIGHT_GRID * math.sqrt(0.55 / total)
    good, bad_scale = None, None
    for attempt in range(tries):
        placed, used = _try(isles, scale, r, TIGHT_CELL)
        if placed is None:
            o = where[used][0]
            say('tight pack: scale %.4f does not fit: an island of %s (%d by %d texels at 4096) found no place' % (
                scale / TIGHT_GRID, o.name, int(np.ptp(isles[used][0]) * scale), int(np.ptp(isles[used][1]) * scale)))
            bad_scale = scale
        else:
            say('tight pack: scale %.4f fits, %.1f %% of the sheet covered, %.0f %% of its height used' % (
                scale / TIGHT_GRID, 100.0 * total * (scale / TIGHT_GRID) ** 2, used * 100))
            good = (scale, placed)
        if good and bad_scale:
            if bad_scale / good[0] < 1.01:
                break
            scale = (good[0] + bad_scale) / 2.0
        elif good:
            scale = good[0] * min(1.06, max(1.01, math.sqrt(1.0 / max(used, 1.0e-6)) * 0.995))
        else:
            scale *= 0.94
    if good is None:
        raise RuntimeError('tight pack: no scale fitted in %d tries' % tries)
    scale, placed = good
    for o in objs:
        layer = o.data.uv_layers[UV_NAME]
        old = np.empty(len(o.data.loops) * 2, dtype=np.float64)
        layer.data.foreach_get('uv', old)
        old = old.reshape(-1, 2)
        new = old.copy()
        for k, (owner, loops, u0, v0) in enumerate(where):
            if owner is not o:
                continue
            turns, ox, oy, h, w, x, y = placed[k]
            fu, fv = _turn((old[loops, 0] - u0) * scale - ox, (old[loops, 1] - v0) * scale - oy, h, w, turns)
            new[loops, 0] = (fu + x) / TIGHT_GRID
            new[loops, 1] = (fv + y) / TIGHT_GRID
        layer.data.foreach_set('uv', new.astype(np.float32).ravel())
    say('tight pack: %d islands, scale %.4f, %.1f %% of the sheet' % (len(isles), scale / TIGHT_GRID, 100.0 * total * (scale / TIGHT_GRID) ** 2))
    return scale


def export_layout(objs, path, size=2048):
    """A picture of the UV sheet (for checking the pack). Blender draws it when it has a window; `blender -b` cannot (the operator
    needs a GPU), so there the triangle edges are drawn with numpy instead."""
    if not bpy.app.background:
        only(objs)
        run(bpy.ops.object.mode_set, mode='EDIT')
        try:
            run(bpy.ops.mesh.select_all, action='SELECT')
            run(bpy.ops.uv.export_layout, filepath=path, size=(size, size), opacity=0.35, export_all=True, mode='PNG')
            return path
        except RuntimeError:
            pass
        finally:
            run(bpy.ops.object.mode_set, mode='OBJECT')
    sheet = np.zeros((size, size), dtype=np.float32)
    for obj in objs:
        mesh = obj.data
        layer = mesh.uv_layers[UV_NAME]
        uvs = np.empty(len(layer.data) * 2, dtype=np.float32)
        layer.data.foreach_get('uv', uvs)
        uvs = uvs.reshape(-1, 2)
        starts = np.array([p.loop_start for p in mesh.polygons])
        totals = np.array([p.loop_total for p in mesh.polygons])
        for k in range(int(totals.max()) if len(totals) else 0):
            ok = totals > k
            a = uvs[starts[ok] + k]
            b = uvs[starts[ok] + (k + 1) % totals[ok]]
            steps = int(max(2, np.abs(b - a).max() * size * 1.5)) if len(a) else 0
            for t in np.linspace(0.0, 1.0, steps):
                p = np.clip(((a + (b - a) * t) * size).astype(np.int64), 0, size - 1)
                sheet[p[:, 1], p[:, 0]] = 1.0
    rgba = np.stack([sheet, sheet, sheet, np.ones_like(sheet)], axis=2)
    img = bpy.data.images.new('wf_uv_layout', size, size, alpha=False)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path
