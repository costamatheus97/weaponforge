"""weaponforge: bake the high-detail parts onto the game mesh's UV sheet (tangent normal, ambient occlusion, material ID).

Each game part takes detail only from its own high-detail part (same builder), so neighbours never print onto each other; the
occlusion pass also sees the neighbours a part never moves against (Weapon.ao_friends). Results are float arrays, row 0 at v = 0.

The settings below are the ones that worked first time on the pistol and were never changed: see PLAYBOOK.md, "Bake".
"""
import json
import os
import time

import bpy
import numpy as np

from . import maps
from .ops import only, run


class Kind:
    """A surface kind: its code in the material-ID map and the edge break (cm) its normal map carries.

    The code is one bit per colour channel, so there are seven (black is "no surface"). The material decodes them again
    (surface.Surface.mask), so a kind's name is all a builder and a recipe ever use."""

    def __init__(self, code, bevel):
        self.code = tuple(float(c) for c in code)
        self.bevel = bevel


KINDS = {
    'steel': Kind((1, 0, 0), 0.030),       # the default: blued or parkerised steel
    'bright': Kind((1, 0, 1), 0.030),      # bare polished steel (a barrel, a bolt)
    'dark': Kind((1, 1, 0), 0.026),        # small black parts (sights, controls)
    'wood': Kind((0, 1, 0), 0.014),
    'brass': Kind((0, 0, 1), 0.020),
    'copper': Kind((0, 1, 1), 0.020),
    'polymer': Kind((1, 1, 1), 0.035),
}

CAGE_EXTRUSION = 0.02      # cm: how far outside the game surface a ray starts
MAX_RAY = 0.25             # cm: how far it may travel to find the detail
BEVEL_SAMPLES = 12
AO_DISTANCE = 6.0          # cm


def log(*a):
    print('[bake]', *a, flush=True)


def kinds_of(weapon):
    return weapon.kinds or KINDS


# ------------------------------------------------------------------------------------------------------------ materials
def hp_material(weapon, kind):
    """The bake-source material of one kind: a Bevel node rounds every edge in the normal pass, the emission is the ID code."""
    spec = kinds_of(weapon)[kind]
    name = '%s_HP_%s' % (weapon.tag, kind)
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bevel = nt.nodes.new('ShaderNodeBevel')
    bevel.samples = BEVEL_SAMPLES
    bevel.inputs['Radius'].default_value = float(weapon.edge_break.get(kind, spec.bevel))
    nt.links.new(bevel.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1.0)
    bsdf.inputs['Emission Color'].default_value = spec.code + (1.0,)
    bsdf.inputs['Emission Strength'].default_value = 1.0
    return mat


def assign_hp_materials(weapon, hp_objs):
    """One slot per kind the part has. Weapon.hp_kinds may paint the faces of a part with more than one (it sets material_index)."""
    known = kinds_of(weapon)
    for obj in hp_objs:
        obj.data.materials.clear()
        kinds = weapon.hp_kinds(obj)
        for kind in kinds:
            if kind not in known:
                raise KeyError('%s: surface kind %r is not in the weapon\'s kinds (%s)' % (obj.name, kind, ', '.join(known)))
            obj.data.materials.append(hp_material(weapon, kind))
        if len(kinds) == 1:
            obj.data.polygons.foreach_set('material_index', [0] * len(obj.data.polygons))
            obj.data.update()


INKS = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))        # the lettering mask's channel for each of a weapon's paints


def _glow(name, colour):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = tuple(colour) + (1.0,)
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def mark_objects(weapon):
    """{builder: [copies of the lettering cut into its parts]} (kit.keep_mark), each with the material of its ink."""
    coll = bpy.data.collections.get(weapon.coll('MARKS'))
    found = {}
    for obj in (coll.objects if coll else ()):
        ink = min(max(int(obj.get('ink', 0)), 0), len(INKS) - 1)
        obj.data.materials.clear()
        obj.data.materials.append(_glow('%s_MARK_%d' % (weapon.tag, ink), INKS[ink]))
        found.setdefault(obj.get('builder'), []).append(obj)
    return found


def lp_bake_material(weapon):
    name = '%s_LP_bake' % weapon.tag
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.name = 'target'
    nt.nodes.active = tex
    return mat


