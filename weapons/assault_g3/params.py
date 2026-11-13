"""AssaultG3: every dimension in one place (pure Python, no bpy: the builders, the rig and the checks all read it).

Frame: the game's weapon frame as Blender sees it: origin at the grip (the middle of the hold on the pistol grip), +X toward
the muzzle, +Z up, +Y the weapon's LEFT. Unreal gets (x, -y, z): +Y right there. Centimetres.

The pattern: a bullpup. The action lies in the butt, behind the hand: the magazine goes in behind the pistol grip, the
ejection port is over it, and the bolt carrier runs back to within a thumb's width of the butt plate. One polymer shell
carries all of it: the butt, the housing of the action, the flat over the grip and the trigger, and the handguard, with a rail
along its flat top. A guard takes the whole hand, from the grip's toe up to the handguard. That gives a 43 cm barrel in a
gun 70 cm long.

Along the gun, from the back: butt pad -31.5, the shell -30.6 to 21.0, the carrier's rear -20.4, the magazine -14.3 to -7.9,
the bolt face -7.0, the grip at 0, the trigger at 6, the charging handle at 14, the barrel's end 36.0, the flash hider's
front 38.8.
"""
import math

from weaponforge import sections as S     # pure Python: the faceted section's arithmetic (corner, facet_ring, facet_y, lin, boss_top)

# --- datums
BZ = 8.60                              # bore axis, z
SEAT = 0.02                            # never model two parts into the same surface: this much air between them

# --- the cartridge: the 5.6 mm bottleneck of our own
CASE_R, CASE_LEN = 0.47, 4.45
SHOULDER_X, SHOULDER_R = 3.60, 0.44
NECK_X, NECK_R = 3.95, 0.32
BULLET_R = 0.285
OAL = 5.70

# --- the action, in the butt
BOLT_FACE_X = -7.00
CART_X = BOLT_FACE_X + SEAT            # the chambered cartridge's base
CHAMBER_R = 0.52
CHAMBER_X1 = CART_X + OAL + 0.25       # how far the hole for it runs into the shell
TUNNEL_R = 1.27                        # the hole the bolt carrier runs in
TUNNEL_X0 = -29.20                     # its rear end: the butt's wall is behind it
CARRIER_R = 1.22
CARRIER_X = (-20.40, -8.90)
BOLT_R = 0.72
BOLT_TRAVEL = 8.0
PORT_X = (-14.80, -8.20)               # the ejection port, on the right, over the magazine
PORT_Z = (BZ - 0.60, BZ + 0.85)
DECK_Z = BZ - 1.75                     # the level the magazine feeds up to

# --- the shell: a lofted body. Its side outline (x, z, corner radius) says how tall it is at each x; tables say how wide it is,
#     how far its flat top reaches and how square its underside is. (This used to be one outline of one thickness.)
TOP_Z = BZ + 2.20                      # its flat top, wherever the rail sits
BUTT_X = -30.45                        # the heel's rear (pass 3: 0.10 further back, so that the raked face still leaves a wall behind the tunnel)
BUTT_RAKE = 1.20                       # pass 3: the rear face is raked: its toe is this far forward of its heel
RAKE_FADE = 3.6                        # the rake fades out over this far from the rear (the flutes and the cheek panels are not sheared)
NOSE_X = 21.00                         # the top of its front face
NOSE_CHAMFER = 0.22                    # the chamfer round the front face
NOSE_LEAN = 1.15                       # the front face is sloped: its bottom (at the hand stop) is this far behind its top
NOSE_LOFT = NOSE_X + 0.15              # the loft runs this far past it, and a cut makes the face
FCG_Z = 4.05                           # its underside over the grip and the trigger
HG_Z = 5.70                            # the handguard's underside
LIP_Z = 4.90                           # the hand stop under the nose
WELL_X = (-15.15, -7.05)               # the magazine well, outside (at its mouth: the walls lean 0.3 cm and 0.5 cm back as they rise)
WELL_IN_X = (-14.40, -7.80)            # and inside
WELL_IN_HW = 1.14
WELL_Z = (0.30, 1.05)                  # its mouth: the height at the rear and at the front
BELLY_Z = 2.10                         # the butt's underside where it leaves the well
TOE_Z = -0.60
WELL_DRAFT = (0.50, 0.30)              # how far the rear and the front wall lean (a moulded wall, not a cliff the loft cannot make)
COMB_HEEL = 0.42                       # the top line falls toward the heel (the tunnel's roof is 0.93 under TOP_Z: 0.42 at most)
COMB_END = -15.5                       # where it starts to fall, a little behind the rail's rear end (-12.6)
COMB = [(BUTT_X + (COMB_END - BUTT_X) * i / 7.0, COMB_HEEL * (1.0 - i / 7.0) ** 1.8) for i in range(1, 7)]       # sampled, so that it has no kinks to catch the light
HEEL_R, TOE_R = 1.00, 0.35             # pass 3: the heel is rounder than the toe (the heel's arc is clamped by its neighbour, 0.9 at most)
HOOK_CREST = (-22.80, 2.55, 2.40)      # pass 3: the underside of the butt rises to a crest behind the well, then drops to the toe: a relief and a hook
SHELL_OUTLINE = [                      # from the heel forward along the top, down the nose, back along the underside
    (BUTT_X, TOP_Z - COMB_HEEL, HEEL_R)] + [(x, TOP_Z - d) for x, d in COMB] + [(COMB_END, TOP_Z),
    (NOSE_LOFT, TOP_Z), (NOSE_LOFT, LIP_Z, 0.6), (NOSE_X - 1.7, LIP_Z, 0.4), (NOSE_X - 2.5, HG_Z, 0.5),
    (11.20, HG_Z, 0.6), (9.90, FCG_Z, 0.6), (WELL_X[1] + WELL_DRAFT[1], FCG_Z, 0.4), (WELL_X[1], WELL_Z[1], 0.45),
    (WELL_X[0], WELL_Z[0], 0.45), (WELL_X[0] - WELL_DRAFT[0], BELLY_Z, 0.3), HOOK_CREST, (BUTT_X, TOE_Z, TOE_R),
]


