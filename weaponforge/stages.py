"""weaponforge: the pipeline, one function per stage. Each works on the open .blend and takes the weapon (weapon.load).

    model    build every part twice from the weapon's builders: <TAG>_LP (the game mesh) and <TAG>_HP (the bake source)
    uv       clean and triangulate the game parts, set hard edges and normals, unwrap, pack onto one sheet
    bake     high detail -> normal / occlusion / material ID / curvature masks        (files in <asset>/bake)
    texture  the weapon's surface over the bakes -> T_<Name>_BC / _N / _ORM           (files in <asset>/textures)
    rig      pivots, armature with socket joints, SKM_ / SM_ / prop meshes and their LODs, in <TAG>_GAME
    check    every automatic check, measured on the meshes
    export   check, write the FBX files and the spec (<id>.json)
    render   review sheets to look at                                                (files in <asset>/renders)
    verify   read the FBX files back in an empty scene and compare with the spec (EMPTIES THE SCENE: last, after saving)

A stage needs the ones before it, and re-running one makes the later ones stale: rebuild a game part and the UVs, the bakes, the
textures and the rig all have to follow (rebuild only the high-detail parts and it is the bakes onward). export() refuses a
stale chain, and one with a stage left out.

From a shell, bin/weaponforge runs these headless. In a live Blender (its Python console, or a script):

    import sys; sys.path.insert(0, '/path/to/weaponforge')          # the repository: bin/, weaponforge/, weapons/
    from weaponforge import stages, weapon
    w = weapon.load('_template', reload=True)
    stages.model(w, only=['slide'])
"""
import json
import math
import os
import time
import traceback

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

from . import bake as B
from . import check as CHK
from . import kit as K
from . import rig as R
from . import surface as S
from . import uv as U
from . import view as V

ORDER = ('model', 'uv', 'bake', 'texture', 'rig')      # the chain export() checks
NEEDS = {'uv': ('model',), 'bake': ('model', 'model_hp', 'uv'), 'texture': ('bake',), 'rig': ('model', 'uv', 'texture')}
#        what each stage is made from. 'model' is stamped when game parts are built, 'model_hp' when high-detail parts are.
ALL = ('model', 'uv', 'bake', 'texture', 'rig', 'check', 'export', 'render', 'verify')
RENDERS = ('grey', 'look', 'game', 'poses', 'eyes')
STAMPS = 'wf_stamps'


def log(*a):
    print('[weaponforge]', *a, flush=True)


# ---------------------------------------------------------------------------------------------------------------- state
def parts(weapon, kind='LP'):
    """The mesh objects of the weapon's LP or HP collection, by name."""
    coll = bpy.data.collections.get(weapon.coll(kind))
    if coll is None:
        return []
    return sorted((o for o in coll.objects if o.type == 'MESH'), key=lambda o: o.name)


def _need(weapon, kind, stage):
    objs = parts(weapon, kind)
    if not objs:
        raise RuntimeError('%s is empty: run the stage "%s" first' % (weapon.coll(kind), stage))
    return objs


def _stamps():
    try:
        return json.loads(bpy.context.scene.get(STAMPS, '{}'))
    except (TypeError, ValueError):
        return {}


def _stamp(stage):
    """Record that a stage ran now, after everything recorded so far."""
    stamps = _stamps()
    stamps[stage] = max(stamps.values(), default=0) + 1
    bpy.context.scene[STAMPS] = json.dumps(stamps)


def stale_by_stage():
    """{stage: why} for every stage of the chain that is older than something it is made from (NEEDS), or was made from one that is
    stale itself, in the chain's order. Empty when the chain is in order (or in a file made before stamps existed, which cannot
    tell)."""
    stamps = _stamps()
    out = {}
    for stage in ORDER:
        if stage not in stamps:
            continue
        for need in NEEDS.get(stage, ()):
            if need in out:
                out[stage] = '"%s" was made from a stale "%s"' % (stage, need)
            elif need in stamps and stamps[need] > stamps[stage]:
                out[stage] = '"%s" is older than the latest "%s"' % (stage, 'model --hp-only' if need == 'model_hp' else need)
            else:
                continue
            break
    return out


