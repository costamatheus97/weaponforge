# AssaultG3: brief

A bullpup rifle of original design for a first-person game: the action and the magazine lie in the butt, behind the hand. No
real maker's name, logo or markings. A bullpup was chosen as the one modern rifle layout the other rifles built with the tool
did not have.

**Built ahead, as a worked example. Of the four approvals only the second (the high-detail model, which is what the forms are)
was given, on seeing before/after pictures; the other three are open** (see "Approvals" and "Forms and edges").

## What it is

- One olive polymer shell from the butt to the handguard's nose: the butt (with the bolt carrier's tunnel in it), the housing
  of the action with the magazine well under it, a flat over the grip and the trigger, and the handguard with a hand stop
  under its nose. Its top is flat from end to end, and its section is faceted (see "Forms and edges"). Three long flutes are
  pressed into each side of the butt, six slanted blind vents into each side of the handguard, and there is a slot through
  the butt for a sling.
- A black rubber butt pad, ribbed across.
- A raked olive grip, textured on both sides, and a guard for the whole hand: a moulded blade that leaves the grip's toe,
  runs forward under the hand, turns in one elbow and climbs to the handguard.
- A black slotted rail along the shell's top (23 slots), with an aperture rear sight (two ears, a windage knob on the right)
  clamped on its rear end and a front post between two wings clamped on its front end.
- The ejection port on the right, over the magazine, with the bare bolt carrier in it.
- A barrel that shows for 13 cm ahead of the handguard, held by a notched nut, turned down toward the front, with a slotted
  flash hider (five slots, none underneath).
- A magazine of curved steel, 30 rounds, ribbed, straight inside the well. It goes in behind the grip.
- Controls: a charging handle on the left of the handguard (a knob on a lug that runs in a slot), a safety button pushed
  through the shell over the grip (standing out on the left is "safe", on the right "fire"), a magazine release paddle
  hanging behind the well (pushed forward), the trigger in a slot of the shell.
- The cartridge is a 5.6 mm bottleneck round of the game's own: 5.7 cm long, brass case, copper-jacketed bullet.
- Engraved, on the left of the magazine well: `MOD. AS3`, `CAL 5.6 mm`, `AS3 044582`; over the safety: `SAFE` on the left,
  `FIRE` on the right.

The sections below are a log of passes, not in strict time order. Where two of them disagree, "As built" has the last word.

## Finish

Every weapon of the first set had the same blued steel and the same walnut. This weapon was textured again with a finish of its
own, and exported again. Where the text above or below says otherwise, this is what it wears now:

- Steel: `nitride` (`finish` in `weapon.py`): a satin neutral black on the barrel, the rail, the sights and the magazine; the olive shell is unchanged.

The choice was judged in the review light. The mesh, the bake, the rig and the checks are as they were.

## Lettering

The engraved lettering is filled with paint: white for the model, calibre and serial lines and for SAFE on the left, red for FIRE on the right (`paint` in `weapon.py`; the red text is cut with `ink=1` in `parts.py`).
Bare engraving was close to invisible on the dark finish. The detailed parts were built again so that the tool could keep
the letters for the bake (PLAYBOOK.md, "Textures and look", item 16), and the weapon was baked, textured, exported and
verified again; the mesh, the bones, the sockets and the collision boxes are unchanged. A copy of the files as they were was
kept.

## Size (cm)