def curve(points):
    """A smooth function through [(x, y)] (x rising) that never overshoots its points (the monotone cubic of Fritsch and
    Carlson, as weaponforge.kit.curve: copied here so that this file stays pure Python)."""
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    count = len(xs)
    if count == 1:
        return lambda x: ys[0]
    h = [xs[i + 1] - xs[i] for i in range(count - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(count - 1)]
    m = [d[0]] + [0.0] * (count - 2) + [d[-1]]
    for i in range(1, count - 1):
        if d[i - 1] * d[i] > 0.0:
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
        return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (3 * t2 - 2 * t3) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])
    return f


# --- the shell's section is FACETS with creases (a moulded body, not a soap bar): from the top a flat land, a shoulder facet
#     leaning SHOULDER_DEG, a side facet with a little draft, a belt line where the lower moulding stands proud of the upper one,
#     the lower side facet (draft the other way), a lower facet tucking in TUCK_DEG toward the flat underside. Each crease has a
#     small real radius. How wide it is changes in short ramps with crisp ends (a chamfered step), not in long swells.
DRAFT_DEG = 2.5                        # the side facets lean this far from upright (narrower away from the belt line)
SHOULDER_DEG, SHOULDER_RUN = 40.0, 0.70    # the shoulder's lean from level, and how far across it goes where there is room
TUCK_DEG = 18.0                        # the lower facet's lean from upright, toward the underside
LAND_MIN = 1.25                        # the flat top reaches at least this far from the middle where the rail sits
BELT_PROUD = 0.13                      # the lower moulding stands this far out of the upper one (a chamfered parting step)
CREASE_R, COLLAR_R = 0.17, 0.10        # the radius of the creases; of the collar's small corners (two chords each in the game mesh)
BOTTOM_R, TUCK_R = 0.20, 0.25
# half the shell's width at the belt line (the lower moulding), along the gun: the butt's edge chamfer, the butt, the housing of the
# action, the waist over the hand, the handguard. Straight lines between the points: a ramp 2.5 to 3 cm long has a crease at each end.
SECTION_HW = [(BUTT_X, 1.55), (BUTT_X + 0.20, 1.75), (-28.40, 1.75), (-25.90, 2.20), (-3.90, 2.20), (-0.90, 1.78), (7.00, 1.78),
              (10.00, 2.05), (12.00, 2.05), (NOSE_LOFT, 1.92)]
# the belt line's height along the gun: level over the butt, the housing and the waist, then a diagonal jog down under the vents
SECTION_BELT = [(BUTT_X, BZ - 1.30), (7.00, BZ - 1.30), (10.00, BZ - 2.25)]
WELL_COLLAR, WELL_COLLAR_H = 0.25, 1.30       # the magazine well's collar: how far it stands out all round, and how tall it is
SECTION_COLLAR = [(WELL_X[0] - WELL_DRAFT[0], 0.0), (WELL_X[0], WELL_COLLAR), (WELL_X[1], WELL_COLLAR), (WELL_X[1] + WELL_DRAFT[1], 0.0)]
WELL_FUNNEL = 0.30                     # the well's mouth is chamfered (a funnel) this much
HG_MAX_Y = 2.05                        # the widest the handguard gets (the charging handle's box starts outside it)


lin = S.lin                            # straight lines between the points, constant beyond the ends (weaponforge.sections)


# --- pass 3: the top cover. A black alloy skin over the upper half of the shell, from the handguard's nose to just behind the ejection port,
#     standing CV_PROUD proud of the shell's upper side facets (its top land stays level with TOP_Z, so the rail sits as before), with a
#     shut line all round it: a groove CV_GW wide and CV_GD deep, with the cover's edge overhanging it. Its lower edge is stepped: it follows
#     the belt line's jog, the other way. All of it is in the section (ring), so the game mesh has it too and no hidden face is made.
CV_X0 = -17.40                         # the cover's rear end (the transverse shut line is just behind it); it runs on over the nose
CV_TAIL = (9.45, 1.70)                  # pass 3b: the cover's rear end is a diagonal tail (its lower edge rises to this z at the very end, over this length: 45 degrees, echoing the belt line's jog)
CV_EDGE = [(CV_X0, CV_TAIL[0]), (CV_X0 + CV_TAIL[1], 7.75), (7.20, 7.75), (9.80, 8.75), (23.0, 8.75)]     # its lower edge, z: a tail at the rear, level over the housing, up a step over the handguard
CV_PROUD, CV_GW, CV_GD = 0.10, 0.07, 0.08
CV_A = (CV_X0 - CV_GW - 0.012, CV_X0 - CV_GW, CV_X0 - 0.012)           # where the transverse groove's walls are (stations, crisp)
# --- the cheek pad: a rubber saddle on the comb behind the rear sight (its section is in the ring, like the cover)
CP_X = (BUTT_X + 2.00, CV_X0 - 0.20)  # pass 3b: the cheek pad is its own part (parts.cheek_pad): from 2 cm ahead of the butt's rear face to the cover's shut line
CP_H, CP_ZL, CP_DROP_R = 0.30, 7.00, 2.50   # how far it stands proud; its lower edge on the left (z; about 3.5 to 3.8 under the comb); how far down the right shoulder it goes
CP_RIB_D, CP_RIB_PITCH, CP_RIB_W = 0.11, 0.40, 0.26   # the cross ribs on its top: their depth, pitch and groove width at the top (45 degree walls, a floor 0.04 wide, a rib top 0.14)
CP_STEP = 0.07                         # the border step's chamfer
CP_HW, CP_RAMP, CP_SAG, CP_SAGS = 0.95, 0.14, 0.0, 0   # (the section's own cheek pad is gone: pad_h is 0)

