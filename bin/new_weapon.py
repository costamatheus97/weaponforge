#!/usr/bin/env python3
"""Start a new weapon from the template:   weaponforge new <id> <Name> <TAG>

    id     the definition folder (weapons/<id>/) and the asset folder: lower case, e.g. shotgun_g1
    Name   the asset stem, e.g. ShotgunG1 -> SKM_ShotgunG1, SM_ShotgunG1, T_ShotgunG1_BC, MI_ShotgunG1
    TAG    a short prefix for the weapon's collections in its .blend, e.g. SG1 -> SG1_LP, SG1_HP, SG1_GAME

Copies weapons/_template/ (a small pistol: a long gun replaces its parts.py and most of its weapon.py) and renames what has
to be renamed. Nothing else is created until the first stage runs. The order of work it belongs to is in README.md ("The order
of work for a new weapon"): read CRAFT.md, ask the person, run this, write BRIEF.md, show the concept, then build.
Refuses an id, name or tag that anything already uses: a definition, an asset folder, a spec, and, when the setting
unreal.project names a project, a folder under its content folder for weapons (a weapon made by hand may live there, and an
import must never land on it). Where those are comes from weaponforge/settings.py (weaponforge.toml, WEAPONFORGE_*).
"""
import os
import re
import shutil
import sys

TOOL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(TOOL, 'weaponforge'))
import settings  # noqa: E402  (weaponforge/settings.py: pure Python, read here without importing the package)

WEAPONS = os.path.join(TOOL, 'weapons')
TEMPLATE = os.path.join(WEAPONS, '_template')


def fail(text):
    sys.exit('weaponforge new: ' + text)


def declared(field):
    """{weapon folder: the value of `field = '...'` in its weapon.py}."""
    out = {}
    for folder in sorted(os.listdir(WEAPONS)):
        path = os.path.join(WEAPONS, folder, 'weapon.py')
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as fh:
                m = re.search(r"^\s+%s = '([^']+)'" % field, fh.read(), re.M)
            if m:
                out[folder] = m.group(1)
    return out


def asset_folder(wid):
    """Where the weapon's source files will go (the setting `assets`; weaponforge/weapon.py: Weapon.asset_root)."""
    return os.path.join(settings.get('assets'), wid)


def spec_file(wid):
    """Where its spec will go (weaponforge/weapon.py: Weapon.spec_path): in the spec folder if one is set, else beside its files."""
    folder = settings.get('spec_dir')
    return os.path.join(folder, wid + '.json') if folder else os.path.join(asset_folder(wid), wid + '.json')


def unreal_folder():
    """The folder on disk that holds the weapons in the Unreal project (unreal.project, unreal.content), or None when no
    project is set. /Game/... is the project's Content/ folder."""
    project = settings.get('unreal.project')
    content = settings.get('unreal.content').strip('/')
    if not project or not (content == 'Game' or content.startswith('Game/')):
        return None
    return os.path.join(os.path.dirname(project), 'Content', *content.split('/')[1:])


