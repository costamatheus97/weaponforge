# Craft: read this before the first build

What earlier weapons taught, put where it is needed: before the step, not after the mistake. `PLAYBOOK.md` is the long record
(every wall, by stage); this file is the short one, and it is meant to be read whole before a weapon is started.

Two things it is not:

- **Not a parts list.** Every weapon is its own design, made from what the person said they want (section 1). Nothing here says
  what a weapon should look like, and no part or look is taken over from another weapon. The shared code holds technique (a clean
  loft, a pocket, an engraved mark, wear that follows use) and the few things that really are standard in the world (a screw, a
  pin, a rivet). A sight, a stock, a barrel group or a colour designed for one weapon stays in that weapon's folder. AssaultG3
  is the example: `weapons/assault_g3/sights.py` and `barrels.py` are its own designs (a rail-clamped aperture and post sight;
  a gas block, castellated nut and slotted flash hider) with their sizes as arguments. Copy them only if the brief asks for
  that design; otherwise design the part in the weapon's folder (`docs/kit.md`).
  `stocks.py` is method (a pad, a cap, checkering) and no shipped weapon uses it.
- **Not a set of gates.** The figures the tool prints (`check`, `review`) are there to be read with the pictures. The pictures
  and the person decide.

AssaultG3 is the worked example of the standard: its `BRIEF.md` says, pass by pass, what was changed, what was tried and turned
back, and why. Read it for the reasoning. Do not copy its parts.

## 1. Ask first, on every weapon

The order: read this file, ask the person these questions, run `weaponforge new <id> <Name> <TAG>`, write the brief, show the
concept, and build only after approval 1. Do not model anything until the person has answered these and seen a concept. Ask
them as questions with two to four concrete
options each (and your recommendation), not as an open form; "you decide" is an answer, and then the decision and its reason go
into the brief. Skip a question only when the request already answers it.

1. **Role.** Who carries it in the game and for what: issued military, police, a hunter's, a collector's, improvised?
2. **Feel.** Three words for it (blunt, elegant, cheap, over-built, worn out, clinical ...), and which era and part of the world
   it should feel made in. Any pictures the person has in mind are for feel only: the weapon is the game's own design, with no
   real maker's name, logo or markings.
3. **The one thing.** What should a player remember about its outline? If nothing comes to mind, propose two or three
   silhouettes and let the person choose.
4. **How it works.** The action and the feed, and what the player sees move: a slide, a bolt, a lever, a cylinder, a magazine.
5. **Materials and condition.** What it is made of, how it was finished, and its history: new from the crate, issued and
   maintained, neglected, repaired in the field?
6. **What goes on it.** Sights, and anything planned later (a scope, a suppressor, a light): they decide the rails and sockets.
7. **How it is seen.** First person at the hip and aiming, or mostly in other hands or on the ground? Right-handed? Which
   side are the controls on, and which marks must be readable at the hip?
8. **What it replaces.** What must stay the same as a weapon it replaces: bone names, socket names, sizes (the game's code
   looks them up)? Or nothing.
