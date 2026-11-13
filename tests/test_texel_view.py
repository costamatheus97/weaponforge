#!/usr/bin/env python3
"""What a definition may say about texels by view (Weapon.texel_view, .player_eyes), tested without Blender:
python3 tests/test_texel_view.py

Exits 1 when a case fails. Touches nothing. (uv.view_demand itself needs Blender: see docs/texels.md, "Texels by place".)
"""
import os
import sys

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge.weapon import TexelZone, Weapon  # noqa: E402

failed = []


def gun(**change):
    class Gun(Weapon):
        id, name, tag = 'test_gun', 'TestGun', 'TG'
        bones = [('Root', None, (0, 0, 0)), ('Grip', 'Root', (0, 0, 0))]
        sockets = [('SightRear', 'Grip', (-5, 0, 4), (0, 0, 0), 'rear sight'), ('SightFront', 'Grip', (10, 0, 4), (0, 0, 0), 'front sight')]
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


case('the defaults: no view weights', gun(), None)
case('texel_view on, the hero eyes', gun(texel_view=True, uv_pack='tight', texel_hidden=0.45), None)
case('texel_view on with a hand zone on top', gun(texel_view=True, texel_zones=[TexelZone(2.0, builders='sight')]), None)
case('one eye moved', gun(texel_view=True, player_eyes={'ads': (-15.0, 0.0, 4.0)}), None)
case('both eyes moved', gun(texel_view=True, player_eyes={'fp': (-25.0, 7.0, 10.5), 'ads': (-15.0, 0.0, 4.0)}), None)
case('texel_view as a word', gun(texel_view='auto'), 'texel_view')
case('an eye with a typo for its name', gun(player_eyes={'hip': (-25.0, 7.0, 10.5)}), 'player_eyes')
case('an eye with two numbers', gun(player_eyes={'fp': (-25.0, 7.0)}), 'player_eyes')
case('player_eyes as a list', gun(player_eyes=[(-25.0, 7.0, 10.5)]), 'player_eyes')

if failed:
    print('test_texel_view: %d FAILED: %s' % (len(failed), ', '.join(failed)))
    sys.exit(1)
print('test_texel_view: PASS')
