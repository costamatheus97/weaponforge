"""weaponforge: a small hard-surface toolkit (Blender 5.2, bmesh). Units are centimetres (scene unit scale 0.01).

Everything works on mesh data directly (no bpy.ops), so it runs the same from the live session and from `blender -b`.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

AXES = {'XZ': (0, 2, 1), 'YZ': (1, 2, 0), 'XY': (0, 1, 2)}


# ---------------------------------------------------------------------------------------------------------- scene helpers
def collection(name, parent=None):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def remove(obj):
    mesh = obj.data if obj.type == 'MESH' else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def wipe(coll):
    for obj in list(coll.objects):
        remove(obj)


def obj_from_bm(name, bm, coll):
    mesh = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def edit(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    return bm


def commit(obj, bm):
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def tag(obj, bone, group=None, mat='steel'):
    """Every part says which bone carries it, which group it belongs to and what it is made of (a key of bake.KINDS)."""
    obj['bone'] = bone
    obj['group'] = group or bone
    obj['mat'] = mat
    return obj


def setup_scene(scene=None):
    """Centimetres: one Blender unit is 1 cm (unit scale 0.01), which the FBX export then writes 1:1 for Unreal."""
    scene = scene or bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.01
    scene.unit_settings.length_unit = 'CENTIMETERS'
    return scene


# ------------------------------------------------------------------------------------------------------------ 2D profiles
def arc(cx, cy, r, a0, a1, n):
    """n + 1 points from angle a0 to a1 (degrees)."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n)))
            for k in range(n + 1)]


def circle(cx, cy, r, n):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def round_poly(pts, seg90=6):
    """A polygon with filleted corners. pts: [(a, b) or (a, b, r) or (a, b, r, steps)]; a corner with r > 0 becomes an arc
    of that radius (convex or concave), clamped so it never eats more than half of either neighbouring edge.

    The arc is cut into ceil(angle / 90 deg * seg90) chords, so a long flat arc (a back strap's arch: 30 cm radius, a few
    degrees) gets one chord in the game mesh and two in the bake source, and the bake source's middle point then stands
    0.05 cm outside the game mesh: further out than the bake's rays start (PLAYBOOK, "Bake"). Give such a corner its number
    of chords as a fourth value, the same in both meshes."""
    count = len(pts)
    out = []
    for i in range(count):
        p = Vector(pts[i][:2])
        r = pts[i][2] if len(pts[i]) > 2 else 0.0
        if r <= 1.0e-6:
            out.append((p.x, p.y))
            continue
        u = Vector(pts[i - 1][:2]) - p
        v = Vector(pts[(i + 1) % count][:2]) - p
        lu, lv = u.length, v.length
        u /= lu
        v /= lv
        theta = math.acos(max(-1.0, min(1.0, u.dot(v))))
        if theta < 1.0e-4 or abs(theta - math.pi) < 1.0e-4:
            out.append((p.x, p.y))
            continue
        d = r / math.tan(theta / 2)
        dmax = min(lu, lv) * 0.5
        if d > dmax:
            d = dmax
            r = d * math.tan(theta / 2)
        t1 = p + u * d
        t2 = p + v * d
        c = p + (u + v).normalized() * (r / math.sin(theta / 2))
        a1 = math.atan2(t1.y - c.y, t1.x - c.x)
        da = math.atan2(t2.y - c.y, t2.x - c.x) - a1
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        steps = int(pts[i][3]) if len(pts[i]) > 3 else max(1, int(math.ceil(abs(da) / (math.pi / 2) * seg90)))
        for k in range(steps + 1):
            ang = a1 + da * k / steps
            out.append((c.x + r * math.cos(ang), c.y + r * math.sin(ang)))
    # drop duplicates
    clean = []
    for q in out:
        if not clean or (abs(q[0] - clean[-1][0]) + abs(q[1] - clean[-1][1])) > 1.0e-6:
            clean.append(q)
    if len(clean) > 1 and (abs(clean[0][0] - clean[-1][0]) + abs(clean[0][1] - clean[-1][1])) <= 1.0e-6:
        clean.pop()
    return clean


def offset_line(p0, p1, dist):
    """The segment p0-p1 moved `dist` to its left (looking from p0 to p1)."""
    d = (Vector(p1) - Vector(p0)).normalized()
    n = Vector((-d.y, d.x)) * dist
    return (p0[0] + n.x, p0[1] + n.y), (p1[0] + n.x, p1[1] + n.y)


def line_x_at(p0, p1, b):
    """a on the line p0-p1 at second coordinate b."""
    t = (b - p0[1]) / (p1[1] - p0[1])
    return p0[0] + (p1[0] - p0[0]) * t


def span(outline, a):
    """Where the closed 2D outline [(a, b)] crosses the line "first coordinate = a": (lowest b, highest b), or None when the
    outline does not reach that far. Reads a profile at a station: a stock's bottom and top line at x, a plan's width at x.

    An outline from round_poly is single precision (mathutils), so its end lies up to 1e-6 away from the number it was drawn
    with: a station put exactly at that number is given the end's own values (tol), not None."""
    hits = []
    count = len(outline)
    tol = 1.0e-5
    for i in range(count):
        a0, b0 = outline[i][:2]
        a1, b1 = outline[(i + 1) % count][:2]
        if min(a0, a1) - tol <= a <= max(a0, a1) + tol:
            if abs(a1 - a0) < 1.0e-12:
                hits += [b0, b1]
            else:
                hits.append(b0 + (b1 - b0) * min(1.0, max(0.0, (a - a0) / (a1 - a0))))
    return (min(hits), max(hits)) if hits else None


def curve(points):
    """A smooth function through [(x, y)] (x rising) that never overshoots its points: straight through three in a line, level
    at a peak or a dip, constant beyond the ends. For a number that changes along a part (a width, a taper, a roundness)."""
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    count = len(xs)
    if count == 1:
        return lambda x: ys[0]
    h = [xs[i + 1] - xs[i] for i in range(count - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(count - 1)]
    m = [d[0]] + [0.0] * (count - 2) + [d[-1]]
    for i in range(1, count - 1):
        if d[i - 1] * d[i] > 0.0:                        # the monotone cubic of Fritsch and Carlson
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = max(k for k in range(count - 1) if xs[k] <= x)
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (3 * t2 - 2 * t3) * ys[i + 1]
                + (t3 - t2) * h[i] * m[i + 1])
    return f


def stations(marks, lo, hi, max_gap, min_gap=0.0, must=()):
    """Where to put the rings of a loft from lo to hi: lo, hi and the marks between them (the corners of its outline, the
    points of its width table), none closer than min_gap to the one before, and any gap wider than max_gap divided evenly.
    must: marks that get a ring whatever is near them (where a UV seam goes round the part); a mark too close to one is dropped."""
    must = {m for m in must if lo < m < hi}
    marks = {m for m in marks if lo < m < hi and all(abs(m - k) >= min_gap for k in must)}
    out = [lo]
    for x in sorted(marks | must) + [hi]:
        prev = out[-1]
        if x < hi and x not in must and x - prev < min_gap:
            continue
        steps = max(1, int(math.ceil((x - prev) / max_gap - 1.0e-9)))
        out += [prev + (x - prev) * i / steps for i in range(1, steps + 1)]
    if len(out) > 2 and out[-1] - out[-2] < min_gap and out[-2] not in must:
        del out[-2]
    return out


