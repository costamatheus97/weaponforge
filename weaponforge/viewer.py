"""A viewer copy of an exported weapon: one .glb with its three textures inside, for looking at it in a browser.

The game files are an FBX with no textures in it and three PNGs beside it, which is what Unreal wants and what an online 3D
viewer cannot show: a viewer reads one file. `weaponforge <id> view` reads the exported static mesh (export/SM_<Name>.fbx) and
the game textures (textures/T_<Name>_BC, _N, _ORM), and writes <asset root>/_gallery/3d/<Name>.glb. It reads the weapon's
files and writes nothing among them; the weapon's .blend is neither opened nor saved. The copy is for looking only: Unreal
never sees it.

glTF packs occlusion, roughness and metallic the way the game's _ORM texture does (R, G, B), and wants the normal map's green
the way the bake writes it, so the textures go in as they are: the game's own PNG files, at their own size, without loss.

They used to go in at half size and as JPEG, to make a file of 2 to 3 MB. That was wrong for what the copy is for. In a browser viewer
it looked blurry and granulated behind decals: JPEG leaves a halo
of blocks round every hard edge, and in a normal or roughness map on polished steel that halo is a patch of grain round the
lettering; the game's textures were clean at the same place (tests/check_viewer_copy.py holds the copy to them). A copy that
is for judging the weapon must not look worse than the weapon. It is now 20 to 35 MB; `--size` still makes a smaller one,
smaller but never lossy.
"""
import os

import bpy

from . import stages

SIZE = None          # the game textures' own size. A number here (or `--size`) scales them down, still as PNG


def folder(weapon):
    """Where the viewer copies go: beside the weapons' folders, never inside one."""
    return os.path.join(os.path.dirname(weapon.asset_root), '_gallery', '3d')


def _occlusion_group():
    """The node group Blender's glTF exporter reads the occlusion map from."""
    group = bpy.data.node_groups.get('glTF Material Output')
    if group is None:
        group = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
        group.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    return group


def _material(name, textures, prefix, size):
    """The material, and the size its textures go into the copy at."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
    sizes = []

    def tex(key, colour):
        node = tree.nodes.new('ShaderNodeTexImage')
        img = bpy.data.images.load(os.path.join(textures, '%s_%s.png' % (prefix, key)))
        img.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
        if size and img.size[0] > size:
            img.scale(size, size)
        sizes.append(img.size[0])          # read here: after the export the image reports its file's size again
        node.image = img
        return node
    colour, normal, orm = tex('BC', True), tex('N', False), tex('ORM', False)
    tree.links.new(colour.outputs['Color'], bsdf.inputs['Base Color'])
    bump = tree.nodes.new('ShaderNodeNormalMap')
    tree.links.new(normal.outputs['Color'], bump.inputs['Color'])
    tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    split = tree.nodes.new('ShaderNodeSeparateColor')
    tree.links.new(orm.outputs['Color'], split.inputs['Color'])
    tree.links.new(split.outputs['Green'], bsdf.inputs['Roughness'])
    tree.links.new(split.outputs['Blue'], bsdf.inputs['Metallic'])
    occlusion = tree.nodes.new('ShaderNodeGroup')
    occlusion.node_tree = _occlusion_group()
    tree.links.new(split.outputs['Red'], occlusion.inputs['Occlusion'])
    return mat, max(sizes)


def load(weapon, size=None):
    """Start from an empty scene and bring in the exported static mesh with its game textures on it: what `view` writes out
    and what `hero` (hero.py) lights. Returns (the mesh object, the size its textures were loaded at)."""
    size = size or SIZE
    source = os.path.join(weapon.export_dir, 'SM_%s.fbx' % weapon.name)
    wanted = [source] + [os.path.join(weapon.tex_dir, 'T_%s_%s.png' % (weapon.name, key)) for key in ('BC', 'N', 'ORM')]
    missing = [p for p in wanted if not os.path.isfile(p)]
    if missing:
        raise SystemExit('view: not exported yet, no %s (run: weaponforge %s export)' % (', '.join(missing), weapon.id))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=source)
    mesh = bpy.data.objects.get('SM_' + weapon.name)
    if mesh is None or mesh.type != 'MESH':
        raise SystemExit('view: no mesh SM_%s in %s; it holds %s' % (weapon.name, source, sorted(o.name for o in bpy.data.objects)))
    world = mesh.matrix_world.copy()
    mesh.parent = None
    mesh.matrix_world = world
    for other in [o for o in bpy.data.objects if o is not mesh]:          # the collision boxes and the LODs
        bpy.data.objects.remove(other, do_unlink=True)
    mesh.data.materials.clear()
    material, pixels = _material('M_' + weapon.name, weapon.tex_dir, 'T_' + weapon.name, size)
    mesh.data.materials.append(material)
    mesh.name = weapon.name
    return mesh, pixels


def make(weapon, size=None):
    """Write the viewer copy and return its path. Starts from an empty scene, so it is run on its own (cli.py)."""
    mesh, pixels = load(weapon, size)
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    out = os.path.join(folder(weapon), weapon.name + '.glb')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # AUTO keeps a PNG a PNG: no JPEG, whose blocks show as grain round engraved lettering on polished steel
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True, export_apply=True, export_image_format='AUTO')
    dims = mesh.dimensions
    stages.log('view: %s, %.1f MB, %d triangles, %.1f x %.1f x %.1f cm, textures at %d px'
               % (out, os.path.getsize(out) / 1.0e6, sum(len(p.vertices) - 2 for p in mesh.data.polygons),
                  dims.x * 100.0, dims.y * 100.0, dims.z * 100.0, pixels))
    return out
