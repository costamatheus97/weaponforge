"""TemplateGun: the weapon definition. A small made-up pistol that goes through every stage in about a minute.

This is the file to copy for a new weapon (bin/weaponforge new <id> <Name> <TAG>). Everything a stage needs is declared here;
what you do not need, delete (the base class in weaponforge/weapon.py has a default for every hook but builders() and surface()).
"""
import math

from mathutils import Matrix, Vector

from weaponforge import check as CHK
from weaponforge import finish as F
from weaponforge import kit as K
from weaponforge import surface as S
from weaponforge.weapon import Move, Prop, Weapon

from . import params as P
from . import parts as PT

MAG_AXIS = Vector(P.GRIP_AXIS)                 # up the magazine, into the gun


class TemplateGun(Weapon):
    id = '_template'               # this folder's name, and the folder under the asset root
    name = 'TemplateGun'           # asset stem: SKM_TemplateGun, SM_TemplateGun, T_TemplateGun_BC, MI_TemplateGun
    tag = 'TP'                     # prefix of this weapon's collections in the .blend: TP_LP, TP_HP, TP_GAME
    design = 'the weaponforge template: a made-up blocky pistol, no real maker or markings'

    texture_size = 1024            # a real first-person weapon: 4096
    # paint in the engraved lettering and marks (parts.py cuts them with K.text_solid and the fittings' marks): one entry per
    # ink number, names in surface.PAINT. Here ink 0 (the slide's lettering, the safe mark) is white and ink 1 (the fire mark)
    # red; () leaves them as bare engraving
    paint = ('white', 'red')
    budget = (600, 6000)           # LOD0 triangles the design allows; a real first-person pistol: (15000, 30000)
    # texels where the player looks, with no boxes to draw (docs/texels.md, "Texels by view", PLAYBOOK "UVs" items 8 and 9): the tool's own
    # packer, every face weighed by what the hip eye and the aiming eye see of it, and less on what no pose ever shows.
    # Look at `hero --shots fp,ads`, and add a TexelZone only for what the eyes cannot know (a hand, an animation, a scope)
    uv_pack = 'tight'
    texel_view = True
    texel_hidden = 0.45
    lods = ((1, 0.5), (2, 0.25))

    # ---- the rig. Bone names are the ones the game's animation code drives (it reads Slide_Bone, Clip_Bone, ...);
    #      a bone sits on the pivot of the part it moves. [(name, parent, head position in Blender's frame)]
    bones = [
        ('Root_Bone1', None, (0.0, 0.0, 0.0)),
        ('Grip_Bone', 'Root_Bone1', (0.0, 0.0, 0.0)),
        ('Slide_Bone', 'Grip_Bone', (0.0, 0.0, P.BZ)),
        ('Barrel_Bone', 'Grip_Bone', (P.BARREL_X0, 0.0, P.BZ)),
        ('Clip_Bone', 'Grip_Bone', P.MAG_TOP_CENTRE),
        ('Safety_Bone', 'Grip_Bone', (P.SAFETY_PIVOT[0], P.FRAME_HW, P.SAFETY_PIVOT[1])),      # on the lever's pin
    ]

    # ---- sockets: [(name, bone, position in Blender's frame, Unreal rotation (pitch, yaw, roll), what it means)]
    #      Blender's +Y is the weapon's LEFT, so the right-hand side is -Y here (and +Y in Unreal).
    sockets = [
        ('Muzzle', 'Grip_Bone', (P.MUZZLE_X, 0.0, P.BZ), (0.0, 0.0, 0.0), 'centre of the muzzle, +X out of the barrel'),
        ('AmmoEject', 'Grip_Bone', (5.0, -P.SLIDE_HW, P.SLIDE_TOP - 0.4), (0.0, 90.0, 0.0), 'where a spent case leaves, on the right; +X is its way out'),
        ('MagWell', 'Grip_Bone', P.MAGWELL, (-P.RAKE_DEG, 0.0, 0.0), 'centre of the magazine opening; +Z up the magazine axis into the gun'),
    ]

    motion = {
        'Slide_Bone': 'translate -X by %.1f cm' % P.SLIDE_TRAVEL,
        'Clip_Bone': 'the magazine; it leaves along the MagWell socket\'s -Z',
        'Safety_Bone': 'the safety lever; its front end pitches down by %.0f deg about the bone' % P.SAFETY_DOWN_DEG,
    }

    # ---- a prop is cut out of the weapon as its own static mesh, in its own frame (here: origin at the magazine's top centre,
    #      +Z up its axis)
    props = [Prop('Mag', ('Clip_Bone',), Matrix.Translation(Vector(P.MAG_TOP_CENTRE)) @ Matrix.Rotation(P.RAKE, 4, 'Y'),
                  'the dropped / inserted magazine; origin at the top centre of its body, +Z up its axis')]

    # ---- what must travel clear of everything else. The check puts the parts on `bones` where matrix(amount) says and measures
    #      the deepest overlap with every other part. matrix(amount) is a 4x4 in the weapon frame, applied to the parts as they sit
    #      at rest: a translation for a slide, a rotation ABOUT THE PIVOT for a lever (K.rot_y(pivot_xz, degrees) turns about the
    #      lateral axis; positive degrees tip +Z toward -X, a hammer cocking back, so a front end going down is negative).
    moves = [
        Move('slide travel', ('Slide_Bone',), lambda t: Matrix.Translation((-t, 0.0, 0.0)), (P.SLIDE_TRAVEL / 2, P.SLIDE_TRAVEL), unit='cm back'),
        Move('magazine leaves', ('Clip_Bone',), lambda d: Matrix.Translation(-MAG_AXIS * d), (1.0, 4.0, 8.0), unit='cm out'),
        Move('safety lever', ('Safety_Bone',), lambda deg: K.rot_y(P.SAFETY_PIVOT, -deg), (P.SAFETY_DOWN_DEG / 2, P.SAFETY_DOWN_DEG), unit='deg down'),
    ]

    # ---- poses for the review renders: {bone: {'loc': cm, 'rot': degrees (x, y, z), 'scale': s}}, in the bone's own axes, which
    #      are the weapon's (Blender's right-hand rule: +rot about Y takes +X toward -Z, the opposite sign to K.rot_y)
    poses = {
        'rest': {},
        'slide_back': {'Slide_Bone': {'loc': (-P.SLIDE_TRAVEL, 0.0, 0.0)}},
        'reload': {'Clip_Bone': {'loc': tuple(-MAG_AXIS * 6.0)}, 'Safety_Bone': {'rot': (0.0, P.SAFETY_DOWN_DEG, 0.0)}},
    }

    # ---- builders whose high-detail parts shade each other in the occlusion bake (parts that never move apart)
    ao_friends = {'frame': ['grip_l', 'grip_r', 'safety'], 'grip_l': ['frame'], 'grip_r': ['frame'], 'safety': ['frame'],
                  'slide': ['sights'], 'sights': ['slide']}

    # ---- flat colours for the grey review renders, by object-name prefix
    palette = {'Slide': (0.30, 0.32, 0.36, 1), 'Frame': (0.20, 0.20, 0.21, 1), 'Barrel': (0.62, 0.62, 0.60, 1),
               'Grip': (0.45, 0.27, 0.15, 1), 'Magazine': (0.25, 0.25, 0.27, 1), 'Sight': (0.12, 0.12, 0.13, 1),
               'Safety': (0.12, 0.12, 0.13, 1)}

    # ---- the design brief, checked against the mesh: label: (low, high) cm, measured in measure()
    brief = {'overall length': (15.5, 18.5), 'height': (11.0, 13.0), 'slide width': (2.4, 2.8)}

    # ------------------------------------------------------------------------------------------------------------ hooks
    def builders(self):
        return dict(PT.BUILDERS)

    def images(self):
        """The texforge sets the finishes in surface() lay on (finish.sets); a set not on disk leaves its finish procedural."""
        return S.texforge_sets(self, *F.sets('phosphate_parts', 'moulded_polymer'))

    def surface(self, s):
        """The look: a named finish (weaponforge/finish.py, docs/look.md, "Named finishes") per surface kind the builders tagged, stacked
        by the kind's mask, the first row the base. Override any argument in the row's dict; a place the finish cannot know
        (where grime gathers, where black metal wears bright) is an argument too, or comes from the weapon's own zones,
        bones and sockets (each finish's docstring says which). The steel's set and the wood are this weapon's `finish` and
        `timber` (names in surface.STEEL and surface.WOOD): choose them, do not leave every gun alike (docs/look.md, "Writing `surface()`")."""
        return F.look(s, [('steel', 'phosphate_parts', {'finish': self.finish}),
                          ('polymer', 'moulded_polymer', {'colour': (0.020, 0.020, 0.022)}),     # a black frame
                          ('wood', S.timber(s, self.timber, grain_deg=P.RAKE_DEG))])

    def measure(self, parts):
        lo, hi = CHK.bounds(list(parts.values()))
        s_lo, s_hi = CHK.bounds([parts['Slide']])
        return {'overall length': hi.x - lo.x, 'height': hi.z - lo.z, 'slide width': s_hi.y - s_lo.y}

    def socket_targets(self, parts):
        """Where the mesh itself puts a socket, so a socket typed from the wrong number is caught."""
        return {'Muzzle': CHK.face_centre(parts['Barrel'], 0, 1.0, band=0.01)}

    def checks(self, c):
        """Checks only this weapon has. c.by_name / c.on(bone) / c.off(bone) find parts; c.game is the rig once it exists."""
        _lo, hi = CHK.bounds(c.on('Barrel_Bone'))
        c.add('frame: muzzle on +X', abs(hi.x - P.MUZZLE_X) < CHK.TOL, 'the barrel ends at x %.2f (muzzle %.2f)' % (hi.x, P.MUZZLE_X))
        g_lo, g_hi = CHK.bounds([o for name, o in c.by_name.items() if name.startswith('Grip')])     # measured on the panels
        c.add('frame: origin in the grip', g_lo.x < 0.0 < g_hi.x and g_lo.z < 0.0 < g_hi.z,
              'the grip panels run from x %.2f to %.2f and z %.2f to %.2f' % (g_lo.x, g_hi.x, g_lo.z, g_hi.z))

    def collision(self, static, C):
        """Simple collision for the world copy: the upper, and the raked grip as a pitched box."""
        pts = C.points(static)
        upper = C.aligned('upper', [p for p in pts if p.z >= P.FRAME_BOT])
        grip = C.pitched('grip', [p for p in pts if p.z < P.FRAME_BOT], -P.RAKE_DEG)
        return [upper, grip]

    def spec_extra(self, game):
        """Numbers the game side needs, written into the spec."""
        from weaponforge.rig import ue
        return {'dimensions_cm': {'bore_height': P.BZ, 'muzzle_x': P.MUZZLE_X, 'slide_travel': P.SLIDE_TRAVEL, 'grip_rake_deg': P.RAKE_DEG},
                'reload_targets': {'mag_well': ue(Vector(P.MAGWELL)), 'mag_axis': ue(MAG_AXIS)}}


WEAPON = TemplateGun()
