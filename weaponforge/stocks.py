"""weaponforge: what the long guns' wooden stocks share. A stock is one skinned solid (K.loft over K.section ovals, built by the
weapon) that is then split three ways: the wood, a steel grip cap under the pistol grip and a rubber recoil pad on the butt.
On the bake source the pad gets a line and ribs and the wood gets checkered panels.

Every function takes the weapon's params module first and reads these names from it (all (x, z) in the weapon frame, cm):

    BUTT_HEEL, BUTT_TOE        the ends of the recoil pad's rear face
    CAP_REAR, CAP_FRONT        the ends of the grip cap's underside
    PAD_T, CAP_T, SEAT         the pad's and the cap's thickness; the air between parts that sit against one another
    PAD_BORDER, PAD_RIB_PITCH  the line round the pad's face and the ribs across it
    CHECK_PITCH                checkering: the spacing of its lines
    stock_side()               the side outline [(x, z, corner radius)], for K.round_poly

No shipped weapon uses it yet (AssaultG3's butt is part of its polymer shell); it is kept as technique for a wooden-stocked long
gun. Giving several weapons the same numbers for the butt and the grip makes them shoulder alike.
"""
from mathutils import Matrix, Vector
from mathutils.geometry import convex_hull_2d

from . import fittings as F
from . import kit as K


def side_mid(P):
    """f(x): the height half way up the stock's side outline at x, or None beyond its ends."""
    side = K.round_poly(P.stock_side(), 6)

    def mid(x):
        s = K.span(side, x)
        return None if s is None else (s[0] + s[1]) / 2
    return mid


def butt_frame(P):
    """(heel, unit vector down the pad's rear face, unit vector out of it toward the muzzle), all in (x, z)."""
    heel, toe = Vector(P.BUTT_HEEL), Vector(P.BUTT_TOE)
    down = (toe - heel).normalized()
    return heel, down, Vector((-down.y, down.x))


def pad_frame(P):
    """The drawing plane on the recoil pad's rear face: a across it (toward the weapon's left), b down it from the heel."""
    heel, down, fwd = butt_frame(P)
    return Matrix(((0.0, down.x, -fwd.x, heel.x), (1.0, 0.0, 0.0, 0.0), (0.0, down.y, -fwd.y, heel.y), (0.0, 0.0, 0.0, 1.0)))


def pad_cuts(P, pad, coll):
    """A line round the pad's face and ribs across it inside the line: the cutters for K.cut_grooves (they do not touch each
    other). The face's outline is read off the pad."""
    frame = pad_frame(P)
    inv = frame.inverted()
    flat = [(inv @ v.co).to_2d() for v in pad.data.vertices]
    hull = [flat[i] for i in convex_hull_2d(flat)]
    lo, hi = min(p.y for p in hull), max(p.y for p in hull)
    half_a, half_b, mid = max(abs(p.x) for p in hull), (hi - lo) / 2, (lo + hi) / 2

    def inset(d):
        return [(p.x * (1.0 - d / half_a), mid + (p.y - mid) * (1.0 - d / half_b)) for p in hull]
    border = inset(P.PAD_BORDER)
    return [
        K.grooves_on(pad, [border + border[:1]], frame, coll, half_w=0.06, depth=0.06, facing=0.9),
        K.grooves_on(pad, K.hatch(inset(P.PAD_BORDER + 0.40), 0.0, P.PAD_RIB_PITCH), frame, coll, half_w=0.11, depth=0.09, facing=0.9),
    ]


def butt_slab(P, a, b):
    """The slice between a and b cm ahead of the pad's rear face, as an (x, z) outline."""
    heel, down, fwd = butt_frame(P)
    top, bot = heel - down * 3.0, Vector(P.BUTT_TOE) + down * 3.0
    return [tuple(top + fwd * a), tuple(bot + fwd * a), tuple(bot + fwd * b), tuple(top + fwd * b)]


def cap_slab(P, a, b, back=0.0):
    """The slice between a and b cm above the grip cap's underside, as an (x, z) outline. It stops at the cap's rear edge (plus
    `back`): carried on, its plane would rise into the butt behind the grip."""
    rear, front = Vector(P.CAP_REAR), Vector(P.CAP_FRONT)
    along = (front - rear).normalized()
    up = Vector((-along.y, along.x))
    r, f = rear - along * back, front + along * 1.5
    return [tuple(r + up * a), tuple(f + up * a), tuple(f + up * b), tuple(r + up * b)]


