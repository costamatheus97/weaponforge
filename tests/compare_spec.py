#!/usr/bin/env python3
"""Compare two weapon specs on what they measure:   compare_spec.py <reference.json> <new.json>

Every measurement in the sections below must agree (to 0.001, or 2 parts in 10000 for the big ones), every count and every name
must be the same,
and a check that both specs ran must have the same outcome. Paths, the status line, prose and the "unreal" block are left out:
they differ between a weapon and its test copy. Exits 1 when anything differs.
"""
import json
import sys

SECTIONS = ('bounds_ue_cm', 'bones', 'sockets', 'sockets_in_fbx', 'meshes', 'lods', 'budget', 'uv', 'dimensions_cm', 'reload_targets')
SKIP_KEYS = {'axes', 'use', 'meaning', 'note'}        # prose
ABS, REL = 1.0e-3, 2.0e-4


def leaves(node, path=''):
    if isinstance(node, dict):
        for key, value in node.items():
            if key not in SKIP_KEYS:
                yield from leaves(value, '%s/%s' % (path, key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from leaves(value, '%s/%d' % (path, i))
    else:
        yield path, node


def same(a, b):
    number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if isinstance(a, int) and isinstance(b, int):          # counts (triangles, parts): exactly
        return a == b
    if number(a) and number(b):
        return abs(a - b) <= max(ABS, REL * max(abs(a), abs(b)))
    return a == b


def compare(ref, new):
    out = []
    for section in SECTIONS:
        if (section in ref) != (section in new):
            out.append('%s: only in %s' % (section, 'the reference' if section in ref else 'the new spec'))
            continue
        if section not in ref:
            continue
        a, b = dict(leaves(ref[section], section)), dict(leaves(new[section], section))
        for key in sorted(set(a) | set(b)):
            if key not in a:
                out.append('%s: only in the new spec (%r)' % (key, b[key]))
            elif key not in b:
                out.append('%s: only in the reference (%r)' % (key, a[key]))
            elif not same(a[key], b[key]):
                out.append('%s: %r -> %r' % (key, a[key], b[key]))
    old = {c['check']: c['ok'] for c in ref.get('checks', [])}
    for c in new.get('checks', []):
        if c['check'] in old and old[c['check']] != c['ok']:
            out.append('check "%s": %s -> %s (%s)' % (c['check'], 'pass' if old[c['check']] else 'MISS', 'pass' if c['ok'] else 'MISS', c.get('detail', '')))
    for name in sorted(set(old) - {c['check'] for c in new.get('checks', [])}):
        out.append('check "%s": no longer run' % name)
    return out


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    with open(argv[0], 'r', encoding='utf-8') as fh:
        ref = json.load(fh)
    with open(argv[1], 'r', encoding='utf-8') as fh:
        new = json.load(fh)
    diffs = compare(ref, new)
    for line in diffs:
        print('DIFF ' + line)
    shared = sum(1 for s in SECTIONS if s in ref and s in new)
    print('compare_spec: %s (%d sections compared, %d checks in the new spec, %d of them missed)'
          % ('%d differences' % len(diffs) if diffs else 'the specs agree', shared, len(new.get('checks', [])),
             sum(1 for c in new.get('checks', []) if not c['ok'])))
    return 1 if diffs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
