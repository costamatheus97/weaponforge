#!/usr/bin/env python3
"""What a weapon definition may say, tested without Blender:   python3 tests/test_definition.py

Weapon.validate() is what turns a typo in weapons/<id>/weapon.py into one message at the first stage instead of a KeyError in
the middle of a later one. Each case here is a mistake a definition can make. Exits 1 when a case fails. Touches nothing.
"""
import os
import sys

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge.weapon import Move, Prop, Weapon  # noqa: E402

failed = []


def good(**change):
    class Gun(Weapon):
        id, name, tag = 'test_gun', 'TestGun', 'TG'
        bones = [('Root', None, (0, 0, 0)), ('Grip', 'Root', (0, 0, 0)), ('Slide', 'Grip', (0, 0, 3)), ('Sight', 'Slide', (5, 0, 4)),
                 ('Mag', 'Grip', (0, 0, -2))]
        sockets = [('Muzzle', 'Grip', (10, 0, 3), (0, 0, 0), 'the muzzle')]
        props = [Prop('Mag', 'Mag')]
        moves = [Move('slide', 'Slide', lambda t: None, (1.0, 2.0))]
        poses = {'rest': {}, 'back': {'Slide': {'loc': (-2, 0, 0)}}}
        motion = {'Slide': 'back'}
    for key, value in change.items():
        setattr(Gun, key, value)
    return Gun()


def case(label, weapon, expect):
    """expect: a piece of the message validate() must give, or None for a sound definition."""
    got = weapon.validate()
    ok = (not got) if expect is None else any(expect in g for g in got)
    print('%s %s -> %s' % ('ok  ' if ok else 'FAIL', label, '; '.join(got)[:150] if got else 'sound'))
    if not ok:
        failed.append(label)


def same(label, got, want):
    ok = got == want
    print('%s %s -> %r' % ('ok  ' if ok else 'FAIL', label, got))
    if not ok:
        failed.append(label)


B = good().bones
case('the sound definition', good(), None)
case('a weapon with no sockets, props, moves or LODs', good(sockets=[], props=[], moves=[], lods=(), poses={'rest': {}}, motion={}), None)
case('a bone twice', good(bones=B + [('Slide', 'Grip', (0, 0, 0))]), 'defined twice')
case('a parent that comes later', good(bones=[B[0], B[2], B[1]] + B[3:]), 'not defined before it')
case('a parent that does not exist', good(bones=B + [('Bolt', 'Carrier', (0, 0, 0))]), 'not defined before it')
case('two roots', good(bones=B + [('Other', None, (0, 0, 0))]), 'only the first bone is the root')
case('a bone named like a socket joint', good(bones=B + [('SOCKET_Muzzle', 'Grip', (0, 0, 0))]), 'kept for the socket joints')
case('a bone without a position', good(bones=B + [('Bolt', 'Grip')]), 'write (name, parent or None')
case('no bones at all', good(bones=[], sockets=[], props=[], moves=[], poses={}, motion={}), 'at least a root bone')
case('a socket on a missing bone', good(sockets=[('Muzzle', 'Barrel', (0, 0, 0), (0, 0, 0), '')]), 'which is not defined')
case('a socket twice', good(sockets=good().sockets * 2), 'defined twice')
case('a socket without its rotation', good(sockets=[('Muzzle', 'Grip', (0, 0, 0), '')]), 'write (name, bone')
case('a prop on a missing bone', good(props=[Prop('Mag', 'Clip')]), 'prop Mag: bone Clip')
case('a prop suffix with a path in it', good(props=[Prop('../Mag', 'Mag')]), 'prop suffix')
case('a move on a missing bone', good(moves=[Move('slide', 'Slyde', lambda t: None, (1.0,))]), 'move "slide": bone Slyde')
case('a pose on a missing bone', good(poses={'back': {'Slyde': {'loc': (0, 0, 0)}}}), 'pose back: bone Slyde')
case('a pose with an unknown key', good(poses={'back': {'Slide': {'location': (0, 0, 0)}}}), 'not one of loc, rot, scale')
case('motion for a missing bone', good(motion={'Slyde': 'back'}), 'motion: bone Slyde')
case('LOD shares that grow', good(lods=((1, 0.25), (2, 0.5))), 'lods')
case('LOD indices that skip', good(lods=((1, 0.5), (3, 0.25))), 'lods')
case('a budget upside down', good(budget=(30000, 15000)), 'budget')
case('a texture size that is not a power of two', good(texture_size=3000), 'texture_size')
BOX = ((-1, -1, -1), (1, 1, 1))
case('a closeup, with the pose sheets framed on it', good(closeups={'action': BOX}, pose_closeup='action', pose_views=('right', 'q_rear_r')), None)
case('a closeup with its own views', good(closeups={'action': BOX + (['left', 'top'],)}), None)
case('a closeup with its corners the wrong way round', good(closeups={'action': (BOX[1], BOX[0])}), 'the first corner the lower one')
case('a closeup whose name cannot end a file name', good(closeups={'The Action': BOX}), 'it ends a file name')
case('pose sheets framed on a closeup that is not there', good(closeups={'action': BOX}, pose_closeup='acton'), 'is not one of closeups')
case('pose views given as one word', good(pose_views='right'), 'pose_views')
case('no pose views', good(pose_views=()), 'pose_views')
case('a name with a folder in it', good(name='../OtherGun/TestGun'), 'name')
case('an id with a capital', good(id='TestGun'), 'id')

