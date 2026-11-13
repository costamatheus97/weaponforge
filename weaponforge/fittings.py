"""weaponforge: small things more than one weapon carries (a slotted screw head, a sling stud, a takedown pin, a riveted data
plate, a sling loop and cup, the marks a moulding carries) and two helpers their builders share. Built with kit.py and
forms.py; nothing here knows any one weapon's dimensions.
"""
import math

from mathutils import Matrix, Vector

from . import forms as FM
from . import kit as K
from . import sections as S


def rim(point, normal, tol=2.0e-3):
    """For K.bevel: the edges round the flat face through `point` that faces `normal`."""
    point, normal = Vector(point), Vector(normal).normalized()

    def pred(e, mid, d):
        if abs((mid - point).dot(normal)) > tol or abs(d.dot(normal)) > 1.0e-3:
            return False
        return any(abs(f.normal.dot(normal)) < 0.9 for f in e.link_faces)
    return pred


def side_frame(side):
    """The drawing plane for detail on one side of the gun: its (a, b) are the weapon's (x, z). side +1: the left, -1: the right."""
    return Matrix(((1.0, 0.0, 0.0, 0.0), (0.0, 0.0, side, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)))


def screw_cuts(centre, out, r, coll, slot_deg=0.0, depth=0.04):
    """Cutters that draw a slotted screw head flush in a surface (high detail only): a ring groove round it and the slot across
    it. centre: on the surface; out: the surface's normal there. The slot ends inside the ring groove, never a hair short of it:
    a wall a few hundredths thick between two cutters is what makes the exact boolean give up."""
    centre, out = Vector(centre), Vector(out).normalized()
    ring = K.tube('cut', centre - out * depth, centre + out * 0.3, r, r - 0.028, 32, coll)
    frame = (Matrix.Translation(centre) @ out.to_track_quat('Z', 'Y').to_matrix().to_4x4()
             @ Matrix.Rotation(math.radians(slot_deg), 4, 'Z'))
    w, half = 0.024, r - 0.014
    slot = K.prism_m('cut', [(-half, -w), (half, -w), (half, w), (-half, w)], frame, -depth * 1.3, 0.3, coll)
    return [ring, slot]


def pin_cuts(centre, out, r, coll, depth=0.035):
    """A cutter that draws the end of a pin flush in a surface (high detail only): a ring groove round it."""
    centre, out = Vector(centre), Vector(out).normalized()
    return [K.tube('cut', centre - out * depth, centre + out * 0.3, r, r - 0.028, 32, coll)]


def stud(name, base, out, coll, seg, seat=0.02):
    """A sling stud: a flange on the surface at `base`, a post along `out`, and an eye with a hole across the gun.
    seg(lo, hi): the builder's own segment dial (game-mesh count, bake-source count)."""
    base, out = Vector(base), Vector(out).normalized()
    centre, r = 0.82, 0.34
    phi0 = math.asin(0.20 / r)
    steps = max(3, int(round((math.pi - phi0) / (math.pi / 2) * seg(0.8, 10))))          # a centimetre of steel: few triangles
    prof = [(0.0, 0.0), (0.0, 0.36), (0.12, 0.36), (0.14, 0.20)]
    prof += [(centre - r * math.cos(phi0 + (math.pi - phi0) * i / steps), r * math.sin(phi0 + (math.pi - phi0) * i / steps)) for i in range(steps + 1)]
    obj = K.lathe(name, prof, base + out * seat, out, seg(2.6, 28), coll)
    eye = base + out * (seat + centre)
    K.boolean(obj, K.cylinder('cut', eye - Vector((0.0, 1.0, 0.0)), eye + Vector((0.0, 1.0, 0.0)), 0.14, seg(2, 24), coll))
    return obj


# ------------------------------------------------------------------------------------------------------------- hardware
# Moved from AssaultG3 with their arithmetic unchanged. The marks below are cutters for the bake source (the `hp`
# branch), cut into the part after its coarse cuts and before its lettering (PLAYBOOK, "Modelling", item 49). Each is placed
# by a ray from outside the part (forms.hit), so it lies flat on whatever slope the surface has there, and each returns []
# when the ray misses. `side_ray(x, z, side)` is the ray from the side; pass any other (origin, direction) for a top or an
# underside. Steel hardware that is a part of its own (a pin's head, a rivet, a plate, a sling loop) is a closed solid to
# K.join into the weapon's hardware part.

def side_ray(x, z, side, far=6.0):
    """(origin, direction): a ray at (x, z) from `far` out on one side of the gun (side +1: the left) toward the middle."""
    return (x, side * far, z), (0.0, -side, 0.0)