def stale(weapon=None):
    """What has to be re-run, as text: ['"uv" is older than the latest "model"', ...]. A stage is stale when something it is made
    from (NEEDS) ran after it, or is stale itself. Empty when the chain is in order (or in a file made before stamps existed,
    which cannot tell)."""
    return list(stale_by_stage().values())


def skipped():
    """The stages of the chain that never ran in this file, when it is a file this tool started (its "model" stamp exists). A file
    from before the tool (the first pistol's) has no such stamp and cannot tell: []."""
    stamps = _stamps()
    return [s for s in ORDER if s not in stamps] if 'model' in stamps else []


# ---------------------------------------------------------------------------------------------------------------- model
def _name(obj, kind, coll):
    """A game part keeps the name its builder gave it (the checks and the weapon's hooks find parts by name); the high-detail
    twin is <name>_HP. Blender would otherwise call whichever was built second <name>.001."""
    base = obj.name.rsplit('.', 1)[0] if obj.name.rsplit('.', 1)[-1].isdigit() else obj.name
    if kind == 'HP':
        want = base + '_HP'
    else:
        want = base
        holder = bpy.data.objects.get(base)
        if holder is not None and holder is not obj:
            if holder.name in coll.objects:
                raise RuntimeError('two game parts are both called %s: give each builder\'s object its own name' % base)
            holder.name = base + ('_HP' if holder.get('builder') and holder.users_collection and holder.users_collection[0].name.endswith('_HP')
                                  else '_old')
    obj.name = want
    obj.data.name = want


def model(weapon, only=None, lp=True, hp=True, quiet=False):
    """Build (or rebuild the named builders of) the game parts and the bake source. Returns {'LP': {builder: [objects]}, 'HP': ...}.
    Every builder is tried; if any fails the stage raises at the end, naming them all."""
    K.setup_scene()
    todo = weapon.builders()
    if only:
        unknown = [k for k in only if k not in todo]
        if unknown:
            raise KeyError('no such builder: %s (have %s)' % (', '.join(unknown), ', '.join(todo)))
        todo = {k: v for k, v in todo.items() if k in only}
    made, failed = {}, []
    bone_names = {name for name, _parent, _pos in weapon.bones}
    kinds = B.kinds_of(weapon)
    for kind, wanted in (('LP', lp), ('HP', hp)):
        if not wanted:
            continue
        coll = K.collection(weapon.coll(kind))
        # copies of the lettering cut into the bake source (kit.keep_mark), for the bake's lettering mask
        sink = K.collection(weapon.coll('MARKS')) if kind == 'HP' else None
        made[kind] = {}
        t0 = time.time()
        for key, fn in todo.items():
            t = time.time()
            for old in [o for o in coll.objects if o.get('builder') == key]:
                K.remove(old)
            for old in [o for o in (sink.objects if sink else ()) if o.get('builder') == key]:
                K.remove(old)
            before = set(coll.objects)
            kept = set(sink.objects) if sink else set()
            K.MARK_SINK = sink
            try:
                fn(coll, kind == 'HP')
            except Exception:
                log('FAILED %s (%s)' % (key, kind))
                traceback.print_exc()
                failed.append('%s (%s)' % (key, kind))
                for o in set(coll.objects) - before:
                    K.remove(o)
                for o in (set(sink.objects) - kept) if sink else ():
                    K.remove(o)
                continue
            finally:
                K.MARK_SINK = None
            for o in (set(sink.objects) - kept) if sink else ():
                o['builder'] = key
            new = [o for o in coll.objects if o not in before]
            try:
                for o in new:
                    _name(o, kind, coll)
                    o['builder'] = key
            except RuntimeError as e:
                log('FAILED %s (%s): %s' % (key, kind, e))
                failed.append('%s (%s): %s' % (key, kind, e))
                for o in new:
                    K.remove(o)
                continue
            for o in new:
                if 'bone' not in o.keys():
                    failed.append('%s (%s): left the untagged object %s (kit.tag every part; remove the cutters)' % (key, kind, o.name))
                elif o['bone'] not in bone_names:
                    failed.append('%s (%s): %s is tagged for bone %r, which the weapon does not define (have %s)'
                                  % (key, kind, o.name, o['bone'], ', '.join(sorted(bone_names))))
                elif kind == 'HP':
                    odd = [k for k in weapon.hp_kinds(o) if k not in kinds]
                    if odd:
                        failed.append('%s (HP): %s is of the surface kind %s, which is not one of %s' % (key, o.name, odd, ', '.join(kinds)))
            made[kind][key] = new
            if not quiet:
                log('%-3s %-14s %-24s tris %7d  %.1fs' % (kind, key, ','.join(o.name for o in new), sum(K.tri_count(o) for o in new), time.time() - t))
        V.colour_parts(coll.objects, weapon.palette)
        objs = [o for o in coll.objects if o.type == 'MESH']
        if objs and not quiet:
            lo, hi = K.bounds(objs)
            log('%s: %d parts, %d triangles, bounds %s .. %s, %.1fs' % (weapon.coll(kind), len(objs), sum(K.tri_count(o) for o in objs),
                                                                    [round(v, 2) for v in lo], [round(v, 2) for v in hi], time.time() - t0))
    if failed:
        raise RuntimeError('builders failed: ' + '; '.join(failed))
    if lp:
        _stamp('model')
    if hp:
        _stamp('model_hp')
    return made


