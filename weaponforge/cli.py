"""weaponforge: the command line, run inside a headless Blender (bin/weaponforge starts it):

    blender -b --factory-startup --python-exit-code 1 --python cli.py -- <weapon> <stage> [<stage> ...] [options]

Opens <asset root>/<weapon>/<weapon>.blend (or starts an empty file), runs the stages in order, and saves after each one that
changes the file. Exits 1 on the first stage that fails, or when `verify` finds a problem, or when --strict and a check misses.

`view`, `hero` and `review` are not stages: each runs alone, reads the exported files and writes beside the weapons' folders, a
viewer copy (viewer.py), presentation pictures (hero.py) or a review pack (review.py). None of them saves the .blend (`review`
opens it, and the other build's, to measure them).
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.dirname(HERE)
if TOOL not in sys.path:
    sys.path.insert(0, TOOL)

import bpy                                                                # noqa: E402

from weaponforge import kit as K, stages, weapon as W                     # noqa: E402

SAVES = ('model', 'uv', 'bake', 'texture', 'rig')      # the stages that change the .blend


def parse(argv):
    p = argparse.ArgumentParser(prog='weaponforge', description='Build a game weapon from its definition in weapons/<id>/.')
    p.add_argument('weapon', help='the definition folder under weapons/, or "list"')
    p.add_argument('stages', nargs='*', help='any of: %s, all; or alone: "view" (a .glb of the exported weapon, for a browser), "hero" (presentation pictures of it; --shots adds beauty, fp, ads, left, right, outline; --pose NAME puts the weapon in one of its poses), "review" (a review pack: pictures, crops, figures; --against compares)'
                   % ', '.join(stages.ALL))
    p.add_argument('--root', help='another asset root: everything, the spec included, is written under <root>/<weapon>/ (tests)')
    p.add_argument('--blend', help='open and save this .blend instead of <asset root>/<weapon>/<weapon>.blend')
    p.add_argument('--size', type=int, help='bake and texture size in pixels (default: the weapon\'s texture_size); '
                                            'view: the textures\' size in the copy (default: the game textures\' own size, unchanged)')
    p.add_argument('--cpu', action='store_true', help='bake on the CPU')
    p.add_argument('--only', help='model: rebuild only these builders (comma separated)')
    p.add_argument('--lp-only', action='store_true', help='model: only the game parts')
    p.add_argument('--hp-only', action='store_true', help='model: only the high-detail parts')
    p.add_argument('--what', help='render: comma separated from grey, look, game, poses, eyes (default: all the file is ready for). '
                                  'grey includes eyes: the model from the player\'s own hip and aiming cameras; eyes alone makes only those')
    p.add_argument('--samples', type=int, default=64, help='render: Cycles samples')
    p.add_argument('--res', default='1400x900', help='render: tile size, WxH')
    p.add_argument('--shots', help='hero: comma separated from default, beauty, fp, ads, left, right, outline (default: default, '
                                   'the front and rear pictures)')
    p.add_argument('--pose', help='hero: take the pictures with the weapon in this pose (a name from the weapon\'s poses, the ones '
                                  '"render --what poses" shows), as <Name><shot>_pose_<pose>.png; needs the .blend as it was exported')
    p.add_argument('--against', help='review: another build to compare with: its review pack, or its build folder (or an asset '
                                     'root holding <weapon>/)')
    p.add_argument('--out', help='review: write the pack here (default: <assets>/_gallery/review/<Name>/)')
    p.add_argument('--pack-file', help=argparse.SUPPRESS)          # bin/weaponforge: where to write the pack's folder
    p.add_argument('--force', action='store_true', help='export: write even when a stage is stale or was left out')
    p.add_argument('--strict', action='store_true', help='check / export: exit 1 when any check misses')
    p.add_argument('--no-save', action='store_true', help='do not save the .blend')
    # intermixed: a stage name may follow an option (model --lp-only render), which plain parse_args refuses
    return p.parse_intermixed_args(argv)


def main(argv):
    args = parse(argv)
    if args.weapon == 'list':
        for name in W.available():
            print(name)
        return 0
    weapon = W.load(args.weapon, root=args.root)
    for alone in ('view', 'hero', 'review'):
        if alone in args.stages:
            if args.stages != [alone]:
                raise SystemExit('"%s" runs alone: weaponforge %s %s' % (alone, args.weapon, alone))
            given = [a.split('=')[0] for a in argv]
            if args.pose and alone != 'hero':
                raise SystemExit('--pose goes with hero')
            if alone == 'view':
                from weaponforge import viewer
                viewer.make(weapon, size=args.size)
            elif alone == 'review':
                from weaponforge import review
                review.make_pack(weapon, out=args.out, against=args.against, samples=args.samples if '--samples' in given else None,
                                 res=tuple(int(v) for v in args.res.lower().split('x')) if '--res' in given else None,
                                 size=args.size, pack_file=args.pack_file, log=stages.log)
            else:
                from weaponforge import hero
                shots = args.shots.split(',') if args.shots else None
                if shots and [s for s in shots if s not in hero.SHOT_NAMES]:
                    raise SystemExit('--shots takes any of %s, comma separated (got %s)' % (', '.join(hero.SHOT_NAMES), args.shots))
                if args.pose and args.pose not in weapon.poses:
                    raise SystemExit('--pose takes one of %s (got %s)' % (', '.join(weapon.poses), args.pose))
                hero.make(weapon, size=args.size, samples=args.samples if '--samples' in given else None,
                          res=tuple(int(v) for v in args.res.lower().split('x')) if '--res' in given else None, shots=shots,
                          pose=args.pose)
            return 0
    if args.pose:
        raise SystemExit('--pose goes with hero: weaponforge %s hero --pose %s' % (args.weapon, args.pose))
    todo = []
    for name in args.stages or ['check']:
        todo += list(stages.ALL) if name == 'all' else [name]
    unknown = [s for s in todo if s not in stages.ALL]
    if unknown:
        raise SystemExit('unknown stage: %s (have %s, all)' % (', '.join(unknown), ', '.join(stages.ALL)))
    if 'verify' in todo and todo[-1] != 'verify':
        raise SystemExit('"verify" empties the scene: it has to be the last stage')
    what = args.what.split(',') if args.what else None
    if what and [w for w in what if w not in stages.RENDERS]:
        raise SystemExit('--what takes any of %s, comma separated (got %s)' % (', '.join(stages.RENDERS), args.what))

    blend = args.blend or weapon.blend
    if os.path.isfile(blend):
        bpy.ops.wm.open_mainfile(filepath=blend)
        stages.log('opened %s' % blend)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        K.setup_scene()
        stages.log('new file (will be saved as %s)' % blend)
    os.makedirs(os.path.dirname(blend), exist_ok=True)
    res = tuple(int(v) for v in args.res.lower().split('x'))
    gpu = not args.cpu
    status = 0
    for name in todo:
        t = time.time()
        stages.log('---- %s' % name)
        if name == 'model':
            stages.model(weapon, only=args.only.split(',') if args.only else None, lp=not args.hp_only, hp=not args.lp_only)
        elif name == 'uv':
            stages.uv(weapon)
        elif name == 'bake':
            stages.bake(weapon, size=args.size, gpu=gpu)
        elif name == 'texture':
            stages.texture(weapon, size=args.size, gpu=gpu)
        elif name == 'rig':
            stages.rig(weapon)
        elif name == 'check':
            report = stages.check(weapon)
            if args.strict and any(not r['ok'] for r in report):
                status = 1
        elif name == 'export':
            report = stages.export(weapon, force=args.force)['checks']
            if args.strict and any(not r['ok'] for r in report):
                status = 1
        elif name == 'render':
            stages.render(weapon, what=what, samples=args.samples, res=res)
        elif name == 'verify':
            if stages.verify(weapon):
                status = 1
        if name in SAVES and not args.no_save:
            bpy.ops.wm.save_as_mainfile(filepath=blend, check_existing=False)
            stages.log('saved %s' % blend)
        stages.log('---- %s done in %.1fs' % (name, time.time() - t))
    return status


if __name__ == '__main__':
    code = main(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if code:
        sys.exit(code)
