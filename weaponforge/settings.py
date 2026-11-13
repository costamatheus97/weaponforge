"""weaponforge: where things live, from three places (the first that has a value wins):

    1. an environment variable   WEAPONFORGE_<KEY>, the key in capitals with dots as _ (WEAPONFORGE_UNREAL_CONTENT)
    2. the settings file         weaponforge.toml at the top of the repository, or the file WEAPONFORGE_CONFIG names
    3. the default               below; every one works with no configuration at all

Pure Python, no bpy: Blender's Python reads it, and so do the launcher (bin/weaponforge), bin/new_weapon.py and the Unreal
runner, on whatever python3 the system has (tomllib from 3.11; older ones get the small reader at the bottom of this file).
weaponforge.example.toml lists every key with a comment.

A path is taken as written when absolute, else relative to the settings file's folder (a value from the file) or to the
current folder (a value from the environment); a default is relative to the repository. Each Python sees paths in its own
form: a Windows Blender started from WSL reads /mnt/d/x as D:\\x, and a WSL Python reads D:\\x as /mnt/d/x.

    python3 weaponforge/settings.py                 every setting, its value and where it came from
    python3 weaponforge/settings.py get KEY         one value (empty when it has none)
"""
import os
import re
import sys

TOOL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the repository

# key: (default, is a path). A default path is relative to the repository; '' means "not set".
KEYS = {
    'blender': ('', True),                         # the Blender executable (the launcher: else `blender` on PATH)
    'assets': ('build/weapons', True),             # the asset root: <assets>/<id>/ holds a weapon's .blend, bakes, textures, FBX
    'spec_dir': ('', True),                        # where <id>.json goes; '' = beside the weapon's files, <assets>/<id>/<id>.json
    'materials': ('', True),                       # one more folder searched for texforge sets and decals (surface.material_dirs)
    'unreal.content': ('/Game/Weapons', False),    # each weapon imports to <content>/<Name>, a trial to <content>/_Scratch/<Name>
    'unreal.master_material': ('/Game/Materials/M_Weapon', False),   # parent of every MI_<Name> (docs/unreal.md: the master material)
    'unreal.param_base_color': ('BaseColor', False),                 # the master's texture parameters ...
    'unreal.param_normal': ('Normal', False),
    'unreal.param_masks': ('ARM', False),                            # (R occlusion, G roughness, B metal)
    'unreal.param_roughness_scale': ('RoughnessScale', False),       # ... and its two scalars (set to 1.0)
    'unreal.param_metallic_scale': ('MetallicScale', False),
    'unreal.editor': ('', True),                   # UnrealEditor-Cmd (Linux, macOS) or UnrealEditor-Cmd.exe (Windows, from WSL)
    'unreal.project': ('', True),                  # the .uproject the weapons are imported into
}


class SettingsError(RuntimeError):
    pass


def env_name(key):
    return 'WEAPONFORGE_' + key.upper().replace('.', '_')


def config_path():
    """(the settings file, whether it was asked for by WEAPONFORGE_CONFIG). The file may not exist."""
    given = os.environ.get('WEAPONFORGE_CONFIG')
    if given:
        return native(given, os.getcwd()), True
    return os.path.join(TOOL, 'weaponforge.toml'), False


def native(path, base):
    """`path` in the form this Python can open, made absolute against `base` when relative."""
    path = str(path).strip()
    if not path:
        return ''
    if os.name == 'nt':
        m = re.match(r'^/mnt/([A-Za-z])(/.*)?$', path)
        if m:                                                    # a WSL path read by a Windows program
            path = '%s:%s' % (m.group(1).upper(), (m.group(2) or '/').replace('/', '\\'))
        elif path.startswith('/') and not path.startswith('//') and os.environ.get('WSL_DISTRO_NAME'):
            path = r'\\wsl.localhost\%s%s' % (os.environ['WSL_DISTRO_NAME'], path.replace('/', '\\'))
    else:
        m = re.match(r'^([A-Za-z]):[\\/](.*)$', path)
        if m and os.path.isdir('/mnt/%s' % m.group(1).lower()):    # a Windows path read under WSL
            path = '/mnt/%s/%s' % (m.group(1).lower(), m.group(2).replace('\\', '/'))
    path = os.path.expanduser(path)
    if not os.path.isabs(path) and not re.match(r'^[A-Za-z]:[\\/]|^\\\\', path):
        path = os.path.join(base, path)
    return os.path.normpath(path)