9. **Id, name and tag.** `<id>` (lower case; the weapon's folder and asset folder), `<Name>` (the asset stem: `SKM_<Name>`) and
   `<TAG>` (2 to 6 capitals; the collections in its `.blend`). `weaponforge new` refuses any that something already uses.
10. **Limits**, only if they differ from the project's: triangles, texture size.

**Two things this list left out, and two weapons were thrown away for it.**

- **Where is it found in the game's world?** A hunter's cabinet, a police station, a military camp, an old stockpile. A weapon
  nobody can place does not belong in the game, however well it is built: one carbine was withdrawn at its grey model because
  the person could not say where a player would find it.
- **Show the concept as a picture of a believable weapon, not only as outlines drawn by code.** Stay inside a real archetype,
  with real proportions and mechanical logic; uniqueness comes from details, materials, marks and wear, not from a silhouette
  bent away from every real weapon. One rifle was told to depart visibly from real rifles: it matched its code-drawn outline to
  96 %, passed every check, and was rejected on sight (a funnel for a flash hider, a cask for a fore-end, a box bigger than
  its magazine). What replaced that process: a rendered concept image (painted, or generated) that the person approves; the
  outline taken from it by measurement; and the model shown beside it, at the same scale, at every approval.

Then write the design into `weapons/<id>/BRIEF.md` (made by `new`; the template's headings) before the first builder:

- **Outline**: the datums and overall size in cm, and the feature from question 3.
- **Assemblies**: how the real object would be made. Which pieces are separate, what each is made of, how they are held
  together. This is where shut lines, fasteners and the material of every part come from; a weapon designed as one outline has
  none of them.
- **Hardware**: what holds it together and what the user operates, each on the part it belongs to.
- **Marks**: lettering, pictograms, a serial, in the game's own fiction.
- **Wear story**: where hands, a holster, a sling, the ground and the mechanism touch it, from question 5.
- **What the eye is near**: the parts within reach of the hip and aiming views. They get the triangles, the texels and the
  hand-made detail; the underside and the far side do not.

Show the concept: the brief, two or three to-scale side outlines that differ in kind (filled silhouettes in flat material
colours, saved in `<asset root>/<id>/ref/`), your recommendation, and what each differs in (`docs/concept.md`). **Approval 1**
is the person's.

## 2. Form

- **A slab with rounded edges reads as a CAD blockout**, however much detail the normal map carries. Give a body a section
  made of facets and creases (a land, a shoulder, a draft angle, a belt line), and make every change of width a ramp with crisp
  ends. Use the section loft (`sections.py`, `forms.py`), not one outline extruded and bevelled. When a lofted body tapers, every
  facet's width must taper with it, or its faces twist and the first boolean fails on a volume.
- **A silhouette is judged as a silhouette.** An outline can have the drawing's numbers and still not read as the drawing. Before
  the model is shown, lay its filled side outline over the concept's at the same scale. On one SMG the wedge had the drawn sweep
  (0.7 cm) and read as two rectangles; it needed the nose at about half the tail's height.
- **Keep measuring against the approved outline.** Measure the model's flat silhouette (`hero --shots outline`, or the review
  pack's) against the approved fill after every model pass, not a shaded sheet: one rifle held 96 % of its approved fill
  through two model passes and a new grip.
- **A grip, a stock and a fore-end are made by how their lines leave the straight line.** A grip of three straight tables on
  a rake read as a board in every side picture, through two approvals. The fix was only numbers: a hollow under the tang,
  0.25 cm of palm swell, a waist, a heel, 0.2 cm of finger relief, a toe, a section nearer an ellipse. Draw those in the first
  model pass, and ask of the grey side view "is any long edge of something a hand holds straight?".
- **A control is designed for the direction the hip eye sees it from.** What the support hand grabs is seen end-on from the hip:
  on one SMG a turned knob end-on read as a screw, and a tab with a hook, a hole and a visible stop read as a handle.
- **Build it the way it would be made.** A separate piece is a separate surface kind with a shut line all round, cut into the
  section so the game mesh has it too, and it stands a little proud or sunk (about 0.1 cm). One moulding in one colour was the
  main reason a build was rated 6.5.
- **Detail belongs to a part and is designed with it.** A screw sits in a counterbore, a pin has a head and a clip, a groove ends
  on a line the part gives it. Stripes laid over a wall that already had a recess and a screw came out with ragged ends and
  crowded both; they were taken off again. If a feature has to dodge something, redesign the surface, do not lay it over.
- **Fine repeated detail goes into the detail model only**: ribs, serrations, knurling, threads, checkering. As game geometry a
  ribbed pad made 130 UV islands and cost 15 points of sheet coverage.
- **Round things near the eye need sides for their size on screen.** An aperture or a knob a hand's width from the camera shows
  its flats at 24 sides; 34 to 40 was needed. Far from the eye, fewer is right. Count with `LP_Q` in mind (`parts.seg`). With
  triangles spare, spend them here first (the aperture and its countersink, the hood ring, the charging handle, the muzzle
  device, the bends of a wire stock): one SMG spent 2,560 that way and none on the magazine or the underside.
- **Ribs and fine cuts on a rounded face end inside its flat.** Ribs that run onto the round end at different places and
  bake as dashes. And test lettering against the other cuts in grey before the bake: one property line ran into a flute and
  was found only in the textured picture.
- **More chords on a corner that hardly turns makes slivers.** A corner turning 24 degrees with as many chords as one turning
  90 made triangles under the engine's smallest area, found only after `uv`. Give chords by the turn, and read the
  smallest-triangle note straight after `model`.
- **A hole's rim is a clean circle with a flat land round it.** Grooves that each stop round the hole leave a stair of ends that
  reads as noise; stop them all on one straight line short of the rim.
- **Do not add a fillet that stands off the surface it should blend into.** Two tries at a blended root left a plate and then a
  hump, both worse than the plain corner. Shape the two surfaces so they meet, or leave the corner.
- **Subtle machining reads better than busy machining.** A pocket 0.14 deep bakes as a soft dark shape; five flutes on the same
  wall read as clutter. Sink a panel into a flat side: on a curved one its floor is capped in strips and shades in streaks.
- **Look at what the action shows.** Pose every moving part at its limits and look into what it uncovers (a port with the bolt
  back, a magazine well with the magazine out). A plain tunnel behind a detailed bolt is seen every reload.
- **Edges need a real break to catch light.** The defaults are small; a moulded part wanted about 0.10 cm and steel about 0.045
  (`edge_break`). Too large and it is a soap bar (PLAYBOOK "Modelling" item 65).
- **A raised line lower than about 0.02 cm does not bake.** Cut it instead (0.03 deep).
- Things that cost a rebuild each time: a part that overlaps another solid by a hair must be joined after the cuts; a cutter
  that ends inside material leaves a closed cavity, which the check reports as a part inside out; a cutter face in the plane of
  a target face, or a ring cutter with the target's own segment count, sends the cut to the second solver.

## 3. Texels

- **Spend the sheet where the eye is.** Use the tight pack and the view-driven weights (`uv_pack = 'tight'`, `texel_view = True`,
  `texel_hidden`; `docs/texels.md`, "Texels by view"). The parts in the hip and aiming views want about 80 texture px/cm or more at 4096;
  an even 48 px/cm everywhere looked soft exactly where the player looks.
- **Keep about 14 px between islands at 4096** (`uv_margin` 0.0017). Less bleeds at the second mip.
- **A smooth skin that runs from one wall over the top to the other is seamed where flat meets curved.** Unwrapped as one
  piece it stretches, the stage recuts it by angle, and one island can end folded over itself: wedges of another face's
  texture on a wall, with every check passing (`uv: no overlaps` has 0.4 % of slack; one fold was 0.445 % of the sheet). Put a
  seam where a flat wall or top meets anything else, so every piece is flat or a folded strip. A seam rule sees the part's
  own frame, which moves once `rig` has run: take the part's origin off before testing coordinates.
- **Read the bake's "rays that found no detail, by part" line after every bake.** Where the game mesh stands more than the
  ray (0.25 cm) off the detail model, the texels get no surface kind and take the look's first row: on one shotgun a dark
  triangle of steel in the toe of a wooden grip. `bake/preview_missed.png` shows where.
- **Settle the density before tuning the look.** The wear masks are worked out per texel; a look tuned first had to be tuned
  again after the pack changed.
- **Every game-mesh change costs the UV pack again** (about 4 minutes with the tight pack): collect model changes and make
  them together. The bake source may stand 0.02 cm proud of the game mesh's chords, no more: a coarse round part misses the
  bake (one SMG's grip at 16 points a slice missed 2.2 % of the sheet; at 32 it did not).

## 4. Look

- **Choose every material; do not take a default.** Fourteen weapons on the default steel and wood looked alike: the wood on
  every one was the same, and so was the metal. The colour, the age and the amount of wear come from the brief.
- **A named finish is how a material behaves, not how this weapon looks.** `weaponforge/finish.py` has moulded polymer,
  anodised alloy, phosphate and sheet steel, rubber: each lays on its painted set, its wear and its grime in one row of
  `surface()`. Their default numbers are one olive rifle's, tuned at its texel density. Set the colour, the grain, the amount
  of polish and wear from the brief, and look: on a black gun at half the density the default polymer grain read as rough
  casting and the phosphate as busy. There is no named finish for painted sheet steel or for wood (the steel finish `painted`
  and the timbers are recipes in `surface.py`; `docs/look.md` says which is which): make what the weapon needs.
- **Materials must read apart by sheen, not only by colour**: anodised alloy, phosphate steel, polymer and rubber each have
  their own roughness, and a dark part beside a dark part still needs to be told from it.
- **Wear follows use, not curvature.** A pale line round every convex edge reads as a toy. Say where the weapon is touched
  (`handled`, each zone with a note of what touches it) and let edges wear only where they stand out or are handled; grime
  gathers in recesses, round controls, pins and shut lines; elsewhere the surface stays even. A `handled` zone on a flat wall
  gives blotches a few cm across, not a rub line: keep such a zone narrow and weak (0.3 cm, strength 0.5), and keep zones off
  what the aiming eye looks down on.
- **Handled polymer goes darker and polished, in patches.** Paler reads as bleached or chalky.
- **Scuffs stay in the material's own colour.** A tint or a film meant as heat or soot read as rust and as a pale veil; both
  were dropped.
- **Watch what a shared recipe does to a flat part.** A handling term polished a whole magazine side pale; only its floor is
  handled now. The darkest metal on a weapon should stay dark. On a flat stamped wall the recipes' broad variation (`cloud`,
  `vary` at 1) reads as smudged paint: one SMG's phosphate is at `cloud=0.2, vary=0.3`, the grain from the painted set and the
  wear from `handled`. `vary_broad` turns the mottling down on its own and keeps the fine variation ([docs/look.md](docs/look.md)).
- **A thinned dark finish is led by its edges and has no border.** A zone plus noise, thresholded, is a grey patch with an
  edge: on blued steel it read as smoke when round and as camouflage paint when big (two builds lost). What read as worn blue:
  the finish gone on and beside the edges, part-thinned on the flats in fine streaks along the weapon, each zone fading out
  over centimetres, grooves keeping their blue, about a fifth of the steel visibly greyer. Unevenness of oil goes in the
  sheen, not in the tone. Without it, a dark finish reads as black paint from half a metre.
- **A zone on a flat face shows as its box**, and noise on the fade of a strip a millimetre or two wide is a row of scallops
  that looks like texel steps. Fade a zone far or leave it out; drive a crease's wear from the distance to the crease.
- **Wood is made at picture distance, not close up.** A plank that read as beech close up read as varnished laminate from two
  metres until each piece had its own tone, streaks 5 to 15 cm long along its own grain, a darker and less orange base, an
  uneven satin sheen, and dirt where wood meets steel.
- **What the aiming eye looks along stays matt and quiet.** A top surface seen at a few degrees mirrors the backdrop into the
  sight picture when glossy, and lights up again with any tone or sheen variation laid on it for the hip view. Put the hip's
  interest behind it, and read the `ads` picture's exposure line in the `hero` log after every look change.
- **Tune edge wear at 4096.** At 1024 the bake's edge masks find almost no edge, so a look that is right there is wrong at
  full size.
- **Set a mid-value dielectric by the picture, not by the albedo's name.** In the review light an albedo of 0.105 shows at
  sRGB 150, 0.062 at 131, 0.031 at 110 and 0.027 at 107: a "slate grey" polymer beside a black slide needed about 0.027, and
  at 0.1 it read as primer. The game's light may show it darker; say so when you report.
- **A phosphate or oxide on small dark parts is metal, not a coat.** As a coat a pistol's sights read sRGB 119 beside a slide
  at 50.
- **Judge both side pictures, not only the hip side.** With texels given by view, the side the hip eye never sees has fewer
  texels, and the baked edge zone is wider in cm there, so every zone-led effect (edge line, rubbed band, specks) grows. A
  pistol's right side carried a pale outline round every cut that its left did not.
- **A rubbed band above about 0.3 on a black finish draws a border round every cut and letter.** Lead wear by `handled`
  zones and keep the generic edge terms low.
- **A line of wear along every edge draws the box, however broken it is.** Three things each drew one on a phosphate
  receiver: the weapon's own edge strips, the steel recipe's `edges`, and its `thin` band. Wear goes on the few edges this
  weapon is carried and worked by (a front lower corner, the lips of a port, a guard's bow), each fading out along its edge,
  with two scales of breakup: stretches a few cm long and a finer one inside each. A wear zone on a flat wall is narrow:
  on the edge or shoulder itself with a fade under 1 cm; a box 3 cm tall thinned a whole wall into another metal.
- **Where the eye looks along a face, roughness decides its brightness, not colour.** The hip eye sees a receiver's shoulder
  and a wrist's top at 70 to 75 degrees from the normal, where they mirror the studio: a shoulder with base colour 0.04 read
  sRGB 151 and a brown wrist read grey at 130. Darkening moved them a few levels; drier did it (the shoulder 0.20 rougher
  than the walls: 93; the wrist at 0.86: about 80). Under about 0.6 roughness hardly matters at that angle; over 0.75 it
  matters a great deal.
- **A coat reads far paler in the pictures than its colour says, and parts of one steel must stay one family.** Phosphate
  as a coat at linear 0.05 to 0.09 came out pale aluminium grey, a receiver paler than its barrel, like primer; 0.027 to
  0.050 is the dark grey that was meant. Measure the picture's pixels at the place before changing a colour again.
- **The steel recipe's `exposure` scatters pale chips beside exposed corners whatever `edges` is.** They were specks on
  sight matting and on a safety's ribs. Turn it off where the aiming eye looks; to find such a thing, return one finish
  alone and count bright texels in the base colour, instead of changing arguments.
- **Engraved letters need their whole stroke.** A lettering mask taken at 0.30 to 0.70 filled only the middle of each stroke
  and the words did not read from the side; taken at 0.08 to 0.42, with a floor at 0.005, dry (0.88) and a little deeper in
  the height, they read at 1024. No bright rim.
- **Leave stipple one dry sheen with a little dust.** Polish and grime inside it read as stains.
- **Read every mark for what it says beside this outline.** A two-digit rack number is harmless on most weapons; on one
  archetype a particular number is a real rifle's name, and it cost a rebuild from the bake. Choose digits, letters and
  dates with "no real model name" in mind.
- **Anti-glare serrations are the darkest thing in the aiming view.** No dust and no edge wear on them; at most a thin worn
  line on a few ridge ends. The black-metal finishes take them as `serrated` zones ([docs/look.md](docs/look.md)).
- **Lettering has to survive at half size.** Make it big enough that its fill is still there at 2048, and wear it where the
  story says, not evenly. A letter needs about 8 screen pixels of width along the gun in the 2400 px hip picture to be read; at
  5.5 only the word's shape is (on a side wall, about 0.35 cm wide near the grip and 0.6 over the magazine well): make the
  letters wider, not taller. A raised control hides the wall beyond it from the hip eye, about 4.7 times its height ahead of
  it and twice its height below: put a mark outside that, or accept that the control covers it.
- **Judge the look at full size.** 512 px is for finding errors, never for approving.
- **Nobody has verified the look in the game's lighting.** Recess darkening is in the base colour; if the game's material also
  applies occlusion, recesses sit darker there than in the pictures. Dark metals may read as holes. Say so when you report.
  The other half: a finish with `coat=1` and a roughness over 0.6 reads pale grey where the aiming eye looks along it (one
  SMG's rear top went from a base colour of 0.082 to 0.036 and the picture only from 0.163 to 0.159). Do not chase it with
  the base colour; it is the light on a rough surface. What can be changed there is the speckle (the painted set's share).

## 5. Judging a pass

- **Compare, do not score.** Two reviewers gave one build 6.5 and 8.5; every "is this crop better than that one" call held up.
  After each pass run `weaponforge <id> review --against <the build before>` and look at `pairs.png`: the same crops, cameras
  and lights, side by side. Copy the build's folder before every round of changes that will be shown: `review --against` needs
  the folder, and a baseline at another texture size is compared as it is.
- **Keep a change only if its pair is better. Otherwise put it back**, and write down what it looked like and why it failed.
  A reverted try with its reason is worth as much as a kept one.
- **Look where the player looks**: the hip and aiming pictures at native size, before the three-quarter beauty picture.
- **The order that wasted least**: outline and assemblies; hardware; the parts near the eye; texel density; the look; small
  machining last. Each of these was done out of order once and redone.
- **Retries are normal.** What this file is for is not repeating a mistake someone already made.

## 6. When the weapon is done: what did it teach?

Before calling a weapon finished, go through its brief's passes and put each lesson where the next weapon will meet it:

- **A technique** (a way of making something well that is not about this weapon's design) goes into the shared code, with a
  line in the reference (`docs/`). The test: would it help a weapon that looks nothing like this one?
- **A standard** (what good measured or looked like) goes into section 2 to 5 here, and into `weaponforge/review_rubric.md` if a
  reviewer comparing two crops should know it.
- **A mistake** goes here, at the step where it bites, in one or two lines with the reason. The full story goes into
  `PLAYBOOK.md`.
- **A design** (this weapon's sight, its stock, its colours) stays in the weapon's folder.

Keep this file short enough to read whole. When a lesson replaces an older one, take the older one out.
