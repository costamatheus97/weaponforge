"""weaponforge: review renders written to disk.

shots() renders one tile per view direction with a temporary camera and stitches them into a single PNG. Reading that PNG is how an
agent looks at its work: the Blender MCP `look` tool cannot hand an image across the WSL / Windows boundary, and `blender -b` has no
viewport at all.
"""
import math
import os
import time

import bpy
import numpy as np
from mathutils import Vector

from . import kit as K

VIEW = {
    'left': (0, 1, 0), 'right': (0, -1, 0), 'top': (0, 0.0001, 1), 'bottom': (0, 0.0001, -1), 'front': (1, 0, 0), 'rear': (-1, 0, 0),
    'fp': (-1.0, 0.45, 0.42),           # stands in for the hip eye's direction only where a sheet is not given the weapon's own eye
                                        # (stages.render resolves it per weapon from hero.player_eyes). It was (-1, -0.45, 0.42), from the
                                        # weapon's RIGHT, while the hero hip picture is taken from its left
    'q_front_l': (1, 0.8, 0.45), 'q_front_r': (1, -0.8, 0.45), 'q_rear_l': (-1, 0.8, 0.45), 'q_rear_r': (-1, -0.8, 0.45),
    'q_low_l': (0.6, 1, -0.5),
}
BACKDROP = (0.16, 0.165, 0.175)


def _engine(scene, wanted):
    for name in wanted:
        try:
            scene.render.engine = name
            return name
        except TypeError:
            continue
    return scene.render.engine


def _save(img, out):
    """Write the sheet and return where it went. Windows refuses to replace a picture that something has open (a viewer, an
    upload still reading it): wait a little, and if it stays locked write the sheet beside it as <name>_new.png."""
    stem, ext = os.path.splitext(out)
    other = stem + '_new' + ext
    for wait in (0.0, 0.5, 1.0, 2.0, 4.0):
        time.sleep(wait)
        try:
            img.filepath_raw = out
            img.save()
        except RuntimeError:
            continue
        if os.path.exists(other):              # an older stand-in for this sheet would now be the stale one
            try:
                os.remove(other)
            except OSError:
                pass
        return out
    img.filepath_raw = other
    img.save()
    print('[view] %s is open in another program and could not be replaced: this render is in %s' % (out, other), flush=True)
    return other


def _stitch(paths, cols, out, backdrop=None):
    tiles = []
    for path in paths:
        img = bpy.data.images.load(path)
        w, h = img.size
        arr = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(arr)
        arr = arr.reshape(h, w, 4)
        if backdrop is not None:
            # a flat backdrop put in afterwards: mixed into the world it darkens the whole picture
            a = arr[..., 3:4]
            arr[..., :3] = arr[..., :3] * a + np.array(backdrop, dtype=np.float32) * (1.0 - a)
            arr[..., 3] = 1.0
        tiles.append(arr)
        bpy.data.images.remove(img)
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + cols - 1) // cols
    sheet = np.zeros((rows * h, cols * w, 4), dtype=np.float32)
    sheet[..., 3] = 1.0
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        sheet[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w] = tile      # image rows run bottom-up
    # a thin line between tiles: two cropped close-ups side by side otherwise read as one mirrored shape
    for c in range(1, cols):
        sheet[:, c * w - 1:c * w + 1, :3] = 0.32
    for r in range(1, rows):
        sheet[r * h - 1:r * h + 1, :, :3] = 0.32
    img = bpy.data.images.new('wf_sheet', cols * w, rows * h, alpha=False)
    img.pixels.foreach_set(sheet.ravel())
    img.file_format = 'PNG'
    out = _save(img, out)
    bpy.data.images.remove(img)
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass
    return out


class _Solo:
    """Render exactly `objs`: everything else is hidden from the render for the duration, and put back after."""

    def __init__(self, objs):
        self.objs = set(objs)

    def __enter__(self):
        self.saved = {o.name: o.hide_render for o in bpy.data.objects}
        self.colls = {}
        for o in bpy.data.objects:
            o.hide_render = o not in self.objs
        for o in self.objs:
            for coll in o.users_collection:
                if coll.name not in self.colls:
                    self.colls[coll.name] = coll.hide_render
                    coll.hide_render = False

    def __exit__(self, *exc):
        for o in bpy.data.objects:
            if o.name in self.saved:
                o.hide_render = self.saved[o.name]
        for name, value in self.colls.items():
            coll = bpy.data.collections.get(name)
            if coll is not None:
                coll.hide_render = value


