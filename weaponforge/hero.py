"""A presentation picture of an exported weapon: the game mesh with its game textures, lit and framed the way a showcase
render is.

The review sheets (stages.render) are for judging the asset: flat, even, every side. They make a good weapon look plain, and
that is half of why a showcase render of somebody else's gun looks better than ours on a sheet. `weaponforge <id> hero` is the
other kind of picture: one soft key light on the side the camera is on and a rim light behind the weapon, an outdoor image for the metal to mirror
(it has bright and dark in it; a studio image has only bright), a plain grey backdrop that the camera sees instead of that
image, a floor that only catches the shadow, a long lens, a view transform with some contrast, and an exposure metered on
the weapon itself (METER), so that one set of lights serves a black gun and a stainless one.

It reads what `view` reads, the exported static mesh and the three game textures, so the picture is of the asset the game
gets and of nothing else: no authoring material, no extra detail. It neither opens nor saves the weapon's .blend, and writes
<asset root>/_gallery/hero/<Name>.png (from the front) and <Name>_rear.png (from behind and above, near where a player's
eye is). Asked for by name (`--shots`, SHOT_NAMES), it also writes <Name>_beauty.png (the front view on a near-black
backdrop), <Name>_fp.png (from the player's eye, the gun at the hip) and <Name>_ads.png (down the sights); <Name>_left.png and
<Name>_right.png (straight from each side of the weapon, lit as the front picture is) and <Name>_outline.png (its silhouette from the
left, flat grey on near-black: nothing but the outline, for comparing two builds). With a pose (`--pose`, make's pose) every
picture is of the weapon in that pose, <Name>_<shot>_pose_<pose>.png, and is framed and lit as the rest pose's is. A weapon that
looks dull here will look dull in the engine too: fix the textures, not this file."""
import math
import os
import tempfile

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from . import bake as B
from . import stages
from . import view as V
from . import viewer

RES = (2400, 1500)
SAMPLES = 160
SIZE = 4096                    # the textures go on at full size: this is a still picture, not a download
# name suffix, where the camera is (toward the muzzle, toward the weapon's left, up), lens in mm
SHOTS = (('', (0.74, 0.62, 0.17), 80.0), ('_rear', (-0.78, 0.50, 0.38), 80.0))
BACKDROP = ((0.30, 0.30, 0.31), (0.52, 0.52, 0.53))        # what the camera sees behind the weapon: bottom, top
ENV = ('courtyard.exr', 0.45, 160.0, 0.25)                 # what the metal mirrors: bundled image, strength, turn (degrees),
#                                                            how much of its colour is kept (a blue sky tints black steel blue)
KEY = (4.6, 1.5)               # watts for a pistol-sized weapon (scaled with the length squared), size in weapon lengths
RIM = (7.0, 0.45, 2.4)         # watts, width and length in weapon lengths
# The exposure is metered on the weapon, as a photographer's is: of the weapon's own pixels, this share may be no brighter
# than this (scene-linear), and the picture is exposed down until that holds, by this many stops at most. It is never exposed
# up: a black gun stays black. Without it one light serves blued steel well and burns stainless steel white.
METER = (0.85, 0.42, 1.6)