def fastener(body, origin, direction, coll, groove=(0.34, 0.27), hex_r=0.17, up=(0.0, 0.0, 1.0)):
    """A socket-head screw let flush into a surface where the ray meets it: a ring groove round it (outer and inner radius) and a
    hex socket. Cutters, or [] on a miss. up: which way the hex's flats are squared to (along the surface). A cover's side
    screw took the defaults; a smaller one on a top facet groove=(0.27, 0.20), hex_r=0.13, up=(1, 0, 0)."""
    got = FM.hit(body, origin, direction)
    if got is None:
        return []
    loc, nrm = got
    f = FM.surface_frame(loc, nrm, up=up)
    ring = K.tube('cut', loc - nrm * 0.05, loc + nrm * 0.3, groove[0], groove[1], 24, coll)
    return [ring, K.prism_m('cut', S.hex_pts(hex_r), f, -0.14, 0.3, coll)]


def takedown_pin(x, z, face, coll, seg, side=1.0):
    """A takedown pin across the gun at (x, z), as three closed solids to join: a domed head (radius 0.40) with a wire clip and
    its tab on one side, the pin's plain end on the other. face: how far from the middle each end stands (the face of the boss
    round it plus the seat). side +1: the head on the left. seg(lo, hi): the builder's segment dial. On the bake source add
    `takedown_pin_cuts` (the end's ring groove) to the part's cuts."""
    o = face
    head = K.lathe('head', [(0.0, 0.0), (0.0, 0.40), (0.07, 0.40), (0.15, 0.37), (0.22, 0.29), (0.27, 0.15), (0.30, 0.0)], (x, side * o, z),
                   (0.0, side, 0.0), seg(7, 28), coll)
    clip = K.tube('clip', (x, side * (o + 0.05), z), (x, side * (o + 0.12), z), 0.50, 0.38, seg(8, 24), coll)
    a, b = sorted((side * (o + 0.05), side * (o + 0.12)))
    tab = K.box('tab', (x - 0.05, a, z + 0.38), (x + 0.05, b, z + 0.90), coll)
    K.boolean(clip, tab, 'UNION')
    end = K.lathe('pin', [(0.0, 0.0), (0.0, 0.29), (0.10, 0.29), (0.18, 0.22), (0.20, 0.0)], (x, -side * o, z), (0.0, -side, 0.0), seg(8, 24), coll)
    return [head, clip, end]


def takedown_pin_cuts(x, z, face, coll, side=1.0):
    """The ring groove round the pin's plain end (bake source)."""
    return pin_cuts((x, -side * (face + 0.20), z), (0.0, -side, 0.0), 0.12, coll)


def pin_head(base, axis, coll, seg_n, name='pin_head'):
    """A small domed pin head (radius 0.20, 0.14 high) standing on a surface at `base`, along `axis` (out of it): a pivot pin's
    end. Sit it 0.01 into the surface, never on it (base = surface + seat - 0.01)."""
    return K.lathe(name, [(0.0, 0.0), (0.0, 0.20), (0.04, 0.20), (0.09, 0.17), (0.12, 0.10), (0.14, 0.0)], base, axis, seg_n, coll)


def rivet(base, axis, coll, seg_n, name='rivet', r=0.11):
    """A domed rivet head (radius `r`, 0.11 by default, 0.09 high) at `base`, along `axis`. The head keeps its shape as r changes:
    its height and its dome go with the radius (r 0.18 is 0.147 high), so a bigger rivet is a bigger copy, not a taller pillar.
    At 0.11 cm (about a pixel and a half on a 1024 sheet) a rivet is hardly seen from the hip; 0.16 to 0.20 reads. A part that
    is built by data_plate has its own rivets at the default."""
    if r == 0.11:
        return K.lathe(name, [(0.0, 0.0), (0.0, 0.11), (0.035, 0.11), (0.06, 0.085), (0.08, 0.05), (0.09, 0.0)], base, axis, seg_n, coll)
    k = r / 0.11
    return K.lathe(name, [(0.0, 0.0), (0.0, r), (0.035 * k, r), (0.06 * k, 0.085 * k), (0.08 * k, 0.05 * k), (0.09 * k, 0.0)], base, axis,
                   seg_n, coll)


def plate_recess(x0, x1, z0, z1, floor, coll, side=1.0, out=3.0):
    """The cutter of a data plate's recess in a body's side: from `floor` (its depth from the middle, at the low edge: a side
    that leans gives the rest) out to `out`."""
    a, b = sorted((side * floor, side * out))
    return K.box('cut', (x0, a, z0), (x1, b, z1), coll)


