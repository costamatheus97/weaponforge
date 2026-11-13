"""TemplateGun: the part builders. Each is fn(coll, hp=False): it leaves its mesh object(s) in coll, in the weapon frame, tagged
with K.tag(obj, bone, mat=kind), and deletes every helper it made.

The game mesh and the bake source come from the same code. hp=True raises the segment counts and adds the small cuts the game
mesh only gets through its normal map (grooves, pins, markings). Rules that keep the meshes clean (PLAYBOOK.md, "Modelling"):

  * build big rounded shapes as real geometry (K.round_poly, K.bevel before a boolean); leave the fine edge break to the bake
  * never let a cutter's face lie in a face of its target, and never model two parts into the same surface: offset by 0.02 cm
  * one closed solid per part; anything that moves on its own in the game is its own part on its own bone

Use the shared technique before writing your own (PLAYBOOK, "Modelling", item 66; docs/kit.md): weaponforge/sections.py (a
faceted section's arithmetic, pure Python for params.py), forms.py (section_loft, pocket, boss, the ray-placed marks' frame)
and fittings.py (screws, pins, plates, sling fittings, selector and moulding marks). Here the slide is a section loft, the
grip screws, frame pins and selector marks are fittings. Sights and barrel furniture are designed in the weapon's own folder: AssaultG3's
(weapons/assault_g3/sights.py, barrels.py) are its own, for a brief that asks for that design.
"""
import math

from mathutils import Matrix, Vector

from weaponforge import fittings as F
from weaponforge import forms as FM
from weaponforge import kit as K
from weaponforge import sections as S

from . import params as P

LP_Q = 2.0        # game-mesh roundness: scales every game-resolution segment count (the triangle budget dial)
tag = K.tag


def seg(hp, lo, hi):
    """Segments for a rounded feature: `hi` on the bake source, `lo` (times LP_Q) on the game mesh."""
    return hi if hp else max(1, int(lo * LP_Q + 0.5))


def grip_matrix():
    """Local X toward the front strap, local Y lateral, local Z up the grip; origin on the magazine's centre line at z = 0."""
    ex, ez = Vector(P.GRIP_FRONT_N), Vector(P.GRIP_AXIS)
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2] = ex[i], (0.0, 1.0, 0.0)[i], ez[i]
    m[0][3] = P.mag_centre_x(0.0)
    return m


def mag_section(grow, s90):
    """The magazine's cross-section in the grip frame, grown by `grow` (the well is the same shape plus clearance)."""
    d, w = P.MAG_DEPTH / 2 + grow, P.MAG_HW + grow
    return K.round_poly([(-d, -w, 0.25), (d, -w, 0.25), (d, w, 0.25), (-d, w, 0.25)], s90)


# ------------------------------------------------------------------------------------------------------------------ frame
def frame(coll, hp=False):
    s90 = seg(hp, 2, 8)
    profile = K.round_poly([
        (P.FRAME_X1, P.FRAME_BOT, 0.5), (P.FRAME_X1, P.SLIDE_BOT), (P.SLIDE_X0, P.SLIDE_BOT),
        (P.back_strap_x(P.GRIP_BOT), P.GRIP_BOT, 0.6), (P.front_strap_x(P.GRIP_BOT), P.GRIP_BOT, 0.4), (P.GRIP_FRONT_X, P.FRAME_BOT, 0.5),
    ], s90)
    body = K.prism('Frame', profile, 'XZ', -P.FRAME_HW, P.FRAME_HW, coll)
    # the magazine well: the magazine's section plus clearance, cut up the grip from far below it
    well = K.prism_m('cut', mag_section(P.WELL_CLEAR, s90), grip_matrix(), -20.0, (P.MAG_TOP + 0.10) / math.cos(P.RAKE), coll)
    cutters = [well]
    if hp:
        # bake-only detail (item 64): the ends of two pins on each side and three grooves across the front strap
        for x in (5.2, 8.6):
            for side in (1.0, -1.0):
                cutters += F.pin_cuts((x, side * P.FRAME_HW, 2.8), (0.0, side, 0.0), 0.22, coll)
        for z in (-1.5, -2.6, -3.7):
            x = P.front_strap_x(z)
            cutters.append(K.box('cut', (x - 0.05, -P.FRAME_HW - 0.1, z - 0.07), (x + 0.3, P.FRAME_HW + 0.1, z + 0.07), coll))
        # the selector's marks where the lever's front end points, safe (ink 0) and fire (ink 1): placed by a ray from the left,
        # so they lie on the surface whatever its slope; painted from `paint` in weapon.py, and cut last (item 49)
        cutters += F.safe_mark(body, *F.side_ray(*P.SAFE_AT, 1.0), coll) + F.fire_mark(body, *F.side_ray(*P.FIRE_AT, 1.0), coll)
    K.boolean(body, cutters)
    return tag(K.shade(body), 'Grip_Bone', mat='polymer')


