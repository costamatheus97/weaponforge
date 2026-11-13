"""weaponforge: what a weapon definition is, and where its files live.

A weapon is a folder weapons/<id>/ with three modules:

    params.py   every dimension, pure Python (no bpy)
    parts.py    one builder per part: fn(coll, hp=False) -> mesh objects in the weapon frame, each tagged with kit.tag()
    weapon.py   WEAPON = an instance of a Weapon subclass: names, bones, sockets, materials, poses, checks

Everything a stage needs comes from that object, so the stages themselves (stages.py) know nothing about any one weapon.

Frame, everywhere: the game's weapon frame as Blender sees it. Origin at the grip, +X toward the muzzle (or the tip), +Z up,
+Y the weapon's LEFT. Unreal reads (x, -y, z), so +Y is the right there. Centimetres (scene unit scale 0.01).
"""
import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.dirname(HERE)                                      # the repository (weapons/ is under it)
if TOOL not in sys.path:
    sys.path.insert(0, TOOL)

from weaponforge import settings as _settings                     # noqa: E402  (weaponforge.toml, WEAPONFORGE_*: settings.py)

# ---- where things go: settings (weaponforge.toml or WEAPONFORGE_<KEY>), each with a default that needs no configuration
ASSET_ROOT = _settings.get('assets')            # sources: <ASSET_ROOT>/<id>/ holds the .blend, bakes, textures, FBX
SPEC_DIR = _settings.get('spec_dir')            # <id>.json, read by the Unreal import; '' = beside the weapon's files
UNREAL_BASE = _settings.get('unreal.content').rstrip('/')         # /<Name>/ under it
UNREAL_MASTER = _settings.get('unreal.master_material')           # parent of every MI_<Name>
UNREAL_TEXTURES = (('BC', _settings.get('unreal.param_base_color'), 'colour'), ('N', _settings.get('unreal.param_normal'), 'normal'),
                   ('ORM', _settings.get('unreal.param_masks'), 'masks'))     # file suffix, the master's texture parameter, how
#                                                                               Unreal must treat the file
UNREAL_SCALAR_PARAMS = {_settings.get('unreal.param_roughness_scale'): 1.0, _settings.get('unreal.param_metallic_scale'): 1.0}

SOCKET_PREFIX = 'SOCKET_'      # Unreal's importer makes a mesh socket of a leaf joint with this prefix, on the joint's parent bone


def _names(value):
    """('Slide_Bone',) from 'Slide_Bone' or from a list: a bare string must not be read as its letters."""
    return (value,) if isinstance(value, str) else tuple(value)


class Prop:
    """A separate static mesh cut from some of the parts (a magazine, a scope): SM_<Name>_<suffix>.

    bones: the parts on these bones make it up. matrix: the prop's own frame in the weapon frame (its origin and axes); the mesh is
    written in that frame. use: one line for the spec."""

    def __init__(self, suffix, bones, matrix=None, use=''):
        self.suffix = suffix
        self.bones = _names(bones)
        self.matrix = matrix
        self.use = use


class Move:
    """A part that travels: checked for overlap with everything it must clear.

    bones: what moves (the bones under them in the skeleton move with them). matrix(amount): where it is after moving by
    `amount` (a 4x4). steps: the amounts to test. limit: the amounts up to this one (by size, so a negative travel works) must
    stay clear; larger ones are reported only. unit: what `amount` is, for the report."""

    def __init__(self, name, bones, matrix, steps, limit=None, unit='cm', note=''):
        self.name = name
        self.bones = _names(bones)
        self.matrix = matrix
        self.steps = tuple(steps) if isinstance(steps, (tuple, list)) else (steps,)
        if not self.steps:
            raise ValueError('Move %r: give at least one amount to test in steps' % name)
        self.limit = limit if limit is not None else max(self.steps, key=abs)
        self.unit = unit
        self.note = note