def recoil_pad(P, full, coll, hp, seg):
    """Cut the recoil pad out of a copy of the skinned solid `full`. Returns (pad, the cutter that makes its place in the wood).
    seg(hp, lo, hi): the builder's segment dial."""
    heel, _down, fwd = butt_frame(P)
    pad = K.copy(full, 'Pad', coll)
    K.boolean(pad, K.prism('cut', butt_slab(P, 0.0, P.PAD_T), 'XZ', -6.0, 6.0, coll), 'INTERSECT')
    K.cleanup(pad, dissolve_deg=0.0 if hp else 0.5)
    K.bevel(pad, F.rim((heel.x, 0.0, heel.y), (-fwd.x, 0.0, -fwd.y)), 0.30, seg(hp, 1, 6))
    if hp:
        K.cut_grooves(pad, pad_cuts(P, pad, coll), coll)
    return pad, K.prism('cut', butt_slab(P, -8.0, P.PAD_T + P.SEAT), 'XZ', -6.0, 6.0, coll)


def grip_cap(P, full, coll, hp):
    """Cut the grip cap out of a copy of the skinned solid `full`. Returns (cap, the cutter that makes its place in the wood).
    A stock without a butt (a sawn-off) still has this."""
    cap = K.copy(full, 'GripCap', coll)
    K.boolean(cap, K.prism('cut', cap_slab(P, -3.0, P.CAP_T), 'XZ', -6.0, 6.0, coll), 'INTERSECT')
    K.cleanup(cap, dissolve_deg=0.0 if hp else 0.5)
    if hp:
        rear, front = Vector(P.CAP_REAR), Vector(P.CAP_FRONT)
        mid, along = (rear + front) / 2, (front - rear).normalized()
        K.boolean(cap, F.screw_cuts((mid.x, 0.0, mid.y), (along.y, 0.0, -along.x), 0.30, coll, slot_deg=20.0))
    return cap, K.prism('cut', cap_slab(P, -3.0, P.CAP_T + P.SEAT, P.SEAT), 'XZ', -6.0, 6.0, coll)


def pad_and_cap(P, full, coll, hp, seg):
    """Cut the recoil pad and the grip cap out of copies of the skinned solid `full`. Returns (pad, cap, cutters): the two
    finished parts, and the cutters that make their places in the wood, for the stock's own boolean (with its other cuts).
    seg(hp, lo, hi): the builder's segment dial."""
    pad, pad_place = recoil_pad(P, full, coll, hp, seg)
    cap, cap_place = grip_cap(P, full, coll, hp)
    return pad, cap, [pad_place, cap_place]


def checker(P, wood, panels, coll):
    """Checkering on the bake source: two sets of V grooves that follow the wood and a border line round each panel, on both
    sides of the gun. panels: [(outline in (x, z), line angle in degrees off the bore)]. The game mesh has none of it: it is
    in the normal map."""
    sets = {'a': [], 'b': [], 'border': []}
    for side in (1.0, -1.0):
        frame = F.side_frame(side)
        for outline, deg in panels:
            sets['a'].append(K.grooves_on(wood, K.hatch(outline, deg, P.CHECK_PITCH), frame, coll))
            sets['b'].append(K.grooves_on(wood, K.hatch(outline, -deg, P.CHECK_PITCH), frame, coll))
            sets['border'].append(K.grooves_on(wood, [outline + outline[:1]], frame, coll, half_w=0.055, depth=0.05))
    for key in ('a', 'b', 'border'):                      # one cut per line direction: the two directions cross
        K.cut_grooves(wood, sets[key], coll)
    K.cleanup(wood, dissolve_deg=0.0)
    K.mend(wood)                                          # the cleanup can leave a pinhole where it dropped a sliver


def finish(wood, cap, pad, bone='Grip_Bone'):
    """Shade and tag the three parts: walnut, a dark steel cap, a rubber pad (surface kind "polymer")."""
    return [K.tag(K.shade(wood, 40.0), bone, mat='wood'), K.tag(K.shade(cap), bone, mat='dark'), K.tag(K.shade(pad), bone, mat='polymer')]
