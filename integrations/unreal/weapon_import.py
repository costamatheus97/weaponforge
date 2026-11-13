"""Import a weapon built with weaponforge into an Unreal project. Driven entirely by the weapon's spec (the JSON the tool's
"export" stage writes), so one script serves every weapon. UNTESTED since it was taken out of the project it was written in:
see docs/unreal.md.

    bin/weaponforge <id> unreal-import [options]                      (through integrations/unreal/run.sh, the usual way)
    integrations/unreal/run.sh import --weapon <id> [options]
    integrations/unreal/run.sh import --spec <path to a spec> --dest <base>/_Scratch/<Name>

run.sh adds --base <content folder> and --specs <folder of the weapons' own specs> from the settings (unreal.content;
spec_dir, else the asset root); this script has no default for either and refuses to run without them.

Options (after the weapon):
    --dest <base>/_Scratch/<Name>   a trial run: import there instead of the spec's folder. Only a folder under _Scratch is
                               taken, and a spec that is not one of the weapons' own (a --root build, a copy) can only be
                               imported with it.
    --reimport                 redo everything; --reimport-meshes: the skeletal mesh, its skeleton and the static meshes;
                               --reimport-static: the static meshes. Without one of these, an asset that exists is not touched:
                               not re-imported, not re-bound, not saved.
    --replace-referenced       with a re-import of a weapon the game already uses: go on although assets outside the weapon's
                               folder reference the meshes (a re-import DELETES the mesh and its skeleton and makes new ones)
    --remove                   delete the trial folder again (only ever a folder under <base>/_Scratch/)

Safety (weapon_spec.py holds the rules, tests/test_unreal_args.py tests them):
  * an option without its value, an unknown option, a missing --base or --specs, a folder outside <base>/ or a name with a
    path in it stops the run before anything is touched.
  * every source file is looked at before anything is deleted for a re-import.
  * any warning makes the run FAIL at the end (run.sh reports it), after the list of warnings.

Read the result back with weapon_check.py (same arguments).

Writes, under the weapon's folder only (plus one flag on the shared master material, unreal.master_material, see make_material;
never in a trial run):
    SKM_<Name> (+ _Skeleton)    skeletal mesh with its sockets and LODs
    SM_<Name>                   world copy: its LODs from the file, simple collision boxes from the spec
    SM_<Name>_<Prop>            each prop (a magazine, ...)
    Textures/T_<Name>_BC|N|ORM  sRGB / normal map with flipped green / masks
    MI_<Name>                   instance of the weapon master material
Wiring the weapon into the game (weapon data, sockets the code reads, packaging) is a separate step: PLAYBOOK.md, "Unreal import".

Why it is built this way (each line cost a failed run):
  * the skeletal mesh goes through Interchange, because only Interchange makes mesh sockets from the FBX (a leaf joint named
    SOCKET_<name> becomes socket <name> on its parent bone). Python cannot name a new socket: SocketName and BoneName are read-only.
  * the static meshes go through the legacy FBX factory, which honours FbxImportUI and reads an FBX LodGroup's children as
    LOD0, LOD1, ... (Interchange ignores FbxImportUI when the task has no factory).
  * a mesh is deleted before it is imported again: importing over an existing mesh goes through the reimport handler, which reuses
    the options stored at its first import and ignores this script's.
  * the StaticMeshEditorSubsystem does not exist in a commandlet, so collision is set with GeometryScript.
"""
import os
import sys

import unreal

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:                                  # the commandlet may run the file without __file__: argv[0] is the script
    HERE = os.path.dirname(os.path.abspath(sys.argv[0]))
sys.path.insert(0, HERE)
import weapon_spec as wspec  # noqa: E402  (no Unreal in it: the command line and the spec, shared with the check script)

FLAGS = ("--reimport", "--reimport-meshes", "--reimport-static", "--replace-referenced", "--remove")
POS_TOLERANCE_CM = 0.2
TAG = "weapon_import: "

eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
saved = []
warnings = []


def log(msg):
    unreal.log(TAG + msg)


def warn(msg):
    warnings.append(msg)
    unreal.log_warning(TAG + "WARNING " + msg)


# ----------------------------------------------------------------------------------------------------------------- helpers
def save(asset, path):
    if not eal.save_loaded_asset(asset, only_if_is_dirty=False):
        warn("could not save " + path)
    elif path not in saved:
        saved.append(path)


def drop_asset(path):
    """Delete one of this script's own assets so that the import after it is a fresh one (see the header)."""
    if eal.does_asset_exist(path):
        if eal.delete_asset(path):
            log("deleted %s for a fresh import" % path)
        else:
            warn("could not delete %s before the re-import; it keeps its old import options" % path)


def refuse(msg):
    raise RuntimeError(TAG + "REFUSED, nothing was changed: " + msg)


def outside_users(paths, dest, master):
    """The packages outside the weapon's folder that reference any of these assets; None when the asset registry cannot say.
    (It sees assets only: a path written in C++ is invisible to it.)"""
    try:
        if not eal.find_package_referencers_for_asset(master, False):   # the master has users in this project; none means no data
            return None
        users = set()
        for path in paths:
            for ref in eal.find_package_referencers_for_asset(path, False):
                if not (str(ref) + "/").startswith(dest + "/"):
                    users.add(str(ref))
        return sorted(users)
    except Exception as e:
        log("note: the asset registry could not be asked for referencers (%s)" % e)
        return None