# --shots: which pictures. 'default' is the two above; the others are asked for by name, and they are taken in this order
# whatever order they are asked in, the default two first, so that asking for more never changes those two by a pixel
SHOT_NAMES = ('default', 'beauty', 'fp', 'ads', 'left', 'right', 'outline')
# beauty (<Name>_beauty.png): the front shot as a portfolio render. A near-black backdrop (bottom, top), a harder and
# brighter key (watts as KEY's, size in weapon lengths), a stronger rim, and a kicker from below the weapon's far side
# (watts, size in weapon lengths) that draws the underside's edges, so a black gun does not sink into the black behind it
BEAUTY_BACKDROP = ((0.012, 0.012, 0.013), (0.075, 0.075, 0.078))
BEAUTY_KEY = (6.0, 0.9)
BEAUTY_RIM = (16.0, 0.45, 2.4)
KICKER = (3.0, 1.0)
# fp (<Name>_fp.png): the weapon as the player sees it, held at the hip/ready. A weapon is drawn in a game at a narrower
# field of view than the world (about 60 degrees across), in a 16:9 frame. The eye, from the grip origin in cm (behind,
# toward the weapon's left, up), for a pistol-sized and a rifle-sized weapon (FP_SPAN: their lengths in m; between them it
# blends, beyond them it holds): a pistol is held further forward. The camera looks straight down the weapon's own axis,
# tipped down by FP_PITCH degrees, so the gun points into the picture toward its middle from the lower right
FP_FOV = 60.0
FP_RES = (2400, 1350)
FP_EYE = ((-25.0, 7.0, 10.5), (-36.0, 9.5, 19.5))
FP_SPAN = (0.20, 0.70)
FP_PITCH = 5.0
# ads (<Name>_ads.png): aiming down the sights, the eye on the line from the SightRear socket to SightFront, this many cm
# behind the rear sight (pistol-sized, rifle-sized, blended as FP_EYE). Skipped when the weapon has no such sockets
ADS_BACK = (24.0, 10.0)
# fp and ads are lit as a game scene is, from above and ahead of the player: the key stands above the weapon toward its
# muzzle (the weights of its direction from the weapon's middle: ahead, up, toward the left; it stands 1.75 weapon
# lengths away, as the key always does), the rim is off, and there is no floor (a gun in the hand casts
# its shadow on nothing close)
FP_KEY = (0.9, 1.3, 0.3)
# left, right (<Name>_left.png, <Name>_right.png): straight from the weapon's own side (not from the muzzle's side: the weapon's +Y
# is its left), a longer lens than the front picture's so that a flat side stays flat, lit as the front picture is (the key on the
# camera's side), no floor. The pictures a control or a mark on one side is cropped from (review.py)
SIDE_LENS = 120.0
# outline (<Name>_outline.png): the weapon's silhouette from its left, orthographic, flat grey (OUTLINE_FILL) on near-black
# (OUTLINE_BACK), at most OUTLINE_W px wide and 2/3 as high; nothing in it but the outline, so that two builds' silhouettes can be put
# over each other
OUTLINE_W = 1200
OUTLINE_FILL = (0.62, 0.62, 0.62)
OUTLINE_BACK = (0.035, 0.035, 0.04)


def folder(weapon):
    """Beside the weapons' folders, never inside one."""
    return os.path.join(os.path.dirname(weapon.asset_root), '_gallery', 'hero')


