"""AssaultG3: what shows of a rifle's barrel ahead of its handguard: a castellated barrel nut, a gas block with cross pins and
a two-position regulator, and a slotted flash hider with a recessed crown. This is AssaultG3's own design, kept in its folder;
the weapon's dimensions come in as arguments.

The barrel itself is the weapon's own lathe profile (its taper, steps and thread are what make it that gun); these add to it.
All of them are on the bore: the line y = 0, z = bz along +x. `seg(lo, hi)` is the builder's segment dial bound to hp. The
cutters that only the bake source gets come back as lists, so the builder can cut them in one pass in the order it wants
(the order of the cuts decides which ones the exact solver hands to the second one: PLAYBOOK, "Modelling", items 48 and 49).
"""
import math

from mathutils import Matrix

from weaponforge import fittings as F
from weaponforge import forms as FM
from weaponforge import kit as K
from weaponforge import sections as S


def gas_ring(x0, x1, r):
    """The gas block's ring as four points of the barrel's lathe profile [(x, radius)]: from x0 to x1, radius r, its ends
    chamfered 0.12. Put the barrel's own points before and after it (0.02 clear of its ends)."""
    return [(x0, r - 0.12), (x0 + 0.12, r), (x1 - 0.12, r), (x1, r - 0.12)]


def gas_block(obj, x0, x1, r, bz, coll, seg, reg_r=0.52, reg_h=0.70, flat=None, pin_reach=None, pin_r=0.15, pin_in=0.34):
    """Onto a barrel whose profile has `gas_ring(x0, x1, r)`: the regulator's knob standing on the ring's top (radius reg_r,
    reg_h above it, its top edge broken), two wrench flats (`flat` from the middle, default 0.12 inside the ring), the two
    cross pins standing on them (radius pin_r, `pin_in` in from the ring's ends, reaching `pin_reach` from the middle, default
    0.04 inside the ring) and the regulator's detent flange. Four booleans, in that order. On the bake source add
    `cross_pin_heads`, `regulator_notches`, `regulator_grip` and `gas_ring_groove` (or `gas_block_cuts`, all four)."""
    flat = r - 0.12 if flat is None else flat
    pin_reach = r - 0.04 if pin_reach is None else pin_reach
    rx = (x0 + x1) / 2
    reg = K.cylinder('reg', (rx, 0.0, bz + r - 0.2), (rx, 0.0, bz + r + reg_h), reg_r, seg(8, 32), coll)
    K.bevel(reg, lambda e, m, d: abs(m.z - (bz + r + reg_h)) < 1.0e-4 and abs(d.z) < 0.01, 0.07, seg(1, 3))
    K.boolean(obj, reg, 'UNION')
    gf = [K.box('cut', (x0 + 0.12, flat if s > 0 else -2.0, bz - 2.0), (x1 - 0.12, 2.0 if s > 0 else -flat, bz + 2.0), coll) for s in (1.0, -1.0)]
    K.boolean(obj, gf)
    pins = [K.cylinder('pin', (px, -pin_reach, bz), (px, pin_reach, bz), pin_r, seg(3, 16), coll) for px in (x0 + pin_in, x1 - pin_in)]
    K.boolean(obj, pins, 'UNION')
    K.boolean(obj, K.cylinder('flange', (rx, 0.0, bz + r - 0.05), (rx, 0.0, bz + r + 0.15), reg_r + 0.17, seg(6, 32), coll), 'UNION')
    return obj


def cross_pin_heads(x0, x1, bz, coll, pin_r=0.15, pin_reach=1.12, pin_in=0.34):
    """The cross pins' slotted heads, both sides (bake source): each slot turned its own way."""
    cuts = []
    for sgn in (-1.0, 1.0):
        for px in (x0 + pin_in, x1 - pin_in):
            cuts += F.screw_cuts((px, sgn * pin_reach, bz), (0.0, sgn, 0.0), pin_r, coll, slot_deg=90.0 * (px - x0))
    return cuts


def regulator_notches(x0, x1, r, bz, coll, reg_r=0.52, count=12):
    """The detent notches round the regulator's flange (bake source)."""
    rx = (x0 + x1) / 2
    cuts = []
    for i in range(count):
        a = math.radians(360.0 / count * i)
        cuts.append(K.box('cut', (rx + (reg_r + 0.17) * math.cos(a) - 0.07, (reg_r + 0.17) * math.sin(a) - 0.07, bz + r + 0.03),
                          (rx + (reg_r + 0.17) * math.cos(a) + 0.07, (reg_r + 0.17) * math.sin(a) + 0.07, bz + r + 0.30), coll))
    return cuts


