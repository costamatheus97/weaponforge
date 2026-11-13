#!/usr/bin/env python3
"""What a definition may say about the review (Weapon.review, .review_limits), tested without Blender:
python3 tests/test_review_definition.py

Exits 1 when a case fails. Touches nothing.
"""
import os
import sys

TOOL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, TOOL)
from weaponforge.weapon import Weapon  # noqa: E402

failed = []


def gun(**change):
    class Gun(Weapon):
        id, name, tag = 'test_gun', 'TestGun', 'TG'
        bones = [('Root', None, (0, 0, 0)), ('Grip', 'Root', (0, 0, 0))]
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


case('the defaults: figures said, none held', gun(), None)
case('review first_person', gun(review='first_person'), None)
case('review first_person with two limits moved', gun(review='first_person', review_limits={'fp_sharp_share': 0.5, 'fp_kinds': 2}), None)
case('review as True', gun(review=True), 'review')
case('review with a typo', gun(review='first-person'), 'review')
case('review_limits as a list', gun(review_limits=[('fp_kinds', 2)]), 'review_limits')
case('a limit for a figure there is none of', gun(review='first_person', review_limits={'fp_sharpness': 0.5}), 'not a figure')
case('a limit that is not a number', gun(review='first_person', review_limits={'fp_kinds': 'three'}), 'not a number')
case('a limit that is True', gun(review='first_person', review_limits={'fp_kinds': True}), 'not a number')

if failed:
    print('test_review_definition: %d FAILED: %s' % (len(failed), ', '.join(failed)))
    sys.exit(1)
print('test_review_definition: PASS')
