"""weaponforge: the surface. One procedural material over the baked maps, used for the look-dev renders and then baked down to
the game's BaseColor / Normal / ORM set.

A weapon's look is a few lines in its Weapon.surface(s):

    steel = S.worn_steel(s, bright=s.mask('bright'), dark=s.mask('dark'))
    return S.stack(s, steel, (s.mask('wood'), S.wood(s, grain_deg=15.0)), (s.mask('brass'), S.brass(s)))

s is a Surface: the node graph plus everything the recipes share (the bake's occlusion / edge / cavity masks, one mask per surface
kind decoded from the ID map, a set of 3D noises). A recipe returns a Layer (colour, roughness, metallic, height). Write a new
recipe as a plain function of s; the ones here keep their first weapon's tuned numbers as their defaults.

All noise is 3D, in the weapon frame (cm), so nothing shows at a UV seam.
"""
import math
import os

import bpy
import numpy as np

from . import bake as B
from . import maps
from .ops import only, run


# ------------------------------------------------------------------------------------------------------------- images
def image_from(arr, name, path, is_float):
    """arr (h, w, c) in 0..1, row 0 at v = 0 -> a saved, file-backed Blender image (data, not colour)."""
    h, w, c = arr.shape
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :c] = arr
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=is_float, is_data=True)
    img.alpha_mode = 'CHANNEL_PACKED'
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = 'OPEN_EXR' if is_float else 'PNG'
    img.save()
    img.source = 'FILE'
    img.filepath = path
    img.reload()
    img.colorspace_settings.name = 'Non-Color'
    img.alpha_mode = 'CHANNEL_PACKED'
    return img


def load_file(name, path, space):
    """A picture on disk as a Blender image, or None when it is not there (a recipe then falls back to its own pattern)."""
    if not path or not os.path.isfile(path):
        return None
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.load(path)
    img.name = name
    img.colorspace_settings.name = space
    return img


def load_maps(weapon):
    """The cleaned bakes (stage "bake") as images <TAG>_normal, <TAG>_masks (AO, convex, cavity, wear zone) and <TAG>_id, plus the
    weapon's own pictures (Weapon.images)."""
    os.makedirs(weapon.work_dir, exist_ok=True)
    folder, tag = weapon.bake_dir, weapon.tag
    for name in ('normal.npy', 'masks.npy', 'id.npy'):
        if not os.path.isfile(os.path.join(folder, name)):
            raise FileNotFoundError('%s is missing: run the stage "bake" first' % os.path.join(folder, name))
    normal = np.load(os.path.join(folder, 'normal.npy')).astype(np.float32)
    masks = np.load(os.path.join(folder, 'masks.npy')).astype(np.float32) / 255.0
    idm = np.load(os.path.join(folder, 'id.npy')).astype(np.float32) / 255.0
    if getattr(weapon, 'edge_px_cm', None):                # opt-in: the edge masks by the centimetre (edges_by_cm)
        masks = edges_by_cm(weapon, normal, masks, float(weapon.edge_px_cm))
    low = tag.lower()
    images = {
        'normal': image_from(normal, tag + '_normal', os.path.join(weapon.work_dir, low + '_normal.exr'), True),
        'masks': image_from(masks, tag + '_masks', os.path.join(weapon.work_dir, low + '_masks.png'), False),
        'id': image_from(idm, tag + '_id', os.path.join(weapon.work_dir, low + '_id.png'), False),
    }
    marks = os.path.join(folder, 'marks.npy')              # only a weapon with lettering has it (bake.run_bake)
    if os.path.isfile(marks):
        arr = np.load(marks).astype(np.float32) / 255.0
        images['marks'] = image_from(arr, tag + '_marks', os.path.join(weapon.work_dir, low + '_marks.png'), False)
    del _MISSING_SETS[:]
    for key, (path, space) in weapon.images().items():
        images[key] = load_file('%s_%s' % (tag, key), path, space)
    no_decal = []
    for name in sorted({d.image for d in getattr(weapon, 'decals', None) or ()}):   # only a weapon that declares decals
        folder = find_set(weapon, name)
        if folder is None:
            no_decal.append(name)                          # left out: decals() skips a decal whose picture is not loaded
            continue
        print('[texture] decal picture %s: found in %s' % (name, folder))
        for suffix, space in (('BaseColor', 'sRGB'), ('Opacity', 'Non-Color'), ('Height', 'Non-Color')):
            images['decal_%s_%s' % (name, suffix)] = load_file('%s_decal_%s_%s' % (tag, name, suffix),
                                                               os.path.join(folder, '%s_%s.png' % (name, suffix)), space)
    if _MISSING_SETS or no_decal:
        what = [p for p in ('tiling sets ' + ', '.join(_MISSING_SETS) if _MISSING_SETS else '',
                            'decals ' + ', '.join(no_decal) if no_decal else '') if p]
        then = [p for p in ('the finishes keep their procedural pattern' if _MISSING_SETS else '',
                            'those decals are left out' if no_decal else '') if p]
        print('[texture] painted sets not found: %s; looked for <name>/<name>_BaseColor.png in %s. Without them %s (the setting '
              '`materials`, or WEAPONFORGE_MATERIALS, adds a folder to look in)'
              % ('; '.join(what), ', '.join(material_dirs(weapon)), ' and '.join(then)))
    return images


def island_density(weapon, size=4096):
    """Each game-mesh triangle's UVs (n, 3, 2) and the texel density of the UV island it is in (px/cm on a `size` sheet): the
    square root of the island's texels over its cm2. Measured on the mesh as packed, so it is what the weights
    (uv.face_weights, uv.island_weights), the zones and the packer's scale came to, for any weapon."""
    from . import uv as UV
    coll = bpy.data.collections.get(weapon.coll('LP'))
    tris, dens = [], []
    for o in (coll.all_objects if coll else ()):
        if o.type != 'MESH' or UV.UV_NAME not in o.data.uv_layers:
            continue
        mesh = o.data
        mesh.calc_loop_triangles()
        n = len(mesh.loop_triangles)
        if not n:
            continue
        loops = np.empty(n * 3, np.int64)
        mesh.loop_triangles.foreach_get('loops', loops)
        poly = np.empty(n, np.int64)
        mesh.loop_triangles.foreach_get('polygon_index', poly)
        uvs = np.empty(len(mesh.loops) * 2, np.float32)
        mesh.uv_layers[UV.UV_NAME].data.foreach_get('uv', uvs)
        vi = np.empty(len(mesh.loops), np.int64)
        mesh.loops.foreach_get('vertex_index', vi)
        co = np.empty(len(mesh.vertices) * 3, np.float64)
        mesh.vertices.foreach_get('co', co)
        m = np.array(o.matrix_world)
        co = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        t_uv = uvs.reshape(-1, 2)[loops].reshape(n, 3, 2).astype(np.float64)
        t_co = co[vi[loops]].reshape(n, 3, 3)
        a_uv = 0.5 * np.abs(np.cross(t_uv[:, 1] - t_uv[:, 0], t_uv[:, 2] - t_uv[:, 0])) * size * size
        a_cm = 0.5 * np.linalg.norm(np.cross(t_co[:, 1] - t_co[:, 0], t_co[:, 2] - t_co[:, 0]), axis=1)
        ids, count = UV.islands(o)
        isl = ids[poly]
        per = np.sqrt(np.bincount(isl, a_uv, count) / np.maximum(np.bincount(isl, a_cm, count), 1.0e-9))
        tris.append(t_uv)
        dens.append(per[isl])
    if not tris:
        return np.zeros((0, 3, 2)), np.zeros(0)
    return np.concatenate(tris), np.concatenate(dens)


