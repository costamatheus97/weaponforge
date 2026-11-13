"""weaponforge: the rig, the game meshes and the exports.

Bones sit on the parts' pivots with identity rest axes (in Unreal: X forward, Y right, Z up), every part is skinned rigidly to one
bone, and the mesh is bound in the game's reference pose (a hammer that the game expects cocked is modelled cocked).

Blender here is +X muzzle, +Y the weapon's LEFT, +Z up; Unreal reads (x, -y, z). Everything marked `ue` is in Unreal's frame.
The export settings are the ones Unreal 5.8 reads without any fix-up: see PLAYBOOK.md, "Rig and export".
"""
import json
import math
import os

import bpy
from mathutils import Matrix, Vector

from . import collision as C
from . import kit as K
from . import mesh as M
from .ops import only, run
from .weapon import SOCKET_PREFIX, UNREAL_BASE, UNREAL_MASTER, UNREAL_SCALAR_PARAMS, UNREAL_TEXTURES

ARMATURE_NAME = 'Armature'      # Unreal drops the armature's own node only when it is called exactly this


def ue(v):
    return [round(v[0], 4) + 0.0, round(-v[1], 4) + 0.0, round(v[2], 4) + 0.0]      # + 0.0: no "-0.0" in the spec


def ue_bounds(lo, hi):
    return {'min': ue(Vector((lo.x, hi.y, lo.z))), 'max': ue(Vector((hi.x, lo.y, hi.z)))}


def ue_rotation(pitch, yaw, roll):
    """Unreal's axes for a rotator (degrees), carried into Blender's frame (whose +Y is Unreal's -Y). Columns: X, Y, Z."""
    p, y, r = (math.radians(a) for a in (pitch, yaw, roll))
    cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(y), math.sin(y), math.cos(r), math.sin(r)
    m = Matrix(((cp * cy, sr * sp * cy - cr * sy, -(cr * sp * cy + sr * sy)),
                (cp * sy, sr * sp * sy + cr * cy, cy * sr - cr * sp * sy),
                (sp, -sr * cp, cr * cp)))
    flip = Matrix(((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)))
    return flip @ m @ flip


# ---------------------------------------------------------------------------------------------------------------- pivots
def set_pivot(obj, pos):
    """Move the object's origin to pos without moving its geometry."""
    pos = Vector(pos)
    delta = pos - obj.matrix_world.translation
    if delta.length < 1.0e-9:
        return
    obj.data.transform(Matrix.Translation(-(obj.matrix_world.inverted().to_3x3() @ delta)))
    obj.matrix_world.translation = pos
    obj.data.update()


def pivots(weapon, lp_objs):
    """Every game part's origin onto its bone."""
    pos = weapon.bone_pos
    for obj in lp_objs:
        bone = obj.get('bone')
        if bone not in pos:
            raise KeyError('%s is tagged for bone %r, which the weapon does not define' % (obj.name, bone))
        set_pivot(obj, pos[bone])
    bpy.context.view_layer.update()


# -------------------------------------------------------------------------------------------------------------- game mesh
def _join_copies(name, objs, coll, groups=True):
    """One mesh object from copies of objs (their custom normals and UVs kept), origin at the world origin."""
    dups = []
    for obj in objs:
        dup = obj.copy()
        dup.data = obj.data.copy()
        coll.objects.link(dup)
        if groups:
            dup.vertex_groups.clear()
            vg = dup.vertex_groups.new(name=obj['bone'])
            vg.add(list(range(len(dup.data.vertices))), 1.0, 'REPLACE')
        dups.append(dup)
    only(dups, active=dups[0])
    bpy.context.view_layer.update()
    if len(dups) > 1:
        run(bpy.ops.object.join)
    out = bpy.context.view_layer.objects.active
    out.name = name
    out.data.name = name
    set_pivot(out, (0.0, 0.0, 0.0))
    for key in list(out.keys()):
        del out[key]
    return out


