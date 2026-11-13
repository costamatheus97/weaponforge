# weaponforge playbook

Every wall met while building the first weapons with the tool (a pistol first, then a bolt-action rifle, the first long gun and
the first with a wooden stock, and the weapons after them), what caused it, and what got past it. Most of the fixes are now
inside the tool; those entries are marked **[in the tool]** and are here so that you know why the code is the way it is before
you change it. The ones marked **[yours]** are things a new weapon still has to get right by hand.

Many entries describe a weapon by what it is ("a side-by-side shotgun", "a lever-action carbine") and quote the names of
builders, constants and checks from its code. Only `_template` and `assault_g3` are in this repo; the other weapons are not, so
a name from one of them (`split_at`, `STOCK_HW`, `tang_blank`, ...) is not in the code here. They are kept so that the lesson can
be followed; the technique is what matters.

When you hit something new, add it here: symptom, cause, fix, in that order.

Contents: 1 Working rules · 2 Tools and environment · 3 Modelling · 4 Mesh repair · 5 UVs · 6 Bake · 7 Textures and look ·
8 Rig and export · 9 Checks · 10 Unreal import · 11 Putting the weapon into the game · 12 Noise you can ignore ·
13 What nobody has verified

---

## 1. Working rules

- **Four things are the person's to approve: the concept, the high-detail model, the textures, the look in the game.** Show
  each as pictures (the `render` sheets), say plainly what is still wrong in them, and wait. On a first pistol the hammer,
  trigger guard and magazine release were all redesigned after a review picture; nothing was changed after the textures.
- **Report misses as misses.** The first pistol shipped with two failed checks (0.45 cm over its length brief because of the
  beavertail, 1,000 triangles under budget after junk removal). Both were stated in the report and accepted. A check that is
  edited until it passes is worth nothing.
- **The import only creates assets in the new weapon's own folder.** Nothing already in the game is overwritten by importing a
  new weapon.
- **Heavy jobs run headless and in the background** (a 4K bake is minutes). Write the next thing while they run.
- **"Why does that one look better than ours?" is a question about the tool, not about one gun.** Once, a showcase render of
  somebody else's gun and three photographs of a real pistol were set beside the tool's output with the question of what ours
  were missing. The answer given was to rebuild one weapon against one photograph, to the millimetre, for hours, and it was
  the wrong answer: the aim was to improve the pipeline so that it generates better, high quality, realistic weapons, not a
  1:1 3D match of one photographed gun. The right answer is a change in the shared code that every weapon gets (a
  finish, the lighting, a detail the kit can now cut), tried on ONE weapon as the test piece, with a picture in the
  person's hands inside the hour. A reference photograph is for proportions: one overlay to see the big errors
  ("Modelling", item 54), then stop measuring. And say what you are doing in pictures, early and often: a grey mesh
  after ten minutes beats a perfect one after three hours.
