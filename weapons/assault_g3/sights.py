"""AssaultG3: iron sights that clamp on a rail: a rear aperture sight and a front post sight, each one closed part, each built
to the same detail on the game mesh's silhouette and the bake source's (the game mesh and the detail model agree in outline;
the fine cuts are the bake source's only). This is AssaultG3's own design, kept in its folder; the weapon's dimensions come in as
arguments (the defaults are AssaultG3's proportions).

Both take the weapon's segment dial `seg(lo, hi)` (bound to hp: `lambda lo, hi: seg(hp, lo, hi)` with the weapon's own `seg`),
the `hp` flag, and a `Mount`: where the rail is and how wide the clamp's base is. They return the part untagged and unshaded;
the builder tags it (`K.tag(K.shade(obj, 30.0, flats=hp), bone)`). Every dimension not given is derived from the mount, the
part's ends and the line of sight; the defaults are AssaultG3's proportions.

Rules they keep (PLAYBOOK, "Modelling"):
  * round parts the eye is close to get their sides on the GAME mesh: an aperture 10 x the weapon's LP_Q (34 at 3.4), the
    windage knob 11 x LP_Q (37), round at 8 to 15 cm, where a player's eye is in the aiming view
  * the anti-glare serrations on the aperture arm stop at a flat LAND round both apertures (a straight strip, not a stair
    round each circle), so each countersunk rim is a clean circle on smooth metal; the countersinks are cut once more last,
    because the serrations nick their rims
  * small parts stand 0.02 off their seats or overlap them clearly; never on a face (item 3)
"""
import collections
import math

from mathutils import Matrix, Vector

from weaponforge import fittings as F
from weaponforge import forms as FM
from weaponforge import kit as K
from weaponforge import sections as S

Mount = collections.namedtuple('Mount', 'rail_z rail_hw base_hw jaw_z seat')
Mount.__doc__ = """Where a sight sits: rail_z the rail's top, rail_hw half the rail's width at its widest, base_hw half the
clamp's width, jaw_z the jaws' underside (under the rail's widest point), seat the air between parts (0.02)."""

_T = Matrix(((0.0, 0.0, 1.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)))   # local (x, y, z) -> (y, z, x): a prism along local z lies along y


def clamp(name, x0, x1, coll, seg, mount):
    """What a sight stands on, from x0 to x1: a base on the rail's top (0.55 high, its top edges bevelled) and the two jaws that
    grip the rail's sides. Returns (base, [jaws]): union the jaws and the sight's own parts into the base in one go."""
    bw = mount.base_hw
    base = K.box(name, (x0, -bw, mount.rail_z + mount.seat), (x1, bw, mount.rail_z + 0.55), coll)
    K.bevel(base, lambda e, m, d: abs(m.z - mount.rail_z - 0.55) < 1.0e-4 and abs(d.z) < 0.01, 0.08, seg(1, 3))
    jaws = []
    for side in (1.0, -1.0):
        a, b = sorted((side * (mount.rail_hw + mount.seat), side * bw))
        jaws.append(K.box('jaw', (x0, a, mount.jaw_z), (x1, b, mount.rail_z + 0.2), coll))
    return base, jaws