def section(hw, lo, hi, n, widest=0.5, top=2.0, bottom=2.0):
    """A closed oval as n points (a, b), symmetric about a = 0: half-width hw, from b = lo to b = hi, widest at
    lo + widest * (hi - lo). top / bottom say how square the upper and lower halves are: 2 is an ellipse, higher goes toward a
    rectangle with round corners. It starts at the bottom centre and goes round by +a, so point n / 2 is the top centre and
    equal indices on two sections line up for K.loft. n: a multiple of 4."""
    mid = lo + widest * (hi - lo)
    out = []
    for k in range(n):
        t = -math.pi / 2 + 2 * math.pi * k / n
        c, s = math.cos(t), math.sin(t)
        c = 0.0 if abs(c) < 1.0e-12 else c
        s = 0.0 if abs(s) < 1.0e-12 else s
        e = top if s > 0.0 else bottom
        half = (hi - mid) if s > 0.0 else (mid - lo)
        out.append((hw * math.copysign(abs(c) ** (2.0 / e), c), mid + half * math.copysign(abs(s) ** (2.0 / e), s)))
    return out


# -------------------------------------------------------------------------------------------------------------- solids
def loft(name, rings, coll):
    """A closed solid skinned over rings of 3D points (an organic part: a stock, a grip). Every ring has the same number of
    points, wound the same way and starting at matching points; a ring of one point closes the solid to a tip there. An open
    end is capped with one face."""
    bm = bmesh.new()
    made = [[bm.verts.new(p) for p in ring] for ring in rings]
    for a, b in zip(made[:-1], made[1:]):
        count = max(len(a), len(b))
        for k in range(count):
            j = (k + 1) % count
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[k], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[k], a[j], b[0]))
            else:
                bm.faces.new((a[k], a[j], b[j], b[k]))
    for ring in (made[0], made[-1]):
        if len(ring) > 1:
            bm.faces.new(ring)
    face_out(bm)
    return obj_from_bm(name, bm, coll)


def fillet_cutter(name, stations, coll, seg=3, out=0.3):
    """A cutter that rounds the corner between two faces of a solid along a path: boolean() it out of the solid.

    stations: (corner, u, v, r) at points along the corner's edge, in order: the corner itself, the two directions that leave
    it along the one face and along the other (both square to the edge, both pointing along the solid's surface), and the
    rounding's radius there.

    What bevel() cannot do and this can: the overlap clamp cannot shrink it (PLAYBOOK.md, "Modelling", item 38); the radius
    may change along the way; and the path may start or end outside the solid, so the rounding runs out through an end face
    the way a milled one does. To end a rounding in the middle of an edge, let r fall to about a millimetre over the last
    stations and move those corners out of the solid along -(u + v) by half of r: the cut then tapers to nothing, with no step.

    Its section is the corner less the rounding's disc. The arc's first and last chords are carried on past the two faces, so
    the cutter crosses them at a real angle and never lies in them."""
    rings = []
    for corner, u, v, r in stations:
        c, u, v = Vector(corner), Vector(u).normalized(), Vector(v).normalized()
        half = u.angle(v) / 2.0
        bis = (u + v).normalized()
        centre = c + bis * (r / math.sin(half))
        a0, a1 = c + u * (r / math.tan(half)) - centre, c + v * (r / math.tan(half)) - centre
        sweep = math.pi - 2.0 * half
        arc = [centre + (a0 * math.sin((1.0 - k / seg) * sweep) + a1 * math.sin(k / seg * sweep)) / math.sin(sweep) for k in range(seg + 1)]
        ext = max(0.5 * r, 0.05)
        rings.append([c - bis * out, arc[0] + (arc[0] - arc[1]).normalized() * ext] + arc + [arc[-1] + (arc[-1] - arc[-2]).normalized() * ext])
    return loft(name, rings, coll)


def edge_stations(path, y, radius, solid='right', fade_in=0.0, fade_out=0.0, end_r=0.10, step=0.25):
    """fillet_cutter() stations for the commonest corner: the edge an 'XZ' prism's outline makes with its side at this y.

    path: the stretch of the outline to round, as (x, z) points in order (the outline's own points where it bends, so the
    cutter follows the solid exactly; it may start and end beyond the solid). solid: the side of the direction of travel the
    solid lies on, 'right' or 'left', looking at the XZ plane with +X to the right and +Z up. fade_in / fade_out: over this
    length at the path's start / end the rounding grows from nothing / tapers to nothing (leave 0 where the path leaves the
    solid). Long stretches are divided every `step` so a fade has stations to change on."""
    pts = [Vector(path[0])]
    for q in path[1:]:
        a, b = pts[-1], Vector(q)
        n = max(1, int(math.ceil((b - a).length / step)))
        pts += [a.lerp(b, k / n) for k in range(1, n + 1)]
    along = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        along.append(along[-1] + (b - a).length)
    u = Vector((0.0, -1.0 if y > 0.0 else 1.0, 0.0))
    out = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        inward = Vector((t.y, 0.0, -t.x)) if solid == 'right' else Vector((-t.y, 0.0, t.x))
        s = 1.0
        if fade_in > 0.0:
            s = min(s, along[i] / fade_in)
        if fade_out > 0.0:
            s = min(s, (along[-1] - along[i]) / fade_out)
        s = max(0.0, min(1.0, s))
        s = s * s * (3.0 - 2.0 * s)
        r = end_r + (radius - end_r) * s
        gone = max(0.0, 1.0 - s / 0.35)                      # the last third of a fade also lifts the cutter out of the solid
        lift = gone * gone * (0.42 * end_r + 0.02)
        out.append((Vector((p.x, y, p.y)) - (u + inward).normalized() * lift, u, inward, r))
    return out


def prism(name, pts, plane, lo, hi, coll):
    """Extrude the 2D polygon pts (in `plane`: 'XZ', 'YZ' or 'XY') from lo to hi along the third axis."""
    ia, ib, ic = AXES[plane]
    bm = bmesh.new()

    def vert(p, w):
        co = [0.0, 0.0, 0.0]
        co[ia], co[ib], co[ic] = p[0], p[1], w
        return bm.verts.new(co)

    lo_ring = [vert(p, lo) for p in pts]
    hi_ring = [vert(p, hi) for p in pts]
    count = len(pts)
    bm.faces.new(lo_ring)
    bm.faces.new(hi_ring)
    for i in range(count):
        j = (i + 1) % count
        bm.faces.new((lo_ring[i], lo_ring[j], hi_ring[j], hi_ring[i]))
    face_out(bm)
    return obj_from_bm(name, bm, coll)


def prism_m(name, pts, matrix, lo, hi, coll):
    """A prism built in a local frame (profile in local XY, extruded along local Z from lo to hi), then moved by matrix."""
    obj = prism(name, pts, 'XY', lo, hi, coll)
    obj.data.transform(matrix)
    if Matrix(matrix).to_3x3().determinant() < 0.0:
        obj.data.flip_normals()
    obj.data.update()
    return obj