# ------------------------------------------------------------------------------------------------------------------ slide
def slide(coll, hp=False):
    # a section loft (item 65): flat facets meeting in creases with a real radius, the top chamfer growing toward the muzzle.
    # side: the slide's side outline; the section is its left half's sharp corners [(y, z, radius)] from the underside up
    side = [(P.SLIDE_X0, P.SLIDE_BOT), (P.SLIDE_X1, P.SLIDE_BOT), (P.SLIDE_X1, P.SLIDE_TOP), (P.SLIDE_X0, P.SLIDE_TOP)]
    chamfer, k = S.lin(P.SLIDE_CHAMFER), seg(hp, 1, 4)

    def section(x, lo, hi):
        c = chamfer(x)
        return S.facet_ring([(P.SLIDE_HW, lo, 0.10), (P.SLIDE_HW, hi - c, 0.12), (P.SLIDE_HW - c, hi, 0.12)], lo, (0.0, hi), k)
    body = FM.section_loft('Slide', side, section, coll, P.SLIDE_X0, P.SLIDE_X1, 3.0 if hp else 6.0, 0.04 if hp else 0.15,
                           knots=S.knots(P.SLIDE_CHAMFER))
    # the tunnel the barrel sits in: a little wider than the barrel, and open at the front
    cutters = [K.cylinder('cut', (P.TUNNEL_X0, 0, P.BZ), (P.SLIDE_X1 + 0.5, 0, P.BZ), P.BARREL_R + P.TUNNEL_CLEAR, seg(hp, 12, 48), coll)]
    if hp:
        for i in range(P.SERR_COUNT):                    # grasping grooves: on the game mesh they exist only in the normal map
            x = P.SERR_X0 + i * P.SERR_PITCH
            for side in (1.0, -1.0):
                y0, y1 = sorted((side * (P.SLIDE_HW - P.SERR_D), side * (P.SLIDE_HW + 0.1)))
                cutters.append(K.box('cut', (x, y0, P.SLIDE_BOT + 0.3), (x + P.SERR_W, y1, P.SLIDE_TOP - 0.5), coll))
        # lettering: on the left side it reads toward the butt. K.text_solid cuts `depth` deep, and the tool keeps a copy of
        # the letters for the bake, so the look can fill them with paint (`paint` in weapon.py); a second colour is ink=1
        cutters.append(K.text_solid('cut', P.MARK, 0.55, (6.5, P.SLIDE_HW, (P.SLIDE_BOT + P.SLIDE_TOP) / 2), (-1, 0, 0), (0, 0, 1), 0.02, coll))
    K.boolean(body, cutters)
    return tag(K.shade(body), 'Slide_Bone')


def sights(coll, hp=False):
    """A builder may leave several parts; each needs its own name and tag. (AssaultG3's own sights.py, in its folder, has a
    rear_aperture and a front_post that clamp a pair on a rail: an aperture's sides and its land are done there, item 66.)"""
    top = P.SLIDE_TOP + P.SIGHT_H
    front = K.prism('SightFront', [(P.FRONT_SIGHT_X[0], P.SLIDE_TOP), (P.FRONT_SIGHT_X[1], P.SLIDE_TOP), (P.FRONT_SIGHT_X[1] - 0.25, top),
                                   (P.FRONT_SIGHT_X[0], top)], 'XZ', -0.16, 0.16, coll)
    rear = K.box('SightRear', (P.REAR_SIGHT_X[0], -0.55, P.SLIDE_TOP), (P.REAR_SIGHT_X[1], 0.55, top), coll)
    K.boolean(rear, K.box('cut', (P.REAR_SIGHT_X[0] - 0.1, -0.17, P.SLIDE_TOP + 0.15), (P.REAR_SIGHT_X[1] + 0.1, 0.17, top + 0.1), coll))
    return [tag(K.shade(front), 'Slide_Bone', mat='dark'), tag(K.shade(rear), 'Slide_Bone', mat='dark')]


# ----------------------------------------------------------------------------------------------------------------- barrel
def barrel(coll, hp=False):
    # a pistol's barrel is a tube under its slide; a rifle's lathe profile can take a gas block, a castellated nut and a
    # flash hider on its thread (AssaultG3's own barrels.py has them)
    tube = K.tube('Barrel', (P.BARREL_X0, 0, P.BZ), (P.MUZZLE_X, 0, P.BZ), P.BARREL_R, P.BORE_R, seg(hp, 12, 48), coll)
    return tag(K.shade(tube), 'Barrel_Bone', mat='bright')