def edges_by_cm(weapon, normal, masks, px_cm):
    """Weapon.edge_px_cm (opt-in, read with getattr; off by default): the bake's convex, cavity and wide-zone masks worked out
    again by the centimetre (maps.edge_masks), so a bevel's edge wear is as wide in cm on a dense island as on a sparse one.
    px_cm: the density (px/cm on a 4096 sheet) the masks stay as baked at; an island twice as dense gets the curvature twice
    over and the wide zone's blur twice as many texels. The occlusion (R) and the hollows (from masks.npy) are as baked."""
    cover = np.load(os.path.join(weapon.bake_dir, 'cover.npy'))
    size = normal.shape[0]
    tris, dens = island_density(weapon)
    scale = maps.raster(tris, dens / px_cm, size)
    got = scale > 0.0
    maps.dilate([scale], got, steps=6)                       # the texels round an island's rim its triangles' centres missed
    scale = np.where(scale > 0.0, scale, 1.0)
    convex, concave, wide = maps.edge_masks(normal, cover, scale)
    out = masks.copy()
    out[..., 1], out[..., 2], out[..., 3] = (np.round(np.clip(a, 0, 1) * 255.0) / 255.0 for a in (convex, concave, wide))
    maps.dilate([out], cover, steps=max(8, size // 170))
    q = np.percentile(scale[cover], (5, 50, 95)) if cover.any() else (1, 1, 1)
    print('[texture] edges by the cm at %.1f px/cm (4096): texel density over it %.2f / %.2f / %.2f (5 / 50 / 95 %% of the cover)'
          % (px_cm, q[0], q[1], q[2]))
    return out


# ---------------------------------------------------------------------------------------------- texforge sets and decals
def material_dirs(weapon):
    """Where texforge sets (S.detail) and decals (Weapon.decals) are looked for, in this order: the weapon's own textures/
    folder; `_materials/` beside the weapons under the asset root the weapon is built in (a trial root's own copy); `_materials/`
    under the configured asset root (sets shared by several weapons); the folder the setting `materials` names, if any
    (weaponforge.toml or WEAPONFORGE_MATERIALS). A set is the folder <name>/ in one of them."""
    from .weapon import ASSET_ROOT
    from . import settings
    out = []
    for d in (weapon.tex_dir, os.path.join(os.path.dirname(weapon.asset_root), '_materials'), os.path.join(ASSET_ROOT, '_materials'),
              settings.get('materials')):
        if d and d not in out:
            out.append(d)
    return out


def find_set(weapon, name):
    """The folder of the texforge set or decal called `name` (it holds <name>_BaseColor.png), or None."""
    for d in material_dirs(weapon):
        if os.path.isfile(os.path.join(d, name, name + '_BaseColor.png')):
            return os.path.join(d, name)
    return None


_MISSING_SETS = []           # the sets texforge_sets did not find in this run, for load_maps' one line about them


def texforge_sets(weapon, *names):
    """For Weapon.images(): the BaseColor (key `name`) and Height (key `name_h`) of each tiling texforge set named, as data
    (Non-Color: S.detail measures and normalises them itself). A set that is not found is left out, and S.detail then gives
    None, so the recipe keeps its own procedural pattern (load_maps says once which sets were not found, and where it looked)."""
    out = {}
    for name in names:
        folder = find_set(weapon, name)
        if folder is None:
            if name not in _MISSING_SETS:
                _MISSING_SETS.append(name)
            continue
        out[name] = (os.path.join(folder, name + '_BaseColor.png'), 'Non-Color')
        if os.path.isfile(os.path.join(folder, name + '_Height.png')):
            out[name + '_h'] = (os.path.join(folder, name + '_Height.png'), 'Non-Color')
    return out


# ------------------------------------------------------------------------------------------------------- node builder
class Graph:
    def __init__(self, nt):
        self.nt = nt
        self.col = 0
        self.row = 0

    def new(self, kind, **props):
        node = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(node, k, v)
        node.location = (self.col * 190, -self.row * 150)
        self.row += 1
        if self.row > 9:
            self.row = 0
            self.col += 1
        return node

    def set(self, sock, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.nt.links.new(value, sock)
        elif value is not None:
            if isinstance(value, (tuple, list)) and len(value) == 3 and sock.type == 'RGBA':
                value = tuple(value) + (1.0,)
            sock.default_value = value

    def math(self, op, a, b=None, clamp=False):
        node = self.new('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.set(node.inputs[0], a)
        if b is not None:
            self.set(node.inputs[1], b)
        return node.outputs[0]

    def add(self, a, b, clamp=False):
        return self.math('ADD', a, b, clamp)

    def sub(self, a, b, clamp=False):
        return self.math('SUBTRACT', a, b, clamp)

    def mul(self, a, b, clamp=False):
        return self.math('MULTIPLY', a, b, clamp)

    def inv(self, a):
        return self.math('SUBTRACT', 1.0, a, True)

    def maxf(self, a, b):
        return self.math('MAXIMUM', a, b)

    def step(self, a, lo, hi):
        """Smooth step of a from lo..hi to 0..1."""
        node = self.new('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        self.set(node.inputs['Value'], a)
        node.inputs['From Min'].default_value = lo
        node.inputs['From Max'].default_value = hi
        return node.outputs[0]

    def mix(self, fac, a, b):
        node = self.new('ShaderNodeMix', data_type='RGBA', blend_type='MIX', clamp_factor=True)
        self.set(node.inputs[0], fac)
        self.set(node.inputs[6], a)
        self.set(node.inputs[7], b)
        return node.outputs[2]

    def mixf(self, fac, a, b):
        node = self.new('ShaderNodeMix', data_type='FLOAT', clamp_factor=True)
        self.set(node.inputs[0], fac)
        self.set(node.inputs[2], a)
        self.set(node.inputs[3], b)
        return node.outputs[0]

    def mapping(self, vec, scale=(1, 1, 1), rot=(0, 0, 0), loc=(0, 0, 0)):
        node = self.new('ShaderNodeMapping')
        self.set(node.inputs['Vector'], vec)
        node.inputs['Location'].default_value = loc
        node.inputs['Rotation'].default_value = [math.radians(v) for v in rot]
        node.inputs['Scale'].default_value = scale
        return node.outputs[0]

    def noise(self, vec, scale, detail=3.0, rough=0.5, distortion=0.0, lac=2.0):
        node = self.new('ShaderNodeTexNoise', noise_dimensions='3D')
        self.set(node.inputs['Vector'], vec)
        node.inputs['Scale'].default_value = scale
        node.inputs['Detail'].default_value = detail
        node.inputs['Roughness'].default_value = rough
        node.inputs['Lacunarity'].default_value = lac
        node.inputs['Distortion'].default_value = distortion
        return node.outputs[0]

    def image(self, img, uv=None):
        node = self.new('ShaderNodeTexImage', interpolation='Cubic')
        node.image = img
        if uv is not None:
            self.set(node.inputs[0], uv)
        return node

    def xyz(self, vec):
        node = self.new('ShaderNodeSeparateXYZ')
        self.set(node.inputs[0], vec)
        return node.outputs[0], node.outputs[1], node.outputs[2]

    def absf(self, a):
        return self.math('ABSOLUTE', a)

    def rgb(self, colour):
        node = self.new('ShaderNodeSeparateColor')
        self.set(node.inputs[0], colour)
        return node.outputs[0], node.outputs[1], node.outputs[2]

    def vmath(self, op, a, b=None):
        """Vector maths; LENGTH (and the other operations that give a number) returns the number."""
        node = self.new('ShaderNodeVectorMath', operation=op)
        self.set(node.inputs[0], a)
        if b is not None:
            self.set(node.inputs[1], b)
        return node.outputs[1] if op in ('LENGTH', 'DOT_PRODUCT', 'DISTANCE') else node.outputs[0]

    def times(self, colour, k):
        """colour multiplied by k: a number, a colour, or a socket."""
        node = self.new('ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY', clamp_factor=True)
        node.inputs[0].default_value = 1.0
        self.set(node.inputs[6], colour)
        self.set(node.inputs[7], (k, k, k) if isinstance(k, (int, float)) else k)
        return node.outputs[2]


# ---------------------------------------------------------------------------------------------------------- the surface
class Layer:
    """What a recipe returns. Each is a node socket or a constant; height None means "keep the height of what is underneath"."""

    def __init__(self, colour, rough, metal=0.0, height=None):
        self.colour = colour
        self.rough = rough
        self.metal = metal
        self.height = height


class Surface:
    def __init__(self, weapon, images, name=None):
        self.weapon = weapon
        self.images = images
        self.mat = bpy.data.materials.get(name or weapon.mat_author) or bpy.data.materials.new(name or weapon.mat_author)
        self.mat.use_nodes = True
        self.nt = self.mat.node_tree
        self.nt.nodes.clear()
        g = self.g = Graph(self.nt)
        self.pos = g.new('ShaderNodeNewGeometry').outputs['Position']      # world space: the parts keep their own pivots
        masks = g.image(images['masks'])
        self.ao, self.convex, self.cavity = g.rgb(masks.outputs[0])
        self.zone = masks.outputs[1]                                       # alpha: the broad wear zone around convex edges
        idr, idg, idb = g.rgb(g.image(images['id']).outputs[0])
        self._bits = [g.step(c, 0.25, 0.45) for c in (idr, idg, idb)]
        # where the lettering is, one mask per ink (kit.text_solid's `ink`), or None when the bake found no lettering
        self.lettering = g.rgb(g.image(images['marks']).outputs[0]) if images.get('marks') is not None else None
        self._nots = {}
        self._masks = {}
        self._made = {}

    # ---- one mask per surface kind, decoded from the ID map
    def mask(self, kind):
        """1 where the surface is of this kind (bake.KINDS or the weapon's own table), 0 elsewhere."""
        if kind not in self._masks:
            code = B.kinds_of(self.weapon)[kind].code
            out = None
            for i, bit in enumerate(code):
                if bit > 0.5:
                    term = self._bits[i]
                else:
                    if i not in self._nots:
                        self._nots[i] = self.g.inv(self._bits[i])
                    term = self._nots[i]
                out = term if out is None else self.g.mul(out, term)
            self._masks[kind] = out
        return self._masks[kind]

    def shared(self, key, make):
        """A value several recipes use, built once."""
        if key not in self._made:
            self._made[key] = make()
        return self._made[key]

    # ---- shared 3D noise (weapon frame, cm)
    @property
    def n_large(self):
        return self.shared('n_large', lambda: self.g.noise(self.pos, 0.33, 3.0, 0.55))

    @property
    def n_zone(self):
        return self.shared('n_zone', lambda: self.g.noise(self.g.mapping(self.pos, loc=(7.3, 2.1, 5.7)), 0.55, 2.0, 0.5))

    @property
    def n_med(self):
        return self.shared('n_med', lambda: self.g.noise(self.pos, 2.4, 4.0, 0.55))

    @property
    def n_fine(self):
        return self.shared('n_fine', lambda: self.g.noise(self.pos, 16.0, 3.0, 0.6))

    @property
    def n_spot(self):
        return self.shared('n_spot', lambda: self.g.noise(self.g.mapping(self.pos, loc=(3.1, 9.4, 1.2)), 6.5, 5.0, 0.62))

    @property
    def scratch(self):
        """Handling scratches: thin lines mostly along +X (the bore), a second sparse set across."""
        def make():
            g = self.g
            s1 = g.noise(g.mapping(self.pos, scale=(0.35, 30.0, 30.0), rot=(0, 4, 3)), 1.0, 2.0, 0.5)
            s2 = g.noise(g.mapping(self.pos, scale=(0.5, 26.0, 26.0), rot=(12, 38, 21), loc=(4.0, 1.0, 2.0)), 1.0, 2.0, 0.5)
            lines = g.maxf(g.step(s1, 0.705, 0.725), g.mul(g.step(s2, 0.715, 0.735), 0.7))
            return g.mul(lines, g.step(self.n_med, 0.46, 0.66))
        return self.shared('scratch', make)

    # ---- where the weapon is touched (Weapon.handled / .smooth / .textured): a mask, or None when the weapon names no zone
    @property
    def handled(self):
        return zones(self, getattr(self.weapon, 'handled', None), 'handled')

    @property
    def smooth(self):
        return zones(self, getattr(self.weapon, 'smooth', None), 'smooth')

    @property
    def textured(self):
        return zones(self, getattr(self.weapon, 'textured', None), 'textured')

    # ---- the output
    def output(self, layer):
        """Wire a finished Layer to the shader, with the taps the texture bake reads. Returns the material."""
        g, nt = self.g, self.nt
        rough = g.math('MAXIMUM', g.math('MINIMUM', layer.rough, 0.95), 0.12)
        nmap = g.new('ShaderNodeNormalMap', space='TANGENT')
        g.set(nmap.inputs['Color'], g.image(self.images['normal']).outputs[0])
        bump = g.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.6
        bump.inputs['Distance'].default_value = 0.004
        g.set(bump.inputs['Height'], layer.height if layer.height is not None else 0.0)
        g.set(bump.inputs['Normal'], nmap.outputs[0])
        bsdf = g.new('ShaderNodeBsdfPrincipled')
        bsdf.name = 'BSDF'
        out = g.new('ShaderNodeOutputMaterial')
        out.name = 'OUT'
        one = g.new('ShaderNodeValue')
        one.outputs[0].default_value = 1.0
        taps = {}
        for key, value in (('colour', layer.colour), ('rough', rough), ('metal', layer.metal), ('ao', self.ao), ('cover', one.outputs[0])):
            if not isinstance(value, bpy.types.NodeSocket):                # a constant: give it a socket to tap
                if isinstance(value, (tuple, list)):
                    node = g.new('ShaderNodeRGB')
                    node.outputs[0].default_value = tuple(value)[:3] + (1.0,)
                else:
                    node = g.new('ShaderNodeValue')
                    node.outputs[0].default_value = float(value)
                value = node.outputs[0]
            r = g.new('NodeReroute')
            r.name = 'TAP_' + key
            nt.links.new(value, r.inputs[0])
            taps[key] = r
        nt.links.new(taps['colour'].outputs[0], bsdf.inputs['Base Color'])
        nt.links.new(taps['rough'].outputs[0], bsdf.inputs['Roughness'])
        nt.links.new(taps['metal'].outputs[0], bsdf.inputs['Metallic'])
        nt.links.new(bump.outputs[0], bsdf.inputs['Normal'])
        nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
        em = g.new('ShaderNodeEmission')
        em.name = 'TAP_EMIT'
        target = g.new('ShaderNodeTexImage')
        target.name = 'target'
        return self.mat


# ------------------------------------------------------------------------------------------------- wear by use and exposure
# What the recipes' opt-in arguments (handled, exposure, recess, vary; polymer's smooth, textured, fade) are built from. Every
# one is made the first time a recipe asks for it, so a weapon that asks for none of them gets the very graph it had before.
def zones(s, boxes, key):
    """1 inside the weapon-frame boxes (weapon.Zone), fading out over each one's `soft` cm beyond it, scaled by its strength;
    the strongest zone wins where they overlap. None when there are no boxes. The fade's edge is broken by noise."""
    if not boxes:
        return None

    def make():
        g = s.g
        out = None
        for z in boxes:
            centre = tuple((a + b) / 2.0 for a, b in zip(z.lo, z.hi))
            half = tuple((b - a) / 2.0 for a, b in zip(z.lo, z.hi))
            v = g.vmath('SUBTRACT', s.pos, centre)
            if z.tilt:
                # the box is turned by kit.rot_y(tilt) (+Z toward -X); turning the point the other way puts it in the box's axes
                rot = g.new('ShaderNodeVectorRotate', rotation_type='Y_AXIS')
                g.set(rot.inputs['Vector'], v)
                rot.inputs['Angle'].default_value = math.radians(z.tilt)
                v = rot.outputs[0]
            v = g.vmath('MAXIMUM', g.vmath('SUBTRACT', g.vmath('ABSOLUTE', v), half), (0.0, 0.0, 0.0))
            soft = max(z.soft, 0.01)
            d = g.add(g.vmath('LENGTH', v), g.mul(g.sub(s.n_med, 0.5), 0.9 * soft))
            m = g.step(d, soft, 0.0)
            if z.strength != 1.0:
                m = g.mul(m, z.strength)
            out = m if out is None else g.maxf(out, m)
        return out
    return s.shared('zones_' + key, make)


def hollow_map(weapon, images):
    """The floors of grooves and pockets as a picture: the bake's concave mask (masks.npy, blue) blurred inside the islands
    the way the broad edge zone is blurred from the convex one (maps.process). The cavity mask itself is only the crease at a
    groove's floor, and the broad edge zone fills a narrow groove from its two lips, so without this a flute's floor reads
    as an edge. Derived when a recipe first asks for it (no bake pass); written to the work folder."""
    if images.get('hollows') is None:
        m = np.load(os.path.join(weapon.bake_dir, 'masks.npy'))
        cover = np.load(os.path.join(weapon.bake_dir, 'cover.npy'))
        concave = m[..., 2].astype(np.float32) / 255.0
        rel = concave.shape[0] / 4096.0
        wide = np.clip(maps.masked_blur(concave, cover, max(1, int(4 * rel + 0.5)), passes=2) * 3.0, 0.0, 1.0)
        maps.dilate([wide], cover, steps=max(8, concave.shape[0] // 170))
        images['hollows'] = image_from(np.repeat(wide[..., None], 3, axis=2), weapon.tag + '_hollows',
                                       os.path.join(weapon.work_dir, weapon.tag.lower() + '_hollows.png'), False)
    return images['hollows']


def hollows(s):
    """1 across the floor of a groove, a flute, a vent or a panel line, 0 on open faces and outside edges."""
    return s.shared('hollows', lambda: s.g.rgb(s.g.image(hollow_map(s.weapon, s.images)).outputs[0])[0])


def exposed(s):
    """1 out in the open, 0 in the shelter of a wall, a recess or a neighbouring part (from the occlusion bake and the floors
    of grooves)."""
    return s.shared('exposed', lambda: s.g.mul(s.g.step(s.ao, 0.72, 0.97), s.g.sub(1.0, s.g.mul(hollows(s), 0.8)), True))


def corner(s):
    """1 where edges stand out: the broad edge zone is strong where edges meet and on big outside corners; not inside a
    narrow groove, where the zone is strong only because both lips are near."""
    return s.shared('corner', lambda: s.g.mul(s.g.step(s.zone, 0.30, 0.80), s.g.inv(hollows(s))))


def stretches(s):
    """Rubbed stretches along an edge, a centimetre or two long, mostly along the weapon, with gaps between them."""
    def make():
        g = s.g
        n = g.noise(g.mapping(s.pos, scale=(0.45, 1.0, 1.0), loc=(5.3, 2.2, 9.1)), 1.4, 3.0, 0.55)
        return g.step(n, 0.44, 0.60)
    return s.shared('stretches', make)


def chips(s):
    """Small chips, about a millimetre, scattered."""
    return s.shared('chips', lambda: s.g.step(s.g.noise(s.g.mapping(s.pos, loc=(8.6, 3.9, 6.4)), 7.5, 4.0, 0.65), 0.615, 0.665))


def recesses(s):
    """1 in grooves, pockets, panel lines and the ring round a boss: where dust and grime gather. From the cavity mask (the
    crease at a groove's floor) and the occlusion (a pocket's floor), with a little noise so it is not one even fill."""
    def make():
        g = s.g
        pocket = g.step(s.ao, 0.96, 0.55)
        groove = g.mul(g.step(s.cavity, 0.05, 0.40), 0.75)       # not full on fine checkering, or it goes black (PLAYBOOK "Textures and look", item 5)
        floor = g.step(hollows(s), 0.30, 0.80)
        return g.mul(g.maxf(g.maxf(pocket, groove), floor), g.add(0.55, g.mul(s.n_med, 0.7)), True)
    return s.shared('recesses', make)


def smudges(s):
    """Greasy, glossier patches a few cm across, where hands and oil have been."""
    return s.shared('smudges', lambda: s.g.step(s.g.noise(s.g.mapping(s.pos, loc=(4.1, 8.8, 2.6)), 0.9, 4.0, 0.6, distortion=0.8),
                                                0.57, 0.74))


def mid_rough(s):
    """Roughness variation a few millimetres across, between the broad clouds and the fine pitting: about -0.5..0.5."""
    return s.shared('mid_rough', lambda: s.g.sub(s.g.noise(s.g.mapping(s.pos, loc=(1.3, 5.7, 3.1)), 4.5, 3.0, 0.55), 0.5))


def scuffs(s, dense=None, key='sparse'):
    """Fine scratches along the direction of handling (+X, the way a weapon slides in and out of hands and racks) and a few
    across it, sparse, denser where `dense` (a mask) is high. key: one name per distinct `dense`, so each is built once."""
    def make():
        g = s.g
        l1 = g.step(g.noise(g.mapping(s.pos, scale=(0.22, 34.0, 34.0), rot=(0, 2.5, 4.0), loc=(2.0, 7.0, 1.0)), 1.0, 2.0, 0.5), 0.715, 0.728)
        l2 = g.step(g.noise(g.mapping(s.pos, scale=(0.30, 28.0, 28.0), rot=(25, 50, 30), loc=(6.0, 3.0, 4.0)), 1.0, 2.0, 0.5), 0.720, 0.733)
        lines = g.maxf(l1, g.mul(l2, 0.6))
        gate = g.noise(g.mapping(s.pos, loc=(9.2, 4.4, 0.7)), 1.6, 3.0, 0.55)
        if dense is not None:
            gate = g.add(gate, g.mul(dense, 0.30))
        return g.mul(lines, g.step(gate, 0.64, 0.74))
    return s.shared('scuffs_' + key, make)


def edge_wear(s, line, handled=None):
    """`line` (an edge mask, 0..1) weighted by exposure and broken up: strong on corners that stand out, weak on edges in
    shelter, in rubbed stretches rather than one line, with chips beside it on exposed corners; full where handled."""
    g = s.g
    weight = g.mul(exposed(s), g.add(0.25, g.mul(corner(s), 0.85)))
    if handled is not None:
        weight = g.maxf(weight, g.mul(handled, 1.15))
    wear = g.mul(g.mul(line, weight), g.mixf(stretches(s), 0.35, 1.0), True)
    near = g.mul(chips(s), g.step(s.zone, 0.10, 0.40))
    hit = g.mul(corner(s), 0.8)
    if handled is not None:
        hit = g.maxf(hit, g.mul(handled, 0.7))
    return g.maxf(wear, g.mul(g.mul(near, exposed(s)), hit))


def stack(s, base, *overlays):
    """base with each (mask, layer) laid over it in turn."""
    g = s.g
    colour, rough, metal, height = base.colour, base.rough, base.metal, base.height
    for mask, layer in overlays:
        colour = g.mix(mask, colour, layer.colour)
        rough = g.mixf(mask, rough, layer.rough)
        metal = g.mixf(mask, metal, layer.metal)
        if layer.height is not None:
            height = layer.height if height is None else g.mixf(mask, height, layer.height)
    return Layer(colour, rough, metal, height)


# What fills engraved lettering (Weapon.paint). Paint is not metal and not glossy; the white is the off-white of a paint stick
# rubbed into the cut, not paper white, or it glares beside black steel
PAINT = {
    'white': (0.62, 0.61, 0.57),
    'red': (0.46, 0.030, 0.022),
    'yellow': (0.64, 0.47, 0.05),
    'green': (0.06, 0.30, 0.09),
    'gold': (0.55, 0.40, 0.14),
}


def paint(s, layer, inks, wear=0.35, rough=0.58):
    """`layer` with its engraved lettering filled with paint. inks: the paint for each ink number the weapon's text was cut
    with (kit.text_solid's `ink`, 0 unless said): a name in PAINT, a colour, or None for letters left bare.
    wear: how much of the paint has come out (0 fresh, 1 mostly gone); it goes in specks, and the letters stay readable
    because the engraving under it is still there. Without a lettering mask (a bake made before the tool kept one, or a
    weapon with no text) the layer comes back as it is."""
    if s.lettering is None or not inks:
        return layer
    g = s.g
    stays = g.inv(g.mul(g.step(s.n_spot, 0.70 - 0.22 * wear, 0.84 - 0.22 * wear), min(1.0, 0.4 + wear), True))
    grime = g.mixf(g.step(s.n_med, 0.35, 0.75), 0.72, 1.0)                 # the paint is not one flat colour either
    colour, rgh, metal = layer.colour, layer.rough, layer.metal
    for ink, mask in zip(inks, s.lettering):
        if ink is None:
            continue
        if isinstance(ink, str):
            if ink not in PAINT:
                raise KeyError('no paint called %r: there are %s' % (ink, ', '.join(sorted(PAINT))))
            ink = PAINT[ink]
        tone = g.new('ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY', clamp_factor=True)
        tone.inputs[0].default_value = 1.0
        g.set(tone.inputs[6], tuple(ink))
        g.set(tone.inputs[7], grime)                    # a number into a colour socket: the same in all three channels
        on = g.mul(g.step(mask, 0.30, 0.70), stays, True)
        colour = g.mix(on, colour, tone.outputs[2])
        rgh = g.mixf(on, rgh, rough)
        metal = g.mixf(on, metal, 0.0)
    return Layer(colour, rgh, metal, layer.height)


# ------------------------------------------------------------------------------------------- painted detail (texforge sets)
# A tiling texforge set made from a painted picture (texforge, `make`) laid on the weapon by position, the way
# `wood` lays its plank: what a texture artist adds by hand that noise cannot (a mould's spark-eroded grain, a bead-blast,
# machining passes). Only its BaseColor and Height are used, and both only as VARIATION: each is measured when it is loaded
# and normalised to mean 0 and one standard deviation, so the recipe keeps its own hue and value and the set only says
# where it is lighter or darker, higher or lower. texforge's own Normal (DirectX), roughness and shadow lift are not for
# this (PLAYBOOK "Textures and look" 6 and 19).
DETAIL_SHARP = 4.0                    # a box projection's weight is |normal along its axis| ** this: higher, a narrower blend
DETAIL_CLIP = 3.0                     # a variation is clipped at this many standard deviations: a stray pixel makes no hole
DETAIL_HEIGHT = 0.13                  # height at detail_relief=1 per standard deviation, in the bump node's units: about the
#                                       depth of polymer's procedural grain at grain=1
DETAIL_SHIFT = ((0.00, 0.00), (0.37, 0.61), (0.71, 0.23))   # where each of the three projections starts in the tile, so
#                                                             their repeats do not line up along a corner
LUMA = (0.2126, 0.7152, 0.0722)


class Detail:
    """A texforge set ready to lay on: its BaseColor and Height images (data), one tile's size in cm (u, v), and the
    measured mean and spread of each. around=(y, z): projected round a line along +X through that point instead of
    through the three sides, with the picture's u round it and v along it (a lathe-turned barrel: a picture of horizontal
    lines becomes rings)."""

    def __init__(self, name, colour, height, world_cm, around=None):
        self.name = name
        self.colour = colour
        self.height = height
        self.world_cm = world_cm
        self.around = around
        self.c_stats = _stats(colour, luma=True)
        self.h_stats = _stats(height, luma=False) if height is not None else None


def _stats(img, luma):
    """(mean, standard deviation) of an image's luminance (or its first channel), as the shader reads it (data)."""
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    v = px[:, :3] @ np.array(LUMA, dtype=np.float32) if luma else px[:, 0]
    return float(v.mean()), max(float(v.std()), 1.0e-4)


def _world_cm(img, name):
    """One tile's (width, height) in cm, from the set's <name>.texforge.json beside its pictures."""
    import json
    path = os.path.join(os.path.dirname(bpy.path.abspath(img.filepath)), name + '.texforge.json')
    with open(path, 'r', encoding='utf-8') as fh:
        cm = json.load(fh)['world_cm']
    return (float(cm[0]), float(cm[1])) if isinstance(cm, (list, tuple)) else (float(cm), float(cm))


def detail(s, name, around=None, world_cm=None):
    """The texforge set `name` (loaded by Weapon.images through texforge_sets) as a Detail for a recipe's `detail=`, or None
    when it is not there (the recipe then keeps its procedural pattern). world_cm overrides the set's own tile size."""
    img = s.images.get(name)
    if img is None:
        return None
    key = 'detail_%s_%s_%s' % (name, around, world_cm)
    return s.shared(key, lambda: Detail(name, img, s.images.get(name + '_h'), world_cm or _world_cm(img, name), around))


def _unit(g, value, stats):
    """(value - mean) / spread, clipped: a variation of mean 0 and one standard deviation."""
    v = g.mul(g.sub(value, stats[0]), 1.0 / stats[1])
    return g.math('MAXIMUM', g.math('MINIMUM', v, DETAIL_CLIP), -DETAIL_CLIP)


def _sample(s, d, u, v, shift):
    """Both of the set's variations at tile coordinates (u, v) (cm / world_cm, plus a shift)."""
    g = s.g
    uv = g.new('ShaderNodeCombineXYZ')
    g.set(uv.inputs[0], g.add(u, shift[0]))
    g.set(uv.inputs[1], g.add(v, shift[1]))
    tone = _unit(g, g.vmath('DOT_PRODUCT', g.image(d.colour, uv.outputs[0]).outputs[0], LUMA), d.c_stats)
    bump = _unit(g, g.rgb(g.image(d.height, uv.outputs[0]).outputs[0])[0], d.h_stats) if d.height is not None else None
    return tone, bump


def _blend(g, parts):
    """[(weight, tone, bump)] -> one (tone, bump). Weights sum to 1; dividing by sqrt(sum of squared weights) keeps one
    standard deviation where two uncorrelated pictures overlap, so the grain does not fade along the blend between faces."""
    tone = bump = norm = None
    for w, t, b in parts:
        tone = g.mul(w, t) if tone is None else g.add(tone, g.mul(w, t))
        if b is not None:
            bump = g.mul(w, b) if bump is None else g.add(bump, g.mul(w, b))
        norm = g.mul(w, w) if norm is None else g.add(norm, g.mul(w, w))
    k = g.math('INVERSE_SQRT', g.maxf(norm, 1.0e-4))
    return g.mul(tone, k), (g.mul(bump, k) if bump is not None else None)


def _project(s, d):
    """The set laid on by position: a box projection through the three sides of the weapon frame, blended by the normal,
    or (d.around) round a line along +X, falling back to the box projection along X on faces that look along it."""
    def make():
        g = s.g
        x, y, z = g.xyz(s.pos)
        nx, ny, nz = (g.absf(c) for c in g.xyz(g.new('ShaderNodeNewGeometry').outputs['Normal']))
        wu, wv = d.world_cm
        planes = ((nx, y, z), (ny, x, z), (nz, x, y))                       # each side's two axes, u then v
        if d.around is None:
            raw = [g.math('POWER', n, DETAIL_SHARP) for n, _a, _b in planes]
            total = g.add(g.add(raw[0], raw[1]), raw[2])
            parts = []
            for i, ((_n, a, b), r) in enumerate(zip(planes, raw)):
                t, bb = _sample(s, d, g.mul(a, 1.0 / wu), g.mul(b, 1.0 / wv), DETAIL_SHIFT[i])
                parts.append((g.math('DIVIDE', r, total), t, bb))
            return _blend(g, parts)
        dy, dz = g.sub(y, d.around[0]), g.sub(z, d.around[1])
        radius = g.math('SQRT', g.add(g.mul(dy, dy), g.mul(dz, dz)))
        turn = g.mul(g.math('ARCTAN2', dy, dz), 0.5 / math.pi)              # -0.5..0.5, the wrap underneath (-Z)
        tiles = g.maxf(g.math('ROUND', g.mul(radius, 2.0 * math.pi / wu)), 1.0)   # a whole number of tiles round: no seam
        t_c, b_c = _sample(s, d, g.mul(turn, tiles), g.mul(x, 1.0 / wv), DETAIL_SHIFT[0])
        t_e, b_e = _sample(s, d, g.mul(y, 1.0 / wu), g.mul(z, 1.0 / wv), DETAIL_SHIFT[1])
        end = g.step(nx, 0.55, 0.85)                                         # a shoulder or a face that looks along the bore
        return g.mixf(end, t_c, t_e), (g.mixf(end, b_c, b_e) if b_c is not None else None)
    return s.shared('proj_' + d.name + str(d.around), make)


def detail_terms(s, detail):
    """(tone, bump): the set's two variations where the weapon is, mean 0, one standard deviation (bump None without a
    Height). detail: a Detail, or [(mask, Detail), ...] for different sets on different parts of one recipe (0 where no
    mask is)."""
    g = s.g
    if isinstance(detail, Detail):
        return _project(s, detail)
    tone = bump = None
    for mask, d in detail:
        if d is None:
            continue
        t, b = _project(s, d)
        tone = g.mul(mask, t) if tone is None else g.add(tone, g.mul(mask, t))
        if b is not None:
            bump = g.mul(mask, b) if bump is None else g.add(bump, g.mul(mask, b))
    return (tone if tone is not None else 0.0), bump


def has_detail(detail):
    """True when a recipe's `detail` argument asks for anything (a Detail, or a list with at least one found set)."""
    if detail is None:
        return False
    return isinstance(detail, Detail) or any(d is not None for _m, d in detail)


def tone_by(g, colour, tone, strength):
    """colour made lighter and darker by a unit variation: strength is the relative spread of its brightness (0.15: one
    standard deviation of the set is 15 % lighter or darker). The hue stays the recipe's."""
    return g.times(colour, g.maxf(g.add(1.0, g.mul(tone, strength)), 0.25))


# ------------------------------------------------------------------------------------------------------------------ decals
DECAL_FACING = (0.20, 0.55)           # a face takes a decal from this cosine to its side on (fully from the second)
DECAL_GRIME = (0.30, 0.26, 0.20)      # what `darken` multiplies the colour by at 1: oil and dust are brown, not grey
# where a decal's direction lies along the weapon frame, and its picture's u and v: (axis, sign) of the box's own axes
DECAL_AXES = {'+Y': ((0.0, 1.0, 0.0), (0, -1.0), (2, 1.0)), '-Y': ((0.0, -1.0, 0.0), (0, 1.0), (2, 1.0)),
              '+Z': ((0.0, 0.0, 1.0), (1, -1.0), (0, 1.0)), '-Z': ((0.0, 0.0, -1.0), (1, 1.0), (0, 1.0)),
              '+X': ((1.0, 0.0, 0.0), (1, 1.0), (2, 1.0)), '-X': ((-1.0, 0.0, 0.0), (1, -1.0), (2, 1.0))}


def _decal_wear(s):
    """Where a decal is rubbed off: exposed convex edges and corners, the handled zones, and specks all over."""
    def make():
        g = s.g
        rub = g.maxf(g.step(g.mul(s.convex, g.add(0.6, g.mul(s.n_med, 0.8))), 0.15, 0.55), g.mul(g.step(s.zone, 0.35, 0.85), 0.8))
        if s.handled is not None:
            rub = g.maxf(rub, g.mul(s.handled, 0.75))
        return g.maxf(rub, g.mul(g.step(s.n_spot, 0.64, 0.76), 0.85))
    return s.shared('decal_wear', make)


def decal_reach(weapon, d):
    """What a decal can land on: (triangles, cm2, part names) of the game mesh that look toward its side (the cosine over the first
    of DECAL_FACING, the material's own test) and have a box that meets the decal's box. The area is an estimate: each triangle whose box
    meets the decal's is sampled at 21 points (a thin box on a big triangle may then show an area near 0, which is only the estimate:
    the triangle is counted). A triangle bigger than a thin decal box is found."""
    from mathutils import Matrix, Vector
    facing = Vector(DECAL_AXES[d.side][0])
    centre = Vector([(a + b) / 2.0 for a, b in zip(d.lo, d.hi)])
    half = [(b - a) / 2.0 for a, b in zip(d.lo, d.hi)]
    turn = Matrix.Rotation(math.radians(d.tilt), 3, 'Y') if d.tilt else None
    grid = [(i / 5.0, j / 5.0) for i in range(6) for j in range(6 - i)]
    tris, area, names = 0, 0.0, []
    for o in _lp_objects(weapon):
        mesh = o.data
        mesh.calc_loop_triangles()
        m = o.matrix_world
        hit = 0
        for t in mesh.loop_triangles:
            p = [m @ mesh.vertices[i].co for i in t.vertices]
            n = (p[1] - p[0]).cross(p[2] - p[0])
            a = n.length / 2.0
            if a < 1.0e-12:
                continue
            n = n / (2.0 * a)
            q = [v - centre for v in p]
            if turn is not None:
                q, n = [turn @ v for v in q], turn @ n
            if n.dot(facing) <= DECAL_FACING[0]:
                continue
            if any(min(v[i] for v in q) > half[i] or max(v[i] for v in q) < -half[i] for i in range(3)):
                continue
            inside = sum(1 for u, w in grid if all(abs((q[0] * (1 - u - w) + q[1] * u + q[2] * w)[i]) <= half[i] for i in range(3)))
            hit += 1
            area += a * inside / len(grid)
        if hit:
            tris += hit
            names.append(o.name)
    return tris, area, names


def _lp_objects(weapon):
    coll = bpy.data.collections.get(weapon.coll('LP'))
    return [o for o in (coll.all_objects if coll else ()) if o.type == 'MESH']


def decals(s, layer, items):
    """`layer` with each weapon.Decal laid over it in turn: projected through its box from its side, only onto faces that
    look that way, clipped to the box, broken up by wear; then colour, darkening, roughness, metal and height where the
    decal says so. Called by build() only when the weapon declares decals."""
    g = s.g
    colour, rough, metal, height = layer.colour, layer.rough, layer.metal, layer.height
    normal = g.new('ShaderNodeNewGeometry').outputs['Normal']
    for d in items:
        label = '%s on %s%s' % (d.image, d.side, (' (' + d.note + ')') if d.note else '')
        if 'decal_%s_BaseColor' % d.image not in s.images:      # its picture was not found (load_maps said so): left out
            print('[texture] decal %s: SKIPPED, its picture %s_BaseColor.png was not found in %s'
                  % (label, d.image, ', '.join(material_dirs(s.weapon))))
            continue
        tris, area, names = decal_reach(s.weapon, d)
        if tris:
            print('[texture] decal %s: applied, strength %.2f, box x %.1f..%.1f y %.1f..%.1f z %.1f..%.1f; reaches %d game triangles '
                  '(about %.2f cm2 inside the box) of %s' % (label, d.strength, d.lo[0], d.hi[0], d.lo[1], d.hi[1], d.lo[2], d.hi[2], tris, area, ', '.join(names)))
        else:
            print('[texture] decal %s: applied, but it reaches NO face of the game mesh: nothing inside its box (x %.1f..%.1f y %.1f..%.1f '
                  'z %.1f..%.1f) looks toward %s' % (label, d.lo[0], d.hi[0], d.lo[1], d.hi[1], d.lo[2], d.hi[2], d.side))
        centre = tuple((a + b) / 2.0 for a, b in zip(d.lo, d.hi))
        half = tuple((b - a) / 2.0 for a, b in zip(d.lo, d.hi))
        v, n = g.vmath('SUBTRACT', s.pos, centre), normal
        if d.tilt:
            # as zones(): the box is turned by kit.rot_y(tilt); turn the point and the normal back into its axes
            for sock in ('v', 'n'):
                rot = g.new('ShaderNodeVectorRotate', rotation_type='Y_AXIS')
                g.set(rot.inputs['Vector'], v if sock == 'v' else n)
                rot.inputs['Angle'].default_value = math.radians(d.tilt)
                if sock == 'v':
                    v = rot.outputs[0]
                else:
                    n = rot.outputs[0]
        local = g.xyz(v)
        out = g.vmath('MAXIMUM', g.vmath('SUBTRACT', g.vmath('ABSOLUTE', v), half), (0.0, 0.0, 0.0))
        inside = g.step(g.vmath('LENGTH', out), 0.02, 0.0)                     # clipped to the box, a hair soft
        facing, (ua, us), (va, vs) = DECAL_AXES[d.side]
        face = g.step(g.vmath('DOT_PRODUCT', n, facing), DECAL_FACING[0], DECAL_FACING[1])
        key = 'decal_%s_' % d.image
        # the picture is fitted inside the box, keeping its own aspect, centred (texforge crops a decal to its mark)
        w, h = s.images[key + 'BaseColor'].size
        hu, hv = half[ua], half[va]
        if not d.stretch:
            hu, hv = min(hu, hv * w / float(h)), min(hv, hu * h / float(w))
        uv = g.new('ShaderNodeCombineXYZ')
        g.set(uv.inputs[0], g.add(0.5, g.mul(local[ua], us * 0.5 / hu)))
        g.set(uv.inputs[1], g.add(0.5, g.mul(local[va], vs * 0.5 / hv)))
        pic = g.image(s.images[key + 'BaseColor'], uv.outputs[0])
        pic.extension = 'CLIP'
        opa = g.image(s.images[key + 'Opacity'], uv.outputs[0])
        opa.extension = 'CLIP'
        alpha = g.mul(g.mul(g.rgb(opa.outputs[0])[0], inside), face, True)
        if d.strength != 1.0:
            alpha = g.mul(alpha, d.strength, True)
        if d.wear:
            alpha = g.mul(alpha, g.sub(1.0, g.mul(_decal_wear(s), d.wear), True), True)
        if d.darken:
            colour = g.mix(g.mul(alpha, d.darken, True), colour, g.times(colour, DECAL_GRIME))
        if d.colour is True:
            colour = g.mix(alpha, colour, pic.outputs[0])
        elif d.colour is not None:
            colour = g.mix(alpha, colour, tuple(d.colour))
        if isinstance(d.rough, (tuple, list)):
            light = g.step(g.vmath('DOT_PRODUCT', pic.outputs[0], LUMA), 0.0, 0.5)
            rough = g.mixf(alpha, rough, g.mixf(light, d.rough[0], d.rough[1]))
        elif d.rough is not None:
            rough = g.mixf(alpha, rough, float(d.rough))
        if d.metal is not None:
            metal = g.mixf(alpha, metal, float(d.metal))
        lift = None
        if d.relief and s.images.get(key + 'Height') is not None:
            hgt = g.image(s.images[key + 'Height'], uv.outputs[0])
            hgt.extension = 'CLIP'
            lift = g.mul(g.mul(g.sub(g.rgb(hgt.outputs[0])[0], 0.5), d.relief), alpha)
        if d.thick:
            step = g.mul(alpha, d.thick)
            lift = step if lift is None else g.add(lift, step)
        if lift is not None:
            height = lift if height is None else g.add(height, lift)
    return Layer(colour, rough, metal, height)


def build(weapon, images):
    """The weapon's authoring material: Weapon.surface(s) over the baked maps, then its decals (Weapon.decals), then the
    lettering's paint (Weapon.paint)."""
    s = Surface(weapon, images)
    layer = weapon.surface(s)
    if getattr(weapon, 'decals', None):
        layer = decals(s, layer, weapon.decals)
    if weapon.paint:
        layer = paint(s, layer, weapon.paint, wear=weapon.paint_wear)
    return s.output(layer)


def assign(objs, mat):
    for obj in objs:
        obj.data.materials.clear()
        obj.data.materials.append(mat)


# -------------------------------------------------------------------------------------------------------------- recipes
def worn_steel(s, bright=None, dark=None, blue=((0.012, 0.014, 0.020), (0.030, 0.033, 0.044)),
               black=((0.010, 0.010, 0.012), (0.022, 0.022, 0.025)), white=((0.42, 0.42, 0.41), (0.55, 0.55, 0.53)), rust=1.0,
               gloss=((0.24, 0.36), (0.20, 0.30), (0.38, 0.48)), plum=((0.046, 0.030, 0.030), 0.55),
               thin=((0.105, 0.098, 0.092), 0.80, 0.36), edges=1.0, scratches=1.0, coat=0.0, case=0.0, cloud=1.0, brush=0.0,
               fill=0.0, dirt=1.0, handled=None, exposure=0.0, recess=0.0, vary=0.0, detail=None, detail_tone=0.0,
               detail_relief=1.0, detail_rough=0.0, vary_broad=None):
    """Blued steel that has been carried: bluing rubbed thin on the high spots, bare edges, handling scratches, rust freckles in
    patches, grime in the cuts. bright / dark: masks (s.mask(...)) of the parts that are bare polished steel / black instead.
    blue, black, white: (dark, light) colour pairs of the three finishes. rust: 0 for none.

    The defaults are the reference blued look and must stay what they are (they keep earlier builds unchanged). Everything
    after `rust` is there so that not every gun wears the same steel; STEEL holds named sets of them:
      gloss      roughness (dark, light) of the main finish, of bare steel, of the black parts
      plum       (colour, amount) of the plum-brown patches old bluing turns to
      thin       (colour, amount, roughness) where the finish is rubbed thin round edges and high spots
      edges      how much bare metal shows on the edges themselves (1 = the default)
      scratches  how much the handling scratches show (1 = the default)
      coat       1 when the main and the black finish are paint or lacquer, not an oxide: no metal shows except where it is
                 worn through (the thin places, the edges, the scratches)
      case       0..1: colour case-hardening on the bare parts, mottled blue, straw and grey, instead of plain white steel
    The last four are there because a bright finish shows what a dark one hides. On bright steel the default broad light and
    dark clouds read as smoke and its soft grime as soot, and engraving nearly vanishes:
      cloud      how much of the broad light-and-dark variation is kept (1 = the default; a clean bright finish wants 0.3)
      brush      0..1: the finish is brushed along the weapon: fine streaks along +X in the roughness and the colour, and
                 the fine pitting in the relief gives way to them. It is what makes bright steel read as metal, not paint
      fill       0..1: engraving and other sharp cuts are filled dark (blacking, or just shadow), so markings can be read.
                 Only where the finish is not black (the `dark` mask): a cut in a black part keeps its own light edge
      dirt       how much of the soft grime round every recess is kept (1 = the default)
    The last four say where the wear comes from: use and exposure, not curvature alone (a pale line on every convex edge
    reads as a mask, not as use). All are off by default; `polymer` takes the same four:
      handled    a mask (s.handled, from Weapon.handled): where hands, gear and the ground touch the weapon. There the
                 finish is rubbed thin over the high spots, the edges wear through to bare metal and scratches are denser
      exposure   0..1: the bare edges and the rubbed-thin band are weighted by exposure (strong on corners that stand out,
                 weak on edges in shelter, from the occlusion and the broad edge zone) and broken into rubbed stretches
                 and chips; at 1 the even line round every edge is gone
      recess     0..1: grime in grooves, pockets, panel lines and round bosses (cavity and occlusion): darker and rougher
      vary       0..1: roughness as the main channel: a broad drift, greasy glossier smudges, a millimetre-scale variation,
                 a hair of tone drift, and sparse fine scratches along the weapon (denser where handled)
      vary_broad 0..1, None (the default) = the same as `vary`: how much of vary's BROAD part is kept: the drift of roughness
                 over many cm, the greasy smudges a few cm across and the patches of paler tone (these are what read as smudged
                 paint on a flat wall). The millimetre variation and the scuffs follow `vary` alone. vary=1, vary_broad=0.2 is
                 the fine variation with the mottling turned down; vary=0 with a vary_broad is the broad part alone
    A painted texforge set under the wear (off by default; `polymer` takes the same four; PLAYBOOK "Textures and look" 19):
      detail        S.detail(s, name): a bead-blast, a phosphate's crystals, machining passes, laid on by position; or
                    [(mask, S.detail(...)), ...] for one set on the rail and another on the sights
      detail_tone   how much it lightens and darkens the finish: the relative spread of the brightness (0.15 = 15 %)
      detail_relief how deep it goes into the normal map, 1 = about polymer's procedural grain
      detail_rough  how much its high spots are glossier and its low spots drier (roughness per standard deviation)
    The bare edges, scratches, rust and grime lie over it, as they would."""
    g = s.g
    bright = 0.0 if bright is None else bright
    dark = 0.0 if dark is None else dark
    not_bright = g.inv(bright)
    n_large, n_zone, n_med, n_fine, n_spot, scratch = s.n_large, s.n_zone, s.n_med, s.n_fine, s.n_spot, s.scratch

    tone = g.step(n_large, 0.30, 0.72)
    if cloud != 1.0:
        tone = g.mixf(cloud, 0.5, tone)
    streak = fine_lines = None
    if brush:
        fine_lines = g.noise(g.mapping(s.pos, scale=(0.02, 1.0, 1.0)), 40.0, 2.0, 0.5)
        bands = g.noise(g.mapping(s.pos, scale=(0.012, 1.0, 1.0), loc=(3.0, 1.0, 7.0)), 11.0, 2.0, 0.5)
        streak = g.add(g.mul(fine_lines, 0.6), g.mul(bands, 0.4))
        # a face that looks along the weapon is brushed end on: there the streaks are only grain, so they fade out
        nx, _ny, _nz = g.xyz(g.new('ShaderNodeNewGeometry').outputs['True Normal'])
        along = g.step(g.absf(nx), 0.80, 0.45)
        streak = g.mixf(along, 0.5, streak)
        fine_lines = g.mixf(along, 0.5, fine_lines)
    col_blue = g.mix(tone, blue[0], blue[1])
    col_black = g.mix(tone, black[0], black[1])
    col_white = g.mix(tone, white[0], white[1])
    if case:
        m1 = g.noise(g.mapping(s.pos, loc=(1.7, 6.3, 2.9)), 0.85, 3.0, 0.6, distortion=1.8)
        m2 = g.noise(g.mapping(s.pos, loc=(8.1, 0.4, 5.5)), 1.30, 3.0, 0.6, distortion=1.3)
        hard = g.mix(g.step(m1, 0.40, 0.60), (0.045, 0.080, 0.190), (0.330, 0.235, 0.105))            # blue into straw
        hard = g.mix(g.step(m2, 0.52, 0.70), hard, (0.200, 0.195, 0.190))                              # grey patches
        hard = g.mix(g.mul(g.step(m2, 0.36, 0.24), 0.8), hard, (0.105, 0.050, 0.085))                  # plum between them
        col_white = g.mix(case, col_white, hard)
    patch = g.mul(g.step(n_zone, 0.40, 0.70), g.step(n_med, 0.30, 0.70))
    col_blue = g.mix(g.mul(patch, plum[1]), col_blue, plum[0])
    steel = g.mix(dark, g.mix(bright, col_blue, col_white), col_black)
    rough = g.mixf(dark, g.mixf(bright, g.mixf(tone, gloss[0][0], gloss[0][1]), g.mixf(tone, gloss[1][0], gloss[1][1])),
                   g.mixf(tone, gloss[2][0], gloss[2][1]))
    rough = g.add(rough, g.mul(g.sub(n_fine, 0.5), 0.07))
    d_bump = None
    if has_detail(detail):
        d_tone, d_bump = detail_terms(s, detail)
        if detail_tone:
            steel = tone_by(g, steel, d_tone, detail_tone)
        if detail_rough and d_bump is not None:
            rough = g.sub(rough, g.mul(d_bump, detail_rough))
    broad = vary if vary_broad is None else vary_broad            # the broad low-frequency part of `vary`, apart from its fine part
    if broad:
        drift = g.sub(g.add(g.mul(n_large, 0.6), g.mul(n_zone, 0.4)), 0.5)
        rough = g.add(rough, g.mul(drift, 0.20 * broad))
    if vary:
        rough = g.add(rough, g.mul(mid_rough(s), 0.08 * vary))
    if broad:
        rough = g.sub(rough, g.mul(smudges(s), 0.10 * broad))
        steel = g.mix(g.mul(g.step(n_zone, 0.45, 0.75), 0.18 * broad), steel, thin[0])          # not one tone from end to end
    if brush:
        rough = g.add(rough, g.mul(g.sub(streak, 0.5), 0.28 * brush))
        steel = g.mix(g.mul(g.step(streak, 0.62, 0.36), 0.13 * brush, True), steel, (0.0, 0.0, 0.0))
    # the finish rubbed thin around edges and high spots
    rubbed = g.step(g.add(g.mul(s.zone, 0.95), g.mul(g.sub(n_med, 0.5), 0.55)), 0.30, 0.72)
    if exposure:
        keep = g.mul(exposed(s), g.add(0.05, g.mul(corner(s), 0.35)))
        if handled is not None:
            keep = g.maxf(keep, g.mul(handled, g.inv(hollows(s))))
        rubbed = g.mul(rubbed, g.mixf(exposure, 1.0, keep))
    if handled is not None:
        high = g.step(g.add(g.mul(s.zone, 0.9), g.mul(g.sub(n_med, 0.5), 0.8)), 0.10, 0.45)
        rubbed = g.maxf(rubbed, g.mul(handled, high))
    rubbed = g.mul(rubbed, not_bright)
    steel = g.mix(g.mul(rubbed, thin[1]), steel, thin[0])
    rough = g.mixf(g.mul(rubbed, thin[1]), rough, thin[2])
    # bare metal on the edges themselves
    n_edge = g.noise(g.mapping(s.pos, loc=(11.0, 4.0, 8.0)), 1.1, 3.0, 0.6)
    edge = g.step(g.mul(s.convex, g.add(0.50, g.mul(n_fine, 1.0))), 0.30, 0.66)
    edge = g.mul(edge, g.mixf(g.step(n_edge, 0.38, 0.62), 0.22, 1.0))
    raw = edge
    if edges != 1.0:
        edge = g.mul(edge, edges, True)
    if exposure:
        edge = g.mixf(exposure, edge, edge_wear(s, edge))
    if handled is not None:
        # where it is handled the finish wears through on the edges whatever `edges` says, in rubbed stretches
        edge = g.maxf(edge, g.mul(g.mul(raw, handled), g.mixf(stretches(s), 0.45, 1.0)))
    steel = g.mix(g.mul(edge, g.mixf(bright, 0.92, 0.35)), steel, (0.58, 0.57, 0.55))
    rough = g.mixf(edge, rough, 0.27)
    # scratches
    steel = g.mix(g.mul(scratch, 0.42 * scratches), steel, (0.24, 0.24, 0.25))
    rough = g.add(rough, g.mul(scratch, 0.10 * scratches))
    if vary:
        dense = g.mul(exposed(s), 0.35)
        if handled is not None:
            dense = g.maxf(dense, handled)
        sc = scuffs(s, dense, 'steel' if handled is None else 'steel_handled')
        steel = g.mix(g.mul(sc, 0.30 * vary, True), steel, (0.20, 0.20, 0.21))
        rough = g.add(rough, g.mul(sc, 0.07 * vary))
    # rust freckles, in patches
    patch = g.step(n_zone, 0.48, 0.66)
    where = g.maxf(patch, g.mul(s.cavity, 0.8))
    freckle = g.mul(g.mul(g.step(n_spot, 0.635, 0.70), where), not_bright)
    halo = g.mul(g.step(n_spot, 0.585, 0.66), where)
    if rust != 1.0:
        freckle, halo = g.mul(freckle, rust, True), g.mul(halo, rust, True)
    rust_col = g.mix(n_fine, (0.22, 0.085, 0.030), (0.095, 0.040, 0.020))
    steel = g.mix(g.mul(halo, 0.45), steel, (0.085, 0.055, 0.040))
    steel = g.mix(freckle, steel, rust_col)
    rough = g.mixf(g.maxf(freckle, g.mul(halo, 0.6)), rough, 0.86)
    metal = g.sub(1.0, g.mul(freckle, 0.92), True)
    if coat:
        # paint: metal only where it is worn through
        through = g.maxf(g.maxf(g.mul(rubbed, thin[1]), g.mul(edge, 0.9)), g.mul(scratch, min(1.0, 0.9 * scratches)))
        metal = g.mul(metal, g.sub(1.0, g.mul(g.mul(not_bright, coat), g.inv(through)), True))
    # grime in the cuts
    grime = g.mul(g.step(g.add(g.mul(s.cavity, 1.3), g.mul(g.inv(s.ao), 0.85)), 0.22, 0.85), g.add(0.55, g.mul(n_med, 0.6)), True)
    if dirt != 1.0:
        grime = g.mul(grime, dirt, True)
    if recess:
        grime = g.maxf(grime, g.mul(recesses(s), 0.85 * recess, True))
    steel = g.mix(g.mul(grime, 0.85), steel, (0.030, 0.026, 0.021))
    rough = g.mixf(grime, rough, 0.80)
    metal = g.mul(metal, g.sub(1.0, g.mul(grime, 0.65), True))
    if fill:
        ink = g.mul(g.step(s.cavity, 0.22, 0.50), fill, True)
        if dark != 0.0:
            ink = g.mul(ink, g.inv(dark), True)        # not on the black parts: black in black is a marking nobody can read
        steel = g.mix(ink, steel, (0.012, 0.012, 0.013))
        rough = g.mixf(ink, rough, 0.62)
        metal = g.mul(metal, g.sub(1.0, g.mul(ink, 0.85), True))
    pits = g.mul(g.sub(n_fine, 0.5), 0.10 * (1.0 - min(1.0, brush)))
    height = g.sub(g.add(g.mul(freckle, 0.6), pits), g.mul(scratch, 0.5))
    if brush:
        height = g.add(height, g.mul(g.sub(fine_lines, 0.5), 0.05 * brush))
    if d_bump is not None and detail_relief:
        height = g.add(height, g.mul(d_bump, DETAIL_HEIGHT * detail_relief))
    return Layer(steel, rough, metal, height)


# Named steel finishes: keyword sets for worn_steel (S.worn_steel(s, bright=..., dark=..., **S.STEEL['parkerized'])). 'blued'
# is the reference look (worn_steel's defaults). The others vary it so that not every gun's metal looks the same; each was
# judged in the review light only. A weapon may override any key.
STEEL = {
    'blued': {},
    # a commercial polish and a deep blue-black: glossier and bluer, hardly worn (a well-kept revolver or sporting gun)
    'polished_blue': dict(blue=((0.006, 0.009, 0.019), (0.016, 0.023, 0.046)), gloss=((0.13, 0.21), (0.16, 0.24), (0.30, 0.40)),
                          plum=((0.046, 0.030, 0.030), 0.15), thin=((0.090, 0.092, 0.105), 0.45, 0.24), edges=0.6, scratches=0.6,
                          rust=0.25),
    # manganese phosphate left grey-green and dry: matt, wears to a paler grey before it wears to metal (a military arm)
    'parkerized': dict(blue=((0.046, 0.050, 0.044), (0.082, 0.088, 0.076)), black=((0.022, 0.024, 0.022), (0.042, 0.045, 0.040)),
                       gloss=((0.62, 0.74), (0.22, 0.32), (0.58, 0.68)), plum=((0.046, 0.030, 0.030), 0.0),
                       thin=((0.150, 0.152, 0.140), 0.75, 0.50), edges=0.8, rust=0.55),
    # zinc phosphate, paler and greyer: the dry grey of a wartime stamped gun
    'grey_phosphate': dict(blue=((0.085, 0.088, 0.084), (0.140, 0.144, 0.136)), black=((0.078, 0.081, 0.077), (0.128, 0.132, 0.125)),
                           gloss=((0.60, 0.72), (0.22, 0.32), (0.60, 0.72)), plum=((0.046, 0.030, 0.030), 0.0),
                           thin=((0.230, 0.232, 0.225), 0.70, 0.46), edges=0.8, rust=0.7),
    # the same coating oiled until it is nearly black. It is a coating (coat=1: no metal shows but where it is worn through),
    # which is also what keeps it from being a hole in a lit picture: as a METAL this dark and this matt it mirrored 2 % and
    # had no colour of its own; as a coating it has its own dark grey and the sheen every surface has
    'phosphate_black': dict(blue=((0.020, 0.021, 0.021), (0.040, 0.041, 0.040)), black=((0.014, 0.014, 0.015), (0.030, 0.030, 0.031)),
                            gloss=((0.46, 0.58), (0.22, 0.32), (0.44, 0.54)), plum=((0.046, 0.030, 0.030), 0.0),
                            thin=((0.095, 0.096, 0.092), 0.70, 0.44), edges=0.8, rust=0.45, coat=1.0),
    # a nitrided slide or barrel: satin, a neutral black, hard, so it shows little wear and no rust to speak of
    'nitride': dict(blue=((0.007, 0.007, 0.008), (0.016, 0.016, 0.018)), gloss=((0.36, 0.46), (0.20, 0.30), (0.40, 0.50)),
                    plum=((0.046, 0.030, 0.030), 0.0), thin=((0.060, 0.060, 0.064), 0.40, 0.34), edges=0.55, scratches=0.8, rust=0.15),
    # black hard-anodised aluminium (the black parts) with a phosphated steel barrel (the main finish): the anodising is a
    # grey-black that goes silver, not brown, where it wears, and it does not rust
    'anodized': dict(blue=((0.030, 0.032, 0.031), (0.056, 0.058, 0.055)), black=((0.013, 0.013, 0.015), (0.028, 0.028, 0.031)),
                     gloss=((0.56, 0.68), (0.22, 0.32), (0.46, 0.56)), plum=((0.046, 0.030, 0.030), 0.0),
                     thin=((0.120, 0.122, 0.128), 0.55, 0.40), edges=0.9, rust=0.2),
    # black enamel baked over sheet steel: a soft gloss, chipped to the metal on the folds and corners
    'painted': dict(blue=((0.008, 0.008, 0.009), (0.019, 0.019, 0.020)), black=((0.008, 0.008, 0.009), (0.019, 0.019, 0.020)),
                    gloss=((0.27, 0.38), (0.22, 0.32), (0.27, 0.38)), plum=((0.046, 0.030, 0.030), 0.0),
                    thin=((0.300, 0.295, 0.285), 0.55, 0.34), edges=1.3, scratches=1.3, coat=1.0, rust=0.7),
    # bluing gone brown with age: plum and brown all over, grey where it is handled, rust taking hold
    'patina': dict(blue=((0.026, 0.024, 0.024), (0.056, 0.050, 0.046)), black=((0.018, 0.016, 0.015), (0.038, 0.033, 0.030)),
                   white=((0.20, 0.195, 0.185), (0.31, 0.30, 0.285)), gloss=((0.40, 0.54), (0.30, 0.42), (0.44, 0.56)),
                   plum=((0.085, 0.042, 0.030), 0.80), thin=((0.200, 0.190, 0.178), 0.85, 0.40), edges=1.2, scratches=1.3, rust=1.5),
    # bright nickel plate, a little yellow, worn through to a dull grey on the edges. Its black parts (the `dark` mask) are
    # a polished blue, not the pistol's dull black: beside bright plate a black that is both dark and matt mirrors nothing
    # and reads as a hole once the part is bigger than a lever (PLAYBOOK.md, "Textures and look", item 15)
    'nickel': dict(blue=((0.50, 0.48, 0.43), (0.66, 0.64, 0.58)), black=((0.020, 0.023, 0.030), (0.046, 0.052, 0.066)),
                   gloss=((0.24, 0.34), (0.18, 0.26), (0.20, 0.30)), plum=((0.046, 0.030, 0.030), 0.0),
                   thin=((0.230, 0.215, 0.190), 0.50, 0.34), edges=0.3, scratches=0.7, rust=0.2, cloud=0.4, fill=0.7, dirt=0.4),
    # stainless steel brushed along the gun: bright and even, nothing to wear off, the engraving filled dark
    'stainless': dict(blue=((0.50, 0.50, 0.49), (0.58, 0.58, 0.57)), gloss=((0.27, 0.33), (0.27, 0.33), (0.42, 0.52)),
                      plum=((0.046, 0.030, 0.030), 0.0), thin=((0.58, 0.58, 0.57), 0.0, 0.30), edges=0.5, scratches=0.45, rust=0.04,
                      cloud=0.3, brush=1.0, fill=0.9, dirt=0.3),
}


def wood(s, plank=None, relief=None, tile_cm=14.0, tint=(0.92, 1.0, 1.0), grain_deg=0.0, shift=(0.50, 0.55), side_shift=(0.43, 0.31),
         stretch=1.0, bow=0.0, waver=0.0, stain=None, pores=0.55, blotch=((0.040, 0.015, 0.008), 0.22), sheen=(0.36, 0.28),
         worn=((0.23, 0.125, 0.062), 0.24), grime=0.60, plies=None):
    """Oiled hardwood, worn pale on the high spots, dirty in the cuts.

    The defaults are the reference walnut and must stay what they are. The arguments after `waver` are there so that not
    every gun is stocked in the same wood; WOOD holds named sets of them. They all work on the one painted plank there is:
      tint    multiplies the plank's colour, and may be well over 1: the plank is a dark walnut (mean linear 0.078, 0.028,
              0.016), so a pale wood needs 4 to 8
      stain   (colour, amount): the tinted plank mixed toward one flat colour, which is how a pale wood loses the walnut's
              contrast
      pores   how dark the grain's lines and pores are drawn (0.55)
      blotch  (colour, amount) of the broad darker clouds
      sheen   roughness (untouched, handled): 0.36 is an oil finish, 0.22 a lacquer, 0.65 bare dry wood
      worn    (colour, amount) on the high spots; grime: how dark the cuts go
      plies   (pitch cm, strength, glue colour): a laminated stock. The plies lie flat against the gun's centre plane, so on a
              rounded stock their glue lines come out as contour lines, close together where the surface turns under

    plank / relief: a painted plank's colour and height pictures (texforge: PLAYBOOK.md, "Textures and look"), projected flat through the
    weapon's side with one tile = tile_cm. Without them the grain is procedural.
    grain_deg: 0 runs the grain up the weapon (+Z: a pistol's grip panels; give the grip's rake), 90 runs it along the bore (a
    long gun's stock; a little under 90 makes it fall toward the butt, the way it runs through a wrist).

    Two flat panels (the defaults): each side takes its own piece of the plank (side_shift).
    One piece of wood that goes round the weapon (a stock): side_shift=None, so the two sides meet without a line down the
    comb and the belly, and
      bow     cm of shift across the grain per cm^2 of distance from the centre plane: the growth layers curve, so the top and
              the underside show arcs of grain instead of one layer smeared across the width (0.25)
      stretch one tile covers tile_cm * stretch along the grain: a plank picture repeats every tile, and on 80 cm of stock a
              14 cm tile shows its figure six times (2.5)
      waver   cm by which the layers wander over a hand's length, so a repeat does not line up with the one before (0.8)"""
    g = s.g
    grain_pos = g.mapping(s.pos, rot=(0, -grain_deg, 0))
    wear = g.step(g.add(s.convex, g.mul(s.zone, 0.30)), 0.40, 0.95)
    dirt = g.step(g.add(g.mul(s.cavity, 1.0), g.mul(g.inv(s.ao), 0.75)), 0.40, 1.05)
    if plank is not None and relief is not None:
        sep = g.new('ShaderNodeSeparateXYZ')
        g.set(sep.inputs[0], grain_pos)
        across, along = sep.outputs[0], sep.outputs[2]
        if bow:
            across = g.add(across, g.mul(g.mul(sep.outputs[1], sep.outputs[1]), bow))
        if waver:
            across = g.add(across, g.mul(g.sub(g.noise(g.mapping(s.pos, loc=(2.7, 5.1, 8.3)), 0.07, 2.0, 0.5), 0.5), waver))
        u = g.add(g.mul(across, 1.0 / tile_cm), shift[0])
        v = g.add(g.mul(along, 1.0 / (tile_cm * stretch)), shift[1])
        if side_shift:
            side = g.step(sep.outputs[1], -0.01, 0.01)
            u, v = g.add(u, g.mul(side, side_shift[0])), g.add(v, g.mul(side, side_shift[1]))
        uv = g.new('ShaderNodeCombineXYZ')
        g.set(uv.inputs[0], u)
        g.set(uv.inputs[1], v)
        paint = g.image(plank, uv.outputs[0]).outputs[0]
        bumps = g.image(relief, uv.outputs[0]).outputs[0]
        deep = g.step(bumps, 0.55, 0.10)                               # the dark lines and pores of the grain
        colour = g.mix(1.0, paint, tint)
        colour.node.blend_type = 'MULTIPLY'
        if stain:
            colour = g.mix(stain[1], colour, stain[0])
        colour = g.mix(g.mul(deep, pores), colour, (0.016, 0.007, 0.004))
        colour = g.mix(g.mul(g.step(s.n_large, 0.35, 0.75), blotch[1]), colour, blotch[0])
        rough = g.add(sheen[0], g.mul(deep, 0.16))
        height = g.mul(g.sub(bumps, 0.5), 0.9)
    else:
        warp = g.noise(g.mapping(grain_pos, scale=(0.8, 0.8, 0.12)), 0.8, 3.0, 0.5)
        wave = g.new('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', wave_profile='SIN')
        g.set(wave.inputs['Vector'], g.mapping(grain_pos, scale=(1.0, 0.5, 0.07)))
        wave.inputs['Scale'].default_value = 1.15
        g.set(wave.inputs['Distortion'], g.mul(warp, 14.0))
        wave.inputs['Detail'].default_value = 2.0
        wave.inputs['Detail Scale'].default_value = 1.4
        wave.inputs['Detail Roughness'].default_value = 0.55
        figure = g.step(wave.outputs[1], 0.20, 0.80)
        streak = g.noise(g.mapping(grain_pos, scale=(15.0, 15.0, 0.45)), 1.0, 3.0, 0.6)
        dots = g.step(g.noise(g.mapping(grain_pos, scale=(38.0, 38.0, 1.5)), 1.0, 2.0, 0.5), 0.62, 0.74)
        colour = g.mix(figure, (0.034, 0.014, 0.007), (0.105, 0.046, 0.020))
        colour = g.mix(g.mul(g.step(streak, 0.50, 0.80), 0.28), colour, (0.17, 0.085, 0.036))
        colour = g.mix(g.mul(g.step(s.n_large, 0.35, 0.75), 0.30), colour, (0.060, 0.022, 0.012))
        colour = g.mix(g.mul(dots, 0.45), colour, (0.022, 0.009, 0.005))
        rough = g.add(g.mixf(figure, 0.46, 0.38), g.mul(dots, 0.14))
        height = g.sub(g.mul(g.sub(streak, 0.5), 0.5), g.mul(dots, 0.9))
    if plies:
        pitch, strength, glue = plies
        across_gun = g.new('ShaderNodeSeparateXYZ')
        g.set(across_gun.inputs[0], s.pos)
        # the sheets are never quite square to the gun: they lean a little, and they wander over its length, so that even a
        # flat-sided butt shows a few long lines running along it (without this a flat side lies in one ply and shows none)
        wander = g.mul(g.sub(g.noise(g.mapping(s.pos, scale=(0.22, 1.0, 1.0), loc=(4.4, 1.9, 6.2)), 0.30, 2.0, 0.5), 0.5), 0.34)
        lean = g.add(g.mul(across_gun.outputs[2], 0.055), g.mul(across_gun.outputs[0], 0.006))
        ply = g.mul(g.add(g.add(across_gun.outputs[1], lean), wander), 1.0 / pitch)
        line = g.step(g.math('PINGPONG', ply, 0.5), 0.070, 0.020)              # 1 on a glue line, one every `pitch`
        other = g.step(g.math('PINGPONG', g.mul(ply, 0.5), 0.5), 0.22, 0.28)   # every second ply a shade darker
        colour = g.mix(g.mul(other, 0.14 * strength), colour, glue)
        colour = g.mix(g.mul(line, strength), colour, glue)
    # narrow, soft wear and grime: on checkering a strong edge mask lights every peak and the pattern goes pale and flat
    colour = g.mix(g.mul(wear, worn[1]), colour, worn[0])
    colour = g.mix(g.mul(dirt, grime), colour, (0.020, 0.012, 0.008))
    rough = g.mixf(g.mul(wear, 0.7), rough, sheen[1])
    rough = g.mixf(dirt, rough, 0.68)
    return Layer(colour, rough, 0.0, height)


# Named woods: keyword sets for wood() over the one painted plank (S.wood(s, plank=..., relief=..., **S.WOOD['beech'])).
# 'walnut' is the reference look (wood's defaults). The others vary it so that not every gun's wood looks the same; each
# was judged in the review light only. They change the colour, the contrast,
# the finish and which piece of the plank is used; the figure itself is still the one plank's. A new species with its own
# figure needs a new painted plank (PLAYBOOK, "Textures and look", item 6).
WOOD = {
    'walnut': {},
    # walnut soaked in oil and handling until it is nearly black: an arsenal stock
    'dark_walnut': dict(tint=(0.62, 0.56, 0.50), sheen=(0.30, 0.24), worn=((0.170, 0.090, 0.046), 0.30), shift=(0.21, 0.83)),
    # beech: pale, a little pink, close-grained, an oil finish
    'beech': dict(tint=(4.6, 7.4, 6.4), stain=((0.380, 0.225, 0.110), 0.35), pores=0.28, blotch=((0.200, 0.105, 0.050), 0.16),
                  sheen=(0.42, 0.32), worn=((0.50, 0.34, 0.19), 0.20), grime=0.50, shift=(0.13, 0.37)),
    # birch under an amber shellac: orange, glossy
    'amber_birch': dict(tint=(4.0, 3.6, 1.8), stain=((0.330, 0.110, 0.024), 0.30), pores=0.32, blotch=((0.150, 0.045, 0.012), 0.20),
                        sheen=(0.23, 0.20), worn=((0.46, 0.23, 0.08), 0.22), grime=0.50, shift=(0.71, 0.18)),
    # birch plywood under a red-brown lacquer: the glue lines of its plies show as contour lines
    'red_laminate': dict(tint=(2.0, 1.30, 0.90), stain=((0.150, 0.036, 0.014), 0.30), pores=0.40,
                         blotch=((0.070, 0.015, 0.007), 0.22), sheen=(0.24, 0.21), worn=((0.33, 0.14, 0.060), 0.24),
                         plies=(0.17, 0.60, (0.030, 0.009, 0.005)), shift=(0.33, 0.61)),
    # a dark red tropical hardwood with black streaks, polished
    'rosewood': dict(tint=(1.10, 0.74, 0.70), pores=0.80, blotch=((0.016, 0.005, 0.004), 0.50), sheen=(0.21, 0.18),
                     worn=((0.190, 0.080, 0.045), 0.16), shift=(0.62, 0.29)),
    # a light golden wood under varnish
    'honey': dict(tint=(4.4, 4.9, 2.7), stain=((0.360, 0.165, 0.045), 0.30), pores=0.34, blotch=((0.170, 0.070, 0.018), 0.18),
                  sheen=(0.25, 0.21), worn=((0.52, 0.30, 0.11), 0.20), grime=0.50, shift=(0.87, 0.44)),
    # a stock that has lost its finish to weather: grey-brown, dry, dirty
    'weathered': dict(tint=(1.9, 3.8, 4.9), stain=((0.150, 0.125, 0.100), 0.45), pores=0.75, blotch=((0.060, 0.045, 0.034), 0.30),
                      sheen=(0.66, 0.50), worn=((0.30, 0.26, 0.21), 0.28), grime=0.75, shift=(0.44, 0.09)),
}


def _named(table, what, name):
    if name not in table:
        raise KeyError('no %s called %r: there are %s' % (what, name, ', '.join(sorted(table))))
    return dict(table[name])


def steel(s, finish='blued', bright=None, dark=None, **over):
    """worn_steel in one of the named finishes (STEEL); a keyword given here replaces the finish's own."""
    kw = _named(STEEL, 'steel finish', finish)
    kw.update(over)
    return worn_steel(s, bright=bright, dark=dark, **kw)


def timber(s, kind='walnut', **over):
    """wood in one of the named woods (WOOD); a keyword given here (the plank, the grain's direction, ...) replaces the wood's own."""
    kw = _named(WOOD, 'wood', kind)
    kw.update(over)
    return wood(s, **kw)


def _tarnish(s):
    return s.shared('tarnish', lambda: s.g.step(s.n_med, 0.40, 0.75))


def brass(s):
    """Cartridge brass, tarnishing in patches. Keeps the height of the layer underneath."""
    g, t = s.g, _tarnish(s)
    return Layer(g.mix(g.mul(t, 0.55), (0.80, 0.58, 0.25), (0.42, 0.27, 0.10)), g.mixf(t, 0.26, 0.42), 1.0)


def copper(s):
    """A bullet's copper jacket."""
    g, t = s.g, _tarnish(s)
    return Layer(g.mix(g.mul(t, 0.45), (0.74, 0.40, 0.25), (0.40, 0.20, 0.12)), g.mixf(t, 0.26, 0.42), 1.0)


def polymer(s, colour=(0.018, 0.018, 0.020), worn=(0.060, 0.060, 0.062), matt=(0.62, 0.40), mottle=1.0, grain=1.0, edge=1.0,
            handled=None, exposure=0.0, recess=0.0, vary=0.0, smooth=None, textured=None, fade=0.0, detail=None, detail_tone=0.0,
            detail_relief=1.0, detail_rough=0.0, vary_broad=None):
    """Moulded polymer: matt, a moulded grain, polished shinier and a little paler where it is handled and along its edges,
    clouded in soft patches, dusty in the cuts.
    matt: roughness (untouched, handled). Black rubber (a recoil pad): a darker colour and worn, matt=(0.82, 0.66); at the
    defaults a rubber pad comes out as grey plastic.
    mottle: the clouding. Black polymer shows almost no colour of its own: what the eye gets is the light it mirrors
    dully, so a tone change in the base colour is invisible on it and the clouds have to be in the ROUGHNESS (drier and
    greasier patches a few cm across) and in a thin pale film with specks of dust, which is the one thing that lifts the
    colour. Without them a big flat of polymer (a stock, a shell) is one flat grey with nothing on it. 0 switches it off.
    grain: the depth of the moulded texture in the normal map. edge: the pale, polished line a moulding wears along its
    convex edges, which is what draws a polymer part's shape when the faces are all the same grey. 0 switches each off.
    Wear by use (all off by default; worn_steel takes the first four too):
      handled   a mask (s.handled): there the moulding is polished by hands: smoother, a little darker and glossier, its
                grain flattened, its edges polished, fine scratches denser
      exposure  0..1: the pale edge line and the broad rubbed band only where an edge stands out in the open (or is
                handled), broken into rubbed stretches and chips; at 1 the even line round every edge is gone
      recess    0..1: grooves, pockets, panel lines and the rings round bosses go darker and rougher, so the relief reads;
                the pale dust there gives way to it
      vary      0..1: more roughness variation (a millimetre-scale one, greasy smudges) and sparse fine scratches along
                the weapon, in the roughness and a hair in the colour
      vary_broad 0..1, None = the same as `vary`: how much of vary's broad part (the drift over many cm and the smudges a few
                cm across) is kept; the millimetre variation and the scuffs follow `vary` alone
      smooth    a mask (s.smooth): moulded smooth there: no grain, a satin sheen beside the grained shell
      textured  a mask (s.textured): a moulded stipple there, deeper and drier than the grain
      fade      0..1: faces that look up are a hair paler and greyer (sun), a little drier
    A painted texforge set (off by default; the four arguments as worn_steel's): `detail=S.detail(s, 'poly_mould')` lays a
    real mould texture under the wear, `detail_tone` lightens and darkens the colour by it (the hue stays `colour`),
    `detail_relief` puts its height into the normal map (flattened where handled, none where `smooth`), `detail_rough` makes
    its high spots glossier. Give grain=0 with it, or the procedural pebble lies on top.
    A starting point: judge it in a render before trusting the numbers."""
    g = s.g
    tone = g.step(s.n_large, 0.30, 0.72)
    base = g.mix(g.mul(tone, 0.5), colour, tuple(min(1.0, c * 1.6) for c in colour))
    d_bump = None
    if has_detail(detail):
        d_tone, d_bump = detail_terms(s, detail)
        if detail_tone:
            base = tone_by(g, base, d_tone, detail_tone)
    rub = g.step(g.add(g.mul(s.zone, 0.9), g.mul(g.sub(s.n_med, 0.5), 0.5)), 0.35, 0.80)
    if exposure:
        keep = g.mul(exposed(s), g.add(0.05, g.mul(corner(s), 0.35)))
        if handled is not None:
            keep = g.maxf(keep, g.mul(handled, g.inv(hollows(s))))
        rub = g.mul(rub, g.mixf(exposure, 1.0, keep))
    base = g.mix(g.mul(rub, 0.55), base, worn)
    rough = g.add(g.mixf(rub, matt[0], matt[1]), g.mul(g.sub(s.n_fine, 0.5), 0.10))
    if detail_rough and d_bump is not None:
        rough = g.sub(rough, g.mul(d_bump, detail_rough))
    if mottle:
        cloud = s.shared('poly_cloud', lambda: g.sub(g.add(g.add(g.mul(s.n_large, 0.48), g.mul(s.n_zone, 0.30)), g.mul(s.n_med, 0.22)), 0.5))      # about -0.3 .. +0.3
        rough = g.add(rough, g.mul(cloud, POLY_CLOUD[0] * mottle))
        dusty = tuple(0.35 * c + 0.65 * d for c, d in zip(colour, (0.115, 0.108, 0.098)))
        film = g.mul(g.step(cloud, -0.04, 0.20), POLY_CLOUD[1] * mottle, True)
        base = g.mix(film, base, dusty)
        speck = g.mul(g.step(s.n_spot, 0.70, 0.78), g.mul(g.step(s.n_med, 0.38, 0.62), POLY_CLOUD[2] * mottle), True)
        base = g.mix(speck, base, (0.16, 0.15, 0.135))
        rough = g.mixf(speck, rough, 0.86)
    broad = vary if vary_broad is None else vary_broad            # the broad low-frequency part of `vary`, apart from its fine part
    if broad:
        drift = g.sub(g.add(g.mul(s.n_large, 0.6), g.mul(s.n_zone, 0.4)), 0.5)
        rough = g.add(rough, g.mul(drift, 0.16 * broad))
    if vary:
        rough = g.add(rough, g.mul(mid_rough(s), 0.10 * vary))
    if broad:
        rough = g.sub(rough, g.mul(smudges(s), 0.14 * broad))
    if smooth is not None:
        rough = g.mixf(smooth, rough, g.sub(rough, 0.17))
    if textured is not None:
        rough = g.mixf(textured, rough, g.add(rough, 0.08))
    if edge:
        line = g.mul(g.step(g.mul(s.convex, g.add(0.62, g.mul(s.n_med, 0.76))), 0.26, 0.70), POLY_EDGE * edge, True)
        if exposure:
            line = g.mixf(exposure, line, edge_wear(s, line, handled))
        base = g.mix(line, base, tuple(min(1.0, c * 1.7) for c in worn))
        rough = g.mixf(line, rough, max(0.16, matt[1] - 0.08))
    if handled is not None:
        polish = g.mul(handled, g.mixf(g.step(s.n_med, 0.30, 0.70), 0.65, 1.0))
        base = g.mix(g.mul(polish, 0.75), base, g.times(base, 0.64))
        rough = g.mixf(g.mul(polish, 0.90), rough, max(0.14, matt[1] - 0.20))
    if vary:
        dense = g.mul(exposed(s), 0.35)
        if handled is not None:
            dense = g.maxf(dense, handled)
        sc = scuffs(s, dense, 'polymer' if handled is None else 'polymer_handled')
        base = g.mix(g.mul(sc, 0.22 * vary, True), base, tuple(min(1.0, c * 1.5) for c in worn))
        rough = g.add(rough, g.mul(sc, 0.14 * vary))
    dust = g.mul(g.step(g.add(g.mul(s.cavity, 1.2), g.mul(g.inv(s.ao), 0.8)), 0.30, 0.95), g.add(0.5, g.mul(s.n_med, 0.6)), True)
    if recess:
        dust = g.mul(dust, 1.0 - 0.85 * min(1.0, recess))
    base = g.mix(g.mul(dust, 0.55), base, (0.085, 0.075, 0.062))
    rough = g.mixf(dust, rough, 0.85)
    if recess:
        rec = recesses(s)
        base = g.mix(g.mul(rec, 0.90 * recess, True), base, g.times(base, (0.30, 0.28, 0.24)))
        rough = g.mixf(g.mul(rec, 0.9 * recess, True), rough, 0.86)
    if fade:
        _nx, _ny, nz = g.xyz(g.new('ShaderNodeNewGeometry').outputs['True Normal'])
        lum = 0.3 * worn[0] + 0.6 * worn[1] + 0.1 * worn[2]
        sun = tuple(min(1.0, 0.65 * c * 1.25 + 0.35 * lum * 1.25) for c in worn)
        up = g.step(nz, 0.25, 0.95)
        base = g.mix(g.mul(g.mul(up, g.add(0.6, g.mul(s.n_large, 0.8))), 0.30 * fade, True), base, sun)
        rough = g.add(rough, g.mul(up, 0.04 * fade))
    height = g.sub(g.mul(g.sub(s.n_fine, 0.5), 0.35), g.mul(s.scratch, 0.3))
    if grain:
        pebble = s.shared('poly_grain', lambda: g.noise(g.mapping(s.pos, loc=(1.7, 6.2, 3.3)), 11.0, 2.0, 0.5))
        bumps = g.mul(g.sub(pebble, 0.5), POLY_GRAIN * grain)
        if handled is not None:
            bumps = g.mul(bumps, g.sub(1.0, g.mul(handled, 0.7)))
        if smooth is not None:
            bumps = g.mul(bumps, g.inv(smooth))
        height = g.add(height, bumps)
    if textured is not None:
        stip = s.shared('poly_stipple', lambda: g.step(g.noise(g.mapping(s.pos, loc=(5.5, 0.9, 7.7)), 24.0, 2.0, 0.5), 0.42, 0.62))
        dots = g.mul(g.mul(g.sub(stip, 0.5), POLY_STIPPLE), textured)
        if handled is not None:
            dots = g.mul(dots, g.sub(1.0, g.mul(handled, 0.35)))
        height = g.add(height, dots)
    if d_bump is not None and detail_relief:
        bumps = g.mul(d_bump, DETAIL_HEIGHT * detail_relief)
        if handled is not None:
            bumps = g.mul(bumps, g.sub(1.0, g.mul(handled, 0.7)))
        if smooth is not None:
            bumps = g.mul(bumps, g.inv(smooth))
        height = g.add(height, bumps)
    if vary:
        height = g.sub(height, g.mul(sc, 0.25 * vary))                  # the scuffs are a hair deep too
    return Layer(base, rough, 0.0, height)


POLY_CLOUD = (0.32, 0.16, 0.35)      # the clouding at mottle=1: the roughness swing, the pale film's cover, the dust specks'
POLY_EDGE = 0.72                     # how far the edge line goes to the polished colour at edge=1
POLY_GRAIN = 1.6                     # the moulded grain's height at grain=1, in the bump node's units
POLY_STIPPLE = 2.4                   # the height of a `textured` zone's stipple, in the same units


# ------------------------------------------------------------------------------------------------------------ look-dev
def studio(weapon, strength=1.0, world='studio.exr', rotation=40.0):
    """An image-lit world: Blender's bundled studio light, which every install has."""
    scene = bpy.context.scene
    name = weapon.tag + '_World'
    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    path = os.path.join(bpy.utils.resource_path('LOCAL'), 'datafiles', 'studiolights', 'world', world)
    env.image = bpy.data.images.load(path, check_existing=True)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(rotation))
    nt.links.new(coord.outputs['Generated'], mp.inputs['Vector'])
    nt.links.new(mp.outputs[0], env.inputs['Vector'])
    nt.links.new(env.outputs[0], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    mp.name = 'ROT'
    scene.world = w
    return w


def beauty(out_dir, name, views, objs, res=(1400, 900), cols=1, samples=96, engine='CYCLES', region=None, lens=90.0, margin=1.12,
           key=-50.0, flat_key=-95.0):
    """Rendered review sheet with the real material. The studio turns with the camera so every view is lit alike (key: where the
    light sits relative to the camera, degrees; +55 lights the far side). flat_key is the same for a view straight down an
    axis ('left', 'top', ...): there a flat face mirrors whatever is behind the camera, and at -50 that is a strip light, which
    paints every flat side of the weapon white."""
    from . import view
    scene = bpy.context.scene
    saved = (scene.cycles.use_denoising, scene.cycles.samples)
    rot = scene.world.node_tree.nodes.get('ROT') if scene.world and scene.world.use_nodes else None

    def turn(d):
        if rot is not None:
            head_on = sorted(abs(c) for c in d)[1] < 0.01 * max(abs(c) for c in d)
            rot.inputs['Rotation'].default_value = (0.0, 0.0, math.atan2(d.y, d.x) + math.radians(flat_key if head_on else key))

    try:
        scene.cycles.use_denoising = True
        return view.shots(out_dir, name, views, objs, res=res, cols=cols, engine=engine, persp=True, lens=lens, margin=margin,
                          region=region, samples=samples, on_view=turn, backdrop=view.BACKDROP)
    finally:
        scene.cycles.use_denoising, scene.cycles.samples = saved


# ---------------------------------------------------------------------------------------------------------- game textures
def _tap_bake(obj, mat, key, img, samples=4):
    nt = mat.node_tree
    out, bsdf, em, target = nt.nodes['OUT'], nt.nodes['BSDF'], nt.nodes['TAP_EMIT'], nt.nodes['target']
    target.image = img
    nt.nodes.active = target
    scene = bpy.context.scene
    scene.cycles.samples = samples
    bk = scene.render.bake
    bk.use_selected_to_active = False
    bk.margin = 0
    bk.use_clear = True
    bk.target = 'IMAGE_TEXTURES'
    only([obj])
    if key == 'normal':
        nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
        bk.normal_space = 'TANGENT'
        run(bpy.ops.object.bake, type='NORMAL')
    else:
        nt.links.new(nt.nodes['TAP_' + key].outputs[0], em.inputs['Color'])
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        run(bpy.ops.object.bake, type='EMIT')
        nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
    arr = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    return arr.reshape(img.size[1], img.size[0], 4)


def bake_textures(obj, mat, size, log=print):
    """BaseColor (linear floats), Normal (OpenGL), roughness, metallic, occlusion for the single mesh `obj` carrying `mat`, and
    'cover': 1 on every texel the mesh owns."""
    out = {}
    img = bpy.data.images.get('wf_tex_bake')
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new('wf_tex_bake', size, size, alpha=True, float_buffer=True, is_data=True)
    for key, samples in (('colour', 4), ('rough', 4), ('metal', 4), ('ao', 1), ('cover', 1), ('normal', 16)):
        out[key] = _tap_bake(obj, mat, key, img, samples)[..., :3].copy()
        log('baked', key)
    bpy.data.images.remove(img)
    return out


def srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1.0 / 2.4) - 0.055)


def _save8(arr, name, path, is_colour):
    h, w, c = arr.shape
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :c] = arr
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False, is_data=not is_colour)
    img.pixels.foreach_set(np.clip(rgba, 0.0, 1.0).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return img


def write_game_textures(weapon, tex, cover=None, pad=None, log=print):
    """Pads the islands and writes T_<Name>_BC (sRGB), _N (OpenGL green: the Unreal import flips it), _ORM (R occlusion,
    G roughness, B metallic). Returns {'BC', 'N', 'ORM'}: paths."""
    os.makedirs(weapon.tex_dir, exist_ok=True)
    if cover is None:
        cover = tex['cover'][..., 0] > 0.5
    if pad is None:
        pad = max(4, tex['colour'].shape[0] // 170)
    colour, rough, metal, ao, normal = (tex[k].copy() for k in ('colour', 'rough', 'metal', 'ao', 'normal'))
    orm = np.stack([ao[..., 0], rough[..., 0], metal[..., 0]], axis=2)
    maps.dilate([colour, orm, normal], cover, steps=pad)
    normal[~maps.dilate([], cover, steps=pad)] = (0.5, 0.5, 1.0)
    prefix = weapon.tex_prefix
    paths = {key: os.path.join(weapon.tex_dir, '%s_%s.png' % (prefix, key)) for key in ('BC', 'N', 'ORM')}
    # an 8-bit colour image's buffer holds sRGB-encoded values: encode the linear bake, or the colours come out dark
    _save8(srgb(colour), prefix + '_BC', paths['BC'], True)
    _save8(normal, prefix + '_N', paths['N'], False)
    _save8(orm, prefix + '_ORM', paths['ORM'], False)
    log('wrote', paths)
    return paths


def game_material(weapon):
    """The written BC / N / ORM files on a plain PBR material, as the engine reads them: what the exported meshes carry."""
    name, prefix = weapon.mat_game, weapon.tex_prefix
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')

    def tex(suffix, space):
        node = nt.nodes.new('ShaderNodeTexImage')
        node.image = load_file(prefix + suffix, os.path.join(weapon.tex_dir, prefix + suffix + '.png'), space)
        return node

    colour, normal, orm = tex('_BC', 'sRGB'), tex('_N', 'Non-Color'), tex('_ORM', 'Non-Color')
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(orm.outputs[0], sep.inputs[0])
    nt.links.new(colour.outputs[0], bsdf.inputs['Base Color'])
    nt.links.new(sep.outputs[1], bsdf.inputs['Roughness'])
    nt.links.new(sep.outputs[2], bsdf.inputs['Metallic'])
    nt.links.new(normal.outputs[0], nmap.inputs['Color'])
    nt.links.new(nmap.outputs[0], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
    return mat
