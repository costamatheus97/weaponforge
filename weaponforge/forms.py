"""weaponforge: the big forms of a moulded or machined body, and the cuts that follow its surface. Built with kit.py; nothing here
knows any one weapon's dimensions: the section, the surface and the segment counts come in as arguments.

  section_loft     a body skinned over a faceted section that changes along the gun (sections.facet_ring makes the rings)
  pocket, boss     a pocket sunk into a curved side and a round boss standing out of it, both following the surface
  slab             a cutter that takes away what lies outside a plane (a chamfer across an edge, a sloped face)
  hit, surface_frame, engrave, ring_cut
                   a mark laid on the surface where a ray meets it: the frame (x along the surface, z out of it), and the
                   cutters of an engraved polygon or a thin ring, optionally filled with paint by the look (ink)
  inset_poly, cap_strip, bar_pts, ball, about_bore, turned, bore_seam
                   the small geometry the above are made of

Moved from AssaultG3 with their arithmetic unchanged, so that weapon builds to the same vertices from them.
PLAYBOOK, "Modelling", item 66 says when to start from these. The rules they keep:

  * a cutter's vertices never lie on the target's face: a pocket's lip is 0.04 outside the surface, its walls run on `lift`
  * a cavity is never closed: a pocket is open to the outside (item 8)
  * the rings of a loft line up: every ring has the same point count (sections.facet_ring), and a ring goes in at every corner
    of the side outline and every knot of the tables, or the corner is cut off (item 11)
"""
import math

import bmesh
from mathutils import Matrix, Vector

from . import kit as K
from . import sections as S

DOWN = (0.0, 0.0, -1.0)                # where a round part on the bore starts: a line of edges underneath, for the UV seam


# ------------------------------------------------------------------------------------------------------- the faceted loft
TWIST_TOL = 0.03          # cm: a four-sided facet whose corners are this far from one plane is said to be twisted (section_loft). AssaultG3's
#                           lofts reach 0.026 and build clean; SmgG2's receiver, whose booleans failed, has facets at 0.052


def twist(p0, p1, p2, p3):
    """How far apart the two diagonals of the four-sided facet p0 p1 p2 p3 (in order round it) pass, cm: 0 for four corners in one
    plane, whatever the facet's size or shape. (A flat quad is two triangles whichever diagonal splits it; a twisted one is two
    different surfaces by the diagonal, and a boolean may split it the other way than the loft's own triangulation does.)"""
    p0, p1, p2, p3 = (Vector(p) for p in (p0, p1, p2, p3))
    n = (p2 - p0).cross(p3 - p1)
    if n.length < 1.0e-12:
        return 0.0                                   # diagonals parallel: a degenerate sliver, not a twist
    return abs((p1 - p0).dot(n)) / n.length


def twisted_facets(rings, tol=TWIST_TOL):
    """Every four-sided facet between two neighbouring rings whose corners are not in one plane by more than `tol` cm:
    [(ring i, facet k, twist cm)] worst first. rings: [[(x, y, z)]], every ring the same count; facet k lies between points k and
    k + 1 of rings i and i + 1."""
    out = []
    for i, (a, b) in enumerate(zip(rings[:-1], rings[1:])):
        if len(a) < 3 or len(a) != len(b):
            continue
        for k in range(len(a)):
            j = (k + 1) % len(a)
            t = twist(a[k], a[j], b[j], b[k])
            if t > tol:
                out.append((i, k, t))
    return sorted(out, key=lambda r: -r[2])


