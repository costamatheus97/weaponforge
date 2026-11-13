# Rig, bones and sockets

How a weapon's rig is declared, what the tool itself requires of it, which names the tool and the Unreal adapter look up, and
what the names in the two long guns built with it so far carry (`assault_g3`, which ships, and SmgG2, a submachine gun
whose folder is not in this repository). The definition's other hooks are in
[definition.md](definition.md); the Unreal side is in [unreal.md](unreal.md).

## What a rig is

A weapon declares its rig in `weapon.py` with these class attributes: `bones`, `sockets`, `props`, `moves`, `poses` and
`motion`. They are all about places on the weapon, given in the weapon frame as Blender sees it (origin in the grip, +X
toward the muzzle, +Z up, +Y the weapon's left; centimetres), except a socket's rotation, which is in Unreal's pitch, yaw and
roll.

**Bones.** `[(name, parent, head position)]`. The names are the ones the game's code looks up (`Slide_Bone`, `Clip_Bone`,
`Hammer_Bone`, ...; the list and what each is for is in the playbook). Every bone's rest axes are the weapon's own, so the game
moves a part by plain weapon-frame vectors. Every vertex is on exactly one bone at full weight.

**Sockets.** `[(name, bone, position, Unreal rotation (pitch, yaw, roll), meaning)]`. They are exported as leaf joints named
`SOCKET_<name>` and become mesh sockets at import. `socket_targets()` lets the mesh say where a socket should be (the centre
of the muzzle face, the middle of the magazine well), so a mistyped number is caught by the check.

**Props.** `Prop('Mag', bones, matrix, use)` cuts the parts on those bones out as their own static mesh, `SM_<Name>_Mag`,
written in the frame `matrix` gives (the magazine: origin at its top centre, +Z up its axis).

**Moves.** `Move(name, bones, matrix, steps, limit=None, unit='cm')`: the check puts the parts on those bones (and on the
bones under them in the skeleton, which move with them) where `matrix(amount)` says, for each amount in `steps`, and measures
the deepest overlap with everything else. `matrix(amount)` is a
4x4 in the weapon frame applied to the parts as they sit at rest: a translation for a slide
(`Matrix.Translation((-t, 0, 0))`), a rotation **about the pivot** for a lever (`K.rot_y(pivot_xz, degrees)`, or
`Matrix.Translation(p) @ Matrix.Rotation(angle, 4, axis) @ Matrix.Translation(-p)` for another axis, such as a cylinder turning
about the bore). Amounts up to `limit` (by size) must stay clear; larger ones are only reported. This is what finds a slide that scrapes
the barrel hood or a magazine that cannot leave the well:

    ok   moving: slide travel      deepest overlap at rest 0.000 cm; moved by 1.5 cm back 0.000; 3 cm back 0.000
    MISS moving: magazine leaves   deepest overlap at rest 0.000 cm; moved by 1 cm out 0.168; 4 cm out 0.210; 8 cm out 0.210
    MISS moving: safety lever      deepest overlap at rest 0.100 cm (over 0.05: the part is modelled into its neighbour); ...

(the second is a magazine pulled straight down out of a raked grip; the third a lever sunk into the frame). Parts may touch at
rest, up to 0.05 cm; moving must not make it worse.

**Poses** are for the review renders only; the game animates the bones itself. `{bone: {'loc': (x, y, z) cm, 'rot': (x, y, z)
degrees, 'scale': s}}`, in the bone's own axes, which are the weapon's, about the bone's head, by Blender's right-hand rule:
`+rot` about Y takes +X toward -Z, **the opposite sign to `K.rot_y`**.

## What the tool requires, and what it looks up by name