# ------------------------------------------------------------------------------------------------------------------- uv
def uv(weapon):
    """Finish the game parts (weld, triangulate, drop the slivers Unreal would, hard edges, weighted normals), unwrap, pack.
    Returns the sheet's stats; writes a picture of it to <asset>/textures/work/uv_layout.png."""
    lp = _need(weapon, 'LP', 'model')
    report, stats = U.layout(lp, weapon.uv_margin, weapon.density, weapon.seams, how=weapon.uv_pack, weapon=weapon, log=log)
    for name, (patches, recut, picked, where, bad) in sorted(report.items()):
        log('%-16s %4d patches, %3d recut for stretch, %3d seam edges of its own, %d open edges' % (name, patches, recut, picked, bad))
        for line in where:              # a patch cut up by angle: where a seam of the weapon's own (Weapon.seams) would do better
            log('%-16s      recut: %s' % ('', line))
    leaks = {name: r[4] for name, r in report.items() if r[4]}
    os.makedirs(weapon.work_dir, exist_ok=True)
    U.export_layout(lp, os.path.join(weapon.work_dir, 'uv_layout.png'))
    log('sheet: %s' % stats)
    if leaks:
        log('WARNING open edges (the mesh is not closed there; see PLAYBOOK.md, "Mesh repair"): %s' % leaks)
    _stamp('uv')
    return stats


# ----------------------------------------------------------------------------------------------------------------- bake
def bake(weapon, size=None, gpu=True):
    """The detail bake at `size` (default: the weapon's texture size). Minutes at 4K: run it headless, not in a live session."""
    lp = _need(weapon, 'LP', 'model')
    hp = _need(weapon, 'HP', 'model')
    missing = [o.name for o in lp if U.UV_NAME not in o.data.uv_layers]
    if missing:
        raise RuntimeError('no UVs on %s: run the stage "uv" first' % ', '.join(missing))
    B.unhide([bpy.data.collections[weapon.coll('LP')], bpy.data.collections[weapon.coll('HP')]])
    out = B.run_bake(weapon, lp, hp, size or weapon.texture_size, gpu=gpu)
    _stamp('bake')
    return out


# -------------------------------------------------------------------------------------------------------------- texture
def texture(weapon, size=None, gpu=True):
    """Build the weapon's authoring material over the bakes and bake it down to the game's three textures."""
    lp = _need(weapon, 'LP', 'model')
    size = size or weapon.texture_size
    images = S.load_maps(weapon)
    mat = S.build(weapon, images)
    S.assign(lp, mat)                                        # the parts keep it, for look-dev renders
    B.unhide([bpy.data.collections[weapon.coll('LP')]])
    tmp_coll = K.collection(weapon.coll('TMP'))
    try:
        tmp = R._join_copies('wf_texture_target', lp, tmp_coll, groups=False)
        B.setup_cycles(4, gpu=gpu)
        tex = S.bake_textures(tmp, mat, size, log=log)
    finally:
        K.wipe(tmp_coll)
        bpy.data.collections.remove(tmp_coll)
    paths = S.write_game_textures(weapon, tex, log=log)
    S.game_material(weapon)
    _stamp('texture')
    return paths


