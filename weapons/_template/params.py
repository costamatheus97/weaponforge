"""TemplateGun: every dimension in one place (pure Python, no bpy: the builders, the rig and the checks all read it).

Frame: the game's weapon frame as Blender sees it: origin at the grip (the middle of the hold), +X toward the muzzle, +Z up,
+Y the weapon's LEFT. Unreal gets (x, -y, z): +Y right there. Centimetres.

Start a weapon here: fix the datums (bore height, muzzle, grip) from the design brief first, then derive the rest from them, so
a change to one number moves everything that hangs off it.
"""
import math

# --- datums
BZ = 4.2                              # bore axis, z
SLIDE_X0, SLIDE_X1 = -2.6, 13.0       # slide rear and front faces
MUZZLE_X = SLIDE_X1 + 0.3

# --- slide
SLIDE_HW = 1.30
SLIDE_BOT, SLIDE_TOP = 3.3, 5.3
SLIDE_TRAVEL = 3.0
# the chamfer along each top edge, (x, size): it grows toward the muzzle in a 2.5 cm ramp with crisp ends, so the section
# changes along the slide (PLAYBOOK, "Modelling", item 65 (b)); parts.slide lofts it with sections.facet_ring
SLIDE_CHAMFER = ((SLIDE_X0, 0.30), (7.0, 0.30), (9.5, 0.55), (SLIDE_X1, 0.55))
SERR_X0, SERR_COUNT, SERR_PITCH, SERR_W, SERR_D = -2.0, 8, 0.30, 0.14, 0.06
MARK = 'MOD. TP'                       # engraved on the slide's left: the game's own model name, never a real maker's

# --- barrel (fixed to the frame; the slide runs over it)
BARREL_X0 = 4.0
BARREL_R, BORE_R = 0.62, 0.42
TUNNEL_CLEAR = 0.03                   # never model two parts into the same surface: leave air between them
TUNNEL_X0 = 0.5                       # the tunnel reaches this far back, so the slide can travel over the barrel

# --- frame and grip
FRAME_HW = 1.20
FRAME_X1 = 11.0
FRAME_BOT = 2.3                       # underside of the frame ahead of the grip
RAKE_DEG = 12.0
RAKE = math.radians(RAKE_DEG)
TAN_RAKE = math.tan(RAKE)
GRIP_FRONT_X = 2.4                    # the front strap is a straight line down and back from (GRIP_FRONT_X, FRAME_BOT)
GRIP_CHORD = 4.8
GRIP_BOT = -6.0

# --- magazine (its axis is parallel to the front strap)
MAG_HW = 0.85
MAG_DEPTH = 3.0
MAG_FRONT_WALL = 0.45
MAG_TOP = 2.5
MAG_BELOW = 0.6                       # how far it stands out of the bottom of the grip
WELL_CLEAR = 0.04

# --- safety lever: a part that TURNS (left side of the frame, above the grip panel, under the slide's overhang)
SAFETY_PIVOT = (-1.2, 2.75)           # x, z of its pin: the bone sits here and the lever turns about it
SAFETY_LEN = 1.9                      # from the pin forward
SAFETY_HH = 0.18                      # half its height
SAFETY_T = 0.14                       # thickness
SAFETY_GAP = 0.02                     # air between it and the frame's side
SAFETY_DOWN_DEG = 25.0                # "fire": its front end tips down by this
SAFE_AT, FIRE_AT = (1.25, 2.95), (1.15, 2.05)     # (x, z) of the two marks on the frame the lever's front end points at

# --- sights and grip panels
SIGHT_H = 0.40
FRONT_SIGHT_X = (11.6, 12.4)
REAR_SIGHT_X = (-2.2, -1.4)
PANEL_T = 0.30
PANEL_INSET = 0.45
PANEL_SCREW = 3                       # the grip screw sits where this groove of the panel's seven would be (an island: item 41)


def front_strap_x(z):
    return GRIP_FRONT_X - (FRAME_BOT - z) * TAN_RAKE


def back_strap_x(z):
    return front_strap_x(z) - GRIP_CHORD


GRIP_AXIS = (math.sin(RAKE), 0.0, math.cos(RAKE))          # up the grip, into the gun
GRIP_FRONT_N = (math.cos(RAKE), 0.0, -math.sin(RAKE))      # perpendicular to it, toward the front strap


def mag_centre_x(z):
    """The magazine's centre line (parallel to the front strap)."""
    return front_strap_x(z) - (MAG_FRONT_WALL + MAG_DEPTH / 2) / math.cos(RAKE)


MAG_TOP_CENTRE = (mag_centre_x(MAG_TOP), 0.0, MAG_TOP)
MAGWELL = (mag_centre_x(GRIP_BOT), 0.0, GRIP_BOT)
