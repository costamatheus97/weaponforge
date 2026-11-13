"""Read an imported weapon's assets back and compare them with its spec. Saves nothing.

    bin/weaponforge <id> unreal-check [--dest <base>/_Scratch/<Name>]          (through integrations/unreal/run.sh)
    integrations/unreal/run.sh check --spec <path> [--dest <base>/_Scratch/<Name>]

UNTESTED since it was taken out of the project it was written in: see docs/unreal.md. run.sh adds --base and --specs.

Prints one "weapon_check: OK|MISS|NOTE|INFO <what>: <detail>" line per fact and raises at the end when anything is a MISS, so
run.sh reports the run as failed. NOTE marks a fact Python could not read (not a failure), INFO one that is neither right nor
wrong (who uses the weapon). Find the lines with
    grep "weapon_check: " <the log run.sh names>
The command line follows the importer's rules (weapon_spec.py): an option without its value or an unknown one stops it.

It cannot see the weapon: a commandlet runs with -nullrhi. The look (and whether the normal map's green is the right way up) is
checked by eye in the editor or a game run: PLAYBOOK.md, "What nobody has verified".
"""
import math
import os
import sys

import unreal

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:                                  # the commandlet may run the file without __file__: argv[0] is the script
    HERE = os.path.dirname(os.path.abspath(sys.argv[0]))
sys.path.insert(0, HERE)
import weapon_spec as wspec  # noqa: E402  (no Unreal in it: the command line and the spec, shared with the import script)

TOL_CM = 0.05
TOL_DEG = 0.5
TAG = "weapon_check: "

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
misses = []


def say(kind, what, detail=""):
    unreal.log("%s%s %s%s" % (TAG, kind, what, (": " + detail) if detail else ""))
    if kind == "MISS":
        misses.append(what)


def verdict(ok, what, detail=""):
    say("OK" if ok else "MISS", what, detail)


def load(dest, name, cls):
    path = "%s/%s" % (dest, name)
    obj = eal.load_asset(path) if eal.does_asset_exist(path) else None
    verdict(obj is not None and isinstance(obj, cls), "asset " + path, type(obj).__name__)
    return obj