# ------------------------------------------------------------------------------------------------------------------ rig
def rig(weapon):
    """Pivots onto the bones, then the armature and every exported mesh into <TAG>_GAME. Returns the game dict (rig.find)."""
    lp = _need(weapon, 'LP', 'model')
    R.pivots(weapon, lp)
    mat = S.game_material(weapon)
    if any(n.type == 'TEX_IMAGE' and n.image is None for n in mat.node_tree.nodes):
        log('WARNING the textures are not on disk yet (stage "texture"): the game meshes carry an empty %s' % mat.name)
    game = R.build(weapon, lp, mat)
    log('%s %d triangles; LODs %s; props %s' % (game['skm'].name, K.tri_count(game['skm']), [K.tri_count(o) for o in game['lods']],
                                               {k: K.tri_count(o) for k, o in game['props'].items()}))
    _stamp('rig')
    return game


# ---------------------------------------------------------------------------------------------------------------- check
def _cover(weapon):
    path = os.path.join(weapon.bake_dir, 'cover.npy')
    return np.load(path) if os.path.isfile(path) else None


def _bake_info(weapon):
    """What the last bake wrote about itself (bake.json). A bake older than that record has no count of the rays that found
    nothing; which way its normals point is read off the saved normal map, so that check runs for every baked weapon.
    None when there is no bake."""
    path = os.path.join(weapon.bake_dir, 'bake.json')
    info = {}
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as fh:
            info = json.load(fh)
    if 'inward' not in info:
        normal, cover = os.path.join(weapon.bake_dir, 'normal.npy'), os.path.join(weapon.bake_dir, 'cover.npy')
        if os.path.isfile(normal) and os.path.isfile(cover):
            info['inward'] = round(B.inward(np.load(normal, mmap_mode='r'), np.load(cover)), 5)
    return info or None


def check(weapon):
    """Run every check and return the report. Before the rig exists only the mesh and UV checks run.

    A stage that is older than the model (stale_by_stage) is not measured: its files were made from parts that are no longer
    there, so what they say (the UVs, the rig's triangle count, the bake's coverage and the figures read from it) is no miss of the
    current model. Each such stage is named in the log and what depends on it is left out, with "model" and a current stage held to
    every check as before: a stage that is current and fails still misses, and `--strict` still exits 1 on it. `export` is not
    this: it refuses a stale chain."""
    lp = _need(weapon, 'LP', 'model')
    old = stale_by_stage()
    game, cover, info = R.find(weapon), _cover(weapon), _bake_info(weapon)
    if 'rig' in old:
        game = None                          # the old rig's meshes: the Checker then says "not measured yet", as before a rig
    if 'bake' in old or 'uv' in old:
        cover, info = None, None             # the old bake's coverage and rays
    report = CHK.run(weapon, lp, game, cover, log=log, bake=info)
    if 'bake' in old:
        # the figures and the notes about the looks read the bake files themselves: counted against parts they were not baked from
        gone = [r for r in report if r['check'].startswith('review: ')]
        report = [r for r in report if r not in gone]
        for r in gone:
            log('%-4s %-30s not counted: the bake is older than the model' % ('--', r['check']))
    text = CHK.summary(report)
    if old:
        text += '; stale, not measured: %s (re-run from "%s")' % (', '.join(old), next(iter(old)))
        for stage, why in old.items():
            log('%-4s %-30s %s: not counted as a miss of the current model' % ('--', 'stale: ' + stage, why))
    log(text)
    return report


