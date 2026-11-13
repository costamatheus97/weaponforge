"""AssaultG3: the part builders. Each is fn(coll, hp=False): it leaves its mesh object(s) in coll, in the weapon frame, tagged
with K.tag(obj, bone, mat=kind), and deletes every helper it made.

The game mesh and the bake source come from the same code. hp=True raises the segment counts and adds the small cuts the game
mesh only gets through its normal map. Rules that keep the meshes clean (PLAYBOOK.md, "Modelling"):

  * build big rounded shapes as real geometry (K.round_poly, K.bevel before a boolean); leave the fine edge break to the bake
  * never let a cutter's face lie in a face of its target, and never model two parts into the same surface: offset by 0.02 cm
  * one closed solid per part; anything that moves on its own in the game is its own part on its own bone
  * a cutter on the bore is turned a degree or two off the lines of what it cuts (PLAYBOOK, Modelling 48)

The faceted-section loft, the cuts that follow the shell's surface and the hardware were moved into the shared kit
(weaponforge/sections.py, forms.py, fittings.py) with their arithmetic unchanged. Both sights and the barrel's details are this
weapon's own designs and stay in its folder (sights.py, barrels.py); what is left here is its composition: its section, its
outline, its parts and their order.

What is new with this weapon: the whole gun is one shell, a side outline of one thickness with its side edges rounded, and
every hole in it is a cut: the carrier's tunnel (a hole closed at both ends, opened by the port and the magazine's way in),
the magazine well, the charging handle's slot, the trigger's slot, the hole for the safety and the sling's slot. The grip and
the guard for the whole hand are one part made of two thicknesses.
"""
import math

import bmesh
import numpy as np
from mathutils import Matrix, Vector

from weaponforge import fittings as F
from weaponforge import forms as FM
from weaponforge import kit as K
from weaponforge import sections as S

from . import barrels as BR
from . import params as P
from . import sights as SI

LP_Q = 3.4        # game-mesh roundness: scales every game-resolution segment count (the triangle budget dial)
tag = K.tag
AXIS = (1.0, 0.0, 0.0)
DOWN = (0.0, 0.0, -1.0)                # where the round parts on the bore start: a line of edges underneath, for the UV seam
BORE = (0.0, 0.0, P.BZ)
TOP = Matrix.Identity(4)               # the drawing plane for detail seen from above: (a, b) are the weapon's (x, y)
REAR = Matrix(((0.0, 0.0, -1.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)))     # seen from behind: (y, z)
LEFT, RIGHT = F.side_frame(1.0), F.side_frame(-1.0)
MOUNT = SI.Mount(P.RAIL_Z, P.RAIL_HW, P.SIGHT_BASE_HW, P.SIGHT_BASE_Z[0], P.SEAT)     # where both sights sit on the rail
rect = S.rect
densify = S.densify
inset_poly = FM.inset_poly


def seg(hp, lo, hi):
    """Segments for a rounded feature: `hi` on the bake source, `lo` (times LP_Q) on the game mesh."""
    return hi if hp else max(1, int(lo * LP_Q + 0.5))


def on_bore(x):
    return (x, 0.0, P.BZ)


def turned(obj, deg):
    """The object turned about the bore by deg: a cutter on the bore must not have its corners in the edges of what it cuts."""
    return FM.turned(obj, deg, BORE)


def shade(obj, hp, angle=30.0):
    """The parts cut from flat plate have large flat sides: on the bake source those keep their own normals (K.shade)."""
    return K.shade(obj, angle, flats=hp)


def bore_seam():
    """One cut along the underside of a part on the bore (built with start=DOWN, or with a vertex at its bottom centre)."""
    return FM.bore_seam(P.BZ)