_hw, _belt, _collar = lin(SECTION_HW), lin(SECTION_BELT), lin(SECTION_COLLAR)
_cv_edge = lin(CV_EDGE)
_cv_proud = lin([(CV_A[2], 0.0), (CV_X0, CV_PROUD)])
_cv_inset = lin([(CV_A[0], 0.0), (CV_A[1], CV_GD), (CV_A[2], CV_GD), (CV_X0, 0.0)])
_cv_groove = lin([(CV_A[0], 0.0), (CV_A[1], CV_GD)])
SECTION_KNOTS = sorted({p[0] for t in (SECTION_HW, SECTION_BELT, SECTION_COLLAR, CV_EDGE[:-1]) for p in t} | set(CV_A) | {CV_X0})
CV_MUST = CV_A + (CV_X0,)             # these get a ring however close they are


def rake(x, z):
    """Where the point (x, z) of the shell's straight rear goes once the rear face is raked: the shell's rear stays vertical in the
    outline and every ring is sheared, forward by up to BUTT_RAKE toward the toe (z = TOE_Z) and by nothing at the heel; the shear fades
    out over RAKE_FADE from the rear, so nothing forward of the butt moves."""
    t = min(1.0, max(0.0, (x - BUTT_X) / RAKE_FADE))
    w = 1.0 - t * t * (3.0 - 2.0 * t)
    f = min(1.0, max(0.0, (TOP_Z - COMB_HEEL - z) / (TOP_Z - COMB_HEEL - TOE_Z)))
    return x + BUTT_RAKE * w * f


def hw(x):
    """Half the shell's width at its widest (the belt line), x along the gun."""
    return _hw(x)


def belt(x):
    return _belt(x)


def outline_span(x):
    """(lowest z, highest z) of the shell's side outline at x (the straight outline, corners not rounded)."""
    hits = []
    pts = [p[:2] for p in SHELL_OUTLINE]
    for i, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1])):
        if min(a[0], b[0]) - 1.0e-9 <= x <= max(a[0], b[0]) + 1.0e-9:
            if abs(b[0] - a[0]) < 1.0e-9:
                hits += [a[1], b[1]]
            else:
                hits.append(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))
    return (min(hits), max(hits)) if hits else None


def cover_z(x):
    """The cover's lower edge at x."""
    return _cv_edge(x)


def pad_h(x):
    """The cheek pad's height over the comb at x: 0 off its ends, ramped on them, sagging in the middle (a saddle along its length)."""
    return 0.0                             # pass 3b: the cheek pad is a part of its own (parts.cheek_pad), not a bulge of the shell's section


def facets(x, lo, hi):
    """The sharp corners of the shell's section at x, left half, from the underside up to the top: [(y, z, radius)], and the top centre
    point (0, z) the ring closes on. lo and hi are the underside and the top there (the side outline). Pass 3: after the belt line, the
    cover's shut line (a groove, then the cover's edge overhanging it), the cover's proud side and shoulder, and, on the comb, the cheek
    pad's section. Outside the cover and the pad those points lie on the facets they leave, a few hundredths apart: a collinear run the
    cleanup dissolves."""
    zb, yb, c = _belt(x), _hw(x), _collar(x)
    td, tl, tn = math.tan(math.radians(DRAFT_DEG)), math.tan(math.radians(TUCK_DEG)), math.tan(math.radians(SHOULDER_DEG))
    s = c / WELL_COLLAR
    tuck = min(0.8, max(0.25, 0.20 * (zb - lo)))
    tuck = tuck * (1.0 - s) + 0.5 * s                         # round the well the tuck is short: the collar stands there
    zt = lo + tuck

    def lower(z):                                             # the lower side facet: narrower going down
        return yb - td * (zb - z)
    avail = zb - zt
    z3 = zt + min(WELL_COLLAR_H - 0.5 - 0.25, 0.40 * avail)   # where the collar's chamfer starts (1.05 over the mouth)
    z4 = z3 + min(0.25, 0.30 * avail)                         # and where it ends: 45 degrees when the collar is full
    u0 = yb - BELT_PROUD + td * (zb + BELT_PROUD)             # the upper side facet: y = u0 - td z
    land = max(u0 - td * (hi - 0.5) - SHOULDER_RUN, LAND_MIN if x > -13.4 else 0.0)
    zs = (hi - (u0 - land) * tn) / (1.0 - td * tn)            # where the shoulder starts: it is as far across as the land allows
    ys = u0 - td * zs
    proud, inset, groove = _cv_proud(x), _cv_inset(x), _cv_groove(x)
    zc = _cv_edge(x)

    def up(z):
        return u0 - td * z
    cover = [(up(zc - 0.045), zc - 0.045, 0.0), (up(zc - 0.030) - groove, zc - 0.030, 0.0), (up(zc + 0.025) - groove, zc + 0.025, 0.0),
             (up(zc + 0.040) + proud - inset, zc + 0.040, 0.0)]
    top = (0.0, hi - inset)
    v = [(lower(zt) - tuck * tl + c, lo, BOTTOM_R), (lower(zt) + c, zt, TUCK_R), (lower(z3) + c, z3, COLLAR_R), (lower(z4), z4, COLLAR_R),
         (yb, zb, 0.0), (yb - BELT_PROUD, zb + BELT_PROUD, 0.0)] + cover + [(ys + proud - inset, zs, CREASE_R), (land, hi - inset, CREASE_R)]
    return v, top