**Required by the tool** (`Weapon.validate`, `rig.py`, the check `rig: bones`): at least one bone; the first bone is the root,
with no parent, and every other bone has a parent that is listed before it; each bone name is used once; no bone name starts
with `SOCKET_` (that prefix is kept for the socket joints); every part is tagged (`K.tag`) for a bone that exists; every
socket is on a bone that exists and is named once; every pose, move, prop and `motion` entry names bones that exist. The
armature object is named exactly `Armature` (Unreal drops the armature's own node only then), the rest axes are the weapon's
own, and every vertex is on exactly one bone at weight 1. A typo in any of this stops the first stage with a list of
everything wrong. **No bone or socket name is required by the tool.** The names below are conventions of the examples, and
the tool reads a few of them to do something extra when they are there.

**Looked up by name in the tool's code** (a weapon without the name loses only the extra):

| Name | Kind | What the tool does with it |
|---|---|---|
| `SightRear`, `SightFront` | sockets | the line from the one to the other is the aiming eye of the `hero --shots ads` picture and of the `texel_view` texel weights (`hero.player_eyes`); `review` cuts its `ads_rear_sight` and `fp_rear_sight` crops at `SightRear`; without both there is no aiming picture and the review says so |
| `Muzzle` | socket | the `muzzle` crop of `review`; the default `muzzle_x` of the named finish `barrel_phosphate` (where the soot and fouling are measured from) |
| `AmmoEject` | socket | the named finish `moulded_polymer` puts grime in a box round it when the weapon names no `grime` zones |
| `Root_Bone1`, `Root_Bone`, `Grip_Bone`, bones starting `Clip`, `Ammo`, `MagAmmo_Bone` | bones | left out of the places where that same grime gathers (a box is put round every other bone's head: the controls' pivots) |

The `control_<part>` crops of `review` are chosen by a rule, not a name: a small part on a bone of its own, that is not the
bone carrying the most surface, not a prop's bone and not a brass or copper part.

**The Unreal adapter looks up no name.** `weapon_import.py` and `weapon_check.py` read the spec (`<id>.json`): every bone,
socket and mesh the weapon declares is imported, and read back and compared, whatever it is called. The only name rule is the
prefix: a leaf joint called `SOCKET_<name>` becomes a socket called `<name>` on its parent bone. A game's own code is another
matter: `PLAYBOOK.md` section 11, item 3, lists the names the first game's pistol code looked up, and what did not work
without each. If the game has no code for your kind of weapon yet, the names are yours to choose and that code is written
against the spec.

## Sign conventions

Two rotations in a definition have opposite signs, and a weapon often needs both.

- **`K.rot_y(pivot_xz, degrees)`**, in the matrix of a `Move` (and the rule `Zone.tilt` and `Decal.tilt` follow): positive
  degrees tip +Z toward -X, a hammer cocking back.
- **A pose's `rot`**: Blender's right-hand rule about the bone's own axes, which are the weapon's: `+rot` about Y takes +X
  toward -Z.

So the same turn is written with opposite signs. The template's safety lever: its `Move` uses `K.rot_y(P.SAFETY_PIVOT, -deg)`
and its pose says `'rot': (0.0, P.SAFETY_DOWN_DEG, 0.0)`; SmgG2's selector is the same pair. Write the pose, look at the
`pose_*` sheet, and write the `Move` with the sign that makes the moved parts land where the pose put them. The same note is
beside `K.rot_y` in [kit.md](kit.md).

## The bones the examples use

Every name here is a convention of `weapons/_template`, `weapons/assault_g3` and SmgG2 unless the last column says
otherwise. Nothing in the tool requires any of them. A bone sits on the pivot of the part it moves (the trigger on its pin, the
bolt on the bore axis at its face), and every part that does not move on its own rides on `Grip_Bone`.

| Bone | Parent | Sits at | Carries | Seen in |
|---|---|---|---|---|
| `Root_Bone1` | none | the origin | nothing: the root. The first bone must be the root, whatever it is called | all three |
| `Grip_Bone` | root | the origin | every part that stays still: receiver, grip, barrel, sights, fixed furniture. The sockets for fixed points (`Muzzle`, `MagWell`, the sights) are on it | all three |
| `Slide_Bone`, `Barrel_Bone` | `Grip_Bone` | the bore axis | a pistol's slide, and its barrel (the template's slide moves 3 cm back) | template |
| `Bolt_Bone` | `Grip_Bone` | the bore axis, at the bolt's face | the bolt, which moves back along -X when the action opens; a shot cycles it there and back | both long guns |
| `ChargingHandle_Bone` | `Grip_Bone` | where the handle leaves the receiver's wall | the charging handle; pulled back it takes `Bolt_Bone` with it (the game does that; the check moves them one at a time) | both long guns |
| `Trigger_Bone` | `Grip_Bone` | the trigger's pivot pin | the trigger blade; it turns about the lateral axis | both long guns |
| `Safety_Bone` | `Grip_Bone` | the pin (or the button) of the safety or selector | the safety or selector lever: a button that slides in AssaultG3, a lever that turns in SmgG2 and in the template | all three |
| `MagRelease_Bone` | `Grip_Bone` | the catch's pin | the magazine catch: pressed forward in AssaultG3, turned in SmgG2 | both long guns |
| `Clip_Bone` | `Grip_Bone` | the middle of the magazine's top | the magazine body. It leaves along `MagWell`'s -Z. The `Mag` prop is cut from the parts on this bone and its children | all three |
| `MagAmmo_Bone` | `Clip_Bone` | the base of the top cartridge | the cartridges you see in the magazine's mouth. It is a child of the magazine, so it goes with it; the game scales it to zero or hides it when the magazine is empty | both long guns |
| `Ammo` | `Root_Bone1` | the base of the chambered cartridge | the one cartridge in the chamber: it comes back with the bolt and is then thrown out at `AmmoEject`; scale it to zero when the chamber is empty. It is under the root, not under `Bolt_Bone`: the examples list it beside `Bolt_Bone` in the bolt's `Move` and in the poses, which is how it travels with it | both long guns |
| `Hammer_Bone`, `Stock_Bone`, and others | | | `PLAYBOOK.md` mentions these and the bones of weapons that are not in this repository (a pump, a cylinder, a lever) in sections 11 and 13: they were chosen by the weapon, and no game code drives them | not shipped |

