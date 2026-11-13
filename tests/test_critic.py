#!/usr/bin/env python3
"""The critic's round trip with a stub judge, without Blender or a model (weaponforge/critic.py):

    python3 tests/test_critic.py

A pack is faked in a scratch folder: crops whose files say "before" or "after". The stub judge reads the two it is given and
answers for the one that says "after", so whatever order the critic draws, every answer must come back as "this build is
better". Around that: a judge that says "same", one that writes nonsense, one that exits with an error, one that prints its
answer instead of writing it, a pair the pixel difference left unchanged and a crop only one build has. The punch list must
put the worse-than-before and same items first and the surest first among them, and the A/B order must be blind (both orders
drawn) and the same on every run. Touches nothing outside its scratch folder. Exits 1 when a case fails.
"""
import json
import os
import shlex
import shutil
import sys
import tempfile

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(TOOL, 'weaponforge'))
import critic  # noqa: E402

failed = []


def result(label, ok, detail=''):
    print('%s %s%s' % ('ok  ' if ok else 'FAIL', label, (' -> ' + str(detail)[:170]) if detail != '' else ''))
    if not ok:
        failed.append(label)


STUB = r'''
import json, sys
a, b, name, rubric, out = sys.argv[1:6]
assert open(rubric).read().startswith('# rubric'), 'no rubric'
ta, tb = open(a).read(), open(b).read()
if name == 'nonsense':
    open(out, 'w').write('I think the left one, mostly')
elif name == 'crash':
    sys.stderr.write('the judge fell over')
    sys.exit(3)
elif name == 'printed':
    print('thinking...')
    print(json.dumps({'better': 'a' if ta == 'after' else 'b', 'confidence': 0.55, 'why': 'printed, not written'}))
elif name == 'worse':
    json.dump({'better': 'a' if ta == 'before' else 'b', 'confidence': 0.8, 'why': 'the old one reads better'}, open(out, 'w'))
elif name == 'worse_sure':
    json.dump({'better': 'a' if ta == 'before' else 'b', 'confidence': 0.95, 'why': 'plainly worse'}, open(out, 'w'))
elif name == 'flat':
    json.dump({'better': 'same', 'confidence': 0.7, 'why': 'no difference at this size'}, open(out, 'w'))
elif name == 'outside':
    json.dump({'better': 'a', 'confidence': 1.7, 'why': 'too sure'}, open(out, 'w'))
else:
    json.dump({'better': 'a' if ta == 'after' else 'b', 'confidence': 0.9, 'why': 'the new one'}, open(out, 'w'))
'''