def shoulder_z(x):
    """The height where the shoulder facet meets the side facet at x (the top of the flat side)."""
    lo, hi = outline_span(x)
    return facets(x, lo, hi)[0][10][1]


_corner = S.corner                     # k + 1 points round a corner (an arc of radius r, clamped to its neighbours); moved to weaponforge.sections


def ring(x, lo, hi, k=2):
    """The shell's section at x: points (y, z) from the bottom centre round by +y (left) over the top to the right and back, the
    facets with their creases rounded (k chords each). The same number of points at every x, and 2 more on the centre line."""
    v, top = facets(x, lo, hi)
    return S.facet_ring(v, lo, top, k)


def side_y(x, z):
    """How far from the middle the shell's surface is at (x, z), on either side: None above or below the section. The sharp
    facets, not the rounded creases: keep what is seated on it a crease's radius away from the creases."""
    span = outline_span(x)
    if span is None or not span[0] <= z <= span[1]:
        return None
    lo, hi = span
    v, top = facets(x, lo, hi)
    return S.facet_y(v, lo, top, z)


SECTION_K = (3, 4)                     # chords in each crease of the section: the game mesh, the bake source
SHELL_ARC = (3, 6)                     # chords in a quarter turn of the outline's corners (a ring goes in at each)
SLING_X = (-28.40, -26.80)             # a slot through the butt for a sling
SLING_Z = (1.95, 2.85)                 # pass 3: above the hook's descending underside

# --- the relief, in the game mesh as well as the bake source (each is cut or raised from the surface where it is, not from a flat)
FLUTE_X = (-25.40, -17.20)             # three long flutes pressed into each side of the butt (on the lower moulding, under the belt line)
FLUTE_Z = (3.50, 5.00, 6.50)
FLUTE_HH, FLUTE_DEPTH, FLUTE_INSET = 0.42, 0.25, 0.19     # half their height; how deep; how far the floor is drawn in from the lip
VENT_X0, VENT_PITCH, VENTS = 12.70, 1.25, 6            # blind pockets in the handguard's sides, leaning forward (over the belt line's jog)
VENT_Z = (6.85, 8.15)                  # pass 3: under the cover's raised edge (8.75 over the handguard)
VENT_W, VENT_LEAN, VENT_DEPTH, VENT_INSET = 0.60, 0.55, 0.90, 0.12     # pass 3: deep (the floor is dark: a hollow behind them), in the game mesh too
PANEL_X, PANEL_Z, PANEL_DEPTH, PANEL_R = (-15.60, -7.40), (7.95, 9.90), 0.22, 0.45   # the recess round the ejection port (on the right)
DEFL_X = (-15.55, -14.95, -14.75)      # the case deflector at the port's rear edge: where it rises, where its top begins, its face
DEFL_Z = (7.95, 9.60)
DEFL_H = 0.55                          # its height above the recess's floor (about 0.35 above the shell round it)
CHEEK_X = (-25.60, -18.60)             # a raised cheek panel on each side of the butt's upper half (above the belt line)
CHEEK_Z0 = BZ - 0.15                   # its lower edge; its upper edge follows the top line, 0.25 under where the shoulder starts
CHEEK_H, CHEEK_CHAMFER = 0.15, 0.12
BOSS_PIN = 0.62                        # the boss round each action pin and its height above the surface
BOSS_PIN_H = 0.22
PINS = ((-4.90, 5.75), (-29.15, 5.00))                 # the two pins that hold the action in the shell
BOSS_SAFE = 0.78
BOSS_SAFE_H = 0.28


def boss_top(x, z, r, h):
    """How far from the middle the flat top of a boss of radius r stands at (x, z): `h` above the highest the surface gets under it."""
    return S.boss_top(side_y, x, z, r, h)