def _begin(scene, engine, res, color, samples, transparent):
    """Set the scene up for a review render (engine, flat or studio shading, size, file type). Returns what _end puts back."""
    saved = dict(engine=scene.render.engine, camera=scene.camera, path=scene.render.filepath, rx=scene.render.resolution_x,
                 ry=scene.render.resolution_y, pct=scene.render.resolution_percentage, fmt=scene.render.image_settings.file_format,
                 mode=scene.render.image_settings.color_mode, transparent=scene.render.film_transparent)
    if engine == 'WORKBENCH':
        _engine(scene, ('BLENDER_WORKBENCH', 'BLENDER_WORKBENCH_NEXT'))
        sh = scene.display.shading
        sh.light = 'STUDIO'
        sh.color_type = color
        sh.show_cavity = True
        sh.cavity_type = 'BOTH'
        sh.cavity_ridge_factor = 1.0
        sh.cavity_valley_factor = 1.0
        sh.curvature_ridge_factor = 1.0
        sh.curvature_valley_factor = 1.0
        sh.show_shadows = False
        sh.show_specular_highlight = True
        sh.show_object_outline = False
        scene.display.render_aa = '8'
    elif engine == 'EEVEE':
        _engine(scene, ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'))
        if samples:
            scene.eevee.taa_render_samples = samples
    else:
        _engine(scene, (engine,))
        if samples:
            scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = transparent
    scene.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    return saved


def _end(scene, saved):
    scene.camera = saved['camera']
    scene.render.filepath = saved['path']
    scene.render.resolution_x, scene.render.resolution_y = saved['rx'], saved['ry']
    scene.render.resolution_percentage = saved['pct']
    scene.render.image_settings.file_format = saved['fmt']
    scene.render.image_settings.color_mode = saved['mode']
    scene.render.film_transparent = saved['transparent']
    try:
        scene.render.engine = saved['engine']
    except TypeError:
        pass


def _temp_camera(scene):
    cam_data = bpy.data.cameras.new('wf_tmp_cam')
    cam = bpy.data.objects.new('wf_tmp_cam', cam_data)
    scene.collection.objects.link(cam)
    cam_data.clip_start = 0.5
    cam_data.clip_end = 5000.0
    return cam, cam_data


def shots(out_dir, name, views, objs, res=(900, 620), cols=2, engine='WORKBENCH', persp=False, lens=85.0, margin=1.10,
          color='OBJECT', region=None, samples=None, on_view=None, backdrop=None):
    """Render `views` (names from VIEW or direction vectors, target -> eye) of exactly `objs` into <out_dir>/<name>.png.
    region: ((lo), (hi)) overrides the framed box (cm) for close-ups. Returns the path."""
    scene = bpy.context.scene
    objs = [o for o in objs if o.type == 'MESH']
    if not objs:
        raise ValueError('shots: nothing to render')
    os.makedirs(out_dir, exist_ok=True)
    if region is not None:
        lo, hi = Vector(region[0]), Vector(region[1])
        corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    else:
        bpy.context.view_layer.update()
        lo, hi = K.bounds(objs)
        corners = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    centre = (lo + hi) / 2

    saved = _begin(scene, engine, res, color, samples, backdrop is not None)
    cam, cam_data = _temp_camera(scene)
    aspect = res[0] / res[1]
    paths = []
    try:
        with _Solo(objs):
            for i, view in enumerate(views):
                d = Vector(VIEW[view] if isinstance(view, str) else view).normalized()
                quat = d.to_track_quat('Z', 'Y')
                cam.rotation_euler = quat.to_euler()
                right = quat @ Vector((1.0, 0.0, 0.0))
                up = quat @ Vector((0.0, 1.0, 0.0))
                xs = [(c - centre).dot(right) for c in corners]
                ys = [(c - centre).dot(up) for c in corners]
                width = (max(xs) - min(xs)) * margin
                height = (max(ys) - min(ys)) * margin
                mid = centre + right * ((max(xs) + min(xs)) / 2) + up * ((max(ys) + min(ys)) / 2)
                span = max(width, height * aspect)
                if persp:
                    cam_data.type = 'PERSP'
                    cam_data.lens = lens
                    cam_data.sensor_width = 36.0
                    dist = span / 2 / (18.0 / lens) + max((c - centre).dot(d) for c in corners)
                    cam.location = mid + d * dist
                else:
                    cam_data.type = 'ORTHO'
                    cam_data.ortho_scale = span
                    cam.location = mid + d * 300.0
                scene.camera = cam
                if on_view is not None:
                    on_view(d)
                path = os.path.join(out_dir, '_tile_%s_%d.png' % (name, i))
                scene.render.filepath = path
                bpy.ops.render.render(write_still=True)
                paths.append(path)
        out = _stitch(paths, cols, os.path.join(out_dir, name + '.png'), backdrop)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cam_data)
        _end(scene, saved)
    return out