def angle_off(a, b):
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def check_skeletal(spec, mi):
    u = spec["unreal"]
    name, dest = u["skeletal"]["name"], u["asset_dir"]
    skm = load(dest, name, unreal.SkeletalMesh)
    if skm is None:
        return
    sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    lib = unreal.SkeletalMeshEditorSubsystem

    # ---- bones: walk the tree down from the spec's root
    want = {b["name"]: b["parent"] for b in spec["bones"]}
    root = next(n for n, p in want.items() if p is None)
    try:
        found, stack = {root: None}, [root]
        while stack:
            bone = stack.pop()
            for child in lib.get_bone_children(skm, bone):
                found[str(child)] = bone
                stack.append(str(child))
        socket_bones = sorted(n for n in found if n.startswith("SOCKET_"))
        verdict(not socket_bones, "no socket joint came in as a bone", ", ".join(socket_bones) or "none")
        order = list(want)
        verdict(found == want, "bones", "%d: %s" % (len(found), ", ".join("%s<%s" % (n, p) for n, p in
                                                                         sorted(found.items(), key=lambda kv: order.index(kv[0]) if kv[0] in want else 99))))
    except Exception as e:
        say("NOTE", "bones not readable", str(e))

    # ---- sockets
    try:
        got = {}
        for i in range(skm.num_sockets()):
            s = skm.get_socket_by_index(i)
            got[str(s.get_editor_property("socket_name"))] = s
        verdict(set(got) == {s["name"] for s in spec["sockets"]}, "socket names", ", ".join(sorted(got)) or "none")
        for s in spec["sockets"]:
            sock = got.get(s["name"])
            if sock is None:
                say("MISS", "socket " + s["name"], "missing")
                continue
            loc = sock.get_editor_property("relative_location")
            rot = sock.get_editor_property("relative_rotation")
            scale = sock.get_editor_property("relative_scale")
            bone = str(sock.get_editor_property("bone_name"))
            off = max(abs(loc.x - s["relative_ue"][0]), abs(loc.y - s["relative_ue"][1]), abs(loc.z - s["relative_ue"][2]))
            pitch, yaw, roll = s["rotation_ue_pitch_yaw_roll"]
            turn = max(angle_off(rot.pitch, pitch), angle_off(rot.yaw, yaw), angle_off(rot.roll, roll))
            unit = max(abs(scale.x - 1.0), abs(scale.y - 1.0), abs(scale.z - 1.0))
            verdict(bone == s["bone"] and off <= TOL_CM and turn <= TOL_DEG and unit <= 1.0e-3, "socket " + s["name"],
                    "on %s at (%.3f, %.3f, %.3f), rotation (%.2f, %.2f, %.2f), scale off %.4f; position off %.4f cm, rotation off %.3f deg"
                    % (bone, loc.x, loc.y, loc.z, rot.pitch, rot.yaw, rot.roll, unit, off, turn))
    except Exception as e:
        say("NOTE", "sockets not readable", str(e))

    # ---- LODs
    try:
        count = sub.get_lod_count(skm)
        verts = [sub.get_num_verts(skm, i) for i in range(count)]
        falling = all(verts[i] > verts[i + 1] for i in range(len(verts) - 1))
        verdict(count == 1 + len(spec.get("lods", [])) and falling, "skeletal LODs", "%d LODs, render vertices %s (spec triangles %s)"
                % (count, verts, [spec["meshes"][name]["triangles"]] + [l["triangles"] for l in spec.get("lods", [])]))
        sections = [sub.get_num_sections(skm, i) for i in range(count)]
        verdict(all(n == 1 for n in sections), "one section per LOD", str(sections))
    except Exception as e:
        say("NOTE", "LODs not readable", str(e))

    # ---- size and material
    try:
        b = skm.get_bounds()
        lo = [b.origin.x - b.box_extent.x, b.origin.y - b.box_extent.y, b.origin.z - b.box_extent.z]
        hi = [b.origin.x + b.box_extent.x, b.origin.y + b.box_extent.y, b.origin.z + b.box_extent.z]
        worst = max(max(abs(lo[i] - spec["bounds_ue_cm"]["min"][i]), abs(hi[i] - spec["bounds_ue_cm"]["max"][i])) for i in range(3))
        verdict(worst <= 0.5, "skeletal bounds", "min (%.2f, %.2f, %.2f) max (%.2f, %.2f, %.2f); largest difference from the spec %.3f cm"
                % (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2], worst))
    except Exception as e:
        say("NOTE", "skeletal bounds not readable", str(e))
    try:
        mats = list(skm.get_editor_property("materials"))
        names = [m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else "None" for m in mats]
        verdict(len(mats) == 1 and mi is not None and mats[0].get_editor_property("material_interface") == mi, "skeletal material", str(names))
    except Exception as e:
        say("NOTE", "skeletal material not readable", str(e))
    try:
        skel = skm.get_editor_property("skeleton")
        verdict(skel is not None and skel.get_path_name().startswith(dest + "/"), "skeleton asset", skel.get_path_name() if skel else "None")
        phys = skm.get_editor_property("physics_asset")
        say("OK", "physics asset", phys.get_path_name() if phys else "none (as intended)")
    except Exception as e:
        say("NOTE", "skeleton not readable", str(e))


def box_corners(box):
    """The eight corners of one of the spec's collision boxes (Unreal: a pitch p turns +X toward +Z)."""
    p = math.radians(box["pitch_deg"])
    ax, az = (math.cos(p), 0.0, math.sin(p)), (-math.sin(p), 0.0, math.cos(p))
    c, (sx, sy, sz) = box["centre_ue"], box["size_cm"]
    out = []
    for i in (-0.5, 0.5):
        for j in (-0.5, 0.5):
            for k in (-0.5, 0.5):
                out.append((c[0] + ax[0] * sx * i + az[0] * sz * k, c[1] + sy * j, c[2] + ax[2] * sx * i + az[2] * sz * k))
    return out