def armature(weapon, coll):
    """The weapon's armature in coll (build() empties coll first, so the weapon's own old one is gone by now)."""
    other = bpy.data.objects.get(ARMATURE_NAME)
    if other is not None:
        # never deleted: in a live session it is someone's rig. The export needs this exact name, so it has to make way.
        raise RuntimeError('this file already has an object named "%s" outside %s (in %s). Unreal needs the weapon\'s armature to '
                           'have exactly that name: rename the other one, or rig the weapon in its own file.'
                           % (ARMATURE_NAME, coll.name, ', '.join(c.name for c in other.users_collection) or 'no collection'))
    arm = bpy.data.armatures.new('SK_' + weapon.name)
    obj = bpy.data.objects.new(ARMATURE_NAME, arm)
    coll.objects.link(obj)
    only([obj])
    run(bpy.ops.object.mode_set, mode='EDIT')
    try:
        made = {}
        for bone_name, parent, pos in weapon.bones:      # parents first, every name once: Weapon.validate
            b = arm.edit_bones.new(bone_name)
            b.head = Vector(pos)
            b.tail = Vector(pos) + Vector((0.0, 1.0, 0.0))      # along +Y with no roll: an identity rest matrix
            b.roll = 0.0
            b.use_deform = True
            if parent:
                b.parent = made[parent]
                b.use_connect = False
            made[bone_name] = b
        # the sockets ride along as leaf joints (no skin on them); Unreal's importer turns each into a socket on its parent bone
        for sock_name, parent, pos, rot, _means in weapon.sockets:
            b = arm.edit_bones.new(SOCKET_PREFIX + sock_name)
            b.head = Vector(pos)
            b.tail = Vector(pos) + Vector((0.0, 0.5, 0.0))
            m = ue_rotation(*rot).to_4x4()
            m.translation = Vector(pos)
            b.matrix = m
            b.use_deform = False
            b.parent = made[parent]
            b.use_connect = False
    finally:
        run(bpy.ops.object.mode_set, mode='OBJECT')
    obj.show_in_front = True
    arm.display_type = 'STICK'
    return obj


def lod_mesh(skm, ratio, name, coll):
    """A lighter copy of the skinned mesh on the same bones and the same UV sheet. Each part stays whole and on its bone."""
    dup = skm.copy()
    dup.data = skm.data.copy()
    dup.name = name
    dup.data.name = name
    coll.objects.link(dup)
    for mod in list(dup.modifiers):
        dup.modifiers.remove(mod)
    dec = dup.modifiers.new('Decimate', 'DECIMATE')
    dec.decimate_type = 'COLLAPSE'
    dec.ratio = ratio
    dec.use_collapse_triangulate = True
    only([dup])
    run(bpy.ops.object.modifier_apply, modifier=dec.name)
    M.clean_micro(dup, caps=True)      # the decimator can leave a triangle Unreal would drop as degenerate; then hard edges and normals
    arm_mod = dup.modifiers.new('Armature', 'ARMATURE')
    arm_mod.object = skm.parent
    return dup


def static_lod(lod, name, coll):
    """A LOD of the world copy: the skinned LOD's surface without its bones."""
    dup = lod.copy()
    dup.data = lod.data.copy()
    dup.name = name
    dup.data.name = name
    coll.objects.link(dup)
    for mod in list(dup.modifiers):
        dup.modifiers.remove(mod)
    dup.vertex_groups.clear()
    dup.parent = None
    dup.matrix_world = Matrix.Identity(4)
    return dup


def build(weapon, lp_objs, mat):
    """The exported objects, in collection <TAG>_GAME: SKM_<Name> (skinned, on its armature), SM_<Name> (the world copy), one
    SM_<Name>_<suffix> per prop, and the LODs of the first two. Returns the same dict as find()."""
    coll = K.collection(weapon.coll('GAME'))
    K.wipe(coll)
    for data in [a for a in bpy.data.armatures if a.users == 0 and a.name.split('.')[0] == 'SK_' + weapon.name]:
        bpy.data.armatures.remove(data)                    # the wiped armature's bones
    for obj in lp_objs:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    skm = _join_copies(weapon.skm, lp_objs, coll)
    arm = armature(weapon, coll)
    mod = skm.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    skm.parent = arm
    static = _join_copies(weapon.static, lp_objs, coll, groups=False)
    props = {}
    for prop in weapon.props:
        parts = [o for o in lp_objs if o['bone'] in prop.bones]
        if not parts:
            raise ValueError('prop %s: no part is on %s' % (prop.suffix, ', '.join(prop.bones)))
        obj = _join_copies(weapon.prop_name(prop), parts, coll, groups=False)
        if prop.matrix is not None:
            obj.data.transform(Matrix(prop.matrix).inverted())      # into the prop's own frame
            obj.data.update()
        props[prop.suffix] = obj
    game = {'skm': skm, 'armature': arm, 'static': static, 'props': props, 'lods': [], 'static_lods': []}
    for index, ratio in weapon.lods:
        game['lods'].append(lod_mesh(skm, ratio, weapon.lod_name(index), coll))
    game['static_lods'] = [static_lod(o, weapon.lod_name(index, static=True), coll) for (index, _), o in zip(weapon.lods, game['lods'])]
    bpy.context.view_layer.update()
    return game