def box(name, lo, hi, coll):
    pts = [(lo[0], lo[2]), (hi[0], lo[2]), (hi[0], hi[2]), (lo[0], hi[2])]
    return prism(name, pts, 'XZ', lo[1], hi[1], coll)


def _first_side(axis, start):
    """The direction a round solid's first line of vertices lies in: `start` squared up to the axis, or any perpendicular."""
    if start is None:
        return axis.orthogonal().normalized()
    start = Vector(start)
    side = start - axis * start.dot(axis)
    if side.length < 1.0e-6:
        raise ValueError('start %r runs along the axis: give a direction across it' % (tuple(start),))
    return side.normalized()


def cylinder(name, p0, p1, r, seg, coll, r1=None, start=None):
    """A capped cylinder (or cone, r at p0 and r1 at p1) between two points. start: the direction one line of vertices lies in
    (see lathe)."""
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r if r1 is None else r1,
                          depth=axis.length)
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(axis.normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((p0 + p1) / 2) @ rot, verts=bm.verts)
    if start is not None:
        unit = axis.normalized()
        want = _first_side(unit, start)
        radial = max(((v.co - p0) - unit * (v.co - p0).dot(unit) for v in bm.verts), key=lambda q: q.length).normalized()
        angle = math.atan2(unit.dot(radial.cross(want)), radial.dot(want))
        bmesh.ops.rotate(bm, cent=p0, matrix=Matrix.Rotation(angle, 3, unit), verts=bm.verts)
    face_out(bm)
    return obj_from_bm(name, bm, coll)


def tube(name, p0, p1, r_out, r_in, seg, coll, start=None):
    """A closed annular solid (a ring / pipe wall) between two points. start: the direction one line of vertices lies in (see
    lathe)."""
    p0, p1 = Vector(p0), Vector(p1)
    axis = (p1 - p0).normalized()
    side = _first_side(axis, start)
    other = axis.cross(side)
    bm = bmesh.new()
    rings = []
    for base, radius in ((p0, r_out), (p1, r_out), (p1, r_in), (p0, r_in)):
        rings.append([bm.verts.new(base + (side * math.cos(2 * math.pi * k / seg) + other * math.sin(2 * math.pi * k / seg)) * radius)
                      for k in range(seg)])
    for i in range(4):
        a, b = rings[i], rings[(i + 1) % 4]
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((a[k], a[j], b[j], b[k]))
    face_out(bm)
    return obj_from_bm(name, bm, coll)


def text_solid(name, text, size, origin, x_dir, up_dir, depth, coll, align='CENTER', resolution=3, font=None, spacing=1.0, ink=0, wide=1.0):
    """Extruded text as a mesh: it reads along x_dir, stands along up_dir and is centred on the plane through origin
    (so it reaches `depth` to either side of it).

    It is lettering, and says so: when it is cut into (or joined onto) a part of the bake source, a thin copy of it is
    kept for the bake, which turns it into a mask of where the letters are (keep_mark below). The look can then fill the
    letters with paint (surface.paint, Weapon.paint). ink: which of the weapon's paints these letters take, 0, 1 or 2
    (say, white for the model and red for FIRE). Place the text with this function's own arguments or with K.transform;
    a text moved any other way leaves its mask behind.

    wide: the letters (and the spaces between them) made this many times as wide along x_dir, their height and depth as they
    were: 1.6 is an extended face. The text is stretched about its own origin along x_dir (the middle of the line with the
    default align), so the mark's plane (origin and normal, which is what keep_mark squashes its paint mask about) does not move:
    the mask follows the cutter. A wall seen at a grazing angle from the hip is short of width along the gun, not of height."""
    curve = bpy.data.curves.new(name, 'FONT')
    curve.body = text
    curve.size = size
    curve.extrude = depth
    curve.resolution_u = resolution
    curve.align_x = align
    curve.space_character = spacing
    if font is not None:
        curve.font = font
    tmp = bpy.data.objects.new(name + '_curve', curve)
    coll.objects.link(tmp)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(tmp.evaluated_get(depsgraph), depsgraph=depsgraph)
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(curve)
    ex = Vector(x_dir).normalized()
    ey = Vector(up_dir).normalized()
    ez = ex.cross(ey)
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = ex[i], ey[i], ez[i], origin[i]
    if wide != 1.0:
        mesh.transform(Matrix.Scale(wide, 4, (1.0, 0.0, 0.0)))        # along the text's own x, before it is put on its plane
    mesh.transform(m)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1.0e-5)
    face_out(bm)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj['mark'] = [float(v) for v in origin] + [ez.x, ez.y, ez.z, float(ink)]
    return obj


MARK_SINK = None      # a collection while the bake source is being built (stages.model), else None: where lettering is kept


def keep_mark(cutter):
    """If `cutter` is lettering (text_solid) and the bake source is being built, keep a copy of it for the bake.

    The copy is squashed to half its depth about the plane the text was set on. The cutter reaches `depth` under that
    plane, and its far face IS the floor of the engraving it cuts; a copy of the same depth would lie in that floor, and
    the bake's rays would find floor and copy by turns. At half the depth the copy lies above the floor everywhere
    inside a letter, so a ray from outside meets it first."""
    plane = cutter.get('mark')
    if MARK_SINK is None or plane is None:
        return None
    world = cutter.matrix_world
    at = world @ Vector(plane[0:3])
    out = (world.to_3x3() @ Vector(plane[3:6])).normalized()
    mesh = cutter.data.copy()
    mesh.transform(world)
    for v in mesh.vertices:
        v.co -= out * ((v.co - at).dot(out) * 0.5)
    mesh.update()
    dup = bpy.data.objects.new('Mark', mesh)
    MARK_SINK.objects.link(dup)
    dup['ink'] = int(round(plane[6]))
    dup.hide_render = True
    return dup


def lathe(name, profile, origin, axis, seg, coll, start=None):
    """Spin profile [(along, radius)] about `axis` through `origin`. Ends with radius 0 close to a point; others are capped.
    start: the direction one line of vertices lies in (with an even `seg`, another lies opposite). Without it the line falls
    wherever the axis's own perpendicular happens to point, a diagonal for a barrel along X. Give (0, 0, -1) to a part on the
    bore: it is then the same on both sides, and its underside has a line of edges for a UV seam (Weapon.seams, in_plane)."""
    axis = Vector(axis).normalized()
    side = _first_side(axis, start)
    other = axis.cross(side)
    origin = Vector(origin)
    bm = bmesh.new()
    rings = []
    for along, radius in profile:
        base = origin + axis * along
        if radius <= 1.0e-6:
            rings.append([bm.verts.new(base)])
        else:
            rings.append([bm.verts.new(base + (side * math.cos(2 * math.pi * k / seg) + other * math.sin(2 * math.pi * k / seg)) * radius)
                          for k in range(seg)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[k], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[k], a[j], b[0]))
            else:
                bm.faces.new((a[k], a[j], b[j], b[k]))
    if len(rings[0]) > 1:
        bm.faces.new(rings[0])
    if len(rings[-1]) > 1:
        bm.faces.new(rings[-1])
    face_out(bm)
    return obj_from_bm(name, bm, coll)