def check_static(dest, name, mi, want_lod_tris, boxes, want_lo, want_hi):
    sm = load(dest, name, unreal.StaticMesh)
    if sm is None:
        return
    try:
        count = sm.get_num_lods()
        tris = [sm.get_num_triangles(i) for i in range(count)]
        verdict(tris == want_lod_tris, name + " LODs", "%d LODs, triangles %s (spec %s)" % (count, tris, want_lod_tris))
    except Exception as e:
        say("NOTE", name + " LODs not readable", str(e))
    try:
        gc = unreal.GeometryScript_Collision
        shapes = gc.get_simple_collision_from_static_mesh(sm)
        n = int(gc.get_simple_collision_shape_count(shapes))
        verdict(n == len(boxes), name + " simple collision shapes", "%d (spec %d)" % (n, len(boxes)))
        if boxes and n:
            # the stored shapes as a mesh: its bounds must be the bounds of the spec's boxes
            dm = unreal.new_object(unreal.DynamicMesh)
            made = unreal.GeometryScript_Primitives.append_simple_collision_shapes(dm, unreal.GeometryScriptPrimitiveOptions(), unreal.Transform(), shapes,
                                                                                  unreal.GeometryScriptSimpleCollisionTriangulationOptions())
            dm = made[0] if isinstance(made, tuple) else made
            bb = unreal.GeometryScript_MeshQueries.get_mesh_bounding_box(dm)
            corners = [c for box in boxes for c in box_corners(box)]
            lo = [min(c[i] for c in corners) for i in range(3)]
            hi = [max(c[i] for c in corners) for i in range(3)]
            got_lo, got_hi = [bb.min.x, bb.min.y, bb.min.z], [bb.max.x, bb.max.y, bb.max.z]
            worst = max(max(abs(got_lo[i] - lo[i]), abs(got_hi[i] - hi[i])) for i in range(3))
            verdict(worst <= TOL_CM, name + " collision extent", "min (%.3f, %.3f, %.3f) max (%.3f, %.3f, %.3f); largest difference from the spec's boxes %.4f cm"
                    % (got_lo[0], got_lo[1], got_lo[2], got_hi[0], got_hi[1], got_hi[2], worst))
    except Exception as e:
        say("NOTE", name + " collision not readable", str(e))
    try:
        box = sm.get_bounding_box()
        lo, hi = [box.min.x, box.min.y, box.min.z], [box.max.x, box.max.y, box.max.z]
        worst = max(max(abs(lo[i] - want_lo[i]), abs(hi[i] - want_hi[i])) for i in range(3))
        verdict(worst <= TOL_CM, name + " bounds", "min (%.3f, %.3f, %.3f) max (%.3f, %.3f, %.3f); largest difference %.4f cm"
                % (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2], worst))
    except Exception as e:
        say("NOTE", name + " bounds not readable", str(e))
    try:
        mat = sm.get_material(0)
        verdict(mi is not None and mat == mi, name + " material", mat.get_name() if mat else "None")
    except Exception as e:
        say("NOTE", name + " material not readable", str(e))
    try:
        nanite = sm.get_editor_property("nanite_settings").get_editor_property("enabled")
        verdict(not nanite, name + " Nanite off", str(bool(nanite)))
    except Exception as e:
        say("NOTE", name + " Nanite setting not readable", str(e))


