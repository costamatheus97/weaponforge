"""AssaultG3: the weapon definition. A bullpup rifle of the game's own design: the action lies in the butt behind the hand, the
magazine goes in behind the pistol grip, and one polymer shell carries everything from the butt pad to the handguard's nose,
with a rail along its flat top and a guard for the whole hand under it. No real maker's name or markings.

Geometry is in parts.py, every dimension in params.py; this file says how the parts make a weapon.

The rig uses the bone and socket names a conventional carbine's would (Clip_Bone, Bolt_Bone, Muzzle, ...), with the same
meanings, so game code written for one drives the other. What a bullpup changes is where things are: the magazine and the
ejection port are behind the grip, the charging handle is on the left of the handguard, the safety is a button pushed
through the shell (it slides, where a carbine's lever turns), the magazine release is a paddle behind the well (it is
pushed forward).
"""
import math

import bmesh
import numpy as np
from mathutils import Matrix, Vector

from weaponforge import bake as B
from weaponforge import check as CHK
from weaponforge import finish as F
from weaponforge import kit as K
from weaponforge import surface as S
from weaponforge.weapon import Decal, Move, Prop, TexelZone, Weapon, Zone   # TEXFORGE: Decal; UV DENSITY: TexelZone

from . import params as P
from . import parts as PT

MAG_PARTS = ('Clip_Bone', 'MagAmmo_Bone')
KNOB = (P.CH_KNOB[0], (P.CH_KNOB_Y[0] + P.CH_KNOB_Y[1]) / 2, P.CH_KNOB[1])           # the middle of the charging handle's knob
KNOB_ROOT = (P.CH_KNOB[0], P.CH_SEAT_Y, P.CH_KNOB[1])
FORE_HOLD = (P.FORE_HOLD_X, 0.0, P.HG_Z)
REAR_APERTURE = (P.APERTURE_X, 0.0, P.SIGHT_Z)
RAIL_MID = (P.RAIL_SLOT_X0 + P.RAIL_PITCH * (P.RAIL_SLOTS - 1) / 2, 0.0, P.RAIL_Z)
MAG_DROP = 9.0                         # how far below MagWell a released magazine is shown
RELEASE = (P.REL_OUTLINE[0][0], 0.0, 1.30)                                           # the middle of the paddle's rear face
SAFETY = (P.SAFE_XZ[0], 0.0, P.SAFE_XZ[1])
RISER_DEG = P.RISER_DEG                # the guard's lean
GRIP_MID = P.grip_pt(2.4, P.GRIP_DEPTH / 2)                                           # the middle of the hand on the pistol grip


def _cut_at(obj, z):
    """Every x at which the object's edges cross the plane at height z."""
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return [a.lerp(b, (z - a.z) / (b.z - a.z)).x for a, b in ((pts[e.vertices[0]], pts[e.vertices[1]]) for e in obj.data.edges)
            if (a.z - z) * (b.z - z) < 0.0]


def _front_at(obj, z):
    """The foremost x of the object's cut through the plane at height z."""
    xs = _cut_at(obj, z)
    return max(xs) if xs else None


