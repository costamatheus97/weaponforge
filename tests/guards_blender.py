"""The guards that need Blender, on the template in an empty scene (smoke.sh runs it; about ten seconds):

    blender -b --factory-startup --python-exit-code 1 --python tests/guards_blender.py -- <scratch root>

  * a rig in the file that is not the weapon's (an object named "Armature", as in a live session with other work open) is never
    deleted: the stage "rig" stops and says so, and works once the other one is renamed
  * a part tagged for a bone the weapon does not define fails "model" by name
  * an unknown review sheet fails "render" before anything is rendered

Writes only under the scratch root (the UV layout picture). Saves no .blend.
"""
import os
import sys

import bpy

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge import kit as K, rig as R, stages, weapon as W  # noqa: E402

root = sys.argv[sys.argv.index('--') + 1]
failed = []


def result(label, ok, detail=''):
    print('guards: %s %s%s' % ('ok  ' if ok else 'FAIL', label, (' -> ' + detail[:170]) if detail else ''), flush=True)
    if not ok:
        failed.append(label)


def raises(label, kind, piece, fn):
    try:
        fn()
    except kind as e:
        result(label, piece in str(e), str(e))
    else:
        result(label, False, 'nothing was raised')


w = W.load('_template', root=root)
bpy.ops.wm.read_factory_settings(use_empty=True)
K.setup_scene()

# ---- someone else's rig is in the file
theirs = bpy.data.objects.new(R.ARMATURE_NAME, bpy.data.armatures.new('TheirBones'))
bpy.context.scene.collection.objects.link(theirs)
stages.model(w, hp=False, quiet=True)
stages.uv(w)
raises('a foreign "Armature" stops the rig', RuntimeError, 'already has an object named', lambda: stages.rig(w))
result('... and is still there, untouched', bpy.data.objects.get(R.ARMATURE_NAME) is theirs and theirs.data.name == 'TheirBones')
result('... and nothing of theirs counts as the weapon\'s rig', R.find(w) is None)
theirs.name = 'TheirRig'
game = stages.rig(w)
result('once it is renamed the rig is built', game['armature'].name == R.ARMATURE_NAME and R.find(w) is not None
       and bpy.data.objects.get('TheirRig') is theirs, 'armature %s, theirs %s' % (game['armature'].name, theirs.name))
stages.rig(w)
result('a second rig replaces the weapon\'s own and leaves one armature of its own',
       [a.name for a in bpy.data.armatures if a.name.startswith('SK_')] == ['SK_' + w.name] and bpy.data.objects.get('TheirRig') is theirs,
       str([a.name for a in bpy.data.armatures]))

# ---- a part on a bone that does not exist
real = w.builders


def stray(coll, hp=False):
    return [K.tag(K.box('Stray', (0, 0, 0), (1, 1, 1), coll), 'Slyde_Bone')]


w.builders = lambda: dict(real(), stray=stray)
try:
    raises('a part tagged for an undefined bone fails "model"', RuntimeError, 'which the weapon does not define',
           lambda: stages.model(w, only=['stray'], hp=False, quiet=True))
finally:
    del w.builders

# ---- an unknown review sheet
raises('an unknown review sheet fails "render"', ValueError, 'no such sheet', lambda: stages.render(w, what=['gray']))

print('guards: %s' % ('PASS' if not failed else 'FAIL: ' + '; '.join(failed)), flush=True)
sys.exit(1 if failed else 0)