class Zone:
    """A soft box in the weapon frame (cm) that the look reads by position (Weapon.handled, .smooth, .textured; surface.zones).

    lo, hi: two opposite corners. strength: 0..1, how much of the effect it carries (where zones overlap the strongest
    wins). soft: cm over which it fades out beyond the box, the edge of the fade broken by noise so it never reads as a
    box. tilt: degrees the box is turned about the lateral axis round its own middle, by the same rule as kit.rot_y
    (positive tips +Z toward -X: a grip raked back). note: what touches the weapon there, for whoever reads the file."""

    def __init__(self, lo, hi, strength=1.0, soft=1.0, tilt=0.0, note=''):
        self.lo = tuple(float(v) for v in lo)
        self.hi = tuple(float(v) for v in hi)
        if len(self.lo) != 3 or len(self.hi) != 3 or any(a > b for a, b in zip(self.lo, self.hi)):
            raise ValueError('Zone %r: lo %s and hi %s must be (x, y, z) with lo under hi on every axis' % (note, self.lo, self.hi))
        self.strength = float(strength)
        self.soft = float(soft)
        self.tilt = float(tilt)
        self.note = note


class Decal:
    """A picture laid on the weapon through a box in the weapon frame, after the recipes (surface.decals): a stencil, a label,
    a scrape, or, with no colour of its own, a mask: a grime leak that only darkens and roughens.

    image: the name of a texforge decal set (`texforge decal`: <name>_BaseColor.png, <name>_Opacity.png and, if it is there,
    <name>_Height.png in a folder <name>/), looked for where surface.material_dirs says. lo, hi: two opposite corners of the
    box (cm). The picture is fitted inside the box's two axes across `side`, keeping its aspect, centred (stretch=True: it fills
    the box, for a streak or a smear that may be widened); keep the box shallow
    along `side` (the near wall and a few mm), or the inner walls of a cut on the far side, which face the same way, catch it.
    side: the side it is put on from, '+Y' (the weapon's left), '-Y', '+Z' (from above), '-Z', '+X' (from the muzzle), '-X';
    only faces that look toward that side take it, and it reads unmirrored from there (from above and below, its top is
    toward the muzzle). tilt: degrees the box (and the picture in it) is turned about the lateral axis round its own middle,
    by Zone's rule (positive tips +Z toward -X). strength: 0..1, how opaque it is.
    What it does where it is:
      colour  True: the picture's own colour; a colour: that one, with the picture as its mask; None: the colour stays
      darken  0..1: the colour under it goes darker and browner (grime, oil)
      rough   None: unchanged; a number: that roughness; (dark, light): from the picture's darkest to its lightest
      metal   None: unchanged; a number (0 for paint and paper)
      relief  how much of the picture's height goes into the normal map; thick: a step at its outline (a label, thick paint)
      wear    0..1: worn away on exposed edges, where the weapon is handled (Weapon.handled) and in specks
    note: why it is there, for whoever reads the file."""

    SIDES = ('+X', '-X', '+Y', '-Y', '+Z', '-Z')

    def __init__(self, image, lo, hi, side='+Y', tilt=0.0, strength=1.0, colour=True, darken=0.0, rough=None, metal=None,
                 relief=0.0, thick=0.0, wear=0.0, stretch=False, note=''):
        self.image = str(image)
        self.lo = tuple(float(v) for v in lo)
        self.hi = tuple(float(v) for v in hi)
        if len(self.lo) != 3 or len(self.hi) != 3 or any(a >= b for a, b in zip(self.lo, self.hi)):
            raise ValueError('Decal %r: lo %s and hi %s must be (x, y, z) with lo under hi on every axis' % (image, self.lo, self.hi))
        if side not in self.SIDES:
            raise ValueError('Decal %r: side %r is not one of %s' % (image, side, ', '.join(self.SIDES)))
        self.side = side
        self.tilt = float(tilt)
        self.strength = float(strength)
        self.colour = colour
        self.darken = float(darken)
        self.rough = rough
        self.metal = metal
        self.relief = float(relief)
        self.thick = float(thick)
        self.wear = float(wear)
        self.stretch = bool(stretch)
        self.note = note