def section_loft(name, side, section, coll, x0, x1, max_gap, min_gap, knots=(), must=(), warp=None, twist_tol=TWIST_TOL):
    """A closed body skinned over sections along x (a shell, a receiver, a handguard).

    side: the body's side outline as K.round_poly gives it, [(x, z)]; at each station K.span reads its underside and top.
    section(x, lo, hi): the ring at that station, [(y, z)] from the bottom centre round by +y (sections.facet_ring of the
    weapon's own corners; every ring the same count). Rings go at every point of `side` and every x in `knots` (the points of
    the width and height tables: a ramp's ends must be crisp), with gaps over `max_gap` divided and marks closer than
    `min_gap` dropped, except those in `must` (K.stations). Between knots the facets are flat, so few rings are needed: 6 cm
    and 0.15 in the game mesh, 3 cm and 0.04 in the bake source worked on AssaultG3.
    warp(x, z): the x a ring's point really goes to (a raked butt: each ring sheared toward the toe), or None.
    twist_tol: a four-sided facet between two rings whose corners are further than this (cm) from one plane is said in the log
    (`[kit] warning`) with the facet, the rings and the amount; None says nothing. Such a facet is two triangles whose diagonal a
    later boolean may turn the other way, and what comes of that is a volume message two steps on that names no cause.

    The section must change along the gun (item 65 (b)): a constant section swept along a line still looks extruded."""
    marks = [p[0] for p in side] + list(knots)
    rings = []
    for x in K.stations(marks, x0, x1, max_gap, min_gap, must=must):
        lo, hi = K.span(side, x)
        if warp is None:
            rings.append([(x, y, z) for y, z in section(x, lo, hi)])
        else:
            rings.append([(warp(x, z), y, z) for y, z in section(x, lo, hi)])
    if twist_tol is not None:
        bad = twisted_facets(rings, twist_tol)
        for i, k, t in bad[:4]:
            a, b = rings[i], rings[i + 1]
            j = (k + 1) % len(a)
            mid = lambda r: ((r[k][1] + r[j][1]) / 2.0, (r[k][2] + r[j][2]) / 2.0)        # the facet's middle (y, z) at one ring
            print('[kit] warning: section_loft %s: facet %d (between points %d and %d of the section; at y %.2f, z %.2f on ring %d and '
                  'y %.2f, z %.2f on ring %d) between rings %d and %d (x %.2f to %.2f) is twisted by %.3f cm: its four corners are '
                  'not in one plane, so a boolean may turn its diagonal. Make the facet\'s two edges parallel (the corner moves the '
                  'same way at both rings: a knot where its width changes, or a ramp that starts and ends on a ring), or accept it '
                  'and watch the volume checks after the booleans'
                  % (name, k, k, j, mid(a)[0], mid(a)[1], i, mid(b)[0], mid(b)[1], i + 1, i, i + 1, a[0][0], b[0][0], t), flush=True)
        if len(bad) > 4:
            print('[kit] warning: section_loft %s: %d facets in all are twisted by more than %.3f cm (the worst %.3f cm)'
                  % (name, len(bad), twist_tol, bad[0][2]), flush=True)
    return K.loft(name, rings, coll)


# ----------------------------------------------------------------------------------------- what follows a curved surface
def inset_poly(pts, d):
    """A closed outline moved `d` inward along its edges' bisectors (negative: outward). For the rounded, convex outlines of
    pockets, whose corners are arcs."""
    area = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1]))
    sign = 1.0 if area > 0.0 else -1.0                     # counter-clockwise: the inside is on the left of the travel
    out = []
    count = len(pts)
    for i in range(count):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % count]
        n = []
        for p, q in ((a, b), (b, c)):
            t = Vector((q[0] - p[0], q[1] - p[1])).normalized()
            n.append(Vector((-t.y, t.x)) * sign)
        v = (n[0] + n[1]) / max(0.2, 1.0 + n[0].dot(n[1]))
        out.append((b[0] + v.x * d, b[1] + v.y * d))
    return out


