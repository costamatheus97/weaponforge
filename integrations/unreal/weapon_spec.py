"""What weapon_import.py and weapon_check.py share: the command line and the weapon's spec.

No Unreal in here, so the rules that keep an import away from the wrong folder are tested outside the engine
(tests/test_unreal_args.py). The runner (run.sh) always passes --base and --specs from the settings; the scripts have no
default for either. The rules:

  * --base (the content folder for weapons, e.g. /Game/Weapons) and --specs (the folder the trusted specs are in) are
    required. A run without them, or with an empty value, stops: nothing falls back to a built-in folder.
  * an option that takes a value and has none (or an empty one) stops the run. A lost --dest must never turn a trial run into a
    run on the weapon's real folder.
  * a weapon's folder is <base>/<Name>, or <base>/_Scratch/<Name> for a trial; nothing else. A spec that names its content
    folder ("content", written by weaponforge) must name the same --base.
  * --dest is for trials: only a folder under <base>/_Scratch.
  * when the run writes: a spec that is not exactly <specs>/<id>.json or <specs>/<id>/<id>.json (a test copy, a scratch root)
    goes into _Scratch only.
  * every asset and file name in the spec is a plain name: no folders, no dots that walk upward.
"""
import json
import os
import re

VALUED = ("--weapon", "--spec", "--dest", "--base", "--specs")

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_WEAPON_ID = re.compile(r"^[a-z_][a-z0-9_]*$")
_FILE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$")
_BASE = re.compile(r"^/Game(/[A-Za-z][A-Za-z0-9_]*)+$")


def scratch(base):
    """The trial folder under a content folder: <base>/_Scratch/."""
    return base + "/_Scratch/"


def _folder_re(base):
    return re.compile("^" + re.escape(base) + r"/(_Scratch/)?[A-Za-z][A-Za-z0-9_]*$")


def _trial_re(base):
    return re.compile("^" + re.escape(base) + r"/_Scratch/[A-Za-z][A-Za-z0-9_]*$")


class ArgError(RuntimeError):
    pass


def parse(argv, flags=()):
    """({'--weapon': value, ...}, {flags given}) from argv (argv[0] is the script). Raises ArgError on anything it does not know."""
    values, given = {}, set()
    tokens = [str(t) for t in argv[1:]]
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in VALUED:
            v = tokens[i + 1] if i + 1 < len(tokens) else ""
            if not v or v.startswith("--"):
                raise ArgError("%s needs a value and has none. Nothing was done." % t)
            if t in values:
                raise ArgError("%s is given twice" % t)
            values[t] = v
            i += 2
        elif t in flags:
            given.add(t)
            i += 1
        else:
            raise ArgError("unknown argument %r (known: %s)" % (t, ", ".join(list(VALUED) + sorted(flags))))
    return values, given


def is_trial(folder, base):
    return bool(_trial_re(base).match(folder))