def _read_file():
    path, asked = config_path()
    if not os.path.isfile(path):
        if asked:
            raise SettingsError('WEAPONFORGE_CONFIG names %s, which does not exist' % path)
        return {}, path, False
    with open(path, 'rb') as fh:
        raw = fh.read()
    try:
        import tomllib
        data = tomllib.loads(raw.decode('utf-8'))
    except ImportError:
        data = _small_toml(raw.decode('utf-8'), path)
    except ValueError as e:
        raise SettingsError('%s: %s' % (path, e))
    flat = {}
    for k, v in data.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, dict):
                    raise SettingsError('%s: [%s.%s] is one table too deep' % (path, k, k2))
                flat['%s.%s' % (k, k2)] = v2
        else:
            flat[k] = v
    unknown = sorted(set(flat) - set(KEYS))
    if unknown:
        raise SettingsError('%s: unknown setting%s %s (known: %s)' % (path, 's' if len(unknown) > 1 else '', ', '.join(unknown),
                                                                        ', '.join(KEYS)))
    return flat, path, True


_CACHE = {}


def resolve(reload=False):
    """{key: (value, where it came from)} for every key."""
    if _CACHE and not reload:
        return _CACHE
    flat, path, have = _read_file()
    out = {}
    for key, (default, is_path) in KEYS.items():
        env = os.environ.get(env_name(key))
        if env:
            value, where, base = env, env_name(key), os.getcwd()
        elif have and key in flat and str(flat[key]) != '':
            value, where, base = flat[key], os.path.basename(path), os.path.dirname(path)
        else:
            value, where, base = default, 'default', TOOL
        if not isinstance(value, str):
            raise SettingsError('%s: %s must be a string, got %r' % (where, key, value))
        if is_path and value:
            value = native(value, base)
        out[key] = (value, where)
    _CACHE.clear()
    _CACHE.update(out)
    return out


def get(key):
    return resolve()[key][0]


# ---- a reader for the subset of TOML the settings use, for a python3 older than 3.11 (no tomllib): [table], key = "string" or
# 'string', numbers and true / false, # comments. Anything else is an error that says so.
def _small_toml(text, path):
    data = {}
    table = data
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        m = re.match(r'^\[\s*([A-Za-z0-9_.-]+)\s*\]\s*(#.*)?$', s)
        if m:
            table = data
            for part in m.group(1).split('.'):
                table = table.setdefault(part, {})
            continue
        m = re.match(r'''^([A-Za-z0-9_-]+)\s*=\s*("(?:[^"\\]|\\.)*"|'[^']*'|[-+0-9.eE_]+|true|false)\s*(#.*)?$''', s)
        if not m:
            raise SettingsError('%s line %d: not understood (python3 < 3.11 reads only [table], key = "text" and # comments): %s'
                                % (path, n, s))
        key, v = m.group(1), m.group(2)
        if v.startswith('"'):
            v = re.sub(r'\\(.)', lambda e: {'n': '\n', 't': '\t'}.get(e.group(1), e.group(1)), v[1:-1])
        elif v.startswith("'"):
            v = v[1:-1]
        elif v in ('true', 'false'):
            v = v == 'true'
        else:
            v = float(v.replace('_', '')) if any(c in v for c in '.eE') else int(v.replace('_', ''))
        table[key] = v
    return data


def main(argv):
    try:
        if len(argv) == 2 and argv[0] == 'get':
            if argv[1] not in KEYS:
                print('unknown setting %r (known: %s)' % (argv[1], ', '.join(KEYS)), file=sys.stderr)
                return 2
            print(get(argv[1]))
            return 0
        if argv:
            print(__doc__.split('\n\n')[-1].rstrip(), file=sys.stderr)
            return 2
        values = resolve()
        path, _asked = config_path()
        print('settings file: %s%s' % (path, '' if os.path.isfile(path) else ' (none: defaults and environment only)'))
        for key, (value, where) in values.items():
            print('  %-30s %-40s (%s)' % (key, value or '-', where))
        return 0
    except SettingsError as e:
        print('weaponforge settings: %s' % e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    if '--' in sys.argv:                                  # run by a Blender: blender -b --python settings.py -- [get KEY]
        args = sys.argv[sys.argv.index('--') + 1:]
    else:
        args = [] if 'bpy' in sys.modules else sys.argv[1:]
    sys.exit(main(args))