# ------------------------------------------------------------------------------------------- detail that follows a surface
def hatch(outline, angle_deg, pitch, origin=(0.0, 0.0), islands=()):
    """Parallel lines across a closed 2D outline: [[p0, p1]] at angle_deg to the first axis, `pitch` apart, cut off at the
    outline. Two calls, at +a and -a, are the two line sets of a checkering. islands: [((a, b), radius)], round patches the
    lines stop short of and pick up again behind: the flat a screw head sits in."""
    a = math.radians(angle_deg)
    along = Vector((math.cos(a), math.sin(a)))
    across = Vector((-along.y, along.x))
    o = Vector(origin)
    pts = [Vector(p[:2]) - o for p in outline]
    reach = [p.dot(across) for p in pts]
    out = []
    for k in range(int(math.ceil(min(reach) / pitch)), int(math.floor(max(reach) / pitch)) + 1):
        d = k * pitch + 1.0e-6                       # never exactly through a corner of the outline
        cuts = []
        for p, q in zip(pts, pts[1:] + pts[:1]):
            dp, dq = p.dot(across) - d, q.dot(across) - d
            if (dp < 0.0) != (dq < 0.0):
                cuts.append((p + (q - p) * (dp / (dp - dq))).dot(along))
        cuts.sort()
        spans = [(t0, t1) for t0, t1 in zip(cuts[0::2], cuts[1::2])]
        for centre, radius in islands:
            c = Vector(centre[:2]) - o
            off = c.dot(across) - d
            if abs(off) >= radius:
                continue
            half = math.sqrt(radius * radius - off * off)
            lo, hi = c.dot(along) - half, c.dot(along) + half
            spans = [part for t0, t1 in spans for part in ((t0, min(t1, lo)), (max(t0, hi), t1))]
        for t0, t1 in spans:
            if t1 - t0 > 1.0e-4:
                out.append([o + across * d + along * t0, o + across * d + along * t1])
    return out


def grooves_on(obj, lines, frame, coll, half_w=0.07, depth=0.06, lift=0.02, step=0.12, facing=0.35, name='grooves'):
    """V grooves that follow obj's surface, as one cutter for K.boolean: checkering on a stock, a border round it, a line.

    lines: polylines [[(a, b), ...]] drawn in the XY plane of `frame` (a 4x4 in the weapon frame whose Z axis points from the
    surface toward whoever looks at it); a closed one repeats its first point. Each is dropped onto the surface along that Z
    and becomes a triangular channel 2 * half_w wide and `depth` deep, standing `lift` proud so the cut is clean. Where the
    surface turns away (its normal under `facing` along Z) or is missed, the line stops. Make every cutter before cutting with
    any: they follow the surface as it is now. Lines that cross belong in separate cutters (one per direction).

    Cut with K.cut_grooves, not K.boolean: it looks for every groove afterwards. The cutter carries the places to look in its
    'probes' property: the middle of each section's top, then its bottom, six numbers a section."""
    from mathutils.bvhtree import BVHTree
    src = bmesh.new()
    src.from_mesh(obj.data)
    src.transform(obj.matrix_world)
    tree = BVHTree.FromBMesh(src)
    rot = frame.to_3x3()
    out_dir = (rot @ Vector((0.0, 0.0, 1.0))).normalized()
    bm = bmesh.new()
    probes = []

    def tube(run, closed):
        for sect in (run if closed else run[1:-1]):            # an open run's end sections are its caps: nothing to look for
            probes.extend((sect[0] + sect[1]) / 2)
            probes.extend(sect[2])
        rings = [[bm.verts.new(p) for p in sect] for sect in run]
        pairs = list(zip(rings, rings[1:] + rings[:1])) if closed else list(zip(rings[:-1], rings[1:]))
        for a, b in pairs:
            for k in range(3):
                j = (k + 1) % 3
                bm.faces.new((a[k], a[j], b[j]))
                bm.faces.new((a[k], b[j], b[k]))
        if not closed:
            bm.faces.new(rings[0])
            bm.faces.new(rings[-1])

    made = 0
    for line in lines:
        pts = [Vector(p[:2]) for p in line]
        closed = len(pts) > 3 and (pts[0] - pts[-1]).length < 1.0e-6
        if closed:
            pts = pts[:-1]
        fine = []                                     # the line again, in steps no longer than `step`
        for p, q in zip(pts, pts[1:] + (pts[:1] if closed else [])):
            n = max(1, int(math.ceil((q - p).length / step)))
            fine += [p + (q - p) * (i / n) for i in range(n)]
        if not closed:
            fine.append(pts[-1])
        runs, whole = [[]], True
        for i, p in enumerate(fine):
            before = fine[i - 1] if (i > 0 or closed) else fine[i]
            after = fine[(i + 1) % len(fine)] if (i + 1 < len(fine) or closed) else fine[i]
            t = after - before
            sect = None
            if t.length > 1.0e-9:
                t.normalize()
                hit, normal, _index, _dist = tree.ray_cast(frame @ Vector((p.x, p.y, 0.0)) + out_dir * 500.0, -out_dir)
                if hit is not None:
                    if normal.dot(out_dir) < 0.0:
                        normal = -normal
                    side = rot @ Vector((-t.y, t.x, 0.0))
                    side = side - normal * normal.dot(side)
                    if normal.dot(out_dir) >= facing and side.length > 1.0e-6:
                        side.normalize()
                        sect = (hit - side * half_w + normal * lift, hit + side * half_w + normal * lift, hit - normal * depth)
            if sect is None:
                whole = False
                if runs[-1]:
                    runs.append([])
            else:
                runs[-1].append(sect)
        if closed and not whole and len(runs) > 1 and runs[0] and runs[-1]:
            runs[0] = runs.pop() + runs[0]            # the loop's start fell in the middle of a run
        for run in runs:
            if len(run) >= (3 if closed and whole else 2):
                tube(run, closed and whole)
                made += 1
    src.free()
    if not made:
        bm.free()
        raise ValueError('grooves_on: no line reached the surface of %s (is the frame\'s Z pointing out of it?)' % obj.name)
    face_out(bm)
    out = obj_from_bm(name, bm, coll)
    if probes:
        out['probes'] = probes
    return out