def eye_shots(out_dir, name, eyes, objs, res=(1400, 788), fov=60.0, log=print):
    """The player's own cameras, taken from `objs` alone, so that a model can be judged from them before there is an export. eyes:
    {label: (eye, look)} in the weapon frame, cm (hero.player_eyes: the hip picture's camera and the aiming one's, which are the ones
    `hero` takes its `fp` and `ads` pictures from). Each is a perspective camera `fov` degrees across the picture's width, and the
    tile is the game's frame, 16:9, whatever `res` says about the height: what the camera sees is what the game shows, the weapon cut
    by the frame's edge where the game cuts it. The tiles go one above the other, in the order of `eyes`. Returns the path."""
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    objs = [o for o in objs if o.type == 'MESH']
    if not objs:
        raise ValueError('eye_shots: nothing to render')
    os.makedirs(out_dir, exist_ok=True)
    bpy.context.view_layer.update()
    res = (res[0], max(1, res[0] * 9 // 16))
    saved = _begin(scene, 'WORKBENCH', res, 'OBJECT', None, False)
    cam, cam_data = _temp_camera(scene)
    cam_data.type = 'PERSP'
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.angle = math.radians(fov)
    cam_data.clip_start = 0.5
    step = max(1, sum(len(o.data.vertices) for o in objs) // 6000)
    pts = [o.matrix_world @ o.data.vertices[i].co for o in objs for i in range(0, len(o.data.vertices), step)]
    paths = []
    try:
        with _Solo(objs):
            for i, (label, (eye, look)) in enumerate(eyes.items()):
                look = Vector(look).normalized()
                cam.location = Vector(eye)
                cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
                bpy.context.view_layer.update()
                scene.camera = cam
                seen = [world_to_camera_view(scene, cam, p) for p in pts]
                inside = [p for p in seen if 0.0 <= p.x <= 1.0 and 0.0 <= p.y <= 1.0 and p.z > 0.0]
                note = '%d %% of the model in the frame' % (100 * len(inside) // max(1, len(seen)))
                if inside:
                    note += ', across x %.2f to %.2f and y %.2f to %.2f' % (min(p.x for p in inside), max(p.x for p in inside),
                                                                          min(p.y for p in inside), max(p.y for p in inside))
                log('%s: %s eye at (%.1f, %.1f, %.1f) cm, %d degrees across, %dx%d; %s'
                    % (name, label, eye[0], eye[1], eye[2], fov, res[0], res[1], note))
                path = os.path.join(out_dir, '_tile_%s_%d.png' % (name, i))
                scene.render.filepath = path
                bpy.ops.render.render(write_still=True)
                paths.append(path)
        out = _stitch(paths, 1, os.path.join(out_dir, name + '.png'))
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cam_data)
        _end(scene, saved)
    return out


def colour_parts(objs, palette):
    """Flat object colours for the grey review renders: palette is {object-name prefix: (r, g, b, a)}."""
    keys = sorted(palette, key=len, reverse=True)       # the longest prefix wins: 'SlideStop' before 'Slide'
    for obj in objs:
        for key in keys:
            if obj.name.startswith(key):
                obj.color = palette[key]
                break
