# Unreal

An optional adapter in `integrations/unreal/` imports an exported weapon into an Unreal project and reads it back.
**It is untested since it was taken out of the project it was written in**: the scripts ran there (Unreal 5.8, Windows,
started from WSL) on every weapon, but the move changed how they find their folders and how they are started, and nothing
here has run them in an engine since. Its argument rules are tested without Unreal (`tests/test_unreal_args.py`). Expect to
debug the first run.

    bin/weaponforge <id> unreal-import [options]       weapon_import.py, through integrations/unreal/run.sh
    bin/weaponforge <id> unreal-check [options]        weapon_check.py: one OK or MISS line per fact, then RESULT

`integrations/unreal/run.sh` needs two settings, `unreal.editor` (the `UnrealEditor-Cmd` executable; from WSL, the Windows
`UnrealEditor-Cmd.exe`, which it then runs through `cmd.exe` with every path in Windows form) and `unreal.project` (the
`.uproject`), and stops with a message when either is missing. It runs

    <editor> <project> -run=pythonscript -script="<script> <args> --base <unreal.content> --specs <folder>" -unattended -nullrhi -nosplash -NoSound -stdout -abslog=<log>

writes the log to `build/logs/unreal-<import|check>-<time>.log`, prints the script's own lines, and ends with
`unreal run: OK` or `unreal run: FAIL` (the editor's exit code is not 0, or the log has a Python error, a traceback or a
crash). `--specs` is the folder of the weapons' own specs: `spec_dir` if set, else the asset root. It does not stop a second
Unreal process from opening the same project: run one at a time, with the editor closed.

What the import makes, under `<content>/<Name>/` (`/Game/Weapons/<Name>/` by default): `Textures/T_<Name>_BC`, `_N`, `_ORM`
(sRGB; a normal map with its green flipped, since weaponforge writes OpenGL normals; masks), `MI_<Name>` (an instance of the
master material with the three textures), `SKM_<Name>` with its skeleton, sockets and LODs (through Interchange, the only
importer that makes mesh sockets from the FBX's `SOCKET_<name>` joints), `SM_<Name>` with its LODs and box collision, and
`SM_<Name>_<Prop>` for each prop. Both scripts run with `-nullrhi`: **they prove names, counts, sizes and settings, not the
look**.

Its safety rules (`weapon_spec.py`):

- The runner always passes `--base` (the content folder) and `--specs`; the scripts have no default for either and refuse
  to run without them. A lost value never falls back to a folder: an option without its value, an empty one, or an unknown
  one stops the run before anything is touched.
- A weapon's folder is `<content>/<Name>`, or `<content>/_Scratch/<Name>` for a trial; nothing else. A spec made for another
  content folder is refused.
- `--dest` is for trials only: `--dest <content>/_Scratch/<Name>`, and `--remove` with the same `--dest` deletes that
  trial folder again (never anything else).
- A spec that is not one of the weapons' own (exactly `<specs>/<id>.json` or `<specs>/<id>/<id>.json`) can be imported into a
  trial folder only. A weapon built with `--root` writes a spec that already names its trial folder:
  `integrations/unreal/run.sh import --spec <root>/<id>/<id>.json`, then `run.sh check --spec ...`, then
  `run.sh import --spec ... --remove`.
- An asset that exists is not touched unless asked (`--reimport`, `--reimport-meshes`, `--reimport-static`). A mesh
  re-import deletes the mesh and its skeleton and makes new ones; when other assets reference them the import refuses and
  lists them, and `--replace-referenced` goes on anyway. Every source file is looked at before anything is deleted, and any
  warning makes the run fail after listing them.
- A trial run never changes the master material. A real import sets one flag on it, "Used with Skeletal Mesh", once.

**The master material** is not created by the adapter: make it once in your project, at `unreal.master_material`
(`/Game/Materials/M_Weapon` by default). It must be a surface material (opaque, default lit) that exposes, by these names
(all of them settings, [README](../README.md#configure)):

| Parameter | Kind | Wire it to |
|-|-|-|
| `BaseColor` | texture parameter, sampler type Color | Base Color (RGB) |
| `Normal` | texture parameter, sampler type Normal | Normal |
| `ARM` | texture parameter, sampler type Masks | R: Ambient Occlusion, G: Roughness (times `RoughnessScale`), B: Metallic (times `MetallicScale`) |
| `RoughnessScale` | scalar parameter, default 1.0 | multiplies ARM.G |
| `MetallicScale` | scalar parameter, default 1.0 | multiplies ARM.B |

The import sets both scalars to 1.0 on every instance. A missing master is a warning, so the run fails and the meshes keep
the default material.

Putting the weapon into the game (weapon data, the sockets the code reads, animation) is outside the tool:
`PLAYBOOK.md`, "Putting the weapon into the game".

## Importing and checking a new weapon

The two commands for a weapon of your own, as step 6 of [building.md](building.md):

    bin/weaponforge shotgun_g1 unreal-import
    bin/weaponforge shotgun_g1 unreal-check

The import creates `<content>/<Name>/` (the setting `unreal.content`, default `/Game/Weapons`: textures, `MI_<Name>`, `SKM_<Name>` with its sockets and LODs,
`SM_<Name>` with LODs and box collision, the props). The check prints one `OK` or `MISS` line per fact and ends with
`RESULT all facts match the spec`. Both are headless (`-nullrhi`): **they prove names, counts, sizes and settings, not the
look.**

What the import will and will not do (the rules are in `integrations/unreal/weapon_spec.py`, tested by
`tests/test_unreal_args.py`):

- **An asset that exists is not touched** unless you ask: `--reimport` redoes everything, `--reimport-meshes` the skeletal
  mesh, its skeleton and the static meshes, `--reimport-static` the static meshes.
- **A mesh re-import deletes the mesh (and the skeleton) and makes a new one.** On a weapon that other assets already
  reference (animations on its skeleton, a blueprint) the import refuses and lists them; `--replace-referenced` goes on
  anyway. Code that refers to the weapon by path survives; the registry cannot see it, so ask before
  re-importing a weapon that is in use. Copy the weapon's content folder first: nothing here can undo it.
- **Every source file is looked at before anything is deleted**, and **any warning makes the run fail** (`unreal run: FAIL`)
  after listing what went wrong; the log is `build/logs/unreal-<import|check>-<time>.log`.
- **An option without its value, an unknown option, or a folder that is not a weapon folder stops the run** before it
  touches anything.
- **A trial run** goes to `<content>/_Scratch/<Name>` and nowhere else: add
  `--dest <content>/_Scratch/<Name>`, and delete it again with the same `--dest` plus `--remove`. A weapon
  built under `--root` is imported straight from its own spec, which already names its trial folder:
  `integrations/unreal/run.sh import --spec <root>/<id>/<id>.json` (then `run.sh check --spec ...`, then
  `run.sh import --spec ... --remove`). A trial run never changes the shared master material (the setting
  `unreal.master_material`).
