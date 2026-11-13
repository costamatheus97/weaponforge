#!/usr/bin/env python3
"""The rules that keep the Unreal importer in the right folder, tested without Unreal:

    python3 tests/test_unreal_args.py [SPEC]       SPEC: a spec weaponforge exported (tests/smoke.sh gives its own), also checked

They live in integrations/unreal/weapon_spec.py, which both Unreal scripts use for their command line and the spec. Each case
below is a way a run could end up writing to, or deleting from, a folder it was not meant for. The content folder (--base) is
a made-up one, so that nothing here depends on the settings. Exits 1 when a case fails. Touches nothing: the specs it reads are
written to a temporary folder.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'integrations', 'unreal'))
import weapon_spec as W  # noqa: E402

FLAGS = ('--reimport', '--reimport-meshes', '--reimport-static', '--replace-referenced', '--remove')
BASE = '/Game/Studio/Weapons'
SCRATCH = BASE + '/_Scratch/'
MASTER = '/Game/Studio/M_Weapon'
failed = []


def spec(**change):
    s = {'name': 'TestGun', 'source': {'export_dir': '/somewhere/export'}, 'unreal': {'master_material': MASTER}, 'bounds_ue_cm': {'min': [0, 0, 0], 'max': [1, 1, 1]},
         'meshes': {'SKM_TestGun': {'fbx': 'SKM_TestGun.fbx', 'triangles': 100},
                    'SM_TestGun': {'fbx': 'SM_TestGun.fbx', 'triangles': 100, 'lods_in_fbx': [100, 50]},
                    'SM_TestGun_Mag': {'fbx': 'SM_TestGun_Mag.fbx', 'triangles': 20}},
         'lods': [{'fbx': 'SKM_TestGun_LOD1.fbx', 'triangles': 50}], 'sockets': [], 'bones': []}
    s.update(change)
    return s


def unreal(**change):
    u = {'master_material': MASTER}
    u.update(change)
    return u


def case(label, expect, argv, body=None, writes=True, inside=True, layout='beside', base=BASE, specs=True):
    """expect: the folder the run must end up with, or None when it must be refused. layout: where the trusted spec is, 'beside'
    (<specs>/<id>/<id>.json, the default with no spec folder) or 'folder' (<specs>/<id>.json); inside=False puts it elsewhere.
    base / specs: what the runner adds (None / False: left out)."""
    with tempfile.TemporaryDirectory() as tmp:
        spec_dir = os.path.join(tmp, 'assets')
        trusted = os.path.join(spec_dir, 'test_gun') if layout == 'beside' else spec_dir
        other = os.path.join(tmp, 'elsewhere', 'test_gun')
        os.makedirs(trusted)
        os.makedirs(other)
        path = os.path.join(trusted if inside else other, 'test_gun.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(body if body is not None else spec(), fh)
        argv = ['script.py'] + [a.replace('<SPEC>', path) for a in argv]
        argv += (['--base', base] if base is not None else []) + (['--specs', spec_dir] if specs else [])
        try:
            got = W.load(argv, FLAGS, writes=writes)[0]['unreal']['asset_dir']
        except W.ArgError as e:
            got, why = None, str(e)
        else:
            why = ''
        ok = got == expect
        print('%s %s -> %s%s' % ('ok  ' if ok else 'FAIL', label, got if got else 'refused', (' (' + why[:90] + ')') if why else ''))
        if not ok:
            failed.append(label)


REAL = BASE + '/TestGun'
TRIAL = SCRATCH + 'TestGun'

# ---- the ordinary runs
case('a weapon by id', REAL, ['--weapon', 'test_gun'])
case('a weapon by id, re-import', REAL, ['--weapon', 'test_gun', '--reimport'])
case('a weapon by id, its spec in a spec folder', REAL, ['--weapon', 'test_gun'], layout='folder')
case('its own spec by path', REAL, ['--spec', '<SPEC>'])
case('a base with a trailing slash', REAL, ['--weapon', 'test_gun'], base=BASE + '/')
case('a trial run', TRIAL, ['--weapon', 'test_gun', '--dest', TRIAL])
case('a trial run, trailing slash', TRIAL, ['--weapon', 'test_gun', '--dest', TRIAL + '/'])
case('a test copy of a spec into a trial folder', TRIAL, ['--spec', '<SPEC>', '--dest', TRIAL], inside=False)
case('a test copy of a spec, read only (the check script)', REAL, ['--spec', '<SPEC>'], inside=False, writes=False)
case('a spec written under a scratch root names a trial folder itself', TRIAL, ['--spec', '<SPEC>'], inside=False,
     body=spec(unreal=unreal(asset_dir=TRIAL)))

# ---- the runner's two arguments: required, never defaulted
case('no --base', None, ['--weapon', 'test_gun'], base=None)
case('no --specs', None, ['--weapon', 'test_gun'], specs=False)
case('--base with no value', None, ['--weapon', 'test_gun', '--base'], base=None)
for bad in ('/Game', 'Game/Studio/Weapons', '/Engine/Weapons', BASE + '/_Scratch', '/Game/Studio//Weapons', '/Game/1Weapons', '/Game/Stu dio'):
    case('--base %s' % bad, None, ['--weapon', 'test_gun'], base=bad)
case('a spec made for another content folder', None, ['--weapon', 'test_gun'], body=spec(unreal=unreal(content='/Game/Other')))
case('a spec made for this content folder', REAL, ['--weapon', 'test_gun'], body=spec(unreal=unreal(content=BASE)))
case('the real folder of another base is not taken', None, ['--weapon', 'test_gun'], body=spec(unreal=unreal(asset_dir='/Game/Other/TestGun')))

# ---- a lost value must never fall back to the real folder (the runner joins the arguments with spaces: an empty one vanishes)
case('--dest with no value, last', None, ['--weapon', 'test_gun', '--dest'])
case('--dest with an empty value', None, ['--weapon', 'test_gun', '--dest', '', '--reimport'])
case('--dest followed by another option', None, ['--weapon', 'test_gun', '--dest', '--reimport'])
case('--weapon with no value', None, ['--weapon'])
case('an unknown option', None, ['--weapon', 'test_gun', '--reimport-all'])
case('an option written with =', None, ['--weapon', 'test_gun', '--dest=' + TRIAL])
case('--dest twice', None, ['--weapon', 'test_gun', '--dest', TRIAL, '--dest', TRIAL + '2'])
case('neither --weapon nor --spec', None, ['--reimport'])
case('both --weapon and --spec', None, ['--weapon', 'test_gun', '--spec', '<SPEC>'])
case('a spec that does not exist', None, ['--weapon', 'no_such_gun'])

# ---- --dest is for trials only
for bad in (BASE + '/OtherGun', BASE, SCRATCH, SCRATCH.rstrip('/'), SCRATCH + '.', SCRATCH + '..',
            SCRATCH + 'A/B', SCRATCH + 'A.B', SCRATCH + '../OtherGun', SCRATCH + 'A//', '/Game/Characters/Hero', SCRATCH.lstrip('/') + 'A',
            SCRATCH + 'A\\..\\..', BASE + '/_scratch/A', SCRATCH + '_Hidden', SCRATCH + '1Gun', '/Game/Other/_Scratch/A'):
    case('--dest %s' % bad, None, ['--weapon', 'test_gun', '--dest', bad])

# ---- a spec from outside the project's own folder cannot write to a real folder
case('a test copy of a spec with no --dest', None, ['--spec', '<SPEC>'], inside=False)
case('a test copy of a spec, re-import, no --dest', None, ['--spec', '<SPEC>', '--reimport'], inside=False)
case('a weapon id that walks out of the spec folder', None, ['--weapon', '../elsewhere/test_gun'])
with tempfile.TemporaryDirectory() as tmp:          # <specs>/x/y/test_gun.json: inside the folder, but not a weapon's own place
    deep = os.path.join(tmp, 'assets', '_trial', 'test_gun')
    os.makedirs(deep)
    with open(os.path.join(deep, 'test_gun.json'), 'w', encoding='utf-8') as fh:
        json.dump(spec(), fh)
    try:
        W.load(['s.py', '--spec', os.path.join(deep, 'test_gun.json'), '--base', BASE, '--specs', os.path.join(tmp, 'assets')], FLAGS, writes=True)
        got = 'accepted'
    except W.ArgError:
        got = 'refused'
    print('%s a spec deeper under the specs folder (a --root inside it) -> %s' % ('ok  ' if got == 'refused' else 'FAIL', got))
    if got != 'refused':
        failed.append('a spec deeper under the specs folder')

# ---- what the spec itself may name
case('a spec whose folder is outside the weapons', None, ['--weapon', 'test_gun'], body=spec(unreal=unreal(asset_dir='/Game/Characters/Hero')))
case('a spec whose folder is the weapons root', None, ['--weapon', 'test_gun'], body=spec(unreal=unreal(asset_dir=BASE)))
case('a spec whose folder is two levels down', None, ['--weapon', 'test_gun'], body=spec(unreal=unreal(asset_dir=BASE + '/A/B')))
case('a spec whose folder is _Scratch itself', None, ['--weapon', 'test_gun'], body=spec(unreal=unreal(asset_dir=SCRATCH.rstrip('/'))))
case('an old-style asset_dir at the top of the spec', BASE + '/Other', ['--weapon', 'test_gun'], body=spec(asset_dir=BASE + '/Other'))
case('a spec with no master material', None, ['--weapon', 'test_gun'], body=spec(unreal={}))
case('a weapon name with a folder in it', None, ['--weapon', 'test_gun'], body=spec(name='../OtherGun/TestGun'))
case('a mesh name with a folder in it', None, ['--weapon', 'test_gun'],
     body=spec(meshes={'SKM_TestGun': {'fbx': 'SKM_TestGun.fbx', 'triangles': 1}, 'SM_../OtherGun/SM_OtherGun': {'fbx': 'a.fbx', 'triangles': 1}}))
case('a mesh file that walks upward', None, ['--weapon', 'test_gun'],
     body=spec(meshes={'SKM_TestGun': {'fbx': '../../other_gun/export/SKM_OtherGun.fbx', 'triangles': 1}}))
case('a LOD file with a folder in it', None, ['--weapon', 'test_gun'], body=spec(lods=[{'fbx': 'sub/SKM_TestGun_LOD1.fbx', 'triangles': 1}]))
case('a material instance with a path', None, ['--weapon', 'test_gun'], body=spec(unreal=unreal(material_instance='/Game/Other/MI_X')))
case('a master material outside /Game', None, ['--weapon', 'test_gun'], body=spec(unreal=unreal(master_material='/Engine/BasicShapes/M')))

# ---- the source files, looked at before anything is deleted
with tempfile.TemporaryDirectory() as tmp:
    good, empty, text, half = (os.path.join(tmp, n) for n in ('good.fbx', 'empty.fbx', 'tex.png', 'half.fbx'))
    with open(good, 'wb') as fh:
        fh.write(b'Kaydara FBX Binary  \x00\x1a\x00' + b'\0' * 64)
    open(empty, 'wb').close()
    with open(text, 'wb') as fh:
        fh.write(b'\x89PNG....')
    with open(half, 'wb') as fh:
        fh.write(b'\0' * 64)
    got = W.source_problems([good, text])
    ok = got == []
    print('%s good source files -> %s' % ('ok  ' if ok else 'FAIL', got or 'no problems'))
    if not ok:
        failed.append('good source files')
    got = W.source_problems([good, empty, half, os.path.join(tmp, 'missing.fbx')])
    ok = len(got) == 3 and got[0].startswith('empty') and got[1].startswith('not an FBX') and got[2].startswith('missing')
    print('%s bad source files -> %s' % ('ok  ' if ok else 'FAIL', [g.split(':')[0] for g in got]))
    if not ok:
        failed.append('bad source files')

# ---- a spec weaponforge really wrote (tests/smoke.sh passes the template's): it loads, and as it was built under --root it
# names a trial folder of the content folder it was made for and nothing else
if len(sys.argv) > 1:
    path = sys.argv[1]
    with open(path, encoding='utf-8') as fh:
        made = json.load(fh)['unreal']
    base = made.get('content', '')
    try:
        s = W.load(['script.py', '--spec', path, '--base', base, '--specs', os.path.dirname(os.path.dirname(path))], FLAGS, writes=True)[0]
        u = s['unreal']
        ok = u['asset_dir'] == W.scratch(base) + s['name'] and len(u['textures']) == 3 and u['skeletal']['name'] == 'SKM_' + s['name']
        print('%s the exported spec %s -> %s (%s, %d statics, %d textures)' % ('ok  ' if ok else 'FAIL', os.path.basename(path), u['asset_dir'],
                                                                              u['skeletal']['name'], len(u['statics']), len(u['textures'])))
    except Exception as e:  # noqa: BLE001
        ok = False
        print('FAIL the exported spec %s: %s' % (path, e))
    if not ok:
        failed.append('the exported spec')

print('test_unreal_args: %s' % ('PASS' if not failed else 'FAIL: ' + '; '.join(failed)))
sys.exit(1 if failed else 0)