def check_textures(spec, mi):
    u = spec["unreal"]
    size_want = (spec.get("textures") or {}).get("size")
    facts_for = {"colour": (True, unreal.TextureCompressionSettings.TC_DEFAULT, False),
                 "normal": (False, unreal.TextureCompressionSettings.TC_NORMALMAP, True),
                 "masks": (False, unreal.TextureCompressionSettings.TC_MASKS, False)}
    for entry in u["textures"]:
        name = entry["asset"]
        path = "%s/Textures/%s" % (u["asset_dir"], name)
        tex = eal.load_asset(path) if eal.does_asset_exist(path) else None
        if tex is None:
            say("MISS", "asset " + path, "missing")
            continue
        try:
            size = (tex.blueprint_get_size_x(), tex.blueprint_get_size_y())
            facts = (tex.get_editor_property("srgb"), tex.get_editor_property("compression_settings"), tex.get_editor_property("flip_green_channel"))
            verdict((size_want is None or size == (size_want, size_want)) and facts == facts_for[entry["kind"]], name,
                    "%dx%d, sRGB %s, %s, flip green %s" % (size + facts))
        except Exception as e:
            say("NOTE", name + " not readable", str(e))
        if mi is not None:
            try:
                bound = mel.get_material_instance_texture_parameter_value(mi, entry["param"])
                verdict(bound == tex, "%s.%s" % (u["material_instance"], entry["param"]), bound.get_name() if bound else "None")
            except Exception as e:
                say("NOTE", "%s.%s not readable" % (u["material_instance"], entry["param"]), str(e))


def report_users(spec):
    """Who references the weapon from outside its folder. A re-import of the meshes deletes and re-creates them, so this is what
    it would cut (the importer refuses it without --replace-referenced). Paths written in C++ are invisible here."""
    u = spec["unreal"]
    dest = u["asset_dir"]
    try:
        if not eal.find_package_referencers_for_asset(u["master_material"], False):
            say("NOTE", "users outside the folder", "the asset registry returned no referencers at all, so this cannot be told")
            return
        for name in [u["skeletal"]["name"], u["skeletal"]["name"] + "_Skeleton"] + [e["name"] for e in u["statics"]] + [u["material_instance"]]:
            path = "%s/%s" % (dest, name)
            if eal.does_asset_exist(path):
                users = sorted(str(r) for r in eal.find_package_referencers_for_asset(path, False) if not (str(r) + "/").startswith(dest + "/"))
                say("INFO", "used outside the folder, " + name, ", ".join(users) or "by no asset (C++ paths are not seen)")
    except Exception as e:
        say("NOTE", "users outside the folder not readable", str(e))


def main():
    problem = None
    try:
        spec, _, _ = wspec.load(sys.argv)
    except wspec.ArgError as e:
        problem = str(e)
    if problem:
        raise RuntimeError(TAG + "nothing was checked: " + problem)
    u = spec["unreal"]
    dest = u["asset_dir"]
    unreal.log("%s%s in %s" % (TAG, spec["name"], dest))
    mi = load(dest, u["material_instance"], unreal.MaterialInstanceConstant)
    if mi is not None:
        parent = mi.get_editor_property("parent")
        verdict(parent is not None and parent.get_path_name().split(".")[0] == u["master_material"], u["material_instance"] + " parent",
                parent.get_path_name() if parent else "None")
        try:
            usage = parent.get_editor_property("used_with_skeletal_mesh") if isinstance(parent, unreal.Material) else None
            if usage is not None:
                verdict(bool(usage), "master material usable on a skeletal mesh", "Used with Skeletal Mesh %s (off: a game run draws the default grid)" % bool(usage))
        except Exception as e:
            say("NOTE", "master material usage not readable", str(e))
    check_textures(spec, mi)
    check_skeletal(spec, mi)
    lo, hi = spec["bounds_ue_cm"]["min"], spec["bounds_ue_cm"]["max"]
    for entry in u["statics"]:
        mesh = spec["meshes"][entry["name"]]
        boxes = mesh["collision"]["boxes"] if entry.get("collision") else []
        own = mesh.get("bounds_ue_cm")
        # the world copy is the skinned mesh's surface in its bind pose, so the weapon's bounds are its bounds; a prop has its own
        check_static(dest, entry["name"], mi, list(entry["lods_in_fbx"]), boxes, own["min"] if own else lo, own["max"] if own else hi)
    report_users(spec)
    unreal.log("%sRESULT %s" % (TAG, "all facts match the spec" if not misses else "%d MISS: %s" % (len(misses), "; ".join(misses))))
    if misses:
        raise RuntimeError("%s%d facts differ from the spec" % (TAG, len(misses)))


main()