# --------------------------------------------------------------------------------------------------------------- export
def export(weapon, force=False):
    """Check, write the FBX files and the spec. Refuses a chain that is stale (a stage older than what it is made from) or
    incomplete (a stage that never ran, parts without UVs, textures not on disk); force=True writes anyway."""
    lp = _need(weapon, 'LP', 'model')
    game = R.find(weapon)
    if game is None:
        raise RuntimeError('no game meshes in %s: run the stage "rig" first' % weapon.coll('GAME'))
    old = stale()
    if old and not force:
        raise RuntimeError('stale: %s. Re-run from the first of them.' % '; '.join(old))
    gaps = ['the stage "%s" never ran in this file' % s for s in skipped()]
    bare = [o.name for o in lp if U.UV_NAME not in o.data.uv_layers]
    if bare:
        gaps.append('no UVs on %s (stage "uv")' % ', '.join(bare))
    absent = [n for n in ('%s_%s.png' % (weapon.tex_prefix, sfx) for sfx in ('BC', 'N', 'ORM')) if not os.path.isfile(os.path.join(weapon.tex_dir, n))]
    if absent:
        gaps.append('%s not in %s (stages "bake" and "texture")' % (', '.join(absent), weapon.tex_dir))
    if gaps and not force:
        raise RuntimeError('incomplete: %s. An export now would be a weapon without them; run what is missing, then "rig" again.'
                           % '; '.join(gaps))
    report = CHK.run(weapon, lp, game, _cover(weapon), log=log, bake=_bake_info(weapon))
    log(CHK.summary(report))
    files = R.export_all(weapon, game)
    textures = None
    names = {key: '%s_%s.png' % (weapon.tex_prefix, suffix) for key, suffix in (('base_colour', 'BC'), ('normal', 'N'), ('orm', 'ORM'))}
    if all(os.path.isfile(os.path.join(weapon.tex_dir, n)) for n in names.values()):
        size = bpy.data.images.load(os.path.join(weapon.tex_dir, names['base_colour']), check_existing=True).size[0]
        textures = {'dir': weapon.tex_dir, 'size': size, 'files': names,
                    'conventions': 'BC sRGB; N is OpenGL (green up) on disk, flipped at import (the Unreal adapter sets flip green); '
                                   'ORM is R occlusion, G roughness, B metallic, linear',
                    'material_slot': '%s (one slot on every mesh)' % weapon.mat_game}
    status = None
    if os.path.isfile(weapon.spec_path):               # the status line belongs to whoever imported or wired the weapon: keep it
        try:
            with open(weapon.spec_path, 'r', encoding='utf-8') as fh:
                status = json.load(fh).get('status')
        except (OSError, ValueError):
            status = None
    spec = R.spec(weapon, game, U.stats(lp), textures, report, status)
    if CHK.LAST_FIGURES is not None:                  # the review figures of the check just run (check.Checker.review)
        from . import review as RV
        figs = {k: v for k, v in CHK.LAST_FIGURES.items() if k != 'seconds'}      # timing would change the spec every export
        spec['review'] = {'figures': json.loads(json.dumps(figs, default=RV._plain)), 'held_by': weapon.review,
                          'limits': {k: list(v) for k, v in RV.limits(weapon).items()}}
    path = R.write_spec(spec, weapon.spec_path)
    for key, value in files.items():
        log('wrote %s' % value)
    log('wrote %s' % path)
    return {'files': files, 'spec': path, 'checks': report}


# --------------------------------------------------------------------------------------------------------------- render
CLOSE_VIEWS = ('left', 'right', 'q_rear_r', 'fp')
EYES_W = 1440          # px: the eye sheets' tiles are this wide and 16:9 (the game's frame): 810 high


def _long(objs):
    """A long gun: its sheets are laid out wide, or the weapon is a thin line across a pistol's tile."""
    lo, hi = K.bounds(objs)
    return (hi.x - lo.x) > 3.0 * max(hi.z - lo.z, hi.y - lo.y, 1.0e-6)


def eyes(weapon, objs):
    """({'fp': (eye, look), 'ads': (eye, look)}, the middle of the parts) in the weapon frame, cm: the player's own cameras
    (hero.player_eyes, the ones the hero pictures and the review's figures are taken from) for the weapon's length. The sheets that
    look from the hip eye's side, and the sheet of what the eyes see, are made from this one place."""
    from . import hero
    lo, hi = K.bounds(objs)
    return hero.player_eyes(weapon, max(hi.x - lo.x, hi.y - lo.y) / 100.0), (lo + hi) / 2


def _sided(views, where):
    """views with the name 'fp' (the hip eye's side) turned into the direction from the model's middle to the hip eye, which is the
    side and height the player looks from. It used to be a fixed direction on the weapon's right; the hero picture is on its left."""
    if where is None:
        return list(views)
    hip = where[0]['fp'][0] - where[1]
    return [tuple(hip) if v == 'fp' else v for v in views]