def main(argv):
    if len(argv) != 3:
        fail('usage: weaponforge new <id> <Name> <TAG>   e.g. weaponforge new shotgun_g1 ShotgunG1 SG1')
    wid, name, tag = argv
    if not re.fullmatch(r'[a-z][a-z0-9_]*', wid):
        fail('the id must be lower case letters, digits and underscores, starting with a letter (it is a Python package): %r' % wid)
    if not re.fullmatch(r'[A-Z][A-Za-z0-9]*', name):
        fail('the name must be letters and digits starting with a capital (it becomes SKM_<Name>): %r' % name)
    if not re.fullmatch(r'[A-Z][A-Z0-9]{1,5}', tag):
        fail('the tag must be 2 to 6 capitals / digits starting with a letter: %r' % tag)
    dest = os.path.join(WEAPONS, wid)
    if os.path.exists(dest):
        fail('%s already exists' % dest)
    try:
        assets = asset_folder(wid)
        spec = spec_file(wid)
        unreal = unreal_folder()
    except settings.SettingsError as e:
        fail(str(e))
    if os.path.exists(assets):
        fail('%s already exists: another weapon\'s source files live there. Pick another id.' % assets)
    for field, value in (('name', name), ('tag', tag)):
        taken = [w for w, v in declared(field).items() if v.lower() == value.lower()]
        if taken:
            fail('%s %r is already used by weapons/%s' % (field, value, taken[0]))
    if os.path.exists(spec):
        fail('%s already exists: that id belongs to a weapon the game may use. Pick another id.' % spec)
    if unreal and os.path.isdir(unreal):
        taken = [d for d in os.listdir(unreal) if d.lower() == name.lower()]       # Unreal's paths ignore case
        if taken:
            fail('the Unreal project already has %s: an import of %r would land on that weapon. Pick another name.'
                 % (os.path.join(unreal, taken[0]), name))

    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    try:
        rename(dest, wid, name, tag)
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)          # never leave a half-renamed weapon behind
        raise
    print('created %s' % dest)
    print('The template is a small PISTOL. A pistol is edited from it; a long gun replaces parts.py and most of weapon.py')
    print('(weapons/assault_g3 is the long-gun example for the rig, poses and sockets: read it for how, not for its parts).')
    print('The order of work is the same everywhere (README.md, "The order of work for a new weapon"). You should already have')
    print('read CRAFT.md whole and asked the person its section 1 questions; if not, do that first, before anything else. Then:')
    print('  1. write weapons/%s/BRIEF.md from their answers' % wid)
    print('  2. show the concept (docs/concept.md): the brief, two or three to-scale side outlines that differ in kind, a')
    print('     recommendation and what each differs in, with the pictures in %s' % os.path.join(assets, 'ref'))
    print('  3. wait for approval 1 (the concept)')
    print('  4. only then edit params.py, parts.py and weapon.py (docs/building.md) and run')
    print('     bin/weaponforge %s model render --what grey' % wid)


def rename(dest, wid, name, tag):
    swaps = {
        'weapon.py': [("id = '_template'", "id = '%s'" % wid), ("name = 'TemplateGun'", "name = '%s'" % name), ("tag = 'TP'", "tag = '%s'" % tag),
                      ('class TemplateGun(Weapon)', 'class %s(Weapon)' % name), ('WEAPON = TemplateGun()', 'WEAPON = %s()' % name),
                      ('TP_LP, TP_HP, TP_GAME', '%s_LP, %s_HP, %s_GAME' % (tag, tag, tag)),
                      ('SKM_TemplateGun, SM_TemplateGun, T_TemplateGun_BC, MI_TemplateGun', 'SKM_%s, SM_%s, T_%s_BC, MI_%s' % (name, name, name, name)),
                      ("design = 'the weaponforge template: a made-up blocky pistol, no real maker or markings'",
                       "design = 'TODO: one line saying what this weapon is (fictional: no real maker or markings)'"),
                      ("texture_size = 1024            # a real first-person weapon: 4096",
                       "texture_size = 4096            # TODO: the sheet a first-person weapon gets; iterate with --size 1024"),
                      ("budget = (600, 6000)           # LOD0 triangles the design allows; a real first-person pistol: (15000, 30000)",
                       "budget = (15000, 30000)        # TODO: LOD0 triangles the design allows (this is a first-person pistol's; the\n"
                       "    #                                template's blocks have far fewer, so \"mesh: triangles\" misses until the real parts exist)")],
    }
    for fname in ('weapon.py', 'parts.py', 'params.py', '__init__.py', 'BRIEF.md'):
        path = os.path.join(dest, fname)
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
        for old, new in swaps.get(fname, []):
            if old not in text:
                fail('the template changed: %r is not in %s any more (update bin/new_weapon.py)' % (old, fname))
            text = text.replace(old, new)
        text = text.replace('TemplateGun', name)
        if fname == '__init__.py':
            text = '"""%s: a weaponforge weapon. See weapon.py."""\n' % name
        elif fname == 'weapon.py':
            text = re.sub(r'\A""".*?"""\n', '"""%s: the weapon definition. TODO: say what the weapon is.\n\nGeometry is in parts.py, every dimension in '
                          'params.py; this file says how the parts make a weapon. Started from the weaponforge\ntemplate: what you do not need, '
                          'delete (the base class in weaponforge/weapon.py has a default for every hook\nbut builders() and surface()).\n"""\n' % name, text, count=1, flags=re.S)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)


if __name__ == '__main__':
    main(sys.argv[1:])