def front_post(name, x0, x1, coll, seg, hp, mount, sight_z, wing=(0.50, 0.82), pedestal=None, post=None):
    """A front sight clamped on the rail from x0 to x1: a post on a pedestal between two hooded wings (a curled, forward-leaning
    top, a 45 degree outer chamfer and a lightening hole each), an adjuster with detent notches on the left and a cross-bolt
    head on the right, a clamp bar each side; on the bake source anti-glare serrations on the post's and the pedestal's rear
    faces, the clamp's split lines and the screws' slots.

    sight_z: the top of the post (the line of sight). wing: the wings' inner and outer y. pedestal: ((x0, x1), half width),
    default 1 cm long under the post's middle, 0.34 wide each side; post: (x, half width), default the pedestal's middle and
    0.09 (a post 0.18 wide reads as a post at arm's length)."""
    if pedestal is None:
        pedestal = ((x0 + 0.85, x0 + 1.85), 0.34)
    if post is None:
        post = ((pedestal[0][0] + pedestal[0][1]) / 2, 0.09)
    base, parts = clamp(name, x0, x1, coll, seg, mount)
    w0, w1 = wing
    bw = mount.base_hw
    rail_z = mount.rail_z
    foot, top = rail_z + 0.45, sight_z + 0.30
    sg = seg
    shape = K.round_poly([(x0 + 0.15, foot), (x1 - 0.15, foot), (x1 - 0.15, top - 1.00, 0.10), (x1 - 0.45, top - 0.20, 0.45), (x1 - 1.05, top, 0.40),
                          (x0 + 1.15, top, 0.35), (x0 + 0.40, top - 0.70, 0.45)], sg(1, 8))
    for side in (1.0, -1.0):
        a, b = sorted((side * w0, side * w1))
        w = K.prism('wing', shape, 'XZ', a, b, coll)
        K.bevel(w, lambda e, m, d, o=side * w1: abs(m.y - o) < 1.0e-4 and m.z > foot + 0.02, 0.06, 1)
        parts.append(w)
    (px0, px1), pw = pedestal
    parts.append(K.box('ped', (px0, -pw, foot), (px1, pw, sight_z - 0.80), coll))
    px, hw = post
    parts.append(K.box('post', (px - hw, -hw, sight_z - 0.95), (px + hw, hw, sight_z), coll))
    z_lo, z_hi = mount.jaw_z + 0.04, rail_z + 0.15
    for side in (1.0, -1.0):                                                   # the clamp bar each side of the jaws
        a, b = sorted((side * (bw - 0.04), side * (bw + 0.20)))
        parts.append(K.box('bar', (x0 + 0.35, a, z_lo), (x1 - 0.35, b, z_hi), coll))
    bx, bz = x1 - 0.95, rail_z - 0.20                                          # a cross-bolt, head on the right
    parts.append(K.cylinder('bolt', (bx, -(bw + 0.14), bz), (bx, -(bw + 0.62), bz), 0.36, sg(7, 28), coll))
    parts.append(K.cylinder('nut', (x0 + 1.35, bw - 0.1, rail_z - 0.20), (x0 + 1.35, bw + 0.55, rail_z - 0.20), 0.40, sg(7, 28), coll))
    K.boolean(base, parts, 'UNION')
    # a lightening hole through each wing
    K.boolean(base, K.cylinder('cut', (x0 + 0.85, -(w1 + 0.1), foot + 0.60), (x0 + 0.85, w1 + 0.1, foot + 0.60), 0.22, sg(7, 24), coll))
    K.cleanup(base)
    if hp:
        nx, nz, ny = x0 + 1.35, rail_z - 0.20, bw + 0.55
        cuts = [K.prism_m('cut', S.rect(ny - 0.50, ny + 0.1, -0.04, 0.04),
                          Matrix.Translation((nx, 0.0, nz)) @ Matrix.Rotation(math.radians(30.0 * i), 4, 'Y') @ _T,
                          0.40 - 0.05, 0.40 + 0.3, coll) for i in range(12)]                    # the adjuster's detents: twelve notches round its rim
        cuts += F.screw_cuts((nx, ny, nz), (0.0, 1.0, 0.0), 0.24, coll, slot_deg=0.0)           # and a slotted end
        cuts += F.screw_cuts((bx, -(bw + 0.62), bz), (0.0, -1.0, 0.0), 0.25, coll, slot_deg=60.0)
        # the post's rear face: serrations (pitch 0.08, 0.025 deep); the pedestal's: pitch 0.12, 0.04 deep
        for i in range(9):
            z = sight_z - 0.74 + 0.08 * i
            cuts.append(K.prism('cut', [(px - hw - 0.04, z - 0.07), (px - hw - 0.04, z + 0.07), (px - hw + 0.025, z)], 'XZ', -(hw + 0.02), hw + 0.02, coll))
        for i in range(9):
            z = foot + 0.20 + 0.12 * i
            cuts.append(K.prism('cut', [(px0 - 0.06, z - 0.10), (px0 - 0.06, z + 0.10), (px0 + 0.04, z)], 'XZ', -(pw + 0.02), pw + 0.02, coll))
        for side in (1.0, -1.0):                                                 # a split line along each side of the clamp
            a, b = sorted((side * (bw - 0.06), side * (bw + 0.06)))
            cuts.append(K.prism('cut', [(x0 - 0.1, rail_z + 0.31), (x0 - 0.1, rail_z + 0.39), (x1 + 0.1, rail_z + 0.39), (x1 + 0.1, rail_z + 0.31)], 'XZ', a, b, coll))
        K.boolean(base, cuts)
    return base