def studs_on(obj, points, frame, coll, r, h, seg=8, facing=0.35, sink=0.012, name='studs'):
    """Small round studs standing on a surface (a pebbled rubber grip), for the bake source only: one mesh of closed domes,
    to be join()ed to the part, never cut into it or united with it (a thousand booleans for something the game mesh only
    gets through its normal map).

    points: (a, b) in the drawing plane of `frame`, whose Z points out of the surface (fittings.side_frame). Each is dropped
    onto the surface along -Z; a point that misses, or lands where the surface faces away by more than `facing` allows, is
    left out. r, h: a stud's radius at its foot and its height. Its foot is sunk `sink` into the surface, so no gap shows."""
    from mathutils.bvhtree import BVHTree
    src = bmesh.new()
    src.from_mesh(obj.data)
    tree = BVHTree.FromBMesh(src)
    rot = frame.to_3x3()
    out_dir = (rot @ Vector((0.0, 0.0, 1.0))).normalized()
    big = (r * r + h * h) / (2.0 * h)                    # the sphere the dome is a cap of
    top = math.asin(min(1.0, r / big))
    rings = ((r + sink, -sink),) + tuple((big * math.sin(top * k / 2.0), big * math.cos(top * k / 2.0) - (big - h)) for k in (2, 1))
    bm = bmesh.new()
    made = 0
    for a, b in points:
        hit, normal, _index, _dist = tree.ray_cast(frame @ Vector((a, b, 0.0)) + out_dir * 500.0, -out_dir)
        if hit is None:
            continue
        if normal.dot(out_dir) < 0.0:
            normal = -normal
        if normal.dot(out_dir) < facing:
            continue
        u = normal.orthogonal().normalized()
        v = normal.cross(u)
        loops = [[bm.verts.new(hit + normal * up + (u * math.cos(2.0 * math.pi * k / seg) + v * math.sin(2.0 * math.pi * k / seg)) * rad)
                  for k in range(seg)] for rad, up in rings]
        tip = bm.verts.new(hit + normal * h)
        for lo, hi in zip(loops[:-1], loops[1:]):
            for k in range(seg):
                j = (k + 1) % seg
                bm.faces.new((lo[k], lo[j], hi[j], hi[k]))
        for k in range(seg):
            bm.faces.new((loops[-1][k], loops[-1][(k + 1) % seg], tip))
        bm.faces.new(loops[0][::-1])
        made += 1
    src.free()
    if not made:
        bm.free()
        raise ValueError('studs_on: no point reached the surface of %s (is the frame\'s Z pointing out of it?)' % obj.name)
    face_out(bm)
    print('[kit] studs_on: %s: %d of %d studs stand on the surface' % (obj.name, made, len(points)), flush=True)
    return obj_from_bm(name, bm, coll)