def cap_strip(bm, ring):
    """Close a ring of vertices that is not flat with a strip of triangles between its two halves (split at its rearmost and
    foremost vertices), not a fan: a fan from the middle of a long thin floor shows its rays in the shading."""
    n = len(ring)
    xs = [v.co.x for v in ring]
    i0, i1 = xs.index(min(xs)), xs.index(max(xs))
    a = [ring[(i0 + k) % n] for k in range((i1 - i0) % n + 1)]
    b = [ring[(i0 - k) % n] for k in range((i0 - i1) % n + 1)]
    ia = ib = 0
    while ia < len(a) - 1 or ib < len(b) - 1:
        if ib >= len(b) - 1 or (ia < len(a) - 1 and a[ia + 1].co.x <= b[ib + 1].co.x):
            tri = (a[ia], a[ia + 1], b[ib])
            ia += 1
        else:
            tri = (a[ia], b[ib + 1], b[ib])
            ib += 1
        if len(set(tri)) == 3:                              # the two halves share their first and last vertex
            bm.faces.new(tri)


def pocket(surface_y, outline, side, depth, inset, coll, lift=0.40, name='pocket'):
    """A cutter for a pocket in a body's side that follows its curved surface: the outline [(x, z)] on the surface (densify it:
    sections.densify), a floor `depth` under it and drawn in by `inset` (so the walls slope), and the walls run on `lift`
    outside the surface. surface_y(x, z): how far from the middle the surface is (sections.facet_y of the weapon's section);
    side +1 is the left. The caps are strips, not n-gons: the floor is not flat. Flutes, vents, a recess round a port."""
    floor_o = inset_poly(outline, inset)
    outer_o = inset_poly(outline, -inset * lift / depth)
    bm = bmesh.new()
    rings = [[], [], []]
    for (fx, fz), (qx, qz), (ox, oz) in zip(floor_o, outline, outer_o):
        ys = surface_y(qx, qz)
        rings[0].append(bm.verts.new((fx, side * (surface_y(fx, fz) - depth), fz)))
        rings[1].append(bm.verts.new((qx, side * (ys + 0.04), qz)))     # the lip a hair outside the surface, not on it: a cutter's vertices on the target's face spoil the exact solver
        rings[2].append(bm.verts.new((ox, side * (ys + lift), oz)))
    count = len(outline)
    for a, b in ((rings[0], rings[1]), (rings[1], rings[2])):
        for k in range(count):
            j = (k + 1) % count
            bm.faces.new((a[k], a[j], b[j], b[k]))
    for ring in (rings[0], rings[2]):
        cap_strip(bm, ring)
    K.face_out(bm)
    return K.obj_from_bm(name, bm, coll)


def boss(surface_y, x, z, r, h, side, coll, seg, name='boss'):
    """A round boss standing out of a body's side round a pin or a button (to UNION): its flat face `h` above the highest the
    surface gets under it (sections.boss_top), its foot well inside the body, its rim chamfered. seg(lo, hi): the builder's
    segment dial (game mesh, bake source); a boss of 0.6 cm radius took (8, 24)."""
    top = S.boss_top(surface_y, x, z, r, h)
    foot = top - h - 0.45
    along = top - foot
    prof = [(0.0, 0.0), (0.0, r), (along - 0.12, r), (along - 0.07, r - 0.03), (along, r - 0.13), (along, 0.0)]
    return K.lathe(name, prof, (x, side * foot, z), (0.0, side, 0.0), seg(8, 24), coll)


def slab(quad, normal, depth, coll, name='cut'):
    """A cutter: the quad (four points in a plane, in order) pushed `depth` along `normal`: what lies outside that plane there."""
    n = Vector(normal).normalized() * depth
    bm = bmesh.new()
    low = [bm.verts.new(p) for p in quad]
    high = [bm.verts.new(Vector(p) + n) for p in quad]
    bm.faces.new(low)
    bm.faces.new(high)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((low[i], low[j], high[j], high[i]))
    K.face_out(bm)
    return K.obj_from_bm(name, bm, coll)


# ------------------------------------------------------------------------------------------- marks found on the surface
def hit(body, origin, direction):
    """Where a ray from origin along direction first meets body, and the surface's normal there; None for a miss. Start the ray
    well outside the part: it takes the FIRST surface it meets."""
    ok, loc, nrm, _ = body.ray_cast(Vector(origin), Vector(direction).normalized())
    return (loc.copy(), nrm.normalized()) if ok else None