def image(name, size, fill=(0.0, 0.0, 0.0, 0.0)):
    img = bpy.data.images.get(name)
    if img is not None and (img.size[0] != size or not img.is_float):
        bpy.data.images.remove(img)
        img = None
    if img is None:
        img = bpy.data.images.new(name, size, size, alpha=True, float_buffer=True, is_data=True)
    img.pixels.foreach_set(np.tile(np.array(fill, dtype=np.float32), size * size))
    img.update()
    return img


def pixels(img):
    arr = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    return arr.reshape(img.size[1], img.size[0], 4)


def _target(mat, img):
    node = mat.node_tree.nodes['target']
    node.image = img
    mat.node_tree.nodes.active = node


# ------------------------------------------------------------------------------------------------------------------ bake
def setup_cycles(samples, gpu=None):
    """Cycles for baking. gpu=True takes the first graphics backend that has a device (a fresh `blender -b` reports none until
    one is chosen); gpu=False forces the CPU; gpu=None leaves the device alone."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    if gpu is not None:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        used = 'CPU'
        if gpu:
            for kind in ('HIP', 'OPTIX', 'CUDA', 'ONEAPI', 'METAL'):
                try:
                    prefs.compute_device_type = kind
                except TypeError:
                    continue
                prefs.get_devices()
                devs = [d for d in prefs.devices if d.type == kind]
                if devs:
                    for d in prefs.devices:
                        d.use = d.type == kind
                    used = kind
                    break
        scene.cycles.device = 'GPU' if used != 'CPU' else 'CPU'
        log('cycles device', used)
    return scene


def unhide(colls):
    """Look-dev renders hide the high-detail parts; a bake needs both collections visible and selectable, or it stops with
    "No valid selected objects"."""
    for coll in colls:
        coll.hide_render = coll.hide_viewport = coll.hide_select = False
        for obj in coll.objects:
            obj.hide_render = obj.hide_viewport = obj.hide_select = False
            obj.hide_set(False)


def _bake(kind, **kw):
    return run(bpy.ops.object.bake, type=kind, **kw)


def bake_all(weapon, lp_objs, hp_objs, size, samples_normal=64, samples_ao=128, only_builders=None):
    """Returns {'normal', 'ao', 'id', 'cover'}: float arrays (size, size, 4), row 0 at v = 0."""
    scene = bpy.context.scene
    mat = lp_bake_material(weapon)
    for obj in lp_objs:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    assign_hp_materials(weapon, hp_objs)
    tag = weapon.tag.lower()
    imgs = {'normal': image(tag + '_bake_normal', size, (0.5, 0.5, 1.0, 0.0)), 'ao': image(tag + '_bake_ao', size, (1.0, 1.0, 1.0, 0.0)),
            'id': image(tag + '_bake_id', size), 'cover': image(tag + '_bake_cover', size), 'marks': image(tag + '_bake_marks', size)}
    lettering = mark_objects(weapon)
    blank = _glow(weapon.tag + '_HP_blank', (0.0, 0.0, 0.0))
    by_builder = {}
    for obj in hp_objs:
        by_builder.setdefault(obj.get('builder'), []).append(obj)
    saved = {o.name: o.hide_render for o in bpy.data.objects}
    bk = scene.render.bake
    bk.margin = 0                      # the islands are padded afterwards (maps.dilate), which also fills the missed rays
    bk.use_clear = False
    bk.target = 'IMAGE_TEXTURES'
    bk.normal_space = 'TANGENT'
    bk.cage_extrusion = CAGE_EXTRUSION
    bk.max_ray_distance = MAX_RAY
    bk.use_cage = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new('World')
    scene.world.light_settings.distance = AO_DISTANCE
    t0 = time.time()
    missing = []
    try:
        for lp in lp_objs:
            key = lp.get('builder')
            if only_builders and key not in only_builders:
                continue
            src = by_builder.get(key, [])
            if not src:
                missing.append(key)
                continue
            t = time.time()
            for o in bpy.data.objects:
                o.hide_render = True
            lp.hide_render = False
            for o in src:
                o.hide_render = False
            only(src + [lp], active=lp)
            bk.use_selected_to_active = True
            # normal
            scene.cycles.samples = samples_normal
            _target(mat, imgs['normal'])
            _bake('NORMAL')
            # material ID
            scene.cycles.samples = 4
            _target(mat, imgs['id'])
            _bake('EMIT')
            # lettering: the kept copies of the text cutters glow, the detail itself is black and stands in their way from
            # behind (a thin part's letters would otherwise show through on its other side)
            ink = lettering.get(key, [])
            if ink:
                held = [(slot, slot.material) for o in src for slot in o.material_slots]
                try:
                    for slot, _was in held:
                        slot.material = blank
                    for o in ink:
                        o.hide_render = o.hide_viewport = o.hide_select = False
                    only(src + ink + [lp], active=lp)
                    scene.cycles.samples = 16
                    _target(mat, imgs['marks'])
                    _bake('EMIT')
                finally:
                    for slot, was in held:
                        slot.material = was
                    for o in ink:
                        o.hide_render = True
                only(src + [lp], active=lp)
            # occlusion: the friends shade, but only this part's own detail is projected
            for friend in weapon.ao_friends.get(key, []):
                for o in by_builder.get(friend, []):
                    o.hide_render = False
            scene.cycles.samples = samples_ao
            _target(mat, imgs['ao'])
            _bake('AO')
            # coverage of the game part's own texels
            bk.use_selected_to_active = False
            only([lp])
            scene.cycles.samples = 1
            _target(mat, imgs['cover'])
            _bake('EMIT')
            log('%-14s %.1fs' % (key, time.time() - t))
    finally:
        for o in bpy.data.objects:
            if o.name in saved:
                o.hide_render = saved[o.name]
    if missing:
        raise RuntimeError('no high-detail part for: %s (build them: stage "model")' % ', '.join(sorted(set(missing))))
    log('baked in %.1fs' % (time.time() - t0))
    return {k: pixels(v) for k, v in imgs.items()}


def preview(arr, path, size=1024, channels=3):
    """A small PNG of a baked array for looking at."""
    step = max(1, arr.shape[0] // size)          # never 0: a bake smaller than the preview
    small = arr[::step, ::step, :].copy()
    if small.shape[2] < 4:
        small = np.concatenate([small, np.ones(small.shape[:2] + (4 - small.shape[2],), np.float32)], axis=2)
    if channels == 1:
        small[..., 1] = small[..., 0]
        small[..., 2] = small[..., 0]
    small[..., 3] = 1.0
    img = bpy.data.images.new('wf_preview', small.shape[1], small.shape[0], alpha=False)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(np.clip(small, 0.0, 1.0).astype(np.float32).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def inward(normal, cover):
    """The share of the covered texels whose baked normal points INTO the game mesh (its blue under one half). A face hidden
    against another part does that and nobody sees it; a whole part that does is inside out, and black in any light."""
    cover = np.asarray(cover)
    cover = cover.astype(bool) if cover.ndim == 2 else cover[..., 0].astype(bool)
    blue = np.asarray(normal)[..., 2]
    return float(((blue < 0.5) & cover).sum()) / max(1, int(cover.sum()))


def missed_by_part(lp_objs, missed, reach_px=0.75):
    """Which part the texels whose ray found no detail are on: ([(part name, texels)], owner), the list worst first (parts with
    none are left out), then ('(no part)', texels) for any not on a triangle of the game mesh; owner is an int map like `missed`:
    0 where nothing missed, i + 1 for the i-th entry of the list (the last one, '(no part)', for the rest). `missed`: (h, w) bool, row 0 at v = 0 (maps.process).
    A texel counts for the part whose UV triangle holds its centre, or lies within `reach_px` texels of it (the bake covers a
    texel a triangle only touches); each texel is counted once. Only the triangles whose box holds a missed texel are looked at,
    so the cost follows the misses, not the sheet."""
    from . import uv as UV
    missed = np.asarray(missed, dtype=bool)
    total = int(missed.sum())
    if not total:
        return [], np.zeros(missed.shape, np.int16)
    h, w = missed.shape
    sat = np.zeros((h + 1, w + 1), np.int64)
    sat[1:, 1:] = missed.astype(np.int64).cumsum(0).cumsum(1)
    claimed = np.zeros_like(missed)
    first = np.zeros(missed.shape, np.int32)        # which part claimed a texel, by the order the parts were looked at
    counts = {}
    order = []
    for o in lp_objs:
        if o.type != 'MESH' or UV.UV_NAME not in o.data.uv_layers:
            continue
        mesh = o.data
        mesh.calc_loop_triangles()
        n = len(mesh.loop_triangles)
        if not n:
            continue
        loops = np.empty(n * 3, np.int64)
        mesh.loop_triangles.foreach_get('loops', loops)
        uvs = np.empty(len(mesh.loops) * 2, np.float32)
        mesh.uv_layers[UV.UV_NAME].data.foreach_get('uv', uvs)
        tri = uvs.reshape(-1, 2)[loops].reshape(n, 3, 2).astype(np.float64) * np.array([w, h], np.float64)
        x0 = np.clip(np.floor(tri[..., 0].min(axis=1) - reach_px).astype(np.int64), 0, w)
        x1 = np.clip(np.ceil(tri[..., 0].max(axis=1) + reach_px).astype(np.int64), 0, w)
        y0 = np.clip(np.floor(tri[..., 1].min(axis=1) - reach_px).astype(np.int64), 0, h)
        y1 = np.clip(np.ceil(tri[..., 1].max(axis=1) + reach_px).astype(np.int64), 0, h)
        inbox = sat[y1, x1] - sat[y0, x1] - sat[y1, x0] + sat[y0, x0]
        got = 0
        for i in np.nonzero(inbox > 0)[0]:
            ys, xs = np.nonzero(missed[y0[i]:y1[i], x0[i]:x1[i]] & ~claimed[y0[i]:y1[i], x0[i]:x1[i]])
            if not len(xs):
                continue
            ys, xs = ys + y0[i], xs + x0[i]
            p = np.stack([xs + 0.5, ys + 0.5], axis=1)
            a, b, c = tri[i]
            area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if abs(area) < 1.0e-12:
                continue
            sign = 1.0 if area > 0 else -1.0
            inside = np.ones(len(xs), bool)
            for u, v in ((a, b), (b, c), (c, a)):
                length = max(float(np.hypot(v[0] - u[0], v[1] - u[1])), 1.0e-12)
                dist = sign * ((v[0] - u[0]) * (p[:, 1] - u[1]) - (v[1] - u[1]) * (p[:, 0] - u[0])) / length      # texels, inside > 0
                inside &= dist >= -reach_px
            if inside.any():
                claimed[ys[inside], xs[inside]] = True
                first[ys[inside], xs[inside]] = len(order) + 1
                got += int(inside.sum())
        order.append(o.name)
        if got:
            counts[o.name] = counts.get(o.name, 0) + got
    out = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    rank = {name: i + 1 for i, (name, _n) in enumerate(out)}
    owner = np.zeros(missed.shape, np.int16)
    for k, name in enumerate(order):
        owner[first == k + 1] = rank.get(name, 0)
    rest = total - int(claimed.sum())
    if rest > 0:
        out.append(('(no part)', rest))
        owner[missed & ~claimed] = len(out)
    return out, owner


MISSED_COLOURS = ((1.0, 0.15, 0.15), (0.2, 0.9, 0.2), (0.25, 0.45, 1.0), (1.0, 0.85, 0.1), (1.0, 0.3, 1.0), (0.1, 0.9, 0.95),
                  (1.0, 0.55, 0.1), (0.6, 0.35, 1.0), (0.6, 1.0, 0.4), (0.9, 0.5, 0.5), (0.4, 0.7, 0.6), (0.7, 0.7, 0.3))
MISSED_NAMES = ('red', 'green', 'blue', 'yellow', 'magenta', 'cyan', 'orange', 'violet', 'lime', 'pink', 'teal', 'olive')


def missed_picture(owner, parts, size=2048):
    """The picture bake/preview_missed.png: each missed texel in the colour of the part it is on (the worst part first in
    MISSED_COLOURS; parts beyond the twelfth, and texels on no part, are white), pooled to `size` as preview() does. Returns
    (rgb float array, legend text)."""
    step = max(1, owner.shape[0] // size)
    if owner.shape[0] % step == 0 and owner.shape[1] % step == 0:
        # the worst-ranked part present in a block wins (the lowest non-zero index), so a part with few misses is still seen
        big = np.where(owner > 0, owner.astype(np.int32), 1 << 20)
        pooled = big.reshape(owner.shape[0] // step, step, owner.shape[1] // step, step).min(axis=(1, 3))
        pooled = np.where(pooled == 1 << 20, 0, pooled)
    else:
        pooled = owner.astype(np.int32)
    rgb = np.zeros(pooled.shape + (3,), np.float32)
    legend = []
    for i, (name, _n) in enumerate(parts):
        colour = MISSED_COLOURS[i] if i < len(MISSED_COLOURS) and name != '(no part)' else (1.0, 1.0, 1.0)
        rgb[pooled == i + 1] = colour
        if i < len(MISSED_COLOURS) and name != '(no part)':
            legend.append('%s %s' % (name, MISSED_NAMES[i]))
        elif name == '(no part)':
            legend.append('(no part) white')
    if len(parts) > len(MISSED_COLOURS):
        legend.append('the rest white')
    return rgb, ', '.join(legend)



def run_bake(weapon, lp_objs, hp_objs, size, gpu=True):
    """The whole detail bake: bake, clean (maps.process), and write normal / masks / id / cover .npy with small previews.
    Returns {'missed': share of covered texels no ray reached, 'seconds'}."""
    t0 = time.time()
    setup_cycles(32, gpu=gpu)
    raw = bake_all(weapon, lp_objs, hp_objs, size)
    out = maps.process(raw, pad=max(8, size // 170), log=log)
    folder = weapon.bake_dir
    os.makedirs(folder, exist_ok=True)
    np.save(os.path.join(folder, 'normal.npy'), out['normal'].astype(np.float16))
    np.save(os.path.join(folder, 'masks.npy'), (np.clip(out['masks'], 0, 1) * 255.0 + 0.5).astype(np.uint8))
    np.save(os.path.join(folder, 'id.npy'), (np.clip(out['id'], 0, 1) * 255.0 + 0.5).astype(np.uint8))
    np.save(os.path.join(folder, 'cover.npy'), out['cover'])
    m = out['masks']
    preview(out['normal'], os.path.join(folder, 'preview_normal.png'), 2048)
    preview(np.stack([m[..., 0]] * 3, axis=2), os.path.join(folder, 'preview_ao.png'), 2048)
    preview(np.stack([m[..., 1], m[..., 2], m[..., 3]], axis=2), os.path.join(folder, 'preview_curv.png'), 2048)
    preview(out['id'], os.path.join(folder, 'preview_id.png'), 2048)
    # where no ray found the detail: those texels have no surface kind, so they take the base look (the check reads the share)
    missed = np.asarray(out['missed'])
    share = float(missed.sum()) / max(1, int(np.asarray(out['cover']).sum()))
    # each missed texel in the colour of the part it is on (the picture's legend is in the log and in bake.json)
    by_part, owner = missed_by_part(lp_objs, missed)
    if by_part:
        picture, legend = missed_picture(owner, by_part)
    else:
        picture, legend = np.zeros(missed.shape[:1] + missed.shape[1:] + (3,), np.float32), ''
    preview(picture, os.path.join(folder, 'preview_missed.png'), 2048)
    if by_part:
        log('rays that found no detail, by part (worst first): ' + ', '.join(
            '%s %d (%.1f%%)' % (name, n, 100.0 * n / max(1, int(missed.sum()))) for name, n in by_part[:12])
            + (' and %d more' % (len(by_part) - 12) if len(by_part) > 12 else ''))
        log('bake/preview_missed.png: ' + legend)
    turned = inward(out['normal'], out['cover'])
    log('covered texels whose normal points into the game mesh: %.2f%%' % (turned * 100))
    # the lettering mask: one channel per ink. A weapon without lettering has no such file (and an old one is removed)
    marks = np.clip(raw['marks'][..., :3], 0.0, 1.0)
    marks_path = os.path.join(folder, 'marks.npy')
    lettered = float((marks.max(axis=2) > 0.25).sum()) / max(1, int(np.asarray(out['cover']).sum()))
    if lettered > 0.0:
        np.save(marks_path, (marks * 255.0 + 0.5).astype(np.uint8))
        preview(marks, os.path.join(folder, 'preview_marks.png'), 2048)
        log('lettering: %.3f%% of the drawn texels (bake/preview_marks.png)' % (lettered * 100))
    else:
        for stale in (marks_path, os.path.join(folder, 'preview_marks.png')):
            if os.path.isfile(stale):
                os.remove(stale)
    with open(os.path.join(folder, 'bake.json'), 'w') as fh:
        json.dump({'size': size, 'missed': round(share, 5), 'inward': round(turned, 5), 'lettering': round(lettered, 6),
                   'extrusion_cm': CAGE_EXTRUSION, 'max_ray_cm': MAX_RAY,
                   'missed_by_part': [[name, n] for name, n in by_part]}, fh)
    seconds = time.time() - t0
    with open(os.path.join(folder, 'DONE.txt'), 'w') as fh:
        fh.write('size %d, %.1fs\n' % (size, seconds))
    log('all done in %.1fs' % seconds)
    return {'size': size, 'seconds': round(seconds, 1), 'covered': round(float(np.asarray(out['cover']).mean()), 4),
            'missed': round(share, 5), 'inward': round(turned, 5)}
