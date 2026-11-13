"""weaponforge: the arithmetic of a faceted section, in plain Python (no bpy, no mathutils), so that a weapon's params.py can
build its own section with it and stay importable anywhere.

A moulded or machined body reads as designed when its section is flat FACETS that meet in creases with a small real radius,
and the section changes along the gun in short ramps (PLAYBOOK, "Modelling", items 65 and 66). The weapon describes the left
half of its section at a station x as a list of sharp corners [(y, z, radius)] from the underside up to the top, plus the top
centre point; these functions turn that into the ring a loft skins (`forms.section_loft`), and answer "how far from the middle
is the surface at this height" for anything seated on it (pockets, bosses, screws). AssaultG3's `facets` in its params.py is
the worked example.

Every function here was moved out of AssaultG3 unchanged in its arithmetic: the same expressions in the same order, so that
weapon builds to the same vertices from them.
"""
import math


def lin(points):
    """A function through [(x, y)] (x rising) with straight lines between the points and constant beyond the ends: a width or a
    height along the gun that changes in ramps with crisp ends (a ring at each point, `knots`)."""
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = max(k for k in range(len(xs) - 1) if xs[k] <= x)
        return ys[i] + (ys[i + 1] - ys[i]) * (x - xs[i]) / (xs[i + 1] - xs[i])
    return f


def knots(*tables):
    """The x of every point of these (x, value) tables, sorted, once each: where a section loft needs a ring."""
    return sorted({p[0] for t in tables for p in t})


def corner(a, p, b, r, k):
    """k + 1 points round the corner p between a and b: an arc of radius r (clamped to the neighbours), or, for a corner with
    nothing to round (a straight run, or r = 0), the same number of points along the lines, so every ring has the same count."""
    if r <= 0.0:
        return [p]
    u = (a[0] - p[0], a[1] - p[1])
    v = (b[0] - p[0], b[1] - p[1])
    lu, lv = math.hypot(*u), math.hypot(*v)
    u, v = (u[0] / lu, u[1] / lu), (v[0] / lv, v[1] / lv)
    theta = math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])))
    if theta > math.pi - 0.01:                                # no corner: spread the points along the line
        d = min(0.12, 0.40 * lu, 0.40 * lv)
        return [(p[0] + u[0] * d + (v[0] - u[0]) * d * i / k, p[1] + u[1] * d + (v[1] - u[1]) * d * i / k) for i in range(k + 1)]
    d = r / math.tan(theta / 2.0)
    d_max = 0.45 * min(lu, lv)
    if d > d_max:
        d = d_max
        r = d * math.tan(theta / 2.0)
    t1 = (p[0] + u[0] * d, p[1] + u[1] * d)
    t2 = (p[0] + v[0] * d, p[1] + v[1] * d)
    bis = (u[0] + v[0], u[1] + v[1])
    lb = math.hypot(*bis)
    cen = (p[0] + bis[0] / lb * r / math.sin(theta / 2.0), p[1] + bis[1] / lb * r / math.sin(theta / 2.0))
    a1 = math.atan2(t1[1] - cen[1], t1[0] - cen[0])
    da = math.atan2(t2[1] - cen[1], t2[0] - cen[0]) - a1
    while da > math.pi:
        da -= 2.0 * math.pi
    while da < -math.pi:
        da += 2.0 * math.pi
    return [(cen[0] + r * math.cos(a1 + da * i / k), cen[1] + r * math.sin(a1 + da * i / k)) for i in range(k + 1)]


def facet_ring(corners, lo, top, k=2):
    """The closed section [(y, z)] of a faceted body: from the bottom centre (0, lo) round by +y (the left) over `top` (the top
    centre point, (0, z)) to the right and back. corners: the left half's sharp corners [(y, z, radius)] from the underside up;
    each is rounded with k chords (radius 0: a sharp corner, one point). Every corner gives k + 1 points whatever its radius, so
    rings made from the same list at different stations have the same count and line up for K.loft. Give the creases about
    three chords in the game mesh (k = 3) and four or more in the bake source."""
    pts = [(0.0, lo)] + [(q[0], q[1]) for q in corners] + [top]
    left = [(0.0, lo)]
    for i, (y, z, r) in enumerate(corners):
        left += corner(pts[i], (y, z), pts[i + 2], r, k)
    return left + [top] + [(-y, z) for y, z in reversed(left[1:])]


def facet_y(corners, lo, top, z):
    """How far from the middle the faceted surface is at height z (the sharp facets, not the rounded creases), or None above
    `top` or below `lo`. Keep what is seated on the surface a crease's radius away from the creases."""
    pts = [(0.0, lo)] + [(q[0], q[1]) for q in corners] + [top]
    for (y0, z0), (y1, z1) in zip(pts, pts[1:]):
        if z1 > z0 + 1.0e-9 and z0 - 1.0e-9 <= z <= z1 + 1.0e-9:
            return y0 + (y1 - y0) * (z - z0) / (z1 - z0)
    return None


def rrect(hw, lo, hi, r, k):
    """A rounded rectangle section (y, z) as 4k + 6 points from the bottom centre round by +y: the same count at every size, so a
    loft can run from a thin blade to a thick root (AssaultG3's guard). r is the radius of its four edges, k the chords in each."""
    r = min(r, 0.9 * hw, 0.45 * (hi - lo))
    pts = [(0.0, lo), (hw, lo), (hw, hi), (0.0, hi)]
    left = [(0.0, lo)] + corner(pts[0], pts[1], pts[2], r, k) + corner(pts[1], pts[2], pts[3], r, k)
    return left + [(0.0, hi)] + [(-y, z) for y, z in reversed(left[1:])]


def boss_top(surface_y, x, z, r, h):
    """How far from the middle the flat top of a round boss of radius r at (x, z) stands: `h` above the highest the surface gets
    under it (its centre and eight points round its rim). surface_y(x, z): the body's surface (None off it counts as 0)."""
    pts = [(x, z)] + [(x + r * math.cos(a * math.pi / 4), z + r * math.sin(a * math.pi / 4)) for a in range(8)]
    return max(surface_y(px, pz) or 0.0 for px, pz in pts) + h


# ------------------------------------------------------------------------------------------------- small 2D outlines
def rect(x0, x1, z0, z1, r=0.0):
    """A rectangle for K.round_poly: [(a, b, radius)] counter-clockwise from (x0, z0)."""
    return [(x0, z0, r), (x1, z0, r), (x1, z1, r), (x0, z1, r)]


def densify(pts, step):
    """A closed outline [(a, b)] with no edge longer than `step` (a cutter that follows a curved surface needs points along its
    long straight runs, or it cuts the chord)."""
    out = []
    for p, q in zip(pts, pts[1:] + pts[:1]):
        n = max(1, int(math.ceil(math.hypot(q[0] - p[0], q[1] - p[1]) / step)))
        out += [(p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n) for i in range(n)]
    return out


def hex_pts(r, turn=0.0):
    """A hexagon of corner radius r (a socket screw's key)."""
    return [(r * math.cos(math.radians(turn + 60.0 * k)), r * math.sin(math.radians(turn + 60.0 * k))) for k in range(6)]


def disc_pts(r, n=12):
    """A circle as n points."""
    return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]