class TexelZone:
    """Where the UV sheet's texels go, by place (uv.face_weights; opt-in, Weapon.texel_zones): the faces of the game parts that
    lie in a box in the weapon frame (cm) get `weight` times the texel density of an undeclared face. 2 for what the player
    looks at in first person, 0.5 for what he never sees.

    weight: > 0. lo, hi: two opposite corners; None for no box (every face of the builders named). facing: None, or one or
    more of '+X', '-X', '+Y' (the weapon's left), '-Y', '+Z', '-Z': only faces whose normal is within 60 degrees of one of
    them. builders: () for every part, or the builders it is limited to. Where zones overlap the LAST one listed wins; a
    face that is hidden in every pose takes Weapon.texel_hidden whatever zone it is in. note: what it is, for the report."""

    def __init__(self, weight, lo=None, hi=None, facing=None, builders=(), note=''):
        self.weight = float(weight)
        self.lo = tuple(float(v) for v in lo) if lo is not None else None
        self.hi = tuple(float(v) for v in hi) if hi is not None else None
        self.facing = (facing,) if isinstance(facing, str) else tuple(facing or ())
        self.builders = (builders,) if isinstance(builders, str) else tuple(builders or ())
        self.note = note

    def problems(self):
        bad = []
        if not self.weight > 0.0:
            bad.append('weight %r: more than 0' % (self.weight,))
        if (self.lo is None) != (self.hi is None):
            bad.append('give both lo and hi, or neither')
        elif self.lo is not None and (len(self.lo) != 3 or len(self.hi) != 3 or any(a > b for a, b in zip(self.lo, self.hi))):
            bad.append('lo %s and hi %s must be (x, y, z) with lo under hi on every axis' % (self.lo, self.hi))
        bad += ['facing %r is not one of %s' % (f, ', '.join(Decal.SIDES)) for f in self.facing if f not in Decal.SIDES]
        if self.lo is None and not self.builders:
            bad.append('no box and no builders: it would be every face (use Weapon.density for a whole part)')
        return ['texel zone %r: %s' % (self.note, b) for b in bad]