def set_prop(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as e:
        warn("could not set %s on %s: %s" % (name, obj.get_class().get_name(), e))
        return False


# ------------------------------------------------------------------------------------------------------------- textures
def import_texture(u, entry):
    """Import (or import over) one texture, set what kind of texture it is, save it."""
    src = os.path.join(u["texture_dir"], entry["file"])
    dest_dir = u["asset_dir"] + "/Textures"
    path = "%s/%s" % (dest_dir, entry["asset"])
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", src)
    task.set_editor_property("destination_path", dest_dir)
    task.set_editor_property("destination_name", entry["asset"])
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    tools.import_asset_tasks([task])
    tex = eal.load_asset(path)
    if tex is None:
        warn("texture import failed: " + path)
        return None
    if entry["kind"] == "normal":
        # the file is OpenGL (green up), as weaponforge writes it: flipped here
        want = {"compression_settings": unreal.TextureCompressionSettings.TC_NORMALMAP, "srgb": False, "flip_green_channel": True}
    elif entry["kind"] == "masks":
        want = {"compression_settings": unreal.TextureCompressionSettings.TC_MASKS, "srgb": False}
    else:
        want = {"compression_settings": unreal.TextureCompressionSettings.TC_DEFAULT, "srgb": True}
    for prop, val in want.items():
        if tex.get_editor_property(prop) != val:
            tex.set_editor_property(prop, val)
    save(tex, path)
    return tex


def make_material(u, textures, redo, trial):
    """The weapon's material instance: made when it does not exist, redone with --reimport, otherwise only loaded."""
    master = eal.load_asset(u["master_material"])
    if master is None:
        warn("master material %s not found (make it first: docs/unreal.md, the master material); meshes keep the default material" % u["master_material"])
        return None
    # The master was made for static weapon meshes. Without "Used with Skeletal Mesh" a -game run draws the skeletal weapon with the
    # engine's default grid material (the editor sets the flag by itself when it opens the mesh; a game run cannot). This is the one
    # change outside the weapon's folder; it is made once, and never by a trial run.
    if isinstance(master, unreal.Material) and not master.get_editor_property("used_with_skeletal_mesh"):
        if trial:
            log("note: %s has Used with Skeletal Mesh off and a trial run leaves it so (the first real import sets it)" % u["master_material"])
        else:
            recompile = mel.set_material_usage(master, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)   # None: could not be set
            if recompile:
                mel.recompile_material(master)
            if recompile is not None and master.get_editor_property("used_with_skeletal_mesh"):
                save(master, u["master_material"])
                log("set Used with Skeletal Mesh on %s" % u["master_material"])
            else:
                warn("could not set Used with Skeletal Mesh on %s: a game run will draw the skeletal mesh with the default grid. "
                     "Tick it in the material editor (Details, Usage) and save." % u["master_material"])
    name = u["material_instance"]
    path = "%s/%s" % (u["asset_dir"], name)
    if eal.does_asset_exist(path):
        mi = eal.load_asset(path)
        if not redo:
            return mi
    else:
        mi = tools.create_asset(name, u["asset_dir"], unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    if mi is None:
        warn("could not create " + path)
        return None
    if mi.get_editor_property("parent") != master:
        mel.set_material_instance_parent(mi, master)
    for entry in u["textures"]:
        if textures.get(entry["asset"]) is not None:
            mel.set_material_instance_texture_parameter_value(mi, entry["param"], textures[entry["asset"]])
    for pname, value in u["scalar_params"].items():
        mel.set_material_instance_scalar_parameter_value(mi, pname, float(value))
    mel.update_material_instance(mi)
    save(mi, path)
    return mi


# -------------------------------------------------------------------------------------------------------- skeletal mesh
def _task(fbx, dest, name):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("save", False)
    return task


def _interchange_pipeline():
    """The stock assets pipeline, set for this file: keep the authored normals, MikkTSpace tangents, sockets on, nothing else made."""
    pipe = unreal.InterchangeGenericAssetsPipeline()
    set_prop(pipe, "use_source_name_for_asset", True)
    common = pipe.get_editor_property("common_meshes_properties")
    set_prop(common, "recompute_normals", False)          # the mesh carries weighted normals; the bake assumed them
    set_prop(common, "recompute_tangents", True)
    set_prop(common, "use_mikk_t_space", True)
    set_prop(common, "import_sockets", True)              # SOCKET_<name> leaf joints -> mesh sockets
    skel = pipe.get_editor_property("common_skeletal_meshes_and_animations_properties")
    set_prop(skel, "import_only_animations", False)
    set_prop(skel, "use_t0_as_ref_pose", False)
    mesh = pipe.get_editor_property("mesh_pipeline")
    set_prop(mesh, "import_skeletal_meshes", True)
    set_prop(mesh, "import_static_meshes", False)
    set_prop(mesh, "create_physics_asset", False)
    set_prop(mesh, "import_morph_targets", False)
    set_prop(pipe.get_editor_property("animation_pipeline"), "import_animations", False)
    mat = pipe.get_editor_property("material_pipeline")
    set_prop(mat, "import_materials", False)              # one slot, filled with the material instance below
    set_prop(mat.get_editor_property("texture_pipeline"), "import_textures", False)
    return pipe


def _import_skeletal_legacy(fbx, dest, name):
    """Fallback only: the legacy factory imports the mesh and bones but turns the SOCKET_ joints into bones, not sockets."""
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("create_physics_asset", False)
    ui.set_editor_property("skeleton", None)
    skd = ui.get_editor_property("skeletal_mesh_import_data")
    set_prop(skd, "import_uniform_scale", 1.0)
    set_prop(skd, "normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    set_prop(skd, "normal_generation_method", unreal.FBXNormalGenerationMethod.MIKK_T_SPACE)
    set_prop(skd, "use_t0_as_ref_pose", False)
    set_prop(skd, "preserve_smoothing_groups", True)
    set_prop(skd, "import_morph_targets", False)
    set_prop(skd, "convert_scene", True)
    task = _task(fbx, dest, name)
    task.set_editor_property("factory", unreal.FbxFactory())
    task.set_editor_property("options", ui)
    tools.import_asset_tasks([task])
    return eal.load_asset("%s/%s" % (dest, name))


def import_skeletal(u):
    """A fresh import: an existing mesh and its skeleton are deleted first (see the header)."""
    name, dest = u["skeletal"]["name"], u["asset_dir"]
    path = "%s/%s" % (dest, name)
    fbx = os.path.join(u["export_dir"], u["skeletal"]["fbx"])
    drop_asset(path)
    drop_asset(path + "_Skeleton")
    mesh = None
    try:
        pipe = _interchange_pipeline()                    # held in a variable: the override keeps only a soft path to it
        override = unreal.InterchangePipelineStackOverride()
        override.add_pipeline(pipe)
        task = _task(fbx, dest, name)                     # no factory: the engine's importer for .fbx, which is Interchange
        task.set_editor_property("options", override)
        tools.import_asset_tasks([task])
        mesh = eal.load_asset(path)
    except Exception as e:
        warn("Interchange import of %s raised %s" % (name, e))
    if mesh is None or not isinstance(mesh, unreal.SkeletalMesh):
        warn("Interchange made no skeletal mesh for %s; falling back to the legacy FBX factory. The sockets will then be MISSING "
             "(they come in as bones named SOCKET_<name>): import by hand with Interchange, Import Sockets on, or add them from the spec." % name)
        mesh = _import_skeletal_legacy(fbx, dest, name)
    if mesh is None:
        warn("no asset for %s after both importers" % name)
    return mesh


def set_skeletal_material(mesh, mi):
    if mi is None:
        return
    try:
        mats = list(mesh.get_editor_property("materials"))
        for m in mats:
            m.set_editor_property("material_interface", mi)
        mesh.set_editor_property("materials", mats)
    except Exception as e:
        warn("could not assign %s to the skeletal mesh: %s" % (mi.get_name(), e))


def check_sockets(mesh, spec):
    """The sockets come from the FBX. Report each against the spec; a missing one cannot be made from Python."""
    found = 0
    for s in spec["sockets"]:
        name = s["name"]
        sock = None
        try:
            sock = mesh.find_socket(name)
        except Exception as e:
            warn("find_socket(%s) raised %s" % (name, e))
        if sock is None:
            warn("socket %s is missing: add it in the Skeletal Mesh editor on bone %s at %s, rotation (pitch, yaw, roll) %s"
                 % (name, s["bone"], s["relative_ue"], s["rotation_ue_pitch_yaw_roll"]))
            continue
        found += 1
        try:
            loc = sock.get_editor_property("relative_location")
            rot = sock.get_editor_property("relative_rotation")
            bone = str(sock.get_editor_property("bone_name"))
            want = s["relative_ue"]
            off = max(abs(loc.x - want[0]), abs(loc.y - want[1]), abs(loc.z - want[2]))
            pitch, yaw, roll = s["rotation_ue_pitch_yaw_roll"]
            turn = max(abs(((a - b + 180.0) % 360.0) - 180.0) for a, b in ((rot.pitch, pitch), (rot.yaw, yaw), (rot.roll, roll)))
            if bone != s["bone"] or off > POS_TOLERANCE_CM or turn > 0.5:
                warn("socket %s: on %s at (%.3f, %.3f, %.3f) rotation (%.2f, %.2f, %.2f); spec: on %s at %s rotation %s"
                     % (name, bone, loc.x, loc.y, loc.z, rot.pitch, rot.yaw, rot.roll, s["bone"], want, [pitch, yaw, roll]))
        except Exception as e:
            log("note: socket %s exists but could not be read back (%s)" % (name, e))
    return found


def import_skeletal_lods(mesh, u):
    """The LODs are authored files on the same bones (Python cannot set a skeletal LOD's reduction share)."""
    sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    files = u["skeletal"].get("lods", [])
    made = 0
    for index, name in enumerate(files, start=1):
        fbx = os.path.join(u["export_dir"], name)
        if not os.path.isfile(fbx):
            warn("missing " + fbx)
            continue
        try:
            got = sub.import_lod(mesh, index, fbx)
            if got == index:
                made += 1
            else:
                warn("import_lod returned %s for LOD%d (%s)" % (got, index, fbx))
        except Exception as e:
            warn("import_lod failed for LOD%d: %s" % (index, e))
    try:
        count = sub.get_lod_count(mesh)
    except Exception:
        count = 1 + made
    if made < len(files):
        warn("the skeletal mesh has %d LODs; import the LOD files by hand (LOD Import in the mesh editor) from %s" % (count, u["export_dir"]))
    return count


def check_skeletal(mesh, spec):
    ok = True
    try:
        b = mesh.get_bounds()
        lo = [b.origin.x - b.box_extent.x, b.origin.y - b.box_extent.y, b.origin.z - b.box_extent.z]
        hi = [b.origin.x + b.box_extent.x, b.origin.y + b.box_extent.y, b.origin.z + b.box_extent.z]
        for got, want, label in ((lo, spec["bounds_ue_cm"]["min"], "min"), (hi, spec["bounds_ue_cm"]["max"], "max")):
            for axis in range(3):
                if abs(got[axis] - want[axis]) > POS_TOLERANCE_CM + 0.3:        # skinned bounds are padded a little
                    warn("bounds %s %s: %.2f, spec %.2f (a factor of 100 means the unit scale was lost)" % (label, "XYZ"[axis], got[axis], want[axis]))
                    ok = False
    except Exception as e:
        log("note: bounds not readable from Python (%s)" % e)
    return ok


# -------------------------------------------------------------------------------------------------------- static meshes
def set_box_collision(mesh, boxes):
    """Simple collision from the spec's boxes (none when the list is empty); returns the number of shapes the mesh then has.
    Each box is one shell of a proxy mesh, and the generator fits one oriented box to each shell."""
    gc = unreal.GeometryScript_Collision
    sopts = unreal.GeometryScriptSetStaticMeshCollisionOptions()
    if not boxes:
        gc.set_simple_collision_of_static_mesh(unreal.GeometryScriptSimpleCollision(), mesh, unreal.GeometryScriptSetSimpleCollisionOptions(), sopts)
    else:
        proxy = unreal.new_object(unreal.DynamicMesh)
        for box in boxes:
            where = unreal.Transform(location=unreal.Vector(*box["centre_ue"]), rotation=unreal.Rotator(roll=0.0, pitch=box["pitch_deg"], yaw=0.0))
            size = box["size_cm"]
            made = unreal.GeometryScript_Primitives.append_box(proxy, unreal.GeometryScriptPrimitiveOptions(), where, size[0], size[1], size[2], 0, 0, 0,
                                                               unreal.GeometryScriptPrimitiveOriginMode.CENTER)
            proxy = made[0] if isinstance(made, tuple) else made
        opts = unreal.GeometryScriptCollisionFromMeshOptions()
        opts.set_editor_property("emit_transaction", False)
        opts.set_editor_property("method", unreal.GeometryScriptCollisionGenerationMethod.ORIENTED_BOXES)
        opts.set_editor_property("min_thickness", 0.1)                       # a thin box (a base plate) would otherwise be fattened to 1 cm
        opts.set_editor_property("remove_fully_contained_shapes", False)
        gc.set_static_mesh_collision_from_mesh(proxy, mesh, opts, sopts)
    return int(gc.get_simple_collision_shape_count(gc.get_simple_collision_from_static_mesh(mesh)))


def import_static(u, entry, boxes):
    """A fresh import (an existing mesh is deleted first). boxes: the spec's collision boxes (an empty list for none)."""
    name, dest, lods = entry["name"], u["asset_dir"], len(entry["lods_in_fbx"])
    path = "%s/%s" % (dest, name)
    fbx = os.path.join(u["export_dir"], entry["fbx"])
    drop_asset(path)
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    smd = ui.get_editor_property("static_mesh_import_data")
    set_prop(smd, "combine_meshes", True)
    set_prop(smd, "import_uniform_scale", 1.0)
    set_prop(smd, "transform_vertex_to_absolute", False)       # keep the authored origin
    set_prop(smd, "bake_pivot_in_vertex", False)
    set_prop(smd, "auto_generate_collision", False)
    set_prop(smd, "build_nanite", False)
    set_prop(smd, "normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    set_prop(smd, "normal_generation_method", unreal.FBXNormalGenerationMethod.MIKK_T_SPACE)
    set_prop(smd, "import_mesh_lods", lods > 1)                # bImportMeshLODs: the LodGroup's children become LOD0, LOD1, ...
    task = _task(fbx, dest, name)
    task.set_editor_property("factory", unreal.FbxFactory())   # the legacy FBX factory honours FbxImportUI
    task.set_editor_property("options", ui)
    tools.import_asset_tasks([task])
    mesh = eal.load_asset(path)
    if mesh is None:
        warn("FBX import produced no asset for " + name)
        return None
    try:
        shapes = set_box_collision(mesh, boxes)
        if shapes != len(boxes):
            warn("%s has %d simple collision shapes, wanted %d" % (name, shapes, len(boxes)))
    except Exception as e:
        warn("collision setup failed on %s: %s" % (name, e))
    try:
        got = mesh.get_num_lods()
        if got != lods:
            warn("%s has %d LODs, wanted %d" % (name, got, lods))
    except Exception as e:
        log("note: the LOD count of %s is not readable (%s)" % (name, e))
    return mesh


# --------------------------------------------------------------------------------------------------------------------- main
def remove(dest, base):
    if not wspec.is_trial(dest, base):
        refuse("--remove only deletes a trial folder, %s<Name> (got %s)" % (wspec.scratch(base), dest))
    if eal.does_directory_exist(dest):
        ok = eal.delete_directory(dest)
        log("removed %s: %s" % (dest, "done" if ok else "FAILED"))
        if not ok:
            raise RuntimeError(TAG + "could not remove " + dest)
    else:
        log("nothing to remove at " + dest)
    parent = wspec.scratch(base).rstrip("/")
    if eal.does_directory_exist(parent) and not eal.list_assets(parent, recursive=True, include_folder=False):
        eal.delete_directory(parent)


def main():
    problem = None
    try:
        spec, spec_path, flags = wspec.load(sys.argv, FLAGS, writes=True)
    except wspec.ArgError as e:
        problem = str(e)
    if problem:                     # raised out here, so the log shows one error and not a chain of two
        refuse(problem)
    u = spec["unreal"]
    dest = u["asset_dir"]
    trial = wspec.is_trial(dest, u["content"])
    if "--remove" in flags:
        if len(flags) > 1:
            refuse("--remove goes alone, not with %s" % ", ".join(sorted(flags - {"--remove"})))
        remove(dest, u["content"])
        return
    reimport = "--reimport" in flags
    reimport_meshes = reimport or "--reimport-meshes" in flags
    reimport_static = reimport_meshes or "--reimport-static" in flags
    log("%s from %s into %s%s" % (spec["name"], spec_path, dest, " (a trial run)" if trial else ""))

    # ---- what this run will import, and whether it can: decided before anything is deleted
    asset = lambda name: "%s/%s" % (dest, name)
    skm_name = u["skeletal"]["name"]
    do_textures = [e for e in u["textures"] if reimport or not eal.does_asset_exist("%s/Textures/%s" % (dest, e["asset"]))]
    do_skeletal = reimport_meshes or not eal.does_asset_exist(asset(skm_name))
    do_statics = [e for e in u["statics"] if reimport_static or not eal.does_asset_exist(asset(e["name"]))]
    sources = [os.path.join(u["texture_dir"], e["file"]) for e in do_textures]
    if do_skeletal:
        sources += [os.path.join(u["export_dir"], f) for f in [u["skeletal"]["fbx"]] + list(u["skeletal"].get("lods", []))]
    sources += [os.path.join(u["export_dir"], e["fbx"]) for e in do_statics]
    problems = wspec.source_problems(sources)
    if problems:
        refuse("%d source files cannot be imported: %s" % (len(problems), "; ".join(problems)))
    replaced = [p for p in ([asset(skm_name), asset(skm_name) + "_Skeleton"] if do_skeletal else []) + [asset(e["name"]) for e in do_statics]
                if eal.does_asset_exist(p)]
    if replaced and not trial and "--replace-referenced" not in flags:
        users = outside_users(replaced, dest, u["master_material"])
        if users is None:
            refuse("a re-import deletes and re-creates %s, and the asset registry cannot say whether anything outside %s uses them. "
                   "Copy the weapon's folder first, then add --replace-referenced." % (", ".join(replaced), dest))
        if users:
            refuse("a re-import deletes and re-creates %s, and these assets outside %s reference them: %s. Their references would "
                   "be cut. Copy the weapon's folder first, then add --replace-referenced (and re-point those assets afterwards)."
                   % (", ".join(replaced), dest, ", ".join(users)))
    left = [e["asset"] for e in u["textures"] if e not in do_textures] + ([] if do_skeletal else [skm_name]) \
        + [e["name"] for e in u["statics"] if e not in do_statics]

    if not eal.does_directory_exist(dest):
        eal.make_directory(dest)
    textures = {}
    for entry in u["textures"]:
        if entry in do_textures:
            textures[entry["asset"]] = import_texture(u, entry)
        else:
            textures[entry["asset"]] = eal.load_asset("%s/Textures/%s" % (dest, entry["asset"]))
    mi_existed = eal.does_asset_exist(asset(u["material_instance"]))
    mi = make_material(u, textures, reimport, trial)
    if mi_existed and not reimport:
        left.append(u["material_instance"])

    # An asset that exists and is not re-imported is only read: its material and its file are left as they are.
    if do_skeletal:
        skm = import_skeletal(u)
    else:
        skm = eal.load_asset(asset(skm_name))
    if skm is not None:
        sockets = check_sockets(skm, spec)
        if do_skeletal:
            set_skeletal_material(skm, mi)
            lods = import_skeletal_lods(skm, u)
            set_skeletal_material(skm, mi)                # a LOD import can add a slot
        else:
            lods = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem).get_lod_count(skm)
        ok = check_skeletal(skm, spec)
        if do_skeletal:
            save(skm, asset(skm_name))
            try:
                skel = skm.get_editor_property("skeleton")
                if skel is not None:
                    save(skel, skel.get_path_name().split(".")[0])
            except Exception as e:
                warn("could not save the skeleton asset (%s): save it from the editor" % e)
        log("%s: %d of %d sockets, %d LODs, size check %s" % (skm_name, sockets, len(spec["sockets"]), lods, "passed" if ok else "FAILED"))

    for entry in do_statics:
        boxes = spec["meshes"][entry["name"]]["collision"]["boxes"] if entry.get("collision") else []
        sm = import_static(u, entry, boxes)
        if sm is not None:
            if mi is not None:
                sm.set_material(0, mi)
            save(sm, asset(entry["name"]))

    log("saved %d assets: %s" % (len(saved), ", ".join(saved) or "none"))
    if left:
        log("left as they are (they exist, and no re-import was asked for): " + ", ".join(left))
    if warnings:
        log("%d warnings:" % len(warnings))
        for w in warnings:
            log("  - " + w)
        raise RuntimeError(TAG + "FAILED with %d warnings (listed above in the log). What was imported before the failure is saved; "
                           "fix the cause and run again with the re-import option for what failed." % len(warnings))
    log("no warnings")


main()