def drop(obj, points, frame, facing=0.35):
    """Where points drawn in a frame land on a part: [(place on the surface, its normal there) or None].

    points: (a, b) in the drawing plane of `frame`, whose Z points out of the surface (fittings.side_frame). Each is dropped
    onto obj along -Z, as grooves_on and studs_on drop theirs; None where it misses or the surface faces away by more than
    `facing` allows. For detail that needs a place and a direction on a surface that is not flat: a screw head or a pin
    on a lofted stock (fittings.screw_cuts(place, normal, ...)), the floor of a recess."""
    from mathutils.bvhtree import BVHTree
    src = bmesh.new()
    src.from_mesh(obj.data)
    src.transform(obj.matrix_world)
    tree = BVHTree.FromBMesh(src)
    out_dir = (Matrix(frame).to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    found = []
    for a, b in points:
        hit, normal, _index, _dist = tree.ray_cast(Matrix(frame) @ Vector((a, b, 0.0)) + out_dir * 500.0, -out_dir)
        if hit is not None and normal.dot(out_dir) < 0.0:
            normal = -normal
        found.append((hit.copy(), normal.copy()) if hit is not None and normal.dot(out_dir) >= facing else None)
    src.free()
    return found


def _uncut(obj, probes, above=0.15):
    """The groove sections of `probes` that are not in obj, as the points on their bottoms. Each is looked at from `above` cm
    over its top, down its middle: the first thing met must be near its bottom, not the old surface."""
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    tree = BVHTree.FromBMesh(bm)
    missed = []
    for i in range(0, len(probes), 6):
        top, bottom = Vector(probes[i:i + 3]), Vector(probes[i + 3:i + 6])
        down = bottom - top
        deep = down.length
        if deep < 1.0e-9:
            continue
        down /= deep
        _hit, _normal, _index, dist = tree.ray_cast(top - down * above, down)
        if dist is not None and dist < above + 0.6 * deep:
            missed.append(bottom)
    bm.free()
    return missed


def cut_grooves(target, cutters, coll, solver='MANIFOLD'):
    """target minus the cutters of K.grooves_on, with every groove then looked for in the result.

    The exact solver leaves stretches of a groove uncut and says nothing: the mesh comes back closed and its volume is
    plausible (on fore-end checkering: two lines, half a centimetre each, a bald patch three diamonds long in the
    bake). The manifold solver cut every one of them, in a twentieth of the time. So the cutters are joined (they must not
    cross: one call per line direction) and cut with the manifold solver, and each section of each groove is probed. If any is
    missing the other solver is tried on a fresh copy; if both leave some uncut, that is an error saying how many and where."""
    if not isinstance(cutters, (list, tuple)):
        cutters = [cutters]
    cutters = [c for c in cutters if c is not None]
    probes = []
    for c in cutters:
        probes.extend(c.get('probes', ()))
    cutter = join('cut', cutters, coll) if len(cutters) > 1 else cutters[0]
    have = bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items
    order = [s for s in (solver, 'MANIFOLD', 'EXACT') if s in have]
    order = [s for i, s in enumerate(order) if s not in order[:i]]
    name = target.data.name
    before = target.data.copy()
    failed = []
    for how in order:
        boolean(target, cutter, solver=how, keep=True)
        missed = _uncut(target, probes)
        if not missed:
            break
        lo = [min(p[k] for p in missed) for k in range(3)]
        hi = [max(p[k] for p in missed) for k in range(3)]
        failed.append('the %s solver left %d of %d groove sections uncut, between (%.2f, %.2f, %.2f) and (%.2f, %.2f, %.2f)'
                      % (how, len(missed), len(probes) // 6, lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]))
        _give(target, before.copy(), name)
    else:
        bpy.data.meshes.remove(before)
        remove(cutter)
        raise RuntimeError('cut_grooves: %s: %s' % (target.name, '; '.join(failed)))
    bpy.data.meshes.remove(before)
    remove(cutter)
    if failed:
        print('[kit] cut_grooves: %s: %s; the %s solver cut them all' % (target.name, '; '.join(failed), how), flush=True)
    return target


# ------------------------------------------------------------------------------------------------------- mesh operations
def apply_modifiers(obj):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
    old = obj.data
    obj.modifiers.clear()
    obj.data = mesh
    mesh.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return obj


def _measure(mesh):
    """(volume, edges that do not have exactly two faces)."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    out = abs(bm.calc_volume(signed=True)), sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return out


def face_out(bm):
    """Make the faces consistent and looking outward; returns how many closed pieces had to be turned.

    Blender's recalc_face_normals guesses "outward", and for some solids it guesses wrong for the whole piece: a
    detailed pistol slide, an open-topped channel, came out of cleanup() with every face looking inward. Nothing showed it: grey
    renders light both sides alike and every size test took the volume without its sign. The bake then took the slide's
    normals as pointing INTO the game mesh, and the slide was black in any light (easily taken for a black finish). A
    closed piece has a volume whose sign says which way its faces look, so each closed piece is measured after Blender's
    guess and turned when the sign is negative. An open piece has no such test and keeps Blender's guess."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    seen = set()
    turned = 0
    for start in bm.faces:
        if start in seen:
            continue
        seen.add(start)
        stack, piece, closed = [start], [], True
        while stack:
            f = stack.pop()
            piece.append(f)
            for e in f.edges:
                if len(e.link_faces) != 2:
                    closed = False
                for g in e.link_faces:
                    if g not in seen:
                        seen.add(g)
                        stack.append(g)
        if not closed:
            continue
        volume = 0.0
        for f in piece:
            v = [w.co for w in f.verts]
            for i in range(1, len(v) - 1):
                volume += v[0].dot(v[i].cross(v[i + 1]))
        if volume < -6.0e-9:
            bmesh.ops.reverse_faces(bm, faces=piece)
            turned += 1
    if turned:
        bm.normal_update()
        print('[kit] face_out: %d closed piece(s) came out of Blender\'s guess inside out and were turned outward' % turned)
    return turned


def _signed(mesh):
    """The volume with its sign: negative when the faces of a closed mesh look inward."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    out = bm.calc_volume(signed=True)
    bm.free()
    return out


def _booleans(target, cutters, op, solver):
    for cutter in cutters:
        mod = target.modifiers.new('bool', 'BOOLEAN')
        mod.operation = op
        mod.solver = solver
        mod.object = cutter
    apply_modifiers(target)


def _give(obj, mesh, name):
    """obj gets this mesh under its old name; the mesh it had is dropped."""
    old = obj.data
    obj.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    mesh.name = name


def _pieces_volume(obj):
    """The volumes of the object's separate pieces added up, or None when it has open edges. Each piece counts as a solid of its
    own, whichever way its faces point, so the sum is never less than the space the pieces take up together: it is the most a
    cut with this object can remove, and the most a union with it can add."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if any(len(e.link_faces) != 2 for e in bm.edges):
        bm.free()
        return None
    total, seen = 0.0, set()
    for first in bm.faces:
        if first.index in seen:
            continue
        seen.add(first.index)
        stack, six = [first], 0.0
        while stack:
            face = stack.pop()
            co = [v.co for v in face.verts]
            for i in range(1, len(co) - 1):
                six += co[0].dot(co[i].cross(co[i + 1]))
            for e in face.edges:
                for other in e.link_faces:
                    if other.index not in seen:
                        seen.add(other.index)
                        stack.append(other)
        total += abs(six) / 6.0
    bm.free()
    return total * abs(obj.matrix_world.to_3x3().determinant())


def _one_piece(mesh):
    """The mesh is one connected piece. (Several pieces may overlap: a boolean merges them, and the volume drops by more than
    the cutter took, so the size test below is only for a part in one piece.)"""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    if not bm.verts:
        bm.free()
        return False
    seen, stack = {0}, [bm.verts[0]]
    while stack:
        for e in stack.pop().link_edges:
            for v in e.verts:
                if v.index not in seen:
                    seen.add(v.index)
                    stack.append(v)
    whole = len(seen) == len(bm.verts)
    bm.free()
    return whole


def _cut_volume(target_mesh, cutters):
    """The most these cutters can remove from the part or add to it (None when the size test does not apply: the part is in
    several pieces, or a cutter is not a closed solid)."""
    if not _one_piece(target_mesh):
        return None
    parts = [_pieces_volume(c) for c in cutters]
    return None if any(v is None for v in parts) else sum(parts)


def _broken(mesh, had, was_closed, op=None, cut=None):
    """What is wrong with a boolean's result, or None: the solid gone, a closed solid come back with open edges, or a solid of
    a size the operation cannot give (cut: the most the cutters can take or add, from _cut_volume). The last is the exact
    solver handing back a closed piece of the CUTTER in place of the part (a slide: 84.5 cm3 came back as the 0.32 cm3
    of the barrel hole's cutter that stood in the channel behind the wall it was to drill)."""
    volume, loose = _measure(mesh)
    if had > 1.0e-9 and volume < had * 1.0e-9:
        return 'nothing'
    if was_closed and loose:
        return 'a mesh with %d open edges' % loose
    if was_closed and cut is not None and op in ('DIFFERENCE', 'UNION', 'INTERSECT'):
        slack = 0.02 * had + 1.0e-4                    # gross errors only: a wrong piece is far outside these
        lo, hi = {'DIFFERENCE': (had - cut, had), 'UNION': (had, had + cut), 'INTERSECT': (0.0, min(had, cut))}[op]
        if not lo - slack <= volume <= hi + slack:
            return 'a solid of %.4f cm3 (it had %.4f, and this can only leave %.4f to %.4f)' % (volume, had, max(lo, 0.0), hi)
    return None


def _face_planes(mesh, matrix):
    """(centres, normals, offsets, lows, highs) of every face of `mesh` in the world, as numpy arrays (None for an empty mesh)."""
    import numpy as np
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.transform(matrix)
    bm.normal_update()
    if not bm.faces:
        bm.free()
        return None
    centres = np.array([f.calc_center_median()[:] for f in bm.faces])
    normals = np.array([f.normal[:] for f in bm.faces])
    lows = np.array([[min(v.co[i] for v in f.verts) for i in range(3)] for f in bm.faces])
    highs = np.array([[max(v.co[i] for v in f.verts) for i in range(3)] for f in bm.faces])
    bm.free()
    return centres, normals, (centres * normals).sum(axis=1), lows, highs


def coplanar_faces(target_mesh, target_matrix, cutter, tol=1.0e-4, limit=3):
    """Faces of the cutter that lie IN the plane of a face of the target and over it (the usual reason the exact solver fails a
    cut): [(cutter face centre, target face centre, normal)], up to `limit`, as world points. A cutter face is in the plane when
    its normal is the target face's (either way) and the plane's offset differs by under `tol` cm, and their boxes overlap.
    Costs (cutter faces x target faces) in numpy: only asked for when a cut has already gone to the second solver."""
    import numpy as np
    a = _face_planes(target_mesh, target_matrix)
    b = _face_planes(cutter.data, cutter.matrix_world)
    if a is None or b is None:
        return []
    ca, na, da, loa, hia = a
    cb, nb, db, lob, hib = b
    out = []
    for i in range(len(cb)):
        dots = na @ nb[i]
        off = np.where(dots > 0.0, da - db[i], da + db[i])
        near = (np.abs(dots) > 1.0 - 1.0e-6) & (np.abs(off) < tol)
        near &= np.all(loa <= hib[i] + tol, axis=1) & np.all(lob[i] <= hia + tol, axis=1)
        for j in np.nonzero(near)[0]:
            # overlap in the plane, not only in the box: the two boxes must share a stretch of more than a hair in every
            # direction but the normal's
            span = np.minimum(hia[j], hib[i]) - np.maximum(loa[j], lob[i])
            flat = np.abs(nb[i]) > 0.999
            if np.all(span[~flat] > tol) if flat.any() else np.all(span > tol):
                out.append((Vector(cb[i]), Vector(ca[j]), Vector(nb[i])))
                break
        if len(out) >= limit:
            break
    return out


def _say_face(centre, normal):
    n = max(range(3), key=lambda i: abs(normal[i]))
    side = '+-'[0 if normal[n] > 0 else 1]
    return 'a face at (%.3f, %.3f, %.3f) facing %s%s' % (centre[0], centre[1], centre[2], side, 'XYZ'[n]) if abs(normal[n]) > 0.99 else \
        'a face at (%.3f, %.3f, %.3f) with normal (%.2f, %.2f, %.2f)' % (tuple(centre) + tuple(normal))


BOOLEAN_HINT = ('Usual causes: a cutter face lying IN the plane of a face of the target (move it 0.02 to 0.04 cm off the face, or well '
                'past it); a ring cutter (a tube, a groove) with the same number of sides as the round part it cuts, so its vertices '
                'fall on the target\'s (give it another count, or turn it a degree or two: forms.turned)')


def boolean(target, cutters, op='DIFFERENCE', solver='EXACT', keep=False):
    """target = target <op> each cutter (one modifier per cutter, applied at once). Cutters are deleted unless keep.

    The exact solver fails on some cuts without raising an error, in three ways seen so far: it returns NOTHING (a cut that
    nearly coincides with an earlier one: the part is simply gone), it returns the part with sheets of the cutter left hanging
    on it (the second of several ring grooves round one body), or it returns a closed piece of the cutter in place of the part.
    So the result is measured: when the solid has vanished, a closed solid has come back with open edges, or its volume is one
    the operation cannot give, the cutters are applied one by one and each one that goes wrong is done with the manifold solver
    instead (said in the log). A result that is still broken with both solvers is an error. A fourth way:
    the part comes back whole but INSIDE OUT (a detailed slide); that is turned back here and said in the log."""
    if not isinstance(cutters, (list, tuple)):
        cutters = [cutters]
    cutters = [c for c in cutters if c is not None]
    for cutter in cutters:
        keep_mark(cutter)
    name = target.data.name
    before = target.data.copy()
    had, loose = _measure(before)
    closed = loose == 0
    outward = closed and _signed(before) > 0.0
    cut = _cut_volume(before, cutters) if closed else None
    _booleans(target, cutters, op, solver)
    if _broken(target.data, had, closed, op, cut):
        _give(target, before, name)
        have = bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items
        other = next((s for s in ('MANIFOLD', 'EXACT', 'FLOAT') if s != solver and s in have), 'FLOAT')
        redone = []
        flat_found = []
        for index, cutter in enumerate(cutters):
            step = target.data.copy()
            had = _measure(step)[0]
            cut = _cut_volume(step, [cutter]) if closed else None
            _booleans(target, [cutter], op, solver)
            why = _broken(target.data, had, closed, op, cut)
            if not why:
                bpy.data.meshes.remove(step)
                continue
            _give(target, step, name)
            if len(flat_found) < 3:
                try:
                    flat_found += [(index + 1, cutter.name) + t for t in coplanar_faces(step, target.matrix_world, cutter)]
                except Exception as exc:                     # the hint must never turn a repaired cut into an error
                    print('[kit] boolean: (the coplanar test failed: %r)' % exc, flush=True)
            _booleans(target, [cutter], op, other)
            again = _broken(target.data, had, closed, op, cut)
            if again:
                raise RuntimeError('boolean: %s %s %s gives %s with the %s solver and %s with the %s solver'
                                   % (target.name, op, cutter.name, why, solver, again, other))
            redone.append((why, had, _measure(target.data)[0], index + 1))
        why, had, left = redone[0][:3] if redone else ('a broken mesh only with all the cuts at once', 0.0, 0.0)
        which = ', '.join(str(r[3]) for r in redone) or 'none'             # counted in the order the builder listed them
        print('[kit] boolean: %s %s: the %s solver returned %s; %d of %d cuts were done with the %s solver instead'
              ' (cut %s; the first took the volume from %.4f to %.4f). %s%s'
              % (target.name, op, solver, why, len(redone), len(cutters), other, which, had, left,
                 ''.join('Coplanar: cut %d (%s) has %s in the plane of %s of the target. ' % (n, cname, _say_face(c, nrm), _say_face(t, nrm))
                         for n, cname, c, t, nrm in flat_found[:1]), BOOLEAN_HINT), flush=True)
    else:
        bpy.data.meshes.remove(before)
    if outward and _signed(target.data) < 0.0:
        # every size test above takes the volume without its sign, so a solid that comes back with all its faces turned
        # inward passed them: it looks right in grey, bakes with its normals pointing into the part, and is black in any light
        target.data.flip_normals()
        target.data.update()
        print('[kit] boolean: %s %s: the result came back inside out; its faces were turned outward again' % (target.name, op), flush=True)
    if not keep:
        for cutter in cutters:
            remove(cutter)
    return target


def join(name, objs, coll):
    """One object holding the geometry of all of objs (their object transforms applied); the originals are deleted."""
    bm = bmesh.new()
    for obj in objs:
        keep_mark(obj)          # lettering joined into one cutter with other cuts: kept now, the joined object is not lettering
        tmp = obj.data.copy()
        tmp.transform(obj.matrix_world)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    for obj in objs:
        remove(obj)
    return obj_from_bm(name, bm, coll)


def copy(obj, name, coll):
    dup = bpy.data.objects.new(name, obj.data.copy())
    dup.matrix_world = obj.matrix_world.copy()
    coll.objects.link(dup)
    return dup


def transform(obj, matrix):
    obj.data.transform(matrix)
    obj.data.update()
    plane = obj.get('mark')
    if plane is not None:          # lettering (text_solid): the plane it was set on moves with it
        at = matrix @ Vector(plane[0:3])
        out = (matrix.to_3x3() @ Vector(plane[3:6])).normalized()
        obj['mark'] = [at.x, at.y, at.z, out.x, out.y, out.z, plane[6]]
    return obj


def mirror_y(obj, name, coll):
    """A copy mirrored across the XZ plane (the gun's other side), winding fixed."""
    dup = copy(obj, name, coll)
    dup.data.transform(Matrix.Scale(-1.0, 4, (0.0, 1.0, 0.0)))
    dup.data.flip_normals()
    dup.data.update()
    return dup


def rot_y(pivot_xz, degrees):
    """Rotation about the lateral axis through (x, z). Positive degrees tip +Z toward -X (a hammer cocking back)."""
    px, pz = pivot_xz
    pivot = Vector((px, 0.0, pz))
    return Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(-degrees), 4, 'Y') @ Matrix.Translation(-pivot)


def bevel(obj, pred, width, seg=2, profile=0.5, clamp=True):
    """Bevel the edges for which pred(edge, mid, direction) is true.

    clamp is Blender's overlap clamp. It keeps a bevel from running over its neighbours by shrinking the width of the WHOLE
    call, and says nothing: one chosen edge that runs on into a nearly parallel one (a flat that is tangent to an arc) is
    enough to turn 0.30 cm into 0.008 on every edge of the call (on an action body; PLAYBOOK.md, "Modelling", item 38). So
    the strip that came out is measured against the one asked for, and a note is printed when most of it is missing."""
    bm = edit(obj)
    bm.normal_update()
    edges = []
    asked = 0.0
    for e in bm.edges:
        a, b = e.verts[0].co, e.verts[1].co
        if pred(e, (a + b) / 2, (b - a).normalized()):
            edges.append(e)
            if len(e.link_faces) == 2:
                # the strip this width makes along this edge: its chord across the corner, times the edge's length
                bend = e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0)
                asked += 2.0 * width * math.sin(bend / 2.0) * e.calc_length()
    made = None
    if edges:
        res = bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type='OFFSET', segments=seg, profile=profile, affect='EDGES',
                              clamp_overlap=clamp)
        if clamp and asked > 1.0e-6:
            made = sum(f.calc_area() for f in res.get('faces', ()) if f.is_valid)
    commit(obj, bm)
    if made is not None and made < 0.35 * asked:
        print('[kit] bevel: %s: %.3f cm was asked for on %d edge(s) and the overlap clamp left about %.0f%% of it. Give the '
              'bevel an edge to stop on, or pass clamp=False if nothing lies within its width' % (obj.name, width, len(edges), 100.0 * made / asked),
              flush=True)
    return len(edges)