# --- butt pad: a thick crowned rubber pad on a hard black spacer plate, let on to the butt's raked rear face (built vertical, then sheared with
#     the shell's rake). Seen from the side: olive, the black plate, the rubber. Its rear face is domed, its edge rounded
PAD_HW = 1.48
PAD_Z = (TOE_Z + 0.50, TOP_Z - COMB_HEEL - 0.85)
SPACER_T = 0.32                        # the hard plate between the shell and the pad
SPACER_INSET = 0.10                    # how much smaller than the pad it is, all round
PAD_T = 1.02                           # the pad's depth at its edge (its sides, before the edge rounds off)
PAD_CROWN = 0.22                       # how much further back the middle of the rear face stands
PAD_R = 0.50                           # the rounding of its rear edge
PAD_X = (BUTT_X - SPACER_T - PAD_T - PAD_CROWN, BUTT_X - SEAT)      # the pad stack: the rearmost point and the face against the shell

# --- pass 3: under the fore-end: a rubber hold pad on the centre line, and four plain accessory slots (obround, 0.3 deep) either side of it
HOLD_X, HOLD_HW, HOLD_H = (14.30, 18.20), 0.60, 0.20
SLOT_X = ((14.30, 16.20), (16.55, 18.35))
SLOT_Y, SLOT_W, SLOT_DEPTH = 1.02, 0.46, 0.30

# --- the bolt release lever (left, behind the well) and the front sling loop (under the hand stop)
LEVER_X, LEVER_Z, LEVER_H = (-16.95, -15.95), (3.00, 4.50), 0.30
LOOP_X, LOOP_Z = (19.30, 20.75), (3.90, 5.20)

# --- the rail on the shell's top: a section (y, z) run along x
RAIL_X = (-12.60, 19.60)
RAIL_HW = 1.06
RAIL_Z = TOP_Z + 0.80                  # its top
RAIL_HALF = [(0.80, TOP_Z + SEAT), (0.80, TOP_Z + 0.22), (RAIL_HW, TOP_Z + 0.42), (RAIL_HW, TOP_Z + 0.62), (0.88, RAIL_Z)]
RAIL_SLOT_W, RAIL_SLOT_D, RAIL_PITCH = 0.52, 0.30, 1.00
RAIL_SLOT_X0, RAIL_SLOTS = -7.40, 23   # the first slot's middle, how many (the sights sit on the rail at either end)

# --- sights, clamped on the rail
SIGHT_Z = RAIL_Z + 2.60
SIGHT_BASE_HW = 1.30
SIGHT_BASE_Z = (RAIL_Z - 0.62, RAIL_Z + 1.15)          # the jaws' underside; (the knob's height hangs off the second)
REAR_X = (-12.30, -8.60)
REAR_EAR = (0.80, 1.12)                # pass 4: the wings, thin (0.32): from, to (y)
REAR_EAR_X = (REAR_X[0] + 0.70, REAR_X[1] - 0.60)
REAR_ARM_T = 0.45                      # pass 4: the aperture arm, a slim plate (its x thickness), standing between the wings on a pivot pin
REAR_ARM_X0 = REAR_X[0] + 1.80 - 0.115
REAR_LEAF_X = (REAR_ARM_X0, REAR_ARM_X0 + REAR_ARM_T)       # (the arm's rear face, its front face)
REAR_LEAF_HW = 0.62
APERTURE_R = 0.13
REAR_CS_D = 0.08                       # the countersunk rim of each aperture, on the eye side: how deep, and how much wider than the hole at the face
REAR_CS_W = 0.08
DRUM_R = 0.62                          # (pass 3's drum; now the pivot's boss radius)
DRUM_X = (REAR_LEAF_X[0] + REAR_LEAF_X[1]) / 2
DRUM_Z = SIGHT_Z - 1.30                # the arm's pivot pin (along y), 1.3 under the line of sight
APERTURE_X = (REAR_LEAF_X[0] + REAR_CS_D + REAR_LEAF_X[1]) / 2       # where the mesh puts the aperture: the mean of the hole's two rings (the countersink's bottom, the arm's front face)
APERTURE2_R, APERTURE2_DZ = 0.30, SIGHT_Z - 0.62 - (SIGHT_Z - 1.30)      # the second, wide aperture: its radius, and its height relative to the pivot's (0.68 up)
KNOB_R = 0.50                          # the windage knob on the right
KNOB_Y = (-2.00, -1.42)
WIND_XZ = (REAR_EAR_X[1] - 0.35, RAIL_Z + 0.75)       # the windage screw's axis (along y): in front of the arm, just over the base
FRONT_X = (16.00, 18.70)
FRONT_WING = (0.50, 0.82)              # the wings either side of the post: from, to (y)
FRONT_PED_HW = 0.34                    # the pedestal the post stands on
FRONT_PED_X = (16.85, 17.85)
FRONT_POST_X = 17.35
FRONT_POST_HW = 0.09

# --- pistol grip and the guard for the whole hand: one polymer part. The grip is raked 15 degrees (steep:
#     the magazine is close behind it)
GRIP_BEVEL = 0.45
GRIP_RAKE_DEG = 15.0
GRIP_FRONT_TOP = (2.88, 1.20)          # where the front strap starts
GRIP_LEN, GRIP_DEPTH = 7.6, 3.3        # along the front strap; across the grip, strap to strap
GRIP_TOP_Z = FCG_Z - SEAT
GRIP_SINK = 0.55                       # the grip's top runs this far up into the shell (the shell's underside is rounded, so a flat top would show a gap)