`motion = {bone: text}` is where a weapon says how the game should move each bone and what state it is bound in (a hammer
bound cocked must say so); the text goes into the spec for whoever writes the animation.

## The sockets the examples use

Positions are in the weapon frame as Blender sees it, so a socket on the right-hand side has a negative `y`; the spec
carries them in Unreal's frame. A socket's rotation is Unreal's (pitch, yaw, roll) in degrees. The check `rig: socket joints`
proves the joint in the file matches the definition; it does not prove the rotation is the right one for the game, so look
at the Unreal read-back (`unreal-check`) and the pictures.

| Socket | On bone | Marks | Rotation in the examples | Read by |
|---|---|---|---|---|
| `Muzzle` | `Grip_Bone` | the middle of the muzzle device's front face; +X is out of the barrel | (0, 0, 0) | the tool, as above; a game's muzzle flash |
| `AmmoEject` | `Grip_Bone` | the middle of the ejection port, on the right; +X is the way a case leaves (to the right), +Z up | (0, 90, 0) | the tool's grime; a game's ejected cases |
| `MagWell` | `Grip_Bone` | the middle of the magazine well's mouth, +Z up the magazine's axis into the gun. If the magazine is raked, so is this socket, so its -Z is the way the magazine leaves | (rake, 0, 0) | the game's reload; the spec's `reload_targets.mag_well` |
| `MagDrop` | `Grip_Bone` | a point a set distance down the magazine's axis from `MagWell` (9.0 cm in AssaultG3, 7.6 in SmgG2): where a released magazine is clear of the well. Same rotation as `MagWell` | same as `MagWell` | **nothing in the code reads it**: a convention of the examples, for whoever animates the drop (`reload_targets.mag_drop` in SmgG2's spec) |
| `ForeEnd` | `Grip_Bone` | the underside of the handguard or shroud, between the hand stop and the receiver: where the support hand holds | (0, 0, 0) | **nothing in the code reads it**: a convention, the support hand's place on a long gun (`reload_targets.fore_end`) |
| `BoltHandle` | `ChargingHandle_Bone` | the grasp of the charging handle: the middle of the knob in AssaultG3, the hollow in front of the stem in SmgG2. It is on the handle's own bone, so it travels with the handle | (0, 0, 0) | **nothing in the code reads it**: a convention, where the hand goes to charge (`reload_targets.bolt_handle`) |
| `SightFront` | `Grip_Bone` | the top of the front sight post | (0, 0, 0) | the tool, as above; the game's sight alignment |
| `SightRear` | `Grip_Bone` | the middle of the rear sight's aperture | (0, 0, 0) | the tool, as above |
| `Rail` | `Grip_Bone` | AssaultG3 only: the top of the rail, the middle of its free length: where an optic would sit | (0, 0, 0) | nothing |

On a variant with a scope, `SightFront` and `SightRear` become the ends of the scope's axis ([variants.md](variants.md)).

`spec_extra` is where a weapon adds what the game side wants to read beside these (the three shipped weapons write
`dimensions_cm` and `reload_targets`). The key names `mag_well`, `mag_axis`, `mag_drop`, `bolt_handle`, `bolt_axis`,
`fore_end`, `mag_release` and `selector` are the examples' own, in Unreal's frame.

`socket_targets(parts)` lets a weapon say where the mesh itself puts a socket (the centre of the muzzle face, the middle of
the aperture), so that a number typed wrong is caught by the check `sockets`; SmgG2's is a worked
example. Measure a solid by rays or by the bounds of a named piece, not by picking vertices at a position, so the check
survives a part being built another way.
