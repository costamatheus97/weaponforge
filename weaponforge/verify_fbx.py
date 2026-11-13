"""weaponforge: read the exported FBX files back into an empty scene and compare what an importer finds with the spec.

    problems = verify_fbx.run(spec_path, export_dir)

A miss is: a file that is missing; a mesh that comes in scaled, without exactly one UV map, without exactly one material slot
(the spec's, when it names one) or without the authored normals; a triangle count that differs; bounds off by more than 0.01 cm
(a LOD: 0.5 cm, since the decimator moves vertices); a bone or socket joint that is missing, misplaced, on the wrong parent or
turned (a socket joint must carry the spec's rotation); a socket joint in a LOD file; a vertex not on exactly one bone; a static
file whose LodGroup children are not in LOD order.

It empties the scene for every file, so it runs last and in its own Blender (stage "verify"). It reads any weaponforge spec. It
cannot tell what Unreal's importer will make of a file: integrations/unreal/weapon_check.py reads that back.
"""
import json
import os

import bpy
from mathutils import Vector

from .rig import ue_rotation
from .weapon import SOCKET_PREFIX

TOL = 0.01          # cm
LOD_TOL = 0.5       # cm: a LOD's bounds against the weapon's (decimation moves vertices; an offset or a lost unit is far more)
TURN_TOL = 1.0e-3   # largest difference between two rotation matrices' entries


def _load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = 0.01
    bpy.ops.import_scene.fbx(filepath=path, use_custom_normals=True, automatic_bone_orientation=False,
                             primary_bone_axis='Y', secondary_bone_axis='X')
    bpy.context.view_layer.update()
    return [o for o in bpy.data.objects if o.type == 'MESH'], [o for o in bpy.data.objects if o.type == 'ARMATURE']


def _bounds(obj):
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def _from_ue(v):
    return Vector((v[0], -v[1], v[2]))


def _box(block):
    lo, hi = _from_ue(block['min']), _from_ue(block['max'])
    return [min(a, b) for a, b in zip(lo, hi)], [max(a, b) for a, b in zip(lo, hi)]


def _differs(lo, hi, want, tol=TOL):
    w_lo, w_hi = want
    return max(max(abs(lo[i] - w_lo[i]), abs(hi[i] - w_hi[i])) for i in range(3)) > tol


def lod_groups(path):
    """{group name: its children's names in file order} for every FBX LodGroup node: the order Unreal reads them as LOD0, LOD1, ..."""
    from io_scene_fbx import parse_fbx
    root, _version = parse_fbx.parse(path)
    objects = next(e for e in root.elems if e.id == b'Objects')
    links = [e.props for e in next(e for e in root.elems if e.id == b'Connections').elems if e.props[0] == b'OO']
    models = {e.props[0]: e.props[1].split(b'\x00')[0].decode() for e in objects.elems if e.id == b'Model'}
    attrs = {e.props[0] for e in objects.elems if e.id == b'NodeAttribute' and e.props[2] == b'LodGroup'}
    groups = [parent for _kind, child, parent in links if child in attrs]
    return {models[g]: [models[child] for _kind, child, parent in links if parent == g and child in models] for g in groups}


def layout(spec):
    """(skeletal mesh name, [static mesh names], the main static's name) from a spec, new or old."""
    unreal = spec.get('unreal')
    if unreal:
        return unreal['skeletal']['name'], [s['name'] for s in unreal['statics']], unreal['statics'][0]['name']
    skeletal = next(k for k in spec['meshes'] if k.startswith('SKM_'))
    statics = [k for k in spec['meshes'] if k.startswith('SM_')]
    return skeletal, statics, 'SM_' + spec['name']