scratch = tempfile.mkdtemp(prefix='wf_critic_')
try:
    pack = os.path.join(scratch, 'pack with space')
    for sub in ('crops', 'against/crops', 'pairs'):
        os.makedirs(os.path.join(pack, sub))
    with open(os.path.join(pack, 'rubric.md'), 'w') as fh:
        fh.write('# rubric\n')
    stub = os.path.join(scratch, 'stub judge.py')
    with open(stub, 'w') as fh:
        fh.write(STUB)
    better = ['g%02d' % k for k in range(12)]           # enough that both orders are drawn
    judged = better + ['nonsense', 'crash', 'printed', 'worse', 'worse_sure', 'flat', 'outside']
    crops = {}
    for name in judged + ['still']:
        for path, words in (('crops/%s.png' % name, 'after'), ('against/crops/%s.png' % name, 'before')):
            with open(os.path.join(pack, path), 'w') as fh:
                fh.write(words)
        crops[name] = {'pair': 'pairs/%s.png' % name, 'this': 'crops/%s.png' % name, 'against': 'against/crops/%s.png' % name,
                       'diff_mean': 3.0, 'diff_share': 0.2, 'unchanged': False}
    crops['still'].update(diff_share=0.0001, unchanged=True)
    crops['gone'] = {'missing': 'against'}
    with open(os.path.join(pack, 'compare.json'), 'w') as fh:
        json.dump({'this': '/b/new', 'against': '/b/old', 'crops': crops}, fh)

    command = '%s %s {a} {b} {name} {rubric} {out}' % (shlex.quote(sys.executable), shlex.quote(stub))
    said = []
    punch = critic.judge(pack, command, seed=7, timeout=60, log=said.append)
    rows = {r['crop']: r for r in punch['items']}
    with open(os.path.join(pack, 'critic', 'order.json')) as fh:
        order = json.load(fh)['order']

    result('every judged crop has an order, and both orders were drawn',
           set(order) == set(judged) and len(set(order.values())) == 2, sorted(set(order.values())))
    result('the judge never sees which is new: answers for "after" all come back as this build better',
           all(rows[n]['verdict'] == 'this' and rows[n]['confidence'] == 0.9 for n in better),
           [(n, rows[n]['verdict']) for n in better if rows[n]['verdict'] != 'this'])
    result('"the old one reads better" comes back as worse than before', rows['worse']['verdict'] == 'against'
           and rows['worse_sure']['verdict'] == 'against', (rows['worse']['verdict'], rows['worse_sure']['verdict']))
    result('"same" is kept as same', rows['flat']['verdict'] == 'same' and rows['flat']['confidence'] == 0.7)
    result('an answer printed as the last line counts', rows['printed']['verdict'] == 'this', rows['printed'])
    result('nonsense is invalid, the run goes on', rows['nonsense']['verdict'] == 'invalid' and 'not JSON' in rows['nonsense']['why'],
           rows['nonsense'].get('why'))
    result('a judge that exits non-zero is invalid, with its words',
           rows['crash']['verdict'] == 'invalid' and 'exited 3' in rows['crash']['why'] and 'fell over' in rows['crash']['why'],
           rows['crash'].get('why'))
    result('a confidence over 1 is invalid', rows['outside']['verdict'] == 'invalid', rows['outside'].get('why'))
    result('an unchanged pair is not judged', rows['still']['verdict'] == 'unchanged'
           and not os.path.isdir(os.path.join(pack, 'critic', 'still')))
    result('a crop only one build has is skipped', rows['gone']['verdict'] == 'skipped')
    verdicts = [r['crop'] for r in punch['items']]
    result('the punch list: worse first (surest first), then same, invalid, better, unchanged, skipped',
           verdicts[:3] == ['worse_sure', 'worse', 'flat'] and verdicts[-2:] == ['still', 'gone']
           and [r['verdict'] for r in punch['items']][3:6] == ['invalid'] * 3, verdicts)
    with open(os.path.join(pack, 'punchlist.md')) as fh:
        md = fh.read()
    result('punchlist.md says what to do, the surest worse item first',
           md.index('**worse_sure**') < md.index('**worse**') and 'turn the change back' in md and '(confidence 0.95)' in md)
    result('punchlist.json is written and the log names it', os.path.isfile(os.path.join(pack, 'punchlist.json'))
           and said and 'punchlist.md' in said[-1], said)

    again = critic.judge(pack, command, seed=7, timeout=60, log=lambda *_: None)
    with open(os.path.join(pack, 'critic', 'order.json')) as fh:
        result('the same seed draws the same order and the same verdicts', json.load(fh)['order'] == order
               and [(r['crop'], r['verdict']) for r in again['items']] == [(r['crop'], r['verdict']) for r in punch['items']])
    braces = command + " && : '{\"note\": {}}' && awk 'BEGIN {exit 0}'"
    got = critic.fill(braces, {'a': '/x/A.png', 'b': '/x/B.png', 'name': 'muzzle', 'rubric': '/x/r.md', 'out': '/x/o.json'})
    result('fill puts in the five fields and leaves every other brace', "'{\"note\": {}}'" in got and "BEGIN {exit 0}" in got
           and '/x/A.png' in got and '{a}' not in got, got[-120:])
    braced = critic.judge(pack, braces, seed=7, timeout=60, log=lambda *_: None)
    result('a command with braces of its own runs and gives the same verdicts',
           [(r['crop'], r['verdict']) for r in braced['items']] == [(r['crop'], r['verdict']) for r in punch['items']])
    for text, ok in (('{"better": "B", "confidence": 0.6, "why": "x"}', True), ('{"better": "left", "confidence": 0.6}', False),
                     ('{"better": "a", "confidence": "high"}', False), ('[1, 2]', False), ('', False)):
        got, err = critic.parse(text)
        result('parse %r: %s' % (text[:40], 'an answer' if ok else 'refused'), (got is not None) == ok, err or got)
    rc = critic.main([os.path.join(scratch, 'nowhere'), 'true'])
    result('critic.py on a folder with no compare.json stops with 2', rc == 2)
finally:
    shutil.rmtree(scratch, ignore_errors=True)

if failed:
    print('test_critic: %d FAILED: %s' % (len(failed), ', '.join(failed)))
    sys.exit(1)
print('test_critic: PASS')