def _world(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


class AssaultG3(Weapon):
    id = 'assault_g3'
    name = 'AssaultG3'         # asset stem: SKM_AssaultG3, SM_AssaultG3, T_AssaultG3_BC, MI_AssaultG3
    tag = 'AS3'                # prefix of this weapon's collections in the .blend: AS3_LP, AS3_HP, AS3_GAME
    # the look's two choices (surface.STEEL, surface.WOOD): nitrided steel parts on the olive shell
    finish = 'nitride'
    # the lettering is filled with paint: white, and red for FIRE (kit.text_solid's ink 1)
    paint = ('white', 'red')
    design = ('fictional bullpup rifle: the action and the magazine behind the pistol grip in one olive polymer shell that runs '
              'from the butt pad to the handguard\'s nose, a rail along its flat top with a clamped aperture sight and front post, '
              'a guard for the whole hand, a black alloy top cover with a shut line, a charging handle on the left of the handguard, rubber '
              'cheek, grip and hold pads, steel hardware, a slotted flash hider, detachable curved 30-round magazine, 5.6 mm cartridge of '
              'our own; no real maker or markings')
    frame_note = ('the game weapon frame as Unreal reads it: origin at the grip (the hold on the pistol grip), +X muzzle, '
                  '+Y right, +Z up, cm. (In Blender, where the mesh is authored, the same frame has +Y on the weapon\'s left.)')

    texture_size = 4096
    # the bake's edge masks by the centimetre (docs/look.md, "Edge masks by the centimetre") instead of fp_convex(): tried at 47 px/cm:
    # the cover matched fp_convex (0.44 / 1.17 % bright against 0.42 / 1.15), but the rail, the sights
    # and the charging handle wore a third more (4.3 / 4.6 / 13.1 % against 3.0 / 3.8 / 10.0), the rear sight's ears in pale
    # specks in the aiming view, and the butt pad less. Not better, so off: None keeps the masks as baked, widened by fp_convex()
    edge_px_cm = None
    paint_wear = 0.18                  # pass 3b: 0 fresh paint, 1 mostly gone (the default 0.35 took the lettering's strokes out at 2048)
    # pass 3b: texel density by builder, relative to the rest (surface.uv.pack): what is seen up close in first person gets 1.5 times the
    # rest; the magazine and its rounds, the grip and the butt pad, which are seen small or from afar, less. (uv: texel density tests every part against
    # target * weight with the target the area-weighted rms of all of them, so the weights must average out near 1: their rms at most 1.11.) Were all 1.0: 49.9 px/cm at 45 % coverage
    density = {'rear_sight': 1.5, 'rail': 1.5, 'cheek_pad': 1.5, 'charging_handle': 1.5, 'front_sight': 1.4, 'shell': 1.05,
               'magazine': 0.8, 'mag_rounds': 0.8, 'grip': 0.9, 'pad': 0.9}
    # ==== UV DENSITY (begin) texels where the first-person player looks, and a tighter pack (PLAYBOOK "UVs").
    # Replaces `density` above (the per-builder weights, whose rms had to stay under 1.11): the zones below say it by place
    density = {}
    uv_pack = 'tight'                  # the tool's packer: it fills the hollows Blender's leaves (at the same margin, 46 -> 55 % of the sheet)
    # 7 px round each island (14 between two, was 20): the bake pads every island 24 px, the neighbours meet halfway, and a 14 px gap keeps
    # mip 2 (1024 px) free of the neighbour's colour under bilinear filtering, as 20 did (mip 3 needs 30 and was never clean)
    uv_margin = 0.0017
    texel_hidden = 0.45                # faces hidden in every pose (rest, bolt back, charge, reload): between parts, in the well, the bore, the bolt
    texel_zones = [                    # the last that matches wins; 1 is everything not named
        TexelZone(0.5, (-40.0, -9.0, -20.0), (45.0, 9.0, 20.0), facing='-Z', note='the underside'),
        TexelZone(0.6, builders='pad', note='the butt pad: under the eye, out of the frame'),
        TexelZone(0.8, builders='grip', note='the grip and the guard: under the hand'),
        # the sights (pass 4): in the aiming view the rear sight is 8 to 15 cm from the eye, so it gets the most; the front sight, 28 cm
        # further on, needs less. Measured on pass 4: 2.2 costs everything else 1.1 px/cm, the front sight's 1.6 another 0.2 (55.4 left for 1)
        TexelZone(1.6, builders='front_sight', note='the front sight'),
        TexelZone(2.2, builders='rear_sight', note='the rear sight: serrations and aperture in the aiming view'),
        TexelZone(1.6, builders=('rail', 'charging_handle', 'cheek_pad'), note='rail, charging handle, cheek saddle'),
        TexelZone(1.6, (P.CV_X0 - 0.5, -4.0, P.TOP_Z - 2.5), (P.NOSE_X + 0.5, 5.0, P.TOP_Z + 2.0), facing=('+Z', '+Y'), builders='shell',
                  note='the cover\'s top and left shoulder'),
        TexelZone(1.6, (2.0, -4.0, P.LIP_Z - 0.4), (P.NOSE_X + 0.5, 5.0, P.TOP_Z), facing='+Y', builders='shell', note='the fore-end\'s left'),
    ]
    # ==== UV DENSITY (end)
    # the bake rounds every edge of a kind by this much (cm): a wider break on the polymer than the default 0.035 and the steel's 0.030. Set in the
    # forms pass: the only look change besides the new forms
    edge_break = {'polymer': 0.10, 'steel': 0.045, 'dark': 0.035, 'bright': 0.04, 'alloy': 0.035, 'rubber': 0.07}
    budget = (15000, 45000)            # pass 3 (was 30000): the cover's shut line, the pads, the sights and the hardware are real geometry
    # pass 3: seven surface kinds, one code each (bake.Kind): wood's code, which no part of this gun uses, is now rubber; copper's code is the cover's alloy
    # (the bullets' copper tips are told from their brass cases by position, in surface())
    kinds = {'steel': B.KINDS['steel'], 'bright': B.KINDS['bright'], 'dark': B.KINDS['dark'], 'polymer': B.KINDS['polymer'],
             'brass': B.KINDS['brass'], 'alloy': B.Kind((0, 1, 1), 0.040), 'rubber': B.Kind((0, 1, 0), 0.070)}
    lods = ((1, 0.5), (2, 0.25))

    # ---- where the gun is touched (surface.zones), cm in the weapon frame (+Y its left). A right-handed shooter: the cheek
    #      on the butt's left, the support hand under the handguard. A reading of how a bullpup is held and set down
    handled = [
        Zone((P.CV_X0 - 0.2, -P.CP_HW, P.TOP_Z - 0.4), (P.CV_X0 + 7.0, P.CP_HW, P.TOP_Z + 0.3), 0.45, 0.35, note='the cover\'s rear shoulder, where the cheek and the sight are touched'),
        Zone((GRIP_MID[0] - 1.9, -2.1, GRIP_MID[1] - 5.0), (GRIP_MID[0] + 1.9, 2.1, GRIP_MID[1] + 5.0), 1.0, 0.8, tilt=-P.GRIP_RAKE_DEG,
             note='the firing hand round the pistol grip'),
        Zone((5.0, -0.6, 1.5), (7.4, 0.6, 4.6), 0.8, 0.4, note='the trigger finger'),
        Zone((P.SAFE_XZ[0] - 1.0, -3.0, P.SAFE_XZ[1] - 1.0), (P.SAFE_XZ[0] + 1.0, 3.0, P.SAFE_XZ[1] + 1.0), 1.0, 0.6,
             note='the thumb on the safety button, from either side'),
        Zone((P.FORE_HOLD_X - 5.5, -2.7, P.LIP_Z - 0.5), (P.NOSE_X - 0.5, 2.7, P.BZ - 0.3), 0.9, 1.0,
             note='the support hand under and round the handguard'),
        Zone((P.CH_SLOT_X[0] - 0.6, 1.0, P.CH_Z[0] - 0.55), (P.CH_SLOT_X[1] + 0.8, 4.2, P.CH_Z[1] + 0.55), 1.0, 0.3,
             note='the charging handle\'s knob and the lips of its slot, on the left'),
        Zone((P.CHEEK_X[0] + 1.0, 0.6, P.CHEEK_Z0 - 0.2), (P.CHEEK_X[1] + 3.0, 2.8, P.TOP_Z + 0.2), 0.7, 1.5,
             note='the cheek on the butt\'s left'),
        Zone((P.WELL_X[0] - 1.6, -2.8, P.WELL_Z[0] - 0.6), (P.WELL_X[1] + 0.7, 2.8, P.WELL_Z[1] + 0.8), 0.9, 0.8,
             note='the well\'s mouth and the release paddle: magazine changes'),
        Zone((P.MAG_X0 - 2.2, -2.0, -12.8), (P.MAG_X1 + 3.8, 2.0, P.WELL_Z[0] - 1.2), 0.7, 1.0, note='the magazine, gripped to change it'),
        Zone((P.MAG_X0 - 2.6, -2.0, -14.0), (P.MAG_X1 + 4.2, 2.0, -10.6), 1.0, 0.8, note='the magazine\'s floor: set down on it'),
        Zone((P.PAD_X[0] - 0.5, -2.6, P.TOE_Z - 0.8), (P.BUTT_X + 2.4, 2.6, P.TOE_Z + 1.6), 0.9, 1.0, note='the butt\'s toe on the ground'),
        Zone((P.PAD_X[0] - 0.5, -2.6, P.TOP_Z - P.COMB_HEEL - 1.4), (P.BUTT_X + 2.0, 2.6, P.TOP_Z + 0.5), 0.8, 1.0, note='the butt\'s heel'),
        Zone((0.5, -1.6, P.GUARD_Z - 0.6), (10.5, 1.6, P.GUARD_Z + 1.0), 0.6, 0.8, note='the guard\'s strap, rested on'),
        Zone((P.HIDER_X[1] - 1.6, -1.6, P.BZ - 1.6), (P.HIDER_X[1] + 0.5, 1.6, P.BZ + 1.6), 0.5, 0.6, note='the muzzle, leant on'),
    ]
    # polymer moulded smooth beside the grained shell (the raised cheek panels and the well's collar), and stippled where a
    # hand needs purchase (the fore-end's sides under the vents)
    smooth = [
        Zone((P.WELL_X[0] - P.WELL_DRAFT[0], -3.0, P.WELL_Z[0] - 0.2), (P.WELL_X[1] + P.WELL_DRAFT[1], 3.0, P.WELL_Z[1] + P.WELL_COLLAR_H),
             1.0, 0.2, note='the well\'s collar'),
    ]
    textured = [
        Zone((9.5, -3.0, P.LIP_Z - 0.4), (P.NOSE_X - 0.2, 3.0, P.VENT_Z[0] - 0.1), 1.0, 0.15, note='the fore-end\'s hold, under the vents'),
    ]
    # where the black rubber is stippled (its own list: the olive polymer must not take these boxes' stipple too)
    rubber_textured = [
        Zone((P.grip_pt(4.75, 3.3)[0] - 0.5, -1.15, P.grip_pt(4.75, 3.3)[1] - 2.4), (P.grip_pt(4.75, 3.3)[0] + 0.7, 1.15, P.grip_pt(4.75, 3.3)[1] + 2.4),
             1.0, 0.1, tilt=-P.GRIP_RAKE_DEG, note='the grip insert\'s back strap: stipple (its sides are checkered)'),
        Zone((P.CP_X[0] - 0.2, -2.5, 6.8), (P.CP_X[1] + 0.2, 2.5, P.TOP_Z + 0.6), 1.0, 0.05, note='the cheek pad: stipple between its ribs'),
        Zone((P.PAD_X[0] - 0.3, -P.PAD_HW - 0.3, P.PAD_Z[0] - 0.3), (P.BUTT_X, P.PAD_HW + 0.3, P.PAD_Z[1] + 0.3), 1.0, 0.05, note='the butt pad\'s face'),
    ]

    # ==== TEXFORGE (begin) painted texture sets and decals (PLAYBOOK "Textures and look"). They are not in the repository:
    # weapons/assault_g3/painted/ says how to make them. Without them the finishes keep their procedural patterns and the decals
    # are left out (the texture stage says which were not found, and where it looked)
    # the tiling sets this weapon lays on (surface.material_dirs: textures/, <asset root>/_materials/, the setting `materials`)
    tex_sets = ('poly_mould', 'rubber', 'anodised', 'phosphate')
    SCRAPED = (0.135, 0.140, 0.105)        # olive polymer abraded: paler, greyer, the glass fibres showing
    OCHRE = (0.25, 0.155, 0.035)           # a dull ochre paint pen, dirtied (linear)
    # a few marks that tell where this rifle has been: a rack number, an armoury label, a zeroing mark, oil and scrapes. The
    # pictures are texforge decals; the boxes are cm in the weapon frame (+Y its left), shallow along the side they are put on from
    decals = [
        Decal('stencil_07', (-28.45, 1.0, 4.85), (-26.15, 3.4, 6.95), '+Y', strength=0.82, colour=(0.40, 0.395, 0.36), rough=0.72, metal=0.0,
              thick=0.25, wear=0.95, note='(look pass, p4: was strength 0.88, colour (0.44, 0.43, 0.40), wear 0.65: worn through more) ''the rack number, stencilled in white on the butt\'s left, between the flutes and the pad (it was a '
              'paint-filled cut; parts.py no longer cuts it)'),
        # (look pass, p4) the stencil worn through: streaks of the olive scratched back across its lower rear, where a slung butt rubs
        Decal('scrape', (-28.9, 1.0, 4.45), (-26.7, 3.4, 6.35), '+Y', strength=0.70, colour=(0.050, 0.060, 0.024), rough=None, metal=0.0,
              note='the 07 rubbed through to the olive in streaks'),
        Decal('witness', (-12.75, 0.74, 11.45), (-11.95, 0.90, 12.30), '+Z', colour=OCHRE, rough=0.62, metal=0.0, thick=0.15, wear=0.30,
              note='a paint-pen line across the rear sight\'s clamp onto the rail: the zero is marked, so a moved sight shows. In the player\'s view'),
        Decal('witness', (-12.45, 0.74, 11.25), (-12.20, 0.90, 12.55), '-X', colour=OCHRE, rough=0.62, metal=0.0, thick=0.15, wear=0.30,
              note='the same line down the clamp\'s rear face'),
        # oil and dust that ran down from where the gun is oiled and what it breathes through: no colour of their own, only
        # darker, browner, and glossy in the wet core (the oil) and drier at the fringe (the dust it caught)
        Decal('leak_soft', (10.4, 1.0, 6.7), (12.2, 3.6, 9.17), '+Y', colour=None, darken=0.75, stretch=True, rough=(0.30, 0.70), wear=0.15,
              note='oil from the charging handle\'s slot, run down the cover and the handguard\'s left behind the vents. In the player\'s view'),
        # (a run down from the port read as a crack in the panel: what a port leaves is a soft smudge of soot)
        Decal('scrape_soft', (-13.6, -3.6, 6.3), (-9.4, -1.0, 8.05), '-Y', colour=None, darken=0.55, rough=0.72, wear=0.15,
              note='carbon from the ejection port, a soft smudge under its lower lip on the right'),
        Decal('leak_soft', (-5.45, 1.0, 3.3), (-4.35, 3.4, 5.35), '+Y', colour=None, darken=0.55, stretch=True, rough=(0.34, 0.70), wear=0.2,
              note='a little oil from the front takedown pin, on the left'),
        # pale scrapes where the rifle meets the ground, the gear and the magazine: polymer abraded to a paler, drier grey
        Decal('scrape_soft', (-29.6, 1.0, -0.75), (-26.8, 3.4, 1.05), '+Y', colour=SCRAPED, strength=0.8, rough=0.80,
              note='the butt\'s toe, grounded and dragged'),
        Decal('scrape_soft', (-29.8, -1.7, -1.4), (-27.0, 1.7, 0.2), '-Z', colour=SCRAPED, strength=0.8, rough=0.80,
              note='the butt\'s toe from underneath'),
        Decal('scrape_soft', (-15.6, 1.0, -0.2), (-12.6, 3.6, 1.8), '+Y', colour=SCRAPED, strength=0.7, rough=0.78,
              note='the magazine well\'s collar, scuffed by fast magazine changes'),
        Decal('scrape_soft', (18.3, -1.9, 4.3), (20.9, 1.9, 5.6), '-Z', colour=SCRAPED, strength=0.75, rough=0.80,
              note='the hand stop under the nose, rested on walls and sills (ahead of the rubber hold pad)'),
    ]
    # ==== TEXFORGE (end)

    # ---- the rig: a carbine's names (it has no sliding stock, so no Stock_Bone)
    bones = [
        ('Root_Bone1', None, (0.0, 0.0, 0.0)),
        ('Grip_Bone', 'Root_Bone1', (0.0, 0.0, 0.0)),
        ('Bolt_Bone', 'Grip_Bone', (P.BOLT_FACE_X, 0.0, P.BZ)),                   # on the bore axis, at the bolt's face
        ('ChargingHandle_Bone', 'Grip_Bone', KNOB_ROOT),                           # where the knob leaves the shell's left side
        ('Trigger_Bone', 'Grip_Bone', (P.TRIG_PIVOT[0], 0.0, P.TRIG_PIVOT[1])),
        ('Safety_Bone', 'Grip_Bone', SAFETY),
        ('MagRelease_Bone', 'Grip_Bone', RELEASE),
        ('Clip_Bone', 'Grip_Bone', P.MAG_TOP_CENTRE),
        ('MagAmmo_Bone', 'Clip_Bone', (P.MAG_CENTRE_X, 0.0, P.ROUND_TOP[2])),
        ('Ammo', 'Root_Bone1', (P.CART_X, 0.0, P.BZ)),                             # base of the chambered cartridge
    ]

    # ---- sockets: [(name, bone, position in Blender's frame, Unreal rotation (pitch, yaw, roll), what it means)]
    #      Blender's +Y is the weapon's LEFT, so the right-hand side is -Y here (and +Y in Unreal).
    sockets = [
        ('Muzzle', 'Grip_Bone', (P.MUZZLE_X, 0.0, P.BZ), (0.0, 0.0, 0.0), 'centre of the flash hider\'s front face, +X out of the barrel'),
        ('AmmoEject', 'Grip_Bone', ((P.PORT_X[0] + P.PORT_X[1]) / 2, -P.PORT_FLOOR_Y, (P.PORT_Z[0] + P.PORT_Z[1]) / 2), (0.0, 90.0, 0.0),
         'the ejection port on the right, BEHIND the grip; +X is the way a case leaves (to the right), +Z up'),
        ('MagWell', 'Grip_Bone', P.MAGWELL, (0.0, 0.0, 0.0),
         'centre of the magazine well\'s mouth, behind the grip; +Z up the magazine into the gun'),
        ('MagDrop', 'Grip_Bone', (P.MAGWELL[0], 0.0, P.MAGWELL[2] - MAG_DROP), (0.0, 0.0, 0.0),
         '%.0f cm below MagWell: where a released magazine is clear of the well' % MAG_DROP),
        ('BoltHandle', 'ChargingHandle_Bone', KNOB, (0.0, 0.0, 0.0),
         'middle of the charging handle\'s knob, on the left of the handguard: the grasp for charging'),
        ('ForeEnd', 'Grip_Bone', FORE_HOLD, (0.0, 0.0, 0.0),
         'underside of the handguard, between the hand guard and the hand stop: where the support hand holds'),
        ('SightFront', 'Grip_Bone', (P.FRONT_POST_X, 0.0, P.SIGHT_Z), (0.0, 0.0, 0.0), 'top of the front sight post'),
        ('SightRear', 'Grip_Bone', REAR_APERTURE, (0.0, 0.0, 0.0), 'centre of the rear sight\'s aperture'),
        ('Rail', 'Grip_Bone', RAIL_MID, (0.0, 0.0, 0.0), 'top of the rail, the middle of its free length: where an optic would sit'),
    ]

    motion = {
        'Bolt_Bone': 'open: translate -X by bolt_travel (%.1f cm), back into the butt. A shot cycles it there and back; the charging '
                     'handle stays forward' % P.BOLT_TRAVEL,
        'ChargingHandle_Bone': 'charge: translate -X by handle_travel (%.1f cm) along its slot; it takes Bolt_Bone back by bolt_travel '
                               '(the first %.1f cm is free play), then let both go forward' % (P.HANDLE_TRAVEL, P.HANDLE_TRAVEL - P.BOLT_TRAVEL),
        'Ammo': 'the chambered cartridge: it comes back with the bolt, then is thrown out at AmmoEject; scale to zero when the chamber is empty',
        'Trigger_Bone': 'pull: rotate %.0f deg about the lateral axis (the blade swings back)' % P.TRIG_PULL_DEG,
        'Safety_Bone': 'a button through the shell, bound at "safe" (it stands out on the left); "fire": translate %.2f cm to the right '
                       '(Unreal +Y), so that it stands out on the right' % P.SAFE_PRESS,
        'MagRelease_Bone': 'press: translate %.2f cm forward (+X), toward the magazine' % P.REL_PRESS,
        'Clip_Bone': 'the magazine; it leaves straight down (the MagWell socket\'s -Z) and is clear of the well after %.1f cm'
                     % (P.MAG_TOP - P.WELL_Z[0]),
        'MagAmmo_Bone': 'the two visible cartridges; scale to zero or hide when the magazine is empty',
    }

    # the magazine's own frame: origin at the top centre of its body, +Z up, +X toward the bullets' noses
    props = [Prop('Mag', MAG_PARTS, Matrix.Translation(Vector(P.MAG_TOP_CENTRE)),
                  'the dropped / inserted magazine; origin at the top centre of its body, +Z up, so on the MagWell socket it sits at '
                  'relative Z = %.3f cm' % (P.MAG_TOP - P.MAGWELL[2]))]

    # ---- what must travel clear of everything else (K.rot_y: positive degrees tip +Z toward -X, and +X toward +Z)
    moves = [
        Move('bolt travel', ('Bolt_Bone', 'Ammo'), lambda t: Matrix.Translation((-t, 0.0, 0.0)), (2.0, 4.5, P.BOLT_TRAVEL), unit='cm back',
             note='the chambered cartridge on the bolt face'),
        Move('charging handle', ('ChargingHandle_Bone',), lambda t: Matrix.Translation((-t, 0.0, 0.0)), (2.5, 5.0, P.HANDLE_TRAVEL),
             unit='cm back'),
        Move('magazine leaves', MAG_PARTS, lambda d: Matrix.Translation((0.0, 0.0, -d)), (1.0, 3.0, 6.0, 9.0), unit='cm down'),
        Move('trigger pull', ('Trigger_Bone',), lambda deg: K.rot_y(P.TRIG_PIVOT, -deg), (P.TRIG_PULL_DEG / 2, P.TRIG_PULL_DEG), unit='deg'),
        Move('safety', ('Safety_Bone',), lambda t: Matrix.Translation((0.0, -t, 0.0)), (P.SAFE_PRESS / 2, P.SAFE_PRESS), unit='cm to the right'),
        Move('magazine release', ('MagRelease_Bone',), lambda t: Matrix.Translation((t, 0.0, 0.0)), (P.REL_PRESS / 2, P.REL_PRESS),
             unit='cm forward'),
    ]

    # ---- poses for the review renders, in the bone's own axes, which are the weapon's
    poses = {
        'rest': {},
        'bolt_back': {'Bolt_Bone': {'loc': (-P.BOLT_TRAVEL, 0.0, 0.0)}, 'Ammo': {'loc': (-P.BOLT_TRAVEL, 0.0, 0.0)},
                      'Safety_Bone': {'loc': (0.0, -P.SAFE_PRESS, 0.0)}},
        'charge': {'Bolt_Bone': {'loc': (-P.BOLT_TRAVEL, 0.0, 0.0)}, 'Ammo': {'loc': (-P.BOLT_TRAVEL, 0.0, 0.0)},
                   'ChargingHandle_Bone': {'loc': (-P.HANDLE_TRAVEL, 0.0, 0.0)}},
        'reload': {'Bolt_Bone': {'loc': (-P.BOLT_TRAVEL, 0.0, 0.0)}, 'Ammo': {'scale': 0.0}, 'Clip_Bone': {'loc': (0.0, 0.0, -MAG_DROP)},
                   'MagRelease_Bone': {'loc': (P.REL_PRESS, 0.0, 0.0)}, 'Safety_Bone': {'loc': (0.0, -P.SAFE_PRESS, 0.0)}},
    }

    # ---- builders whose high-detail parts shade each other in the occlusion bake (parts that never move apart)
    ao_friends = {
        'shell': ['pad', 'cheek_pad', 'rail', 'grip', 'barrel', 'hardware'], 'pad': ['shell'], 'cheek_pad': ['shell'], 'grip': ['shell', 'hardware'], 'hardware': ['shell', 'grip'],
        'rail': ['shell', 'rear_sight', 'front_sight'], 'rear_sight': ['rail', 'shell'], 'front_sight': ['rail', 'shell', 'barrel'],
        'barrel': ['shell', 'flash_hider', 'front_sight'], 'flash_hider': ['barrel'],
        'magazine': ['mag_rounds'], 'mag_rounds': ['magazine'],
    }

    # ---- flat colours for the grey review renders, by object-name prefix
    palette = {
        'Shell': (0.24, 0.27, 0.17, 1), 'Grip': (0.20, 0.23, 0.14, 1), 'Pad': (0.07, 0.07, 0.08, 1), 'CheekPad': (0.07, 0.07, 0.08, 1), 'Rail': (0.14, 0.14, 0.16, 1),
        'Sight': (0.18, 0.18, 0.20, 1), 'Hardware': (0.50, 0.50, 0.53, 1), 'Barrel': (0.26, 0.27, 0.30, 1), 'FlashHider': (0.20, 0.21, 0.24, 1),
        'Bolt': (0.72, 0.72, 0.70, 1), 'ChargingHandle': (0.40, 0.41, 0.44, 1), 'Trigger': (0.50, 0.50, 0.52, 1),
        'Safety': (0.55, 0.55, 0.57, 1), 'MagRelease': (0.55, 0.55, 0.57, 1),
        'Magazine': (0.32, 0.33, 0.36, 1), 'MagRounds': (0.80, 0.62, 0.25, 1), 'Round': (0.80, 0.62, 0.25, 1),
    }

    # ---- extra review sheets framed on a box (cm)
    closeups = {'action': ((-21.0, -4.0, -0.5), (-3.0, 4.0, 15.5)), 'muzzle': ((17.0, -3.0, 3.5), (40.0, 3.0, 13.0)),
                'grip': ((-4.0, -3.0, -7.0), (14.0, 3.0, 7.5), ['left', 'right', 'q_front_l', 'q_rear_r']),
                'butt': ((-32.5, -3.0, -1.5), (-14.0, 3.0, 11.5), ['left', 'rear', 'q_rear_l']),
                'top': ((-14.0, -3.5, 9.5), (20.5, 3.5, 15.5), ['top', 'fp', 'q_rear_l']),
                'magazine': ((-17.5, -3.0, -12.8), (-4.0, 3.0, 5.0), ['left', 'q_front_r']),
                'handguard': ((2.0, -4.0, 4.0), (23.0, 4.0, 12.5), ['left', 'q_front_l']),
                'whole': ((-33.0, -4.5, -1.0), (40.0, 4.5, 16.0), ['top', 'rear', 'q_front_r', 'bottom']),
                'toe': ((-0.5, -2.8, -6.6), (5.0, 2.8, -3.8), ['left', 'q_front_l', 'q_front_r', 'q_rear_r'])}
    pose_closeup = None                               # the magazine moves too: the whole gun in every pose
    pose_views = ('right', 'q_rear_l')                # the ejection port is on the right, the charging handle on the left

    # ---- the design brief, checked against the mesh: label: (low, high) cm, measured in measure()
    brief = {'overall length': (69.5, 71.0), 'bolt face to muzzle': (45.0, 46.5), 'length of pull': (36.5, 39.0), 'height': (26.0, 28.5),
             'width': (5.7, 6.4)}      # was (5.0, 6.0): the shell is now 4.4 wide, 4.9 at the well's rim (it was 3.8)

    # ------------------------------------------------------------------------------------------------------------ parts
    def builders(self):
        return dict(PT.BUILDERS)

    def hp_kinds(self, obj):
        """The surface kinds on one high-detail part, and which of its faces is which (set here from where each face is). Shell: polymer, the
        cover's alloy (every face above its stepped lower edge, from its rear end on), the cheek pad and the hold pad (rubber), the floors of
        the vents (dark: something dark behind them). Grip: polymer, and the rubber of its side inserts and its back strap insert. Pad: the
        rubber and, behind it, the hard spacer plate (dark). The cartridges: brass (the bullets' copper is told by position, in surface())."""
        kind = obj.get('mat', 'steel')
        name = obj.name
        if name.startswith('Shell'):
            return self._split(obj, ['polymer', 'alloy', 'rubber', 'dark'], self._shell_index)
        if name.startswith('Grip'):
            return self._split(obj, ['polymer', 'rubber'], self._grip_index)
        if name.startswith('SightRear'):
            return self._split(obj, ['steel', 'bright'], self._rear_index)
        if name.startswith('Pad'):
            return self._split(obj, ['rubber', 'dark'], self._pad_index)
        return [kind]

    @staticmethod
    def _split(obj, kinds, index):
        """Give every face of obj the slot index(centre, normal) says; returns kinds."""
        me = obj.data
        n = len(me.polygons)
        cen = np.empty(n * 3, dtype=np.float32)
        nor = np.empty(n * 3, dtype=np.float32)
        me.polygons.foreach_get('center', cen)
        me.polygons.foreach_get('normal', nor)
        got = index(cen.reshape(n, 3).astype(np.float64), nor.reshape(n, 3).astype(np.float64))
        me.polygons.foreach_set('material_index', got.astype(np.int32))
        me.update()
        return kinds

    @staticmethod
    def _rear_index(c, nrm):
        """The rear sight's bare steel (kind 1): the pivot pin's two ends, the detent ball (everything else is phosphate)."""
        x, y, z = c[:, 0], c[:, 1], c[:, 2]
        out = np.zeros(len(x), dtype=np.int64)
        e1 = P.REAR_EAR[1]
        near_pin = (np.abs(x - P.DRUM_X) < 0.27) & (np.abs(z - P.DRUM_Z) < 0.27)
        out[near_pin & (y < -(e1 + 0.125))] = 1                                           # the pin's end (right), beyond the C-clip
        out[near_pin & (y > e1 + 0.10)] = 1                                               # the domed head (left)
        out[(np.abs(x - P.DRUM_X) < 0.15) & (np.abs(z - (P.DRUM_Z + 0.60)) < 0.15) & (y < -e1 - 0.02)] = 1     # the detent ball
        return out

    @staticmethod
    def _shell_index(c, nrm):
        x, y, z = c[:, 0], c[:, 1], c[:, 2]
        out = np.zeros(len(x), dtype=np.int64)
        zc = np.array([P.cover_z(v) for v in x])
        out[(x >= P.CV_X0 - 0.001) & (z >= zc + 0.02)] = 1                                   # the cover
        out[(x > P.HOLD_X[0] - 0.05) & (x < P.HOLD_X[1] + 0.05) & (np.abs(y) < P.HOLD_HW + 0.05) & (z < P.HG_Z - 0.04)] = 2     # the hold pad
        for i in np.nonzero((x > P.VENT_X0 - 0.1) & (x < P.VENT_X0 + P.VENT_PITCH * P.VENTS + P.VENT_LEAN + 0.2) & (z > P.VENT_Z[0] - 0.1) & (z < P.VENT_Z[1] + 0.1))[0]:
            sy = P.side_y(float(x[i]), float(z[i]))
            if sy is not None and abs(y[i]) < sy - 0.30:
                out[i] = 3                                                                  # the floor of a vent
        slot = (x > P.CH_SLOT_X[0] - 0.02) & (x < P.CH_SLOT_X[1] + 0.02) & (z > P.CH_Z[0] - 0.05) & (z < P.CH_Z[1] + 0.05) & (y > P.CH_SLOT_FLOOR - 0.03) & (y < 3.2)
        out[slot] = 3                                                                       # pass 4: the charging slot is lined dark (its floor, walls and ends)
        return out

    @staticmethod
    def _inside(poly, a, b):
        """Even-odd test of the points (a, b) against the closed polygon [(a, b)]."""
        inside = np.zeros(len(a), dtype=bool)
        for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]):
            hit = ((z0 > b) != (z1 > b)) & (a < (x1 - x0) * (b - z0) / ((z1 - z0) if z1 != z0 else 1e-12) + x0)
            inside ^= hit
        return inside

    def _grip_index(self, c, nrm):
        """The overmoulded insert: rubber for every face whose place on the grip (t cm down the strap, w cm round it from the back strap's middle)
        lies inside the border's outline widened by half the groove, so the groove itself is rubber; the rest of the grip is olive."""
        out = np.zeros(len(c), dtype=np.int64)
        t, phi, off = PT.grip_inverse(c)
        poly = PT.insert_outline(P.INS_GW / 2.0)
        out[self._inside(poly, t, phi * P.INS_KW) & (off < 0.16)] = 1
        return out

    @staticmethod
    def _pad_index(c, nrm):
        out = np.zeros(len(c), dtype=np.int64)
        shift = np.array([P.rake(P.BUTT_X, v) - P.BUTT_X for v in c[:, 2]])
        out[(c[:, 0] - shift) > P.BUTT_X - P.SEAT - P.SPACER_T + 0.01] = 1                   # the spacer plate: ahead of the pad's own front face
        return out

    # ------------------------------------------------------------------------------------------------------------- look
    def seams(self, obj):
        if obj.name == 'Shell':
            return PT.underside_seam()                # the shell's rings start at its underside's middle: one seam along it, and up the steps of the well
        if obj.name == 'Grip':
            return PT.grip_seam()                     # the grip and the guard are one loop: one seam along its outside
        if obj.name in ('Bolt', 'Barrel', 'FlashHider'):
            return PT.bore_seam()
        if obj.name == 'Magazine':
            return PT.mag_seam()
        return None                                   # the grip, the pad and the sights are cut up by their own hard edges

    # ==== TEXFORGE (begin)
    def images(self):
        return S.texforge_sets(self, *self.tex_sets)

    # ---- where this rifle's wear goes: the places the named finishes (weaponforge/finish.py) cannot know from the declared zones
    def top_zones(self):
        """Bright thin wear on black metal: the rail lands' and the sight ears' top corners (finish.black_metal_life `tops`)."""
        return [Zone((P.RAIL_X[0], -P.RAIL_HW, P.RAIL_Z - 0.08), (P.RAIL_X[1], P.RAIL_HW, P.RAIL_Z + 0.05), 1.0, 0.02),
                Zone((P.REAR_X[0], -1.3, P.SIGHT_Z - 0.3), (P.REAR_X[1], 1.3, P.SIGHT_Z + 1.2), 1.0, 0.02),
                Zone((P.FRONT_X[0], -1.3, P.SIGHT_Z - 0.3), (P.FRONT_X[1], 1.3, P.SIGHT_Z + 1.2), 1.0, 0.02)]

    def slide_zones(self):
        """Long fine scratches on the alloy (finish.anodised_alloy `slides`): where the charging handle runs and an optic slides."""
        return [Zone((P.CH_SLOT_X[0] - 1.5, 1.0, P.CH_Z[0] - 0.5), (P.CH_SLOT_X[1] + 1.0, 4.0, P.TOP_Z + 0.1), 0.9, 0.6,
                     note='the cover beside the charging slot: the hand and the knob run along it'),
                Zone((-6.0, -1.6, P.RAIL_Z - 0.08), (P.RAIL_X[1] - 2.0, 1.6, P.RAIL_Z + 0.05), 1.0, 0.03,
                     note='the rail\'s lands where an optic is slid on and off'),
                Zone((P.CV_X0, -2.6, P.TOP_Z - 0.6), (P.NOSE_X, 2.6, P.TOP_Z + 0.3), 0.30, 0.5,
                     note='the cover\'s top and shoulders: a few')]

    def grime_zones(self):
        """Grime on the olive (finish.moulded_polymer `grime`): round the vents, the controls, the cover's shut line and the pins."""
        boxes = [Zone((P.VENT_X0 - 0.5, -4.0, P.VENT_Z[0] - 0.5), (P.VENT_X0 + P.VENT_PITCH * P.VENTS + 0.8, 4.0, P.VENT_Z[1] + 0.5), 1.0, 0.5,
                      note='the vents'),
                 Zone((P.SAFE_XZ[0] - 0.9, -4.0, P.SAFE_XZ[1] - 0.9), (P.SAFE_XZ[0] + 0.9, 4.0, P.SAFE_XZ[1] + 0.9), 1.0, 0.5, note='the safety'),
                 Zone((-16.9, -3.0, 0.3), (-15.3, 3.0, 2.9), 0.9, 0.5, note='the magazine release'),
                 Zone((P.CH_SLOT_X[0] - 0.4, 1.0, P.CH_Z[0] - 0.5), (P.CH_SLOT_X[1] + 0.4, 4.0, P.CH_Z[1] + 0.5), 0.8, 0.4, note='the charging slot')]
        boxes += [Zone((px - 0.7, -4.0, pz - 0.7), (px + 0.7, 4.0, pz + 0.7), 1.0, 0.4, note='a pin') for px, pz in P.PINS]
        for x0 in np.arange(P.CV_X0, P.NOSE_X, 2.0):                  # the cover's shut line, in steps along it
            zs = [P.cover_z(v) for v in np.linspace(x0, min(x0 + 2.0, P.NOSE_X), 5)]
            boxes.append(Zone((x0, -4.0, min(zs) - 0.35), (min(x0 + 2.0, P.NOSE_X), 4.0, max(zs) + 0.10), 0.8, 0.3, note='the shut line'))
        boxes.append(Zone((P.CV_X0 - 0.5, -4.0, P.TOP_Z - 3.0), (P.CV_X0 + 0.2, 4.0, P.TOP_Z + 0.3), 0.8, 0.3, note='the shut line across'))
        return boxes

    # ---- (look pass at the p4 texel density)
    def fp_convex(self, s):
        """The bake's convex-edge mask, widened where the UV DENSITY zones put more texels than before. The mask is worked out per
        texel (maps.process), so a bevel saturates it over the same few TEXELS at any density: at 1.6 times the texels it is 1/1.6
        as wide in cm, and the edge wear drawn from it came out thin (measured 0.056 -> 0.040 per cm2 on the cover). Here it is
        the most of itself and of its neighbours `reach` texels away (four taps), with `reach` set by how much denser each place is
        than in g3_final (pass 3b's weights; px/cm measured on the rasterised game mesh): the cover's top and left shoulder 47 -> 89
        (1.4 texels), the rear sight 67 -> 107 (1.4), the fore-end's left (1.0), the front sight 63 -> 78 (0.45), the rail and the
        charging handle 67 -> 77..88 (0.35). Nothing elsewhere: the underside and the butt pad, which got sparser, keep the mask as
        baked. TIED TO THE UV DENSITY zones above: change those and these boxes and reaches want retuning. (The lasting fix is in the
        tool: maps.process working the edge masks out per cm, its curvature gain and blur radius scaled by the local texel density.)"""
        g = s.g
        nx, ny, nz = g.xyz(g.new('ShaderNodeNewGeometry').outputs['True Normal'])
        up, left = g.step(nz, 0.40, 0.60), g.step(ny, 0.40, 0.60)
        m_poly, m_alloy = s.mask('polymer'), s.mask('alloy')
        top = P.TOP_Z + P.CV_PROUD + 0.05                          # the cover's top; the rail stands on it
        cover = S.zones(s, [Zone((P.CV_X0 - 0.5, -4.0, P.TOP_Z - 2.5), (P.NOSE_X + 0.5, 5.0, top), 1.4, 0.05)], 'fp_cover')
        cover = g.mul(g.mul(cover, g.maxf(up, left)), g.add(m_poly, m_alloy, True))
        fore = S.zones(s, [Zone((2.0, -4.0, P.LIP_Z - 0.4), (P.NOSE_X + 0.5, 5.0, P.TOP_Z), 1.0, 0.05)], 'fp_fore')
        fore = g.mul(g.mul(fore, left), m_poly)
        sights = S.zones(s, [Zone((P.REAR_X[0] - 0.1, -1.7, top), (P.REAR_X[1] + 0.1, 1.7, P.SIGHT_Z + 1.6), 1.4, 0.05),
                             Zone((P.FRONT_X[0] - 0.1, -1.7, top), (P.FRONT_X[1] + 0.1, 1.7, P.SIGHT_Z + 1.6), 0.45, 0.05)], 'fp_sights')
        sights = g.mul(sights, g.inv(m_alloy))                      # not the rail under them
        rail = S.zones(s, [Zone((P.RAIL_X[0], -P.RAIL_HW - 0.1, top - 0.1), (P.RAIL_X[1], P.RAIL_HW + 0.1, P.RAIL_Z + 0.1), 0.35, 0.05)], 'fp_rail')
        rail = g.mul(rail, m_alloy, True)
        ch = S.zones(s, [Zone((P.CH_KNOB[0] - 1.2, P.CH_SLOT_FLOOR - 0.2, P.CH_KNOB[1] - 1.0), (P.CH_KNOB[0] + 1.2, P.CH_KNOB_Y[1] + 0.3, P.CH_KNOB[1] + 1.0),
                              0.35, 0.05)], 'fp_ch')
        ch = g.mul(ch, s.mask('dark'), True)
        reach = g.maxf(g.maxf(g.maxf(cover, fore), g.maxf(sights, rail)), ch)
        img = s.images['masks']
        step = g.mul(reach, 1.0 / img.size[0])
        uv = g.new('ShaderNodeTexCoord').outputs['UV']
        out = s.convex
        for ax, sign in ((0, 1.0), (0, -1.0), (1, 1.0), (1, -1.0)):
            off = g.new('ShaderNodeCombineXYZ')
            g.set(off.inputs[ax], g.mul(step, sign))
            tap = g.image(img, g.vmath('ADD', uv, off.outputs[0]))
            out = g.maxf(out, g.rgb(tap.outputs[0])[1])
        return out
    # ==== TEXFORGE (end)

    def surface(self, s):
        """The look: a named finish (weaponforge/finish.py, docs/look.md, "Named finishes") per material, given this rifle's places, then the
        stack. Materials (Weapon.kinds, bake.KINDS: the kind is in the bake source, the place of a finish is told by its mask):
          olive shell       moulded_polymer: the shell, the grip and the guard
          cover and rail    anodised_alloy: satin black hard-anodised alloy, thin bright lines on its corners
          black rubber      rubber: the butt pad, the cheek pad, the hold pad and the grip's overmoulded insert, never polished
          small steel       phosphate_parts (the base): hardware, trigger, controls; the sights and the pad's spacer (`dark`) black
          barrel            barrel_phosphate (told from the rest of the steel by where it is), fouled in the flash hider
          magazine          sheet_magazine: black phosphate, worn on its floor
          brass_case, copper_tip   the cartridges (the copper tips are told from their cases by position)"""
        g = s.g
        # (look pass, p4 density) every finish, the decals and the paint below read the edge mask widened where the texels got denser
        if not self.edge_px_cm:                    # (the per-cm edge masks, when on, replace the widening: never both)
            s.convex = self.fp_convex(s)
        tops = self.top_zones()
        # ---- the places in the weapon's frame, cm, that narrow a kind to one finish
        barrel_zone = S.zones(s, [Zone((P.NOSE_X - 0.8, -2.0, P.BZ - 2.2), (P.MUZZLE_X + 0.5, 2.0, P.BZ + 2.2), 1.0, 0.04)], 'barrel')
        mag_zone = S.zones(s, [Zone((-22.0, -3.0, -14.5), (-1.0, 3.0, P.WELL_Z[0] - 0.02), 1.0, 0.04)], 'magazine')
        # a cartridge's bullet is copper, its case brass: the chambered round is high (z about the bore's), the two in the magazine low
        sep = g.new('ShaderNodeSeparateXYZ')
        g.set(sep.inputs[0], s.pos)
        high = g.step(sep.outputs[2], 4.0, 5.0)
        tip_hi = g.step(sep.outputs[0], P.CART_X + P.CASE_LEN - 0.012, P.CART_X + P.CASE_LEN - 0.002)
        tip_lo = g.step(sep.outputs[0], P.ROUND_TOP[0] + P.CASE_LEN - 0.012, P.ROUND_TOP[0] + P.CASE_LEN - 0.002)
        copper_zone = g.add(g.mul(high, tip_hi), g.mul(g.inv(high), tip_lo), True)
        return F.look(s, [
            ('steel', 'phosphate_parts', dict(tops=tops)),
            ('steel', 'barrel_phosphate', dict(muzzle_x=P.MUZZLE_X, fouling_from=P.HIDER_X[0]), barrel_zone),
            # worn only on its floor, the one place it is set down
            ('steel', 'sheet_magazine', dict(handled=[Zone((P.MAG_X0 - 2.6, -2.0, -14.0), (P.MAG_X1 + 4.2, 2.0, -10.6), 1.0, 0.5)]), mag_zone),
            ('polymer', 'moulded_polymer', dict(fade_z=(-6.0, P.TOP_Z), grime=self.grime_zones())),
            ('alloy', 'anodised_alloy', dict(tops=tops, slides=self.slide_zones())),
            ('rubber', 'rubber'),
            ('brass', S.brass(s), None, g.inv(copper_zone)),
            ('brass', S.copper(s), None, copper_zone),
        ])

    # ----------------------------------------------------------------------------------------------------------- checks
    def measure(self, parts):
        lo, hi = CHK.bounds(list(parts.values()))
        _lo, h_hi = CHK.bounds([parts['FlashHider']])
        _lo, bolt_hi = CHK.bounds([parts['Bolt']])
        finger = _front_at(parts['Trigger'], 3.2)
        return {'overall length': hi.x - lo.x, 'height': hi.z - lo.z, 'width': hi.y - lo.y, 'bolt face to muzzle': h_hi.x - bolt_hi.x,
                'length of pull': (finger if finger is not None else 0.0) - lo.x}

    def socket_targets(self, parts):
        """Where the mesh itself puts a socket, so a socket typed from the wrong number is caught."""
        post = [p for p in _world(parts['SightFront']) if abs(p.y) < P.FRONT_POST_HW + 0.01]
        top = max(p.z for p in post)
        tip = [p for p in post if p.z > top - 0.01]
        hole = [p for p in _world(parts['SightRear']) if math.hypot(p.y, p.z - P.SIGHT_Z) < P.APERTURE_R + 0.02]
        knob = [p for p in _world(parts['ChargingHandle']) if p.y > P.CH_KNOB_Y[0] - 0.05]
        k_lo = Vector((min(p.x for p in knob), min(p.y for p in knob), min(p.z for p in knob)))
        k_hi = Vector((max(p.x for p in knob), max(p.y for p in knob), max(p.z for p in knob)))
        targets = {'Muzzle': CHK.face_centre(parts['FlashHider'], 0, 1.0, band=0.01),
                   'SightFront': sum(tip, Vector()) / len(tip), 'BoltHandle': (k_lo + k_hi) / 2}
        if hole:
            targets['SightRear'] = sum(hole, Vector()) / len(hole)
        return targets

    def checks(self, c):
        """Checks only this weapon has. c.by_name / c.on(bone) / c.off(bone) find parts; c.game is the rig once it exists."""
        _lo, hi = CHK.bounds([c.by_name['FlashHider']])
        c.add('frame: muzzle on +X', abs(hi.x - P.MUZZLE_X) < CHK.TOL, 'the flash hider ends at x %.2f (muzzle %.2f)' % (hi.x, P.MUZZLE_X))
        # the origin is in the grip: at x = 0 the grip runs from below it to above it
        grip = _world(c.by_name['Grip'])
        near = [p for p in grip if abs(p.x) < 1.5]
        ok = bool(near) and min(p.z for p in near) < 0.0 < max(p.z for p in near)
        c.add('frame: origin in the grip', ok, 'round x = 0 the grip runs from z %.2f to %.2f' % (min(p.z for p in near), max(p.z for p in near))
              if near else 'no grip round the origin')
        # the eye looks through the aperture at the post: nothing between them stands in that line
        x0, x1 = P.REAR_LEAF_X[1], P.FRONT_POST_X - 0.5
        top = max(p.z for name, o in c.by_name.items() if not name.startswith('Sight') for p in _world(o) if x0 < p.x < x1 and abs(p.y) < 0.5)
        c.add('sights: clear line', top < P.SIGHT_Z - 0.5, 'line of sight at z %.2f, the highest thing under it at %.2f' % (P.SIGHT_Z, top))
        hole = [p for p in _world(c.by_name['SightRear']) if math.hypot(p.y, p.z - P.SIGHT_Z) < P.APERTURE_R + 0.02]
        c.add('sights: the aperture is open', len(hole) >= 6, '%d vertices round a hole of radius %.2f on the line of sight' % (len(hole), P.APERTURE_R))

        # ---- what makes it a bullpup: everything of the action is behind the hand, measured on the meshes
        back_strap = min(p.x for p in grip if p.z > 0.0)
        _b_lo, bolt_hi = CHK.bounds([c.by_name['Bolt']])
        m_lo, m_hi = CHK.bounds([c.by_name['Magazine']])
        c.add('bullpup: the bolt face is behind the grip', bolt_hi.x < back_strap - 3.0,
              'the bolt face is at x %.2f, the grip\'s back strap at %.2f' % (bolt_hi.x, back_strap))
        heel = min(p.x for p in grip)
        c.add('bullpup: a hand\'s room between the magazine and the grip', heel - m_hi.x > 3.0,
              'the magazine\'s foremost point is at x %.2f, the grip\'s rearmost at %.2f: %.2f cm between' % (m_hi.x, heel, heel - m_hi.x))
        shell_lo, _s_hi = CHK.bounds([c.by_name['Shell']])
        # the butt's face is raked: measure the wall on the mesh, at the bore's height on the centre plane
        face = min(_cut_at(c.by_name['Shell'], P.BZ))          # where the shell's edges cross the bore's height: the rear face is a flat polygon with no vertex there
        wall = P.TUNNEL_X0 - face
        c.add('bullpup: a wall behind the carrier\'s tunnel', wall > 1.0,
              'the tunnel ends %.2f cm ahead of the butt\'s rear face at the bore\'s height (x %.2f)' % (wall, face))
        # the bolt: open, its face is behind the top cartridge in the magazine, and the carrier is still short of the tunnel's end
        behind = P.ROUND_TOP[0] - (P.BOLT_FACE_X - P.BOLT_TRAVEL)
        c.add('bolt: opens behind the magazine\'s top cartridge', behind > 0.3, 'open, the bolt face is %.2f cm behind the cartridge\'s base' % behind)
        room = (P.CARRIER_X[0] - P.HANDLE_TRAVEL) - P.TUNNEL_X0
        c.add('bolt: room in the butt', room > 0.1,
              'pulled back as far as the charging handle goes, the carrier\'s rear is %.2f cm short of the tunnel\'s end' % room)
        # the charging handle: its lug stays in its slot, and the knob stops short of the hand on the grip
        handle = _world(c.by_name['ChargingHandle'])
        slot = min(p.x for p in handle) - P.HANDLE_TRAVEL - P.CH_SLOT_X[0]
        c.add('charging handle: its slot is long enough', slot > 0.1, 'pulled back, the lug is %.2f cm short of the slot\'s rear end' % slot)
        # the guard: the fingers have room between the front strap and the guard's inside, measured at the origin's height
        cut = _cut_at(c.by_name['Grip'], 0.0)
        strap, inside = max([x for x in cut if x < 5.0] or [0.0]), min([x for x in cut if x > 5.0] or [0.0])
        blade = _front_at(c.by_name['Trigger'], 3.2)
        c.add('guard: room for the whole hand', inside - strap > 6.0 and inside - (blade or 0.0) > 2.5,
              'from the front strap to the guard\'s inside %.2f cm; from the trigger to the guard %.2f cm' % (inside - strap, inside - (blade or 0.0)))
        # the magazine holds what the brief says: two columns, each cartridge half a pitch below the last
        need = (P.MAG_ROUNDS - 1) * P.ROUND_PITCH_Z + 2 * P.CASE_R + 1.2
        c.add('magazine: room for %d rounds' % P.MAG_ROUNDS, P.MAG_LEN - P.MAG_LIP_T > need,
              '%.1f cm inside for %.1f cm of cartridges, follower and spring' % (P.MAG_LEN - P.MAG_LIP_T, need))
        # the butt: a pad stack (spacer plate and a crowned rubber pad) that stands proud of the shell's rear face, and a raked face
        pad_lo, pad_hi = CHK.bounds([c.by_name['Pad']])
        c.add('pad: the stack stands proud of the shell\'s rear face', shell_lo.x - pad_lo.x > 1.2,
              'the pad\'s rearmost point is x %.3f, the shell\'s %.3f: %.2f cm proud' % (pad_lo.x, shell_lo.x, shell_lo.x - pad_lo.x))
        # the cheek pad: a saddle standing CP_H proud of the comb along its whole length, with its lower edge on the left under the belt line and a
        # shorter drop on the right (the ribs are in the bake source, 0.11 deep: they are not in the game mesh)
        # (measured as the crest at each station along the comb: the rounded border step and the rounded ends fall away from the crest by design, so only the crest is 0.3)
        crest = {}
        for p in _world(c.by_name['CheekPad']):
            span = P.outline_span(p.x) if abs(p.y) < 3.2 else None
            if span is not None and p.z - span[1] > 0.1:                  # (the skin 0.07 under the comb is not the surface)
                crest[round(p.x, 1)] = max(crest.get(round(p.x, 1), 0.0), p.z - span[1])
        reach = (max(crest) - min(crest)) if crest else 0.0
        proud = [v for x, v in crest.items() if min(crest) + 0.05 < x < max(crest) - 0.05] or [0.0]      # (the outermost ring at each end is the rounded edge)
        c.add('cheek pad: a saddle 0.3 cm proud of the comb', len(proud) >= 3 and reach > 9.0 and all(0.26 < v < 0.34 for v in proud),
              'the crest stands %.2f to %.2f cm proud at %d stations over %.1f cm of the comb' % (min(proud), max(proud), len(proud), reach))
        low = {}
        for p in _world(c.by_name['CheekPad']):
            side = 'left' if p.y > 0.0 else 'right'
            low[side] = min(low.get(side, 99.0), p.z)
        c.add('cheek pad: down the left shoulder 3.5 cm or more, the right 2.5 cm', P.TOP_Z - low['left'] > 3.4 and 2.3 < P.TOP_Z - low['right'] < 3.2,
              'its lower edge is %.2f cm under the top on the left, %.2f on the right' % (P.TOP_Z - low['left'], P.TOP_Z - low['right']))
        toe = min(p.x for p in _world(c.by_name['Shell']) if p.z < P.TOE_Z + 1.0 and abs(p.y) < 1.0)
        rake = toe - shell_lo.x
        c.add('butt: the face is raked, toe forward of heel by 1 to 1.5 cm', 0.9 < rake < 1.6,
              'the shell\'s rearmost point at the toe is %.2f cm forward of its rearmost point' % rake)

    def collision(self, static, C):
        """Fourteen boxes for the world copy. Along the gun: the butt with its pad, the action's housing with the well, the
        flat over the grip, the handguard, the barrel. Under it: the magazine (pitched along its curve), the grip (pitched
        with its rake), the trigger, the guard's strap, the guard's riser (pitched with its lean). On it: the rear sight,
        the rail, the front sight, and the charging handle's knob on the left."""
        pts = C.points(static)
        end = P.mag_centre(P.MAG_LEN)
        mag_pitch = math.degrees(math.atan2(end[0] - P.MAG_CENTRE_X, P.MAG_STRAIGHT_Z - end[1]))     # the box's Z runs up its chord
        rear, front = P.WELL_X[0] - 0.02, P.WELL_X[1] + 0.02
        low, mouth, top = P.FCG_Z - 0.06, P.WELL_Z[0] - 0.05, P.TOP_Z + P.CV_PROUD + 0.02       # (the top cover stands proud of the flat)
        fore, nose = 11.20, P.NOSE_X + 0.01

        def riser(p):
            return (p.x > 9.0 and p.z < low) or (11.8 < p.x <= 13.2 and p.z < P.HG_Z - 0.005)

        def knob(p):
            return p.y > P.CH_BOX_Y and fore < p.x <= nose and p.z <= top

        def cheek(p):
            return p.x < P.CP_X[1] + 0.05 and p.z <= P.TOP_Z + P.CP_H + 0.05                     # the cheek pad is part of the butt

        body = [p for p in pts if (p.z <= top or cheek(p)) and not knob(p)]
        over = [p for p in pts if p.z > top and not cheek(p)]
        # the strap along the bottom is straight, so it has vertices only where it leaves the grip and where it starts to
        # curve: box the ones at the curve and run the box back to the grip's toe
        strap = C.aligned('guard', [p for p in body if 3.2 < p.x <= 9.0 and p.z < -4.0])
        more = (strap['centre'].x - strap['size'].x / 2) - P.grip_pt(P.GRIP_LEN, 0.0)[0]
        strap['centre'].x -= more / 2
        strap['size'].x += more
        return [C.aligned('butt', [p for p in body if p.x <= rear]),
                C.aligned('action', [p for p in body if rear < p.x <= front and p.z >= mouth]),
                C.pitched('magazine', [p for p in body if rear < p.x <= -4.0 and p.z < mouth], mag_pitch),
                C.aligned('hold', [p for p in body if front < p.x <= fore and p.z >= low]),
                C.pitched('grip', [p for p in body if -4.0 < p.x <= 3.2 and p.z < low], -P.GRIP_RAKE_DEG),
                C.aligned('trigger', [p for p in body if 3.2 < p.x <= 9.0 and -4.0 <= p.z < low]),
                strap,
                C.pitched('guard_riser', [p for p in body if riser(p)], -RISER_DEG),
                C.aligned('handguard', [p for p in body if fore < p.x <= nose and not riser(p)]),
                C.aligned('charging_handle', [p for p in pts if knob(p)]),
                C.aligned('barrel', [p for p in body if p.x > nose]),
                C.aligned('rear_sight', [p for p in over if p.x <= P.REAR_X[1] + 0.02]),
                C.aligned('rail', [p for p in over if P.REAR_X[1] + 0.02 < p.x < P.FRONT_X[0] - 0.02]),
                C.aligned('front_sight', [p for p in over if p.x >= P.FRONT_X[0] - 0.02])]

    def spec_extra(self, game):
        """Numbers the game side needs, written into the spec."""
        from weaponforge.rig import ue
        return {'dimensions_cm': {'bore_height': P.BZ, 'muzzle_x': P.MUZZLE_X, 'barrel_end_x': P.BARREL_END_X,
                                  'barrel_length': P.BARREL_END_X - P.BOLT_FACE_X, 'sight_line_z': P.SIGHT_Z,
                                  'sight_radius': P.FRONT_POST_X - REAR_APERTURE[0], 'rail_top_z': P.RAIL_Z,
                                  'bolt_travel': P.BOLT_TRAVEL, 'handle_travel': P.HANDLE_TRAVEL,
                                  'safety_press': P.SAFE_PRESS, 'trigger_pull_deg': P.TRIG_PULL_DEG, 'release_press': P.REL_PRESS,
                                  'cartridge_length': P.OAL, 'case_length': P.CASE_LEN, 'magazine_rounds': P.MAG_ROUNDS,
                                  'magazine_below_well': P.WELL_Z[0] - P.mag_centre(P.MAG_LEN + P.MAG_FLOOR_T)[1],
                                  'bolt_face_x': P.BOLT_FACE_X, 'butt_x': P.PAD_X[0]},
                'reload_targets': {'mag_well': ue(Vector(P.MAGWELL)), 'mag_axis': ue(Vector((0.0, 0.0, 1.0))),
                                   'bolt_handle': ue(Vector(KNOB)), 'bolt_axis': ue(Vector((1.0, 0.0, 0.0))),
                                   'fore_end': ue(Vector(FORE_HOLD)), 'mag_release': ue(Vector(RELEASE)),
                                   'selector': ue(Vector((P.SAFE_XZ[0], P.SAFE_TOP + P.SAFE_PROUD, P.SAFE_XZ[1])))}}


WEAPON = AssaultG3()