def run(spec_path, export_dir=None, log=print):
    problems = []

    def say(*a):
        log('[verify]', *a)

    def miss(text):
        problems.append(text)
        say('MISS', text)

    def mesh_report(obj):
        lo, hi = _bounds(obj)
        tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
        say('  mesh %s: %d triangles, x %.3f..%.3f, y %.3f..%.3f, z %.3f..%.3f, scale %s, uv %s, materials %s, custom normals %s'
            % (obj.name, tris, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2], tuple(round(s, 4) for s in obj.matrix_world.to_scale()),
               [u.name for u in obj.data.uv_layers], [m.name for m in obj.data.materials if m], obj.data.has_custom_normals))
        if max(abs(s - 1.0) for s in obj.matrix_world.to_scale()) > 1.0e-4:
            miss('%s: the mesh comes in scaled %s (the export must write centimetres at scale 1)' % (obj.name, tuple(obj.matrix_world.to_scale())))
        if len(obj.data.uv_layers) != 1:
            miss('%s: %d UV maps (%s), want exactly one' % (obj.name, len(obj.data.uv_layers), [u.name for u in obj.data.uv_layers]))
        slots = [m.name if m else None for m in obj.data.materials]
        if len(slots) != 1 or (want_slot and slots[0] != want_slot):
            miss('%s: material slots %s, want the single slot %s' % (obj.name, slots, want_slot or '(any one)'))
        if not obj.data.has_custom_normals:
            miss('%s: no custom normals (the weighted normals the bake assumed were not written)' % obj.name)
        return tris, lo, hi

    with open(spec_path, 'r', encoding='utf-8') as fh:
        spec = json.load(fh)
    export_dir = export_dir or spec['source']['export_dir']
    skeletal_name, static_names, main_static = layout(spec)
    want_box = _box(spec['bounds_ue_cm'])
    want_slot = (spec.get('unreal') or {}).get('material_slot')

    # ---- the skinned mesh and its LODs
    files = [(spec['meshes'][skeletal_name]['fbx'], spec['meshes'][skeletal_name]['triangles'], True)]
    files += [(l['fbx'], l['triangles'], False) for l in spec.get('lods', [])]
    for name, want_tris, with_sockets in files:
        say(name)
        path = os.path.join(export_dir, name)
        if not os.path.isfile(path):
            miss('%s is missing' % path)
            continue
        meshes, arms = _load(path)
        if len(meshes) != 1 or len(arms) != 1:
            miss('%s: %d meshes and %d armatures (want 1 and 1)' % (name, len(meshes), len(arms)))
            continue
        mesh, arm = meshes[0], arms[0]
        tris, lo, hi = mesh_report(mesh)
        if tris != want_tris:
            miss('%s: %d triangles, spec %d' % (name, tris, want_tris))
        if _differs(lo, hi, want_box, TOL if with_sockets else LOD_TOL):
            miss('%s: bounds differ from the spec by more than %s cm' % (name, TOL if with_sockets else LOD_TOL))
        if arm.name != 'Armature':
            miss('%s: the armature object is named %s (Unreal drops the node only when it is "Armature")' % (name, arm.name))
        say('  armature %s scale %s, %d bones' % (arm.name, tuple(round(s, 4) for s in arm.matrix_world.to_scale()), len(arm.data.bones)))
        found = {b.name: b for b in arm.data.bones}
        for b in spec['bones']:
            bone = found.get(b['name'])
            if bone is None:
                miss('%s: bone %s missing' % (name, b['name']))
                continue
            head = arm.matrix_world @ bone.head_local
            axes = arm.matrix_world.to_3x3() @ bone.matrix_local.to_3x3()
            ident = max(abs(axes[i][j] - (1.0 if i == j else 0.0)) for i in range(3) for j in range(3))
            parent = bone.parent.name if bone.parent else None
            if (head - _from_ue(b['position_ue'])).length > TOL or ident > 1.0e-4 or parent != b['parent']:
                miss('%s: bone %s at %s, parent %s, axes off by %.4f' % (name, b['name'], tuple(round(x, 3) for x in head), parent, ident))
        sockets = [n for n in found if n.startswith(SOCKET_PREFIX)]
        if with_sockets:
            for s in spec['sockets']:
                bone = found.get(SOCKET_PREFIX + s['name'])
                if bone is None:
                    miss('%s: socket joint %s%s missing' % (name, SOCKET_PREFIX, s['name']))
                    continue
                head = arm.matrix_world @ bone.head_local
                parent = bone.parent.name if bone.parent else None
                if (head - _from_ue(s['position_ue'])).length > TOL or bone.children or parent != s['bone']:
                    miss('%s: socket joint %s at %s under %s' % (name, bone.name, tuple(round(x, 3) for x in head), parent))
                axes = arm.matrix_world.to_3x3() @ bone.matrix_local.to_3x3()
                want_axes = ue_rotation(*s['rotation_ue_pitch_yaw_roll'])
                turn = max(abs(axes[i][j] - want_axes[i][j]) for i in range(3) for j in range(3))
                if turn > TURN_TOL:
                    miss('%s: socket joint %s is turned: its axes differ from the spec\'s rotation %s by %.4f'
                         % (name, bone.name, s['rotation_ue_pitch_yaw_roll'], turn))
            say('  socket joints: %s' % ', '.join(sorted(sockets)))
        elif sockets:
            miss('%s: a LOD file must not carry socket joints, found %s' % (name, sockets))
        extra = sorted(set(found) - {b['name'] for b in spec['bones']} - set(sockets))
        if extra:
            miss('%s: unexpected bones %s' % (name, extra))
        groups = sorted(g.name for g in mesh.vertex_groups)
        loose = sum(1 for v in mesh.data.vertices if len(v.groups) != 1 or abs(v.groups[0].weight - 1.0) > 1.0e-4)
        say('  skin: %d groups (%s), vertices not on exactly one bone: %d' % (len(groups), ', '.join(groups), loose))
        if loose or not set(groups) <= set(found):
            miss('%s: skinning is not one bone per vertex' % name)

    # ---- the static copies
    for key in static_names:
        name = spec['meshes'][key]['fbx']
        want_tris = spec['meshes'][key].get('lods_in_fbx') or [spec['meshes'][key]['triangles']]
        say(name)
        path = os.path.join(export_dir, name)
        if not os.path.isfile(path):
            miss('%s is missing' % path)
            continue
        meshes, arms = _load(path)
        if len(meshes) != len(want_tris) or arms:
            miss('%s: %d meshes and %d armatures (want %d and 0)' % (name, len(meshes), len(arms), len(want_tris)))
            continue
        found = {}
        for mesh in sorted(meshes, key=lambda o: o.name):
            found[mesh.name] = mesh_report(mesh)
        base = found.get(key)
        if base is None:
            miss('%s: no mesh named %s (found %s)' % (name, key, sorted(found)))
            continue
        if key == main_static and _differs(base[1], base[2], want_box):
            miss('%s: bounds differ from the spec' % name)
        if len(want_tris) > 1:
            groups = lod_groups(path)
            say('  LodGroup nodes: %s' % groups)
            order = next(iter(groups.values())) if len(groups) == 1 else []
            tris = [found[n][0] for n in order if n in found]
            if tris != want_tris:
                miss('%s: the LodGroup\'s children in file order have %s triangles, spec %s' % (name, tris, want_tris))
            if key == main_static:
                for n in order[1:]:
                    if n in found and _differs(found[n][1], found[n][2], want_box, LOD_TOL):
                        miss('%s: the bounds of %s differ from the spec by more than %s cm' % (name, n, LOD_TOL))
        elif base[0] != want_tris[0]:
            miss('%s: %d triangles, spec %d' % (name, base[0], want_tris[0]))
        own = spec['meshes'][key].get('bounds_ue_cm')
        if own and _differs(base[1], base[2], _box(own)):
            miss('%s: bounds differ from the spec' % name)

    say('RESULT: %s' % ('all files match the spec' if not problems else '%d problems' % len(problems)))
    return problems