- **A weapon is the game's own design.** No real maker's name, logo, model name or markings on the mesh or in the textures.
- **After every pass, run `review --against` the build before it, and turn back what the pairs do not show as better.**
  Before a pass, keep the review pack of the build as it is (`weaponforge <id> review --out <folder>`, or a copy of the
  build's folder); after it, `weaponforge <id> review --against <that> --out <new folder>` and look at `pairs.png`, the
  changed crops first, and at the figures' changes in `compare.json`. A change whose crops look the same, or worse, is not
  progress however much work it was: turn it back, or say plainly why it stays (a figure it moves, a later pass that needs
  it). Ask "is the right one better than the left?" of each pair, not "how good is this out of ten": on AssaultG3 two
  reviewers gave one build 6.5 and 8.5, while pairwise calls agreed. With a judge at hand, `--critic` asks that of every
  changed pair and writes `punchlist.md`, worse first; it is advice, the pairs are the evidence (docs/review.md).
- **Keep the build as it is before every round of changes that will be shown.** `review --against` needs the earlier build's
  folder, and a build kept at another texture size is compared as it is. On a submachine gun the build approved at approval 2
  was copied whole as the baseline for the pass after it, and the build approved at approval 3 for the look pass after that;
  each pass was then paired with its own baseline.

## 2. Tools and environment

1. **The Blender MCP's viewport capture fails** with `Couldn't capture the view: [Errno 2] No such file or directory:
   '/tmp/blender_look_....png'` when Blender runs on Windows and the agent in WSL: the two do not share `/tmp`.
   **Fix [in the tool]:** `render` writes PNG sheets into the weapon's folder under the asset root (README, "Configure");
   read them from there.
2. (removed: specific to the project this tool came from)
3. **Operators fail in scripts with a context error** (no `context.area` in a headless or MCP-driven Blender).
   **Fix [in the tool]:** `weaponforge/ops.py` `run()` wraps an operator in a `temp_override`; in background mode, where no
   window exists, it calls it directly. Use `ops.run` for any operator you add.
4. **A live Blender and the headless one can be different builds** (5.2.3, the Store build, against 5.2.2 headless). No
   difference has shown up. The tool is tested headless; that is the reference.
5. **A render sheet that will not open** (`ENOMEM` from the Read tool on one large PNG): render smaller (`--res 900x600`) or
   fewer views. **[yours]**
6. **`python -m py_compile` leaves `.pyc` files** in a `__pycache__` folder beside the script. Check syntax
   with `python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" file.py` instead. **[yours]**
7. **Appending from the open file**: `ValueError: Cannot load from the current blend file.` Copy the `.blend` first and append
   from the copy. **[yours]**
8. **The Unreal editor MCP is usually not reachable** (`Unreal Editor not reachable at http://127.0.0.1:8000/mcp`) when no
   editor is open. Everything this pipeline needs from Unreal runs headless: `unreal-import` and `unreal-check` start the
   engine themselves. **[in the tool]**
9. **Arguments to an Unreal script** travel inside `-script="..."`, joined by spaces: no `"`, `%`, `^` or `&` in them,
   forward slashes in paths (`D:/some/folder/...` on Windows), and **an empty argument simply vanishes** (`--dest "$UNSET"` arrives
   as `--dest` followed by the next option). The scripts therefore stop on an option that has no value, and on one they do not
   know; never work around that. **[in the tool]**, and **[yours]** when you pass `--spec` or `--dest` by hand.
10. **Concept pictures.** The first pistol's three concept images and its walnut plank were painted with an AI image tool.
    Ask the person before doing the same. The image tool refused a prompt that said "police", "duty" and "combat"; plain words
    ("a classic service pistol") went through. **[yours]**
11. **A review sheet that is open cannot be replaced.** `render` died with `Could not write image: internal error` and
    `OpenImageIO write failed: Could not open file`: Windows locks a picture while a viewer, or the upload that just sent it
    to the person, has it open. **Fix [in the tool]:** the writer tries for a few seconds, then writes `<name>_new.png` beside
    it and says so; take sheet paths from the `wrote ...` lines. The next render that gets through removes the stand-in.
12. **`unrecognized arguments: render`** from `weaponforge <id> model --lp-only render`: a stage name after an option used to
    be refused. **Fix [in the tool]:** stages and options may now come in any order after the weapon's id.

## 3. Modelling

1. **The silhouette is decided by rendering, not by numbers.** The first hammer read as a stick, then as a lollipop, and hit
   the tang when cocked; the trigger guard was too square; the magazine release touched the grip panel. Each was only obvious in
   a close-up render from behind. **Fix [yours]:** render the views a player sees (rear three-quarter, first-person) early and
   often, and build a part that swings (a hammer) in its rest pose, then rotate it (`K.rot_y`) into the bound pose.
2. **A fixed part inside a moving one must clear it over the whole travel.** The pistol's chamber hood would have come through
   the slide roof at slide lock. **Fix:** the hood is a 0.77 cm radius cylinder under the slide's 0.80 cm tunnel, and the
   `Move` check proves 0.000 cm overlap at every step. Declare a `Move` for everything that travels **[yours]**; the check is
   **[in the tool]**.
3. **Coplanar faces break booleans** (non-manifold edges where a cutter's face lies in a face of its target, or two parts
   share a surface). **Fix [yours]:** offset by 0.02 to 0.08 cm in the builder: inset the outline, start the cutter a hair
   outside, leave air between a part and the hole it sits in (the template's `TUNNEL_CLEAR`, `WELL_CLEAR`).
4. **Booleans use the EXACT solver.** `K.boolean` does; the float solver left debris. (Its one failure is item 10.)
   **[in the tool]**
5. **Large roundings are real geometry, small ones are not.** Round the outline (`K.round_poly`) or bevel before the boolean;
   the 0.01 to 0.03 cm edge break that makes metal look machined comes from the Bevel shader at bake time, per surface kind.
   Modelling it costs thousands of triangles and makes the slivers of section 4. **[in the tool]** (`bake.KINDS`)
6. **The triangle budget is one dial.** The first game mesh was 4,400 triangles against a 15,000 to 30,000 budget.
   **Fix:** every game-resolution segment count goes through `seg(hp, lo, hi)`, scaled by `LP_Q` in `parts.py`; 3.0 gave the
   pistol about 15,000. The bake source was about 45,000. **[yours]** to set, pattern **[in the template]**.
7. **`K.prism_m` with a mirroring matrix** (determinant below zero) needs its normals flipped; it does that itself. Duplicate
   points in a lathe profile, inverted wedge cutters and cutters narrower than the thing they cut were the other builder bugs:
   all visible in the first grey render. **[in the tool]** / **[yours]**
8. **Do not leave sealed pockets.** A never-visible cavity under the magazine follower had its normals flipped by the
   cleanup, and showed up as olive patches in 1.4% of the normal map. **Fix [yours]:** end a cavity on the part that closes it,
   so there is no pocket. If patches of wrong colour appear in a normal map, map the texels back to 3D through the UVs to find
   the faces.
9. **A builder that leaves a helper behind** (an untagged cutter) fails the `model` stage by name. Remove cutters, or let
   `K.boolean` do it (`keep=False` is the default). **[in the tool]**
10. **A boolean can return nothing at all, without an error.** The rifle's stock came back with 0 triangles: the builder
    reported 476 triangles for stock, pad and grip cap together and the render showed no wood. Every cutter worked alone; one
    cut after another whose surface it nearly shared (the bolt handle's notch after the receiver's inlet) made the EXACT
    solver give an empty mesh, and moving a radius by a hair made it work again. **Fix [in the tool]:** `K.boolean` compares
    the volume before and after; when the solid has vanished it starts again, applies the cutters one at a time, hands the one
    that empties it to the MANIFOLD solver (FLOAT where there is none), and prints
    `[kit] boolean: <part> DIFFERENCE: the EXACT solver returned nothing; 1 of 10 cuts were done with the MANIFOLD solver
    instead (the first took the volume from ... to ...)`, one line per call.
    **Its second silent failure** is a closed part that comes back with sheets of the cutter hanging on it: the second and
    third of three ring grooves round the rifle's bolt shroud left discs of the cutters standing out of it (seen in a render as
    lines through the part), and several screw and marking cuts each left a triangle missing. The guard catches that the same
    way: a closed solid that has open edges after the cut is redone cutter by cutter. On the rifle's high-detail parts it
    steps in on the stock, receiver, barrel and shroud every build; the game parts have not needed it. Still broken with both
    solvers is an error that names the cutter. **[yours]:** read each builder's triangle count in the `model` log (a part that
    suddenly has a few hundred is this), and never leave a wall a few hundredths of a centimetre thick between two cutters:
    let them overlap (the rifle's `screw_cuts`: the slot ends inside the ring groove).
11. **An organic part is a loft, not a stack of prisms.** A stock built from extruded outlines and bevels reads as a plank.
    **Fix [in the tool]:** `K.loft` over rings from `K.section`, their height from the side outline (`K.span`), their width
    and squareness from tables through `K.curve` (docs/kit.md, "Organic parts"). Square the section where the wood meets metal
    (exponent 6 under the action), round it where a hand goes (2 to 2.5), and put a ring at every corner of the outline
    (`K.stations`) or the corner is cut off. **[yours]** to shape; look at it from `fp` and `q_rear_r`, not only from the side.
12. **A slicing plane goes on for ever.** The grip cap is the part of the stock below a tilted plane; carried on, the same
    plane also sliced the toe of the butt off. **Fix [yours]:** a slab cutter ends where the part ends (the rifle's `cap_slab`
    stops at the cap's rear edge).
13. **A long gun is unreadable on a pistol's review sheet**: a metre of rifle in a 3:2 tile is a thin strip, and the action, a
    hand's width of it, is a few dozen pixels. **Fix [in the tool]:** wide one-column tiles and an `_angles` sheet for anything
    over three times as long as it is high; **[yours]:** give `closeups` boxes for the action and the muzzle, and set
    `pose_closeup` and `pose_views` so the pose sheets show the side the bolt or the port is on.
14. **Show the action open before there is a rig.** The concept and the high-detail model are approved on grey sheets; a
    closed action hides the bolt, the port and the magazine. **Fix [in the tool]:** `render --what grey` also writes
    `<sheet>_pose_<pose>.png`, moving the parts by their bone tags exactly as the rig will. Write the `poses` with the first
    blockout. **[yours]**
15. **Checkering on a curved surface.** The pistol's panels are flat, so straight V-groove prisms did it; on a stock the same
    prisms would cut to the bone where the wood bulges and miss it where it falls away. **Fix [in the tool]:**
    `K.grooves_on(part, lines, frame, coll)` drops 2D lines onto the part and builds each groove along the surface, at one
    depth; `K.hatch(outline, angle, pitch)` makes the lines of one direction inside a panel's outline. Per panel: one cutter
    at `+angle`, one at `-angle`, one for the border line; make all the cutters first (they follow the surface as it is)
    and cut once per set with `K.cut_grooves(part, [cutters that do not cross], coll)` (item 25: never `K.boolean`).
    Pitch 0.17 cm, grooves 0.14 wide and 0.06 deep, 62 degrees on a grip and 28 along a fore-end. The rifle's four panels
    add 170,000 triangles to the bake source (the carbine's whole high-detail stock, four panels too, builds in 5 s); the
    game mesh gets none of it. **[yours]** to place:
    keep a panel on the flank, where the surface faces the side (a groove stops where the normal turns more than about 70
    degrees from the drawing plane's).
16. **An inside cut begun under a sloping top comes out through it.** The shotgun's bolt cavity started under the hump at
    the back of its receiver and opened the receiver's rear top. Every check still passed: a hole removes an overlap, so the
    `moves` check cannot see it. **Fix [yours]:** start a cavity where the wall above it is still thick, shorten the travel
    that needed the room, and look at the grey sheets from above and behind (`top`, `q_rear_r`) after any change to an inside
    cut.
17. **Two cuts that meet become one cutter.** Two cutters that touch along a line, or leave a 0.03 cm step between them (the
    shotgun's magazine-tube hole against its cavity floor), send the cut to the second solver or leave a sliver. **Fix
    [yours]:** draw the whole inside as one outline and cut once: `K.prism` of a section (the shotgun's `cavity_section`), or
    one lathe profile with a step in it (the carbine's bolt tunnel and barrel thread).
18. **Shape a moving part to the hole it closes.** A round bolt behind a square ejection port let the next shell be seen
    past it. **Fix [yours]:** the shotgun's bolt is a D-section block as wide as its port, and the cavity is only as wide as
    the bolt above the shells. On the carbine the port is cut out of a tube, so a round bolt fills it.
19. **Ring cuts close together.** A crest thinner than about 0.09 cm between two ring grooves (a thread) risks the exact
    solver: the suppressed pistol's thread is 0.16 cm pitch with grooves half that. Coaxial cuts through the pointed end
    of a lathe (its fan of triangles) go to the second solver every time; that is harmless, the guard checks the result.
20. **A cutter must not come to a point where it crosses the part.** A lathe profile that ends on the axis closes with a fan
    of triangles; near the axis they are a few thousandths of a centimetre wide. The carbine's receiver bed was cut into the
    stock with such a lathe, its fan crossing the wood's top 0.2 cm from the axis. That cut came back closed, and then
    every later exact cut into the stock returned open edges:
    `4 of 8 cuts were done with the MANIFOLD solver instead (cut 5, 6, 7, 8; ...)`. Nothing looked wrong in a render.
    Turning the cutter (`start`) cured the game mesh and not the bake source; a cutter with flat ends cures both. **Fix
    [yours]:** end a cutting lathe's profile off the axis, so `K.lathe` closes each end with one flat face (the carbine's
    `lathe_cut`), or use `K.cylinder`. A lathe that is a part may still end in a point. **[in the tool]:** the log line names
    which cuts fell back, in the order the builder listed them; a run of cuts that all come after one cutter points at
    that cutter, not at themselves. To find such a thing, try the cutters one at a time in a scratch script with
    `K._booleans` and `K._measure` (volume, open edges) on a copy of the part.
21. **A band's inside goes inside what it holds.** A ring, clamp or sleeve whose bore is the held part's surface plus 0.02 cm
    puts two surfaces a hair apart for its whole length (flicker in the engine, a dark line in the occlusion bake). **Fix
    [yours]:** make the bore smaller than the held part, so it ends inside that part's wall and is never seen: the shotgun's
    clamp, the carbine's barrel band, gas block, front sight band and flash hider. Keep the 0.02 cm seat for parts that sit
    in a hole you can look into (a receiver in its bed, a magazine in its well).
22. **A second wooden part on the first** (a handguard on a stock) sits flush only if it is skinned from the same numbers.
    The carbine's handguard takes its half-width from the stock's own `STOCK_HW` table (times 0.955: the stock's top corner
    is rounded, so a full-width handguard would overhang it) and puts its widest point on the stock's top; the joint is
    then a fine V line, not a ledge. A band round both is the **hull** of the two sections where it sits
    (`mathutils.geometry.convex_hull_2d`), grown by its thickness (`band_outline`). Hold the stock's section constant under
    the band, or the band fits at one end only.
23. **A curved magazine is a loft down a centre line.** `params.mag_centre(s)` gives the line (straight inside the gun, so
    the magazine still leaves straight down; an arc below the belly) and the section's turn; `mag_ring` puts a rounded
    rectangle across it. Start every ring at the middle of the rear face: the loft then has a line of edges there for the
    UV seam (`mag_seam`, kept through `K.cleanup(..., keep=...)`). Pressed ribs that follow the curve are `K.grooves_on`
    lines made from the same centre line. Check on paper that the top round clears the feed lips and the bolt clears the
    top round: with two columns the round lies off centre and comes up under one lip.
24. **`hp_kinds` is called with the bake source's names** (`Round_HP`, `Shell_HP.001`). A test on the game part's name
    misses, and the part bakes as one kind (the shotgun's hulls would have been brass). Strip the suffix first:
    `name = obj.name.split('.')[0]`, then drop a trailing `_HP`.
25. **The exact solver skips stretches of a groove and says nothing.** The carbine's fore-end checkering came out with a
    bald patch three diamonds long: two neighbouring lines of the second set, half a centimetre each, were never cut. The
    mesh was closed, the volume plausible, the log clean; it was found by eye on the high-detail close-up. One cutter per
    panel instead of one per set made it worse (22 sections against 16). The manifold solver cut every section, with no
    open edges, in 0.8 s against 18 s. **Fix [in the tool]:** `K.cut_grooves(part, cutters, coll)` joins the cutters of
    `K.grooves_on`, cuts with the manifold solver and then **looks for every groove**: each cutter carries the places of its
    sections, and a ray down the middle of each must reach its bottom. If any is missing it tries the other solver; if both
    leave some uncut it stops with the count and the place. `stocks.checker` and the recoil pad use it; use it for every
    `grooves_on` cutter. Built the old way in a scratch file, the shotgun's stock has no section missing and **the rifle's
    has 9 of 4,874** (second line set, right side of the fore-end, x 30 to 39): the rifle's approved bake carried them.
26. **A big flat wall shades in streaks.** With plain smooth shading the corners of a flat face lean toward the rounded
    corner or the soft groove beside it; over a face as large as a magazine's wall that is a gradient, drawn in streaks
    along the face's triangles, and the bake copies it into the normal map. **Fix [in the tool]:** `K.shade(obj, angle,
    flats=True)` also writes weighted normals, so the flat keeps its own normal (the carbine's magazine). With it, an edge
    softer than `angle` on that flat all but disappears, so make a groove's edges hard: the magazine's ribs slope at 24
    degrees and the part is shaded at 20; the bake's bevel then rounds them like pressed steel. The game mesh does not
    need this: its finish writes weighted normals anyway.
27. **Parts that turn about an axis parallel to the bore (a revolver's crane and cylinder).** Build each one about its own
    axis and make the bones a chain: the crane on the frame, the cylinder on the crane, the ejector and one bone a
    cartridge on the cylinder. One pose or `Move` of the crane then carries all of them. Work the swing out on paper
    before modelling (a revolver's `params.py`, "the swing"): a point at distance r from the pivot rises to
    `pivot_z + r` before it comes down, so the cylinder's window needs that much air above the cylinder, the crane's own
    top corner has to be round about the cylinder's axis (then it rises no more than the cylinder does), and the window's
    edge nearest the pivot has to be broken where the cylinder passes it. The crane reads as part of the frame only when
    its outer face and its front face are flush with the frame's and its pocket is open to the side and the front; as a
    plate set back in the frame's side it looked like a stuck-on block. Sign: `+rot` about X takes the weapon's left
    (+Y) up toward +Z, so swinging out to the left and down is a negative angle (`about_x` and `swing` in
    that revolver's `weapon.py`).
28. **The exact solver hands back a piece of the cutter in place of the part.** A polymer pistol's slide (84.5 cm3) came back from
    its barrel-hole cut as 0.32 cm3: the stub of the cutter that stood in the channel behind the wall it was to drill. The
    mesh was closed, so nothing looked broken until the render showed a pistol without a slide. **Cause:** edges of no
    length. The slide's outline had rounded corners with edges 0.04 cm long, and a bevel 0.10 and 0.14 cm wide was run
    round that outline; clamped, it leaves vertices on top of each other. **Fix [yours]:** `K.cleanup(obj, dissolve_deg=0.0)`
    after any bevel that is wider than the shortest edge it runs along, before the first boolean. **[in the tool]:**
    `K.boolean` now compares the result's volume with what the operation can leave (a cut can take at most the cutters'
    volume, a union can add at most that) and redoes the cut with the other solver when it is outside; the log says
    `returned a solid of ... cm3`. That line is a reason to look for the zero-length edges, not only to carry on. The test
    applies to a part in one piece cut by closed cutters. Tried on trial rebuilds of the seven weapons that
    existed before it (both pistols' first model and its variant, both rifles, the shotgun, the first carbine, the
    revolver): it fired on none of them, every rebuild ended as before, and `tests/smoke.sh` passes with it.
29. **A bevel "of the outline" that runs across the flat.** After a boolean a flat cap is several faces, and the edges
    between them lie in the cap's plane: `K.is_outline` is true for them. Use `K.on_rim(e, axis)` in the predicate (one of
    the edge's faces is the cap and the other is not), as a polymer pistol's trigger guard does after its opening is cut.
30. **The game mesh is never rounder than the bake source.** `seg(hp, lo, hi)` is `lo * LP_Q` on the game mesh: cap it at
    `hi` (that pistol's `seg`), or raising `LP_Q` to reach a triangle floor gives a barrel with more sides than the surface it
    is baked from. A small gun with flat sides has few triangles' worth of shape; set its floor to fit in the definition
    and say why in the BRIEF (a polymer pistol, a revolver) instead of spending triangles where they show nowhere. **Do not set
    that floor from the modelling stage's count**: it says "about N before cleanup", and the UV stage then merges the
    triangles the cuts left across flat faces. That pistol went from 10,210 to 6,798, a third less, and missed the floor that
    had been set from the first number. Run `uv --size 512` on a trial copy and read `mesh: triangles` there.
31. **Four from a select-fire carbine with two receivers.** A cartridge whose chamber lies inside several hidden parts needs the
    same `chamber_cut` through each of them, or it is "modelled into" every one it touches. A step that a round part
    stands on belongs in the side outline of the part that carries it, and its top must not be level with the round
    part's axis. Two parts that both move (the charging handle over the collapsed stock) cannot be shown clear of each
    other by one `Move`: measure the gap on the meshes in `checks()`. A button that is pressed must have somewhere to go:
    a cross bolt in a hole of its own, not a head in a pocket beside the magazine well.
32. **Five from a select-fire rifle with a sheet-steel receiver.** Pressed ribs across an arched cover: skin the cover over rings
    (`K.loft`) with four rings per rib, and let the rib lift the arch only (`arch(..., grow)` adds nothing where the arch
    meets its sides), or a rib proud of the cover's sides is in the way of whatever lies against them. A lever that is bound
    turned: draw it lying along the bore, build it there, then turn the finished mesh with `K.rot_y(pivot, degrees)`; the
    bone sits on the pivot and every `Move` and pose is measured from where it is bound. A cut off on a slant: a cutter
    built with `K.prism_m` in a frame turned about the bore. A part that widens along its length: scale `v.co.y` by a
    factor that grows with x, which keeps every flat face flat. A ring on the barrel that carries a block: make the ring
    0.10 longer than the block at each end, so no end face of one lies in an end face of the other. The trial run at
    512 px showed two things the grey sheets could not: the true triangle count (13,976 against a floor guessed at 15,000)
    and a moulded grip that came out a light terracotta from numbers that looked dark on paper.
33. **A loft that ends exactly where its side outline ends got `None` for its last ring.** `K.round_poly` gives back
    single-precision numbers (mathutils), so the outline's end at x = -7.82 is really at -7.82000017, and `K.span` at the
    number it was drawn with missed by more than its tolerance of 1e-9: "cannot unpack non-iterable NoneType" in a submachine gun's
    stock, whose rings run to the very butt and to the receiver's end. The wooden stocks never met it, because their
    skinned solid runs past the butt and is cut square afterwards. **Fix [in the tool]:** `K.span` now takes a station
    within 1e-5 cm of a segment's end as on it and never reads beyond the segment. A butt whose edges are round without a
    bevel: narrow the width table over the last 2 and 7 mm (that stock's `STOCK_HW`) and let the outline's fillets round the
    heel and the toe.
34. **Two round parts that cross shallowly leave a knife groove, and the mesh finisher folds it shut.** A submachine gun's sight
    tower was a ring on the barrel and a cap on the cocking tube, two parallel cylinders overlapping by 0.12 cm, with a
    web between them that was shorter than both. Where the web ended, the two round surfaces met in a groove 36 degrees
    wide. The union was clean and the part was closed before `uv`; the finisher's weld and sliver removal then folded the
    groove's bottom into one edge with four faces: `mesh: closed` and `rig: game meshes` missed with "open edges
    {'SightFront': 2}", only in the 512 px trial, because both are counted after `uv`. **Fix:** draw the two circles and
    the flat flank between them as ONE outline and extrude it (`tower_section` in that gun's builders), the way the
    receiver's box and tube are one outline (`rec_section`). In general: two solids of one part should cross at a clear
    angle or not at all; where they must overlap shallowly, the outline of both is the part.
35. **A round boss exactly as wide as the flat end it sits on leaves a loose edge.** A submachine gun's selector hub (radius 0.42)
    touched the flat rear end of the lever's plate, which was drawn 0.42 behind the pivot: after the union one edge of the
    hub stayed in the mesh with no face on it. The finisher deletes such edges from the game part, so no check saw it, but
    the bake source kept it. **Fix:** end the plate inside the hub's circle (or clearly outside it); never on it. To find
    such edges in a built file, count `len(e.link_faces)` per edge over both collections: 0 is a loose edge, 1 a hole, 3
    or more a fold.
36. **A break-action is one bone on the hinge pin, and everything on it is drawn round the pin.** On a side-by-side shotgun. What worked:
    - `Barrel_Bone` sits on the pin and carries the barrels, the fore-end with its iron, the extractor and both shells
      (the last three on child bones), so one rotation opens the gun and the travel check (`Move('barrels open', ...)`,
      four steps to 32 degrees) proves it. Every surface that slides is an arc about the pin with a named radius in
      `params.py`: the action's knuckle (1.15), the iron's seat (knuckle + `CLEAR`), the lump's rear arc (4.50, inside the
      slot's 4.62), the lump's nose (0.95, inside the knuckle). A check (`hinge: drawn round the pin`) compares the
      radii, so a number changed later cannot quietly make the gun jam.
    - The action is the cut of three outlines: its side (`act_side`: underside, knuckle arc, flats, breech face, fences,
      top strap), its section seen from the muzzle (`act_section`: flat sides and the two fences' rounds) and its plan
      (`act_plan`: narrowing to the stock), each a prism, intersected. Three plain outlines gave a clean solid where
      unions of fences and blocks would have met tangentially (items 2 and 34).
    - **The breech wall must cover the shells' rims.** The first build cut the top lever's pocket right through the
      breech face, and the rims showed from behind between the fences. The pocket now stops at a wall
      (`WALL_X`), and the notch between the fences has a flat floor above the rims (`NOTCH_Z`).
    - The extractor and the shells are checked against the barrels alone (`CHK.penetration(riders, [barrels], ...)`):
      they only move when the gun is open, where the action is not in their way; against everything, the closed action
      reads as a collision.
    - `sights: clear line` on a side-by-side looks only at points near the middle plane (`abs(p.y) < RIB_HW + 0.1`):
      the barrels' round tops stand either side of the eye's line, not in it.
    - Whether a shell can come out is plain trigonometry, kept as a function in `params.py`
      (`shell_clears_fences()`) and checked (`hinge: opens far enough to load`).
37. **Checkering can leave a pinhole in the bake source.** `K.cleanup` drops the sliver faces a boolean makes, and now
    and then the faces round one do not close over where it was: a side-by-side shotgun's fore-end had one hole of five edges, a
    millimetre across, with a stray edge in it, among 24,000 faces. Only game meshes are checked for being closed, so
    nothing said so; it was found by counting faces per edge (item 35). **Fix [in the tool]:** `K.mend(obj)` deletes
    stray edges and gives every hole of up to eight edges a face, and prints a `[kit] mend:` note when it did anything;
    `stocks.checker` calls it after its cleanup. Call it yourself after any other fine cut into a bake source
    (`K.cut_grooves` followed by `K.cleanup`).
38. **The bevel's overlap clamp can shrink a rounding to nothing, without a word.** A side-by-side shotgun's action asked for 0.30 cm
    on its long edges and got 0.008. Its underside is tangent to the hinge knuckle, so the bottom edge runs straight on
    into the arc's first segment, 5.6 degrees off it; the clamp measures how far the bevel's end may slide along that
    next edge, and it shrinks the width of the WHOLE `K.bevel` call, so the top edges lost their rounding too. The grey
    sheets looked plausible (smooth shading rounds a hard edge by eye). The only symptom was one needle triangle at the
    bevel's end, and only in the 512 px trial (`mesh: no degenerate triangles`, counted after `uv`). **Fix:** give the
    rounding an edge to stop on where its edge turns into a curve (`split_at(obj, x)` in
    that shotgun's builders: a bisect across the part; the bevel then ends there in a small flat fan), and pass
    `clamp=False` when nothing else lies within the bevel's width. **[in the tool]** `K.bevel` now measures the strip it
    made against the one asked for and prints `[kit] bevel: ... the overlap clamp left about N% of it`. When a rounding
    matters to the look, measure it: `CHK.section(obj, z)` gives the points of the part's cut at a height; read the
    width off them.
39. **A rounding that ends part-way along an edge is cut, not bevelled.** A service pistol's grip straps were meant to be
    rounded by 0.62 and 0.55 cm from under the grip up to the web of the hand and the trigger guard. With the clamp on
    the bevel made nothing (item 38). With `clamp=False` it made the rounding and tore both of its ends: fangs where
    the back strap turns into the web's hollow, a spike at the heel, a tooth under the dust cover, and a crease across
    the whole side of the frame, because a bevel that ends on an edge running on in nearly the same direction slides
    its last vertices along that edge. A stop edge (item 38) cures the tear and leaves a step as wide as the rounding,
    which is no way for a strap to end. **Fix [in the tool]:** `K.fillet_cutter(name, stations, coll, seg)` makes a
    cutter whose section is the corner less the rounding's disc, swept through stations along the edge; cut it out with
    `K.boolean`. `K.edge_stations(path, y, radius, solid, fade_in, fade_out)` writes the stations for the usual case,
    the edge an `'XZ'` prism's outline makes with its side. Three things it does that a bevel cannot:
    - it cannot be clamped: the radius asked for is the radius made (that pistol's check `frame: back strap rounded` reads
      it off a cross-section: 0.62 asked, 0.62 found);
    - it runs out through the end of the part: start the path beyond the solid (a point 1.6 cm below the grip, 0.8 cm
      ahead of the dust cover) and the rounding leaves through the bottom or the front face the way a milled one does;
    - it fades: `fade_out=1.5` lets the radius fall to a millimetre over the last 1.5 cm while the cutter lifts out of
      the solid, so the rounding tapers to nothing with no step.
    Take the path from the outline's own points (`frame_profile(seg90)`, the same list the prism was made from), so the
    cutter bends exactly where the solid does. Leave out the stretch where the outline rounds a corner into an end face
    (the heel, the toe): let the cutter run straight through it. The game mesh and the bake source use the same path
    and differ only in `seg`. The frame's triangle count fell from 7,042 to 3,696 with it. `K.cleanup`'s 0.5 degree
    dissolve may straighten the rounding's edge on the side face across a slight bend of the path (a face 5.6 degrees
    off the side, so 0.08 cm along it is 0.008 cm of surface): harmless, but measure the rounding by the flat it leaves
    on the strap, not by where it meets the side.
40. **A stem right across a magazine well is in the magazine's way.** One pistol's magazine release is one lathe from the
    button on the left to its pin's end on the right, through the well. The travel check passed there by luck of the
    numbers; on another pistol the corner of the magazine's mouth went through the stem 1 cm into its travel (0.078 cm,
    `moving: magazine leaves`). Nothing can see the stem. **Fix:** the button and the pin's end are two stubs, each
    stopping inside its own side wall (`mag_release` in that pistol's builders). To find what a moving part
    touches, call `CHK.penetration(moving, [one part], matrix)` for each other part in turn: the check only names the
    depth.
41. **A screw in a checkered panel needs an island.** `F.screw_cuts` draws a ring and a slot 0.04 cm deep; in a field
    of grooves 0.06 deep they cannot be seen. **Fix [in the tool]:** `K.hatch(..., islands=[((a, b), radius)])` stops
    the lines short of a round patch and picks them up behind it; give the patch a border (`K.arc` through 360 degrees
    as a closed line for `K.grooves_on`) and put the screw on the flat.
42. **Make every groove cutter before cutting with any** (it is in `K.grooves_on`'s text, and easy to get wrong in a
    loop). A pistol's panels made the second direction's cutter after the first direction was cut: its lines followed
    the first grooves down, and `K.cut_grooves` stopped with "108 of 1283 groove sections uncut" under both solvers.
    The order is: all `grooves_on` calls, then one `cut_grooves` per line direction, then the border.
43. **Steel let flush into a skinned part is a slice of that part.** A lever-action carbine's two tangs lie in the wrist of its stock,
    whose top and underside are ovals: a flat bar would stand proud at its edges or sink at its middle. Each tang is a
    copy of the stock's own solid, intersected with a bar that is as thick as the tang inside the wood and open on the
    outside (`tang_blank`, `tangs` in that carbine's builders), so its outer face is the wood's surface. The same bar,
    0.02 cm bigger on its sides, end and inner face, is the cutter that makes its place in the wood. It is the trick
    `stocks.pad_and_cap` uses for a grip cap, and it works for any plate in any lofted part. Run the slice a few
    millimetres into the part it is joined to (the receiver) and union the two: a tang that only touches the receiver
    leaves a seam, and a face in a face.
44. **Draw a turning part on one side of its pin.** Every point of a part that turns goes round the pin: what lies behind
    the pin at its height goes down, but what stands above the pin goes back first, and what lies ahead of it comes up.
    A lever-action carbine's finger lever is a bar from its pin back to the loop, with nothing above the pin's height but a round boss,
    so the whole of it leaves the receiver's floor downward and the slot it lies in needs only 0.03 cm of air (the top
    rear corner of its arm goes 0.01 cm back before it has dropped clear). Its loading gate first turned about a line
    0.6 cm ahead of its own front end: that end swung 0.05 cm forward into the edge of its opening (`moving: loading
    gate`, 0.032 at 25 degrees). The line is now on the plate's end, and that end has 0.05 cm more air than the others.
    When a turning part must have an arm on the far side of its pin, give that arm a round end about the pin.
45. **Two bones for one stroke are tested one at a time.** A lever turns and its bolt slides, so they are two bones and
    two `Move`s: each is tested with the other still in its bound pose, and nothing tests them together. That is enough
    when their paths do not cross (that carbine's lever is under the receiver and its bolt inside it). What a `Move` cannot
    show is a part that is pushed by another on the way: its hammer is bound cocked so that `bolt travel` proves
    the bolt clears it as it lies, and `hammer falls` proves the hammer's own swing; that the bolt's rear end lays a
    fallen hammer back is left to the game's animation, and `motion` in the spec says so.
46. **A variant cannot move one of its base's numbers by importing the base.** `params.py` works its derived numbers out
    as it is imported: the base's module has one `MUZZLE_X`, and where the rib ends, where the bead stands, the sockets
    and the checks are already numbers by the time a variant could set another. Setting it afterwards moves the muzzle
    and nothing that follows from it. **Fix [in the tool]:** `weaponforge.variant.rerun` runs the base's `params.py`,
    `parts.py` and `weapon.py` again inside the variant's own modules, with the top-level numbers the variant names
    pinned to its values (a sawn-off double-barrel: `MUZZLE_X`, `TUBE_R1`, `BEAD_X`, `SIGHT_Z`). The base's builders, class,
    sockets and checks then come out at the variant's numbers, the variant overrides only what a saw changes that a
    number does not (a stub of a stock, no bead, no butt in the collision and the brief), and nothing in the base's
    folder is touched. A pin the base's file does not assign exactly once at its top level stops the run by name.
    Two things to keep straight: a value that is the same metal on both guns (the barrel's radius where the saw went
    through) is read from the base's module, not typed again; and a table the base filled before the variant redefined
    a function (`BUILDERS`) still holds the base's function until the variant puts its own in.
47. **A loft can end in a rounded flat without a bevel.** The sawn stock's end is the stock's own section at each of a
    few stations, drawn in a little more at each (`K.section(hw - d, lo + d, hi - d, ...)`, the inset following a quarter
    circle), and the loft's own cap face is the flat the saw left. No bevel runs round a loft's end ring, so the overlap
    clamp of item 38 has nothing to shrink, and the game mesh and the bake source get the same rounding from the same
    code. The UV seam then takes the flat's rim (`F.rim`) as well as the centre plane, so the flat is a piece of its own.

48. **A cutter whose corners lie exactly in the target's edges spoils every exact cut after it.** A select-fire carbine's
    suppressor is a lathe (40 segments in the game mesh, 72 in the bake source), and the cuts on its axis were cylinders
    made the same way round. The hole in its front cap (15 segments, `start=DOWN`) has a corner at 72 degrees, and so has
    the fan of triangles that closes the lathe's end (8 x 9 degrees). That cut came back closed and whole; the NEXT exact
    cut, the socket at the other end of the body, returned 3 open edges, and they were at the first hole (edges of no
    length, where the cutter's corner met the fan's edge). In the bake source it was the dish in the front cap (48 segments
    against the fan's 72: every third corner in an edge) and then the joint groove (a `K.tube` of 72 segments on a body of
    72: every one of its edges crosses one of the body's), and each sent every later cut to the second solver (`8 of 11
    cuts`, then `14 of 14` for the collar's scallops). A scratch run pinned it down: either cut alone is clean, the two in
    the other order are clean, and the first cutter turned 2.3 degrees about the bore, or given 16 segments, is clean.
    **Fix [yours]:** turn a coaxial cutter a degree or two off the target's segment lines (`turned(obj, deg)` in
    that suppressor's builders, a rotation about the bore), a different odd angle for each; half a segment
    is not enough when the two counts share a factor. With three cutters turned, all 2 + 11 + 14 cuts went through the
    exact solver. The price: a turned cutter has no line of vertices underneath, so the hole's wall gets no UV seam along
    it (these holes are hidden or small). **How to tell:** the log names the cuts that were redone; when they are all the
    cuts AFTER a certain one, look at that one, not at them. This is very likely what lies behind item 19's "coaxial cuts
    through the pointed end of a lathe go to the second solver every time" and item 20; no earlier weapon was rebuilt to
    find out.

49. **Cut the engraved text last.** AssaultG3's shell is one side outline 51 cm long, and all the small cuts of its bake
    source go into its two flat sides: five lines of text, eight pins, twelve vents, six flutes. With the text first in
    the list, the log said `10 of 31 cuts were done with the MANIFOLD solver instead (cut 13, 15, 17, ... 31)`: the last
    pin on the right side and then every vent and every flute on the right side, and not one on the left. The right side
    is where `FIRE` is; the left carries four lines of text and was untouched. The same list with the five text cuts moved
    to the end: all 31 through the exact solver, and the build took 3.5 s where it had taken 8.1. Nothing else was changed
    between the two runs, and which letter does it was not looked for. **Fix [yours]:** build the list coarse to fine (pins,
    slots, flutes, then `K.text_solid`), so that nothing has to be cut into a face the text has already been cut into.
    **How to tell:** the redone cuts are all on one flat face, they are the cuts AFTER a certain point, and there is text
    in that face earlier in the list. Like item 48 it is a cut that comes back whole and spoils the ones after it; unlike
    item 48, turning nothing helps, only the order.

50. **A fillet's path has to start on the straight run, not on a corner's arc.** (Items 50 to 52, and "Bake" item 10,
    were found on the FIRST design of a magnum pistol, a slab-sided one. A second design measured from a photograph of a
    real magnum pistol took its place, item 54; the first design's definition is not included.) Its back strap was rounded with
    `K.fillet_cutter(K.edge_stations(path, ...))`, and the path was taken from the frame's outline by a filter on its
    points. The first points it let through lay on the arc of the heel's corner. The builder carries the path on 1.6 cm
    past its first point, along its first direction, so that the cutter leaves through the bottom of the grip; there that
    direction was the arc's chord, so 1.6 cm of cutter went off sideways through the heel. The log said `Frame DIFFERENCE: the EXACT solver returned nothing; 2 of 6
    cuts were done with the MANIFOLD solver instead (cut 1, 4)`: the two back-strap cutters, the left and the right.
    **Fix [yours]:** make the filter start above the arc (`P.GRIP_BOT + 0.9 < q.y`), so the first two points are on the
    strap itself. No fallback afterwards. **How to tell:** the redone cuts are the
    fillet cutters, in pairs; look at where the path begins.

51. **The cleanup's weld could cap an engraving, and nothing said so.** A magnum pistol's barrel has `MOD. G4` cut into its left
    flank and `CAL 11 mm MAG` into its right. In the high-detail sheet the right flank read `CAL` and nothing more. The log
    was clean, the part was closed, in one piece, and its volume was right to four figures (95.1138 against 95.1171).
    What it was not: the boolean. Traced step by step, the cut came back whole (all twelve letters' floors there and facing
    out). It had left one edge 0.00004 cm long at the right-hand end of the `L`, an edge of the letter's wall whose two
    ends both also lay in the flank's face (one face of 187 corners, the letters' holes joined into its outline).
    `K.cleanup` welds at 0.0001 cm, so the two ends became one, the flank's face touched itself there, and the stretch of
    its outline between the two places, which went round the holes of the seven letters after the `L`, came away as a face
    of its own lying over them: 14 edges folded flat. `recalc_face_normals` then turned eight of the twelve floors to face
    inward. Things that looked like causes and were not: both texts in one cut list or each in its own, the flutes above
    them, the depth of the text. Moving the right-hand text 0.037 cm down, or 1.2 cm along, "fixed" it, by moving the short
    edge somewhere harmless. **Fix [in the tool]:** `K.cleanup` now looks for the faces its weld would pinch (`_pinched`:
    a face holding, at two places of its outline that are not neighbours, vertices about to become one), cuts those
    faces into triangles first, and says so: `[kit] cleanup: Barrel: 1 face(s) the weld would have pinched were cut into
    triangles first`. A run of coincident vertices one after another is not a pinch and is left to the weld (a bevel the
    clamp left without width is hundreds of them). **How to tell, on a file built before the fix:** read every engraved
    line in the grey high-detail sheets, on both sides, letter by letter. A capped letter is simply absent; no check
    looks for it. Section 13 lists what a rebuild of every older weapon's model found.

52. **On a block barrel the middle of the muzzle's face is not the bore.** A turned barrel's muzzle face is a ring round
    the bore, and `CHK.face_centre` of it is the bore's centre: that is how every earlier weapon measures its `Muzzle`
    socket against the mesh. That pistol's barrel is a block with a rib above the bore and a foot below it, so the middle of
    its front face is not on the axis, and a socket that is right would be measured as wrong.
    **Fix [yours]:** measure from something that is round about the bore. The first design read it off the floor of the
    muzzle's counterbore; the present one has no counterbore and a leaning muzzle face, and takes the ring of points one
    bore radius from the axis within 1.2 cm of the muzzle (`_bore_centre` in that pistol's `weapon.py`).

53. **A pistol's hammer angle may not be free: the game may work the lever out from the mesh.** In the game this tool was
    first used for, the pistol animation code racked every pistol's slide by 3.4 cm and took the hammer's lever as the height
    of the `Muzzle` socket above `Hammer_Bone` (which had to come to at least 0.5 cm). It then turned the hammer by
    atan(travel / lever). Find out what yours does. If it works like that, a hammer bound cocked has to be modelled at
    exactly that angle from "down", with the bone on its pivot: a magnum pistol's pivot was 2.05 cm under the bore, hence
    58.9 degrees, the same as two earlier pistols only because the lever was made the same (its third build has the pivot
    2.97 cm under a lower bore, hence 48.9 degrees: item 63). Put the pivot elsewhere and the angle follows; write it as
    `math.degrees(math.atan2(SLIDE_TRAVEL, lever))` in `params.py`, not as a number. The slot in the slide has to take
    the cocked hammer over all the travel the MESH clears (4.6 cm on the magnum pistol, for a 4.0 cm cartridge), not only the
    3.4 the game uses: the move `slide travel` tests each step up to `limit`, and the check `hammer: under the slide when
    cocked` compares the hammer's top with the slot's roof.

54. **A weapon asked for by its real-world counterpart is measured from a photograph, not drawn from memory.** The request
    was for a particular large magnum pistol in place of an invented one. The first blockout, drawn from memory of the
    shape, had the right parts in the
    right order and still read wrong beside a photograph: the trigger guard 0.9 cm too far forward and too small, the
    beavertail thin and drooping, the two grip straps parallel where the real grip widens toward the butt, a safety like
    a key, and no cut on the slide's upper rear corner. Two more things only showed when the photograph was ENLARGED:
    the block under the muzzle reaches down in front of the frame (the blockout had the frame's nose run to the muzzle),
    and the grasping grooves are narrow with wide lands (the blockout had broad flutes). **What worked:**
    - One clean side photograph under a free licence (Wikimedia Commons), in a folder of its own under the scratch
      directory, read only with `python3 -I`. It is a reference for proportions; nothing of it goes into the asset.
    - A scale from two points that are known (the overall length, 27 cm, between the beavertail's tip and the muzzle), then
      every other position read off in pixels and turned into the weapon frame: the slide's rear, the breech face, the
      arms' end, the guard's opening, the straps at two heights, the grip's top edge, each pin and lever. A short script
      that prints the object's first and last column on a pixel row (and row on a column) reads an outline far better
      than the eye does.
    - Crops enlarged two times for the small things (safety, takedown lever, the muzzle's end).
    - The grey game-parts sheet beside the photograph after every round; three rounds were needed.
    **Watch for perspective.** That photograph was taken from slightly below, so the grip is drawn larger than the slide:
    the back strap measured 26 to 29 degrees and was built at 20.
    **What is copied and what is not.** The pattern (the shapes and proportions that make it that gun) is what was asked
    for. The maker's name, logo, model name and real serial are not put on it: the rule is "no real brand or markings", the
    engraving is the weapon's own (`MOD. G4`, `CAL .50 MAG`), and the brief says so.

55. **A block that hangs below a part's own section (the block under a magnum's muzzle).** The barrel is one section run
    from breech to muzzle; under the muzzle it goes on down in front of the frame, narrower than the barrel and with
    rounded lower edges. Joining a second solid on would share faces with the first (item 3). **Fix [yours]:** draw the
    SECTION deeper than anything that is kept, then cut away everything under the line with one cutter: a box with the
    block's own shape hollowed out of it (`foot_block` in that pistol's builders; the beavertail's `tang_cap` is
    the same idea). Three details made it clean:
    - The shape that is hollowed out is drawn taller and longer than what is kept of it, so the swept roundings of its
      edges (`K.fillet_cutter`) run out of it at both ends and never end inside the part.
    - The arc of its lower front corner ends 0.01 cm AHEAD of the muzzle's face, so the cut crosses that face at an angle.
      Ending exactly on the face would leave the cutter touching it along a line, which is item 3 again.
    - The rounding that runs up the muzzle's face fades to 0.10 cm at the line (`fade_out`), which is the width of the
      chamfer on the barrel's face above it: the edge reads as one edge from top to bottom.

56. **Chamfer a face before a cut puts a short edge beside it.** The muzzle's face is chamfered 0.09 cm all round. With
    the block under the muzzle cut FIRST, the chamfer would have ended on the 0.1 cm ledge where the block is narrower
    than the barrel, and Blender's overlap clamp shrinks a bevel to the shortest edge it meets (item 38). **Fix [yours]:**
    bevel the whole rim while the section is still plain, then make the cut: the cut ends the chamfer cleanly at the
    line. The general rule: a bevel goes on before any cut that leaves an edge shorter than its width at one of its ends.

57. **`F.rim` does not find the fold in a face of two planes.** The slide's rear face is two planes (it leans 0.30 cm per
    cm, and 0.92 over its top centimetre). `F.rim(point, normal)` takes an edge as the face's rim when one of its faces
    is turned away from the normal by more than about 26 degrees (a dot product under 0.9). The two planes differ by
    25.9 degrees, so the line where they meet passed by 0.0006: luck. **Fix [yours]:** name such a line yourself in the
    bevel's test (`abs(m.z - zk) < 2e-3 and abs(m.x - xk) < 2e-3` in `slide()`), and call `F.rim` once per plane.

58. **`min() iterable argument is empty` in a weapon's own check.** A check that takes the lowest point of a part "between
    x 6 and x 17" finds no points there when that stretch is a plain prism: after the cleanup a long flat face has
    vertices only at its ends. a magnum pistol's check `barrel: fixed, on its lug` stopped the `check` stage twice that way, after the
    model, the bake and the textures had run. **Fix [yours]:** measure at the faces that END the stretch (the barrel's
    rear face, the lug's rear face), or cut a section with `CHK.section`. And run `check` once on the grey game parts
    (`model --lp-only check`) before a bake is spent on them.

59. **A loft that closes to a tip shows a cross of creases on its end.** The end of a magnum pistol's beavertail is a loft of
    rounded rectangles that draws in to a point (`tang_cap`). From behind, which is where the player's eye is, its end
    showed four light ridges running from the corners to the tip, in the grey renders and under the textures. Turning the
    section into an ellipse toward the tip did not cure it. The cause is where the POINTS are: a rounded rectangle has
    them in four clusters, one per corner, with one long edge between two clusters. An ellipse drawn through points
    clustered like that is still four flats, and the clusters stand up between them. **Fix [yours]:** as the section
    turns oval, move its points to an even spacing round it as well (`cap_ring` in that pistol's builders: point
    k of corner c goes to the angle 45 + 90 c + (k - n / 2) * 90 / (n + 1) degrees on the ellipse). The ring keeps its
    point count, so `K.loft` still joins it to the rectangle before it. Look at any closed-off end from straight behind
    before a bake is spent; the sheet `grey_game_parts_rear.png` has that view.

60. **A barrel's section has to hold its bore.** A magnum pistol's second section was drawn from a side photograph alone: the
    heights were measured, the widths guessed. It passed every check and was wrong in a way no side view shows: the
    bore's axis was so high that the rail's cross slots cut into the bore, and the inclined flats lay 0.61 cm from an
    axis whose bore is 0.63 in radius. Nothing reported it, because cutters overlap silently. **Fix [yours]:** before
    building a barrel that is not a plain tube, write the section down as numbers and check three walls by hand: bore
    radius plus 0.25 cm under the deepest slot on top, the same to each flat (the distance of the flat's PLANE from the
    axis, `FLAT_D` in that pistol's `params.py`), and the same to the muzzle face's lower break. A side photograph
    gives heights only; what tells you where the axis is are the parts drilled square to a face (a brake's ports, a gas
    plug): they point at it. The same weapon's round chamber turned out to be nearly the barrel's whole width (r 1.40
    of 1.53), not a thin tube (0.97): if a cylinder's bright streak in the photograph is well below its top edge, it is
    a big cylinder.

61. **Small studs standing on a surface (a pebbled rubber grip).** Cutting or uniting 480 domes into a bake source is 480
    booleans. `K.studs_on(obj, points, frame, coll, r, h)` ray-casts each point onto the part and stands a closed dome
    there, sunk a hair into the surface; the domes are one mesh that is `K.join`ed to the part for the bake only (the
    bake's rays take the nearest surface, and the dome is nearer). It prints how many of the points found the surface.
    The game mesh gets none of them: at 0.08 cm they are normal-map detail.

62. **An outline made as the hull of swept arcs is full of nearly straight runs, and each is a sliver triangle.** The
    pocket a safety lever sweeps in a magnum pistol's slide is the convex hull of the lever at five angles. Cut into the
    slide, its floor came out with one triangle of 4e-05 cm2 (three points 0.001 cm off a line), which `check` reports
    as "triangles Unreal would skip" and which came and went as unrelated dimensions changed. **Fix [yours]:** drop the
    points of such an outline that stand less than 0.006 cm off the line between their neighbours before using it as a
    cutter (`thinned` in that pistol's builders); corners of arcs are far over that and stay.

63. **When a dimension that other dimensions hang on moves, look for what was derived from it.** Lowering a magnum pistol's
    bore axis moved its hammer's pivot 0.43 cm down into the frame's floor, because the pivot had been written as
    "the bore's height less the lever arm" (to make the cock angle come out at 45 degrees). The check for moving parts
    caught it ("deepest overlap at rest 0.299 cm"). A pivot is a place on the frame: write it as a number, and derive
    the ANGLE from it (the game works the lever out as the muzzle's height above the hammer bone, item 53).

64. **Big faces with nothing on them: what makes a weapon read as a block.** A render of someone
    else's submachine gun, set beside ours, looked more finished ("more AAA"). Taking the two apart, the largest single
    difference is not the finish or the light: on that gun no point of a big face is more than a centimetre or two from
    something modelled (a recessed screw, a pin, a panel line, a rib, a slot, a stippled panel, a line of lettering),
    and ours have faces of 50 to 200 cm2 that are a plain slab (a stock, a bullpup's shell, a receiver's side). No
    texture recipe fixes that: clouding and edge lines (Textures and look, item 17) draw what is modelled and nothing
    else. **In the tool:** `check` now says which faces these are, as a note that is never counted as a miss:
    `note look: bare faces ... Receiver, the left side, 24 of its 87 cm2 (steel)`. A point of a flat face is bare when
    the bake found no edge, groove or lettering within 1 cm of it; covered faces (a frame under its grip, a butt under
    its pad), curved faces and wood are left out (`check.bare_faces`, `BARE_REACH`, `BARE_AREA`). **[yours]:** treat
    the list as the to-do list of the detail pass, before the first bake, and put the detail **into the detail model
    only** (the `hp` branch of the builder): it costs no triangles, and an existing weapon needs just
    `model --hp-only` and the chain from `bake`. What real guns have there: the pins and screws that hold the thing
    together (where the trigger, hammer and stock really pivot or fasten), the seam where two pressings or mouldings
    meet, lightening or stiffening ribs, a recessed panel round a control, inspection and model lettering, a sling
    slot. Put them where the mechanism would have them: a row of screws with no reason reads as decoration.
    `K.studs_on`, `K.grooves_on`, `K.cut_grooves`, `K.hatch`, `K.text_solid`, `F.screw_cuts` and `F.pin_cuts` are
    the helpers so far, and `K.drop(part, [(x, z)], frame)` gives the place and the normal a screw or a recess needs
    on a surface that is not flat. A wooden stock is exempt on purpose; a steel or polymer face that stays plain
    should be a decision, not an omission. **The worked example was a submachine gun's stock** (`stock` in
    that gun's builders, numbers `STOCK_PANEL` to `STOCK_SLING` in its `params.py`; not included): the note read "Stock, the
    right side, 34 of its 78 cm2; the left side, 34 of its 78 cm2"; a sunk panel's outline with three flutes, the two
    screws of the cap over the receiver and a sling slot went into the `hp` branch, about twenty lines.
65. **An outline of one thickness with rounded edges reads as a CAD blockout, however much is baked onto it.**
    AssaultG3's first build was a side outline extruded to one width, every edge given the same small break, and all
    its detail in the normal map. Baked detail (item 64) did not save it: the big forms carried no light. It was
    reworked in two passes, and the first pass is the lesson as much as the second. **Pass 1 answered
    "flat" with roundness**: a smooth superellipse crown along the shell, a tube for the guard's strap, a soft rim
    round the well. It came out as a bar of soap: no face to catch a light, shading in vertical bands, nothing that
    looked designed. **Pass 2 used facets with a hierarchy**, and that is what to do: (a) a section made of flat
    facets that meet in creases with a real radius (the shell: a land under the rail, a shoulder at 40 degrees, a
    nearly upright side with 2.5 degrees of draft, a belt line where the lower moulding stands 0.13 cm proud, a lower
    facet tucked in toward the underside); the creases get about three chords in the game mesh. (b) The section
    changes along the length: every change of width is a ramp 2 to 3 cm long with crisp ends, and the belt line jogs.
    A constant section swept along a line still looks extruded. (c) One or two large radii only where a hand goes
    (the webs where the grip meets the shell). (d) An edge hierarchy in the bake: `edge_break` in the weapon
    (0.10 cm on polymer, 0.045 on steel there, against the tool's 0.035 and 0.030), so that a moulding's edges are
    soft and steel's are tight. (e) Lofted parts need their seams said: a strap lofted round its centre line
    unwrapped as one patch with a stretch of 1,060 until its centre line, inside and outside, was seamed
    (`grip_seam` in `weapons/assault_g3/parts.py`; 1.67 after). The worked example is AssaultG3: the section block in
    its `params.py` (`hw`, `belt`, `facets`, `ring`, `side_y`), `shell_loft`, `grip_loft` and `guard_loft` in its
    `parts.py`. It cost about 6,000 triangles (9,938 to 15,818), which is what a first-person rifle should have had.
    The section's arithmetic and the loft are now in the kit (item 66); the section itself is still that weapon's own.
66. **Start from the shared builders, not from a copy of another weapon's.** AssaultG3's reusable builders were moved
    into the kit: `sections.py` (the facets, plain Python for `params.py`), `forms.py` (the section loft,
    pockets, bosses, the frame a mark is placed in), more of `fittings.py` (screws, pins, plates, sling fittings,
    moulding and selector marks). Its rear aperture and front post clamped on a rail (`sights.py`) and its gas block,
    castellated nut and flash hider (`barrels.py`) stayed in its own folder. The move was checked by building AssaultG3 with the
    tool before and after:
    all 71 objects (18 game parts, 18 bake sources, 35 marks) came out with the same vertices, triangles, bounds and
    shading, and a polymer-frame pistol the same. **[yours]:** take the technique first (`sections.py`, `forms.py`, `fittings.py`) and give it your numbers
    (docs/kit.md lists the arguments). `weapons/assault_g3/sights.py` and `barrels.py` are not technique but one design each, AssaultG3's, with its
    sizes as arguments: copy them only when the brief asks for that design (a rail with clamped iron sights; a gas block, a
    castellated nut, a slotted hider), and design any other sight or muzzle device in the weapon's own folder (SmgG2 uses
    neither). Copy a weapon's builder only for what the kit does not have, and when a second weapon needs it too, move it
    in the same way. What they keep, so you do not have to relearn it: small parts (rivets, a pin's clip) are joined after
    the cuts that would nick them; no cavity is closed (a pocket opens to the outside, item 8); an aperture's countersunk
    rim has 10 x `LP_Q` sides in the game mesh, where the eye is closest, and the serrations round it stop at a flat
    land, so the rim stays a circle; game and detail models are built from the same numbers and agree in silhouette; the cuts come in an
    order that keeps the exact solver's hand-offs where they were (items 48 and 49). Two things to watch. A default
    worked out from other arguments can differ from the number a weapon typed by the last binary digit (12.90 + 0.30 is
    not 13.20 in floating point), so a weapon that must build to the same vertices passes its own numbers. That rim's
    sides go against item 30: at AssaultG3's `LP_Q` of 3.4 they are 34 in the game mesh and 32 in the bake source. It
    was kept so that weapon builds the same; at a lower `LP_Q` it does not arise. And a builder
    that only one weapon has used is proven on that weapon only: `tests/kit_builders.sh` builds a small rifle from the
    defaults and runs the model and mesh checks on it, which is the least to run after changing one.
67. **Judge the model by its filled side outline laid over the concept's.** On a submachine gun the approved build had the
    drawing's numbers (the belly rose 0.7 cm, the top fell 0.6) and still read from the side as a long rectangle with a
    narrower one in front: a step at the collar had eaten 0.2 of the sweep, a level rib hid the falling top, and the hand
    stop hung lower than the belly's tail. The nose is fixed by the barrel (the belly cannot be higher than 4.45 under a 0.93
    bushing on a 5.6 bore), so the sweep had to come from the tail: a chin on the receiver's collar, the shroud's belly
    rising 1.25 cm to the nose, its top falling 0.9, the walls closing in from 1.75 to 1.45 half width, the nose at half
    the tail's height (2.5 against 4.65). **[yours]:** draw the filled outline of the model at the concept's scale and put one
    over the other before approval 2; the numbers in a table do not show a wedge that reads as two boxes.
68. **A tapering loft needs every facet to taper.** The shroud's top land kept its width while the walls closed in; its
    four-sided facets twisted, a twisted four-sided face is two triangles whose diagonal a boolean may turn, and the game
    shroud's sixth slot "added" 0.5 cm3 (24.33 to 24.85) with both solvers, and the builder stopped on a volume message two
    steps later. **Fix:** the land narrows with the walls, so every facet is a flat parallelogram. **[yours]:** when a lofted
    body tapers, taper every width on it with it.
69. **Sink a panel into a flat side.** The first panel on a grip followed a palm swell (the side curved); its floor, capped
    in strips, shaded as vertical streaks. **Fix:** flat sides that lean out toward the base, one panel on each, its edges
    along the straps and square to the axis. Hatch lines shorter than 1 cm are dropped (a stub is left in a slanted area's
    corner). **[yours]:** a panel's floor is flat, or it is not a panel.
70. **A control is read from the direction the hip eye has.** A charging handle that was a turned knob on a neck was end-on to
    the hip eye and read as a screw. It became a hooked tab of pressed sheet: a stem standing 1.3 cm out of its slot, the outer
    end turned forward into a lip, taller outside than at its root, a hole through the stem, a cover plate on the wall over
    the slot and an end stop riveted behind the slot's rear end (0.05 cm short of it at full travel, held by a check).
    **[yours]:** look at every control from the hip and aiming eyes, not from the side.
71. **Spend spare triangles where the eye is.** A pass that added 2,560 triangles (16,350 to 18,910) put them in the hood ring
    (36 to 48 sides), the aperture and its countersink (36 to 48), the thread protector (27 to 42), the barrel seen through
    the slots (24 to 30), a wire stock's rods (15 to 21 round and 9 to 12 chords a bend) and the new handle; nothing went on
    the magazine, the underside or the right side. **[yours]:** the same order.
72. **A cutter face in the plane of a target face, or a ring cutter with the target's own segment count, sends the cut to
    the second solver.** Seen on a lower's well cuts after a 10 degree rake and on a rear sight's 30 cuts; two fallbacks stayed
    in that build, closed and checked. **[yours]:** offset a cutter off the face (item 3), and give a ring cutter a count the
    target does not have.

## 4. Mesh repair

All of this happens in the `uv` stage (`mesh.finish`) on the game parts only. The bake source is never made watertight; the
bake does not need it.

1. **Booleans leave open and doubled geometry** (30 non-manifold edges on the first frame). **Fix [in the tool]:** weld at
   `WELD = 5e-4` cm, dissolve degenerate faces, drop duplicate faces and the extra faces on edges with three or more, fill
   holes. Result: zero open edges on all 14 pistol parts.
2. **Do not weld harder to make a problem go away.** A weld at 4e-4 made the tang worse; a forced cleanup took 36 triangles
   out of the frame and left an edge with four faces; `remove_doubles(0.01)` ate real detail. Fix the builder (section 3.3)
   and keep the weld where it is. **[yours]**
3. **Blender's Triangulate and Weighted Normal modifiers made non-manifold edges**, and the weighting depended on the
   triangulation. **Fix [in the tool]:** own triangulation in bmesh, then own weighted normals (coplanar regions found at
   1 degree, weight by region area squared, written as custom split normals).
4. **Shading bands on a smooth area** (under the beavertail) came from hard-edge flags lost on edges the repair re-created.
   **Fix [in the tool]:** hard edges are marked again from the finished triangles at 30 degrees, then the normals. Anything
   that changes hard edges means a full re-unwrap and re-bake: seams follow hard edges.
5. **Unreal drops degenerate triangles, silently, and then the counts do not match.** Its static-mesh import skips every
   triangle under 5e-5 cm² (`THRESH_POINTS_ARE_SAME` in the tangent pass). The pistol lost exactly 143 triangles that way and
   came in as `[14129, 7135, 3567]` against a spec of `[14272, 7136, 3568]`. **Fix [in the tool]:** `mesh.drop_micro` (part
   of the `uv` stage's finish) collapses edges under `MICRO = 2e-3` cm and needle slivers, flips the long edge of flat cap slivers when both new triangles
   are larger, and leaves nothing under `AREA_MIN = 6e-5` cm². The surface moved by at most 34 µm. The check
   `mesh: no degenerate triangles` holds the line, and the Unreal check compares the counts.
6. **Leftover n-gons** crash the UV density code (`too many values to unpack`). The finish re-triangulates leftovers.
   **[in the tool]**
7. **The decimator makes its own slivers in the LODs.** A rebuild of the pistol left one triangle of 2e-5 cm² in LOD1: a
   corner sitting on a crease between two others, which cannot be flipped away (the neighbour is in another plane) and has no
   short edge to collapse. The check `rig: game meshes` caught it. **Fix [in the tool]:** LOD meshes get one more step
   (`clean_micro(caps=True)`): the middle corner is merged into the nearer end of the crease, only along an edge shorter
   than 0.2 cm, and only for a triangle under the engine's own 5e-5 cm² (not the safety band up to 6e-5: the approved
   pistol's LOD1 has one triangle in that band, Unreal keeps it, and a regression test against that pistol's approved export
   (not included) caught the first version of this fix removing it). The texture shifts by a pixel or two around it, so the full-detail mesh is deliberately not treated this way: if `mesh: no degenerate triangles` misses on
   LOD0, fix the builder (section 3.3).

## 5. UVs

1. **The recipe [in the tool]:** seams on every hard edge and on the edges the weapon's `seams()` names; `unwrap` angle-based; a patch whose texel-area ratio (95th over
   5th percentile) is above 1.8 is recut with smart project at 60 degrees; islands scaled to one density; packed concave,
   axis-aligned rotation, margin 0.0024 of the sheet (10 px at 4K), one sheet for the whole weapon. The pistol came out at
   93 px/cm on a 4K sheet with 58% coverage.
2. **One texel density for every part.** Per-part weights (0.75 to 0.9) broke the rule that all parts are within 10% of each
   other; the check `uv: texel density` enforces it. Leave `density = {}` unless a part is never seen up close, and say so
   when you do. **[yours]** (To spend texels by place, with the check told what was meant: item 8.)
3. **The `uv` stage's time varies a lot** (from under a second to 35 s for meshes of a few hundred triangles; the pistol
   takes about 20 s). It is the concave pack. It is not stuck.
4. **Parts with many small features make many islands** (the pistol's slide: about 170, from the serrations). That is
   expected; coverage, not island count, is what to watch.
5. **A long closed surface needs a seam of its own.** The rifle's first sheet had 44% coverage and 49 px/cm: the stock's
   outside (smooth all round, 77 cm long) and the barrel had no hard edge to open along, so they were cut up by angle into
   bent strips as long as the gun, and the longest island sets the scale of the whole sheet. **Fix [in the tool] + [yours]:**
   `Weapon.seams(obj)` returns a test for the edges to cut along. One cut along the underside of the barrel, receiver, bolt
   and shroud; for the stock one ring round the wrist, the underside, the top of the wrist and the fore-end's nose (butt in one
   piece, fore part as a left and a right side). 60% and 57 px/cm with nothing else changed. The `uv` log prints a `recut:`
   line for every patch that still had to be cut up by angle, with where it is: read those, and give the ones that show a seam.
6. **The seam needs a line of edges to follow, and three things remove it.** (a) A lathe, tube or cylinder along X starts its
   vertices on a diagonal, so there is none underneath: build it with `start=(0, 0, -1)`. (b) The cleanup merges the two sides
   of a flat stretch across the line (the stock's flat belly lost its centre line, and the two sides stayed joined by a 2 cm
   bridge, which is enough to spoil the unwrap): `K.cleanup(obj, keep=pred)` with the same test the seam uses. (c) A loft has
   a ring only where a station is: `K.stations(..., must=[x])` for a ring a seam goes round. The count of
   `seam edges of its own` in the `uv` log, and a `recut:` line for the patch, are how you see a line that is broken. **[yours]**
7. **No island may be longer than the sheet.** At 57 px/cm a 4096 px sheet holds 70 cm: a metre-long piece has to be cut
   across somewhere (the wrist, under a sight base) however good its seam along. **[yours]**
8. **Half the sheet empty, and the texels spread evenly over faces nobody sees.** AssaultG3 had 48.8 px/cm on its 4096 sheet
   at 46.5 % coverage. That is 839 islands, and its moulded grain, bead-blast sparkle and fine scratches were 1 to 2 texels
   wide: they shimmer or vanish in the game. Measured:
   - Blender's packer left a 28 % web of channels between the islands and 11.5 % in the hollows of curved and L-shaped islands.
     No setting of `pack_islands` did better: AABB, CONVEX, any rotation and packing twice all gave 43 to 46 %.
   - Its `margin` is the space round EACH island. 0.0024 gave 20 px between two islands at 4096, not the 10 the old comment said.
   - 39 % of the surface is faces nobody sees: between parts, inside the well, the tunnel, the bore, the bolt, the rounds. Only
     24 % is seen from the first-person eye, yet both got the same density. The per-builder `density` weights could not help:
     the check holds parts to the area-weighted rms of the weights, so the rms had to stay under 1.11.

   **Fix [in the tool], opt-in:**
   - `uv_pack = 'tight'` packs each island's real outline, biggest first, at the lowest place it fits, in four quarter turns.
     That gave 55 % at the same margin.
   - `uv_margin = 0.0017` (14 px between islands) gave 63 %. The bake pads every island 24 px, the neighbours meet halfway,
     and 14 px keeps mip 2 (1024 px) clean under bilinear filtering, as 20 did. Mip 3 needs 30 px and was never clean. Do not
     go lower.
   - `texel_hidden = 0.45` and `texel_zones` (docs/texels.md, "Texels by place") put 1.6 times the density on the rear
     sight, the rail, the charging handle, the cheek saddle, the cover's top and left shoulder and the fore-end's left.
   - The result: 94 px/cm where the player looks (it was 47 to 67), 59 on everything undeclared, 28 on the hidden faces, and a
     mean of 56.9. Over every face a first-person eye can see, 76 px/cm (it was 51); the grip and the butt pad are seen too,
     but they were asked for less (47 and 35). The closest two islands are 15 px apart, and the bake's rays missed 0.86 %.
   - Pass 4 (the new sights): a face is now hidden only when its centre AND three quarters of the way to each
     corner are covered or shut in. On the same geometry that took the faces seen from the first-person eye yet given the
     hidden weight from 9.7 to 5.9 cm2. It also took the hidden surface from 975 to 639 cm2: faces with an end showing now get
     their texels, at about 2 px/cm off everything else (worked out from the areas, not built). What is left is faces with a surface under 0.3 cm in front of all of
     them (the butt pad against the shell, 0.24 cm off it; and, likely the same, 2 cm2 on the front sight), seen only through a slit.
   - The rear sight got its own weight, 2.2 (122 px/cm; in the aiming view it is 8 to 15 cm from the eye), and the front
     sight 1.6 (88). They cost everything else 1.1 and 0.2 px/cm: 55.3 for weight 1, 88 on the rest of the foreground,
     66.6 % of the sheet.
   - The check `uv: texel density` now holds each part to 10 % of what its declared faces ask for, the same 10 % as before;
     a part with no declared face is held to the weight-1 density itself. `uv: texel zones` names the dense and sparse parts
     with their numbers.

   **What to look for:**
   - the `tight pack:` lines in the `uv` log (the scale each try reached, and the island that stopped the next one);
   - `texels:` lines that say how many cm2 each zone took (a zone that matches no face is a miss);
   - `textures/work/uv_layout.png`;
   - in `hero`, seams or a neighbour's colour at the edges of the islands, and lettering that has gone soft;
   - the curvature and wear masks: they are worked out per texel (`maps.py`, the normal's divergence and a blur of so many
     px), so on a denser island the same edge break is a narrower, weaker line. On AssaultG3's faces made 1.3 times denser or
     more, the edge mask fell from 0.056 to 0.040 per cm2 and the wear zone from 0.169 to 0.125; the surface with a strong
     edge (over 0.5) halved, 3.9 to 1.9 %. The sparse faces went the other way. Not fixed: the masks would have to know each
     island's weight.

   The tight pack takes about five minutes where Blender's takes seconds. **[yours]:** zones are boxes in the weapon frame;
   check the `texels:` lines after moving a part.

9. **Zones drawn by hand do not carry to the next weapon.** AssaultG3's nine boxes took several passes and fit no other gun.
   **Fix [in the tool], opt-in:** `texel_view = True` (docs/texels.md, "Texels by view") weighs the faces by what the `hero` eyes
   `fp` and `ads` see of them, in every pose.
   - **What a weight by screen density alone did.** The hip eye meets the cover at a grazing angle: 20 to 40 screen px per
     cm of surface, the same as the far end of the barrel. Weighed by that alone, the cover stayed near the base and 17 % of
     what an eye in any direction sees reached 80 px/cm (hand zones: 47 %). So every face an eye sees gets at least 1.4, and the screen
     density only lifts it further (1.75 from 25 px/cm, 2.2 from 62).
   - **Fragments.** Steps by face cut the sights and the charging handle into islands of a few cm2: 1,366 islands against
     the hand zones' 1,196. Holding a run under 4 cm2 to its neighbour made it worse: a strip along the cover grew longer
     than the sheet (4,791 px) and the whole pack had to shrink to 40 %. Weighing every seen part with less than 90 cm2 not
     hidden as one piece gave 1,184 islands and 487 weight seams (hand zones: 620). Only when a quarter of the part is
     seen or less than 20 cm2 of it is not: a polymer pistol's barrel, 0.9 % of it seen close in the slide-back pose, was lifted
     whole to 2.2 and took 22 % of the used sheet (7 % with the defaults).
   - **Against the hand zones, same geometry (pass 6), at the uv stage:** what the hero frames show 90.7 px/cm against
     86.3; the rear sight 122.6 against 117.6; coverage 64.6 % against 65.8. The plain surface is lower: the check
     `uv: texel zones` gives the faces neither eye sees (x0.90, 2095 cm2) 51.5 px/cm, where the hand zones' undeclared faces
     (1317 cm2) got 54.8, 6 % less; on the same faces (seen by no eye in any direction, not hidden) 55.0 against 55.6.
     Measured with an eye in any direction (the frame left out: the cheek pad, the magazine and the grip count),
     71.2 against 73.0, and 36 % of it at 80 px/cm or more against 48 %: the hand zones also gave the cheek pad 1.6, which
     no frame shows. So AssaultG3 keeps its hand zones.
   - **A polymer pistol, which nobody tuned:** what the hero frames show 184 px/cm (95 with the defaults), the sights 157 and 184,
     the slide 125, the frame 115, the barrel 91, the faces no eye sees 95, the hidden faces 50; 70 % of the sheet with
     the tight pack (50 % before), 358 islands (338). (The 95 is the faces no eye in any direction sees, not hidden; the
     check's class "seen by neither eye" is wider.)

   **What to look for:** the `texels: eyes:` line (an eye in the wrong place sees the wrong side: compare it with the
   `hero` note for `fp` and `ads`), the cm2 on each step, and `weighed whole`. The constants (`uv.VIEW_*`) were chosen on
   AssaultG3. **[yours]:** the eyes know nothing of hands, animations or a scope; add a `TexelZone` on top for those.

## 6. Bake

1. **Settings that worked first time and were never changed [in the tool]:** selected-to-active without a cage, extrusion
   0.02 cm, max ray distance 0.25 cm, no bake margin (own dilation afterwards); tangent normals at 64 samples, occlusion at
   128; ID and coverage as emission bakes; float, non-colour images; Bevel shader at 12 samples with a radius per surface kind
   (steel and bright 0.030 cm, dark 0.026, brass and copper 0.020, wood 0.014).
2. **Each game part bakes only from its own high-detail twin** (same builder), so neighbours cannot print onto it. For
   occlusion only, `ao_friends` names the builders whose parts shade each other because they never move apart (grip panels
   and frame; sights and slide). Parts that do move apart must not be friends, or the slide carries a shadow of the frame
   when it is back. **[yours]**
3. **The bake blocks a live Blender for minutes.** Run it headless (`weaponforge <id> bake`). A 4K pistol bake is 240 to
   340 s on the GPU, 13 to 48 s per part; missed rays were under 1% of the covered texels and take their neighbours' values.
4. **`RuntimeError: Error: No valid selected objects`** from the bake: the high-detail collection was hidden (look-dev hides
   it). The stage un-hides collections and objects first. **[in the tool]**
5. **A failed script that still exits 0.** Blender's `--python` does that. The launcher passes `--python-exit-code 1`; do the
   same in any headless run you write. **[in the tool]**
6. **The GPU.** Cycles finds it only when the compute device type is set (on an AMD card: HIP); the tool tries
   HIP, OptiX, CUDA, oneAPI and Metal in turn and falls back to the CPU. `--cpu` forces that.
7. **A small trial size crashed the preview writer** (`slice step cannot be zero` at 512 px). Fixed; any size works.
   **[in the tool]**
8. **Curvature and wear masks depend on resolution.** They come from the normal map's divergence, so their gain and blur are
   scaled by `size / 4096`. A look tuned at 1024 px is close to, not identical with, the 4K result: approve the look at full
   size. **[in the tool]**, with that caveat
9. **Detail that stands proud of the game mesh is never baked.** A ray starts 0.02 cm outside the game surface and travels
   0.25 cm in. A select-fire carbine's handguard had its ribs (0.10 cm high) only in the bake source: no ray found them, 3.64 % of the
   sheet had no detail, and those texels have no surface kind either, so they took the base look: the polymer handguard
   came out with bands of black steel. Its vents, drilled 0.6 cm deep, had the same fault the other way. **Fix [yours]:**
   a raised shape goes into the game mesh too (the ribs: 3,000 triangles), a hole in the bake source is blind and at most
   0.2 cm deep, and everything else is cut inward. **[in the tool]:** the bake writes `bake/bake.json` and
   `bake/preview_missed.png` (white where no ray found detail; compare it with `textures/work/uv_layout.png`), and the check
   `bake: rays find the detail` misses above 2 % (the pistol: 0.68 %; that carbine after the fix: 0.22 %). A weapon baked
   before the record existed has none, and the check does not run for it until it is baked again.
10. **The same fault from a rounding, with nothing standing proud by design.** A magnum pistol's back strap arches on a 30 cm
    radius over a few degrees. `K.round_poly` cuts an arc into `ceil(angle / 90 * seg90)` chords: one in the game mesh,
    two in the bake source. The bake source's middle point stood 0.05 cm outside the game mesh's one chord, the rays
    started 0.02 cm out, and a patch of the strap 2.5 cm high found nothing. The check passed (0.58 % missed, under the
    2 % limit) and the patch was plain to see, because the frame is bare steel and a texel with no surface kind takes the
    recipe's BASE look, which is blued: a blue-black rectangle on a stainless strap. A service pistol has the same arch and the
    same miss; its frame is the base look, so nothing shows. **Fix [yours]:** give a long flat arc its number of chords,
    the same in both meshes: a fourth value on the corner, `(x, z, 30.0, 5)` (`ARCH_STEPS` in
    that magnum pistol's builders). Misses went from 0.58 % to 0.11 %. **How to tell:** `bake/preview_missed.png` shows a
    solid patch, not specks; in the textured sheets a part that is not the base kind has a patch of the base look on a
    smooth stretch. The 2 % limit is a limit on the sum: a single patch far under it is still a fault, and no check looks
    for one.
11. **A detailed part that is inside out bakes black, and nothing else shows it.** A service pistol's detailed slide (an
    open-topped channel) came out of `K.cleanup` with every face looking inward: Blender's `recalc_face_normals` guesses
    which way is "outward", and for that solid it guessed wrong for the whole piece (signed volume +70.28 before the
    call, -70.28 after). The grey sheets light both sides of a face alike, every size test took the volume without its
    sign, and the game mesh was the right way round. The bake then wrote normals that point INTO the game mesh (the
    normal map's blue at 0 where it should be near 255) and an occlusion of nearly nothing, and the slide was black under
    any light. It was taken for a black finish for a day: reported as "a plain gloss black" slide and written
    into the brief as "a nickel frame under the black slide". **Fix [in the tool]:** every place the kit and the
    game-mesh repair ask Blender for outward faces goes through `K.face_out`, which measures the signed volume of each
    closed piece after Blender's guess and turns the piece when it is negative (a `[kit] face_out:` line says when it
    had to); `K.boolean` tests its own result the same way. Two checks: `mesh: no part is inside out` (every closed
    piece of every game and detail part) and `bake: detail faces outward` (the share of baked texels whose normal
    points into the game mesh, limit 5 %: that pistol had 18.9 %, the seventeen others 0 to 2.4 %, which is faces hidden
    against another part, a butt under its pad or a tube's end in its socket). **How to tell without the checks:** a
    part that stays black in `hero` whatever the light, and whose island in `T_<Name>_N` is not the pale blue of a
    normal map. An open piece (a sheet with free edges) has no volume to measure and keeps Blender's guess. **[yours]:**
    a part that is black and should not be: suspect the bake before the finish.
12. **Wider edge breaks from the bake did not buy the soft, lit edges of a presentation render.** The bake rounds every
    edge by a few tenths of a millimetre (`bake.KINDS`: 0.030 cm steel, 0.035 polymer), which is under two texels on
    a long gun. Tried on a copy of a submachine gun: 0.055 cm for steel and 0.085 for polymer (`edge_break` in
    `weapon.py`, a setting added for the trial and kept). Side by side in `hero` the two are hard to tell apart; the
    wider one softens the engraved lettering and the fine ribs a little, because the Bevel node rounds concave edges
    too. Not adopted; every weapon keeps the defaults. What makes an edge catch the light in the picture is the pale
    line the texture puts on it (steel's worn edge, polymer's `edge`: Textures and look, item 17), and what makes a
    big edge soft is a real bevel in the mesh (`K.bevel`, `K.fillet_cutter`).
13. **The bake source may stand only 0.02 cm proud of the game mesh's chords.** A grip built at 16 points a slice left the bake
    source up to 0.06 cm proud of the game mesh's chords, and 2.2 % of the sheet found no detail (the check's limit is 2 %).
    **Fix:** 32 points a slice. **[yours]:** a coarse round part misses the bake; the check `bake: rays find the detail` says so.

## 7. Textures and look

1. **How the look is built [in the tool]:** the material reads the ID bake (three channels, one bit each, so seven kinds),
   world-space noise from the object position (so wear does not follow UV seams), and the curvature and wear masks. The game
   textures are emission "taps" of that material baked onto the joined game mesh: colour, roughness and metallic at 4 samples,
   occlusion at 1, normal at 16.
2. **What is on disk [in the tool]:** `_BC` is sRGB-encoded (the linear bake is encoded before the 8-bit save, otherwise the
   weapon comes out dark); `_N` is OpenGL (green up); `_ORM` is R occlusion, G roughness, B metallic, linear. The Unreal
   import sets `_N` to a normal map with the green channel flipped and `_ORM` to masks without sRGB, and the material instance's parameters are `BaseColor`, `Normal`, `ARM`.
3. **Review lighting.** A flat backdrop mixed into the world made EEVEE renders almost black. **Fix [in the tool]:** render on
   a transparent film and put the backdrop behind in numpy; turn the studio light with the camera; key light from `-50`
   degrees (the other side lit the weapon from behind). Final review sheets are Cycles, 64 to 96 samples, denoised.
4. **A head-on view painted every flat face white** (the template's wood, then the whole side of the rifle's stock and its
   trigger guard): a flat face seen straight on mirrors whatever is behind the camera, and with the key at -50 degrees that
   was one of the studio's strip lights. It is the light's reflection, not the texture. **Fix [in the tool]:** views straight
   down an axis (`left`, `right`, `top`, ...) turn the studio to -95 instead (`S.beauty(flat_key=)`); the angled views keep
   -50. If a sheet still looks chalky, look at `T_<Name>_BC.png` itself before retuning a recipe.
5. **Wear on fine relief.** The wear mask hit every peak of the grip checkering and made it pale and flat. The wood recipe
   narrows and softens wear and grime. If a new knurled or checkered surface looks chalky, that is why. **[in the tool]** for
   wood, **[yours]** for a new recipe.
6. **Real wood from texforge.** texforge (the companion tool) turns a painted picture into a tiling PBR set, but
   its defaults ruin oiled wood (shadow lift flattens the contrast, roughness comes out 0.84 to 1.0, normal strength 3).
   What worked:
   `bin/texforge make <source.png> --name walnut --type organic --size 2048 --world-cm 14 --no-materials --no-shadow-lift --normal-strength 1.0`
   and then **only its BaseColor and Height** go into `S.wood(plank=..., relief=...)`; roughness comes from the recipe. Its
   normal maps are DirectX-style; do not mix them with this pipeline's. Put the result under the weapon's `textures/` and
   name it in the `images()` hook (the first pistol's `weapon.py` did; it is not included). **[yours]**
7. **`polymer` and plank-less `wood` are a first draft.** They exist so the template runs; they have never been tuned for how they
   look. Treat them as a first draft. **[yours]** At its defaults `polymer` on a rubber recoil pad reads as grey plastic:
   the rifle uses `S.polymer(s, colour=(0.010, 0.010, 0.011), worn=(0.028, 0.028, 0.030), matt=(0.82, 0.66))`.
8. **Changing only the look does not need a re-bake**: `texture rig render`. Changing geometry or hard edges needs
   everything from `uv` on.
9. **Wood that goes right round the weapon (a stock).** `S.wood` was written for two flat grip panels, and on a stock three
   things were wrong at once. The grain ran up the stock, not along it: `grain_deg` 0 is +Z (a grip), 90 is along the bore;
   the rifle uses 86 so it falls toward the butt through the wrist. Each side took its own piece of the plank, which leaves a
   line down the comb and the belly where the two meet: pass `side_shift=None`. And the picture is projected through the
   side, so the top and the underside got one layer smeared across their width, and a 14 cm tile showed its figure six times
   along 80 cm. **Fix [in the tool]:** `bow` (the layers curve away from the centre plane, so the top and underside show arcs
   of grain), `stretch` (one tile covers `tile_cm * stretch` along the grain) and `waver` (the layers wander, so one repeat
   does not line up with the next). The rifle: `side_shift=None, stretch=2.5, bow=0.25, waver=0.8`. The defaults are the
   pistol's panels, unchanged. **[yours]** to choose.
10. **More looks than there are surface kinds.** The ID bake holds seven kinds (three channels, one bit each) and the rifle
    uses all seven; the scoped rifle needed two more, glass and anodised aluminium. **Fix [yours]:** pick a surface out by
    where it is. `s.pos` is the position in the weapon frame, so in `surface()` a mask can be built from it with the graph's
    own maths: the scope's lenses are "within 0.3 cm of the lens's plane and inside its edge's radius", its tube is "a
    `dark` surface above the receiver and behind the objective's rim". Lay such a layer over the base's with `S.stack`
    (a scoped rifle's `weapon.py`, not included). It costs nothing in the bake and cannot bleed, but it only works for parts that do not
    move away from where the mask is: for a moving part, re-tag it or widen the kind table (`Weapon.kinds`).
    An opaque material cannot be glass: a coated lens is a dark mirror here (metallic 1, roughness 0.05, a violet middle
    going green toward the edge). What the player sees through it is game code.
11. **Black polymer comes out mid grey.** At its default colours `S.polymer` beside blackened steel reads as grey plastic
    (a select-fire carbine's first sheets). For black furniture and frames: `S.polymer(s, colour=(0.010, 0.010, 0.011),
    worn=(0.024, 0.024, 0.026), matt=(0.60, 0.44))` (that carbine, a polymer pistol). A part of two kinds, like a steel magazine on a
    polymer floor plate, is split in `hp_kinds` by where its faces are (that pistol's `weapon.py`).

12. **Every gun wore the same steel and the same wood.** Seen together, fourteen weapons built in one night had the
    same wood texture on all of them and the same metal texture on all of them: each `surface()` called
    `S.worn_steel` and `S.wood` at their defaults, which are the first pistol's blued steel and the one painted walnut plank.
    **Fix [in the tool]:** both recipes take more arguments (their defaults unchanged, which a regression test against the first pistol
    proved; that test is not included), and `surface.STEEL` / `surface.WOOD` hold named sets of them: `blued`, `polished_blue`, `parkerized`,
    `grey_phosphate`, `phosphate_black`, `nitride`, `anodized`, `painted`, `patina`, `nickel`, `stainless`; `walnut`,
    `dark_walnut`, `beech`, `amber_birch`, `red_laminate`, `rosewood`, `honey`, `weathered`. A weapon states its two
    choices as class attributes, `finish` and `timber`, and its `surface()` passes them on:
    `S.steel(s, self.finish, bright=..., dark=...)`, `S.timber(s, self.timber, plank=..., relief=..., grain_deg=...)`.
    A variant changes the look by setting the two attributes (a sawn-off double-barrel: `patina`, `weathered`). `case=` on the steel
    puts case-hardening colours on the bare parts (a side-by-side shotgun's action). **[yours]:** pick a finish and a wood that the
    set does not already have twice, and look at the new weapon BESIDE the others before sending it
    (`weapons_overview.png`, or two sheets side by side): each one looked right alone. What the names cannot do: the
    woods all draw the same plank's figure, recoloured, re-finished and taken from a different place; a species with its
    own figure needs its own painted plank (item 6, and "Tools" item 10: ask before using the image tool). The new
    finishes and woods were judged in the review light only.
    A fast look without baking the game textures: build the authoring material on the game parts and render two views
    (`S.load_maps`, `S.build`, `S.assign`, `S.beauty`; 20 s a weapon), then run `texture rig check render` once it is right.

13. **Bright steel shows what dark steel hides.** A magnum pistol in stainless looked like painted plastic with smoke on it,
    beside photographs of the real thing in the same finish. Three things in `S.worn_steel`, all of them fine on a blued gun: its broad light-and-dark variation
    (`n_large`, in colour and roughness) reads as CLOUD on a pale metal; its soft grime round every recess (curvature
    plus occlusion) reads as soot; and engraving has nothing dark in it, so markings vanish. And nothing said "metal":
    a real satin finish is brushed one way, and the eye reads the direction. **Fix [in the tool]:** four more arguments,
    defaults unchanged: `cloud` (how much of the broad variation is kept), `brush` (fine streaks along +X in the
    roughness and the colour, a hair of relief, and the fine pitting gives way to them; it fades out on faces that look
    along the weapon, where streaks seen end on are only grain: the first try had the muzzle block and the trigger
    guard's front looking sand-blasted), `fill` (sharp cuts filled dark, from the cavity map: engraving reads) and `dirt`
    (how much of the soft grime is kept). `STEEL['stainless']` uses them: `cloud=0.3, brush=1.0, fill=0.9, dirt=0.3`, a
    brighter and evener base colour, `thin` off. **[yours]:** any PALE finish wants `cloud`, `fill` and `dirt` (a
    nickel, a bare aluminium, a worn-to-white phosphate; `STEEL['nickel']` has them now), and `brush` if it is a
    brushed one. `fill` is for pale metal ONLY: the ink is black, so on a blued or black finish it makes a marking
    vanish, where the bare edges of the cut were what let it be read; `worn_steel` keeps it off the parts in the
    `dark` mask for that reason. Streak strength was judged in the presentation picture (item 14), not on the dark
    review sheet, where it looks twice as strong.

14. **A review sheet is not a presentation.** The sheets (`final_views` and the rest) are lit flat and even on a dark
    ground so that every side can be judged; they make a good weapon look plain, and they were the only pictures of
    ours that had been set beside a showcase render of somebody else's. **Fix [in the tool]:**
    `weaponforge <id> hero` (`hero.py`): the EXPORTED game mesh with its game textures (nothing the game does not get),
    a soft key light above the side of the weapon the camera is on and a rim strip behind the weapon's far end on its
    FAR side (both placed by the weapon's own sides and re-placed for each picture, not by the camera's left and right), an
    outdoor image for the metal to mirror (bright and dark in it; turned almost grey, or a blue sky tints black steel
    blue), a plain grey backdrop that the camera sees instead of that image, a floor that only catches the shadow, an
    80 mm lens, AgX with a contrast look. Two pictures (docs/stages.md says where they are written): from the front, and from behind
    and above. It reads the weapon's files and writes none of them, so it is safe on an approved weapon. Numbers that
    cost a try each: the mirrored image at strength 1.0 washed a black carbine out to grey-blue (0.45, saturation 0.25);
    a key light tuned on that black carbine burnt stainless steel white (4.6 W for a pistol-sized weapon, 1.5 lengths
    wide; the watts scale with the length squared), and no single wattage serves both: under the light that suits
    blued steel a stainless pistol measured 1.56 scene-linear, a stop and a half past white. So the exposure is
    METERED on the weapon, as a photographer's is: a small render with nothing behind it is read back as numbers, and
    if 85 % of the weapon's own pixels are not under 0.42 the picture is exposed down until they are (1.6 stops at
    most; never up, a black gun stays black; the backdrop is made brighter by as much, so it keeps its grey). The log
    line says what each picture metered and how far it was exposed. **Where the lights stand cost a day:** with the key
    "at the camera's left" it lit the far side of the weapon in one of the two pictures, and the rim strip, placed behind
    the weapon as the camera saw it, skimmed the side in view. A light that skims a rough surface lies over it as a
    milky veil: a bolt-action rifle's walnut came out grey as driftwood from the front (the weapon metered 0.445 with that rim,
    0.160 without it) and looked like a fault in the wood. The rim belongs behind the side the camera does NOT see,
    where it only draws the top edge. **[yours]:** make the hero pictures before you send a weapon and
    send them WITH the sheets; if the weapon is dull there it is dull in the engine too, and the fix is in the textures.

15. **A black that is both very dark and matt is a hole in the picture.** A pump-action shotgun's receiver (`phosphate_black` as it
    was: a METAL of base colour 0.015 to 0.031 at roughness 0.52 to 0.64) came out of the presentation render as a flat
    black cut-out with no form in it, while the revolver's polished blue (as dark, but roughness 0.13 to 0.21 and a
    blue that goes up to 0.046) read as deep, curved steel. A metal's base colour IS how much it mirrors: at 0.02 it
    mirrors 2 %, half of what black plastic does, and with a matt surface that 2 % is smeared over everything. On the
    dark review sheet both looked the same "black". **Fix [in the tool]:** `STEEL['phosphate_black']` is a coating now
    (`coat=1.0`: not a metal but where it is worn through, so it has its own dark grey and the sheen every surface
    has), a little lighter and a little less matt; the black parts of `STEEL['nickel']` are a polished blue (0.020 to
    0.066 at roughness 0.20 to 0.30). **[yours]:** a black part bigger than a control lever wants either gloss enough
    to mirror the lights (a blue, a nitride) or to be a coating; look at it in `hero`, not on the sheet. The first pistol's own
    defaults stay as they are (its black parts are small). **And make sure it is the finish at all:** a service pistol's slide
    was a black cut-out in the same render for another reason, a detailed part that was inside out (Bake, item 11).
    A finish table was retuned for it and nothing changed. Read `bake: detail faces outward` in the check list before
    you tune a colour.

16. **Engraved lettering is invisible on a dark gun, and that is one of the things a showcase render has that ours had
    not.** The cut is 0.02 cm deep; on blued or anodised steel it shows only where a highlight crosses it. Real rifles
    carry their selector marks and often their model line filled with white or red paint. The cavity mask cannot do it:
    it is every recess, so paint by cavity fills the grooves, the pins and the screw slots too. **Fix [in the tool]:**
    the lettering has its own mask. `K.text_solid` marks its cutter as lettering; `K.boolean` and `K.join` keep a copy of
    every such cutter in the collection `<TAG>_MARKS` while the bake source is being built (`kit.keep_mark`,
    `stages.model`); the bake has one more pass in which the copies glow and the detail is black (`bake/marks.npy`, one
    channel per ink; `bake/preview_marks.png`); `surface.paint` lays paint where the mask is, and `Weapon.paint` asks
    for it: `paint = ('white',)`, or `('white', 'red')` with `ink=1` on the red text. Two things that cost a thought:
    the copy is squashed to HALF its depth, because the cutter's far face is the engraving's own floor and a copy lying
    in that floor is found by the rays only now and then; and the detail must be in the pass, black, or a thin part's
    letters show through on its other side. **[yours]:** it needs texels. A select-fire carbine at 45 px/cm carried 0.26 cm
    letters at 12 px; at half the texture size they were dots. Under 30 px/cm give the part that carries the text more
    of the sheet (`density` in `weapon.py`) or make the letters bigger. Place the text with `text_solid`'s own
    arguments or `K.transform`: a text moved some other way leaves its mask where it was. Paint is for the weapons
    that would have it; a pistol's slide legend is mostly bare.
17. **Polymer came out as one flat grey with nothing on it.** A stock, a bullpup's shell, a handguard: under the
    presentation light each was a single tone from end to end, and the panel lines, ribs and steps moulded into it
    (they are in the normal map) could hardly be seen. A reference render from elsewhere had the opposite: soft
    clouds over every polymer face, specks of dust, and a pale catch-light along every edge. Two causes. (a) Black
    polymer has almost no colour of its own (base colour about 0.01): what the eye gets is the light it mirrors dully,
    so the recipe's tone variation, which was in the base colour, was invisible. Variation has to be in the
    **roughness**, plus a thin pale film of dust, which is the one thing that lifts the colour. (b) Nothing marked
    the edges. Steel had its bright worn edge; polymer had only a broad "handled" zone. **Fix [in the tool]:**
    `S.polymer` gained `mottle` (roughness clouds a few cm across, a dust film over the drier half, dust specks),
    `edge` (a paler, shinier line where the convex mask is: a moulding polishes there) and `grain` (a pebble grain in
    the normal map, about 1 mm, which only a close view shows); all default to 1.0 and the numbers behind them are
    `POLY_CLOUD`, `POLY_EDGE`, `POLY_GRAIN` in `surface.py`. **[yours]:** the edge line draws whatever the bake's
    convex mask holds, so a polymer part with no modelled detail still shows nothing: it makes detail visible, it
    does not make any. The roughness clouds show mostly where a light's reflection falls, as streaks across it; if
    they read as smears, lower `mottle`. Coloured polymer (olive, bakelite) goes a little greyer under the film.
18. **Wear drawn from curvature alone reads as a mask, not as use.** AssaultG3 after its forms were reworked: a pale
    line of the same strength round every convex edge, grooves paler than the faces beside them, one roughness from
    nose to butt. It looked like toy plastic with its edges outlined. Three causes, all in the recipes. (a) The edge
    line and the rubbed band were driven by the convex mask only, so a sheltered edge under the rail wore as much as
    the butt's toe. (b) Polymer's dust colour (0.085, 0.075, 0.062) is paler than olive, so every recess came out
    lighter than the face: the relief read inside out. (c) The broad edge zone (`s.zone`) fills a narrow groove from
    both of its lips, so anything driven by it polished the floors of flutes and vents as if they were edges.
    **Fix [in the tool], all of it opt-in (a weapon that asks for none gets the textures it had; proved
    on AssaultG3 with its old `surface()`: mean difference 0.000 in all three textures):** `weapon.Zone` (a soft box
    in the weapon frame, with a tilt) and `Weapon.handled`, `.smooth`, `.textured` (lists of them, read as `s.handled`,
    `s.smooth`, `s.textured`); and on `S.worn_steel` / `S.steel` and `S.polymer` the arguments `handled` (where hands,
    cheek, magazine changes and the ground touch: polymer is polished darker and glossier with its grain flattened,
    steel wears through on its edges), `exposure` (the edge line only where an edge stands out in the open, broken
    into rubbed stretches and chips), `recess` (grooves, pockets and the rings round bosses go darker and rougher, and
    polymer's pale dust gives way) and `vary` (roughness drift, greasy smudges, fine scratches along the weapon);
    polymer also takes `smooth`, `textured` (a stipple) and `fade` (faces that look up a hair paler). AssaultG3's
    `weapon.py` is the worked example: thirteen handled zones, each with a note saying what touches the gun there.
    **[yours]:** (i) the zones are a reading of how the weapon is held and set down: write the note, and look at the
    result, because a zone that is too big reads as a stain. (ii) Fine checkering goes black under full recess grime
    (item 5 again); the crease term is capped for that, but look at the grip. (iii) Flutes and vents that are cut into
    the game mesh have their floors on separate UV islands behind hard edges, so the bake's cavity mask is empty
    there and the occlusion does the work; the derived `hollows` mask (a blur of the bake's concave channel, written
    to `textures/work/<tag>_hollows.png`) only helps on relief that exists in the detail mesh alone. (iv) The hero
    picture carries no baked occlusion (it reads ORM.R as glTF does, which Cycles ignores), and `recess` now puts
    its darkening into the base colour: if the game's material also applies the occlusion channel, recesses and
    checkering sit darker in the engine than in the picture. Nobody has looked at this in Unreal. (v) The stipple
    and the fine scratches are about 2 px wide on a 4096 sheet: expect them to go from the first mip down. (vi) An
    environment variable set in WSL does not reach the Windows Blender; and `masks.npy` has row 0 at v = 0, so flip
    it before comparing it with a PNG Blender wrote.
19. **Every surface had the same synthetic micro-surface, and nothing a texture artist adds by hand.** AssaultG3 was rated
    6.5/10 after item 18: the olive polymer, the rubber and the steel all carried the same few noises, and there was no moulded
    grain, no bead-blast, no grime run, no stencil, no label. **Fix [in the tool], all of it opt-in (a weapon
    that asks for none gets its old textures, node for node; proved on AssaultG3's old `surface()` and on the pistol):**
    (a) *Painted tiling sets* (`S.detail`, and `detail=`, `detail_tone=`, `detail_relief=`, `detail_rough=` on `S.polymer`
    and `S.worn_steel` / `S.steel`): a texforge set laid on by position through the three sides of the weapon frame,
    blended by |normal|^4, the blend variance-kept (divided by the root of the summed squared weights, so the grain does
    not fade where two sides overlap); `around=(y, z)` lays it round a line along +X instead (turned steel), with a whole
    number of tiles round each radius so there is no seam. Its BaseColor's luminance and its Height are measured on load
    and normalised to mean 0, one standard deviation: the recipe keeps its hue and value (`detail_tone` 0.15 = one
    standard deviation is 15 % lighter or darker), the height goes into the bump (`detail_relief` 1 = about polymer's
    procedural grain), `detail_rough` makes the high spots glossier. The detail goes in under the wear, dust and grime.
    (b) *Decals* (`Weapon.decals = [weapon.Decal(...)]`, `surface.decals`, laid on after the recipes, before the
    lettering's paint): a texforge decal through a box from one side (`'+Y'` ... `'-Z'`), only on faces that look that way,
    clipped to the box, fitted with its aspect (or `stretch=True`), reading unmirrored from that side; colour (its own, a
    given colour with the picture as mask, or none), `darken`, roughness (a value or dark..light from the picture),
    `metal`, `relief`/`thick`, `wear` (gone on exposed edges, handled zones and in specks).
    (c) Where they live: `surface.material_dirs` says (the weapon's `textures/` first, then the shared `_materials/` folders under the asset
    root and the setting `materials`; docs/examples-and-layout.md), so a set made once serves every weapon. Copy only
    `<name>_BaseColor.png`, `_Height.png`, `_Opacity.png` (decals) and `<name>.texforge.json`.
    What worked (texforge, always with `--out` outside the tool):
    `texforge --out <dir> gen "<material only, a neutral grey>" --name poly_mould --n 2 --parallel 1` (about 1 min a picture
    alone; 3 at once timed one out at 420 s), then
    `texforge --out <dir> make <src.png> --name poly_mould --type plaster --size 1024 --world-cm 6 --no-shadow-lift --no-materials --normal-strength 1.0`
    and `texforge --out <dir> check poly_mould` (exit 0 = seam metric passed). Ask for the source in a NEUTRAL GREY: the
    recipe supplies the colour, and the picture only says where it is lighter. Force `--type plaster` (min-cut seams; a
    grain has no joints). Decals: `texforge --out <dir> decal "<what>" --image <picture on a plain background> --name <n>
    --surface generic --size 1024 --world-cm <cm>` (it crops to the mark: the box fits the picture by its own aspect).
    **[yours]:** (i) *Texel density decides what reads.* At AssaultG3's 53 px/cm at 4096 a texel is 0.19 mm: a 0.3 mm grain
    is noise, at 2048 it is gone, and in the engine it goes at the first mip. Draw the grain at 0.5 to 1 mm (`world_cm` on
    `S.detail` overrides the set's: AssaultG3's polymer uses 9 cm) and make the source 2 to 3 times the bake's px/cm (512
    to 1024 px). What reads at arm's length is the mid-scale content: flow marks, blotches, roughness. Judge it at 4096,
    in `hero --shots fp`, never at 2048. (ii) *Lathe lines are 0.1 to 0.2 mm apart*: no texture this size shows them; the
    turned set reads as faint banding round the barrel at most. (iii) *AI decal pictures come crisp and thin* (a drip is one
    hair-line, a scrape a few sparse scratches): both vanished at 27 px/cm. A blurred halo under the crisp mark (a stain,
    an abraded patch) made them read; `stretch=True` widens a streak. (iv) *texforge un-premultiplies the colour against the
    background*: a dark leak on white comes back tan-orange at its fringe. Use such a picture as a mask
    (`colour=None, darken=..., rough=(wet, dry)`), not for its colour. (v) Ask for no lettering in a generated picture; make
    numbers and stencils yourself with a font (`Inkfree.ttf` for a hand-written marker, `arialbd.ttf` with bridges for a
    stencil) and put them through `texforge decal --image`. A dark mark on a pale label needs a coloured background (blue):
    alpha is the distance to the background. (vi) Restraint: three or four stories (a rack number, an armoury label, a
    zeroing mark, oil from the slot and the port, scrapes where it is grounded), each with a note in `weapon.py`.

20. **Start a weapon's look from the named finishes, not from another weapon's `surface()`.** AssaultG3's look took three
    passes and some 300 lines; copying it into the next gun copies its constants too. `weaponforge/finish.py` (docs/look.md,
    "Named finishes") has it by name: `moulded_polymer` for any moulded shell (pass the colour), `rubber` for pads and
    inserts, `anodised_alloy` for a cover, rail or alloy receiver, `phosphate_parts` for small steel and sights,
    `barrel_phosphate` for the barrel and its fouled muzzle device, `sheet_magazine` for a dark steel magazine,
    `bright_steel` for a bare bolt or a stainless part. Give each the places only the weapon knows (its grime boxes, where
    black metal is rubbed bright, a magazine's floor) as arguments, or let it read the weapon's zones, bones and sockets;
    override an argument rather than writing a new recipe, and look at `hero --shots fp,ads,beauty` before tuning.
21. **Flat stamped walls turn broad variation into smudged paint.** Large soft pale clouds on a receiver's side walls were
    three things: the recipe's broad drift (`cloud` 1), its pale patches a few cm across (`vary` 1) and two `handled` zones for
    the rods of a folded stock, which on a flat wall give blotches, not lines. **Fix:** `cloud=0.2`, `vary=0.3`, the rod
    zones 0.30 cm high at strength 0.5 (were 0.55 at 0.8). Measured over the phosphate where it is whole, the base colour's
    1 cm averages spread 0.172 of the mean before and 0.088 after. The hinge's `handled` zone also reached forward over the
    receiver's rear chamfer and made it pale and speckled 8 cm under the aiming eye; it now ends at the hinge block.
    **[yours]:** keep a zone on a flat wall narrow and weak, and keep zones off what the aiming eye looks down on.
22. **Serrations are the darkest thing in the aiming view.** On a ramp and a sight leaf the alloy finish's pale dust on every
    groove floor and bright line on every top corner made them read as silver bars. **Fix:** the black dye alone over the finished
    look inside two boxes, with a few ridge ends keeping a thin worn line. Tried and put back: a coat (metal 0, roughness 0.66)
    read as a pale grey slab (a dry black at a grazing angle is pale); all metal gave a black hole with no grooves. Kept: ridges
    0.6 metal on the ramp and 0.15 on the leaf that faces the eye, grooves all metal, black and dry.
23. **A coat with a roughness over 0.6 reads pale where the aiming eye looks along it.** The rear top of a receiver was pale
    and speckled; the base colour went from 0.082 to 0.036 and the picture from 0.163 to only 0.159: the brightness was the
    picture's light on a dry coat seen along its surface (7 to 12 cm under the eye), not the finish's colour. What did change
    was the speckle: a second row of the same finish over the rear top, fading out over 1.2 cm, took the painted set down to a
    third (`texture_tone` 0.12 to 0.04, `texture_relief` 0.8 to 0.28), and the spread in a 60 px window went from 0.097 of the
    mean to 0.039. **[yours]:** do not chase brightness with the base colour; change the speckle.
24. **Lettering is read in screen pixels, and a raised control can hide it.** `CAL 9 mm` at 0.60 cm and a serial at 0.48 were as
    tall as the wall took and still short of a letter's width along the gun: the hip eye sees a side wall at about 10 degrees,
    so a letter 1.6 times as wide read where a taller one did not (5.5 screen pixels of width before, in a picture 2400 across;
    about 8 are needed). `SAFE` and `FIRE` had to lie in the 0.9 cm band of the housing the hip eye sees. Not solved: with the
    lever at SAFE its thumb tab (0.44 cm proud) stands between the hip eye and `FIRE` (it hides the wall for 4.7 times its
    height ahead of itself and twice its height below); the person decided at approval 3 to leave it ("a word the lever covers
    at SAFE is how a real one behaves"). **[yours]:** put a mark outside a raised control's shadow, or accept that the control
    covers it, and say so.

## 8. Rig and export

1. **Unreal's Python cannot create a named socket** (the socket's name and bone are read-only). **Fix [in the tool]:** each
   socket is a leaf joint `SOCKET_<name>` (not deforming) under its bone. Unreal's default importer (Interchange) turns such
   a joint into a mesh socket on the parent bone. The legacy FBX factory would make it a bone, so the skeletal mesh must not
   go through the legacy factory.
2. **Bone axes.** Bones point along Blender's +Y with roll 0 and are exported with primary axis Y, secondary X, forward -Y,
   up Z: every rest axis in Unreal is then the weapon's own, and the game moves parts with plain weapon-frame vectors.
   Unit scale applied, no leaf bones, no baked animation, the armature object named exactly `Armature`. **[in the tool]**
   (`rig.export_fbx`; do not change one flag without re-running the Unreal check.)
3. **Rigid skinning.** Every vertex on one bone at weight 1. A part bound in a pose other than its rest (the pistol's
   hammer is bound cocked) must be said so in `motion`, because the game side will rotate it back. **[yours]**
4. **Skeletal LODs** are made in Blender (collapse to the share in `lods`, then the same cleanup) and exported as their own
   FBX files with deform bones only: a LOD file must carry exactly the base mesh's bones, without the socket joints. Unreal's
   Python cannot set a reduction on a skeletal mesh. **[in the tool]**
5. **Static LODs.** `StaticMeshEditorSubsystem` does not exist in a headless run, so LODs cannot be added after import.
   **Fix [in the tool]:** the world copy and its LODs hang under an Empty with the custom property `fbx_type = 'LodGroup'`,
   which exports as an FBX LOD group. The children are written sorted by name, and Unreal takes them in file order as LOD0,
   LOD1, LOD2: the names `SM_X`, `SM_X_LOD1`, `SM_X_LOD2` sort correctly. Do not rename them.
6. **Props** are written in their own frame (`Prop.matrix`), not the weapon's. Say in `use` where the origin is and which
   way is up, because the game attaches the prop by that. **[yours]**
7. **Blender's +Y is the weapon's left.** Everything in the spec is already in Unreal's frame (`y` negated). When a socket
   is on the right side of the weapon (the ejection port), its Blender `y` is negative. The pistol has a check for exactly
   that; add one for any sided socket. **[yours]**
8. **An online viewer shows the exported FBX grey.** A way to look at a weapon in 3D with its textures, in a browser
   viewer, was wanted. The game files are an FBX with no
   textures in it and three PNGs beside it; a viewer reads one file. **Fix [in the tool]:** `weaponforge <id> view` writes
   `<Name>.glb` (docs/stages.md says where): the exported static mesh with base colour, normal and
   occlusion/roughness/metallic inside (glTF packs them the way the game's `_ORM` does, and takes the normal map's green
   as the bake writes it). It reads `export/` and `textures/` and writes nothing in the weapon's folder, so it may be run
   on an approved weapon. A viewer that offers a share link uploads the file to its own server: that is the person's
   choice to make, not the agent's.
   **The copy carries the game's textures unchanged, and that is not negotiable.** Its first version shrank them to
   2048 px and saved them as JPEG (2 to 3 MB a weapon). A magnum pistol opened in a browser viewer and zoomed in
   looked low quality in some spots up close: blurry and granulated behind the decals. Cut out at the lettering, the bake and the game's `T_<Name>_N` and `_ORM` were sharp and clean; the copy's
   were soft, with a halo of JPEG blocks round each letter, and a normal or roughness map with that halo on polished
   steel is a patch of grain. Rendered with the same camera and light, the same mesh showed the fault with the copy's
   textures and not with the game's. `hero` had never shown it because it loads the game's PNGs. **Fix [in the
   tool]:** `view` embeds the PNG files as they are (glTF export with `export_image_format='AUTO'`, no scaling);
   `tests/check_viewer_copy.py <glb> <textures folder> <Name>` compares the three embedded images with the game's,
   pixel for pixel, and `tests/smoke.sh` runs it. **[yours]:** anything made for the person to judge quality by must
   be made from the files the game gets, at full quality; save bytes somewhere else. What a 4096 px set still cannot
   do: at 78 px/cm a groove that runs diagonally across the texels shows fine stair-steps from about 15 cm away.

## 9. Checks

1. **Checks measure the meshes**, with 0.2 cm tolerance on sizes and 0.02 cm on contact. They do not read `params.py`.
2. **A check can be wrong.** `MagWell` once failed by 1.78 cm; the socket was fine, the measurement sampled a band that
   missed the well's rear wall. When a check fails by a lot on something that looks right, read the measurement before you
   move the mesh. **[yours]**
3. **Before `uv` and `rig` have run**, the mesh, UV, pivot and rig checks are printed as `--` "not measured yet" and are
   not counted (the triangle count shown there is a rough one, before cleanup). The brief, travel and socket checks are
   meaningful from the first `model`. Once the rig exists, a stage that was skipped is a miss.
4. **The travel check has two conditions.** Moving a part must not put it deeper into its neighbours than it is at rest, and
   at rest it may touch them but not sit more than 0.05 cm inside. A constant overlap that is larger than that is a part
   modelled into another: fix the builder. Parts on a bone under a moving bone move with it. **The measurement looks at
   vertices** (how deep one part's vertices sit inside the other, both ways): two parts that cross edge through edge with no
   vertex inside either are not seen, so look at the pose renders too. **[yours]**
   **A travel that only happens from another position** (a revolver ejects with its cylinder swung out) is a `Move` whose
   matrix is that position times the travel: `lambda t: swing(90) @ Matrix.Translation((-t, 0, 0))`, with 0 among the
   steps. It names only the bones that travel (the ejector and the cartridges), so the cylinder itself stays where it is
   bound and is not in the way. On the revolver it found the grip panel 0.06 cm inside the path of the ejected cases
   after the panel's top had been redrawn; a pose render would not have shown that.
5. **The FBX read-back (`verify`) is the proof of export**: a second, empty Blender imports every file and compares it with
   the spec. A miss is a missing file, a scaled mesh, anything but one UV map and one material slot, lost custom normals, a
   different triangle count, bounds off by more than 0.01 cm (a LOD: 0.5 cm, the decimator moves vertices), a bone or socket
   joint that is missing, misplaced, on the wrong parent or turned, a socket joint in a LOD file, a vertex on more than one
   bone, static LODs out of order. It says nothing about what Unreal makes of the files: the Unreal check does.
6. **Stale or incomplete chain.** Each stage stamps the file. `export` refuses when a stage is older than what it is made
   from (parts rebuilt after the bake, say; rebuilding only the high-detail parts makes the bake onward stale, not the UVs),
   when a stage of the chain never ran, when a part has no UVs, and when the three textures are not on disk: `model rig
   export verify` used to give a "verified" weapon with no UVs and no textures. `--force` exists for emergencies; a forced
   export is not a deliverable. Files made before the stamps existed (the approved pistol's `.blend`) cannot tell which
   stages ran and are judged on the UVs and textures alone.
7. **The decimator can eat a very small part.** A LOD keeps each part on its bone, but at 25% a part of a few dozen
   triangles may collapse to almost nothing. Look at the LODs once (`SKM_<Name>_LOD2` in the `.blend`); if a part that
   matters disappears, raise the last share in `lods`. **[yours]**
8. **A definition with a typo stops at once.** `weapon.load` checks the bones (parents first, one root, no name twice), the
   sockets, props, moves and poses against them, the LOD shares and the budget, and lists everything wrong in one message.
   A part tagged for a bone that does not exist, or a high-detail part of an unknown surface kind, fails the `model` stage by
   name. **[in the tool]**
9. **Do not test a prop's origin by the middle of its bounds.** A magazine's own frame runs up its axis; when the grip is
   raked and the floor plate is level with the ground, the plate reaches far forward in that frame (a polymer pistol: 3.15 cm at
   18 degrees) and the bounds' middle is nowhere near the body's. Cut the body instead:
   `CHK.section_mid_x(prop, -4.0, half_width)` in the prop's frame (that pistol's `weapon.py`). The first pistol's test still
   uses the bounds and passes by 0.6 cm of slack, which is luck.
10. **Two checks were added later** (`mesh: no part is inside out`, `bake: detail faces outward`; Bake, item 11),
    so a weapon checked before they existed shows two more checks on its next `check`. For a bake made before them the
    second one is measured from the saved bake (`bake/normal.npy`, `bake/cover.npy`), not skipped.
11. **`note look: bare faces` is not a check and never a miss.** It names the flat faces with a plain stretch of over
    12 cm2 (Modelling, item 64), or says there are none. It is a matter of looks for the modeller and the person to
    weigh, it is not in the count "N of N checks pass" and not in the spec, and it never stops an export. It needs the
    bake's masks, so it is silent before the first bake.
12. **`note review: figures` is said for every weapon and held only for one that asks.** After a bake, `check` measures the
    review's figures from the player's eyes and the front picture (docs/review.md: sharpness in the hip and aiming views,
    surface kinds seen, hardware and marks per area, the largest bare stretch, faces with no kind) and prints them in three
    note lines; they are not in the count and never a miss. A weapon with `review = 'first_person'` holds six of them as
    checks (`review: fp_sharp_share` and so on), counted, in the spec and stopping `export --strict`; `review_limits` moves a
    limit for that weapon, with a reason in a comment. The limits were set on AssaultG3 between its builds; they are a floor
    for a first-person weapon, not a goal: a build can pass all six and still lose its pairs. A miss is reported word for
    word, like any other.

## 10. Unreal import

1. **Re-importing over an existing mesh ignores the new options.** Unreal sends it through the reimport handler with the
   options stored at first import (run 2 of the first pistol: `SM_<Name> has 1 LODs, wanted 3`). **Fix [in the tool]:** the
   `--reimport*` flags delete the asset first, then import fresh. **That is destructive**: the old mesh and its skeleton
   are gone before the new ones exist, and `EditorAssetLibrary.delete_asset` cuts every reference to them. So the import
   (a) looks at every source file first (missing, empty, not an FBX: nothing is deleted), (b) asks the asset registry who
   references the meshes from outside the weapon's folder and refuses when anyone does, unless `--replace-referenced` is
   given, and (c) fails the run on any warning. It still cannot put the old assets back: copy
   the weapon's asset folder before re-importing a weapon the game uses. Game code that refers to the meshes by path is not
   seen by the registry, and a fresh mesh at the same path satisfies it.
   Whether animation assets made on the old skeleton survive a re-import has **not** been tried.
2. **Two importers, on purpose.** The skeletal mesh goes through Interchange (it makes the sockets); the static meshes go
   through a task with `unreal.FbxFactory()` and `FbxImportUI.import_mesh_lods = True` (the only path that honours the LOD
   group). The property is `import_mesh_lods`; `import_mesh_lo_ds` is the deprecated spelling. Skeletal LODs are added with
   `import_lod`. **[in the tool]**
3. **Collision** is set through GeometryScript (`ScriptCollisionShapeType.BOX`) from the boxes in the spec; the subsystem
   normally used for it is missing in a headless run. **[in the tool]**
4. **The shared master material (the setting `unreal.master_material`; docs/unreal.md) must be usable on a skeletal mesh.** The game's had "Used with Skeletal Mesh" off;
   the editor sets it on demand, a `-game` run cannot, so the held pistol drew with the grey default grid. The import sets the
   flag when it is off and saves the master: **the one change outside the weapon's own folder** (a trial run never makes
   it; a real one warns, and so fails, when the flag cannot be set).
5. **Unreal's vertex counts differ from Blender's triangle counts** for a skeletal mesh (hard edges and UV seams split
   vertices): the check compares triangles where the engine gives them and reports render vertices otherwise.
6. **Reading the result.** The command prints the engine log's path (`build/logs/unreal-<import|check>-<time>.log`); the script's own lines start
   with `weapon_import: ` or `weapon_check: `. A check that ends without `RESULT all facts match the spec` has `MISS` lines
   above it saying what and by how much.
7. **Trial folder.** `--dest <unreal.content>/_Scratch/<Name>` imports a weapon somewhere harmless; `--remove` deletes
   it. Both take exactly one folder under `_Scratch` and refuse anything else (`_Scratch` itself, a deeper path, a dot: the
   engine cuts a path at the first dot, so `_Scratch/.` once meant all of `_Scratch`). A spec that does not live where the specs of real weapons do
   (a `--root` build, a test copy) can only be imported into a trial folder, and a `--root` build's
   spec already names one.
8. **Nothing that exists is touched without being asked.** Without a `--reimport*` flag the import only creates what is
   missing: an existing texture, material instance or mesh is not re-bound and not saved. (It used to re-point and save the
   material instance on every run.) **[in the tool]**
9. **Where the rules live.** `integrations/unreal/weapon_spec.py` has no Unreal in it: the command line, the folder
   rules and the look at the source files. `tests/test_unreal_args.py` runs every way a run could end up in the wrong folder
   against it, in a second, without the engine. Change a rule there, add its case to the test.

## 11. Putting the weapon into the game

This is not part of the tool. How a weapon is wired into a game depends on the game. What follows is what the first game it
was used in had to do, kept for what any Unreal project needs to know about the files the tool writes (the frame, the sockets,
the bone names, the normal map convention, the spec), so that the next weapon starts with the list.

1. **Point the weapon definition at the meshes.** `SM_<Name>` is the static world copy and `SKM_<Name>` the skeletal one. A
   mesh made here is already in the weapon frame, so a grip offset is the identity, and the `Muzzle` socket's position is in
   the spec (`dimensions_cm`). A fallback hold, for when no reload fit exists, is the game's to choose.
2. **Soft paths are not found by the cook.** If the game refers to the meshes by soft path, add the weapon's asset folder
   to the always-cook list (`+DirectoriesToAlwaysCook=(Path="/Game/<weapons folder>/<Name>")` in `Config/DefaultGame.ini`) and to
   whatever packaging list the project keeps, or a packaged build has no weapon.
3. **Names the game's code looks up on the skeletal mesh.** The bone and socket names are the weapon definition's own; the spec
   records them. The first game's pistol code looked up these, and did the following without them:

   | Name | Kind | Without it |
   |---|---|---|
   | `Slide_Bone`, `Clip_Bone` | bones | **required**: no animated pistol at all |
   | `Hammer_Bone` | bone | the hammer does not move |
   | `Grip_Bone` | bone | with the slide bone and `Muzzle`, lets the mesh be placed by its own frame |
   | `Muzzle` | socket | muzzle flash and light fall back to a guessed point |
   | `AmmoEject` | socket | cases leave from 12 cm behind the muzzle |
   | `SightFront`, `SightRear` | sockets | measured fixed sight points are used: the sights will not line up |

   These are the pistol's names, read by the pistol's code (docs/rig.md lists every bone and socket the tool and the shipped
   examples use, and what each is for). For another kind of weapon (a revolver's cylinder, a long gun's
   bolt), look for the code that will animate it before choosing bone names; if there is none yet, the names are yours to
   choose, the spec records them, and the game side has to be written against the spec.
4. **Constants that belong to the mesh may be hard-coded.** The slide's travel (3.4 cm for the first pistol: its hammer was
   bound for exactly that travel, and 3.0 leaves it 3 degrees short of cocked) and the hand's place on the magazine were both
   re-measured for the new mesh. Take them from the spec (`dimensions_cm`, `reload_targets`).
5. **The hold is fitted, not guessed.** Hand poses for a reload are fitted to a weapon's mesh from the spec and the FBX
   (`bounds_ue_cm`, `sockets`, `reload_targets.mag_axis`, `dimensions_cm`). The old by-eye hold put the fingers through the new
   grip. **Changing weapons means re-fitting the hands.**
6. **The magazine leaves along the `MagWell` socket's -Z**, which is raked with the grip, not straight down.
7. **Axes.** A weaponforge mesh has +X as its muzzle. An older pistol had +Y as its bore and +X as its left; tests and code
   that assumed those axes had to be adapted.
8. **Left open:** the dropped magazine disappears mid-fall in the empty reload (one magazine bone, nothing spawned;
   `SM_<Name>_Mag` exists for this and nothing uses it yet).
9. (removed: specific to the project this tool came from)

## 12. Noise you can ignore

- `CUEW initialization failed: Error opening the library` (Cycles looking for a CUDA it does not need).
- `WARNING Image file does not exist` / `ERROR Failed to load 1 image files`, once per texture tap: the bake target is an
  in-memory image.
- Unreal: `Possible LOD pattern missmatch. Expecting 'LODxx_Name'` on the static import.
- `weapons/__pycache__` and friends appear in the tool tree; git ignores them.

## 13. What nobody has verified

- The look of a weaponforge weapon **rendered by Unreal** has never been checked by the tool, only by a person watching a
  game run of one pistol. In particular nothing proves the normal map's green direction; it follows the convention in
  "Textures and look", item 2.
- No packaged build with a weaponforge weapon has been checked.
- The first pistol's `.blend` was made by the older scripts. Taken through `texture`, `rig`, `check`, `export` and `verify`
  here, it reproduces its approved spec exactly and its textures within bake noise (a regression test, not included). Built from
  nothing with this tool, the pistol comes out with the same bones, sockets, sizes and check results, 13,998 triangles
  instead of 14,000 and a slightly different UV pack; that rebuild was never reviewed for its look.
- **A mesh re-import of a weapon the game uses.** The fixed importer was tried in a trial folder only (first import,
  a run that changes nothing, `--reimport-meshes`, removal). Its refusal for a weapon that other assets reference has never
  fired on a real one: no asset referenced the first pistol's meshes or skeleton from outside its folder (the game finds
  them by path in code), so that guard would let a pistol re-import through. Whether animation assets made on the old
  skeleton survive one is untried, and a re-import that fails half way cannot be rolled back by the tool.
- A weapon without LODs (`lods = ()`) went through every Blender stage and `verify` once; it was never imported into Unreal.
- **Paint-filled lettering and the presentation render have only been seen in Blender.** `hero` uses the exported mesh and
  the three game textures with Blender's own shading; Unreal's tone curve, its reflections and the master material are not
  in it. Painted lettering is in the base colour, roughness and metallic textures, so the engine gets it, but nobody has
  looked at it there. Paint was tried on a long gun at 45 px/cm and up; under that the letters are a few texels high.
  Four weapons carried it (a select-fire carbine and its suppressed variant, AssaultG3, a submachine gun).
  On the submachine gun the red SEMI and AUTO, set 2.2 mm tall, read as smudges in the presentation picture while the white
  SAFE beside them reads: small red letters on mid-grey steel want to be set larger (2.6 mm read on the select-fire carbine)
  or white.
- **The reworked polymer and the bare-face note have only been judged in `hero`.** Eight weapons carried
  the new polymer (a select-fire carbine and its suppressed variant, a sheet-steel rifle, AssaultG3, a polymer pistol, a
  service pistol, a magnum pistol and a submachine gun);
  nobody has seen the clouding, the edge line or the grain in Unreal, where the grain in particular may shimmer at a
  distance or vanish in the mips. The note's two numbers (1 cm, 12 cm2) were set by looking at what it named on nine
  weapons, not by a judgement of what is enough detail; it found the bullpup's shell (111 and 107 cm2 bare a
  side), the pump shotgun's receiver (24 and 19) and the lever rifle's receiver (21), and **none of those was given
  detail**: only the submachine gun's stock was, as the worked example. A face that curves is never named, so a plain lofted
  polymer stock passes unseen.
- Four pistols (and a suppressed variant of the first), a bolt-action rifle (and a scoped variant), a pump-action shotgun,
  a break-action double-barrel shotgun (and a sawn-off variant), a lever-action carbine, two carbines (one also with a
  suppressor), a sheet-steel rifle, a bullpup rifle, a submachine gun and a revolver were built on the tool. A belt feed, a folding stock, a drum: expect to add to `kit.py`, the surface recipes and this file.
- **Every weapon except the first pistol, the bolt-action rifle and its scoped variant was built without being taken into
  Unreal.** (The magnum pistol was built twice more, in the pattern of a real
  magnum pistol, "Modelling" items 54 and 60 to 63; the last build is the test piece for the brushed finish and the
  presentation render, "Textures and look" items 13 to 15.) So even the headless read-back has
  not been run for them, and no game code drives `Pump_Bone`, `Lifter_Bone`, `Shell_Bone`, `Suppressor_Bone`, the
  revolver's `Crane_Bone`, `Cylinder_Bone`, `Ejector_Bone`, `Ammo1` to `Ammo6` and `CylinderLatch_Bone`, the select-fire carbine's
  `ChargingHandle_Bone` and `Stock_Bone`, the side-by-side shotgun's `Barrel_Bone`, `TopLever_Bone` and `Trigger2_Bone`, or the lever-action carbine's `Lever_Bone` and `Gate_Bone` (its lever and
  bolt are tested one at a time, item 45 of "Modelling": that the two move together without meeting, and what the bolt
  does to the hammer on the way, is the game's animation and unproved). AssaultG3 has the select-fire carbine's bone names, but its magazine, port and bolt are
  behind the grip, its `Safety_Bone` slides where the carbine's turns and its `MagRelease_Bone` is pushed forward: a
  reload written for the carbine would put the hands in the wrong places. The service pistol has the first pistol's bones, but its `Safety_Bone` is the
  slide's child and its `AmmoEject` is in the open top; whether the pistol's code copes with both is untried. The magnum pistol is the same again, and its barrel does not move: its front sight is on `Barrel_Bone`, so code that tilts that bone on firing would tilt the sight. The first pistol's definition gained three hooks for
  its variant (`barrel(muzzle_x, turn)`, `barrel_end_x`, `boxes`); its regression test passes with them, and the
  first pistol's own files were not rebuilt. The select-fire carbine's definition gained `boxes` for its suppressed variant in the
  same way; it was not rebuilt after it.
- **A variant made by re-running its base** (`weaponforge.variant.rerun`, "Modelling" item 46) exists once: a sawn-off
  double-barrel. It pins four numbers of one `params.py`. A base whose `params.py` assigns a number the variant needs in a loop, in a
  function or more than once cannot be pinned as it stands (the run stops and names it); nobody has yet had to rewrite a
  base for that. A variant of a variant (re-running a file that itself re-runs another) is untried.
- **The finishes and woods of "Textures and look", item 12.** Thirteen weapons were textured again
  with them and exported again; they were judged in the review light only, and the only comment on the look of the first set
  (that all its woods matched and all its metals matched) was about the set before them. The first pistol, its suppressed
  variant, a bolt-action rifle and its scoped variant were left as they are: blued steel and the walnut plank.
- **Faces the cleanup's weld would have pinched, on weapons that already exist** ("Modelling", item 51; found
  by rebuilding every weapon's model on a trial copy with the new `[kit] cleanup:` note). The note fired on
  the first pistol and its suppressed variant (the game mesh's `Frame`, one face; each grip panel's bake source, two), the bolt-action rifle
  and its scoped variant, the pump shotgun, a carbine, the revolver, the select-fire carbine and its suppressed variant, a polymer pistol, the sheet-steel rifle, the side-by-side shotgun
  and its sawn-off variant, the service pistol and AssaultG3, nearly always in the bake source of a checkered or textured part (a stock,
  a fore-end, a grip: 2 to 105 faces; the polymer pistol's moulded frame: 71), once in the game mesh (the first pistol's `Frame`) and once
  in the bake source of a carbine's receiver (one face). It did not fire on the lever-action carbine or the submachine gun. What each of those places looks like in the files as they are was NOT examined: a
  pinched face in checkering is a diamond's facet folded over, which nobody would see, and every engraved line was read
  on the sheets when they were first sent, but not letter by letter with this in mind. None of the files was rebuilt.
- **Roundings the bevel clamp took away on weapons that already exist** ("Modelling", item 38; found by
  rebuilding every weapon's model on a trial copy with the new `[kit] bevel:` note). None of these was fixed: the files
  are as they were, and a fix changes the silhouette, so it means a new bake.
  - The first pistol and its suppressed variant: the frame's back strap asked for 0.62 cm and got about 1 % of
    it, the front strap 0.55 cm and got none, the dust cover's lower edges 0.26 cm and got a fifth, the small edges round
    the tang 0.10 cm and got 5 %. The grip straps are square-edged in the mesh; only the bake's edge break softens them.
    `K.fillet_cutter` (item 39), made for the service pistol, is the way to give them their roundings.
  - The polymer pistol: the same four on its frame (0.60, 0.30, 0.12, 0.10 cm; 2 %, 0 %, 28 %, 26 %) and the trigger's 0.09 cm (32 %).
  - The revolver: edge breaks of 0.06 to 0.10 cm on the crane, hammer, trigger and rear sight came out at 11 to 29 %.
  - The select-fire carbine: the pistol grip's 0.45 cm came out at 26 %. The submachine gun: the magazine catch's 0.06 cm at 1 %.
  - In the bake source only: the recoil pad's rim (0.30 cm, 3 % left) on the bolt-action rifle and its scoped variant, the pump shotgun, the side-by-side shotgun and
    a carbine (`stocks.pad_and_cap`). The game mesh has that rounding and the bake source does not, so the normal map
    draws a harder rim than the mesh has. Turning the clamp off there is not enough: the bake source's loft has a ring
    close behind the butt's face, which is what the clamp is protecting.
- **The bolt-action rifle and its scoped variant were imported into Unreal and never run in a game.** Their read-backs match
  their specs; nobody has seen either rendered by the engine, and no game code points at them. A game with no bolt-action
  weapon has none of that code: `Bolt_Bone`, the `BoltHandle` and `ForeEnd` sockets and the
  spec's `bolt_lift_deg` / `bolt_travel` are what it would have to be written against. A game may also copy an
  `L_Hand` socket onto its long guns from another mesh; the rifle gives `ForeEnd` instead and whoever wires it decides which
  the support hand uses.
- **A scope's picture.** `SightFront` / `SightRear` on the scoped rifle are the ends of the scope's axis and `ScopeEye` is
  the eye's place, so a camera put there looks at the inside of an opaque eyepiece lens. The zoomed picture, the reticle and
  the black ring round it are game work that does not exist.
- **Why the exact solver gives up on some cuts is known for one case only** (item 28 of "Modelling": edges of no length).
  The kit redid these with the manifold solver and every result is closed and passes its checks, but the cause was not
  found: a carbine's `Receiver.001`; the select-fire carbine's `Upper`, `Lower.001`, `Handguard.001` and `SightFront`; the polymer pistol's
  `Barrel` (the chamber cut); the lever-action carbine's `Barrel.001` (the engraved text) and `ForeCap.001` (a screw's slot and seat).
  A second cause was found after these (item 48 of "Modelling": a cutter's corner lying exactly in one of the target's
  edges spoils the exact cuts that come after it), and a third after that (item 49: engraved text cut before the other
  cuts in the same face). Whether either explains any of the ones listed here was not tried.
