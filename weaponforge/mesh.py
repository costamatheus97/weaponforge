"""weaponforge: turn a boolean-built part into a game mesh: repair, triangles, hard edges, weighted normals, and the removal of
what a game engine would throw away (microscopic fans and degenerate slivers).
"""
import math

import bmesh
import bpy

from . import kit as K

WELD = 5.0e-4        # cm: closes the hairlines booleans leave behind; far below any real feature


def _repair(bm):
    """Weld, drop zero-area and duplicate faces, close pinholes. Returns the count of edges that still lack two faces."""
    bad = []
    for _ in range(5):
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=WELD)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=WELD)
        zero = [f for f in bm.faces if f.calc_area() < 1.0e-8]
        seen = set()
        for f in bm.faces:
            key = frozenset(v.index for v in f.verts)
            if key in seen and f not in zero:
                zero.append(f)
            seen.add(key)
        if zero:
            bmesh.ops.delete(bm, geom=list(set(zero)), context='FACES')
        bm.verts.index_update()
        # an edge carrying three or more faces: the extra ones are slivers folded onto it
        extra = []
        for e in bm.edges:
            if len(e.link_faces) > 2:
                extra += sorted(e.link_faces, key=lambda f: f.calc_area())[:len(e.link_faces) - 2]
        if extra:
            bmesh.ops.delete(bm, geom=list(set(extra)), context='FACES')
        wire = [e for e in bm.edges if not e.link_faces]
        if wire:
            bmesh.ops.delete(bm, geom=wire, context='EDGES')
        loose = [v for v in bm.verts if not v.link_edges]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        boundary = [e for e in bm.edges if len(e.link_faces) == 1]
        if boundary:
            filled = bmesh.ops.holes_fill(bm, edges=boundary, sides=12)
            faces = [f for f in filled.get('faces', []) if len(f.verts) > 3]
            if faces:
                bmesh.ops.triangulate(bm, faces=faces, quad_method='BEAUTY', ngon_method='BEAUTY')
        bad = [e for e in bm.edges if len(e.link_faces) != 2]
        if not bad and not zero and not extra:
            break
    K.face_out(bm)
    return len(bad)


def weighted_normals(mesh):
    """Custom normals in which a big flat face keeps its own normal next to a bevel. A flat face is taken as a whole
    (all its coplanar triangles together), so the weighting does not depend on how it was triangulated."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    region = [-1] * len(bm.faces)
    area, normal = [], []
    cos_flat = math.cos(math.radians(1.0))
    for f in bm.faces:
        if region[f.index] >= 0:
            continue
        rid = len(area)
        region[f.index] = rid
        stack = [f]
        a_sum = 0.0
        n_sum = f.normal * 0.0
        while stack:
            g = stack.pop()
            a = g.calc_area()
            a_sum += a
            n_sum += g.normal * a
            for e in g.edges:
                if not e.smooth:
                    continue
                for h in e.link_faces:
                    if region[h.index] < 0 and h.normal.dot(g.normal) > cos_flat:
                        region[h.index] = rid
                        stack.append(h)
        area.append(a_sum)
        normal.append(n_sum.normalized() if n_sum.length > 0.0 else f.normal.copy())
    out = []
    for f in bm.faces:
        for loop in f.loops:
            v = loop.vert
            # the smooth fan around this corner
            fan = {f.index: f}
            stack = [f]
            while stack:
                g = stack.pop()
                for e in g.edges:
                    if not e.smooth or (e.verts[0] is not v and e.verts[1] is not v):
                        continue
                    for h in e.link_faces:
                        if h.index not in fan:
                            fan[h.index] = h
                            stack.append(h)
            total = f.normal * 0.0
            for rid in {region[i] for i in fan}:
                total += normal[rid] * (area[rid] ** 2)
            out.append(tuple(total.normalized()) if total.length > 0.0 else tuple(f.normal))
    bm.free()
    mesh.normals_split_custom_set(out)
    mesh.update()


SHARP_DEG = 30.0      # the builders' rule (kit.shade): an edge is hard when its faces meet at more than this


def mark_sharp(bm, angle=SHARP_DEG):
    """Hard edges by angle, read from the finished triangles: the repairs make new edges, and those carry no flag."""
    limit = math.radians(angle)
    bm.normal_update()
    for e in bm.edges:
        e.smooth = len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0) <= limit


MICRO = 2.0e-3       # cm: an edge shorter than 20 um is boolean debris (the smallest modelled edge is over 60 um)
AREA_MIN = 6.0e-5    # cm2: Unreal's FBX import skips a triangle under 5e-5 cm2 as degenerate (FbxStaticMeshImport.cpp: the cross
#                      product of two edges has a squared length under SMALL_NUMBER); it dropped 143 of 14,272 before this rule
SHORT = 0.03         # cm: a triangle that small goes by collapsing its shortest edge, when that edge is under 0.3 mm
ENGINE_AREA = 5.0e-5 # cm2: the engine's own limit (check.ENGINE_AREA); AREA_MIN is that plus a margin
CAP_EDGE = 0.2       # cm: the caps fallback (drop_micro) never collapses an edge longer than 2 mm: that would be seen
CAP_AREA = 4.0 * AREA_MIN   # cm2: a flat sliver is flipped below this, and only when both triangles it leaves are larger


def _collapsible(e):
    """An edge whose collapse keeps the surface a surface: its two ends share exactly the two corners opposite it."""
    if len(e.link_faces) != 2:
        return False
    a, b = e.verts
    return len({x.other_vert(a) for x in a.link_edges} & {x.other_vert(b) for x in b.link_edges}) == 2


def _thickness(f):
    """A triangle's height over its longest edge."""
    return 2.0 * f.calc_area() / max(max(e.calc_length() for e in f.edges), 1.0e-12)