def _world(scene):
    w = bpy.data.worlds.new('Hero')
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(os.path.join(bpy.utils.resource_path('LOCAL'), 'datafiles', 'studiolights', 'world', ENV[0]),
                                     check_existing=True)
    turn = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(coord.outputs['Generated'], turn.inputs['Vector'])
    nt.links.new(turn.outputs[0], env.inputs['Vector'])
    lit = nt.nodes.new('ShaderNodeBackground')
    lit.inputs['Strength'].default_value = ENV[1]
    grey = nt.nodes.new('ShaderNodeHueSaturation')
    grey.inputs['Saturation'].default_value = ENV[3]
    nt.links.new(env.outputs[0], grey.inputs['Color'])
    nt.links.new(grey.outputs[0], lit.inputs['Color'])
    # the backdrop: a plain grey, a little lighter toward the top of the frame
    split = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Window'], split.inputs[0])
    ramp = nt.nodes.new('ShaderNodeMixRGB')
    ramp.inputs[1].default_value = BACKDROP[0] + (1.0,)
    ramp.inputs[2].default_value = BACKDROP[1] + (1.0,)
    nt.links.new(split.outputs['Y'], ramp.inputs[0])
    seen = nt.nodes.new('ShaderNodeBackground')
    nt.links.new(ramp.outputs[0], seen.inputs['Color'])
    path = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(path.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(lit.outputs[0], mix.inputs[1])
    nt.links.new(seen.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    scene.world = w
    return turn, ramp


def _meter(scene):
    """How bright the weapon is in the picture about to be taken: a small render with nothing behind it, read back as
    scene-linear numbers. Returns the brightness that METER[0] of the weapon's pixels lie under, or None."""
    import numpy
    r, im = scene.render, scene.render.image_settings
    keep = (r.resolution_percentage, im.file_format, im.color_mode, im.color_depth, r.film_transparent, scene.cycles.samples,
            scene.cycles.use_denoising, r.filepath)
    path = os.path.join(bpy.app.tempdir, 'weaponforge_meter.exr')
    level = None
    try:
        r.resolution_percentage = 14
        im.file_format = 'OPEN_EXR'
        im.color_mode, im.color_depth = 'RGBA', '32'
        r.film_transparent = True
        scene.cycles.samples, scene.cycles.use_denoising = 32, False
        r.filepath = path
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path, check_existing=False)
        buf = numpy.empty(img.size[0] * img.size[1] * 4, dtype=numpy.float32)
        img.pixels.foreach_get(buf)
        bpy.data.images.remove(img)
        px = buf.reshape(-1, 4)
        own = px[px[:, 3] > 0.98]
        if len(own) >= 50:
            lum = own[:, 0] * 0.2126 + own[:, 1] * 0.7152 + own[:, 2] * 0.0722
            level = float(numpy.quantile(lum, METER[0]))
    finally:
        (r.resolution_percentage, im.file_format, im.color_mode, im.color_depth, r.film_transparent, scene.cycles.samples,
         scene.cycles.use_denoising, r.filepath) = keep
        if os.path.isfile(path):
            os.remove(path)
    return level


def _aim(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat('-Z', 'Y').to_euler()


def _area(scene, name, size_x, size_y, watts):
    data = bpy.data.lights.new(name, 'AREA')
    data.shape = 'RECTANGLE'
    data.size, data.size_y = size_x, size_y
    data.energy = watts
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    return obj


def _blend(pair, length):
    """Between a pistol-sized weapon's number and a rifle-sized one's, by the weapon's length (FP_SPAN)."""
    t = min(1.0, max(0.0, (length - FP_SPAN[0]) / (FP_SPAN[1] - FP_SPAN[0])))
    if isinstance(pair[0], tuple):
        return tuple(a + (b - a) * t for a, b in zip(*pair))
    return pair[0] + (pair[1] - pair[0]) * t


def player_eyes(weapon, length):
    """{'fp': (eye, look), 'ads': (eye, look)}: where the player's eye is and which way it looks, in the weapon's frame (cm,
    the frame the sockets are in), for a weapon `length` m long. fp: FP_EYE blended by length, looking down the weapon's axis
    tipped down FP_PITCH degrees; ads: ADS_BACK behind the SightRear socket on the line to SightFront (left out when the
    weapon has neither). Weapon.player_eyes {'fp': (x, y, z), 'ads': (x, y, z)} moves either eye. The hero pictures `fp`
    and `ads` are taken from here, and so are the texel weights of a weapon with Weapon.texel_view (uv.view_demand)."""
    given = getattr(weapon, 'player_eyes', None) or {}
    out = {'fp': (Vector(given['fp']) if 'fp' in given else Vector(_blend(FP_EYE, length)),
                  Vector((math.cos(math.radians(FP_PITCH)), 0.0, -math.sin(math.radians(FP_PITCH)))))}
    sockets = {s[0]: Vector(s[2]) for s in weapon.sockets}
    if 'SightRear' in sockets and 'SightFront' in sockets:
        look = (sockets['SightFront'] - sockets['SightRear']).normalized()
        out['ads'] = (Vector(given['ads']) if 'ads' in given else sockets['SightRear'] - look * _blend(ADS_BACK, length), look)
    return out


def _state(obj):
    return [list(r) for r in obj.matrix_world]


def _outline(weapon, scene, cam, cam_data, side, pts, length, res, replay, moved, record, where_to, out):
    """<Name>_outline.png: the silhouette from the weapon's left, orthographic, flat grey on near-black, framed on the points `pts`
    (or, for a build compared against, exactly as the recorded one). Written last: it changes the view transform for itself."""
    from mathutils import Matrix
    given = replay['shots'].get('_outline') if replay else None
    keep = (scene.render.engine, scene.view_settings.view_transform, scene.view_settings.look, scene.view_settings.exposure,
            scene.render.resolution_x, scene.render.resolution_y, scene.world.color[:], scene.display.shading.light,
            scene.display.shading.color_type, scene.display.shading.single_color[:], scene.display.shading.show_cavity,
            scene.display.shading.show_specular_highlight, scene.display.shading.show_shadows, scene.display.shading.show_object_outline,
            scene.render.film_transparent)
    try:
        wide = min(OUTLINE_W, (res or RES)[0])
        size = tuple(given['res']) if given else (wide, wide * 2 // 3)
        scene.render.resolution_x, scene.render.resolution_y = size
        cam_data.type = 'ORTHO'
        cam_data.sensor_fit = 'AUTO'
        cam_data.clip_start, cam_data.clip_end = length * 0.02, length * 400.0
        if given:
            cam.matrix_world = moved @ Matrix(given['camera'])
            cam_data.ortho_scale = given['ortho_scale']
        else:
            quat = (-side).to_track_quat('-Z', 'Y')
            right, up = quat @ Vector((1.0, 0.0, 0.0)), quat @ Vector((0.0, 1.0, 0.0))
            xs, ys = [p.dot(right) for p in pts], [p.dot(up) for p in pts]
            mid = right * ((max(xs) + min(xs)) / 2.0) + up * ((max(ys) + min(ys)) / 2.0) + side * (sum(p.dot(side) for p in pts) / len(pts))
            cam_data.ortho_scale = max(max(xs) - min(xs), (max(ys) - min(ys)) * size[0] / size[1]) * 1.10
            cam.location = mid + side * length * 3.0
            _aim(cam, mid)
        bpy.context.view_layer.update()
        V._engine(scene, ('BLENDER_WORKBENCH', 'BLENDER_WORKBENCH_NEXT'))
        sh = scene.display.shading
        sh.light, sh.color_type, sh.single_color = 'FLAT', 'SINGLE', OUTLINE_FILL
        sh.show_cavity = sh.show_specular_highlight = sh.show_shadows = sh.show_object_outline = False
        scene.display.render_aa = '8'
        scene.world.color = OUTLINE_BACK
        scene.render.film_transparent = False
        scene.view_settings.view_transform = 'Standard'
        try:
            scene.view_settings.look = 'None'
        except TypeError:
            pass
        scene.view_settings.exposure = 0.0
        path = os.path.join(where_to, '%s_outline.png' % weapon.name)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out.append(path)
        if record is not None:
            record['shots']['_outline'] = {'camera': [list(r) for r in cam.matrix_world], 'type': 'ORTHO',
                                           'ortho_scale': cam_data.ortho_scale, 'res': list(size)}
        stages.log('hero: %s (silhouette from the weapon\'s left, %dx%d, %.1f cm across%s)'
                   % (path, size[0], size[1], cam_data.ortho_scale * 100.0,
                      '; camera as in the build compared against' if given else ''))
    finally:
        (scene.render.engine, scene.view_settings.view_transform, scene.view_settings.look, scene.view_settings.exposure,
         scene.render.resolution_x, scene.render.resolution_y, scene.world.color, scene.display.shading.light,
         scene.display.shading.color_type, scene.display.shading.single_color, scene.display.shading.show_cavity,
         scene.display.shading.show_specular_highlight, scene.display.shading.show_shadows, scene.display.shading.show_object_outline,
         scene.render.film_transparent) = keep


def _posed_mesh(weapon, pose):
    """The weapon's game mesh in one of its poses (Weapon.poses, the ones `render --what poses` shows), as the only mesh in a .blend of
    its own in the temporary folder: returns that file's path. The weapon's own .blend is opened (never saved) and its armature
    put in the pose, so a pose is what the rig does and not a copy of it; the exported static mesh has no bones to move. The .blend
    must be what was exported: a stage that is stale or never ran refuses (the pictures would be of something the game has not got).
    Starts from nothing it can keep: run it before viewer.load, which empties the scene."""
    from . import rig as R
    if pose not in weapon.poses:
        raise SystemExit('hero: no pose %s (have %s)' % (pose, ', '.join(weapon.poses)))
    if not os.path.isfile(weapon.blend):
        raise SystemExit('hero --pose: %s is not there (a pose needs the .blend: the rig moves the parts)' % weapon.blend)
    bpy.ops.wm.open_mainfile(filepath=weapon.blend)
    old = stages.stale() + ['the stage "%s" never ran in this file' % s for s in stages.skipped()]
    if old:
        raise SystemExit('hero --pose: the .blend is not what was exported (%s): re-run from the first of them and export again'
                         % '; '.join(old))
    game = R.find(weapon)
    if game is None:
        raise SystemExit('hero --pose: no game meshes in %s: run the stage "rig" first' % weapon.blend)
    R.pose(game['armature'], weapon.poses[pose] or None)
    graph = bpy.context.evaluated_depsgraph_get()
    skm = game['skm']
    mesh = bpy.data.meshes.new_from_object(skm.evaluated_get(graph), preserve_all_data_layers=True, depsgraph=graph)
    mesh.transform(skm.matrix_world)
    mesh.name = 'wf_posed'
    # not bpy.app.tempdir: viewer.load's reset of the scene empties it
    path = os.path.join(tempfile.gettempdir(), 'weaponforge_pose_%d.blend' % os.getpid())
    bpy.data.libraries.write(path, {mesh}, fake_user=True)
    return path


def make(weapon, size=None, samples=None, res=None, shots=None, out_dir=None, record=None, replay=None, pose=None):
    """Write the presentation pictures and return their paths. Starts from an empty scene, so it is run on its own (cli.py).
    shots: any of SHOT_NAMES (default: 'default' alone, the two pictures it always took).

    For the review (review.py): out_dir writes the pictures there instead of the gallery; record, a dict, is filled with each
    picture's camera, lights, exposure and the mesh's own frame ({'to_world', 'shots': {suffix: ...}}); replay, such a dict
    from another build, takes every picture with that camera, those lights and that exposure instead of framing, placing and
    metering them on this mesh, so that two builds' pictures differ only in the weapon. Without them nothing changes.

    pose: the name of one of Weapon.poses: every picture is of the weapon in it (<Name><shot>_pose_<pose>.png). The cameras, the
    lights and the eyes are those of the rest pose (framed on the rest mesh), so a pose is judged against the rest from the same
    place; the exposure is metered on the posed weapon."""
    shots = shots or ('default',)
    unknown = [s for s in shots if s not in SHOT_NAMES]
    if unknown:
        raise SystemExit('hero: no shot %s (have %s)' % (', '.join(unknown), ', '.join(SHOT_NAMES)))
    posed = _posed_mesh(weapon, pose) if pose else None
    mesh, pixels = viewer.load(weapon, size or SIZE)
    if record is not None:
        record['to_world'] = _state(mesh)
        record.setdefault('shots', {})
    from mathutils import Matrix
    moved = None
    if replay:
        # the other build's world in this one's: the same weapon frame, whatever matrix the import gave each mesh
        moved = mesh.matrix_world @ Matrix(replay['to_world']).inverted()
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    step = max(1, len(mesh.data.vertices) // 4000)
    pts = [mesh.matrix_world @ mesh.data.vertices[i].co for i in range(0, len(mesh.data.vertices), step)]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    centre = (lo + hi) / 2
    axis = 0 if (hi.x - lo.x) >= (hi.y - lo.y) else 1
    length = hi[axis] - lo[axis]
    # the weapon frame has +X toward the muzzle and +Y on the weapon's left (weapon.py), and the import keeps it. The muzzle used to be
    # taken as the end farther from the grip origin, which is the stock on a weapon with a long stock (the SMG): its "front" picture
    # was taken from behind, and the lights of the hip picture stood behind the player
    muzzle = (mesh.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    up = Vector((0.0, 0.0, 1.0))
    left = up.cross(muzzle)

    if posed:
        # the framing above is the rest mesh's; the posed geometry goes in now, under the same material
        with bpy.data.libraries.load(posed) as (src, dst):
            dst.meshes = list(src.meshes)
        os.remove(posed)
        material = mesh.data.materials[0]
        mesh.data = dst.meshes[0]
        mesh.data.materials.clear()
        mesh.data.materials.append(material)
        bpy.context.view_layer.update()
    tag = '_pose_%s' % pose if pose else ''

    B.setup_cycles(samples or SAMPLES, gpu=True)
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res or RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = 'AgX'
        looks = [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items]
        pick = [k for k in looks if 'Medium High Contrast' in k] or [k for k in looks if 'Base Contrast' in k]
        if pick:
            scene.view_settings.look = pick[0]
    except TypeError:
        pass
    turn, backdrop = _world(scene)

    # the floor catches the shadow and nothing else, a little under the weapon so that it hangs in the air
    bpy.ops.mesh.primitive_plane_add(size=length * 40.0, location=(centre.x, centre.y, lo.z - 0.30 * (hi.z - lo.z)))
    floor = bpy.context.object
    floor.is_shadow_catcher = True

    scale = (length / 0.27) ** 2
    key = _area(scene, 'key', KEY[1] * length, KEY[1] * length, KEY[0] * scale)
    rim = _area(scene, 'rim', RIM[1] * length, RIM[2] * length, RIM[0] * scale)
    cam_data = bpy.data.cameras.new('cam')
    cam = bpy.data.objects.new('cam', cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.clip_start, cam_data.clip_end = length * 0.02, length * 400.0

    out = []
    where_to = out_dir or folder(weapon)
    os.makedirs(where_to, exist_ok=True)

    def frame(d, lens):
        """Stand the camera on direction d from the weapon, lens in mm. Returns how far away it stands."""
        cam_data.lens = lens
        # As near as keeps the whole weapon in the frame, looking at the middle of what the camera SEES. Aimed at the
        # middle of the weapon's box, a long gun seen from behind sat small and off to one side: its near end is large
        # in the picture and its far end small, so one edge of the frame stopped the camera while the other stood empty
        target = centre.copy()
        for attempt in range(6):
            dist = 0.3 * length
            for _ in range(300):
                cam.location = target + d * dist
                _aim(cam, target)
                bpy.context.view_layer.update()
                seen = [world_to_camera_view(scene, cam, p) for p in pts]
                if all(0.07 < p.x < 0.93 and 0.10 < p.y < 0.90 and p.z > 0.0 for p in seen):
                    break
                dist *= 1.03
            off_x = (min(p.x for p in seen) + max(p.x for p in seen)) / 2 - 0.5
            off_y = (min(p.y for p in seen) + max(p.y for p in seen)) / 2 - 0.5
            if attempt == 5 or (abs(off_x) < 0.004 and abs(off_y) < 0.004):
                break
            wide = dist * cam_data.sensor_width / lens
            high = wide * scene.render.resolution_y / scene.render.resolution_x
            target = target + cam.matrix_world.to_3x3() @ Vector((off_x * wide, off_y * high, 0.0))
        return dist

    def place(d):
        """The key and the rim for a camera on direction d. Returns the weapon's side in view and the end in view."""
        # The lights are placed by the WEAPON's sides, not by the camera's left and right. The key stands on the side the
        # camera is on, above the weapon and a little toward the camera's end: the side in view is lit by it, and the three
        # planes in view (side, top, end) each get a different share. The rim stands behind the far end, above, on the FAR
        # side: it draws the top edges and never touches the side in view. Placed by the camera it once skimmed along that
        # side from behind, and a light that skims a surface lies on it as a milky veil (walnut came out grey)
        side = left if d.dot(left) >= 0.0 else -left
        ahead = muzzle if d.dot(muzzle) >= 0.0 else -muzzle
        key.location = centre + (side * 0.95 + up * 1.15 + ahead * 0.35).normalized() * (1.75 * length)
        _aim(key, centre)
        rim.location = centre + (-side * 0.6 + up * 0.9 - ahead * 0.9).normalized() * (1.6 * length)
        _aim(rim, centre)
        return side, ahead

    def take(suffix, d, colours, note):
        """Meter, expose and write <Name><suffix>.png. d: the direction the camera stands on from the weapon, which turns
        the mirrored image with it; colours: the backdrop's (bottom, top)."""
        turn.inputs['Rotation'].default_value = (0.0, 0.0, math.atan2(d.y, d.x) + math.radians(ENV[2]))
        lights = [o for o in scene.objects if o.type == 'LIGHT']
        given = replay['shots'].get(suffix) if replay else None
        if given:
            # another build's picture: its camera, lights, floor, mirrored image and exposure, moved into this mesh's world
            cam.matrix_world = moved @ Matrix(given['camera'])
            cam_data.lens, cam_data.angle, cam_data.sensor_fit = given['lens'], given['angle'], given['sensor_fit']
            cam_data.clip_start, cam_data.clip_end = given['clip']
            scene.render.resolution_x, scene.render.resolution_y = given['res']
            for light in lights:
                spec = given['lights'].get(light.name)
                if spec is None:
                    light.hide_render = True
                    continue
                light.matrix_world = moved @ Matrix(spec['matrix'])
                light.data.size, light.data.size_y, light.data.energy = spec['size']
                light.hide_render = spec['hidden']
            floor.matrix_world = moved @ Matrix(given['floor'][0])
            floor.hide_render = given['floor'][1]
            turn.inputs['Rotation'].default_value = given['turn']
            level, stops = None, given['stops']
        else:
            scene.view_settings.exposure = 0.0
            level = _meter(scene)
            stops = max(-METER[2], math.log2(METER[1] / level)) if level and level > METER[1] else 0.0
        scene.view_settings.exposure = stops
        for slot, colour in ((1, colours[0]), (2, colours[1])):         # the backdrop keeps its grey whatever the exposure
            backdrop.inputs[slot].default_value = tuple(c * 2.0 ** -stops for c in colour) + (1.0,)
        if record is not None:
            back = mesh.matrix_world.inverted() @ Matrix(record['to_world'])     # identity: kept in this mesh's world
            record['shots'][suffix] = {
                'camera': [list(r) for r in back @ cam.matrix_world], 'lens': cam_data.lens, 'angle': cam_data.angle,
                'sensor_fit': cam_data.sensor_fit, 'clip': [cam_data.clip_start, cam_data.clip_end],
                'res': [scene.render.resolution_x, scene.render.resolution_y],
                'lights': {o.name: {'matrix': [list(r) for r in back @ o.matrix_world],
                                    'size': [o.data.size, o.data.size_y, o.data.energy], 'hidden': o.hide_render}
                           for o in lights},
                'floor': [[list(r) for r in back @ floor.matrix_world], floor.hide_render],
                'turn': list(turn.inputs['Rotation'].default_value), 'stops': stops}
        path = os.path.join(where_to, '%s%s%s.png' % (weapon.name, suffix, tag))
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out.append(path)
        stages.log('hero: %s (%s, textures at %d px; the weapon metered %s, exposed %+.2f stops%s)'
                   % (path, note, pixels, '%.3f' % level if level else 'nothing', stops,
                      '; camera, lights and exposure as in the build compared against' if given else ''))

    if 'default' in shots:
        for suffix, where, lens in SHOTS:
            d = (muzzle * where[0] + left * where[1] + up * where[2]).normalized()
            dist = frame(d, lens)
            place(d)
            take(suffix, d, BACKDROP, 'camera %.2f m away, %d mm' % (dist, lens))

    if 'beauty' in shots:
        # the front shot's camera and lights, made harder and darker, with a kicker from below the far side; no floor (its
        # shadow would not show on the dark backdrop, and it would stand between the kicker and the weapon)
        _, where, lens = SHOTS[0]
        d = (muzzle * where[0] + left * where[1] + up * where[2]).normalized()
        dist = frame(d, lens)
        side, ahead = place(d)
        key.data.size = key.data.size_y = BEAUTY_KEY[1] * length
        key.data.energy = BEAUTY_KEY[0] * scale
        rim.data.size, rim.data.size_y, rim.data.energy = BEAUTY_RIM[1] * length, BEAUTY_RIM[2] * length, BEAUTY_RIM[0] * scale
        kicker = _area(scene, 'kicker', KICKER[1] * length, KICKER[1] * length, KICKER[0] * scale)
        kicker.visible_camera = False
        kicker.location = centre + (-side - up * 0.35).normalized() * (1.4 * length)
        _aim(kicker, centre)
        floor.hide_render = True
        take('_beauty', d, BEAUTY_BACKDROP, 'camera %.2f m away, %d mm' % (dist, lens))
        bpy.data.objects.remove(kicker, do_unlink=True)

    wanted = [s for s in ('fp', 'ads') if s in shots]
    if wanted:
        # the player's eye: a 16:9 frame at the weapon's field of view, a near plane close enough for a gun in the hand,
        # the key above and ahead, no rim, no floor. Positions are in the weapon's own frame (cm), as the sockets are
        scene.render.resolution_x, scene.render.resolution_y = res or FP_RES
        cam_data.sensor_fit = 'HORIZONTAL'
        cam_data.angle = math.radians(FP_FOV)
        cam_data.clip_start = 0.005
        key.data.size = key.data.size_y = KEY[1] * length
        key.data.energy = KEY[0] * scale
        key.location = centre + (muzzle * FP_KEY[0] + up * FP_KEY[1] + left * FP_KEY[2]).normalized() * (1.75 * length)
        _aim(key, centre)
        rim.hide_render = True
        floor.hide_render = True
        to_world = mesh.matrix_world
        eyes = player_eyes(weapon, length)
        for name in wanted:
            if name not in eyes:
                stages.log('hero: no ads picture: %s has no SightRear and SightFront sockets' % weapon.id)
                continue
            eye, look = eyes[name]
            cam.location = to_world @ eye
            look = (to_world.to_3x3() @ look).normalized()
            _aim(cam, cam.location + look)
            bpy.context.view_layer.update()
            seen = [world_to_camera_view(scene, cam, p) for p in pts]
            inside = [p for p in seen if 0.0 <= p.x <= 1.0 and 0.0 <= p.y <= 1.0 and p.z > 0.0]
            note = ('eye at (%.1f, %.1f, %.1f) cm, %d degrees across; %d %% of the weapon in the frame, its nearest part %.1f cm '
                    'away' % (eye.x, eye.y, eye.z, FP_FOV, 100 * len(inside) // len(seen),
                              100.0 * min((p.z for p in inside), default=0.0)))
            if inside:
                note += ', across x %.2f to %.2f and y %.2f to %.2f' % (min(p.x for p in inside), max(p.x for p in inside),
                                                                      min(p.y for p in inside), max(p.y for p in inside))
            take('_' + name, -look, BACKDROP, note)

    sides = [(s, sign) for s, sign in (('left', 1.0), ('right', -1.0)) if s in shots]
    if sides or 'outline' in shots:
        # the front picture's rig again (the pictures above changed the lights, the frame and the lens), from the weapon's own sides
        to_world = mesh.matrix_world
        side = (to_world.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()           # the weapon's left, in the picture's world
        scene.render.resolution_x, scene.render.resolution_y = res or RES
        cam_data.sensor_fit = 'AUTO'
        cam_data.clip_start, cam_data.clip_end = length * 0.02, length * 400.0
        key.data.size = key.data.size_y = KEY[1] * length
        key.data.energy = KEY[0] * scale
        rim.data.size, rim.data.size_y, rim.data.energy = RIM[1] * length, RIM[2] * length, RIM[0] * scale
        rim.hide_render = False
        floor.hide_render = True
        for name, sign in sides:
            d = side * sign
            dist = frame(d, SIDE_LENS)
            place(d)
            take('_' + name, d, BACKDROP, 'camera %.2f m away, %d mm, straight from the weapon\'s %s' % (dist, SIDE_LENS, name))
        if 'outline' in shots:
            _outline(weapon, scene, cam, cam_data, side, pts, length, res, replay, moved if replay else None, record, where_to, out)
    return out