def underside_seam():
    """The shell's cuts: the whole centre line under the bore, including the walls where the underside steps up (the well's rear
    and front, the release pocket), so that the left and right halves of the lower band never join across the underside; and, on each
    side, the line where the lower side facet meets the tucked facet (the first point of that crease's arc), so that the long side
    facet, the tuck and the underside are three flat strips and not one band that has to bend."""
    centre = K.in_plane((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    k = P.SECTION_K[0]
    index = 1 + (k + 1)                       # the ring's point after the bottom corner's arc: where the tuck's arc begins

    def on_tuck_line(v):
        span = P.outline_span(v.co.x)
        if span is None:
            return False
        y, z = P.ring(v.co.x, span[0], span[1], k)[index]
        return abs(abs(v.co.y) - y) < 2.0e-3 and abs(v.co.z - z) < 2.0e-3 and abs(v.co.y) > 0.3

    def test(e, mid, d):
        if centre(e) and mid.z < P.BZ:
            return True
        return abs(d.x) > 0.5 and all(on_tuck_line(v) for v in e.verts)
    return test


def grip_seam():
    """The grip's and the guard's one cut: the outside of the loop they make, along its centre plane: up the back strap, under the
    toe and the strap's underside, round the elbow and up the riser's back. An edge is on the outside when its faces look away from a
    point inside the loop."""
    centre = K.in_plane((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    inside = Vector((6.0, 0.0, -2.5))

    def test(e, mid, d):
        if centre(e) and mid.x > 4.0:
            return True                       # the strap itself, inside and outside, to its end: two flat halves (its long flat faces keep a centre line only if told to)
        if not centre(e) or mid.z > 4.3:
            return False
        n = Vector((0.0, 0.0, 0.0))
        for f in e.link_faces:
            n += f.normal
        out = n.dot(mid - inside)
        if out > 0.0:
            return True
        # the front strap's centre line, from the guard's root up to the grip's top: the grip is cut into a left and a right half, each flat
        return mid.x < 3.95 and mid.z > -5.15 and out < 0.0
    return test


def mag_seam():
    """One cut down the middle of the magazine's rear face (its rings start there)."""
    centre = K.in_plane((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    return lambda e, mid, d: centre(e) and mid.x < P.mag_centre_x(mid.z) - 1.0


def about_bore(deg):
    """A frame turned about the bore: its local z points out from the bore, `deg` round from straight up toward the left."""
    return FM.about_bore(deg, P.BZ)


# ------------------------------------------------------------------------------------------------------------------ shell
def shell_loft(coll, hp):
    """The shell's body: P.ring's faceted section skinned along the gun (forms.section_loft). Rings at every point of its outline
    (corners, comb) and at every knot of its tables (the ends of the width ramps, the belt line's jog, the collar); between those
    the facets are flat, so a ring is wanted only now and then. The rear face is raked: each ring is sheared toward the toe."""
    side = K.round_poly(P.SHELL_OUTLINE, P.SHELL_ARC[1 if hp else 0])
    k = P.SECTION_K[1 if hp else 0]
    return FM.section_loft('Shell', side, lambda x, lo, hi: P.ring(x, lo, hi, k), coll, P.BUTT_X, P.NOSE_LOFT,
                           3.0 if hp else 6.0, 0.04 if hp else 0.15, knots=P.SECTION_KNOTS, must=P.CV_MUST, warp=P.rake)


def well_way(coll, hp):
    """The magazine's way in from below: a rectangle that runs up into the tunnel, with a funnel at its mouth (a 45 degree chamfer round
    it, in the mouth's own sloped plane). One loft: the funnel's ring, the mouth's ring, the top ring."""
    (wx0, wx1), w = P.WELL_IN_X, P.WELL_IN_HW
    (zx0, zz0), (zx1, zz1) = (P.WELL_X[0], P.WELL_Z[0]), (P.WELL_X[1], P.WELL_Z[1])
    e, steps = P.WELL_FUNNEL, seg(hp, 1, 4)
    zm = lambda x: zz0 + (zz1 - zz0) * (x - zx0) / (zx1 - zx0)          # the mouth's plane

    def ring(grow, z_of):
        pts = K.round_poly([(wx0 - grow, -w - grow, 0.15 + grow), (wx1 + grow, -w - grow, 0.15 + grow),
                            (wx1 + grow, w + grow, 0.15 + grow), (wx0 - grow, w + grow, 0.15 + grow)], steps)
        return [(x, y, z_of(x)) for x, y in pts]
    top = P.BZ - 0.90
    return K.loft('cut', [ring(e + 0.10, lambda x: zm(x) - 0.10), ring(0.0, lambda x: zm(x) + e), ring(0.0, lambda x: top)], coll)


def nose_cuts(coll):
    """The handguard's front face slopes (its top leads its bottom by P.NOSE_LEAN) and is chamfered all round: a wedge that cuts the
    face, then four slabs, each cutting a chamfer plane along one edge of it (top, bottom and the two sides)."""
    k = P.NOSE_LEAN / (P.TOP_Z - P.LIP_Z)
    xp = lambda z: P.NOSE_X + (z - P.TOP_Z) * k                       # the face's x at height z
    c = P.NOSE_CHAMFER
    z1, z2 = P.TOP_Z + 1.5, P.LIP_Z - 1.5
    cutters = [K.prism('cut', [(xp(z1), z1), (xp(z2), z2), (xp(z2) + 4.0, z2), (xp(z1) + 4.0, z1)], 'XZ', -5.0, 5.0, coll)]
    nf = Vector((1.0, 0.0, -k)).normalized()                          # the face's normal (out, and a little down)
    for z_edge, up in ((P.TOP_Z, 1.0), (P.LIP_Z, -1.0)):             # the edges along the top and along the hand stop's underside
        a = Vector((xp(z_edge) - c, 0.0, z_edge))
        b = Vector((xp(z_edge - up * c), 0.0, z_edge - up * c))
        along = (b - a).normalized()
        out = (nf + Vector((0.0, 0.0, up))).normalized()
        quad = [a - along * 0.4 + Vector((0.0, -5.0, 0.0)), a - along * 0.4 + Vector((0.0, 5.0, 0.0)),
                b + along * 0.4 + Vector((0.0, 5.0, 0.0)), b + along * 0.4 + Vector((0.0, -5.0, 0.0))]
        cutters.append(FM.slab(quad, out, 2.5, coll))
    y0 = P.hw(P.NOSE_X)
    for sgn in (1.0, -1.0):                                           # the two vertical edges
        pa, pb = Vector((xp(z2), sgn * (y0 - c), z2)), Vector((xp(z1), sgn * (y0 - c), z1))
        pd, pc = Vector((xp(z2) - c, sgn * y0, z2)), Vector((xp(z1) - c, sgn * y0, z1))
        across = (pd - pa).normalized()
        quad = [pa - across * 0.4, pb - across * 0.4, pc + across * 0.4, pd + across * 0.4]
        cutters.append(FM.slab(quad, Vector((1.0, sgn, -k)), 2.5, coll))
    return cutters


def relief(coll, hp):
    """The pockets of the shell's sides: three flutes in each side of the butt, six vents in each side of the handguard and the
    recess round the ejection port on the right. All are cutters that follow the crowned surface."""
    cuts = []
    sx = 4 if hp else 3
    for z in P.FLUTE_Z:
        flute = K.round_poly(rect(P.FLUTE_X[0], P.FLUTE_X[1], z - P.FLUTE_HH, z + P.FLUTE_HH, P.FLUTE_HH), 6 if hp else 4)     # a true half circle at each end (a 0.02 cm edge between two arcs breaks the exact solver)
        flute = densify(flute, 0.5 if hp else 1.0)
        for side in (1.0, -1.0):
            cuts.append(FM.pocket(P.side_y, flute, side, P.FLUTE_DEPTH, P.FLUTE_INSET, coll, name='flute'))
    z0, z1 = P.VENT_Z
    for i in range(P.VENTS):
        x = P.VENT_X0 + P.VENT_PITCH * i
        vent = K.round_poly([(x, z0, 0.2), (x + P.VENT_W, z0, 0.2), (x + P.VENT_W + P.VENT_LEAN, z1, 0.2), (x + P.VENT_LEAN, z1, 0.2)], sx)
        vent = densify(vent, 0.5 if hp else 1.0)
        for side in (1.0, -1.0):
            cuts.append(FM.pocket(P.side_y, vent, side, P.VENT_DEPTH, P.VENT_INSET, coll, name='vent'))
    for sx0, sx1 in P.SLOT_X:                                                 # four accessory slots under the fore-end
        for side in (1.0, -1.0):
            o = K.round_poly([(sx0, side * P.SLOT_Y - P.SLOT_W / 2, P.SLOT_W / 2 - 0.01), (sx1, side * P.SLOT_Y - P.SLOT_W / 2, P.SLOT_W / 2 - 0.01),
                              (sx1, side * P.SLOT_Y + P.SLOT_W / 2, P.SLOT_W / 2 - 0.01), (sx0, side * P.SLOT_Y + P.SLOT_W / 2, P.SLOT_W / 2 - 0.01)], 4 if hp else 3)
            cuts.append(K.prism('slot', o, 'XY', P.HG_Z - 0.5, P.HG_Z + P.SLOT_DEPTH, coll))
    (px0, px1), (pz0, pz1) = P.PANEL_X, P.PANEL_Z
    panel = densify(K.round_poly(rect(px0, px1, pz0, pz1, P.PANEL_R), 4 if hp else 3), 0.6)
    cuts.append(FM.pocket(P.side_y, panel, -1.0, P.PANEL_DEPTH, 0.12, coll, name='panel'))
    return cuts


def deflector(coll, hp):
    """The case deflector at the port's rear edge: a wedge in the recess that rises toward the port, a short flat top, a face."""
    xa, xb, xc = P.DEFL_X
    z0, z1 = P.DEFL_Z
    floor = min(P.side_y(x, z) for x in (xa, xb, xc) for z in (z0, z1)) - P.PANEL_DEPTH
    prof = K.round_poly([(xa, floor - 0.30), (xa, floor), (xb, floor + P.DEFL_H, 0.20), (xc, floor + P.DEFL_H, 0.12), (xc, floor - 0.30)], seg(hp, 1, 4))
    return K.prism('deflector', [(x, -d) for x, d in prof], 'XY', z0, z1, coll)


# ---------------------------------------------------------------------------------------------------------------- marks (bake source only)
def fastener_top(body, x, side, coll):
    """A socket-head screw on the cover's shoulder facet (the slope between its top land and its side), found by a ray along the facet's normal
    (F.fastener, smaller than the side screws). Cutters, or [] on a miss."""
    lo, hi = P.outline_span(x)
    v, _top = P.facets(x, lo, hi)
    (ys, zs), (land, zh) = v[10][:2], v[11][:2]
    n = Vector((0.0, side * (zh - zs), -(land - ys))).normalized()        # the facet's outward normal
    mid = Vector((x, side * (ys + land) / 2.0, (zs + zh) / 2.0))
    return F.fastener(body, mid + n * 3.0, -n, coll, groove=(0.27, 0.20), hex_r=0.13, up=(1.0, 0.0, 0.0))


def _facet_mid(x):
    """(the shoulder facet's middle y, its land's y) at x: from the section's own table."""
    lo, hi = P.outline_span(x)
    v, _top = P.facets(x, lo, hi)
    (ys, _zs), (land, _zh) = v[10][:2], v[11][:2]
    return (ys + land) / 2.0, land


def cover_flutes():
    """The two lightening flutes along the cover's shoulder facets: lines in plan (x, y), each side."""
    x0, x1 = P.CFLUTE_X
    n = int((x1 - x0) / 0.5)
    return [[(x0 + (x1 - x0) * i / n, side * _facet_mid(x0 + (x1 - x0) * i / n)[0]) for i in range(n + 1)] for side in (1.0, -1.0)]


def cover_serrations():
    """Cross-grooves on the cover's top land behind the rear sight: a line across the land at each x."""
    x0, x1 = P.SERR_X
    n = int(round((x1 - x0) / P.SERR_PITCH))
    out = []
    for i in range(n + 1):
        x = x0 + P.SERR_PITCH * i
        land = _facet_mid(x)[1]
        out.append([(x, -(land - 0.12)), (x, land - 0.12)])
    return out


def shell(coll, hp=False):
    """The shell: butt, action housing, the flat over the grip and the trigger, and the handguard, as one loft whose section changes
    along the gun (P.ring: a flat land, a shoulder facet, a flat side with a little draft, a belt line where the lower moulding stands
    proud, a lower facet tucking in to a flat underside; the width changes in short ramps; the magazine well has a collar). Bosses round
    the pins and the safety and the cheek panels are added; the sloped front face is cut and chamfered; then the pockets (flutes,
    vents, the port's recess with its deflector); then the holes: the carrier's tunnel and the chamber on the bore, the ejection port
    on the right, the magazine's way in from below (with its funnel), the slots and holes of the controls and the barrel nut's
    counterbore. Order (PLAYBOOK, Modelling 49): what is added, then the pockets, then the holes, then the fine marks, the text last."""
    body = shell_loft(coll, hp)
    sx, sz = P.SAFE_XZ
    sg = lambda lo, hi: seg(hp, lo, hi)
    adds = [FM.boss(P.side_y, x, z, P.BOSS_PIN, P.BOSS_PIN_H, side, coll, sg) for x, z in P.PINS for side in (1.0, -1.0)]
    adds += [FM.boss(P.side_y, sx, sz, P.BOSS_SAFE, P.BOSS_SAFE_H, side, coll, sg) for side in (1.0, -1.0)]
    hold = K.box('hold', (P.HOLD_X[0], -P.HOLD_HW, P.HG_Z - P.HOLD_H), (P.HOLD_X[1], P.HOLD_HW, P.HG_Z + 0.35), coll)      # the rubber hold pad under the fore-end
    K.bevel(hold, lambda e, m, d: abs(m.z - (P.HG_Z - P.HOLD_H)) < 1.0e-4, 0.11, seg(hp, 1, 3))
    adds.append(hold)
    K.boolean(body, adds, 'UNION')
    K.boolean(body, nose_cuts(coll))
    K.boolean(body, relief(coll, hp))
    K.boolean(body, deflector(coll, hp), 'UNION')

    cutters = [
        turned(K.cylinder('cut', on_bore(P.TUNNEL_X0), on_bore(P.BOLT_FACE_X + 0.4), P.TUNNEL_R, seg(hp, 12, 48), coll), 3.7),
        turned(K.cylinder('cut', on_bore(P.BOLT_FACE_X - 0.6), on_bore(P.CHAMBER_X1), P.CHAMBER_R, seg(hp, 8, 24), coll), 2.3),
        K.prism('cut', K.round_poly(rect(P.PORT_X[0], P.PORT_X[1], P.PORT_Z[0], P.PORT_Z[1], 0.22), seg(hp, 2, 6)), 'XZ', -3.0, -0.3, coll),
        well_way(coll, hp),
        K.box('cut', (P.TRIG_SLOT_X[0], -P.TRIG_HW - 0.03, 3.4), (P.TRIG_SLOT_X[1], P.TRIG_HW + 0.03, 6.2), coll),
        K.box('cut', (P.CH_SLOT_X[0], P.CH_SLOT_FLOOR, P.CH_Z[0] - 0.03), (P.CH_SLOT_X[1], 3.0, P.CH_Z[1] + 0.03), coll),
        K.cylinder('cut', (sx, -3.0, sz), (sx, 3.0, sz), P.SAFE_R + 0.03, seg(hp, 8, 32), coll),
        K.box('cut', (P.REL_POCKET_X[0], -P.REL_HW - 0.04, P.REL_POCKET_Z[0]), (P.REL_POCKET_X[1], P.REL_HW + 0.04, P.REL_POCKET_Z[1]), coll),
        K.prism('cut', K.round_poly(rect(P.SLING_X[0], P.SLING_X[1], P.SLING_Z[0], P.SLING_Z[1], 0.4), seg(hp, 2, 6)), 'XZ', -3.0, 3.0, coll),
        turned(K.cylinder('cut', on_bore(P.NUT_X[0] - P.SEAT), on_bore(P.NOSE_X + 2.0), P.CBORE_R, seg(hp, 12, 48), coll), 3.7),   # the nut's counterbore
        F.plate_recess(P.PLATE_X[0], P.PLATE_X[1], P.PLATE_Z[0], P.PLATE_Z[1], P.side_y(sum(P.PLATE_X) / 2, P.PLATE_Z[0]) - P.PLATE_SINK, coll),   # the data plate's recess
        F.qd_cup(P.QD_XZ[0], P.QD_XZ[1], P.side_y(*P.QD_XZ) - P.QD_DEPTH, -1.0, coll, seg(hp, 8, 32), r=P.QD_R),    # pass 3b: a sling's quick-detach cup on the right
    ]
    K.boolean(body, cutters)
    K.cleanup(body, keep=underside_seam())
    if hp:
        # pass 3b: the right side's moulded panel line (a shallow frame round the sling cup), cut first: it follows the surface as it is
        frame = K.round_poly([(P.QD_PANEL_X[0], P.QD_PANEL_Z[0], 0.45), (P.QD_PANEL_X[1], P.QD_PANEL_Z[0], 0.45), (P.QD_PANEL_X[1], P.QD_PANEL_Z[1], 0.45),
                              (P.QD_PANEL_X[0], P.QD_PANEL_Z[1], 0.45)], 6)
        K.cut_grooves(body, K.grooves_on(body, [frame + [frame[0]]], RIGHT, coll, half_w=0.05, depth=0.06, step=0.10), coll)
        # pass 4: the cover's top, so the long black plane is not plain: a shallow lightening flute along each shoulder facet (ramped ends),
        # and fine anti-glare cross-grooves on the top land between the rear sight and the cheek saddle (cut before the fine marks, as the panel line is)
        K.cut_grooves(body, K.grooves_on(body, cover_flutes(), TOP, coll, half_w=P.CFLUTE_HW, depth=P.CFLUTE_D, facing=0.35, step=0.12), coll)
        K.cut_grooves(body, K.grooves_on(body, cover_serrations(), TOP, coll, half_w=0.045, depth=0.04, facing=0.8, step=0.12), coll)
        back, fwd, up = (-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)             # on the left side text reads toward the butt
        tx = (P.WELL_X[0] + P.WELL_X[1]) / 2
        cuts = []
        for side in (1.0, -1.0):
            out = (0.0, side, 0.0)
            cuts += F.pin_cuts((P.TRIG_PIVOT[0], side * P.side_y(P.TRIG_PIVOT[0], P.TRIG_PIVOT[1]), P.TRIG_PIVOT[1]), out, 0.10, coll)
            cuts += F.pin_cuts((9.80, side * P.side_y(9.80, 7.60), 7.60), out, 0.20, coll)  # and the barrel's
        # the markings last: the finest cuts go into the sides after the coarse ones. Lettering goes on a locally flat panel: the
        # side is nearly vertical where it is cut, and each line is set on the surface at its own height
        # pass 3b: bigger (the strokes were one texel at 2048) and cut a hair deeper, so that the paint fill has a wall to sit in
        cuts += [K.text_solid('cut', P.MARK_MODEL, 0.62, (tx, P.side_y(tx, 4.95), 4.95), back, up, 0.03, coll),
                 K.text_solid('cut', P.MARK_CAL, 0.50, (tx, P.side_y(tx, 4.30), 4.30), back, up, 0.03, coll),
                 K.text_solid('cut', P.MARK_SAFE, 0.38, (sx, P.side_y(sx, sz + 1.15), sz + 1.15), back, up, 0.03, coll),
                 K.text_solid('cut', P.MARK_FIRE, 0.38, (sx, -P.side_y(sx, sz + 1.15), sz + 1.15), fwd, up, 0.03, coll, ink=1)]      # red
        K.boolean(body, cuts)
        # pass 3: the marks that are found on the surface itself (a ray from outside gives the point and the normal, so each lies flat on
        # the slope it is on): the selector's pictograms, the rack number, the cover's screws, the arrow by the pin, the date clock,
        # the ejector pins' circles and the parting line
        marks = []
        zp = sz + P.PICTO_DZ
        marks += F.safe_mark(body, *F.side_ray(sx, zp, 1.0), coll)                    # "safe", white: a ring with a dot, on the left
        marks += F.fire_mark(body, *F.side_ray(sx, zp, -1.0), coll)                   # "fire", red: three bars, on the right
        # (the rack number is the worn `stencil_07` decal in weapon.py now, not a cut filled with paint: one, never both)
        for x, z, side in P.COVER_SCREWS:
            marks += F.fastener(body, *F.side_ray(x, z, side), coll)
        marks += F.arrow_mark(body, *F.side_ray(P.PINS[0][0], P.PINS[0][1] + 1.25, 1.0), coll)
        marks += F.lock_mark(body, *F.side_ray(P.PINS[1][0] - 0.15, P.PINS[1][1] + 1.25, 1.0), coll)       # the rear takedown pin's: a padlock
        for x, side in P.COVER_TOP_SCREWS:
            marks += fastener_top(body, x, side, coll)
        marks += F.date_clock(body, *F.side_ray(-27.6, 3.6, -1.0), coll)
        marks += F.qd_cup_marks(body, P.QD_XZ[0], P.QD_XZ[1], P.side_y(*P.QD_XZ) - P.QD_DEPTH, -1.0, coll, r=P.QD_R)   # the sling cup's rim and the pin hole in its floor
        for wx, wy in ((-5.6, 1.1), (-5.6, -1.1), (-16.4, 1.1), (-16.4, -1.1)):
            marks += F.witness(body, (wx, wy, -3.0), (0.0, 0.0, 1.0), coll)
        marks += F.parting_line(body, -29.6, -25.4, True, coll) + F.parting_line(body, -27.0, -17.0, False, coll)
        K.boolean(body, marks)
        # (the belt line is the moulding's own parting line: no groove of the bake source's is cut along the side)
    return tag(K.shade(body, 30.0, flats=True), 'Grip_Bone', mat='polymer')


def shear(obj):
    """The butt's rake (P.rake at the full weight) applied to a part built against the vertical rear face: toward the toe it moves forward."""
    for v in obj.data.vertices:
        v.co.x = P.rake(P.BUTT_X, v.co.z) - P.BUTT_X + v.co.x
    obj.data.update()
    return obj


def pad(coll, hp=False):
    """The butt pad: a rubber pad on a thin spacer, let on to the butt's face. Its edge is rounded, its rear face domed, and on
    the bake source it is ribbed across."""
    hw, (z0, z1) = P.PAD_HW, P.PAD_Z
    zc, hz = (z0 + z1) / 2, (z1 - z0) / 2
    xf, t, r, crown = P.BUTT_X - P.SEAT - P.SPACER_T, P.PAD_T, P.PAD_R, P.PAD_CROWN
    n = 4 * (12 if hp else 8)
    spec = [(xf, 0.0, 1.0), (xf - (t - r), 0.0, 1.0)]
    for deg in (30.0, 60.0, 90.0):                                       # the edge turns in a quarter circle
        a = math.radians(deg)
        spec.append((xf - (t - r) - r * math.sin(a), r * (1.0 - math.cos(a)), 1.0))
    for f in (0.72, 0.45, 0.18):                                         # then the rear face domes toward its middle
        spec.append((xf - t - crown * (1.0 - f * f), r, f))
    # the section is a rounded rectangle at the edge and turns oval toward the middle of the dome (a rectangle shrunk to a point
    # leaves four creases running to it: PLAYBOOK, Modelling 59)
    rings = [[(x, y, z) for y, z in K.section((hw - d) * f, zc - (hz - d) * f, zc + (hz - d) * f, n, 0.5, 2.0 + 4.0 * f ** 2.5, 2.0 + 4.0 * f ** 2.5)]
             for x, d, f in spec]
    obj = K.loft('Pad', rings, coll)
    sp = P.SPACER_INSET
    plate = K.round_poly([(-hw + sp, z0 + sp, 0.45), (hw - sp, z0 + sp, 0.45), (hw - sp, z1 - sp, 0.45), (-hw + sp, z1 - sp, 0.45)], seg(hp, 2, 8))
    K.boolean(obj, K.prism('spacer', plate, 'YZ', xf + 0.08, P.BUTT_X - P.SEAT, coll), 'UNION')
    K.cleanup(obj)
    shear(obj)                                                           # onto the raked rear face
    if hp:
        count = int((z1 - z0 - 1.8) / 0.55) + 1
        lines = [[(-hw + 0.55, z), (hw - 0.55, z)] for z in [z0 + 0.9 + 0.55 * i for i in range(count)]]
        K.cut_grooves(obj, K.grooves_on(obj, lines, REAR, coll, half_w=0.12, depth=0.10, facing=0.8), coll)
    return tag(K.shade(obj, 40.0), 'Grip_Bone', mat='polymer')


def _along(chain, s):
    """The point s along the polyline chain [(y, z)] from its start (None if it is shorter), and the index after which it falls."""
    run = 0.0
    for i, (p, q) in enumerate(zip(chain, chain[1:])):
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        if run + d > s + 1.0e-6:
            f = (s - run) / d
            return (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f), i
        run += d
    return None, None


def cheek_pad(coll, hp=False):
    """The cheek pad: a rubber saddle over the comb and down both shoulders, from 2 cm ahead of the butt's rear face to the cover's shut line:
    P.CP_ZL up the left (under the belt line), P.CP_DROP_R down the right; P.CP_H proud, a border step at its edge (its wall rises to
    CP_H - 0.08 and a chamfer takes it the rest of the way) and, where it lies over the shoulders and the comb, deep cross ribs (a groove
    every CP_RIB_PITCH, 0.11 deep, 45 degree walls: cut into the bake source only, so the game mesh is a clean saddle that the normal map ribs;
    as geometry they were 130 thin UV islands that cost a third of the sheet). Below the shoulder the field is smooth. One closed solid: it skins the shell's own section, so it follows the
    shell's rounded creases, and a skin 0.07 under the shell's surface closes it (it sits in the shell, as the butt pad's spacer does)."""
    side = K.round_poly(P.SHELL_OUTLINE, P.SHELL_ARC[1 if hp else 0])
    k = P.SECTION_K[1 if hp else 0]
    x0, x1 = P.CP_X
    step, dh, inner = P.CP_STEP, 0.08, 0.07
    h_edge = P.CP_H - dh
    gw = P.CP_RIB_W / 2.0
    grooves = {}                                           # station: how deep (0..1) the ribbing is there
    xg = x0 + 0.55
    while hp and xg < x1 - 0.55:                           # the ribs are in the bake source only (a hole 0.11 deep: the bake carries it; as game geometry it would be 108 thin UV islands)
        for dx, g in ((-gw, 0.0), (-0.02, 1.0), (0.02, 1.0), (gw, 0.0)):
            grooves[round(xg + dx, 4)] = g
        xg += P.CP_RIB_PITCH
    marks = {x0, x0 + step, x1 - step, x1} | {m for m in P.SECTION_KNOTS if x0 + 0.05 < m < x1 - 0.05} | set(grooves)
    xs = sorted(marks)
    a0 = 4 * k + 11                                        # the ring index where the shoulder's crease begins: the ribbing starts there
    L = 6 * k + 13                                         # points in half a ring (and the top's index); the ring has 2 L
    core = {4 * k + 6, a0, L, 2 * L - a0, 2 * L - 4 * k - 6}      # the ring indices whose skin points are kept under the shell
    outers, inners = [], []
    for x in xs:
        lo, hi = K.span(side, x)
        pts = P.ring(x, lo, hi, k)
        n = len(pts)
        top = n // 2
        assert top == L, (top, L)
        zr = hi - P.CP_DROP_R
        i = next(i for i in range(1, top) if pts[i][1] > P.CP_ZL)
        cut = tuple(pts[i - 1][c] + (pts[i][c] - pts[i - 1][c]) * (P.CP_ZL - pts[i - 1][1]) / (pts[i][1] - pts[i - 1][1]) for c in (0, 1))
        j = next(j for j in range(top + 1, n) if pts[j][1] < zr)
        cutr = tuple(pts[j - 1][c] + (pts[j][c] - pts[j - 1][c]) * (zr - pts[j - 1][1]) / (pts[j][1] - pts[j - 1][1]) for c in (0, 1))
        drop = set(range(4 * k + 7, a0)) | set(range(n - a0 + 1, n - 4 * k - 6))       # the cover's collinear points on the upper facet
        keep = [q for q in range(i, j) if q not in drop]
        chain = [cut] + [tuple(pts[q]) for q in keep] + [cutr]
        wts = [0.0] + [1.0 if a0 <= q <= n - a0 else 0.0 for q in keep] + [0.0]
        ids = [-1] + keep + [-1]
        for end in (False, True):                          # a point `step` in from each lateral edge: where the chamfer ends
            c = chain[::-1] if end else chain
            w = wts[::-1] if end else wts
            d = ids[::-1] if end else ids
            at, idx = _along(c, step)
            if at is not None:
                c.insert(idx + 1, at)
                w.insert(idx + 1, 0.0)
                d.insert(idx + 1, -1)
            chain, wts, ids = (c[::-1], w[::-1], d[::-1]) if end else (c, w, d)
        m = len(chain)
        run = [0.0]
        for p, q in zip(chain, chain[1:]):
            run.append(run[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
        norms = []
        for p, q in zip(chain, chain[1:]):
            d = math.hypot(q[0] - p[0], q[1] - p[1])
            norms.append(((q[1] - p[1]) / d, -(q[0] - p[0]) / d))
        miter = []
        for q in range(m):
            if q == 0:
                miter.append(norms[0])
            elif q == m - 1:
                miter.append(norms[-1])
            else:
                a, b = norms[q - 1], norms[q]
                f = 1.0 / max(0.35, 1.0 + a[0] * b[0] + a[1] * b[1])
                miter.append(((a[0] + b[0]) * f, (a[1] + b[1]) * f))
        e = min(1.0, (x - x0) / step, (x1 - x) / step)
        o, ii = [], []
        e = min(1.0, (x - x0) / step, (x1 - x) / step)
        for q in range(m):
            edge = min(1.0, run[q] / step, (run[-1] - run[q]) / step, e)
            h = h_edge + dh * edge - P.CP_RIB_D * wts[q] * grooves.get(round(x, 4), 0.0) * (1.0 if edge >= 1.0 else 0.0)
            y, z = chain[q]
            u, v = miter[q]
            o.append((P.rake(x, z + v * h), y + u * h, z + v * h))
            if ids[q] in core or q in (0, m - 1):       # the skin under the shell is coarse: its corners only
                ii.append((P.rake(x, z - v * inner), y - u * inner, z - v * inner))
        outers.append(o)
        inners.append(ii)
    bm = bmesh.new()
    O = [[bm.verts.new(p) for p in r] for r in outers]
    I = [[bm.verts.new(p) for p in r] for r in inners]
    m, mi = len(O[0]), len(I[0])
    for r in range(len(O) - 1):
        for q in range(m - 1):
            bm.faces.new((O[r][q], O[r][q + 1], O[r + 1][q + 1], O[r + 1][q]))
        for q in range(mi - 1):
            bm.faces.new((I[r][q], I[r + 1][q], I[r + 1][q + 1], I[r][q + 1]))
        bm.faces.new((O[r][0], O[r + 1][0], I[r + 1][0], I[r][0]))
        bm.faces.new((O[r][m - 1], I[r][mi - 1], I[r + 1][mi - 1], O[r + 1][m - 1]))
    caps = []
    for r in (0, len(O) - 1):
        caps.append(bm.faces.new(O[r] + I[r][::-1]))
    K.face_out(bm)
    bmesh.ops.triangulate(bm, faces=[f for f in caps if f.is_valid], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    obj = K.obj_from_bm('CheekPad', bm, coll)
    K.cleanup(obj)
    return tag(K.shade(obj, 46.0), 'Grip_Bone', mat='rubber')            # (the ribs' walls are 45 degrees: smooth, so the ribbed field is one UV island, not a hundred)


def rail(coll, hp=False):
    """The rail along the shell's top: one section run along the gun, its ends chamfered, slotted across between the two sights; numbered
    on every other land and held by two cross screws (the bake source)."""
    full = list(P.RAIL_HALF) + [(-p[0], p[1]) for p in reversed(P.RAIL_HALF)]
    body = K.prism('Rail', full, 'YZ', P.RAIL_X[0], P.RAIL_X[1], coll)
    K.bevel(body, lambda e, m, d: (abs(m.x - P.RAIL_X[0]) < 1.0e-4 or abs(m.x - P.RAIL_X[1]) < 1.0e-4) and abs(d.x) < 0.01 and m.z > P.TOP_Z + 0.5, 0.14, seg(hp, 1, 3))
    cutters = []
    for i in range(P.RAIL_SLOTS):
        x = P.RAIL_SLOT_X0 + P.RAIL_PITCH * i
        cutters.append(K.box('cut', (x - P.RAIL_SLOT_W / 2, -1.5, P.RAIL_Z - P.RAIL_SLOT_D), (x + P.RAIL_SLOT_W / 2, 1.5, P.RAIL_Z + 0.5), coll))
    K.boolean(body, cutters)
    K.cleanup(body)
    if hp:
        cuts = []
        for x in (P.RAIL_SLOT_X0 - 1.0, P.RAIL_SLOT_X0 + P.RAIL_PITCH * (P.RAIL_SLOTS - 1) + 1.0):      # the screws that hold it down
            cuts += F.screw_cuts((x, 0.0, P.RAIL_Z), (0.0, 0.0, 1.0), 0.22, coll, slot_deg=20.0)
        for x in (P.RAIL_SLOT_X0 + 0.5 + P.RAIL_PITCH * 5, P.RAIL_SLOT_X0 + 0.5 + P.RAIL_PITCH * 17):    # and two cross screws through its sides
            for side in (1.0, -1.0):
                cuts += F.screw_cuts((x, side * P.RAIL_HW, P.TOP_Z + 0.52), (0.0, side, 0.0), 0.085, coll, slot_deg=0.0, depth=0.03)
        # the slot numbers: on the land after every fourth slot, reading across the rail from behind, painted white; 0.33 cm tall (pass 3b: they were 0.19)
        for k in range(4, P.RAIL_SLOTS, 4):
            x = P.RAIL_SLOT_X0 + P.RAIL_PITCH * (k - 1) + 0.5
            cuts.append(K.text_solid('cut', str(k), 0.47, (x - 0.165, 0.0, P.RAIL_Z), (0.0, -1.0, 0.0), (1.0, 0.0, 0.0), 0.03, coll))
        K.boolean(body, cuts)
    return tag(shade(body, hp), 'Grip_Bone', mat='alloy')


# ------------------------------------------------------------------------------------------------------- grip and guard
def grip_loft(coll, hp):
    """The pistol grip: slices across it, from the toe up into the shell. Each is an oval from the back strap (round) to the front
    strap (flatter), as wide as the palm swell table says; the side outline gives where the two straps are at that height."""
    side = K.round_poly(P.GRIP_OUTLINE, seg(hp, 2, 10))
    zx = [(z, x) for x, z in side]                                  # K.span reads "where does the outline cross the line z = a"
    hw = K.curve(P.GRIP_HW)
    lo_z, top = min(z for z, _x in zx) + 0.10, P.GRIP_TOP_Z + P.GRIP_SINK
    marks = [z for z, _x in zx] + [p[0] for p in P.GRIP_HW]
    n = 4 * P.GRIP_M[1 if hp else 0]
    rings = []
    for z in K.stations(marks, lo_z, top, 0.45 if hp else 0.95, 0.04 if hp else 0.25):
        if abs(z) < 0.03:
            z += 0.04                                               # the check "guard: room for the whole hand" reads the grip at z = 0
        xb, xf = K.span(zx, min(z, P.GRIP_TOP_Z - 0.01))
        rings.append([(b, a, z) for a, b in K.section(hw(z), xb, xf, n, P.GRIP_WIDEST, P.GRIP_FRONT_EXP, P.GRIP_BACK_EXP)])
    return K.loft('Grip', rings, coll)


def guard_loft(coll, hp):
    """The guard's strap, a moulded blade: a rounded rectangle carried along a centre line from inside the grip's toe, forward under the
    hand, round one continuous elbow and up into the handguard. Wider and thicker where it grows into them: each root has a fillet (a
    quarter circle of radius P.GUARD_ROOT_R in the thickness and in the width), with a ring every few degrees of that quarter circle."""
    path = [Vector(p) for p in K.round_poly(P.GUARD_PATH, seg(hp, 3, 12))]
    along = [0.0]
    for a, b in zip(path[:-1], path[1:]):
        along.append(along[-1] + (b - a).length)
    total = along[-1]
    big, hh0 = P.GUARD_ROOT_R, P.GUARD_T / 2
    s_toe = P.GUARD_TOE_XC - P.GUARD_PATH[0][0]                     # the toe fillet's circle: where its centre is along the line
    s_hg = total - (P.GUARD_PATH[2][1] - P.HG_Z) / math.cos(math.radians(P.RISER_DEG))      # where the line meets the handguard's underside

    def rise(u):                                                    # a concave fillet's height u from where it is tangent: 0 at u = 0, R at u = R
        u = max(0.0, min(big, u))
        return big - math.sqrt(max(0.0, big * big - u * u))
    x0 = P.GUARD_PATH[0][0]
    top0 = P.GUARD_PATH[0][1] + hh0

    bigt = P.GUARD_TOE_R

    def rise_toe(s_):                                               # the toe's fillet: a quarter circle (radius GUARD_TOE_R), but never above the grip's own face
        x = x0 + s_
        u = max(0.0, min(bigt, s_toe - s_))
        return max(0.0, min(bigt - math.sqrt(max(0.0, bigt * bigt - u * u)), P.grip_front_z(x) - 0.03 - top0))
    # stations: the line's own corners (the elbow's arc), every `gap` along the straights, a ring every few degrees round each fillet,
    # and a few along the grip's face under the toe's fillet
    step = 7.5 if hp else 15.0
    angles = [math.radians(step * i) for i in range(int(90.0 / step) + 1)]
    marks = list(along) + [s_toe - bigt * math.sin(t) for t in angles] + [s_hg - big + big * math.sin(t) for t in angles]
    marks += [s_toe - bigt - 0.1, s_toe - bigt - 0.2, s_toe - bigt - 0.35]
    gap = 0.35 if hp else 1.2
    stations = []
    for s_ in sorted(m for m in marks if 0.0 <= m <= total):
        if not stations or s_ - stations[-1] > 0.02:
            stations.append(s_)
    out = [stations[0]]
    for s_ in stations[1:]:
        n = max(1, int(math.ceil((s_ - out[-1]) / gap - 1.0e-9)))
        out += [out[-1] + (s_ - out[-1]) * (i + 1) / n for i in range(n)]

    def at(s_):                                                     # the point, and the direction of travel, s_ along the line
        i = min(max(k for k in range(len(along) - 1) if along[k] <= s_ + 1.0e-9), len(path) - 2)
        d = (path[i + 1] - path[i]).normalized()
        point = path[i] + d * (s_ - along[i])
        if abs(s_ - along[i]) < 1.0e-6 and i > 0:                   # on a corner of the line: halfway between the two directions
            d = (d + (path[i] - path[i - 1]).normalized()).normalized()
        return point, d
    rings = []
    for s_ in out:
        c, t = at(s_)
        r_toe, r_hg = rise_toe(s_) * P.GUARD_TOE_FILLET, rise(s_ - (s_hg - big))   # pass 4: a thickness fillet at the toe again, a quarter circle that narrows as it climbs (a full-width one stood out of the grip's rounded face like a plate)
        u = min(1.0, max(0.0, 1.0 - (s_ - P.GUARD_TOE_FACE_S) / P.GUARD_TOE_FLARE_L))      # the blade only widens, in plan, as it runs into the grip
        toe_w = u * u * (3.0 - 2.0 * u)
        t = t.lerp(Vector((0.0, 1.0)), min(1.0, r_hg / big) if t.y > 0.5 else 0.0).normalized()    # up the handguard's root the rings turn level: flush with its underside
        normal = Vector((-t.y, t.x))                                # to the left of the travel: up along the bottom, back up the riser
        flare = max(toe_w, min(1.0, r_hg / big))
        half = P.GUARD_HW + (P.GUARD_HW_ROOT - P.GUARD_HW) * flare - P.GUARD_TOE_NARROW * min(1.0, r_toe / bigt)
        edge = P.GUARD_EDGE + (P.GUARD_ROOT_EDGE - P.GUARD_EDGE) * min(1.0, r_hg / big)       # the edges round off where it grows into the handguard; at the toe they stay tight, so the fillet meets the grip's face as a wide web, with no notch at its corners
        edge = max(edge, P.GUARD_EDGE + 0.30 * min(1.0, r_toe / bigt))
        rings.append([(c.x + normal.x * b, a, c.y + normal.y * b)
                      for a, b in S.rrect(half, -(hh0 + r_hg), hh0 + r_hg + r_toe, edge, P.GUARD_K[1 if hp else 0])])
    return K.loft('guard', rings, coll)


# ---- the grip's own surface, analytically (for the overmoulded insert: its border groove is swept along it, and the faces inside it are told
#      from the rest by where they are). The grip is a loft of slices, each a super-ellipse (grip_loft); phi runs from the back strap's middle
#      (0) round the left (90 degrees) to the front strap's middle (180); t is cm down the front strap's line, as P.grip_pt reads it
_GC = {}


def _grip_tables():
    if not _GC:
        side = K.round_poly(P.GRIP_OUTLINE, 10)
        zx = [(z, x) for x, z in side]
        hw = K.curve(P.GRIP_HW)
        lo_z, hi_z = min(z for z, _x in zx) + 0.001, P.GRIP_TOP_Z - 0.01
        zs = np.linspace(lo_z, hi_z, 800)
        span = [K.span(zx, z) for z in zs]
        _GC.update(zs=zs, xb=np.array([a for a, _b in span]), xf=np.array([b for _a, b in span]), hw=np.array([hw(z) for z in zs]))
    return _GC


def grip_at(z, phi):
    """The grip's surface at height z, angle phi (radians from the back strap's middle, +: toward the left)."""
    g = _grip_tables()
    xb, xf, hw = (float(np.interp(z, g['zs'], g[k])) for k in ('xb', 'xf', 'hw'))
    mid = xb + P.GRIP_WIDEST * (xf - xb)
    tau = phi - math.pi / 2
    c, s_ = math.cos(tau), math.sin(tau)
    e = P.GRIP_FRONT_EXP if s_ > 0.0 else P.GRIP_BACK_EXP
    half = (xf - mid) if s_ > 0.0 else (mid - xb)
    return Vector((mid + half * math.copysign(abs(s_) ** (2.0 / e), s_), hw * math.copysign(abs(c) ** (2.0 / e), c), z)), Vector((mid, 0.0, z))


def grip_tp(t, phi):
    """(point, outward normal) of the grip's surface t cm down the front strap and at angle phi."""
    a = math.radians(P.GRIP_RAKE_DEG)
    ft = P.GRIP_FRONT_TOP
    z = ft[1] - math.cos(a) * t
    for _ in range(5):
        p, _c = grip_at(z, phi)
        z += math.cos(a) * (-((p.x - ft[0]) * math.sin(a) + (p.z - ft[1]) * math.cos(a)) - t)
    p, centre = grip_at(z, phi)
    h = 0.02
    dz = grip_at(z + h, phi)[0] - grip_at(z - h, phi)[0]
    dp = grip_at(z, phi + h)[0] - grip_at(z, phi - h)[0]
    n = dp.cross(dz).normalized()
    if n.dot(p - centre) < 0.0:
        n = -n
    return p, n


def grip_inverse(c):
    """For points c (n, 3) near the grip's surface: (t, phi, off), off how far each is from it (about, cm)."""
    g = _grip_tables()
    x, y, z = c[:, 0], c[:, 1], c[:, 2]
    xb, xf, hw = (np.interp(z, g['zs'], g[k]) for k in ('xb', 'xf', 'hw'))
    mid = xb + P.GRIP_WIDEST * (xf - xb)
    front = x > mid
    e = np.where(front, P.GRIP_FRONT_EXP, P.GRIP_BACK_EXP)
    half = np.where(front, xf - mid, mid - xb)
    cr = np.abs(y) / np.maximum(hw, 1.0e-6)
    sr = np.abs(x - mid) / np.maximum(half, 1.0e-6)
    k = (cr ** e + sr ** e) ** (1.0 / e)
    cc = np.sign(y) * cr ** (e / 2.0)
    ss = np.where(front, 1.0, -1.0) * sr ** (e / 2.0)
    phi = (np.arctan2(ss, cc) + math.pi / 2 + math.pi) % (2 * math.pi) - math.pi
    a = math.radians(P.GRIP_RAKE_DEG)
    t = -((x - P.GRIP_FRONT_TOP[0]) * math.sin(a) + (z - P.GRIP_FRONT_TOP[1]) * math.cos(a))
    return t, phi, np.abs(k - 1.0) * 1.7


def insert_outline(grow=0.0):
    """The overmoulded insert's outline in (t, w): a rounded rectangle, w = P.INS_KW cm per radian round the section from the back strap's middle."""
    wmax = math.radians(P.INS_PHI) * P.INS_KW
    t0, t1 = P.INS_T
    pts = K.round_poly([(t0, -wmax, P.INS_R), (t1, -wmax, P.INS_R), (t1, wmax, P.INS_R), (t0, wmax, P.INS_R)], 8)
    return inset_poly(pts, -grow) if grow else pts


def insert_groove(coll):
    """The sunk border all round the insert: one closed ring of flat-bottomed section swept along the outline on the grip's surface,
    P.INS_GW wide, P.INS_GD deep. A cutter for K.cut_grooves."""
    path = densify(insert_outline(), 0.10)
    pts = [grip_tp(t, w / P.INS_KW) for t, w in path]
    bm = bmesh.new()
    rings = []
    count = len(pts)
    for i, (p, n) in enumerate(pts):
        tang = (pts[(i + 1) % count][0] - pts[i - 1][0]).normalized()
        across = n.cross(tang).normalized() * (P.INS_GW / 2.0)
        lift, sink = n * 0.12, n * P.INS_GD
        rings.append([bm.verts.new(q) for q in (p - across + lift, p + across + lift, p + across - sink, p - across - sink)])
    for i in range(count):
        a, b = rings[i], rings[(i + 1) % count]
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    K.face_out(bm)
    return K.obj_from_bm('cut', bm, coll)


def grip(coll, hp=False):
    """The pistol grip and the guard for the whole hand: a lofted grip with a palm swell, textured on both sides, and a strap of
    oval section that leaves its toe, runs forward under the hand and climbs to the handguard."""
    obj = grip_loft(coll, hp)
    if hp:
        area = K.round_poly(P.GRIP_CHECK, 6)
        sets = []
        for frame in (LEFT, RIGHT):
            for deg in (45.0, -45.0):
                sets.append(K.grooves_on(obj, K.hatch(area, deg, P.GRIP_CHECK_PITCH), frame, coll, half_w=0.05, depth=0.045))
        K.cut_grooves(obj, insert_groove(coll), coll)                                   # the coarse cut first: the insert's border
        for cutter in sets:                                                             # one cut per line direction: they cross
            K.cut_grooves(obj, cutter, coll)
    K.boolean(obj, guard_loft(coll, hp), 'UNION')
    K.cleanup(obj, dissolve_deg=0.0 if hp else 0.5, keep=grip_seam())
    return tag(K.shade(obj, 40.0), 'Grip_Bone', mat='polymer')


# ---------------------------------------------------------------------------------------------------------- small controls
def trigger(coll, hp=False):
    """A curved blade; its head turns inside the shell."""
    hw = P.TRIG_HW
    pts = K.round_poly([(6.65, 5.60), (6.65, 4.10), (6.45, 3.30, 2.0), (6.85, 2.30, 0.10), (6.55, 2.18, 0.12), (6.05, 3.20, 2.2),
                        (5.95, 4.10), (5.95, 5.60)], seg(hp, 4, 12))
    obj = K.prism('Trigger', pts, 'XZ', -hw, hw, coll)
    K.bevel(obj, lambda e, m, d: abs(abs(m.y) - hw) < 1.0e-4 and abs(d.y) < 0.01 and m.z < 3.9, 0.07, seg(hp, 1, 4))
    if hp:
        # pass 4: vertical serrations on the finger face: fine grooves across the blade, every 0.14 down its curve
        lines = [[(-hw + 0.06, z), (hw - 0.06, z)] for z in [2.62 + 0.14 * i for i in range(11)]]
        K.cut_grooves(obj, K.grooves_on(obj, lines, Matrix.Translation((5.95, 0.0, 0.0)) @ REAR, coll, half_w=0.045, depth=0.04, facing=0.5), coll)
    return tag(K.shade(obj), 'Trigger_Bone')


def safety(coll, hp=False):
    """The safety: a button through the shell, bound standing out on the left ("safe")."""
    (sx, sz), top = P.SAFE_XZ, P.SAFE_TOP                  # the face of the boss round it, which stands on each side
    y0, y1 = -top - 0.06, top + P.SAFE_PROUD
    obj = K.cylinder('Safety', (sx, y0, sz), (sx, y1, sz), P.SAFE_R, seg(hp, 8, 32), coll)
    K.bevel(obj, lambda e, m, d: (abs(m.y - y0) < 1.0e-4 or abs(m.y - y1) < 1.0e-4) and abs(d.y) < 0.01, 0.06, seg(hp, 1, 3))
    if hp:
        # a ring round each end's face: the mark the thumb finds
        left = K.tube('cut', (sx, y1 - 0.035, sz), (sx, y1 + 0.3, sz), P.SAFE_R - 0.12, P.SAFE_R - 0.17, 32, coll)
        right = K.tube('cut', (sx, y0 - 0.3, sz), (sx, y0 + 0.035, sz), P.SAFE_R - 0.12, P.SAFE_R - 0.17, 32, coll)
        right['mark'] = [sx, y0, sz, 0.0, -1.0, 0.0, 1.0]            # a painted ring: red, on the end that stands out at "fire" (K.keep_mark; ink 1)
        cuts = [left, right]
        K.boolean(obj, cuts)
    return tag(K.shade(obj), 'Safety_Bone', mat='dark')


def mag_release(coll, hp=False):
    """The magazine release: a paddle hanging behind the well; its head is in a pocket of the butt's underside."""
    hw = P.REL_HW
    obj = K.prism('MagRelease', K.round_poly(P.REL_OUTLINE, seg(hp, 2, 6)), 'XZ', -hw, hw, coll)
    K.bevel(obj, lambda e, m, d: abs(abs(m.y) - hw) < 1.0e-4 and abs(d.y) < 0.01 and m.z < 1.70, 0.10, seg(hp, 1, 3))
    if hp:
        x_back = P.REL_OUTLINE[0][0]
        lines = [[(-hw + 0.15, z), (hw - 0.15, z)] for z in [1.05 + 0.13 * i for i in range(5)]]
        K.cut_grooves(obj, K.grooves_on(obj, lines, Matrix.Translation((x_back, 0.0, 0.0)) @ REAR, coll, half_w=0.04, depth=0.04, facing=0.8), coll)
    return tag(shade(obj, hp), 'MagRelease_Bone', mat='dark')


def charging_handle(coll, hp=False):
    """The charging handle (pass 4): a lug that runs in the slot on the left of the handguard, a clevis with a visible cross pin (the knob folds
    on it), and a knob standing out of it: a neck and a mushroom head, knurled and ringed on the bake source, with a detent dimple in its
    neck and a slotted pin in its face."""
    (z0, z1), seat = P.CH_Z, P.CH_SEAT_Y
    x0, x1 = P.CH_LUG_X
    lug = K.box('ChargingHandle', (x0, P.CH_SLOT_FLOOR + 0.05, z0), (x1, seat + 0.14, z1), coll)
    (kx, kz), (rn, rh), (y0, y1) = P.CH_KNOB, P.CH_KNOB_R, P.CH_KNOB_Y
    knob = K.lathe('knob', [(y0 - 0.10, 0.0), (y0 - 0.10, rn), (y1 - 0.75, rn), (y1 - 0.60, rh), (y1 - 0.10, rh), (y1, rh - 0.10), (y1, 0.0)],
                   (kx, 0.0, kz), (0.0, 1.0, 0.0), seg(hp, 7, 32), coll)
    K.boolean(lug, knob, 'UNION')
    clevis = K.box('clevis', (kx - 0.42, y0 - 0.10, kz - 0.40), (kx + 0.42, y0 + 0.50, kz + 0.40), coll)
    K.bevel(clevis, lambda e, m, d: m.y > y0 + 0.45, 0.07, seg(hp, 1, 3))
    K.boolean(lug, clevis, 'UNION')
    K.boolean(lug, K.cylinder('pin', (kx - 0.50, y0 + 0.22, kz), (kx + 0.50, y0 + 0.22, kz), 0.13, seg(hp, 4, 20), coll), 'UNION')       # the fold's cross pin
    K.cleanup(lug)
    if hp:
        cuts = [K.prism_m('cut', rect(y1 - 0.62, y1 - 0.16, -0.045, 0.045),
                          Matrix.Translation((kx, 0.0, kz)) @ Matrix.Rotation(math.radians(15.0 * i), 4, 'Y')
                          @ Matrix(((0.0, 0.0, 1.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))),
                          rh - 0.045, rh + 0.3, coll) for i in range(24)]                          # the knob's knurl: cuts along it, all the way round
        for yr in (y1 - 0.66, y1 - 0.12):                                                       # and a ring groove at each end of it
            cuts.append(K.tube('cut', (kx, yr, kz), (kx, yr + 0.05, kz), rh + 0.2, rh - 0.045, 40, coll))
        cuts += F.screw_cuts((kx, y1, kz), (0.0, 1.0, 0.0), 0.24, coll, slot_deg=30.0)              # the pivot of its fold: a slotted pin in its face
        cuts += F.pin_cuts((kx + 0.50, y0 + 0.22, kz), (1.0, 0.0, 0.0), 0.10, coll)                  # the cross pin's two ends
        cuts += F.pin_cuts((kx - 0.50, y0 + 0.22, kz), (-1.0, 0.0, 0.0), 0.10, coll)
        dim = K.cylinder('cut', (kx, (y0 + y1) / 2 - 0.1, kz + rn + 0.12), (kx, (y0 + y1) / 2 - 0.1, kz + rn - 0.06), 0.16, 16, coll, r1=0.02)
        cuts.append(dim)                                                                        # the spring detent's dimple in the neck
        K.boolean(lug, cuts)
    return tag(shade(lug, hp), 'ChargingHandle_Bone', mat='dark')


def bolt(coll, hp=False):
    """The bolt carrier, with the bolt standing out of its front: what shows in the ejection port."""
    (x0, x1), r = P.CARRIER_X, P.CARRIER_R
    obj = K.lathe('Bolt', [(x0, 0.0), (x0, r - 0.10), (x0 + 0.10, r), (x1 - 2.45, r), (x1 - 2.35, r - 0.14), (x1 - 1.10, r - 0.14), (x1 - 1.00, r),    # pass 6: a milled step
                           (x1 - 0.15, r), (x1, r - 0.15), (x1, P.BOLT_R),
                           (P.BOLT_FACE_X - 0.05, P.BOLT_R), (P.BOLT_FACE_X, P.BOLT_R - 0.05), (P.BOLT_FACE_X, 0.0)],
                  BORE, AXIS, seg(hp, 12, 48), coll, start=DOWN)
    if hp:
        # fine cuts across the carrier's right side, seen in the port
        lines = [[(x, P.BZ - 0.42), (x, P.BZ + 0.42)] for x in [P.PORT_X[0] + 0.5 + 0.22 * i for i in range(8)]]
        K.cut_grooves(obj, K.grooves_on(obj, lines, RIGHT, coll, half_w=0.05, depth=0.05, facing=0.6), coll)
    # pass 6: the cam slot, a slanted stadium cut into the carrier's right side (game and bake model), and the extractor on the bolt head's right
    p0, p1, hw_ = Vector((-12.50, P.BZ - 0.36)), Vector((-10.55, P.BZ + 0.36)), 0.17
    d = (p1 - p0).normalized()
    nrm = Vector((-d.y, d.x)) * hw_
    quad = [(p0 - nrm + 0.0 * d), (p1 - nrm), (p1 + nrm), (p0 + nrm)]
    K.boolean(obj, K.prism('cut', K.round_poly([(q.x, q.y, 0.16) for q in quad], seg(hp, 1, 4)), 'XZ', -(r + 0.3), -(r - 0.26), coll))
    ex = [K.box('claw', (P.BOLT_FACE_X - 1.75, -(P.BOLT_R + 0.20), P.BZ - 0.20), (P.BOLT_FACE_X + 0.15, -(P.BOLT_R - 0.08), P.BZ + 0.20), coll),
          K.box('lip', (P.BOLT_FACE_X - 0.05, -(P.BOLT_R + 0.20), P.BZ - 0.20), (P.BOLT_FACE_X + 0.15, -(P.BOLT_R - 0.18), P.BZ + 0.20), coll)]
    K.boolean(obj, ex, 'UNION')
    K.cleanup(obj)
    return tag(K.shade(obj), 'Bolt_Bone', mat='bright')


# --------------------------------------------------------------------------------------------------------------- hardware
def hardware(coll, hp=False):
    """Steel hardware that stays where it is (every piece one closed solid in one part): the two takedown pins (a domed head with a wire
    clip on the left, the pin's end with a detent on the right), the bolt release lever behind the well on the left, and the front sling
    loop under the hand stop. (The rear sling slot is the one through the butt.)"""
    s = seg
    sg = lambda lo, hi: seg(hp, lo, hi)
    parts = []
    for x, z in P.PINS:                                     # the takedown pins: the head and its clip on the left, the end on the right
        parts += F.takedown_pin(x, z, P.boss_top(x, z, P.BOSS_PIN, P.BOSS_PIN_H) + P.SEAT, coll, sg)
    # the bolt release lever: a paddle on the left behind the well, pivoting on a pin at its top
    pts = [(P.LEVER_X[0], P.LEVER_Z[0]), (P.LEVER_X[1], P.LEVER_Z[0]), (P.LEVER_X[1], P.LEVER_Z[1]), (P.LEVER_X[0], P.LEVER_Z[1])]
    lever = K.round_poly([(a, b, 0.22 if b == P.LEVER_Z[0] else 0.40) for a, b in pts], s(hp, 2, 6))
    sy = max(P.side_y(px, pz) for px, pz in ((P.LEVER_X[0], P.LEVER_Z[0]), (P.LEVER_X[1], P.LEVER_Z[0]), (P.LEVER_X[0], P.LEVER_Z[1]), (P.LEVER_X[1], P.LEVER_Z[1])))
    arm = K.prism('lever', lever, 'XZ', sy - 0.06, sy + P.LEVER_H, coll)
    K.bevel(arm, lambda e, m, d: abs(m.y - (sy + P.LEVER_H)) < 1.0e-4, 0.07, s(hp, 1, 3))
    parts.append(arm)
    lx, lz = (P.LEVER_X[0] + P.LEVER_X[1]) / 2, P.LEVER_Z[1] - 0.45
    lpin = K.cylinder('lpin', (lx, sy + P.LEVER_H - 0.02, lz), (lx, sy + P.LEVER_H + 0.10, lz), 0.17, s(hp, 8, 24), coll)
    if not hp:
        parts.append(lpin)
    # pass 4: the trigger's pivot pin, a small domed head standing out of each side of the shell
    for side in (1.0, -1.0):
        ty = P.side_y(P.TRIG_PIVOT[0], P.TRIG_PIVOT[1])
        parts.append(F.pin_head((P.TRIG_PIVOT[0], side * (ty + P.SEAT - 0.01), P.TRIG_PIVOT[1]), (0.0, side, 0.0), coll, s(hp, 7, 28), name='tpin'))
    # pass 4: a buffer at the charging slot's front end (the handle rests 0.08 behind it): a block in the slot, steel
    parts.append(K.box('stop', (P.CH_SLOT_X[1] - 0.24, P.CH_SLOT_FLOOR + 0.0, P.CH_Z[0] - 0.02), (P.CH_SLOT_X[1] - 0.02, P.CH_SLOT_FLOOR + 0.55, P.CH_Z[1] + 0.02), coll))
    # the front sling loop: a tab hung under the hand stop, with a hole across the gun
    parts.append(F.sling_loop(P.LOOP_X[0], P.LOOP_X[1], P.LOOP_Z[0], P.LOOP_Z[1], coll, sg))
    # the data plate: steel, sunk in the shell's left side (a recess of the shell's own, F.plate_recess in shell()), two domed rivets, the serial engraved
    plate, rivets, face = F.data_plate(P.PLATE_X[0], P.PLATE_X[1], P.PLATE_Z[0], P.PLATE_Z[1], P.side_y(sum(P.PLATE_X) / 2, P.PLATE_Z[0]) - P.PLATE_SINK,
                                       coll, sg, t=P.PLATE_T)
    parts.append(plate)
    # on the bake source the rivets are joined AFTER the cuts: joined before, the cut dropped both domes (they sit 0.01 into the
    # plate), the bake's rays found nothing over the game mesh's rivets and they took the base steel with a flat normal. The game mesh is as it was
    obj = K.join('Hardware', parts + ([] if hp else rivets), coll)
    if hp:
        cuts = [c for x, z in P.PINS for c in F.takedown_pin_cuts(x, z, P.boss_top(x, z, P.BOSS_PIN, P.BOSS_PIN_H) + P.SEAT, coll)]
        cuts.append(F.plate_text(face, P.MARK_SERIAL, coll))
        K.boolean(obj, cuts)
        # like the rivets: the lever's pin sits 0.02 into the lever, and the cuts dropped it from the bake source, so that 54 game
        # faces found no detail (id 0, no surface kind). It is cut on its own (the slot in its end) and joined after
        K.boolean(lpin, F.screw_cuts((lx, sy + P.LEVER_H + 0.10, lz), (0.0, 1.0, 0.0), 0.12, coll, slot_deg=15.0))
        obj = K.join('Hardware', [obj, lpin] + rivets, coll)
    return tag(shade(obj, hp), 'Grip_Bone')


# ----------------------------------------------------------------------------------------------------------------- barrel
def barrel(coll, hp=False):
    """What shows of the barrel: the nut that holds it in the handguard's nose, the gas block's ring with its two-position regulator knob
    standing on it, the barrel (tapered, then turned down in two steps) and the crush washer behind the flash hider."""
    (n0, n1), x1 = P.NUT_X, P.HIDER_X[0] - P.SEAT
    r, rf, rn = P.BARREL_R, P.BARREL_FRONT_R, P.NUT_R
    g0, g1 = P.GAS_X
    tx0, tr0, tx1, tr1 = P.BARREL_TAPER
    w0 = x1 - 0.44 - P.WASHER_W
    obj = K.lathe('Barrel', [(n0, 0.0), (n0, rn), (n1 - 0.25, rn), (n1, rn - 0.25), (n1, r), (n1 + 0.12, r), (n1 + 0.12, 1.07), (n1 + 0.55, 1.07), (n1 + 0.70, r), (g0 - 0.02, r)]
                  + BR.gas_ring(g0, g1, P.GAS_R) + [(g1 + 0.02, tr0), (tx1, tr1), (P.BARREL_STEP_X, tr1),
                             (P.BARREL_STEP_X + 0.15, rf), (P.BARREL_STEP2_X, rf), (P.BARREL_STEP2_X + 0.12, rf - 0.06),
                             (w0 - 0.40, rf - 0.06), (w0 - 0.30, P.THREAD_R + 0.04), (w0, P.THREAD_R + 0.04), (w0, P.WASHER_R - 0.06), (w0 + 0.06, P.WASHER_R),
                             (w0 + P.WASHER_W - 0.06, P.WASHER_R), (w0 + P.WASHER_W, P.WASHER_R - 0.06), (w0 + P.WASHER_W, P.THREAD_R),
                             (x1, P.THREAD_R), (x1, 0.0)], BORE, AXIS, seg(hp, 12, 48), coll, start=DOWN)
    sg = lambda lo, hi: seg(hp, lo, hi)
    # the regulator's knob on the gas ring, pass 6: the gas block's two wrench flats (the cross pins stand on them), the regulator's
    # detent flange (BR.gas_block); the nut's eight castellations (BR.castellate)
    BR.gas_block(obj, g0, g1, P.GAS_R, P.BZ, coll, sg, reg_r=P.REG_R, reg_h=P.REG_H, flat=1.04, pin_reach=1.12)
    BR.castellate(obj, n1, rn, P.BZ, coll)
    flats = [K.box('cut', (w0 - 0.1, s * 0.86 if s > 0 else -2.0, P.BZ - 2.0), (w0 + P.WASHER_W + 0.1, 2.0 if s > 0 else -0.86, P.BZ + 2.0), coll) for s in (1.0, -1.0)]
    K.boolean(obj, flats)                                                       # the washer's two wrench flats
    if hp:
        # the cross pins' slotted heads and the twelve detent notches round the regulator's flange; two turned rings on the barrel's front
        # step; the regulator's grip, its two positions and a ring groove on the gas block. One pass, in this order: the exact solver
        # hands these cuts to the second one one by one, and the order decides the result
        cuts = BR.cross_pin_heads(g0, g1, P.BZ, coll, pin_reach=1.12) + BR.regulator_notches(g0, g1, P.GAS_R, P.BZ, coll, reg_r=P.REG_R)
        for x in (30.1, 30.35):
            cuts.append(K.tube('cut', on_bore(x), on_bore(x + 0.06), rf + 0.2, rf - 0.045, 48, coll))
        cuts += BR.regulator_grip(g0, g1, P.GAS_R, P.BZ, coll, reg_r=P.REG_R, reg_h=P.REG_H) + BR.gas_ring_groove(g0, P.GAS_R, P.BZ, coll)
        K.boolean(obj, cuts)
    K.cleanup(obj, keep=bore_seam())
    return tag(K.shade(obj), 'Grip_Bone')


def flash_hider(coll, hp=False):
    """A slotted flash hider: a cup on the barrel's end, slots round its top and sides, none underneath; pass 6: a recessed crown, two
    turned rings behind the slots (BR.flash_hider)."""
    obj = BR.flash_hider('FlashHider', P.HIDER_X[0], P.HIDER_X[1], P.BZ, coll, lambda lo, hi: seg(hp, lo, hi), hp, r=P.HIDER_R, r_in=P.HIDER_IN_R,
                         bore_r=P.BORE_R, slot=P.HIDER_SLOT, slot_deg=P.HIDER_SLOT_DEG, keep=bore_seam())
    return tag(K.shade(obj), 'Grip_Bone')


# ----------------------------------------------------------------------------------------------------------------- sights
def front_sight(coll, hp=False):
    """The front sight, clamped on the rail's front end (pass 4; SI.front_post): a post on a pedestal between two hooded wings, an adjuster
    on the left and a cross-bolt head on the right."""
    base = SI.front_post('SightFront', P.FRONT_X[0], P.FRONT_X[1], coll, lambda lo, hi: seg(hp, lo, hi), hp, MOUNT, P.SIGHT_Z,
                         wing=P.FRONT_WING, pedestal=(P.FRONT_PED_X, P.FRONT_PED_HW), post=(P.FRONT_POST_X, P.FRONT_POST_HW))
    return tag(shade(base, hp), 'Grip_Bone')


def rear_sight(coll, hp=False):
    """The rear sight, clamped on the rail's rear end (passes 4 to 6; SI.rear_aperture): two thin wings, the aperture arm on its pivot pin with
    two apertures, the windage screw and knob. The serrations, the wings' panels and the elevation scale are at this weapon's own heights
    (written as numbers, as they were drawn, so the sight is built to the same vertices as before the move)."""
    base = SI.rear_aperture('SightRear', P.REAR_X[0], P.REAR_X[1], coll, lambda lo, hi: seg(hp, lo, hi), hp, MOUNT, P.SIGHT_Z,
                            ear=P.REAR_EAR, ear_x=P.REAR_EAR_X, arm_x=P.REAR_LEAF_X, pivot=(P.DRUM_X, P.DRUM_Z), wind=P.WIND_XZ,
                            apertures=[(P.SIGHT_Z, P.APERTURE_R), (P.DRUM_Z + P.APERTURE2_DZ, P.APERTURE2_R)],
                            countersink=(P.REAR_CS_D, P.REAR_CS_W), knob_r=P.KNOB_R, knob_y=P.KNOB_Y,
                            serrations=(13.20, 15, 0.10), panel_z=(12.78, 14.52), scale_z=(12.98, 13.40, 13.82, 14.24))
    return tag(shade(base, hp), 'Grip_Bone')


# --------------------------------------------------------------------------------------------------- magazine, cartridges
def cartridge(name, base, coll, hp=False):
    """One cartridge pointing +X from its base centre."""
    r, length = P.CASE_R, P.CASE_LEN
    if hp:
        prof = [(0.0, 0.0), (0.0, r - 0.06), (0.06, r), (0.14, r), (0.16, r - 0.09), (0.26, r - 0.09), (0.34, r - 0.01),
                (P.SHOULDER_X, P.SHOULDER_R), (P.NECK_X, P.NECK_R), (length, P.NECK_R), (length, P.BULLET_R),
                (length + 0.5, P.BULLET_R - 0.04), (length + 0.95, 0.16), (P.OAL - 0.10, 0.06), (P.OAL, 0.0)]
    else:
        prof = [(0.0, 0.0), (0.0, r), (P.SHOULDER_X, P.SHOULDER_R), (P.NECK_X, P.NECK_R), (length, P.NECK_R), (length, P.BULLET_R),
                (length + 0.5, P.BULLET_R - 0.04), (P.OAL - 0.30, 0.12), (P.OAL, 0.0)]
    return K.lathe(name, prof, base, AXIS, seg(hp, 8, 32), coll)


def mag_ring(s, grow, s90):
    """The magazine's section s cm down its centre line, as 3D points: a rounded rectangle across the line, starting at the
    middle of its rear face (so K.loft leaves a line of edges there, for the UV seam)."""
    a, w, r = P.MAG_HALF + grow, P.MAG_HW + grow, P.MAG_CORNER + grow
    cx, cz, ang = P.mag_centre(s)
    fx, fz = math.cos(ang), math.sin(ang)
    return [(cx + u * fx, v, cz + u * fz) for u, v in K.round_poly([(-a, 0.0), (-a, w, r), (a, w, r), (a, -w, r), (-a, -w, r)], s90)]


def magazine(coll, hp=False):
    """The magazine: a box skinned down its centre line, straight inside the well and curved forward below it. The
    floor plate is a second, wider skin on its end."""
    s90 = seg(hp, 1, 8)
    straight = P.MAG_TOP - P.MAG_STRAIGHT_Z
    k = max(3, int(math.ceil(P.MAG_ARC_LEN / (0.5 if hp else 2.2))))
    marks = [0.0, straight] + [straight + P.MAG_ARC_LEN * i / k for i in range(1, k + 1)]
    body = K.loft('Magazine', [mag_ring(s, 0.0, s90) for s in marks], coll)
    lip, end = P.MAG_FLOOR_LIP, P.MAG_LEN
    K.boolean(body, K.loft('floor', [mag_ring(end - 0.05, lip, s90), mag_ring(end + P.MAG_FLOOR_T, lip, s90)], coll), 'UNION')

    x0, x1, w, t = P.MAG_X0, P.MAG_X1, P.MAG_HW, P.MAG_WALL
    under_lips = P.MAG_TOP - P.MAG_LIP_T
    follower = P.ROUND_TOP[2] - P.ROUND_PITCH_Z - P.CASE_R - 0.05
    r_in, s_in = P.MAG_CORNER - t, seg(hp, 1, 6)
    room = K.round_poly([(x0 + t, -w + t, r_in), (x1 - t, -w + t, r_in), (x1 - t, w - t, r_in), (x0 + t, w - t, r_in)], s_in)
    open_top = K.round_poly([(x0 + 3.9, -w + t), (x1 - t, -w + t, r_in), (x1 - t, w - t, r_in), (x0 + 3.9, w - t)], s_in)
    K.boolean(body, [
        K.prism('cut', room, 'XY', follower, under_lips, coll),                                               # where the rounds lie
        K.box('cut', (x0 + t, -P.MAG_LIP_Y, under_lips - 0.05), (x1 - t, P.MAG_LIP_Y, P.MAG_TOP + 1.0), coll),   # between the lips
        K.prism('cut', open_top, 'XY', under_lips - 0.05, P.MAG_TOP + 1.0, coll),                             # no lips over the bullet
    ])
    if hp:
        # pressed ribs down each side, following the curve below the well
        s0, s1, steps = straight + 0.4, end - 0.9, 28

        def rib(u):
            line = []
            for i in range(steps + 1):
                cx, cz, ang = P.mag_centre(s0 + (s1 - s0) * i / steps)
                line.append((cx + u * math.cos(ang), cz + u * math.sin(ang)))
            return line
        ribs = [K.grooves_on(body, [rib(-1.9), rib(0.0), rib(1.9)], frame, coll, half_w=0.16, depth=0.07) for frame in (LEFT, RIGHT)]
        K.cut_grooves(body, ribs, coll)
    K.cleanup(body, keep=mag_seam())
    # the ribs' edges slope at 24 degrees: hard at 20, so the bake rounds them, and the flat walls keep their own normals
    return tag(K.shade(body, 20.0, flats=True) if hp else K.shade(body), 'Clip_Bone')


def mag_rounds(coll, hp=False):
    """The two cartridges seen in the magazine's mouth: the top one to the left, the next to the right and lower."""
    bx, by, bz = P.ROUND_TOP
    rounds = [cartridge('r0', (bx, by, bz), coll, hp), cartridge('r1', (bx, -by, bz - P.ROUND_PITCH_Z), coll, hp)]
    return tag(K.shade(K.join('MagRounds', rounds, coll)), 'MagAmmo_Bone', mat='brass')


def chambered(coll, hp=False):
    """The cartridge in the chamber: the game draws it out with the bolt, or hides it."""
    return tag(K.shade(cartridge('Round', on_bore(P.CART_X), coll, hp)), 'Ammo', mat='brass')


BUILDERS = {
    'shell': shell, 'pad': pad, 'cheek_pad': cheek_pad, 'rail': rail, 'grip': grip, 'trigger': trigger, 'safety': safety, 'mag_release': mag_release,
    'charging_handle': charging_handle, 'bolt': bolt, 'barrel': barrel, 'flash_hider': flash_hider, 'front_sight': front_sight,
    'rear_sight': rear_sight, 'hardware': hardware, 'magazine': magazine, 'mag_rounds': mag_rounds, 'chambered': chambered,
}
