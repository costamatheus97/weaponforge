#!/usr/bin/env python3
"""weaponforge: a judge for a review pack's pairs, pluggable and off by default. Plain Python: no Blender, no model.

    python3 weaponforge/critic.py <pack> '<command>' [--seed N] [--timeout S]
    weaponforge <id> review --against DIR --critic '<command>'        (bin/weaponforge runs this after the pack is made)

The command is a template run once per pair that changed (compare.json: a pair whose pixels did not change is skipped). Its
fields, each quoted for the shell (any other brace is left as it is):

    {a} {b}     the two crops, as critic/<crop>/A.png and B.png. Which of them is the build compared against and which is
                this one is drawn per crop (seeded, kept in critic/order.json): the judge is never told which is new
    {name}      the crop's name (ads_rear_sight, fp_near, muzzle, ...)
    {rubric}    the pack's rubric.md: what was kept and what was turned back on AssaultG3, and why
    {out}       where to write the answer, critic/<crop>/answer.json

It must write {"better": "a" | "b" | "same", "confidence": 0 to 1, "why": "one sentence"} to {out} (or print it as its last
line). Anything else, a missing answer, a non-zero exit or a time-out is recorded as invalid and the run goes on. The answers
are turned back into before and after and gathered into punchlist.json and punchlist.md, the surest first: a crop where the
build compared against is better is to fix or turn back; one judged the same is a change the pictures do not show as better.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

VERDICTS = ('a', 'b', 'same')


def _order(seed, name):
    """True when A is this build (the after) for this crop: drawn from the seed and the crop's name, the same every run."""
    return hashlib.sha256(('%s/%s' % (seed, name)).encode('utf-8')).digest()[0] % 2 == 1


FIELDS = re.compile(r'\{(a|b|name|rubric|out)\}')


def fill(command, fields):
    """The command with its five fields put in, each quoted for the shell; every other brace is left as it is (an awk program,
    a JSON one-liner)."""
    return FIELDS.sub(lambda m: shlex.quote(fields[m.group(1)]), command)


def parse(text):
    """The judge's answer from what it wrote: (answer, None) or (None, why it is not one)."""
    text = (text or '').strip()
    if not text:
        return None, 'no answer'
    try:
        got = json.loads(text)
    except ValueError:
        try:
            got = json.loads(text.splitlines()[-1])
        except (ValueError, IndexError):
            return None, 'not JSON: %r' % text[:120]
    if not isinstance(got, dict):
        return None, 'not an object: %r' % (got,)
    better = str(got.get('better', '')).strip().lower()
    if better not in VERDICTS:
        return None, '"better" is %r, not a, b or same' % (got.get('better'),)
    try:
        conf = float(got.get('confidence'))
    except (TypeError, ValueError):
        return None, '"confidence" is %r, not a number' % (got.get('confidence'),)
    if not 0.0 <= conf <= 1.0:
        return None, '"confidence" %r is not between 0 and 1' % conf
    why = str(got.get('why', '')).strip()
    return {'better': better, 'confidence': conf, 'why': why}, None