def _closeups(weapon):
    """[(name, ((lo), (hi)), [views])] from Weapon.closeups."""
    return [(name, (box[0], box[1]), list(box[2]) if len(box) > 2 else list(CLOSE_VIEWS)) for name, box in weapon.closeups.items()]


def _posed(weapon, moves):
    """{bone: 4x4} where each bone carries its parts in a pose. It is what rig.pose does to the armature, for parts that have no
    rig yet: every rest axis is the weapon's own, so a bone's change is about its head, in the weapon's frame."""
    out = {}
    for name, parent, pos in weapon.bones:              # parents come first (validate)
        change = (moves or {}).get(name, {})
        head = Matrix.Translation(Vector(pos))
        s = change.get('scale', 1.0)
        local = (Matrix.Translation(Vector(change.get('loc', (0.0, 0.0, 0.0))))
                 @ Euler([math.radians(a) for a in change.get('rot', (0.0, 0.0, 0.0))], 'XYZ').to_matrix().to_4x4()
                 @ Matrix.Diagonal((s, s, s, 1.0)))
        out[name] = (out[parent] if parent else Matrix.Identity(4)) @ head @ local @ head.inverted()
    return out


def _grey_poses(weapon, folder, label, objs, res, rig=None):
    """The parts in each of the weapon's poses, before there is a rig: the concept and the high-detail model are judged with the
    action open, not only closed."""
    out = []
    region = tuple(weapon.closeups[weapon.pose_closeup][:2]) if weapon.pose_closeup else None
    rest = [(o, o.matrix_world.copy()) for o in objs]
    try:
        for name, moves in weapon.poses.items():
            if not moves:
                continue
            where = _posed(weapon, moves)
            for o, m in rest:
                o.matrix_world = where[o['bone']] @ m if o.get('bone') in where else m
            bpy.context.view_layer.update()
            out.append(V.shots(folder, '%s_pose_%s' % (label, name), _sided(weapon.pose_views, rig), objs, res=res, cols=2, region=region))
    finally:
        for o, m in rest:
            o.matrix_world = m
        bpy.context.view_layer.update()
    return out