same('a bare string is one bone, not its letters (Prop)', Prop('Mag', 'Clip_Bone').bones, ('Clip_Bone',))
same('a bare string is one bone, not its letters (Move)', Move('m', 'Slide_Bone', None, (1.0,)).bones, ('Slide_Bone',))
same('a single amount is one step', Move('m', 'Slide', None, 2.0).steps, (2.0,))
same('the limit is the largest amount by size', Move('m', 'Slide', None, (-1.0, -3.0)).limit, -3.0)
try:
    Move('m', 'Slide', None, ())
    same('no steps is refused', 'accepted', 'refused')
except ValueError:
    same('no steps is refused', 'refused', 'refused')
same('what hangs on a moving bone moves with it', good().with_children(('Slide',)), ('Slide', 'Sight'))
same('... through every level', good().with_children(('Grip',)), ('Grip', 'Slide', 'Sight', 'Mag'))

real, trial = good(), good()
trial.root = '/somewhere/else'
from weaponforge.weapon import UNREAL_BASE  # noqa: E402  (the setting unreal.content: /Game/Weapons unless configured)
same('a weapon built in place goes to its real Unreal folder', real.unreal_dir, UNREAL_BASE + '/TestGun')
same('a weapon built under --root goes to a trial folder', trial.unreal_dir, UNREAL_BASE + '/_Scratch/TestGun')
same('... and its spec stays under that root', os.path.dirname(trial.spec_path).replace('\\', '/'), '/somewhere/else/test_gun')
from weaponforge.weapon import SPEC_DIR  # noqa: E402
if not SPEC_DIR:                         # no spec folder configured: the spec is written beside the weapon's own files
    same('built in place, the spec is beside its files', os.path.dirname(real.spec_path), real.asset_root)

# ---- a variant that changes its base's dimensions (weaponforge/variant.py): the base's params.py run again, numbers pinned
from weaponforge.variant import rerun  # noqa: E402
import weapons.assault_g3.params as FULL  # noqa: E402

before = FULL.BZ
high = rerun('assault_g3', 'params', {'__doc__': 'the variant\'s own'}, BZ=9.0)
same('a pinned number is the variant\'s', high['BZ'], 9.0)
same('... what the file derives from it follows', round(high['TOP_Z'], 9), round(9.0 + 2.20, 9))
same('... and a function of the file reads it', high['grip_pt'].__globals__['BZ'], 9.0)
same('... the rest is the base\'s', high['NOSE_X'], FULL.NOSE_X)
same('... the base\'s own module is as it was', (FULL.BZ, before != 9.0), (before, True))
same('... the variant keeps its own docstring', high['__doc__'], 'the variant\'s own')
pair = rerun('assault_g3', 'params', {}, CASE_LEN=4.0)
same('one name of a pair can be pinned', (pair['CASE_R'], pair['CASE_LEN']), (FULL.CASE_R, 4.0))


def refused(label, expect, name='params', **pins):
    try:
        rerun('assault_g3', name, {}, **pins)
        got = 'accepted'
    except ValueError as e:
        got = 'refused' if expect in str(e) else 'refused, but it said: %s' % e
    same(label, got, 'refused')


refused('a pin the base does not have is refused by name', 'NOSE (not assigned at the top level)', NOSE=17.0)
refused('a function cannot be pinned', 'grip_pt (not assigned at the top level)', grip_pt=1.0)
refused('a pin must be a plain value', 'not a plain value', NOSE_X=len)
refused('only a weapon\'s three files can be run again', 'is not one of', name='__init__')

print('test_definition: %s' % ('PASS' if not failed else 'FAIL: ' + '; '.join(failed)))
sys.exit(1 if failed else 0)