def _uv_continuous(e, uv):
    la, lb = e.link_loops
    return (la[uv].uv - lb.link_loop_next[uv].uv).length < 1.0e-5 and (la.link_loop_next[uv].uv - lb[uv].uv).length < 1.0e-5


def _flip_caps(bm, thin=MICRO):
    """A flat sliver is a corner that sits on a neighbour's edge (a T-junction a boolean left): three points in a line, all its edges
    long, so nothing can be collapsed. Turning its long edge hands the corner to the neighbour and both triangles get a real area. Only
    where the neighbour lies in the same plane on the same UV island, so neither the surface nor the texture moves, and only when both
    results are over CAP_AREA, so no flip is ever undone. Returns the count."""
    uv = bm.loops.layers.uv.active
    flipped = 0
    for f in [f for f in bm.faces if len(f.verts) == 3 and f.calc_area() < CAP_AREA and _thickness(f) < thin]:
        if not f.is_valid:
            continue
        e = max(f.edges, key=lambda e: e.calc_length())
        if len(e.link_faces) != 2 or e.seam or (uv is not None and not _uv_continuous(e, uv)):
            continue
        g = next(x for x in e.link_faces if x is not f)
        if len(g.verts) != 3 or g.material_index != f.material_index or g.calc_area() < AREA_MIN:
            continue
        apex = next(v for v in f.verts if v not in e.verts).co
        far = next(v for v in g.verts if v not in e.verts).co
        normal = g.normal
        turns = []
        for a, b in ((e.verts[0].co, apex), (apex, e.verts[1].co)):
            cross = (a - far).cross(b - far)
            turns.append(cross.normalized().dot(normal) if cross.length >= 2.0 * CAP_AREA else 0.0)
        if min(abs(t) for t in turns) < 0.999 or turns[0] * turns[1] < 0.0:
            continue
        if bmesh.utils.edge_rotate(e, False) is not None:
            flipped += 1
    return flipped


def drop_micro(bm, dist=MICRO, caps=False):
    """Remove what booleans leave behind and a game engine throws away anyway: the microscopic fans where a rounded corner meets a wall
    (every edge shorter than dist), flat slivers (_flip_caps), then every triangle under AREA_MIN by collapsing its shortest edge. The
    surface moves by less than SHORT / 2. What is left is counted by check.tiny(). Returns the number of faces removed.

    caps=True (LOD meshes only) also removes a flat sliver that _flip_caps had to leave because its long edge is a crease: its middle
    corner, which sits on that crease between the two ends, is merged into the nearer end. The crease does not move; the texture on the
    faces around the merged corner shifts by up to half that distance, which is why the full-detail mesh is not treated this way."""
    before = len(bm.faces)
    _flip_caps(bm)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=dist)
    for _ in range(12):
        big = [f for f in bm.faces if len(f.verts) > 3]
        if big:
            bmesh.ops.triangulate(bm, faces=big, quad_method='BEAUTY', ngon_method='BEAUTY')
        flipped = _flip_caps(bm)
        used, edges, pins = set(), [], []
        for f in sorted((f for f in bm.faces if f.calc_area() < AREA_MIN), key=lambda f: f.calc_area()):
            e = min(f.edges, key=lambda e: e.calc_length())
            pin = None
            if e.calc_length() >= SHORT:
                # the caps fallback moves a corner, so only for a triangle the engine would really drop (not the safety band up
                # to AREA_MIN): a pistol's LOD1 can have one in that band, which Unreal keeps
                if not (caps and f.calc_area() < ENGINE_AREA and _thickness(f) < dist and e.calc_length() < CAP_EDGE):
                    continue
                long_edge = max(f.edges, key=lambda e: e.calc_length())
                apex = next(v for v in f.verts if v not in long_edge.verts)       # the corner lying on the long edge
                pin = e.other_vert(apex)                                          # the end of the crease it goes to
            if _collapsible(e) and not any(v in used for w in e.verts for v in [w] + [x.other_vert(w) for x in w.link_edges]):
                edges.append(e)
                used.update(e.verts)
                if pin is not None:
                    pins.append((e.verts[0], e.verts[1], pin.co.copy()))
        if edges:
            bmesh.ops.collapse(bm, edges=edges, uvs=True)
            for a, b, co in pins:                    # the merged corner goes back onto the end of the crease
                for v in (a, b):
                    if v.is_valid:
                        v.co = co
        if not edges and not flipped:
            break
    return before - len(bm.faces)


def clean_micro(obj, caps=False):
    """drop_micro on a finished mesh, then its hard edges and weighted normals again. UVs stay where they are. Returns the faces removed."""
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    removed = drop_micro(bm, caps=caps)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    renormal(obj)
    return removed


def renormal(obj):
    """Hard edges and weighted normals again on a finished mesh; its triangles are left alone."""
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    mark_sharp(bm)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    weighted_normals(mesh)


def finish(obj):
    """Clean, triangulate, hard edges, weighted normals. Returns the count of edges that are not shared by exactly two faces."""
    if obj.get('finished'):
        return int(obj.get('open_edges', 0))
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    _repair(bm)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
    bad = _repair(bm)
    big = [f for f in bm.faces if len(f.verts) > 3]
    if big:
        bmesh.ops.triangulate(bm, faces=big, quad_method='BEAUTY', ngon_method='BEAUTY')
        bad = len([e for e in bm.edges if len(e.link_faces) != 2])
    if drop_micro(bm):
        bad = len([e for e in bm.edges if len(e.link_faces) != 2])
    mark_sharp(bm)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    weighted_normals(mesh)
    obj['finished'] = True
    obj['open_edges'] = bad
    return bad