class Weapon:
    # ---- identity
    id = None                  # folder under weapons/ and under the asset root: 'assault_g3'
    name = None                # asset stem: SKM_<name>, SM_<name>, T_<name>_BC, MI_<name>: 'AssaultG3'
    tag = None                 # prefix of this weapon's collections and datablocks in the .blend: 'G1'
    design = ''                # one line for the spec: what it is
    frame_note = ('the game weapon frame as Unreal reads it: origin at the grip, +X muzzle, +Y right, +Z up, cm. '
                  '(In Blender, where the mesh is authored, the same frame has +Y on the weapon\'s left.)')

    # ---- budget
    texture_size = 4096
    finish = 'blued'                   # the steel's finish: a name in surface.STEEL, for surface() to pass to S.steel
    timber = 'walnut'                  # the wood: a name in surface.WOOD, for surface() to pass to S.timber
    # paint in the engraved lettering, by the ink number its text was cut with (kit.text_solid's `ink`): names in
    # surface.PAINT, colours, or None for letters left bare; () leaves every letter as bare engraving
    paint = ()
    paint_wear = 0.35                  # 0 fresh paint, 1 most of it gone
    # the edge break the bake rounds every edge with, in cm, per surface kind; a kind not named keeps bake.KINDS' own
    # (0.03 for steel: a machined edge). {'polymer': 0.08} gives a moulding its soft edges. It rounds every edge of the
    # kind, the walls of engraved letters and fine grooves too: look at them after widening it
    edge_break = {}
    budget = (15000, 30000)            # LOD0 triangles
    lods = ((1, 0.5), (2, 0.25))       # (index, share of LOD0)
    uv_margin = 0.0024                 # space round each island as a fraction of the sheet (10 px at 4K: 20 px between two islands, 10 to the edge)
    # opt-in (PLAYBOOK "UVs" item 8). None: Blender's packer, as every weapon so far. 'tight': the tool's own packer (uv.pack_tight),
    # which fills the concave gaps Blender's leaves: AssaultG3 went from 46 to 69 % of the sheet at the same margin
    uv_pack = None
    # opt-in: texels by place. [TexelZone]: faces in a box (and facing a side) get that weight times the density of the rest.
    # texel_hidden: None, or the weight of every face no one sees in any of the weapon's poses (shut in, or covered by
    # another part within 0.3 cm). Either one makes the UV islands split where the weight changes, and the check
    # "uv: texel density" test each part against what its faces ask for ("uv: texel zones" reports them)
    texel_zones = []
    texel_hidden = None
    # opt-in: texels by what the player sees (uv.view_weights). True: every face is weighed by how close and how square-on the
    # first-person eye and the aiming eye see it in any pose (the eyes of the hero pictures `fp` and `ads`), on a short
    # ladder of weights; a face neither eye sees gets a little under 1. TexelZones still win where they apply, and
    # texel_hidden over both. player_eyes: None (the hero pictures' eyes: hero.player_eyes, the aiming eye found from the
    # SightRear and SightFront sockets) or {'fp': (x, y, z), 'ads': (x, y, z)} in cm to move either one, pictures and weights alike
    texel_view = False
    player_eyes = None
    # opt-in: the review's figures held as checks (review.py; docs/review.md). None: the check says them and holds none.
    # 'first_person': each figure in review.LIMITS is a check "review: <figure>"; review_limits = {figure: limit} moves a limit
    review = None
    review_limits = {}

    # ---- the rig: [(name, parent or None, head position)] and [(name, bone, position, Unreal (pitch, yaw, roll), meaning)]
    bones = []
    sockets = []
    motion = {}                        # bone: how the game moves it (text, for the spec)
    poses = {'rest': {}}               # pose: {bone: {'loc': (x, y, z) cm, 'rot': (x, y, z) degrees, 'scale': s}}
    props = []                         # [Prop]
    moves = []                         # [Move]

    # ---- surface
    kinds = None                       # {kind: bake.Kind}; None: bake.KINDS
    ao_friends = {}                    # builder: [builders whose high-detail parts shade it in the occlusion pass]
    density = {}                       # builder: texel density relative to the rest (default 1)
    palette = {}                       # object-name prefix: (r, g, b, a) for the grey review renders
    # where the weapon is touched, by position, for the look to read (surface.zones; s.handled, s.smooth, s.textured).
    # Nothing reads them unless surface() passes the masks to a recipe, so the default [] changes nothing:
    handled = []                       # [Zone]: hands, cheek, magazine changes, the ground: wear by use
    smooth = []                        # [Zone]: polymer moulded smooth (no grain, a satin sheen): cheek panels, collars
    textured = []                      # [Zone]: polymer moulded with a stipple: grip panels, the fore-end's hold
    # pictures laid on after the recipes (surface.decals): stencils, labels, scrapes, grime leaks. [] lays none and loads none
    decals = []                        # [Decal]

    # ---- review renders
    closeups = {}                      # name: ((x0, y0, z0), (x1, y1, z1)) cm, or (lo, hi, [views]): an extra sheet framed on that box
    pose_closeup = None                # the closeup the pose sheets are framed on (None: the whole weapon)
    pose_views = ('left', 'q_rear_r')  # the two views of a pose sheet: the side the moving parts show on comes first

    # ---- the design brief: label: (low, high) in cm, measured by measure()
    brief = {}

    root = None                        # set by load(): another asset root (tests write there, and their spec with it)

    # ------------------------------------------------------------------------------------------------------------- names
    @property
    def skm(self):
        return 'SKM_' + self.name

    @property
    def static(self):
        return 'SM_' + self.name

    def prop_name(self, prop):
        return '%s_%s' % (self.static, prop.suffix)

    def lod_name(self, index, static=False):
        return '%s_LOD%d' % (self.static if static else self.skm, index)

    @property
    def tex_prefix(self):
        return 'T_' + self.name

    @property
    def mat_author(self):
        return 'M_%s_Author' % self.name      # the procedural material the textures are baked from

    @property
    def mat_game(self):
        return 'M_' + self.name               # the written textures on a plain PBR material: what the game meshes carry

    def coll(self, kind):
        return '%s_%s' % (self.tag, kind)     # kind: 'LP' (game parts), 'HP' (bake source), 'GAME' (what is exported)

    # ------------------------------------------------------------------------------------------------------------- paths
    @property
    def asset_root(self):
        return os.path.join(self.root or ASSET_ROOT, self.id)

    @property
    def blend(self):
        return os.path.join(self.asset_root, self.id + '.blend')

    @property
    def bake_dir(self):
        return os.path.join(self.asset_root, 'bake')

    @property
    def tex_dir(self):
        return os.path.join(self.asset_root, 'textures')

    @property
    def work_dir(self):
        return os.path.join(self.tex_dir, 'work')

    @property
    def export_dir(self):
        return os.path.join(self.asset_root, 'export')

    @property
    def render_dir(self):
        return os.path.join(self.asset_root, 'renders')

    @property
    def spec_path(self):
        """The spec: beside the weapon's files, unless a spec folder is set (spec_dir) and the weapon is built in place."""
        if self.root or not SPEC_DIR:
            return os.path.join(self.asset_root, self.id + '.json')
        return os.path.join(SPEC_DIR, self.id + '.json')

    @property
    def unreal_dir(self):
        """Where the Unreal import puts the weapon. Built under another asset root (a test, a trial) it is a trial folder, so that
        nothing made from a test copy can be imported over the real weapon."""
        return '%s/%s%s' % (UNREAL_BASE, '_Scratch/' if self.root else '', self.name)

    def with_children(self, bones):
        """These bones and every bone under them in the skeleton."""
        out = list(bones)
        for name, parent, _pos in self.bones:          # parents come first (validate), so one pass finds every descendant
            if parent in out and name not in out:
                out.append(name)
        return tuple(out)

    def validate(self):
        """What is wrong with the definition, as text: [] when it is sound. Run by load(), so a typo stops the first stage with a
        sentence instead of a KeyError in the middle of a later one."""
        bad = []
        if not re.fullmatch(r'[a-z_][a-z0-9_]*', str(self.id or '')):
            bad.append('id %r: lower case letters, digits and _ (it is a folder and a Python package)' % (self.id,))
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', str(self.name or '')):
            bad.append('name %r: letters, digits and _ (it becomes SKM_<name>)' % (self.name,))
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', str(self.tag or '')):
            bad.append('tag %r: letters and digits' % (self.tag,))
        names = []
        for entry in self.bones:
            if len(entry) != 3 or len(entry[2]) != 3:
                bad.append('bone %r: write (name, parent or None, (x, y, z))' % (entry,))
                continue
            name, parent, _pos = entry
            if name in names:
                bad.append('bone %s is defined twice' % name)
            if str(name).startswith(SOCKET_PREFIX):
                bad.append('bone %s: the prefix %s is kept for the socket joints' % (name, SOCKET_PREFIX))
            if parent is None and names:
                bad.append('bone %s has no parent: only the first bone is the root' % name)
            if parent is not None and parent not in names:
                bad.append('bone %s: its parent %s is not defined before it' % (name, parent))
            names.append(name)
        if not names:
            bad.append('no bones: a weapon needs at least a root bone')
        seen = []
        for entry in self.sockets:
            if len(entry) != 5 or len(entry[2]) != 3 or len(entry[3]) != 3:
                bad.append('socket %r: write (name, bone, (x, y, z), (pitch, yaw, roll), meaning)' % (entry,))
                continue
            name, bone = entry[0], entry[1]
            if name in seen:
                bad.append('socket %s is defined twice' % name)
            if bone not in names:
                bad.append('socket %s is on bone %s, which is not defined' % (name, bone))
            seen.append(name)
        suffixes = []
        for prop in self.props:
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', str(prop.suffix)) or prop.suffix in suffixes:
                bad.append('prop suffix %r: letters and digits, each used once' % (prop.suffix,))
            suffixes.append(prop.suffix)
            bad += ['prop %s: bone %s is not defined' % (prop.suffix, b) for b in prop.bones if b not in names]
        for move in self.moves:
            bad += ['move "%s": bone %s is not defined' % (move.name, b) for b in move.bones if b not in names]
        for pose, bones in self.poses.items():
            for bone, change in bones.items():
                if bone not in names:
                    bad.append('pose %s: bone %s is not defined' % (pose, bone))
                odd = sorted(set(change) - {'loc', 'rot', 'scale'})
                if odd:
                    bad.append('pose %s, %s: %s is not one of loc, rot, scale' % (pose, bone, ', '.join(odd)))
        bad += ['motion: bone %s is not defined' % b for b in self.motion if b not in names]
        want = list(range(1, len(self.lods) + 1))
        shares = [r for _i, r in self.lods]
        if [i for i, _r in self.lods] != want or shares != sorted(shares, reverse=True) or any(not 0.0 < r < 1.0 for r in shares):
            bad.append('lods %r: write ((1, share), (2, smaller share), ...) with shares between 0 and 1' % (self.lods,))
        if len(self.budget) != 2 or self.budget[0] > self.budget[1]:
            bad.append('budget %r: write (fewest, most) LOD0 triangles' % (self.budget,))
        if self.texture_size < 64 or self.texture_size & (self.texture_size - 1):
            bad.append('texture_size %r: a power of two' % (self.texture_size,))
        for name, box in self.closeups.items():
            if not re.fullmatch(r'[a-z][a-z0-9_]*', str(name)):
                bad.append('closeup %r: lower case letters, digits and _ (it ends a file name)' % (name,))
            if len(box) not in (2, 3) or len(box[0]) != 3 or len(box[1]) != 3 or any(a >= b for a, b in zip(box[0], box[1])):
                bad.append('closeup %s: write ((x0, y0, z0), (x1, y1, z1)) with the first corner the lower one, then optionally [views]' % name)
        if self.pose_closeup is not None and self.pose_closeup not in self.closeups:
            bad.append('pose_closeup %r is not one of closeups' % (self.pose_closeup,))
        if (not isinstance(self.pose_views, (tuple, list)) or not self.pose_views
                or any(not isinstance(v, str) for v in self.pose_views)):
            bad.append('pose_views %r: write the names of one or more views, like (\'right\', \'q_rear_r\')' % (self.pose_views,))
        if self.uv_pack not in (None, 'tight'):
            bad.append('uv_pack %r: None (Blender\'s packer) or \'tight\'' % (self.uv_pack,))
        for zone in self.texel_zones:
            bad += zone.problems() if isinstance(zone, TexelZone) else ['texel_zones: %r is not a TexelZone' % (zone,)]
        if self.texel_hidden is not None and not 0.0 < float(self.texel_hidden) <= 1.0:
            bad.append('texel_hidden %r: None, or a weight over 0 and at most 1' % (self.texel_hidden,))
        if self.texel_view not in (True, False):
            bad.append('texel_view %r: True or False' % (self.texel_view,))
        eyes = self.player_eyes
        if eyes is not None and (not isinstance(eyes, dict) or set(eyes) - {'fp', 'ads'}
                                 or any(not isinstance(p, (tuple, list)) or len(p) != 3 for p in eyes.values())):
            bad.append('player_eyes %r: None, or {\'fp\': (x, y, z), \'ads\': (x, y, z)} in cm (either may be left out)' % (eyes,))
        if self.review not in (None, 'first_person'):
            bad.append('review %r: None, or \'first_person\' (the review figures held as checks)' % (self.review,))
        if not isinstance(self.review_limits, dict):
            bad.append('review_limits %r: {figure: limit}' % (self.review_limits,))
        elif self.review_limits:
            from .review import LIMITS
            for key, value in self.review_limits.items():
                if key not in LIMITS:
                    bad.append('review_limits: %r is not a figure (have %s)' % (key, ', '.join(LIMITS)))
                elif isinstance(value, bool) or not isinstance(value, (int, float)):
                    bad.append('review_limits %s: %r is not a number' % (key, value))
        return bad

    # ---------------------------------------------------------------------------------------------------------- the rig
    @property
    def bone_pos(self):
        from mathutils import Vector
        return {name: Vector(pos) for name, _parent, pos in self.bones}

    # ------------------------------------------------------------------------------------------------------------ hooks
    def builders(self):
        """{builder name: fn(coll, hp)}: every part of the weapon."""
        raise NotImplementedError

    def hp_kinds(self, obj):
        """The surface kinds on one high-detail part: [kinds], one material slot each. A part of more than one kind sets its faces'
        material_index here (slot 0 is the first kind) and returns them all."""
        return [obj.get('mat', 'steel')]

    def seams(self, obj):
        """Where one game part's UVs are cut besides its hard edges: None, or pred(edge, mid, direction) that is true for an edge
        to cut along (the same call as K.bevel's; K.in_plane makes one). The mesh is the finished, triangulated one. Without a
        seam a closed smooth surface (a barrel, a stock) cannot be laid flat and is cut up by angle, in strips that end where
        they end; with one it is a single piece cut where nobody looks: along the underside."""
        return None

    def images(self):
        """Extra pictures the surface needs: {key: (path, colour space)}. A missing file gives None, so a recipe can fall back.
        Tiling texforge sets for S.detail: `return S.texforge_sets(self, 'poly_mould', 'rubber')` (surface.material_dirs says
        where they are looked for). Decals load their own pictures; they need nothing here."""
        return {}

    def surface(self, s):
        """The look: build layers with surface recipes on s (a surface.Surface) and return the stacked Layer."""
        raise NotImplementedError

    def collision(self, static, C):
        """Simple collision for the world copy: a list of boxes made with C (the collision module). Default: one box."""
        pts = C.points(static)
        return [C.aligned('body', pts)]

    def measure(self, parts):
        """{label: cm} for every label in `brief`, measured on the game parts ({object name: object})."""
        return {}

    def socket_targets(self, parts):
        """{socket: Vector}: where the mesh itself says a socket should be, for the sockets that can be measured."""
        return {}

    def checks(self, c):
        """Checks only this weapon has: call c.add(name, ok, detail). c is a check.Checker."""

    def spec_extra(self, game):
        """Keys this weapon adds to the spec (dimensions_cm, reload_targets, ...)."""
        return {}

    # ------------------------------------------------------------------------------------------------------------- misc
    def __repr__(self):
        return '<Weapon %s (%s)>' % (self.id, self.name)


def load(weapon_id, root=None, reload=False):
    """The WEAPON object of weapons/<id>/weapon.py. reload=True re-reads its modules (a live session after an edit)."""
    base = 'weapons.%s' % weapon_id
    if reload:
        for name in [n for n in sys.modules if n == base or n.startswith(base + '.')]:
            del sys.modules[name]
        importlib.invalidate_caches()
    mod = importlib.import_module(base + '.weapon')
    weapon = mod.WEAPON
    if weapon.id != weapon_id:
        raise ValueError('weapons/%s/weapon.py defines %r' % (weapon_id, weapon.id))
    for attr in ('name', 'tag'):
        if not getattr(weapon, attr):
            raise ValueError('%s: %s is not set' % (weapon_id, attr))
    wrong = weapon.validate()
    if wrong:
        raise ValueError('weapons/%s/weapon.py: %d things to fix:\n  - %s' % (weapon_id, len(wrong), '\n  - '.join(wrong)))
    weapon.root = root
    return weapon


def available():
    folder = os.path.join(TOOL, 'weapons')
    return sorted(d for d in os.listdir(folder) if os.path.isfile(os.path.join(folder, d, 'weapon.py')))