def render(weapon, what=None, samples=64, res=(1400, 900)):
    """Review sheets in <asset>/renders. what: any of 'grey' (the game and high-detail parts, flat colours), 'look' (the parts
    with the authoring material), 'game' (the exported mesh with the written textures), 'poses' (the rig in each of the
    weapon's poses), 'eyes' (the grey sheets' two pictures from the player's own cameras alone: `grey` makes them too).
    Default: everything the file has got as far as. Returns the paths.

    A long gun (over three times as long as it is high) gets wide tiles in one column, with the angled views of the grey
    sheets on a sheet of their own (<sheet>_angles); every box in Weapon.closeups adds a sheet framed on it (<sheet>_<name>).
    The grey sheets also show the parts in each of the weapon's poses (<sheet>_pose_<pose>), which needs no rig.
    <sheet>_eyes (grey_game_parts_eyes, grey_high_detail_eyes) is the model as the player's hip and aiming eyes see it: the very
    cameras `hero --shots fp,ads` takes its pictures from (hero.player_eyes, 60 degrees across, 16:9), so it needs no export. Every
    view called 'fp' in any sheet looks from the side of that hip eye (the weapon's left)."""
    out = []
    folder = weapon.render_dir
    lp, hp, game = parts(weapon, 'LP'), parts(weapon, 'HP'), R.find(weapon)
    views = ['left', 'right', 'top', 'q_front_l', 'q_rear_r', 'fp']
    unknown = [w for w in (what or ()) if w not in RENDERS]
    if unknown:
        raise ValueError('render: no such sheet: %s (have %s)' % (', '.join(unknown), ', '.join(RENDERS)))
    wanted = set(what or RENDERS)
    small = (max(320, res[0] * 2 // 3), max(220, res[1] * 2 // 3))
    where = eyes(weapon, lp or hp) if (lp or hp) else None     # the game parts are what the eyes are placed by, for every sheet
    closeups = [(name, region, _sided(close, where)) for name, region, close in _closeups(weapon)]
    if wanted & {'grey', 'eyes'}:
        for label, objs in (('grey_game_parts', lp), ('grey_high_detail', hp)):
            if not objs:
                continue
            if 'grey' in wanted:
                if _long(objs):
                    out.append(V.shots(folder, label, ['left', 'right', 'top'], objs, res=(res[0], res[0] * 3 // 10), cols=1))
                    out.append(V.shots(folder, label + '_angles', _sided(['q_front_l', 'q_rear_r', 'fp'], where), objs,
                                       res=(res[0], res[0] // 2), cols=1))
                else:
                    out.append(V.shots(folder, label, _sided(views, where), objs, res=small, cols=2))
                for name, region, close in closeups:
                    out.append(V.shots(folder, '%s_%s' % (label, name), close, objs, res=small, cols=2, region=region))
                out += _grey_poses(weapon, folder, label, objs, small, where)
            out.append(V.eye_shots(folder, label + '_eyes', where[0], objs, res=(EYES_W, EYES_W * 9 // 16), log=log))
    author = bpy.data.materials.get(weapon.mat_author)
    lit = wanted & {'look', 'game', 'poses'}
    if lit and (author is not None or game is not None):
        B.setup_cycles(samples, gpu=True)
        S.studio(weapon)
    if 'look' in wanted and lp:
        if author is None:
            log('look: no authoring material yet (the stage "texture" builds it); sheet skipped')
        else:
            # the stage "rig" leaves the game material on the parts: the authoring one goes on for this sheet only
            before = [list(o.data.materials) for o in lp]
            S.assign(lp, author)
            try:
                if _long(lp):                           # a long gun: the whole length from each side, in wide tiles
                    out.append(S.beauty(folder, 'look_authoring', ['left', 'right', 'q_front_l', 'q_rear_r'], lp,
                                        res=(res[0], res[0] * 2 // 5), cols=1, samples=samples))
                else:
                    out.append(S.beauty(folder, 'look_authoring', ['q_front_l', 'q_rear_r'], lp, res=res, cols=1, samples=samples))
                for name, region, close in closeups:
                    out.append(S.beauty(folder, 'look_%s' % name, close, lp, res=small, cols=2, samples=samples, region=region))
            finally:
                for o, mats in zip(lp, before):
                    o.data.materials.clear()
                    for m in mats:
                        o.data.materials.append(m)
    if game is not None and ('game' in wanted or 'poses' in wanted):
        R.pose(game['armature'])
        wide = _long([game['skm']])
        if 'game' in wanted:
            if wide:
                out.append(S.beauty(folder, 'final_views', _sided(['left', 'right', 'q_front_l', 'fp'], where), [game['skm']],
                                    res=(res[0], res[0] * 2 // 5), cols=1, samples=samples))
            else:
                out.append(S.beauty(folder, 'final_views', _sided(['left', 'right', 'q_front_l', 'fp'], where), [game['skm']], res=res, cols=2,
                                    samples=samples))
            for name, region, close in closeups:
                out.append(S.beauty(folder, 'final_%s' % name, close, [game['skm']], res=small, cols=2, samples=samples, region=region))
            for suffix, obj in game['props'].items():
                out.append(S.beauty(folder, 'final_prop_%s' % suffix.lower(), ['q_front_l', 'q_rear_r'], [obj], res=(res[0] // 2, res[1] // 2),
                                    cols=2, samples=samples))
        if 'poses' in wanted:
            # a pose is about the moving parts: frame it on Weapon.pose_closeup when the weapon names one
            region = tuple(weapon.closeups[weapon.pose_closeup][:2]) if weapon.pose_closeup else None
            try:
                for name, moves in weapon.poses.items():
                    if not moves:
                        continue
                    R.pose(game['armature'], moves)
                    out.append(S.beauty(folder, 'pose_%s' % name, _sided(weapon.pose_views, where), [game['skm']], res=(res[0] * 2 // 3, res[1] * 2 // 3),
                                        cols=2, samples=samples, region=region))
            finally:
                R.pose(game['armature'])
    for path in out:
        log('wrote %s' % path)
    return out


# --------------------------------------------------------------------------------------------------------------- verify
def verify(weapon):
    """Read every exported FBX back into an empty scene and compare it with the spec. EMPTIES THE SCENE: save first, and never in
    a live session with work open (bin/weaponforge <id> verify runs it in its own Blender). Returns the list of problems."""
    from . import verify_fbx
    return verify_fbx.run(weapon.spec_path, weapon.export_dir, log=log)