def grip_pt(t, u, *more):
    """A point of the grip: t cm down the front strap from its top, u cm in from it toward the back strap."""
    a = math.radians(GRIP_RAKE_DEG)
    return (GRIP_FRONT_TOP[0] - math.sin(a) * t - math.cos(a) * u, GRIP_FRONT_TOP[1] - math.cos(a) * t + math.sin(a) * u) + more


# the web behind the grip (a beavertail: a concave fillet, radius WEB_R, from the back strap into the shell's underside) and the one in
# front of it toward the trigger slot are part of the outline: a point is put at each end of them and between
WEB_R = 1.0


def _web(cx, cz, a0, a1, n=7):
    """Points of a concave fillet's arc: centre (cx, cz), radius WEB_R, from angle a0 to a1 (degrees)."""
    return [(cx + WEB_R * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))), cz + WEB_R * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1))))
            for i in range(n)]


_BACK_E = (-1.25, 3.00)                # the back strap's line runs up from here toward the shell's underside (it would meet it at about x -2.10)
_BACK_U = (-0.85, 1.03)
_bl = math.hypot(*_BACK_U)
_bn = (_BACK_U[1] / _bl, -_BACK_U[0] / _bl)              # the line's normal toward the grip's side (0.772, 0.637)
# the fillet's circle: its centre is WEB_R under the shell's underside and WEB_R from the line on the side away from the grip
_web_cz = GRIP_TOP_Z - WEB_R
_web_cx = (_bn[0] * _BACK_E[0] + _bn[1] * _BACK_E[1] - WEB_R - _bn[1] * _web_cz) / _bn[0]
_web_a0 = math.degrees(math.atan2(_bn[1], _bn[0]))
def grip_front_z(x):
    """The height of the grip's front strap's face at x (it leans: the face is further forward higher up)."""
    return GRIP_FRONT_TOP[1] - (GRIP_FRONT_TOP[0] - x) / math.tan(math.radians(GRIP_RAKE_DEG))


GRIP_OUTLINE = [
    (3.88, GRIP_TOP_Z)] + _web(3.88, GRIP_TOP_Z - WEB_R, 90.0, 180.0)[1:-1] + [(2.88, GRIP_TOP_Z - WEB_R), GRIP_FRONT_TOP + (0.6,),
    grip_pt(GRIP_LEN, 0.0, 0.3), grip_pt(GRIP_LEN, GRIP_DEPTH, 0.7), grip_pt(2.07, GRIP_DEPTH, 3.0), _BACK_E + (1.2,)] + \
    _web(_web_cx, _web_cz, _web_a0, 90.0)
# the grip is a loft of slices across it (z from the toe up into the shell): half its width at each height, a palm swell between
# the web of the hand and the toe, a flatter front strap (exponent 3.2) and a rounder back strap (2.1). Its top is nearly as wide as
# the shell's underside there (a small step to the tuck, not a narrower neck); its toe as wide as the guard's strap.
GRIP_HW = [(GRIP_TOP_Z + GRIP_SINK, 1.42), (GRIP_TOP_Z, 1.45), (2.5, 1.52), (0.8, 1.58), (-0.9, 1.65), (-2.5, 1.66), (-4.0, 1.58),
           (-5.2, 1.52), (-6.2, 1.42)]
GRIP_BACK_EXP, GRIP_FRONT_EXP, GRIP_WIDEST = 2.1, 3.2, 0.46
GRIP_M = (12, 14)
GRIP_CHECK = [grip_pt(2.9, 1.25, 0.3), grip_pt(6.6, 1.25, 0.4), grip_pt(6.6, 2.85, 0.4), grip_pt(2.9, 2.85, 0.4)]     # the checkering on each side, inside the insert's border
GRIP_CHECK_PITCH = 0.16
BACKSTRAP_HW, BACKSTRAP_T, BACKSTRAP_DEPTH = 0.80, (1.9, 6.6), 0.45      # pass 3: the back strap's rubber insert: half its width, from t to t down the strap, how deep it reaches into the strap
# the guard's strap: a moulded blade, a loft of rounded rectangles along a centre line (x, z, radius). It leaves the grip's toe, runs forward
# under the hand and climbs to the handguard in one curve. It is wider and thicker where it meets the toe and the handguard (root
# fillets that make it one moulding with them) and runs on into both.
GUARD_Z = -6.04                        # its underside along the bottom: level with the grip toe's lowest point
GUARD_T = 0.75                         # its thickness along the bottom and up the riser
GUARD_HW, GUARD_HW_ROOT = 1.10, 1.40   # half its width along the strap, and at the roots
GUARD_EDGE = 0.20                      # the radius that rounds its edges
GUARD_ROOT_EDGE = 0.70                 # and at the roots, where it is thick
GUARD_ROOT_R = 0.80                    # the radius of the root fillets
GUARD_ELBOW_R = 3.10                   # the centre line's radius at the elbow (the inside is this less half the thickness: 2.7)
GUARD_TOE_FACE_S, GUARD_TOE_FLARE_L = 0.45, 2.8        # the grip's front face at the strap's level, along the line from its start; the length over which the blade widens to meet it
GUARD_TOE_XC = 2.150                   # the toe fillet's circle: its centre's x (it is tangent to the grip's front strap there)
GUARD_PATH = [(0.70, GUARD_Z + GUARD_T / 2), (9.81, GUARD_Z + GUARD_T / 2, GUARD_ELBOW_R), (12.70, HG_Z + 0.70)]
GUARD_TOE_FILLET, GUARD_TOE_NARROW, GUARD_TOE_R = 0.0, 0.0, 0.8   # off. pass 4: share of the toe's quarter circle (radius GUARD_TOE_R) kept, and how much narrower the blade gets as it climbs it. Pass 5 tried 1.0, 0.6, 1.3: a hump stood off the grip, reverted
GUARD_K = (4, 6)                       # chords in a corner of its section: the game mesh, the bake source
RISER_DEG = math.degrees(math.atan2(GUARD_PATH[2][0] - GUARD_PATH[1][0], GUARD_PATH[2][1] - GUARD_PATH[1][1]))     # how far the riser leans forward