def data_plate(x0, x1, z0, z1, floor, coll, seg, side=1.0, t=0.09, inset=0.04, rivet_in=0.20, rivet_r=0.11):
    """A steel data plate for the recess `plate_recess(x0, x1, z0, z1, floor)` makes: `inset` smaller all round, 0.01 off its
    floor, `t` thick, its outer edge broken, and two domed rivets near its ends. Returns (plate, rivets, face): the plate,
    the rivet solids and the centre of its outer face (for `plate_text`).

    JOIN THE RIVETS AFTER THE CUTS on the bake source: they sit 0.01 into the plate, and a cut into the joined part (the serial)
    drops them, so that the bake's rays find nothing over the game mesh's rivets and they take the base steel with a flat
    normal. On the game mesh join them with the plate."""
    px0, px1, pz0, pz1 = x0 + inset, x1 - inset, z0 + inset, z1 - inset
    lo = floor + 0.01
    a, b = sorted((side * lo, side * (lo + t)))
    plate = K.box('plate', (px0, a, pz0), (px1, b, pz1), coll)
    K.bevel(plate, lambda e, m, d: abs(m.y - side * (lo + t)) < 1.0e-4, 0.03, seg(1, 2))
    pzc = (pz0 + pz1) / 2
    rivets = [rivet((rx, side * (lo + t - 0.01), pzc), (0.0, side, 0.0), coll, seg(8, 14), r=rivet_r) for rx in (px0 + rivet_in, px1 - rivet_in)]
    return plate, rivets, ((px0 + px1) / 2, side * (lo + t), pzc)


def plate_text(face, text, coll, side=1.0, size=0.205, depth=0.02, wide=1.0):
    """The serial engraved on a data plate's face (a cutter, bake source): it reads toward the butt on the left, toward the
    muzzle on the right. wide: the letters this many times as wide along the line (K.text_solid)."""
    return K.text_solid('cut', text, size, face, (-side, 0.0, 0.0), (0.0, 0.0, 1.0), depth, coll, wide=wide)


def sling_loop(x0, x1, z0, z1, coll, seg, hw=0.16, r=0.55, hole_r=0.27, hole_z=0.62):
    """A sling loop: a tab hung under a part from z1 down to z0, its lower corners rounded (r), a hole across the gun hole_z above
    its bottom. A closed solid to join; seat its top inside the part above it."""
    tab = K.prism('loop', K.round_poly([(x0, z0, r), (x1, z0, r), (x1, z1), (x0, z1)], seg(3, 8)), 'XZ', -hw, hw, coll)
    K.boolean(tab, K.cylinder('cut', ((x0 + x1) / 2, -1.0, z0 + hole_z), ((x0 + x1) / 2, 1.0, z0 + hole_z), hole_r, seg(8, 20), coll))
    return tab


def qd_cup(x, z, floor, side, coll, seg_n, r=0.55, out=3.0):
    """The cutter of a sling's quick-detach cup in a body's side: a round hole of radius r from `floor` (its depth from the
    middle) outward. In the game mesh too: it is seen. On the bake source add `qd_cup_marks`."""
    return K.cylinder('cut', (x, side * floor, z), (x, side * out, z), r, seg_n, coll)


def qd_cup_marks(body, x, z, floor, side, coll, r=0.55, far=6.0):
    """The cup's rim (a ring groove round it, found on the surface above it) and the pin hole in its floor. [] on a miss."""
    got = FM.hit(body, (x, side * far, z + r + 0.65), (0.0, -side, 0.0))
    if not got:
        return []
    f = FM.surface_frame(Vector((x, got[0].y, z)), got[1])
    cuts = [FM.ring_cut(f, r + 0.30, 0.07, 0.04, coll, n=32)]
    y = side * floor
    cuts += [K.cylinder('cut', (x, y - side * 0.25, z), (x, y + side * 0.3, z), 0.16, 16, coll)]
    return cuts


def witness(body, origin, direction, coll, r=0.20):
    """The shallow circle of an ejector pin's mark on a moulding where the ray meets it (an underside: origin below the part,
    direction up). [] on a miss."""
    got = FM.hit(body, origin, direction)
    if got is None:
        return []
    loc, nrm = got
    return [K.cylinder('cut', loc - nrm * 0.035, loc + nrm * 0.3, r, 16, coll)]