def find(weapon):
    """The game objects of an already rigged file, or None when the stage "rig" has not run."""
    coll = bpy.data.collections.get(weapon.coll('GAME'))
    if coll is None:
        return None

    def get(name, kind='MESH'):
        obj = coll.objects.get(name)                       # only what the stage "rig" put in the weapon's own collection
        return obj if obj is not None and obj.type == kind else None

    skm, static, arm = get(weapon.skm), get(weapon.static), get(ARMATURE_NAME, 'ARMATURE')
    if skm is None or static is None or arm is None:
        return None
    game = {'skm': skm, 'armature': arm, 'static': static, 'props': {}, 'lods': [], 'static_lods': []}
    for prop in weapon.props:
        obj = get(weapon.prop_name(prop))
        if obj is None:
            return None
        game['props'][prop.suffix] = obj
    for index, _ratio in weapon.lods:
        lod, slod = get(weapon.lod_name(index)), get(weapon.lod_name(index, static=True))
        if lod is None or slod is None:
            return None
        game['lods'].append(lod)
        game['static_lods'].append(slod)
    return game


def exported(game):
    """Every mesh that goes into an FBX file."""
    return [game['skm'], game['static']] + list(game['props'].values()) + list(game['lods']) + list(game['static_lods'])


# ------------------------------------------------------------------------------------------------------------------ pose
def pose(arm, moves=None):
    """Put the armature in a pose, for looking at the rig: {bone: {'loc': (x, y, z) cm, 'rot': (x, y, z) degrees, 'scale': s}}.
    Every rest axis is the weapon's own, so a move is the same vector in Blender (whose +Y is the weapon's left). None: rest."""
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    for name, move in (moves or {}).items():
        pb = arm.pose.bones[name]
        if 'loc' in move:
            pb.location = move['loc']
        if 'rot' in move:
            pb.rotation_euler = [math.radians(a) for a in move['rot']]
        if 'scale' in move:
            s = move['scale']
            pb.scale = (s, s, s)
    bpy.context.view_layer.update()