# --- trigger: a blade, in a slot of the shell
TRIG_PIVOT = (6.30, 5.30)
TRIG_HW = 0.19
TRIG_SLOT_X = (5.00, 7.10)
TRIG_PULL_DEG = 8.0

# --- safety: a button through the shell over the grip. Bound at "safe": it stands out on the left. Pressed through, it stands
#     out on the right: "fire"
SAFE_XZ = (1.20, 5.60)
SAFE_R = 0.40
SAFE_PROUD = 0.36                      # how far the button stands out of its boss on the left ("safe"); on the right, when pressed
SAFE_PRESS = 0.30
SAFE_TOP = boss_top(SAFE_XZ[0], SAFE_XZ[1], BOSS_SAFE, BOSS_SAFE_H)      # the face of the boss round it, from the middle

# --- magazine release: a paddle behind the well, its head in a pocket of the butt's underside
REL_HW = 0.75
REL_OUTLINE = [(-16.55, 2.60), (-16.55, 0.95, 0.15), (-16.25, 0.55, 0.2), (-15.70, 0.55, 0.2), (-15.60, 2.60)]
REL_POCKET_X = (-16.70, -15.32)
REL_POCKET_Z = (1.00, 2.70)
REL_PRESS = 0.20                       # toward the magazine

# --- charging handle: a knob on the left of the handguard, on a lug that runs in a slot
CH_Z = (BZ + 0.55, BZ + 1.25)
CH_SLOT_X = (4.40, 15.00)
CH_SLOT_FLOOR = 1.00                   # the slot's floor, from the middle: flat, the sides it runs through are not
CH_LUG_X = (13.30, 14.70)
CH_KNOB = ((CH_LUG_X[0] + CH_LUG_X[1]) / 2, (CH_Z[0] + CH_Z[1]) / 2)        # the knob's axis: (x, z)
CH_KNOB_R = (0.42, 0.60)               # its neck and its head
CH_SEAT_Y = max(side_y(CH_KNOB[0] + CH_KNOB_R[1] * math.cos(a * math.pi / 4), CH_KNOB[1] + CH_KNOB_R[1] * math.sin(a * math.pi / 4))
                for a in range(8))      # the handguard's left side where the knob stands: the highest it gets under the knob's head
CH_BOX_Y = HG_MAX_Y + 0.03             # collision: what is outside this on the handguard is the charging handle
CH_KNOB_Y = (CH_SEAT_Y + 0.12, CH_SEAT_Y + 1.55)
HANDLE_TRAVEL = 8.6

# --- barrel: what shows of it, ahead of the handguard's nose
NUT_R = 1.35
GAS_X = (23.20, 24.70)                 # pass 3: the gas block's ring (radius GAS_R); the regulator's knob stands on it
GAS_R = 1.16
REG_R, REG_H = 0.52, 0.70
BARREL_TAPER = (24.70, 0.95, 28.00, 0.88)   # x, r where the taper starts and ends
BARREL_STEP2_X = 32.20                 # a second turned step
WASHER_R, WASHER_W = 1.02, 0.34        # the crush washer behind the flash hider (two wrench flats)
NOSE_FACE_X = NOSE_X + (BZ - TOP_Z) * NOSE_LEAN / (TOP_Z - LIP_Z)       # the sloped front face where the bore comes through it
CBORE_R, CBORE_DEPTH = NUT_R + 0.12, 0.35                               # the nut sits in a shallow counterbore in it
NUT_X = (NOSE_FACE_X - CBORE_DEPTH + SEAT, NOSE_X + 1.00)
BARREL_STEP_X = 29.00                  # ahead of this it is turned down
BARREL_R, BARREL_FRONT_R, THREAD_R = 0.95, 0.82, 0.74
BARREL_END_X = 36.00
BORE_R = 0.285
HIDER_X = (BARREL_END_X - 1.60, BARREL_END_X + 2.80)
HIDER_R = 1.08
HIDER_IN_R = 0.62
HIDER_SLOT = (HIDER_X[0] + 1.65, HIDER_X[0] + 3.75, 0.15)      # the slots: from, to, half width
HIDER_SLOT_DEG = (0.0, 54.0, -54.0, 108.0, -108.0)             # round from the top: none underneath
MUZZLE_X = HIDER_X[1]

# --- magazine: straight inside the well and curved forward below it
MAG_X0, MAG_X1 = -14.30, -7.90
MAG_HW = 1.10
MAG_TOP = DECK_Z - 0.20                # top of the feed lips
MAG_STRAIGHT_Z = -0.30
MAG_ARC_R = 30.0
MAG_ARC_LEN = 10.8
MAG_CORNER = 0.25
MAG_FLOOR_T, MAG_FLOOR_LIP = 0.30, 0.12
MAG_LIP_Y, MAG_LIP_T = 0.78, 0.23
MAG_WALL = 0.10
MAG_ROUNDS = 30