# --------------------------------------------------------------------------------------------------------------- magazine
def magazine(coll, hp=False):
    s90 = seg(hp, 2, 8)
    z0, z1 = (P.GRIP_BOT - P.MAG_BELOW) / math.cos(P.RAKE), P.MAG_TOP / math.cos(P.RAKE)
    body = K.prism_m('Magazine', mag_section(0.0, s90), grip_matrix(), z0, z1, coll)
    if hp:
        m = grip_matrix()
        cutters = []
        for i in range(3):                               # witness holes down the left side
            centre = m @ Vector((0.0, P.MAG_HW, z0 + 2.0 + i * 1.6))
            cutters.append(K.cylinder('cut', centre - Vector((0, 0.05, 0)), centre + Vector((0, 0.05, 0)), 0.16, 20, coll))
        K.boolean(body, cutters)
    return tag(K.shade(body), 'Clip_Bone')


# ----------------------------------------------------------------------------------------------------------- safety lever
def safety(coll, hp=False):
    """A part that turns about a pin. Build it in its rest pose; the bone sits on the pin (weapon.py) and the game, the poses and
    the travel check turn it from there."""
    (px, pz), hh = P.SAFETY_PIVOT, P.SAFETY_HH
    outline = K.round_poly([(px - 0.24, pz - hh, 0.17), (px + P.SAFETY_LEN, pz - hh, 0.10), (px + P.SAFETY_LEN, pz + hh, 0.10),
                            (px - 0.24, pz + hh, 0.17)], seg(hp, 2, 8))
    y0 = P.FRAME_HW + P.SAFETY_GAP
    obj = K.prism('Safety', outline, 'XZ', y0, y0 + P.SAFETY_T, coll)
    if hp:
        cutters = []
        for k in range(3):                               # thumb grooves near the front end
            x = px + P.SAFETY_LEN - 0.30 - k * 0.24
            cutters.append(K.box('cut', (x, y0 + P.SAFETY_T - 0.04, pz - hh - 0.1), (x + 0.10, y0 + P.SAFETY_T + 0.1, pz + hh + 0.1), coll))
        K.boolean(obj, cutters)
    return tag(K.shade(obj), 'Safety_Bone', mat='dark')


# ------------------------------------------------------------------------------------------------------------ grip panels
def grip_panel(coll, side=1.0, hp=False):
    """One builder function, used twice (weapon.py registers grip_l and grip_r)."""
    i = P.PANEL_INSET
    outline = K.round_poly([
        (P.front_strap_x(P.GRIP_BOT + i) - i, P.GRIP_BOT + i, 0.3), (P.front_strap_x(1.4) - i, 1.4, 0.3),
        (P.back_strap_x(1.4) + i, 1.4, 0.3), (P.back_strap_x(P.GRIP_BOT + i) + i, P.GRIP_BOT + i, 0.3),
    ], seg(hp, 2, 8))
    y0, y1 = sorted((side * P.FRAME_HW, side * (P.FRAME_HW + P.PANEL_T)))
    obj = K.prism('GripL' if side > 0 else 'GripR', outline, 'XZ', y0, y1, coll)
    if hp:
        outer = side * (P.FRAME_HW + P.PANEL_T)
        # the screw that holds the panel, on the panel's middle line, found by a ray from outside (fittings.fastener); its hex
        # squared to the grip's axis
        sz = P.GRIP_BOT + 1.2 + P.PANEL_SCREW * 0.85 + 0.06
        cutters = F.fastener(obj, *F.side_ray((P.back_strap_x(sz) + P.front_strap_x(sz)) / 2, sz, side), coll, up=P.GRIP_AXIS)
        for k in range(7):                               # grooves across the panel, none where the screw is
            if k == P.PANEL_SCREW:
                continue
            z = P.GRIP_BOT + 1.2 + k * 0.85
            a, b = sorted((outer - side * 0.05, outer + side * 0.1))
            cutters.append(K.box('cut', (P.back_strap_x(z) + i + 0.35, a, z), (P.front_strap_x(z) - i - 0.35, b, z + 0.12), coll))
        K.boolean(obj, cutters)
    return tag(K.shade(obj), 'Grip_Bone', mat='wood')


BUILDERS = {
    'frame': frame, 'slide': slide, 'sights': sights, 'barrel': barrel, 'magazine': magazine, 'safety': safety,
    'grip_l': lambda coll, hp=False: grip_panel(coll, 1.0, hp),
    'grip_r': lambda coll, hp=False: grip_panel(coll, -1.0, hp),
}