| | |
|---|---|
| Overall length | 70.76 (was 70.3 before the forms) |
| Bolt face to the muzzle | 45.8 (the barrel itself ends inside the flash hider, 43.0 from the bolt face) |
| Height, magazine floor to the top of the rear sight | 27.1 |
| Width (the rear sight's knob on the right to the charging handle's knob on the left) | 5.72; the shell itself is 4.4 at the housing (4.9 at the magazine well's collar), 3.6 at the waist (it was 3.8 everywhere) |
| Length of pull | 38.49 |
| Bore axis above the grip origin | 8.6 |
| Line of sight above the bore | 5.6; sight radius 27.7 |

For comparison, a conventional carbine built with the tool had 39.6 cm from bolt face to muzzle in 84.5 cm overall: this rifle
has 6 cm more barrel in a gun 14 cm shorter. That is what the layout is for.

## Polymer

The polymer parts (the olive shell, the black rubber butt pad) were textured again with the tool's reworked polymer recipe: soft clouding, a thin film and specks of dust, a pale polished
line along the edges and a moulded grain (PLAYBOOK.md, "Textures and look", item 17). A render from elsewhere, set beside
ours, had all of these, and ours was one flat tone on which moulded lines could hardly be seen. No new bake for this and no
change to the game mesh, the bones, the sockets or the collision boxes; the weapon was exported and verified again
(41 of 41 checks pass). A copy of the textures, the sheet and the spec as they were was kept.

## Forms and edges

An early build read as a CAD blockout: a slab outline of one thickness with rounded edges and every detail in the normal map
only. The forms were reworked as a test piece for a pipeline-quality experiment, in two passes on a trial copy, and the new
forms were kept on seeing the before/after hero pictures. Where the text above or below says otherwise, this is what it is now:

- **The shell's section is facets with creases, not one rounded outline**: a flat land under the rail, a shoulder facet at 40
  degrees, a nearly upright side facet (2.5 degrees of draft), a belt line (the lower moulding stands 0.13 proud of the upper
  with a 45 degree chamfer; it runs from the butt to the nose and jogs down under the vents), a lower side facet, a lower
  facet tucked 18 degrees toward the flat underside. Creases have a real radius of 0.17 (three chords in the game mesh).
  Each change of width (butt, housing, waist, handguard) is a ramp 2 to 3 cm long with crisp ends.
- **The magazine well has a collar** (its lowest 1.3 cm thickened by 0.25 all round, a 45 degree chamfer into the shell, a
  chamfered mouth) in place of the first build's rim; the grip is blended into the shell by a web behind and one in front of it
  (radius 1.0); the handguard's front face is sloped (the top leads the bottom by 1.15) and chamfered, with the barrel nut
  in a counterbore; each side of the butt has a raised cheek panel; the vents are 0.6 wide.
- **The guard is a moulded blade** (see "As built").
- **Edge break** (`edge_break` in `weapon.py`, new): the bake rounds every edge of a kind by 0.10 cm on polymer, 0.045 on
  steel, 0.04 on dark and bright steel (the tool's defaults are 0.035 polymer, 0.030 steel). The only look change besides the forms: `finish`, `paint`,
  the olive and every `surface()` argument are as they were. The engraved lettering stays readable at 4096 (checked in the
  presentation picture and the close-up).
- **Triangles and budget**: 9,938 to 15,818 at LOD0; the budget's floor went from 8,000 to 15,000 (`weapon.py`).
  The width check's brief range went from (5.0, 6.0) to (5.7, 6.4), the true new value; no check was loosened.
- **UVs**: seams for the lofted shell (the underside's centre line and the steps of the well, and a line at the tuck crease),
  for the grip (its back and front strap) and for the strap (its centre line, inside and outside) are in `weapon.py`'s `seams`;
  the strap is one patch with a stretch of 1.67 and the grip body one of 1.22, no longer cut by angle. The shell's lower band
  (two halves, stretch about 3) and the butt pad still are cut by angle; where those cuts run on the shell's side was not checked.
- A copy of the build before the forms (definition, textures, export, the .blend, the spec, the hero pictures and the .glb) was
  kept, and so were the trial copies of the two passes.

## Wear by use

After the forms the gun still looked like toy plastic with its edges outlined: one pale line round every convex edge,
grooves paler than the faces, one roughness from nose to butt. The tool's recipes gained opt-in
arguments for wear that follows use (PLAYBOOK, "Textures and look", item 18), and this weapon is the first to use them:

- `handled` in `weapon.py`: thirteen zones, each with a note saying what touches the gun there (the firing hand, the
  trigger finger, the thumb on the safety, the support hand under the handguard, the charging handle and its slot, the
  cheek, the well's mouth and the release, the magazine's body and floor, the butt's toe and heel, the guard's strap, the
  muzzle). `smooth`: the two cheek panels and the well's collar. `textured`: the fore-end's hold under the vents.
- `surface()` passes them on with `exposure=1.0, recess=1.0, vary=1.0` (and `fade=1.0` on the olive): edges wear only where
  they stand out or are handled, in rubbed stretches and chips; grooves, vents, the charging slot and the panel steps sit
  darker; the roughness drifts and smudges; the grip and the fore-end are polished darker; the magazine is worn to bare
  metal on its floor and edges. The rubber pad takes `exposure`, `recess` and `vary` but no handling. The olive, `nitride`
  and the lettering are as they were.
- No new bake and no change to the mesh, the bones, the sockets or the collision boxes. Textured, exported and verified
  again: 41 of 41 checks pass, `verify` matches the spec.
- The zones are a reading of how a right-handed shooter holds and sets down a bullpup. A review rated the gun about 6.5 of 10
  after this pass (still one olive moulding with little hardware). Not checked in an engine: the recess darkening is in the
  base colour, so if the game's material also applies the occlusion channel the recesses will sit darker there than in the hero
  picture.
- A copy of the textures and hero pictures as they were was kept.

## Assemblies, silhouette and hardware (pass 3)

Why: the build was rated 6.5/10 in review: one olive moulding, a brick-like profile, almost no hardware. Pass 3 was built on a
trial copy of the tool and trial asset roots, and the result, with passes 3b and the painted sets, was then merged into the
real folders. Where the text above says otherwise, this is what it is now:

- **A black hard-anodised alloy top cover** (its own surface kind, `alloy`, in the shell's section so the game mesh has it too): from the
  nose back to x -17.4, just behind the ejection port; a shut line all round (a groove 0.07 wide and 0.08 deep in the section, so in the game mesh
  too), standing 0.10 proud, a lower edge that steps up over the handguard (7.75 to 8.75) and a tighter edge
  break (0.035). It carries the rail (alloy too), the charging slot and the ejection port. Six hex-socket screws in counterbores (three
  a side), a small engraved arrow by the front pin. Satin (roughness 0.40 to 0.50), wearing to pale aluminium at exposed corners and
  round the charging slot.
- **Rubber** (a fifth surface kind, `rubber`, roughness about 0.8): a saddle cheek pad on the comb (see "Pass 3b" below),
  the pistol grip's side inserts and back strap (a sunk border with the checkering), a hold pad under the fore-end, and the butt pad.
- **Steel hardware** (`hardware` part): two takedown pins (a domed head with a wire clip on the left, the pin's end on the right), the
  bolt-release lever behind the well (static, not on a bone), a front sling loop, a sunk data plate with two rivets and the serial.
  Sights, rail and hardware are phosphate steel; the barrel is blued and the magazine black phosphate, told apart from the rest of the
  steel by where they are (`surface()`).
- **Nose and barrel**: a barrel nut with wrench notches, a short knurled gas regulator knob, a barrel with a taper and a second turned
  step, a gas block ring and a crush washer with flats behind the flash hider.
- **Butt**: the rear face raked (toe 1.04 cm forward of heel at the shell), a bigger heel radius than toe radius, a hook under the butt
  between the well and the toe, the pad as its own thick crowned part on a hard black spacer plate, a real through sling slot.
- **Fore-end**: deep vents with a dark floor, four plain obround accessory slots, a hand-stop lip.
- **Detail model only** (cuts, all under 0.2 deep): hairline parting lines on the comb and under the butt (cut 0.03 deep, not raised:
  a raised line over 0.02 will not bake), ejector-pin circles under the shell, a date-clock mould mark on the butt's right, selector
  pictograms (white ring for safe, three red bars for fire) under the button, the stencilled rack number 07 (white, 2 cm) on the butt's
  left (later a worn stencil decal, not a cut: see "Painted sets and decals"), the serial moved onto the data plate (`MOD. AS3` and `CAL 5.6 mm` stay engraved on the shell).
- **Sights**: the rear sight is a clamped base with a cross-bolt, a two-aperture drum with a knurled windage knob and index ticks, wings;
  the front sight a post with wings and an adjuster.
- **Numbers**: budget (15000, 45000). The edge breaks per kind are `edge_break`
  in `weapon.py`; the kinds table (`kinds`) maps rubber onto wood's code and alloy onto copper's: the bullets' copper tips are told from
  their brass cases by position in `surface()`.
- The shell's booleans all fall back to the second (MANIFOLD) solver in the log (the exact one returns 6 to 8 open edges on the new loft);
  the finished shell is closed.

## Pass 3b: the punch list

Same trial copy. What changed, and what a later hand (the texture and decal pass) needs to know:

- **Cheek pad** (`cheek_pad` in `parts.py`, constants `CP_*` in `params.py`): a real saddle from the cover's rear end back to 2 cm
  short of the pad plate, `CP_H` 0.30 proud of the comb, over the comb and 3.81 cm down the left shoulder (2.83 on the right; the
  bolt's side is shorter). The game mesh is clean (a rounded border step, an end that rounds off in two rings, no ribs). The ribs
  (`CP_RIB_D` 0.11 deep, pitch 0.40) are **detail model only**: as geometry they made 130 UV islands and cost 15 points of sheet
  coverage. The pad skins `P.ring`, so it follows the shell's creases; the inner skin sits 0.07 under the surface. Black rubber,
  rough 0.75 or more, no handled polish. The cover's tail is stepped and angled (`CV_TAIL`) and the pad butts against it.
- **Grip insert** (`INS_*`, `insert_groove` in `parts.py`): an overmoulded rubber insert with a designed outline (a super-ellipse over
  the back strap and both side panels), a sunk border groove 0.10 deep, 0.16 wide, rounded corners; checkering only inside it
  (`GRIP_CHECK`); the olive frame outside is polymer. Faces are classed as rubber by the same analytic outline (`_grip_index`).
- **Magazine**: darkest metal after the cover (base at most 0.03, roughness near 0.5); only the floor is `handled`. It had gone pale
  because the shared steel recipe's `handled` term polished the whole flat side.
- **Cover wear**: edge lines, charging slot and handle surround, screws and a few scuffs; no cloud, no vary, no thin band.
  `paint_wear` is 0.18 and lettering is bigger so the white fill survives at 2048.
- **First-person detail**: rear sight with lightening cuts, stepped wings with 45 degree chamfers, a recessed rear panel with two
  slotted screws, scale ticks and numerals, a windage knob with 24 or more segments and a slotted end screw; rail numerals every
  4th slot (0.47 tall); front-sight detents; three hex screws on the cover top near the rear sight and a small lock pictogram by the
  rear takedown pin; a right-face QD cup and panel line (clears the "bare faces" note).
- **Texel density**: `density` in `weapon.py` gives fp parts about 1.5 times the mean. The check compares each part to the area-weighted
  rms of the weights, so the spread is 1/rms_w - 1: **keep rms_w at 1.11 or less** or the density check fails (a first set of weights
  gave -16.8 %). Now 48.8 px/cm at 4096 (49.9 before), coverage 46.5 % (45.3 % before), the spread -8.4 %.
- **`surface()`** is rewritten for the next hand: one named recipe variable per material and the masks (`_grip_index`, `_shell_index`)
  that select them.
- **Thin margins, left as they are**: the wall behind the carrier's tunnel is 1.06 cm against a limit of 1.0 (0.06 margin), and the
  width is 6.04 in a 5.7 to 6.4 range. The shell, grip, barrel and rear sight booleans fall back from the EXACT solver to MANIFOLD
  (the exact one leaves open edges on these lofts); every part is audited closed. A change to the tunnel, the butt rake or the
  loft may break either of them.
- **Not done**: the guard-strap toe still reads as a faceted cuff (a root that needs its own pass); the 4096 px bake of the new
  lettering was not tried in this pass.

## Pass 4: first-person hardware

Built on a trial copy; only this weapon's folder changed. Passes 3, 3b and the painted sets were already in the main build.
Parts that sit in the player's foreground got real hardware; the shell, cover outline, butt, pads, magazine, decals and the
materials in `surface()` are unchanged (only masks were added).

- **Rear sight** (`rear_sight`, `REAR_*`, `APERTURE*`, `KNOB_*` in `params.py`): a slim aperture arm 0.45 thick with a rounded
  outline and a thumb tab, on a pivot pin through both wings (domed head left, C-clip and a detent ball right); two apertures cut
  through, each with a countersunk rim on the eye side (`REAR_CS_D/W`, re-cut at the end so the serrations cannot nick them);
  hooked wings 0.32 thick, 45 degree outer chamfer, a lightening slot each, a shallow sunk outer panel (the left one carries the
  elevation scale, kept); a windage screw (threaded shaft with ring grooves, slotted head left, click plate with ten small holes and
  four white index ticks, a 28-flute knurled knob right); a base with clamp bars, a split-line groove along each side, a
  cross-bolt and nut, a recoil lug behind the rear face and the recessed panel with its two slotted screws. Detail model only:
  15 horizontal V serrations on the arm's rear face (pitch 0.10, 0.04 deep), 3 on the tab, the knurl, threads and click holes.
  The sockets stay on the true line of sight (`SightRear` is the mean x of the hole's vertices).
- **Front sight**: hooded wings with a lightening hole each, a serrated post and pedestal rear face (detail model), a clamp with
  a cross-bolt and split lines, the 12 adjuster detents kept.
- **Charging handle**: a clevis and a cross pin (visible, slotted ends), a knob with 24 knurl cuts and two ring grooves, a
  dimple on the neck; the slot has a dark liner (`_shell_index` index 3) and a steel end stop (`Hardware`).
- **Trigger**: 11 vertical serrations on the finger face (detail model) and pivot dome heads on both shell sides. The guard-strap toe
  has a longer plan flare (`GUARD_TOE_FLARE_L` 2.8, `GUARD_TOE_FACE_S` 0.45) and more loft chords (`GUARD_K` (4, 6)); a thickness
  fillet at the toe was tried (`GUARD_TOE_FILLET`) and stood out of the grip as a plate, so it is 0.
- **Cover top and left shoulder**: shoulder flutes along each shoulder facet (`CFLUTE_*`, 0.10 deep) with cross-groove anti-glare
  serrations behind the rear sight (`SERR_*`, 0.04 deep, pitch 0.14): detail model only (the shell's detail model went from 18k to 27k triangles).
- **Bolt-release lever pin** is now built apart and joined AFTER the cuts (see the rule below); that was the source of the faces with
  no surface kind at its rounded rear end.
- **Masks**: `Weapon.hp_kinds` splits `SightRear*` into steel and bright (`_rear_index`: pin ends, domed head, ball).

Rules a later hand needs:

- **`parts.seg(hp, lo, hi)`: the game mesh gets `round(lo * LP_Q)` with `LP_Q = 3.4`.** Pass lo=7 for a 24-gon, lo=1 or 2 for a
  `round_poly` arc; raw segment counts blew the rear sight to 7,048 triangles (now 2,652).
- **Closed cavities count as inside-out parts.** A cutter that ends fully inside material leaves a closed piece with inward
  faces, and the check `mesh: no part is inside out` misses. Two causes here: click-plate holes that fall into the clamp bar
  (skipped) and an index tick inside the pivot pin (moved). Diagnose with the volume of each connected piece (negative = cavity).
- **Parts that overlap another solid by a hair must be joined after the cuts.**
- **Texel density**: keep the rms of the weights at 1.11 or less (unchanged).
- The decals on the rear-sight clamp (`witness`) are placed by weapon-frame box; the clamp base was not moved.
- The shell, grip, barrel and rear-sight booleans still fall back from EXACT to MANIFOLD; every part is audited closed.
- **Result** at 4096: 24,890 triangles (budget 15,000 to 45,000; LODs 12,444 and 6,222), 47.8 px/cm (spread -8.5 %), sheet
  coverage 44.8 % (was 46.5 %), 0.72 % missed rays, 0.04 % detail faces outward, 44 of 44 checks, verify ok.
- **Not done**: the toe's concave corner and slight wedge remain; the 4096 anomaly on the data plate from before is unexplained; the
  rear-sight arm's serrations scallop the countersink rim slightly (reads as machined).

## Pass 5: five small fixes

From the aiming and first-person pictures of the combined build. Only `params.py` and `parts.py` changed.

- **Aperture rims** (`rear_sight`, serration loop): the grooves on the arm's rear face leave one flat vertical land, 0.92 wide, round both
  apertures (each groove stops 0.08 short of the larger countersink's rim); a first try that stopped each groove round its own circle
  left a stair of groove ends round the holes and read as noise in the baked picture, so it was replaced. The apertures are 34-sided in
  the game model now (were 24), the same circle as the bake source.
- **Arm top edge**: the three-block thumb tab and its grooves are gone. The top rear edge has one 0.12 chamfer across the arm and one
  V index notch at the centre, in both the game and the bake model.
- **Windage knob**: 37 sides in the game model (was 24), `sg(11, 40)`; the knurl stays in the bake source.
- **Front sight, the face "treated as hidden"** (0.86 cm2 at about 17.80, -1.08, 11.41, facing +Y): a ray from its centre along +Y hits
  `Rail` 0.02 cm away at (17.80, -1.06, 11.41). It is the right jaw's inner face, which looks at the rail's side across the `SEAT` gap
  (0.02) the kit leaves between parts. Nothing overlaps and nothing is buried; it really is a hidden face (the gap is a slot 0.02 wide).
  Left as it is.
- **Guard-strap toe, one more build** (`GUARD_TOE_R`, `GUARD_TOE_FILLET`, `GUARD_TOE_NARROW`): the strap's own sections rise along a
  longer quarter circle (radius 1.3) and narrow by 0.6 as they climb the grip's face. It left a hump standing off the grip, a worse corner
  than the wedge it replaced, so it is reverted (0.0, 0.0, 0.8: as pass 4). The concave corner and wedge remain.

## Texel density and the look at it

PLAYBOOK "UVs" item 8.

- **The pack.** `uv_pack = 'tight'` (the tool's own packer, which fills the hollows Blender's leaves) with `uv_margin = 0.0017`
  (14 px between two islands at 4096; mip 2 stays clean, do not go lower). 46.5 % of the sheet became 66.5 %.
- **Texels by place.** `texel_zones` and `texel_hidden = 0.45` replace the per-builder `density` weights: 2.2 on the rear
  sight, 1.6 on the front sight, the rail, the charging handle, the cheek saddle, the cover's top and left shoulder and the
  fore-end's left, 0.8 on the grip, 0.6 on the butt pad, 0.5 on the underside. The zones are boxes in the weapon frame: after
  moving a part, read the `texels:` lines of the `uv` log.
- **The look, retuned on the new bake** (`weapon.py`: `olive_life()`, `barrel_life()`, `fp_convex()`): the handled olive is
  darker and hand-polished in patches, no longer bleached (`worn` 0.062/0.074/0.028); grime gathers round the vents, the
  controls, the pins and the shut line; the barrel and flash hider are a dark phosphate metal with carbon in the hider's slots;
  the `07` is worn through at its lower rear. The edge mask is worked out per texel, so on the denser faces the edges had
  thinned: `fp_convex()` widens them by a reach in texels per zone. **Those reaches are tied to the zones' weights** and need
  retuning if the weights change; the lasting fix (not made) is for `maps.process` to know each island's density.
- **Tried and dropped:** a heat tint behind the flash hider (it read as rust), a soot film over the hider (it read paler).

## Pass 6: machining detail

Only `parts.py` and `params.py` changed; `weapon.py` was not touched, so no `surface()`, recipe or UV DENSITY change.

- **Barrel group** (`barrel`, `flash_hider`): a turned shoulder collar (r 1.07, 0.55 long) in front of the barrel nut; the nut has eight castellations (0.36 wide, 0.5 deep, game and bake model; the old 8 shallow notches are gone); the gas block has two wrench flats with a slotted cross pin standing on each (a pin per flat end, four heads), a detent flange (r `REG_R + 0.17`) under the regulator with twelve notches (bake model), and two turned rings on the barrel's front step; the flash hider has a recessed crown (a 0.14 step with a lead-in chamfer at the bore) and two turned rings behind the slots (bake model). Game model +about 1,000 triangles. (The shell's bake source is as in pass 5, 26.8k triangles.)
- **Rear-sight arm, lower half**: two shallow milled pockets (0.14 deep, y 0.20..0.66 each side, `zc - 0.30..zc + 0.26`) either side of a centre rib; bake model only. They read as two dark ovals in the aiming view: subtle, not cluttered.
- **Cover: tried and reverted (the shell builder, `CFLUTE_*`, `SERR_*` are exactly as in pass 5).** The try: five long flutes on the left wall, the shoulder flute deepened to 0.15, the top cross-grooves widened (half width 0.07, depth 0.07, pitch 0.22). Rejected on review: the wall flutes read as an arbitrary patch of stripes behind the charging slot with ragged, staggered ends (the lines had to stop short for the charging track's recess at x 4.4 on, z 9.0 to 9.8, whose floor is at y 1.0, and for the handguard's step at x 7.2; a line across the recess made `cut_grooves` fail), a stray mark among them, they crowded the screw there, and the deeper shoulder flute showed as a wavy bright smear. The pass-5 cover reads cleaner and more designed. Lesson: a surface feature on that wall has to be designed with the recess and the screw, not laid over them.
- **Bolt carrier** (`bolt`): a milled step (0.14) over 1.25 cm ahead of the cam slot, a slanted cam slot (0.34 wide, 0.26 deep, game and bake model) on the right side, the fine grooves cut from 14 to 8, and an extractor claw with a hook lip on the right of the bolt head. **With the bolt fully back (8 cm) the carrier is out of the port and what shows is the empty tunnel in the shell, which is plain (not changed); the head and claw sit behind the port's rear edge.** At rest and at partial travel the port shows the new detail.
- **Sight arm strips** (`rear_sight`): every groove is now the same two strips (from the land at 0.46 to the arm's edge), the same length, square ends at the land, in every row.
- Rules still in force: `LP_Q`, the join-after-cuts rule, closed-cavity check, the MANIFOLD fallbacks (barrel, hider and rear sight cuts use them; every part audited closed).
- **Result** at 4096: 45 of 45 checks pass, `verify` matches the spec, 26,648 triangles, 65.8 % of the sheet, the bake's rays missed 0.78 %; the cover is as in pass 5. Left plain: the empty tunnel seen through the port with the bolt fully back.

## Painted sets and decals

The texforge layer (PLAYBOOK.md, "Textures and look", item 19) was ported onto the pass-3b `surface()`, on a trial copy first.
Everything is in `weapon.py` between `# ==== TEXFORGE` markers or on a line marked `TEXFORGE`; the sets are found by
`material_dirs` (the README says where it looks).

- **Sets, laid on by position under the wear** (`tex()`): `poly_mould` on the olive polymer (a 9 cm tile, so the 0.6 mm grain is two
  texels: it shows in the sheen and the normal map; its tone swing is kept at 8 %, a stronger one paled the olive into a chalky film);
  `rubber` on the cheek saddle, the grip insert, the hold pad and the butt pad (no glossier high spots: the driest thing on the gun);
  `anodised` on the alloy cover and rail (a 2 cm tile: at its own 4 cm its blotches read as woven cloth); `phosphate` on the sights,
  the controls, the hardware and the magazine. The barrel keeps its procedural finish (a turned set's lines are under a texel).
- **Black metal in the first-person view** (`black_metal_life`): a per-texel bead-blast sparkle on the alloy, long fine scratches
  beside the charging slot and on the rail's lands where an optic slides (and a few on the cover's top), bright thin wear on the
  lands' and the sight ears' top corners, pale dust in the rail's slots and round the screws (dark grime is invisible on black).
  The cover's `vary` went from 0.22 to 0.45 (satin smudges on its long top).
- **Magazine**: dark satin METAL now (`coat=0`, base 0.018 to 0.032, roughness 0.50 to 0.60). As a coating its base was already
  0.024 (measured on the texture), but a dielectric's 4 % sheen at roughness 0.5 read mid-grey on its broad sides in the studio light.
- **Decals** (`decals`):
  - `stencil_07`: the rack number, worn white stencil on the butt's left between the flutes and the pad. It replaces the cut, painted
    `07` (`parts.py` no longer cuts it; `MARK_RACK` is unused): one rack number, never two.
  - `witness` (two boxes): a thin dull-ochre paint-pen line across the rear sight's clamp onto the rail and down its rear face (the zero
    is marked). In the player's view.
  - `leak_soft` (two): oil run down from the charging slot (behind the vents, in the player's view) and from the front takedown pin.
  - `scrape_soft` (five): pale polymer scrapes on the butt's toe (side and underneath), the well's collar (faint: little of its box faces it) and the hand stop under the
    nose; and one used as a darkening mask, soot under the ejection port (a run of oil there read as a crack in the panel).
  - The data plate's two rivets (`hardware` in `parts.py`): on the bake source they are now joined after the cuts. Joined before,
    the cut dropped both domes, the bake's rays found nothing over the game mesh's rivets (108 of the plate's 480 faces took no
    kind) and they took the base steel with a flat normal. The game mesh is unchanged. Still without a kind: the lever's rounded
    rear end (54 faces, 0.13 cm2, at x -16.6), as before this pass.
  - Dropped: the armoury label. Remade aged and smaller, it had no flat olive panel on the left free
    of the flutes, the lettering and the bosses: under the flutes the side is a stack of creased strips and it broke into slivers.

## What moves

| Bone | Motion |
|---|---|
| `Bolt_Bone` | the carrier and bolt: 8.0 cm straight back into the butt, and forward again |
| `ChargingHandle_Bone` | 8.6 cm back along its slot to charge (it takes the bolt with it); it does not move when the gun fires |
| `Ammo` | the chambered cartridge: back with the bolt, then out of the port |
| `Trigger_Bone` | 8 degrees about its pin |
| `Safety_Bone` | the button: 0.30 cm to the right ("safe" to "fire"). It slides; on a carbine with a lever selector the lever turns |
| `MagRelease_Bone` | 0.20 cm forward, toward the magazine |
| `Clip_Bone`, `MagAmmo_Bone` | the magazine, straight down out of the well; the two cartridges seen in its mouth |

Every name is one the tool's earlier select-fire carbine had, with the same meaning. There is no `Stock_Bone` (nothing
slides).

## What the game finds on it

Sockets `Muzzle`, `AmmoEject` (the port, pointing right; it is **behind** the grip, 11.5 cm behind the origin), `MagWell` and
`MagDrop` (9 cm below it), also behind the grip, `BoltHandle` (the middle of the charging handle's knob, on its bone, on the
left of the handguard), `ForeEnd` (under the handguard, between the guard and the hand stop), `SightFront`, `SightRear`,
`Rail` (the middle of the free rail: where an optic would sit). The magazine is also a separate static mesh,
`SM_AssaultG3_Mag`.

## Budget

15,000 to 45,000 triangles at LOD0 (the ceiling was 30,000 until pass 3: a first-person rifle with a cover, pads and
hardware needs more), two LODs (50 % and 25 %), one 4096 px texture set. The floor was 8,000 while the shell was
one smooth, plain slab; with the faceted forms the shell, the guard and the grip need 15,000, as the carbines did (`budget` in
`weapon.py`).

## As built

**The final build**, after passes 3 to 6, the painted sets, the tight UV pack with texel zones and the look pass at the new
density (see those sections): 26,648 triangles at LOD0 (13,324 and 6,662 at LOD1 and LOD2), 18
parts, 10 bones, 9 sockets; the magazine alone is 1,148. Bounds x -31.66 to +38.80, y -2.60 to +3.44, z -12.35 to +14.75
(70.46 x 6.04 x 27.10). One 4096 px set, 65.8 % of the sheet covered (it was 46.5 %): 54.9 px/cm on a face of weight 1, 87 to 88 on
the rail, charging handle, cheek saddle, the cover's top and left shoulder, the fore-end's left and the front sight, 121 on the
rear sight, 44 on the grip, 33 on the butt pad, 29 on the underside and 26 on the 639 cm2 nobody sees in any pose. The bake's
rays missed the detail on 0.78 % (the limit is 2 %). 45 of 45 checks pass and `verify` matches the spec. Hero pictures:
`AssaultG3.png`, `_rear`, `_beauty`, `_fp` (the player's eye) and `_ads`. **Not imported into Unreal, and nobody
has seen it there**: the magazine and now the barrel are very dark metals (the magazine below a real metal's reflectance,
because as a coating it read mid-grey in the review light) and may read as holes in the engine; the fine grain, sparkle and
scratches are about one texel wide and may shimmer or vanish in the mips. Known and left: the concave corner and wedge where
the guard strap meets the grip (two attempts at a fillet stood proud and were reverted); a pale band on the grip's front and
the guard's riser in the beauty picture (the base colour there is olive; believed to be the key light at a grazing angle). A copy of
the build was kept before pass 3, before pass 4 and before pass 6, for `review --against`. The paragraphs below describe the first build with the
faceted forms and are kept for the record; where they differ, this paragraph and the sections above are right (the width is now
6.04 in a 5.7 to 6.4 range; the butt is raked with a hook and no longer a rectangle).

15,818 triangles at LOD0 (7,908 and 3,954 at LOD1 and LOD2), 16 parts, 10 bones, 9 sockets, fourteen collision boxes on the
static mesh; the magazine alone is 952. Bounds x -31.96 to +38.80, y -2.38 to +3.34, z -12.35 to +14.75 (70.76 x 5.72 x
27.10). One 4096 px set at 53.4 px/cm; the sheet is 51.3 % covered, and the bake's rays missed the detail on 0.58 % of it
(the limit is 2 %). 41 of 41 checks pass and `verify` matches the spec. Five files
in the weapon's `export/` folder. **Not imported into Unreal.** (Rebuilt with the new forms:
the figures above are the rebuild's; the first build's were 9,938 triangles, 57.5 px/cm and 0.23 % missed.)

One wall was met and is written up (PLAYBOOK, Modelling 49): with the engraved text first in the shell's list of small cuts,
every later cut in the right-hand side went to the second solver (10 of 31). With the text last, all 31 are exact. In the
rebuild the shell's detail model again has 3 of its 10 cuts and the grip's one union done with the second solver (the `[kit]`
notes); both parts were audited closed (no open or non-manifold edge, one piece, volume as the game mesh's).

Open points, for whoever looks at it next:

- **The forms were a slab and are not now.** The shell's section is faceted (see "Forms and edges"). What is still plain: the
  butt's side outline is nearly a rectangle (kept as it is on purpose), and the texture's edge wear is a judgement call.
- **The olive was chosen for this weapon.** A first trial came out a pale sage under the review light and the colour was deepened
  once. The grip and the guard are the same olive, the butt pad black rubber, the
  rail, sights, controls, barrel and magazine black steel.
- **The origin is high in the grip.** It is at the grip's upper third (the grip runs from z -6.04 to +4.58 round x = 0, now
  that it runs up into the shell), about 1.5 cm above the middle of the hold. The calibrated offsets would take that up.
- **The guard's strap is a moulded blade 0.75 cm thick and 2.2 wide**, widening to 2.8 where it meets the grip's toe and the
  handguard; one elbow of 2.7 cm inside radius. It was a 0.7 by 1.9 oval strap (thickened once from a first blockout where it
  read as wire). Where it meets the grip's toe it widens in plan only: there is no thickness fillet there (a fillet there
  stood out of the grip's rounded face as a plate).
- **The rifle is 5.72 wide, against a floor of 5.7 in the brief's check**: it passes by 0.02 cm, so a small change of the
  shell's width or of a knob would make that check miss.
- The engraved lines on the well are small (the largest is 0.42 cm high) and faint at arm's length.

## Approvals

The four approvals (concept, high-detail model, textures, look in the game) are recorded here per weapon; this rifle was built
ahead of them.

| | State |
|---|---|
| 1. Concept (the grey blockout) | open |
| 2. High-detail model | given for the faceted forms, on the before/after hero pictures; the cover, pads, hardware, raked butt and sights were judged by pairs in review only |
| 3. Textures | open (wear by use, the painted sets and the decals were judged by pairs in review only) |
| 4. Look in the game | open |

## Where it would go in the game

Using this rifle in a game is game code and data, not part of this asset: a weapon definition, the mesh path, the grip, muzzle
and hand offsets calibrated for it, and a reload of its own. That reload is not a conventional carbine's with other numbers: the
magazine comes out and goes in **behind** the firing hand, so the support hand reaches back under the forearm, and the
charging handle is forward on the left. Cases leave the port beside the shooter's cheek, on the right.