def edge_faces_normals(e):
    return [f.normal.copy() for f in e.link_faces]


def in_plane(point, normal, tol=1.0e-3):
    """A pred(edge, mid, direction) for bevel and for Weapon.seams: true for an edge that lies in the plane through `point`
    square to `normal` (both ends within tol cm of it). in_plane((0, 0, 0), (0, 1, 0)) is the weapon's centre plane."""
    point, normal = Vector(point), Vector(normal).normalized()

    def pred(e, _mid=None, _direction=None):
        return all(abs((v.co - point).dot(normal)) < tol for v in e.verts)
    return pred


def is_outline(e, axis, value, tol=1.0e-4):
    """Both ends of the edge lie on the plane axis = value (a prism's cap outline)."""
    return abs(e.verts[0].co[axis] - value) < tol and abs(e.verts[1].co[axis] - value) < tol


def on_rim(e, axis):
    """The edge is on the rim of a flat cap square to `axis`: one of its faces is the cap, the other is not. After a boolean a
    cap is several faces, and the edges between them lie in the cap's plane too, so is_outline() is true for them and a bevel
    'of the outline' runs across the flat as well; this is false for them."""
    return sum(1 for f in e.link_faces if abs(f.normal[axis]) > 0.5) == 1


def side_normal(e, axis):
    """The normal of the edge's face that is not a cap perpendicular to `axis` (for outline edges of a prism)."""
    for f in e.link_faces:
        if abs(f.normal[axis]) < 0.5:
            return f.normal
    return None


