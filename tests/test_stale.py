"""`check` straight after a stage that makes the later ones stale (stages.check, stages.stale_by_stage). About twenty seconds:

    blender -b --factory-startup --python-exit-code 1 --python tests/test_stale.py -- <scratch folder>

Builds the template (model, uv, rig) under the scratch folder, rebuilds the parts and checks again. A stage that is older than the
model must be named, and must not be counted as a miss of the current model; a stage that is current and fails must still miss.
Exits 1 when a case fails.
"""
import os
import sys

import bpy

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge import check as CHK, rig as R, stages, weapon as W  # noqa: E402

failed = []


def result(label, ok, detail=''):
    print('stale: %s %s%s' % ('ok  ' if ok else 'FAIL', label, (' -> ' + str(detail)[:220]) if detail != '' else ''), flush=True)
    if not ok:
        failed.append(label)


def misses(report):
    return [r['check'] for r in report if not r['ok']]


root = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
w = W.load('_template', root=root)
stages.model(w, quiet=True)
stages.uv(w)
stages.rig(w)
result('a chain in order has nothing stale', stages.stale_by_stage() == {} and stages.stale() == [], stages.stale_by_stage())
before = stages.check(w)
result('and every check of it counts: the rig\'s are in the report', any(r['check'].startswith('rig:') for r in before), len(before))

stages.model(w, quiet=True)                                    # the parts are new: no UVs, and the rig is of the old ones
old = stages.stale_by_stage()
result('after "model" the uv and the rig are stale, named, each with why', list(old) == ['uv', 'rig'] and 'older than the latest "model"' in old['uv'],
       old)
result('stale() says the same in the same words', stages.stale() == list(old.values()), stages.stale())
lp = stages.parts(w, 'LP')
raw = CHK.run(w, lp, R.find(w), None, log=lambda *a: None)
result('(what check used to report there, from the old rig and no UVs: misses)', len(misses(raw)) > 0, misses(raw))
report = stages.check(w)
result('now none of it is counted as a miss of the current model', misses(report) == [], misses(report))
result('and the rig and uv checks are not in the report', not [r for r in report if r['check'].startswith(('rig:', 'uv'))],
       [r['check'] for r in report if r['check'].startswith(('rig:', 'uv'))])

key = next(iter(w.brief))
w.brief = {key: (0.0, 0.1)}                                    # a check of a current stage that cannot pass: measured on the new parts
report = stages.check(w)
result('a check that is current and fails still misses (the brief)', misses(report) == ['brief: %s' % key], misses(report))

if failed:
    print('stale: %d FAILED: %s' % (len(failed), ', '.join(failed)))
    sys.exit(1)
print('stale: PASS')