def judge(pack, command, seed=0, timeout=300.0, log=print):
    """Run the judge on every changed pair of the pack; write punchlist.json and punchlist.md and return the punch list."""
    with open(os.path.join(pack, 'compare.json'), 'r', encoding='utf-8') as fh:
        compare = json.load(fh)
    rubric = os.path.join(pack, 'rubric.md')
    root = os.path.join(pack, 'critic')
    os.makedirs(root, exist_ok=True)
    order, rows = {}, []
    for name, crop in sorted(compare['crops'].items()):
        if 'missing' in crop:
            rows.append({'crop': name, 'verdict': 'skipped', 'why': 'only one build has this crop'})
            continue
        if crop.get('unchanged'):
            rows.append({'crop': name, 'verdict': 'unchanged', 'why': '%.2f %% of its pixels changed' % (100 * crop['diff_share'])})
            continue
        here = os.path.join(root, name)
        os.makedirs(here, exist_ok=True)
        after_is_a = _order(seed, name)
        order[name] = 'A is this build' if after_is_a else 'A is the build compared against'
        first, second = (crop['this'], crop['against']) if after_is_a else (crop['against'], crop['this'])
        shutil.copyfile(os.path.join(pack, first), os.path.join(here, 'A.png'))
        shutil.copyfile(os.path.join(pack, second), os.path.join(here, 'B.png'))
        out = os.path.join(here, 'answer.json')
        if os.path.isfile(out):
            os.remove(out)
        fields = {'a': os.path.join(here, 'A.png'), 'b': os.path.join(here, 'B.png'), 'name': name, 'rubric': rubric, 'out': out}
        cmd = fill(command, fields)
        row = {'crop': name, 'pair': crop['pair'], 'changed': crop['diff_share']}
        try:
            done = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            row.update(verdict='invalid', why='no answer in %.0f s' % timeout)
            rows.append(row)
            continue
        if done.returncode != 0:
            row.update(verdict='invalid', why='the command exited %d: %s' % (done.returncode, (done.stderr or '').strip()[-200:]))
            rows.append(row)
            continue
        if os.path.isfile(out):
            with open(out, 'r', encoding='utf-8') as fh:
                written = fh.read()
        else:
            written = done.stdout
        answer, err = parse(written)
        if err:
            row.update(verdict='invalid', why=err)
            rows.append(row)
            continue
        if answer['better'] == 'same':
            verdict = 'same'
        else:
            this_won = (answer['better'] == 'a') == after_is_a
            verdict = 'this' if this_won else 'against'
        row.update(verdict=verdict, confidence=answer['confidence'], why=answer['why'])
        rows.append(row)
    with open(os.path.join(root, 'order.json'), 'w', encoding='utf-8') as fh:
        json.dump({'seed': seed, 'order': order}, fh, indent=1)
    rank = {'against': 0, 'same': 1, 'invalid': 2, 'this': 3, 'unchanged': 4, 'skipped': 5}
    rows.sort(key=lambda r: (rank[r['verdict']], -r.get('confidence', 0.0), r['crop']))
    punch = {'pack': pack, 'this': compare.get('this'), 'against': compare.get('against'), 'command': command, 'items': rows}
    with open(os.path.join(pack, 'punchlist.json'), 'w', encoding='utf-8') as fh:
        json.dump(punch, fh, indent=1)
    what = {'against': 'WORSE than the build compared against: fix it or turn the change back',
            'same': 'no better: the change does not show here; turn it back unless it is needed for something else',
            'invalid': 'no valid answer', 'this': 'better: keep', 'unchanged': 'unchanged: not judged',
            'skipped': 'not judged'}
    lines = ['# Punch list', '', 'This build: %s  ' % compare.get('this'), 'Compared against: %s  ' % compare.get('against'),
             'Judge: `%s`' % command, '']
    for r in rows:
        conf = ' (confidence %.2f)' % r['confidence'] if 'confidence' in r else ''
        lines.append('- **%s**: %s%s. %s' % (r['crop'], what[r['verdict']], conf, r.get('why', '')))
    with open(os.path.join(pack, 'punchlist.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    counts = {}
    for r in rows:
        counts[r['verdict']] = counts.get(r['verdict'], 0) + 1
    log('[weaponforge] critic: %s; %s' % (', '.join('%s %d' % kv for kv in sorted(counts.items())), os.path.join(pack, 'punchlist.md')))
    return punch


def main(argv):
    p = argparse.ArgumentParser(prog='critic.py', description='Judge a review pack\'s pairs with a command (see the module text).')
    p.add_argument('pack')
    p.add_argument('command')
    p.add_argument('--seed', type=int, default=0, help='draws which side of each pair is A')
    p.add_argument('--timeout', type=float, default=300.0, help='seconds a judgement may take')
    args = p.parse_args(argv)
    if not os.path.isfile(os.path.join(args.pack, 'compare.json')):
        print('critic: %s has no compare.json: make the pack with review --against first' % args.pack, file=sys.stderr)
        return 2
    judge(args.pack, args.command, args.seed, args.timeout)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