def shade(obj, angle=30.0, flats=False):
    """Smooth shading, with a hard edge wherever two faces meet at more than `angle` degrees.

    flats=True also writes weighted normals (mesh.weighted_normals): a big flat face keeps its own normal beside a rounded
    corner. Without it the flat's corners lean toward the round, the whole face shades as a gradient, in streaks along its
    triangles, and the bake copies the streaks into the normal map (magazine walls). It is for a bake source with
    large flats; the game mesh gets the same from its own finish. Edges softer than `angle` on such a flat all but vanish
    (their normals become the flat's), so make a groove's edges hard: lower `angle` under the groove's slope."""
    mesh = obj.data
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    mesh.set_sharp_from_angle(angle=math.radians(angle))
    mesh.update()
    if flats:
        from . import mesh as M
        M.weighted_normals(mesh)
    return obj


def _pinched(bm, dist):
    """The faces a weld at `dist` would pinch: a face that holds, at two places of its outline that are not next to each
    other, vertices about to become one. Welded, such a face touches itself, and the stretch of its outline between the two
    places comes away as a face of its own, lying over whatever that stretch went round. On a barrel it went round
    the holes of seven engraved letters: a boolean had left an edge 0.00004 cm long beside the eighth (an edge of the
    letter's wall, not of the flank), the weld closed it, the seven were capped, and recalc_face_normals then turned their
    walls inside out. The mesh stayed closed, in one piece and of the right volume to four figures; the letters were simply
    not there in the render or the bake.

    A run of such vertices one after another along the outline is not a pinch: it is an edge of no length closing, which is
    what the weld is for (a bevel the overlap clamp left without width is hundreds of them)."""
    target = bmesh.ops.find_doubles(bm, verts=bm.verts, dist=dist)['targetmap']
    if not target:
        return []

    def root(v):
        while v in target:
            v = target[v]
        return v

    faces = set()
    for v in set(target) | set(target.values()):
        faces.update(f for f in v.link_faces if len(f.verts) > 3)
    out = []
    for f in faces:
        ids = [root(v) for v in f.verts]
        runs = {}
        for i, r in enumerate(ids):
            if r is not ids[i - 1]:
                runs[r] = runs.get(r, 0) + 1
        if any(n > 1 for n in runs.values()):
            out.append(f)
    return out


def cleanup(obj, merge=1.0e-4, dissolve_deg=0.5, keep=None):
    """Weld, drop degenerate geometry and merge coplanar faces left by booleans. keep: pred(edge, mid, direction) for edges the
    merge must leave alone: where a UV seam will run over a flat stretch (Weapon.seams), or the line is gone when it is wanted.

    A face the weld would pinch is cut into triangles first (_pinched); with dissolve_deg 0 it stays in triangles."""
    bm = edit(obj)
    pinched = _pinched(bm, merge)
    if pinched:
        print('[kit] cleanup: %s: %d face(s) the weld would have pinched were cut into triangles first' % (obj.name, len(pinched)), flush=True)
        bmesh.ops.triangulate(bm, faces=pinched)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=merge)
    if dissolve_deg > 0.0:
        delimit = {'NORMAL'}
        if keep is not None:
            for e in bm.edges:
                a, b = e.verts[0].co, e.verts[1].co
                e.seam = (b - a).length > 1.0e-9 and bool(keep(e, (a + b) / 2, (b - a).normalized()))
            delimit.add('SEAM')
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(dissolve_deg), verts=bm.verts, edges=bm.edges, delimit=delimit)
    face_out(bm)
    commit(obj, bm)
    return obj


def mend(obj, sides=8):
    """Close the pinholes a cut leaves in a bake source, and say so. Returns how many were closed.

    cleanup() drops the sliver faces a boolean makes, and now and then the faces round one do not meet where it was: a hole a
    millimetre across with a stray edge hanging in it (a fore-end: one hole of five edges among 24,000 faces of
    checkering). Nothing complains, because only game meshes are checked for being closed, and the bake's rays go through the
    hole to the far wall. So: stray edges and points are deleted and every hole of up to `sides` edges is given a face. A
    larger hole is not a pinhole and is left for the note to report."""
    bm = edit(obj)
    stray = [e for e in bm.edges if not e.link_faces]
    if stray:
        bmesh.ops.delete(bm, geom=stray, context='EDGES')
    loose = [v for v in bm.verts if not v.link_edges]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    rim = [e for e in bm.edges if len(e.link_faces) == 1]
    closed = 0
    if rim:
        closed = len(bmesh.ops.holes_fill(bm, edges=rim, sides=sides)['faces'])
        face_out(bm)
    left = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    commit(obj, bm)
    if stray or closed or left:
        print('[kit] mend: %s: closed %d pinhole(s), dropped %d stray edge(s); %d edge(s) still without two faces'
              % (obj.name, closed, len(stray), left), flush=True)
    return closed


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for obj in objs:
        for v in obj.data.vertices:
            co = obj.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], co[i])
                hi[i] = max(hi[i], co[i])
    return lo, hi