def rear_aperture(name, x0, x1, coll, seg, hp, mount, sight_z, ear=(0.80, 1.12), ear_x=None, arm_x=None, pivot=None, wind=None,
                  apertures=None, countersink=(0.08, 0.08), knob_r=0.50, knob_y=None, serrations=None, panel_z=None, scale_z=None):
    """A rear aperture sight clamped on the rail from x0 to x1 (a precision part): a base with a clamp bar and a cross-bolt each
    side, a recoil lug under its rear, two thin wings (a curved, hooked top; a 45 degree outer chamfer; a lightening slot each;
    on the bake source a shallow sunk panel on the outer face, the left one carrying an elevation scale), and between them a
    slim aperture ARM on a pivot pin (a domed head on the left; on the right the pin's end, a C-clip and a detent ball) with
    its apertures, each a through hole with a countersunk rim on the eye side. The arm's top edge is one chamfer with a centre
    notch; on the bake source its rear face has anti-glare serrations that stop at a land round the apertures, and a shallow
    pocket either side of a centre rib below them. The windage screw lies between the wings in front of the arm, a slotted
    head on the left and a knurled knob on the right behind a click plate.

    sight_z: the centre of the main aperture (the line of sight). ear: the wings' inner and outer y. ear_x: the wings' x
    (default 0.70 in from the rear, 0.60 from the front). arm_x: the arm's rear and front face (default 1.685 from the rear,
    0.45 thick). pivot: the pin's (x, z) (default the arm's middle, 1.30 under the sight line). wind: the windage screw's
    (x, z) (default 0.35 behind the wings' front, 0.75 over the rail). apertures: [(z, radius)], the first is the main one
    (default 0.13 on the sight line and a wide 0.30 one 0.68 over the pivot). countersink: (depth, how much wider than the
    hole at the face). knob_r, knob_y: the windage knob's radius and its (outer, inner) y on the right (default 0.88 and 0.30
    outside the wing). serrations: (z of the first, count, pitch) on the arm's rear face (default from 0.30 over the pivot
    to 0.10 under the arm's top, every 0.10). panel_z: the wings' sunk panels, low and high z (default 1.42 under and 0.32
    over the sight line). scale_z: the elevation scale's four ticks (default 0.20 into the panel, every 0.42)."""
    if ear_x is None:
        ear_x = (x0 + 0.70, x1 - 0.60)
    if arm_x is None:
        a0 = x0 + 1.80 - 0.115
        arm_x = (a0, a0 + 0.45)
    if pivot is None:
        pivot = ((arm_x[0] + arm_x[1]) / 2, sight_z - 1.30)
    if wind is None:
        wind = (ear_x[1] - 0.35, mount.rail_z + 0.75)
    if apertures is None:
        apertures = [(sight_z, 0.13), (pivot[1] + 0.68, 0.30)]
    if knob_y is None:
        knob_y = (-(ear[1] + 0.88), -(ear[1] + 0.30))
    if serrations is None:
        z0 = pivot[1] + 0.30
        serrations = (z0, int((sight_z + 0.40 - z0) / 0.10 + 1.0e-6) + 1, 0.10)
    if panel_z is None:
        panel_z = (sight_z - 1.42, sight_z + 0.32)
    if scale_z is None:
        scale_z = [panel_z[0] + 0.20 + 0.42 * i for i in range(4)]
    cs_d, cs_w = countersink
    rail_z = mount.rail_z
    base, parts = clamp(name, x0, x1, coll, seg, mount)
    (ex0, ex1), (e0, e1) = ear_x, ear
    foot, top = rail_z + 0.45, sight_z + 0.55
    (xc, zc), bw = pivot, mount.base_hw
    xa0, xa1 = arm_x
    wx, wz = wind
    sg = seg
    # the wings: a rear peak that curves down to a small hook at the front
    shape = K.round_poly([(ex0, foot), (ex1, foot), (ex1, top - 1.05, 0.10), (ex1 - 0.30, top - 1.32, 0.12), (ex1 - 0.80, top - 0.72, 0.50),
                          (ex0 + 1.40, top, 0.55), (ex0 + 0.50, top, 0.45), (ex0, top - 0.85, 0.40)], sg(1, 8))
    for side in (1.0, -1.0):
        a, b = sorted((side * e0, side * e1))
        wing = K.prism('ear', shape, 'XZ', a, b, coll)
        K.bevel(wing, lambda e, m, d, o=side * e1: abs(m.y - o) < 1.0e-4 and m.z > foot + 0.02, 0.07, 1)        # the 45 degree chamfer round the outer face
        parts.append(wing)
    # the aperture arm: a rounded plate, its bottom round the pivot
    hw = e0 - 0.035
    arm = K.prism('arm', K.round_poly([(-hw, zc - 0.45, 0.45), (hw, zc - 0.45, 0.45), (hw, sight_z + 0.50, 0.25), (-hw, sight_z + 0.50, 0.25)], sg(2, 12)),
                  'YZ', xa0, xa1, coll)
    az_top = sight_z + 0.50                                                    # the arm's top edge is one clean chamfer (0.12) with a single centre index notch, not a tab of blocks
    K.boolean(arm, [K.prism('cut', [(xa0 - 0.02, az_top - 0.12), (xa0 - 0.02, az_top + 0.02), (xa0 + 0.12, az_top + 0.02)], 'XZ', -(hw + 0.05), hw + 0.05, coll),
                    K.prism('cut', [(-0.07, az_top + 0.02), (0.07, az_top + 0.02), (0.0, az_top - 0.13)], 'YZ', xa0 - 0.02, xa0 + 0.30, coll)])
    parts.append(arm)
    z_lo, z_hi = mount.jaw_z + 0.04, rail_z + 0.15
    for side in (1.0, -1.0):                                                   # the clamp bar each side of the jaws
        a, b = sorted((side * (bw - 0.04), side * (bw + 0.22)))
        parts.append(K.box('bar', (x0 + 0.40, a, z_lo), (x1 - 0.40, b, z_hi), coll))
    parts.append(K.box('lug', (x0 - 0.12, -0.55, rail_z - 0.52), (x0 + 0.70, 0.55, rail_z + 0.10), coll))        # the recoil lug, behind the base's rear face
    bx, bz = x0 + 1.0, rail_z - 0.20                                           # the cross-bolt
    parts.append(K.cylinder('nut', (bx, bw + 0.15, bz), (bx, bw + 0.72, bz), 0.44, 6, coll))
    parts.append(K.cylinder('bolt', (bx, -(bw + 0.15), bz), (bx, -(bw + 0.70), bz), 0.38, sg(7, 28), coll))
    # the pivot pin along y through both wings and the arm: its end on the right, its domed head on the left
    parts.append(K.cylinder('pin', (xc, -(e1 + 0.22), zc), (xc, e1 + 0.02, zc), 0.23, sg(7, 40), coll))
    parts.append(K.lathe('head', [(e1 - 0.10, 0.0), (e1 - 0.10, 0.34), (e1 + 0.12, 0.34), (e1 + 0.22, 0.25), (e1 + 0.28, 0.0)], (xc, 0.0, zc), (0.0, 1.0, 0.0),
                         sg(7, 40), coll))
    clip = K.tube('clip', (xc, -(e1 + 0.04), zc), (xc, -(e1 + 0.12), zc), 0.37, 0.17, sg(7, 40), coll)
    K.boolean(clip, K.box('cut', (xc - 0.07, -(e1 + 0.2), zc + 0.10), (xc + 0.07, -(e1 - 0.02), zc + 0.55), coll))      # a C: open at the top
    parts.append(clip)
    ball_c = Vector((xc, -e1, zc + 0.60))
    parts.append(FM.ball('ball', ball_c, 0.12, (0.0, -1.0, 0.0), sg(7, 20), coll))                  # the detent ball standing out of the right wing
    # the windage screw: a shaft between the wings, a slotted head on the left, the knob on the right behind a click plate
    parts.append(K.cylinder('shaft', (wx, -(e1 + 0.30), wz), (wx, e1 + 0.04, wz), 0.17, sg(7, 28), coll))
    parts.append(K.cylinder('whead', (wx, e1 - 0.02, wz), (wx, e1 + 0.16, wz), 0.28, sg(7, 28), coll))
    parts.append(K.cylinder('plate', (wx, -(e1 - 0.02), wz), (wx, -(e1 + 0.10), wz), 0.64, sg(7, 40), coll))
    K.boolean(base, parts, 'UNION')
    # the apertures: a through hole each with a countersunk rim on the eye side (-x)
    cuts = []

    def holes():
        out = []
        for az, ar in apertures:
            out.append(K.cylinder('cut', (xa0 - 1.0, 0.0, az), (xa1 + 1.0, 0.0, az), ar, sg(10, 32), coll))
            e = 0.02
            out.append(K.cylinder('cut', (xa0 - e, 0.0, az), (xa0 + cs_d, 0.0, az), ar + cs_w * (1.0 + e / cs_d), sg(10, 32), coll, r1=ar))   # 10 x LP_Q sides in the game model: a round rim in the aiming view
        return out
    cuts += holes()
    for side in (1.0, -1.0):                                               # a lightening slot in each wing
        a, b = sorted((side * (e0 - 0.1), side * (e1 + 0.1)))
        cuts.append(K.prism('cut', K.round_poly(S.rect(xc - 0.28, xc + 0.02, sight_z - 0.40, sight_z + 0.25, 0.14), sg(1, 6)), 'XZ', a, b, coll))
    K.boolean(base, cuts)
    kx, kz = wx, wz                                                          # the windage knob, right
    K.boolean(base, K.lathe('knob', [(knob_y[0], 0.0), (knob_y[0], knob_r - 0.06), (knob_y[0] + 0.06, knob_r), (knob_y[1] - 0.05, knob_r),
                                     (knob_y[1], knob_r - 0.10), (knob_y[1], 0.30), (-(e1 + 0.05), 0.30), (-(e1 + 0.05), 0.0)],
                            (kx, 0.0, kz), (0.0, 1.0, 0.0), sg(11, 40), coll), 'UNION')   # 11 x LP_Q sides in the game model: round at 8 to 15 cm
    K.cleanup(base)
    if hp:
        # the knob's grip: 28 cuts along it (a pitch of 0.11 cm), all the way round
        n_k = 28
        cuts = [K.prism_m('cut', S.rect(knob_y[0] - 0.1, knob_y[1] - 0.12, -0.034, 0.034),
                          Matrix.Translation((kx, 0.0, kz)) @ Matrix.Rotation(math.radians(360.0 / n_k * i), 4, 'Y') @ _T,
                          knob_r - 0.06, knob_r + 0.3, coll) for i in range(n_k)]
        cuts += F.screw_cuts((kx, knob_y[0], kz), (0.0, -1.0, 0.0), 0.30, coll, slot_deg=90.0)             # a slotted screw in its face
        cuts += F.screw_cuts((kx, e1 + 0.16, kz), (0.0, 1.0, 0.0), 0.25, coll, slot_deg=20.0)               # and the slotted head on the left
        for i in range(16):                                                      # the screw's thread between the wings: rings every 0.10
            y = -e0 + 0.10 + 0.10 * i
            if y < e0 - 0.08:
                cuts.append(K.tube('cut', (kx, y, kz), (kx, y + 0.05, kz), 0.24, 0.145, 24, coll))
        for i in range(12):                                                      # the click plate: small holes round the knob (not the two that fall into the clamp bar)
            if i in (5, 6):
                continue
            a = math.radians(30.0 * i + 15.0)
            hc = Vector((kx + 0.565 * math.sin(a), -(e1 + 0.17), kz + 0.565 * math.cos(a)))
            cuts.append(K.cylinder('cut', hc, hc + Vector((0.0, 0.17, 0.0)), 0.045, 10, coll))
        for i in (0, 1, 2, 3):                                                   # white index ticks round the plate, on the wing's face (clear of the pivot pin and its clip)
            a = math.radians(-30.0 + 15.0 * i)
            f = FM.surface_frame(Vector((kx + 0.95 * math.sin(a), -e1, kz + 0.95 * math.cos(a))), (0.0, -1.0, 0.0), up=(math.sin(a), 0.0, math.cos(a)))
            cuts.append(FM.engrave([(-0.035, -0.12), (0.035, -0.12), (0.035, 0.12), (-0.035, 0.12)], f, 0.03, coll, ink=0))
        # the pivot: the pin's end (a ring groove round it), a bolt head slot
        cuts += F.pin_cuts((xc, -(e1 + 0.22), zc), (0.0, -1.0, 0.0), 0.14, coll)
        cuts += F.screw_cuts((bx, -(bw + 0.70), bz), (0.0, -1.0, 0.0), 0.27, coll, slot_deg=40.0)
        # the arm's rear face: anti-glare serrations, horizontal V grooves (0.04 deep, walls at 45 degrees). They leave one flat
        # vertical land round the apertures: each stops 0.08 short of the largest countersink's rim (a straight strip, not a
        # stair round each circle), so each rim is a clean circle on smooth metal; every groove the same two strips, square ends
        land = max(r for _z, r in apertures) + cs_w + 0.08
        s0, count, pitch = serrations
        for i in range(count):
            z = s0 + pitch * i
            spans = [(-(hw + 0.02), -land), (land, hw + 0.02)]
            for lo, hi in spans:
                cuts.append(K.prism('cut', [(xa0 - 0.05, z - 0.09), (xa0 - 0.05, z + 0.09), (xa0 + 0.04, z)], 'XZ', lo, hi, coll))
        # the arm's lower half, below the large aperture: a shallow milled pocket either side of the centre rib (0.14 deep), seen from 8 to 15 cm
        for sgn in (1.0, -1.0):
            ya, yb = sorted((sgn * 0.20, sgn * 0.66))
            cuts.append(K.prism('cut', K.round_poly(S.rect(ya, yb, zc - 0.30, zc + 0.26, 0.13), seg(2, 6)), 'YZ', xa0 - 0.3, xa0 + 0.14, coll))
        # the base: a split line between clamp plate and body (a V groove along each side), the rear face's recessed panel with two slotted screws
        for side in (1.0, -1.0):
            a, b = sorted((side * (bw - 0.06), side * (bw + 0.06)))
            cuts.append(K.prism('cut', [(x0 - 0.1, rail_z + 0.31), (x0 - 0.1, rail_z + 0.39), (x1 + 0.1, rail_z + 0.39), (x1 + 0.1, rail_z + 0.31)], 'XZ', a, b, coll))
        pz0, pz1 = rail_z + 0.14, rail_z + 0.44
        cuts.append(K.prism('cut', K.round_poly(S.rect(-0.95, 0.95, pz0, pz1, 0.07), seg(2, 4)), 'YZ', x0 - 0.3, x0 + 0.07, coll))
        for sy in (-0.55, 0.55):
            cuts += F.screw_cuts((x0 + 0.07, sy, (pz0 + pz1) / 2), (-1.0, 0.0, 0.0), 0.095, coll, slot_deg=35.0 + 80.0 * sy, depth=0.03)
        # the wings' outer faces: a shallow sunk panel each, the left one round the elevation scale (four ticks and the numerals 1 to 4, white)
        for side in (1.0, -1.0):
            a, b = (e1 - 0.03, e1 + 0.2) if side > 0 else (-(e1 + 0.2), -(e1 - 0.03))
            cuts.append(K.prism('cut', K.round_poly(S.rect(ex0 + 0.10, ex0 + 0.72, panel_z[0], panel_z[1], 0.12), seg(2, 4)), 'XZ', a, b, coll))
        for i, z in enumerate(scale_z):
            f = FM.surface_frame(Vector((ex0 + 0.38, e1 - 0.03, z)), (0.0, 1.0, 0.0))
            cuts.append(FM.engrave([(0.0, -0.03), (0.18, -0.03), (0.18, 0.03), (0.0, 0.03)], f, 0.03, coll, ink=0))
            cuts.append(K.text_solid('cut', str(i + 1), 0.50, (ex0 + 0.60, e1 - 0.03, z - 0.18), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.03, coll))
        K.boolean(base, [c for c in cuts if c is not None])
        K.boolean(base, holes())                                           # the countersinks again, cleanly: the serrations had nicked their rims
    return base