def parting_line(body, x0, x1, top, coll, step=0.8, far=30.0, hw=0.022):
    """A moulding's parting line along the centre plane from x0 to x1, a hairline a few hundredths deep: a run of short bars,
    each set on the surface a ray down (top=True) or up (top=False) finds. far: where the rays start, outside the part."""
    cuts = []
    x = x0
    while x < x1:
        got = FM.hit(body, (x + step / 2, 0.0, far if top else -far), (0.0, 0.0, -1.0 if top else 1.0))
        if got is not None:
            loc, nrm = got
            cuts.append(K.box('cut', (x - 0.03, -hw, loc.z - 0.03), (x + step + 0.03, hw, loc.z + 0.3), coll) if top else
                        K.box('cut', (x - 0.03, -hw, loc.z - 0.3), (x + step + 0.03, hw, loc.z + 0.03), coll))
        x += step
    return cuts


def date_clock(body, origin, direction, coll):
    """A moulded date clock (generic, no maker's mark): a ring 0.8 across, an arrow in it and seven tick marks. [] on a miss."""
    got = FM.hit(body, origin, direction)
    if got is None:
        return []
    loc, nrm = got
    f = FM.surface_frame(loc, nrm)
    cuts = [FM.ring_cut(f, 0.40, 0.05, 0.028, coll)]
    cuts.append(FM.engrave(FM.bar_pts(0.0, -0.24, 0.0, 0.18, 0.05), f, 0.028, coll))
    cuts.append(FM.engrave([(0.0, 0.30), (-0.09, 0.14), (0.09, 0.14)], f, 0.028, coll))
    for k in range(8):
        a = math.radians(45.0 * k + 90.0)
        if k != 0:
            cuts.append(FM.engrave(FM.bar_pts(math.cos(a) * 0.30, math.sin(a) * 0.30, math.cos(a) * 0.42, math.sin(a) * 0.42, 0.045), f, 0.028, coll))
    return cuts


def lock_mark(body, origin, direction, coll, ink=0):
    """A small padlock, engraved and filled with paint `ink`: a body and a shackle (a takedown pin's mark). [] on a miss."""
    got = FM.hit(body, origin, direction)
    if got is None:
        return []
    loc, nrm = got
    f = FM.surface_frame(loc, nrm)
    cuts = [FM.engrave([(-0.21, -0.20), (0.21, -0.20), (0.21, 0.06), (-0.21, 0.06)], f, 0.03, coll, ink)]
    for a, b, c, d in ((-0.12, 0.06, -0.12, 0.26), (0.12, 0.06, 0.12, 0.26), (-0.12, 0.26, 0.12, 0.26)):
        cuts.append(FM.engrave(FM.bar_pts(a, b, c, d, 0.075), f, 0.03, coll, ink))
    return cuts


def arrow_mark(body, origin, direction, coll, ink=0):
    """A small engraved arrow (the 'turn to unlock' mark by a pin): shaft, head and a hook. [] on a miss."""
    got = FM.hit(body, origin, direction)
    if got is None:
        return []
    loc, nrm = got
    f = FM.surface_frame(loc, nrm)
    shaft = FM.engrave(FM.bar_pts(-0.32, 0.0, 0.14, 0.0, 0.07), f, 0.03, coll, ink)
    head = FM.engrave([(0.34, 0.0), (0.10, 0.16), (0.10, -0.16)], f, 0.03, coll, ink)
    arc = FM.engrave(FM.bar_pts(-0.32, 0.0, -0.32, -0.22, 0.07), f, 0.03, coll, ink)
    return [shaft, head, arc]


def safe_mark(body, origin, direction, coll, ink=0):
    """A selector's "safe" pictogram: a ring with a dot, filled with paint `ink` (white). [] on a miss."""
    got = FM.hit(body, origin, direction)
    if not got:
        return []
    f = FM.surface_frame(*got)
    return [FM.ring_cut(f, 0.30, 0.11, 0.03, coll, ink=ink, n=24), FM.engrave(S.disc_pts(0.09, 12), f, 0.03, coll, ink=ink)]


def fire_mark(body, origin, direction, coll, ink=1):
    """A selector's "fire" pictogram: three bars, filled with paint `ink` (red, the second paint). [] on a miss."""
    got = FM.hit(body, origin, direction)
    if not got:
        return []
    f = FM.surface_frame(*got)
    return [FM.engrave(FM.bar_pts(dx, -0.26, dx, 0.26, 0.12), f, 0.03, coll, ink=ink) for dx in (-0.25, 0.0, 0.25)]
