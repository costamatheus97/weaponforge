"""Every named finish (weaponforge/finish.py) builds on a real bake, by itself and in one table; the per-cm edge masks run.

Run inside Blender on a baked template (tests/finishes.sh does it):
    blender -b <root>/_template/_template.blend --python tests/test_finishes.py -- <tool dir> <root>
"""
import inspect
import sys

argv = sys.argv[sys.argv.index('--') + 1:]
sys.path.insert(0, argv[0])

import numpy as np                         # noqa: E402

from weaponforge import finish as F        # noqa: E402
from weaponforge import maps               # noqa: E402
from weaponforge import surface as S       # noqa: E402
from weaponforge import weapon as W        # noqa: E402

weapon = W.load('_template', argv[1])
images = S.load_maps(weapon)
bad = []

# each finish alone, with its defaults (the template has no rubber_textured, no grime list, no alloy kind)
for name, fn in F.FINISHES.items():
    s = S.Surface(weapon, images, name='wf_test_' + name)
    try:
        lay = F.make(s, name)
        assert isinstance(lay, S.Layer), type(lay)
        s.output(lay)
        print('finishes: %-17s ok (%d nodes)' % (name, len(s.nt.nodes)))
    except Exception as exc:                   # report every one, not only the first
        bad.append('%s: %r' % (name, exc))
    assert name in F.SETS, name
    assert set(inspect.signature(fn).parameters) >= {'s'}, name

# one table with every finish, a ready layer, an override, a place, and a row whose place is not there
s = S.Surface(weapon, images, name='wf_test_look')
try:
    rows = [('steel', 'phosphate_parts', {'finish': 'blued'}), ('steel', 'barrel_phosphate', {}, F.part_zone(s, 'barrel')),
            ('steel', 'sheet_magazine', {}, F.part_zone(s, 'magazine')), ('steel', 'sheet_magazine', {}, F.part_zone(s, 'no_such_part')),
            ('bright', 'bright_steel'), ('polymer', 'moulded_polymer', {'colour': (0.02, 0.02, 0.022)}), ('dark', 'anodised_alloy'),
            ('polymer', 'rubber', {}, F.part_zone(s, 'grip_l')), ('wood', S.timber(s, 'walnut'))]
    s.output(F.look(s, rows))
    print('finishes: look with every finish ok (%d nodes)' % len(s.nt.nodes))
except Exception as exc:
    bad.append('look: %r' % exc)
assert F.sets('moulded_polymer', 'rubber', 'phosphate_parts', 'barrel_phosphate') == ['poly_mould', 'rubber', 'phosphate']
try:
    F.make(S.Surface(weapon, images, name='wf_test_none'), 'no_such_finish')
    bad.append('make: an unknown finish raised nothing')
except KeyError:
    pass

# two rows of one finish with different places keep their own masks
s = S.Surface(weapon, images, name='wf_test_keys')
a = F._zones(s, [W.Zone((0, 0, 0), (1, 1, 1))], 'k')
b = F._zones(s, [W.Zone((0, 0, 0), (2, 1, 1))], 'k')
if a is b:
    bad.append('two different zone lists under one key share a mask')

# the dust and corner controls, serrated faces and the broad part of `vary`: each builds, the defaults leave the graph as it was
Z = W.Zone


def _nodes(name, finish, **kw):
    s = S.Surface(weapon, images, name=name)
    s.output(F.make(s, finish, **kw))
    return len(s.nt.nodes)


try:
    zones = [Z((0, 0, 0), (1, 1, 1), 1.0, 0.02), Z((2, 0, 0), (3, 1, 1), 1.0, 0.02)]
    base = _nodes('wf_test_life_0', 'anodised_alloy')
    same = _nodes('wf_test_life_1', 'anodised_alloy', dust=1.0, corners=1.0, dust_off=None, corners_off=None, serrated=None, vary_broad=None)
    same_vary = _nodes('wf_test_life_2', 'anodised_alloy', vary_broad=0.45)               # anodised_alloy's vary is 0.45: the same
    if not base == same == same_vary:
        bad.append('the defaults of dust, corners, serrated and vary_broad change the graph (%d, %d, %d nodes)' % (base, same, same_vary))
    off = _nodes('wf_test_life_3', 'anodised_alloy', dust=0.0, corners=0.0)
    if off >= base:
        bad.append('dust=0, corners=0 left the dust and the corner line in the graph (%d nodes against %d)' % (off, base))
    zoned = _nodes('wf_test_life_4', 'anodised_alloy', dust_off=zones, corners_off=zones[:1], dust=0.5, corners=0.5)
    serr = _nodes('wf_test_life_5', 'phosphate_parts', serrated=zones, serrated_ends=zones[1:], serrated_metal=[0.6, 0.15])
    s5 = _nodes('wf_test_life_6', 'phosphate_parts')
    if not (zoned > base and serr > s5):
        bad.append('dust_off / serrated added nothing to the graph (%d against %d, %d against %d)' % (zoned, base, serr, s5))
    _nodes('wf_test_life_7', 'moulded_polymer', vary=1.0, vary_broad=0.2)
    _nodes('wf_test_life_8', 'rubber', vary_broad=0.0)
    _nodes('wf_test_life_9', 'bright_steel', vary_broad=0.1, vary=0.6)
    _nodes('wf_test_life_10', 'phosphate_parts', vary=0.0, vary_broad=0.5)                  # the broad part alone
    s = S.Surface(weapon, images, name='wf_test_life_11')
    try:
        F.make(s, 'phosphate_parts', serrated=zones, serrated_metal=[0.6])
        bad.append('serrated_metal with one number for two zones raised nothing')
    except ValueError:
        pass
    print('finishes: dust / corner controls, serrated faces and vary_broad ok (%d nodes plain, %d with serrated)' % (s5, serr))
except Exception as exc:
    bad.append('wear controls: %r' % exc)

# the per-cm edge masks: scale 1 gives the baked masks back (but for the float16 / 8-bit rounding), denser gives wider
normal = np.load(weapon.bake_dir + '/normal.npy').astype(np.float32)
cover = np.load(weapon.bake_dir + '/cover.npy')
baked = np.load(weapon.bake_dir + '/masks.npy').astype(np.float32) / 255.0
cx, cc, wd = maps.edge_masks(normal, cover, np.ones(cover.shape, np.float32))
diff = max(float(np.abs(cx - baked[..., 1])[cover].max()), float(np.abs(wd - baked[..., 3])[cover].max()))
print('finishes: edge_masks at scale 1 against the bake: max difference %.4f' % diff)
if diff > 0.02:
    bad.append('edge_masks at scale 1 differs from the bake by %.4f' % diff)
cx2, _cc2, wd2 = maps.edge_masks(normal, cover, np.full(cover.shape, 2.0, np.float32))
print('finishes: edge_masks mean convex / wide zone at scale 1: %.4f / %.4f, at 2: %.4f / %.4f'
      % (cx[cover].mean(), wd[cover].mean(), cx2[cover].mean(), wd2[cover].mean()))
if not (cx2[cover].mean() > cx[cover].mean() and wd2[cover].mean() > wd[cover].mean()):
    bad.append('edge_masks at scale 2 carries no more edge than at 1')
tris, dens = S.island_density(weapon)
print('finishes: %d triangles, island density %.1f..%.1f px/cm (4096)' % (len(dens), dens.min(), dens.max()))
if not len(dens) or dens.min() <= 0:
    bad.append('island_density found no islands')

if bad:
    print('finishes: FAIL: ' + '; '.join(bad))
    sys.exit(1)
print('finishes: all ok')