# ---------------------------------------------------------------------------------------------------------------- export
def export_fbx(path, objs, deform_only=False, object_types=('ARMATURE', 'MESH')):
    """deform_only leaves the socket joints out (a LOD file must carry exactly the base mesh's bones)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    only(objs, active=objs[0])
    run(bpy.ops.export_scene.fbx, filepath=path, use_selection=True, object_types=set(object_types), apply_unit_scale=True,
        global_scale=1.0, apply_scale_options='FBX_SCALE_NONE', axis_forward='-Y', axis_up='Z', add_leaf_bones=False,
        primary_bone_axis='Y', secondary_bone_axis='X', use_armature_deform_only=deform_only, bake_anim=False, mesh_smooth_type='EDGE',
        use_tspace=False, use_mesh_modifiers=True, use_custom_props=False)
    return path


def export_static_lods(path, static, lods):
    """The world copy and its LODs in one file, under an empty the exporter writes as an FBX LodGroup (its 'fbx_type' property):
    Unreal takes the group's children in file order as LOD0, LOD1, ... The exporter writes objects sorted by name, so the names
    must sort so (SM_X < SM_X_LOD1 < SM_X_LOD2)."""
    meshes = [static] + list(lods)
    names = [o.name for o in meshes]
    if names != sorted(names):
        raise ValueError('LOD names must sort in LOD order: %s' % names)
    group = bpy.data.objects.new(static.name + '_LodGroup', None)
    static.users_collection[0].objects.link(group)
    group['fbx_type'] = 'LodGroup'
    try:
        for o in meshes:
            o.parent = group
        bpy.context.view_layer.update()
        export_fbx(path, [group] + meshes, object_types=('EMPTY', 'MESH'))
    finally:
        for o in meshes:
            o.parent = None
        bpy.data.objects.remove(group)
        bpy.context.view_layer.update()
    return path


def export_all(weapon, game):
    pose(game['armature'])                 # always the bind pose
    folder = weapon.export_dir
    out = {'skeletal': export_fbx(os.path.join(folder, weapon.skm + '.fbx'), [game['armature'], game['skm']])}
    if game['static_lods']:
        out['static'] = export_static_lods(os.path.join(folder, weapon.static + '.fbx'), game['static'], game['static_lods'])
    else:
        out['static'] = export_fbx(os.path.join(folder, weapon.static + '.fbx'), [game['static']])
    for obj in game['props'].values():
        out[obj.name] = export_fbx(os.path.join(folder, obj.name + '.fbx'), [obj])
    for obj in game['lods']:
        out[obj.name] = export_fbx(os.path.join(folder, obj.name + '.fbx'), [game['armature'], obj], deform_only=True)
    return out


# ------------------------------------------------------------------------------------------------------------------ spec
def _merge(base, extra):
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def spec(weapon, game, uv_stats=None, textures=None, checks=None, status=None):
    """Everything the game side needs to know about the weapon, as data: <id>.json (Weapon.spec_path). The Unreal import and check
    scripts are driven by it, and so is anything that poses hands on the weapon."""
    lo, hi = K.bounds([game['skm']])
    bone_pos = weapon.bone_pos
    static_lods = [K.tri_count(o) for o in [game['static']] + list(game['static_lods'])]
    boxes = weapon.collision(game['static'], C)
    meshes = {
        weapon.skm: {'fbx': weapon.skm + '.fbx', 'triangles': K.tri_count(game['skm']), 'use': 'first person, skinned'},
        weapon.static: {'fbx': weapon.static + '.fbx', 'triangles': K.tri_count(game['static']), 'use': 'world copy (pickup, holster)',
                        'lods_in_fbx': static_lods, 'collision': C.report(boxes, C.points(game['static']))},
    }
    statics = [{'name': weapon.static, 'fbx': weapon.static + '.fbx', 'lods_in_fbx': static_lods, 'collision': True, 'bounds': 'weapon'}]
    for prop in weapon.props:
        obj = game['props'][prop.suffix]
        p_lo, p_hi = K.bounds([obj])
        meshes[obj.name] = {'fbx': obj.name + '.fbx', 'triangles': K.tri_count(obj), 'use': prop.use, 'bounds_ue_cm': ue_bounds(p_lo, p_hi)}
        statics.append({'name': obj.name, 'fbx': obj.name + '.fbx', 'lods_in_fbx': [K.tri_count(obj)], 'collision': False, 'bounds': 'own'})
    d = {
        'name': weapon.name,
        'id': weapon.id,
        'status': status or 'built (mesh, UVs, bakes, textures, rig, FBX); not yet imported into Unreal',
        'design': weapon.design,
        'frame': weapon.frame_note,
        'bounds_ue_cm': ue_bounds(lo, hi),
        'bones': [{'name': n, 'parent': p, 'position_ue': ue(pos), 'axes': 'identity (X forward, Y right, Z up)'} for n, p, pos in weapon.bones],
        'motion': dict(weapon.motion),
        'sockets': [{'name': n, 'bone': b, 'position_ue': ue(pos), 'relative_ue': ue(Vector(pos) - bone_pos[b]),
                     'rotation_ue_pitch_yaw_roll': list(rot), 'means': means} for n, b, pos, rot, means in weapon.sockets],
        'sockets_in_fbx': 'each socket is a leaf joint named %s<name> under its bone in %s.fbx; Unreal\'s importer (Interchange, '
                          'Import Sockets on) makes the mesh socket from it and adds no bone' % (SOCKET_PREFIX, weapon.skm),
        'meshes': meshes,
        'lods': [{'lod': index, 'fbx': o.name + '.fbx', 'triangles': K.tri_count(o),
                  'share_of_lod0': round(K.tri_count(o) / max(1, K.tri_count(game['skm'])), 3)}
                 for (index, _ratio), o in zip(weapon.lods, game['lods'])],
        'budget': dict([('lod0_triangles', list(weapon.budget))] + [('lod%d_fraction' % i, r) for i, r in weapon.lods]
                       + [('materials', 1), ('texture_set', '%d BC / N / ORM' % weapon.texture_size)]),
        'asset_dir': weapon.unreal_dir,
        'source': {'blend': weapon.blend, 'export_dir': weapon.export_dir, 'definition': 'weapons/%s/' % weapon.id,
                   'tool': 'weaponforge', 'import_script': 'integrations/unreal/weapon_import.py'},
        'unreal': {
            'asset_dir': weapon.unreal_dir,
            'content': UNREAL_BASE,              # the Unreal adapter refuses a spec made for another content folder
            'master_material': UNREAL_MASTER,
            'material_instance': 'MI_' + weapon.name,
            'material_slot': weapon.mat_game,
            'texture_dir': weapon.tex_dir,
            'textures': [{'asset': '%s_%s' % (weapon.tex_prefix, suffix), 'file': '%s_%s.png' % (weapon.tex_prefix, suffix),
                          'param': param, 'kind': kind} for suffix, param, kind in UNREAL_TEXTURES],
            'scalar_params': dict(UNREAL_SCALAR_PARAMS),
            'export_dir': weapon.export_dir,
            'skeletal': {'name': weapon.skm, 'fbx': weapon.skm + '.fbx', 'lods': [o.name + '.fbx' for o in game['lods']]},
            'statics': statics,
        },
    }
    if uv_stats:
        d['uv'] = {k: (float(v) if not isinstance(v, list) else v) for k, v in uv_stats.items()}
    if textures:
        d['textures'] = textures
    _merge(d, weapon.spec_extra(game) or {})
    if checks:
        d['checks'] = checks
    return d


def write_spec(d, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(d, fh, indent=2)
        fh.write('\n')
    return path