def surface_frame(loc, nrm, up=(0.0, 0.0, 1.0)):
    """The frame of a mark lying on a surface: x reads along the surface (turned so that it reads left to right as seen from
    outside), y is `up` made tangent, z the outward normal; origin at loc. A mark set in it lies flat on the slope it is on."""
    n = Vector(nrm).normalized()
    u = Vector(up)
    ey = (u - n * u.dot(n)).normalized()
    ex = ey.cross(n)
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = ex[i], ey[i], n[i], loc[i]
    return m


def engrave(pts, frame, depth, coll, ink=None, name='cut'):
    """A cutter for a mark: the 2D polygon pts in the frame, reaching depth to either side of the surface. ink: a paint number,
    for a mark the look fills (the same mechanism as K.text_solid's: `paint` in the weapon)."""
    obj = K.prism_m(name, pts, frame, -depth, depth, coll)
    if ink is not None:
        at = frame.translation
        n = frame.to_3x3().col[2]
        obj['mark'] = [at.x, at.y, at.z, n.x, n.y, n.z, float(ink)]
    return obj


def ring_cut(frame, r, w, depth, coll, ink=None, n=20):
    """A thin ring on a surface (a cutter): outer radius r, wall w, reaching depth to either side."""
    c, nrm = frame.translation, frame.to_3x3().col[2]
    obj = K.tube('cut', c - nrm * depth, c + nrm * depth, r, r - w, n, coll)
    if ink is not None:
        obj['mark'] = [c.x, c.y, c.z, nrm.x, nrm.y, nrm.z, float(ink)]
    return obj


def bar_pts(x0, y0, x1, y1, w):
    """A bar of width w from (x0, y0) to (x1, y1), as four points (a stroke of a pictogram)."""
    d = Vector((x1 - x0, y1 - y0))
    nrm = Vector((-d.y, d.x)).normalized() * (w / 2)
    return [(x0 + nrm.x, y0 + nrm.y), (x1 + nrm.x, y1 + nrm.y), (x1 - nrm.x, y1 - nrm.y), (x0 - nrm.x, y0 - nrm.y)]


# ---------------------------------------------------------------------------------------------------- small geometry
def ball(name, centre, r, axis, seg_n, coll):
    """A ball of radius r at centre, its poles along axis (a lathe of a half circle): a detent ball."""
    prof = [(-r, 0.0)] + [(r * math.sin(a), r * math.cos(a)) for a in [math.radians(-90.0 + 180.0 * i / 8) for i in range(1, 8)]] + [(r, 0.0)]
    return K.lathe(name, prof, centre, axis, seg_n, coll)


def about_bore(deg, bz):
    """A frame turned about the bore (the line y = 0, z = bz along x): its local z points out from the bore, `deg` round from
    straight up toward the left. For slots round a flash hider, castellations round a nut."""
    a = math.radians(deg)
    return Matrix(((1.0, 0.0, 0.0, 0.0), (0.0, math.cos(a), math.sin(a), 0.0), (0.0, -math.sin(a), math.cos(a), bz), (0.0, 0.0, 0.0, 1.0)))


def turned(obj, deg, centre):
    """The object turned about the axis along x through `centre` by deg: a cutter on the bore must not have its corners in the
    edges of what it cuts (PLAYBOOK, Modelling 48: a different odd angle for each, a degree or two)."""
    centre = Vector(centre)
    return K.transform(obj, Matrix.Translation(centre) @ Matrix.Rotation(math.radians(deg), 4, 'X') @ Matrix.Translation(-centre))


def bore_seam(bz):
    """A UV seam for a part on the bore built with start=DOWN: one cut along its underside, in the centre plane."""
    centre = K.in_plane((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    return lambda e, mid, d: centre(e) and mid.z < bz and abs(d.x) > 0.5