def _same_file(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def trusted_paths(spec_dir, weapon_id):
    """Where a weapon's own spec may be: <specs>/<id>.json (a spec folder) or <specs>/<id>/<id>.json (beside its files)."""
    return [os.path.join(spec_dir, weapon_id + ".json"), os.path.join(spec_dir, weapon_id, weapon_id + ".json")]


def load(argv, flags=(), writes=False):
    """(spec with a complete "unreal" block, the spec's path, {flags given}). Specs without an "unreal" block get one derived
    from their names, so every weapon reads the same way."""
    values, given = parse(argv, flags)
    for need in ("--base", "--specs"):
        if need not in values:
            raise ArgError("%s is required (the runner passes it from the settings); nothing was done" % need)
    one_slash = lambda text: text[:-1] if text.endswith("/") else text       # one trailing slash is a habit; two are a mistake
    base = one_slash(values["--base"])
    if not _BASE.match(base) or "/_Scratch" in base:
        raise ArgError("--base must be a content folder like /Game/Weapons: got %r" % values["--base"])
    spec_dir = values["--specs"]
    if ("--weapon" in values) == ("--spec" in values):
        raise ArgError("give exactly one of --weapon <id> and --spec <path>")
    if "--weapon" in values:
        if not _WEAPON_ID.match(values["--weapon"]):
            raise ArgError("--weapon is a weapon id (lower case letters, digits, _), not %r" % values["--weapon"])
        found = [p for p in trusted_paths(spec_dir, values["--weapon"]) if os.path.isfile(p)]
        if len(found) > 1:
            raise ArgError("two specs for %s: %s. Remove the one that is not current." % (values["--weapon"], " and ".join(found)))
        path = found[0] if found else trusted_paths(spec_dir, values["--weapon"])[0]
    else:
        path = values["--spec"]
    if not os.path.isfile(path):
        raise ArgError("no spec at %s (the weaponforge stage \"export\" writes it)" % path)
    with open(path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)

    name = spec["name"]
    u = dict(spec.get("unreal") or {})
    if "content" in u and one_slash(str(u["content"])) != base:
        raise ArgError("the spec was made for the content folder %r, and this run's --base is %r: export it again with the same "
                       "unreal.content, or run with that base" % (u["content"], base))
    u.setdefault("asset_dir", spec.get("asset_dir", base + "/" + name))
    if not u.get("master_material"):
        raise ArgError("the spec names no master material (unreal.master_material): export it again")
    u.setdefault("material_instance", "MI_" + name)
    u.setdefault("scalar_params", {"RoughnessScale": 1.0, "MetallicScale": 1.0})
    u.setdefault("export_dir", (spec.get("source") or {}).get("export_dir", ""))
    u.setdefault("texture_dir", (spec.get("textures") or {}).get("dir", os.path.join(os.path.dirname(u["export_dir"]), "textures")))
    u.setdefault("textures", [{"asset": "T_%s_%s" % (name, sfx), "file": "T_%s_%s.png" % (name, sfx), "param": param, "kind": kind}
                              for sfx, param, kind in (("BC", "BaseColor", "colour"), ("N", "Normal", "normal"), ("ORM", "ARM", "masks"))])
    if "skeletal" not in u:
        skm = next(k for k in spec["meshes"] if k.startswith("SKM_"))
        u["skeletal"] = {"name": skm, "fbx": spec["meshes"][skm]["fbx"], "lods": [l["fbx"] for l in spec.get("lods", [])]}
    if "statics" not in u:
        u["statics"] = []
        for key, mesh in spec["meshes"].items():
            if key.startswith("SM_"):
                u["statics"].append({"name": key, "fbx": mesh["fbx"], "lods_in_fbx": mesh.get("lods_in_fbx") or [mesh["triangles"]],
                                     "collision": "collision" in mesh, "bounds": "own" if "bounds_ue_cm" in mesh else "weapon"})

    # ---- names: plain ones only
    assets = [name, u["material_instance"], u["skeletal"]["name"]] + [e["name"] for e in u["statics"]] + [e["asset"] for e in u["textures"]]
    bad = [a for a in assets if not _NAME.match(str(a))]
    files = [u["skeletal"]["fbx"]] + list(u["skeletal"].get("lods", [])) + [e["fbx"] for e in u["statics"]] + [e["file"] for e in u["textures"]]
    bad += [f for f in files if not _FILE.match(str(f)) or ".." in str(f)]
    if bad:
        raise ArgError("the spec names assets or files that are not plain names: %s" % ", ".join(repr(b) for b in bad))
    if not str(u["master_material"]).startswith("/Game/"):
        raise ArgError("the spec's master material is not a /Game/ path: %r" % u["master_material"])

    # ---- the folder
    folder = one_slash(str(u["asset_dir"]))
    if not _folder_re(base).match(folder):
        raise ArgError("the spec's asset folder must be %s/<Name> (or %s<Name>): got %r" % (base, scratch(base), u["asset_dir"]))
    if "--dest" in values:
        folder = one_slash(values["--dest"])
        if not is_trial(folder, base):
            raise ArgError("--dest is for trial runs and takes only a folder under %s<Name>: got %r" % (scratch(base), values["--dest"]))
    stem = os.path.splitext(os.path.basename(path))[0]
    own = _WEAPON_ID.match(stem) and any(_same_file(path, p) for p in trusted_paths(spec_dir, stem))
    if writes and not is_trial(folder, base) and not own:
        raise ArgError("%s is not one of the weapons' own specs (%s): it can only be imported into a trial folder. "
                       "Add --dest %s%s" % (path, " or ".join(trusted_paths(spec_dir, "<id>")), scratch(base), name))
    u["asset_dir"] = folder
    u["content"] = base
    spec["unreal"] = u
    return spec, path, given


def source_problems(paths):
    """What is wrong with the files an import is about to read: [text]. Looked at BEFORE anything is deleted for a re-import."""
    out = []
    for p in paths:
        if not os.path.isfile(p):
            out.append("missing: " + p)
            continue
        if os.path.getsize(p) == 0:
            out.append("empty: " + p)
            continue
        if p.lower().endswith(".fbx"):
            with open(p, "rb") as fh:
                head = fh.read(20)
            if not (head.startswith(b"Kaydara FBX Binary") or head.startswith(b"; FBX")):
                out.append("not an FBX file (half written?): " + p)
    return out