MAG_CENTRE_X = (MAG_X0 + MAG_X1) / 2
MAG_HALF = (MAG_X1 - MAG_X0) / 2
MAG_TOP_CENTRE = (MAG_CENTRE_X, 0.0, MAG_TOP)
MAGWELL = (MAG_CENTRE_X, 0.0, (WELL_Z[0] + WELL_Z[1]) / 2)
MAG_LEN = (MAG_TOP - MAG_STRAIGHT_Z) + MAG_ARC_LEN        # along its centre line, lips to the underside of its body
ROUND_Y = 0.42
ROUND_TOP = (MAG_X0 + 0.30, ROUND_Y, MAG_TOP - 0.56)      # base centre of the top cartridge in the magazine (it lies to the left)
ROUND_PITCH_Z = math.sqrt((2 * CASE_R) ** 2 - (2 * ROUND_Y) ** 2)


def mag_centre(s):
    """(x, z, angle): the magazine's centre line s cm below the top of its lips, measured along it, and how far it has turned
    forward there (radians). Across the magazine at that point, "front" is (cos angle, sin angle) in (x, z)."""
    straight = MAG_TOP - MAG_STRAIGHT_Z
    if s <= straight:
        return MAG_CENTRE_X, MAG_TOP - s, 0.0
    a = (s - straight) / MAG_ARC_R
    return MAG_CENTRE_X + MAG_ARC_R * (1.0 - math.cos(a)), MAG_STRAIGHT_Z - MAG_ARC_R * math.sin(a), a


def mag_centre_x(z):
    """The centre line's x at height z (for telling the magazine's rear face from its front)."""
    if z >= MAG_STRAIGHT_Z:
        return MAG_CENTRE_X
    a = math.asin(min(1.0, (MAG_STRAIGHT_Z - z) / MAG_ARC_R))
    return MAG_CENTRE_X + MAG_ARC_R * (1.0 - math.cos(a))


# --- the ejection port's recess (the right side): its floor, from the middle, at the port's middle
PORT_FLOOR_Y = side_y((PORT_X[0] + PORT_X[1]) / 2, (PORT_Z[0] + PORT_Z[1]) / 2) - PANEL_DEPTH

# --- the hold, the markings (ours: no maker, no real model)
FORE_HOLD_X = 16.0
MARK_MODEL = 'MOD. AS3'
MARK_CAL = 'CAL 5.6 mm'
MARK_SERIAL = 'AS3 044582'
MARK_SAFE, MARK_FIRE = 'SAFE', 'FIRE'
MARK_RACK = '07'                       # pass 3: a stencilled rack number, white, on the butt's left (fictional)
# the data plate: a steel plate sunk in the shell's left side under the model and calibre marks, two rivets, the serial engraved on it
PLATE_X = (-12.20, -10.00)
PLATE_Z = (2.55, 3.55)
PLATE_SINK, PLATE_T = 0.13, 0.09       # how deep the recess goes at the plate's low edge (the side leans a little), and the plate's thickness
# where the cover is bolted (hex-socket screws in counterbores): (x, z, side) with side +1 the left
COVER_SCREWS = ((-14.8, 8.55, 1.0), (-1.5, 8.55, 1.0), (18.6, 9.45, 1.0), (-1.5, 8.55, -1.0), (6.0, 8.55, -1.0), (18.6, 9.45, -1.0))
COVER_TOP_SCREWS = ((-15.2, 1.0), (-15.2, -1.0), (-6.2, 1.0))     # pass 3b: hex screws on the cover's shoulder facets near the rear sight: (x, side)
PICTO_DZ = -1.20                       # the selector's pictograms: this far below the SAFE / FIRE words (they are under the button)



# --- pass 3b: the pistol grip's overmoulded rubber insert: one wrap-around shape (both side panels and the back strap) with a sunk border groove
#     all round it and rounded corners, olive left round it as a frame (the front strap and a margin). Drawn in (t, w): t cm down the strap, w the
#     way round the section (theta, 0 at the back strap, 90 degrees at the sides, times INS_KW cm per radian).
INS_T = (2.45, 7.05)                   # where the insert begins and ends down the strap
INS_PHI = 108.0                        # half of its extent round the section, degrees (the front strap's own 70 degrees stay olive)
INS_KW, INS_R = 1.50, 0.70             # cm per radian round the section; the radius of its corners (in t, w)
INS_GW, INS_GD = 0.16, 0.10            # the border groove: width and depth

# pass 3b: a quick-detach sling cup on the shell's right side (the game mesh has it), in a moulded panel line (the bake source's)
QD_XZ = (-11.40, 4.70)
QD_R, QD_DEPTH = 0.55, 0.40
QD_PANEL_X, QD_PANEL_Z = (-14.60, -8.20), (2.95, 6.55)

# --- pass 4 (first-person hardware)
CFLUTE_X, CFLUTE_HW, CFLUTE_D = (-4.40, 12.40), 0.26, 0.10       # the cover's shoulder flutes: from x to x, half width, depth
SERR_X, SERR_PITCH = (-16.90, -13.20), 0.14                   # the anti-glare cross-grooves on the cover's top land behind the rear sight