def regulator_grip(x0, x1, r, bz, coll, reg_r=0.52, reg_h=0.70, count=14):
    """The regulator knob's grip (axial cuts all round), its two positions (a slot across the top and two index dots) (bake
    source)."""
    rx = (x0 + x1) / 2
    cuts = []
    for i in range(count):
        a = math.radians(360.0 / count * i)
        cuts.append(K.transform(K.box('cut', (-0.045, -0.045, 0.0), (0.045, 0.045, reg_h - 0.2), coll),
                                Matrix.Translation((rx + (reg_r - 0.02) * math.cos(a), (reg_r - 0.02) * math.sin(a), bz + r + 0.0))))
    cuts.append(K.box('cut', (rx - 0.30, -0.045, bz + r + reg_h - 0.04), (rx + 0.30, 0.045, bz + r + reg_h + 0.2), coll))
    for sgn in (-1.0, 1.0):
        cuts.append(K.cylinder('cut', (rx + sgn * 0.0, sgn * 0.33, bz + r + reg_h - 0.035), (rx, sgn * 0.33, bz + r + reg_h + 0.2), 0.06, 12, coll))
    return cuts


def gas_ring_groove(x0, r, bz, coll):
    """A ring groove round the gas block, 0.5 from its rear end (bake source)."""
    return [K.tube('cut', (x0 + 0.5, 0.0, bz), (x0 + 0.56, 0.0, bz), r + 0.2, r - 0.035, 48, coll)]


def gas_block_cuts(x0, x1, r, bz, coll, reg_r=0.52, reg_h=0.70, pin_r=0.15, pin_reach=None, pin_in=0.34):
    """All of the gas block's bake-source cuts, in the order AssaultG3 cuts them (it puts the barrel's own rings after the
    notches)."""
    pin_reach = r - 0.04 if pin_reach is None else pin_reach
    return (cross_pin_heads(x0, x1, bz, coll, pin_r, pin_reach, pin_in) + regulator_notches(x0, x1, r, bz, coll, reg_r)
            + regulator_grip(x0, x1, r, bz, coll, reg_r, reg_h) + gas_ring_groove(x0, r, bz, coll))


def castellate(obj, x1, r, bz, coll, count=8, depth=0.50, half_w=0.18, reach=0.40, turn=22.5):
    """Cut `count` castellations (wrench slots) into the front end of a nut whose front face is at x1 and radius r: each `depth`
    deep along the bore and 2 * half_w wide, the first `turn` degrees round from the top (off the barrel's segment lines)."""
    K.boolean(obj, [K.transform(K.box('cut', (x1 - depth, -half_w, r - reach), (x1 + 0.05, half_w, r + 0.4), coll),
                                FM.about_bore(360.0 / count * i + turn, bz)) for i in range(count)])
    return obj


def flash_hider(name, x0, x1, bz, coll, seg, hp, r=1.08, r_in=0.62, bore_r=0.285, collar_r=0.95, slot=None,
                slot_deg=(0.0, 54.0, -54.0, 108.0, -108.0), keep=None):
    """A slotted flash hider from x0 (its rear face, on the barrel's thread) to x1 (the muzzle): a collar of radius collar_r, a
    cup of radius r with its front edge chamfered, a recessed crown (the face steps in 0.14 to a bore of r_in), slots at
    `slot_deg` degrees round from the top (none underneath: the ground is there), the bore (bore_r) up the middle and, on the
    bake source, two turned rings behind the slots. slot: (from x, to x, half width), default 1.65 to 3.75 from the rear, 0.15.
    keep: a UV-seam predicate kept through the cleanup (default forms.bore_seam(bz)). Built with start=DOWN. Returns the
    part untagged."""
    if slot is None:
        slot = (x0 + 1.65, x0 + 3.75, 0.15)
    floor = slot[0] - 0.15
    obj = K.lathe(name, [(x0, 0.0), (x0, collar_r), (x0 + 0.25, collar_r), (x0 + 0.25, r), (x1 - 0.30, r), (x1 - 0.02, r - 0.12), (x1, r - 0.26),
                         (x1 - 0.14, r - 0.40), (x1 - 0.14, r_in + 0.12), (x1 - 0.26, r_in), (floor, r_in), (floor, 0.0)], (0.0, 0.0, bz), (1.0, 0.0, 0.0),
                  seg(12, 48), coll, start=FM.DOWN)
    s0, s1, w = slot
    cutters = [K.prism_m('cut', K.round_poly(S.rect(s0, s1, -w, w, w - 0.01), seg(2, 6)), FM.about_bore(deg, bz), 0.30, r + 0.4, coll)
               for deg in slot_deg]
    cutters.append(FM.turned(K.cylinder('cut', (floor - 1.2, 0.0, bz), (floor + 0.3, 0.0, bz), bore_r, seg(8, 24), coll), 2.3, (0.0, 0.0, bz)))   # the bore
    if hp:                                                                      # two turned rings behind the slots
        cutters += [K.tube('cut', (x0 + d_, 0.0, bz), (x0 + d_ + 0.07, 0.0, bz), r + 0.2, r - 0.05, 48, coll) for d_ in (0.75, 1.0)]
    K.boolean(obj, cutters)
    K.cleanup(obj, keep=FM.bore_seam(bz) if keep is None else keep)
    return obj
