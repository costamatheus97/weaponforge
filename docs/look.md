# The look: surface kinds, finishes, wear, lettering, painted sets

How a weapon's textures are decided. The look is the weapon's `surface()` in `weapon.py`, laid over the bakes by the `texture`
stage. What the choices should be comes from the person and the brief (`CRAFT.md`, sections 1 and 4); this file is how to
say them.

## Words that are used for two things

- **A surface kind** is what a part is made of: `steel`, `bright`, `dark`, `wood`, `brass`, `copper`, `polymer`, or a kind
  the weapon defines. A builder says it with `K.tag(obj, bone, mat=kind)`; the bake writes it into the material-ID map; the
  look has one recipe per kind. See "Surface kinds".
- **A steel finish** is the weapon's class attribute `finish` (`finish = 'parkerized'`): the name of a steel treatment in
  `surface.STEEL` (`blued`, `polished_blue`, `parkerized`, `grey_phosphate`, `phosphate_black`, `nitride`, `anodized`,
  `painted`, `patina`, `nickel`, `stainless`), which `surface()` hands to the steel recipe (`S.steel(s, self.finish)`). A
  recipe or a named finish that takes a `finish=` argument takes a name from the same table. The wood has the same shape: the
  attribute `timber`, a name in `surface.WOOD`.
- **A named finish** is a whole material look in `weaponforge/finish.py` (`moulded_polymer`, `rubber`, `anodised_alloy`,
  `phosphate_parts`, `barrel_phosphate`, `sheet_magazine`, `bright_steel`): a recipe with its arguments, its painted texforge
  set and the wear on top. A weapon uses them in rows of `F.look(...)`, one row per surface kind. See "Named finishes", below.

In this documentation "the steel finish" always means the attribute and "a named finish" always means an entry of
`finish.py`. The two meet in one place: a row such as `('steel', 'phosphate_parts', {'finish': self.finish})` gives the
named finish `phosphate_parts` the weapon's steel finish as its argument.

## Surface kinds

The seven kinds the tool knows are in `bake.KINDS`: `steel` (the default: blued or parkerised steel), `bright` (bare polished
steel: a barrel, a bolt), `dark` (small black parts: sights, controls), `wood`, `brass`, `copper`, `polymer`. A kind is a
colour code in the material-ID map, one bit per channel, so **at most seven kinds exist at once, and black (0, 0, 0) means "no
surface"**. Each also carries the default edge break (cm) its normal map has (`edge_break`, below).

A weapon that needs another material (anodised alloy, rubber) defines its own table, `kinds = {kind: bake.Kind(code, bevel)}`.
Two things to know first:

- **The weapon's table replaces the default one, it does not add to it.** List every kind the builders use, including the
  ones taken unchanged from `B.KINDS`. A part tagged with a kind that is not in the table stops the bake with an error naming
  the part.
- **There is no free code beyond seven**, so a new kind takes over the code of one the weapon does not use. Nothing checks
  that two kinds have different codes: two kinds with one code are one kind to the bake, and a recipe for the one lays on the
  other. Give each kind its own.

AssaultG3 and SmgG2 both do this: they have no wood, so rubber takes wood's code, and they have no copper part of their own,
so the alloy takes copper's. This is SmgG2's table (a submachine gun built with this tool; its folder is not in this repository):

    from weaponforge import bake as B

    kinds = {'steel': B.KINDS['steel'], 'bright': B.KINDS['bright'], 'dark': B.KINDS['dark'], 'polymer': B.KINDS['polymer'],
             'brass': B.KINDS['brass'],
             'alloy': B.Kind((0, 1, 1), 0.040),      # copper's code
             'rubber': B.Kind((0, 1, 0), 0.070)}     # wood's code
    edge_break = {'alloy': 0.035, 'rubber': 0.07}    # optional: per kind, cm; a kind not named keeps its Kind's bevel

Then a builder tags a part `K.tag(obj, bone, mat='alloy')`, a part of more than one kind names them in `hp_kinds()`, and
`surface()` gets a row or a recipe for each: `('alloy', 'anodised_alloy')` in `F.look`, or a layer you build. The first row of
`F.look` fills everything whatever its kind. In both examples the bullets' copper tips, which have no kind of their own once copper's code is the alloy's, are told from their
brass cases by position in `surface()`.

## Writing `surface()`

The look is `surface()` in `weapon.py`: one recipe per surface kind the builders tagged (`steel`, `bright`, `dark`, `wood`,
`brass`, `copper`, `polymer`), stacked by the kind's mask from the ID bake. `worn_steel`, `wood` with a real plank, `brass`
and `copper` are the reference recipes. **`polymer` and the plank-less procedural `wood` are starting points**: expect to
tune them. To change the look only, re-run `texture rig render` (the bake is not needed again).

`polymer` clouds, wears a pale line along its convex edges and carries a moulded grain (`mottle`, `edge`, `grain`, each
1.0 by default and 0 to switch it off). On black polymer these are most of what there is to see: it has no colour of
its own to vary, and without the edge line a moulding's panel lines and steps are invisible on a flat grey face
(PLAYBOOK "Textures and look" item 17). A part can switch all three off.

A weapon can widen the edge break the bake rounds every edge with: `edge_break = {'polymer': 0.085}` (cm, per surface
kind; `bake.KINDS` holds the defaults, 0.03 for steel).

**Wear can follow use instead of curvature.** By default the recipes wear every convex edge alike, which on a big
moulded weapon reads as an outline. A weapon can say where it is touched: `handled = [Zone(lo, hi, strength, soft,
tilt=..., note='the firing hand'), ...]` (`weaponforge.weapon.Zone`: a soft box in the weapon frame, cm), and likewise
`smooth` and `textured` for polymer moulded smooth or stippled; `surface()` then passes `handled=s.handled, exposure=1.0,
recess=1.0, vary=1.0` to `S.steel` / `S.polymer` (and `smooth=s.smooth, textured=s.textured, fade=1.0` to polymer). All
of it is off unless asked for, so a weapon that sets none of it has its textures unchanged. AssaultG3 is the worked example; PLAYBOOK
"Textures and look" item 18 has what each argument does and what to look for.

**Choose the steel finish and the timber; do not take the defaults.** The defaults are blued steel and walnut, and
weapons that all take them look alike. Each
weapon states two class attributes, `finish` (the steel finish, a name in `surface.STEEL`: `blued`, `polished_blue`, `parkerized`,
`grey_phosphate`, `phosphate_black`, `nitride`, `anodized`, `painted`, `patina`, `nickel`, `stainless`) and `timber` (a
name in `surface.WOOD`: `walnut`, `dark_walnut`, `beech`, `amber_birch`, `red_laminate`, `rosewood`, `honey`,
`weathered`), and `surface()` passes them to `S.steel(s, self.finish, ...)` and `S.timber(s, self.timber, ...)`. Pick what
your other weapons do not already have, and look at the weapon beside the others before showing it. `blued` and `walnut` are
the reference looks (the recipes' defaults); the rest are starting points (PLAYBOOK, "Textures and look", item 12). A pale steel finish (`stainless`, and any
you add) needs four things a dark one does not: less of the broad cloud (`cloud`), brushing along the weapon (`brush`),
dark-filled engraving (`fill`) and less soft grime (`dirt`); they are arguments of `S.worn_steel` (item 13).

**Lettering can be filled with paint.** Engraved text is cut with `K.text_solid` (in the `hp` branch of a builder), and
the tool keeps a copy of every such cutter for the bake, which turns the copies into a mask of where the letters are
(`bake/marks.npy`, `bake/preview_marks.png`). A weapon that sets `paint = ('white',)` gets its letters filled with that
paint; `paint = ('white', 'red')` with `ink=1` on one `text_solid` fills that text red (FIRE beside a white SAFE). The
names are in `surface.PAINT`; `paint_wear` (0 to 1) takes paint out in specks. Bare engraving is close to invisible on a
black gun, and white-filled selector marks are one of the things that make a rifle read as a real object. It needs
texels: a letter wants ten or more across its height, so 0.25 cm letters want 40 px/cm (the check `uv: texel density`
prints the weapon's). A weapon built with an older version of the tool has no lettering copies in its file: run `model --hp-only` and
the chain from `bake` on (item 16).

### Painted texture sets and decals (texforge)

**Painted texture sets and decals (texforge), both opt-in.** What noise cannot give, a moulding's spark-eroded grain,
a bead-blast, a phosphate's crystals, a stencilled number, a label, oil run down from a slot, comes from pictures made with
texforge, a separate companion tool. A *tiling set* (`texforge make`) is laid on by position, through the three sides of
the weapon frame and blended across them (or round the bore, `around=(y, z)`, for turned steel): `images()` returns
`S.texforge_sets(self, 'poly_mould', ...)`, and `surface()` passes `detail=S.detail(s, 'poly_mould'), detail_tone=0.2,
detail_relief=1.4, detail_rough=0.06` to `S.polymer` or `S.steel` (a list `[(mask, S.detail(...)), ...]` gives the rail one set
and the sights another). Only the set's BaseColor and Height are used, and only as variation round their own mean: the
recipe keeps its hue and value. A *decal* is `Weapon.decals = [Decal('stencil_07', lo, hi, '+Y', ...)]`
(`weaponforge.weapon.Decal`): a `texforge decal` picture put on through a box from one side, only on the faces that look that
way, fitted in the box with its own aspect, laid on after the recipes (colour, darkening, roughness, metal, a step at its
outline), optionally worn away where the gun is handled; `colour=None, darken=...` makes it a grime or oil mask. Sets and
decals are found by name, looking in order in the weapon's `textures/`, in `_materials/` beside the weapons under the asset
root it is built in, in `_materials/` under the configured asset root, and in the folder the setting `materials` (or
`WEAPONFORGE_MATERIALS`) names (`surface.material_dirs`); sets several weapons share go in a `_materials/` folder. Put only
`<name>_BaseColor.png`, `_Height.png`, `_Opacity.png` (decals) and `<name>.texforge.json` there. None ship with the
repository; AssaultG3's twelve are described, with how to regenerate them, in `weapons/assault_g3/painted/` (`sets.json`,
`regenerate.sh`). Without them the named finishes keep their procedural pattern and the decals are left out; the texture stage prints
one line naming what it did not find and where it looked. The command lines that worked, and why texforge's own defaults
are wrong here, are in PLAYBOOK "Textures and look" item 19. AssaultG3 is the worked example (its `TEXFORGE` blocks).

**What a decal's background is.** A decal source picture is a mark on a plain background, and `texforge decal` finds the
background itself: it takes the median colour of the picture's border, and the alpha is the distance of every pixel from
that colour (texforge's `decal.py`, `extract_alpha`). Its `--background white|black` option, default `white`, is only
read when texforge asks the image generator for the picture (it tells the generator which background to draw); with
`--image` it does nothing. That is why `weapons/assault_g3/painted/regenerate.sh` passes no `--background` for a stencil
that `make_decals.py` drew white on black: the black border is detected. A mark that touches the picture's border, or a
background that is not plain, is cut out wrongly, and a dark mark on a pale label wants a coloured background
(`PLAYBOOK.md`, "Textures and look", item 19). texforge's own README says only that the alpha comes from the distance to
the plain background; the default and the `--image` behaviour are read from its code.

### Named finishes

Start the look here. `weaponforge/finish.py` holds whole materials by name (named finishes: not the steel finish `finish` of the weapon, see "Words that are used for two things", above), each a recipe with its
arguments, the texforge set it lays on and how, and the wear on top (hand polish in patches, scuffs in the material's own
colour, grime round the controls and in recesses, a top-to-bottom fade, bright thin wear on black metal's top corners, dust
in slots, carbon at the muzzle). They are AssaultG3's tuned look lifted out of that weapon. A weapon names one per surface kind in a small table, the first row the base:

    from weaponforge import finish as F
    def images(self):
        return S.texforge_sets(self, *F.sets('phosphate_parts', 'moulded_polymer'))      # the sets those named finishes lay on
    def surface(self, s):
        return F.look(s, [('steel', 'phosphate_parts', {'finish': self.finish}),
                          ('steel', 'barrel_phosphate', {}, F.part_zone(s, 'barrel')),     # where: narrows the kind to a place
                          ('polymer', 'moulded_polymer', {'colour': (0.020, 0.020, 0.022)}),
                          ('wood', S.timber(s, self.timber))])                            # a ready layer works too

A row is `(kind, finish name or a Layer[, {argument: value}[, where]])`; a `where` given as None (a `part_zone` of a part the
weapon has not got) leaves the row out. Every argument can be overridden; the defaults are AssaultG3's. `DEFAULT` (an
argument's default where it says so) means "take it from what the weapon declares". The named finishes and what they take:

| named finish | for | arguments (defaults in finish.py) | set |
|-|-|-|-|
| `moulded_polymer` | a moulded shell, stock, grip, handguard, any colour | `colour` (olive), `worn` (1.19 x colour), `matt`, `mottle`, `edge`, `fade`, `handled` / `smooth` / `textured` (DEFAULT: the weapon's zones), `exposure`, `recess`, `vary`, `patches`, `polish` / `polish_darken` / `polish_amount` / `polish_rough`, `fade_z` (DEFAULT: the polymer parts' z range), `fade_range`, `fade_rough`, `grime` (DEFAULT: the weapon's `grime` list, else a box round every control bone's head and the AmmoEject socket), `grime_tint` / `grime_amount` / `grime_rough`, `texture*` | `poly_mould` at 9 cm |
| `rubber` | butt pads, cheek pads, grip inserts: matt, never polished | `colour`, `worn`, `matt`, `mottle`, `textured` (DEFAULT: the weapon's `rubber_textured`), `exposure`, `recess`, `vary`, `texture*` | `rubber` |
| `anodised_alloy` | a top cover, a rail, an alloy receiver | the `S.steel` arguments (`finish='anodized'`, `blue`, `gloss`, `thin`, `edges`, `rust`, `cloud`, `handled`, `exposure`, `recess`, `vary`, any other through `**over`), `tops` (DEFAULT: faces that look up), `slides` (where scratches run; DEFAULT: the `handled` zones), `sparkle`, `bare`, `texture*` | `anodised` at 2 cm |
| `phosphate_parts` | small steel parts, hardware, sights, controls (with the `bright` and `dark` kinds when the weapon has them) | `finish='parkerized'`, `bright`, `dark`, `gloss`, `thin`, `handled`, `exposure`, `recess`, `vary`, `tops`, `bare`, `**over`, `texture*` | `phosphate` |
| `barrel_phosphate` | a barrel and its muzzle device | `finish='phosphate_black'`, `blue`, `gloss`, `coat`, `thin`, `edges`, `rust`, `handled`, `exposure`, `recess`, `vary`, `muzzle_x` (DEFAULT: the Muzzle socket), `fouling_from` (DEFAULT: `device_len` cm behind it), `soot`, `soot_rough`, `**over`, `texture*` | `phosphate` |
| `sheet_magazine` | a dark sheet-steel magazine | `finish='phosphate_black'`, `blue`, `black`, `gloss`, `coat`, `thin`, `edges`, `handled` (where it is set down; DEFAULT: faces that look down), `exposure`, `recess`, `vary`, `**over`, `texture*` | `phosphate` |
| `bright_steel` | a bare bolt, carrier, pins, a stainless barrel | `finish='stainless'`, `handled`, `exposure`, `recess`, `vary`, `**over`, `texture*` | none |

`texture*` is `texture` (the set's name, None for none), `texture_cm` (its tile, cm), `texture_tone`, `texture_relief`,
`texture_rough` (the recipe's `detail_*`). Helpers: `F.sets(*names)` (the sets for `images()`), `F.part_zone(s, *builders)`
(a mask over those builders' parts, for `where`), `F.black_metal_life(s, layer, kind, tops, slides)`, `F.grime_places(weapon)`,
`F.make(s, name, **arguments)` (one named finish as a Layer). AssaultG3's `surface()` is the worked example: its places (grime
boxes, the rail's and the sights' tops, where the charging handle runs, the magazine's floor) are its own methods, passed as
arguments.

**Turning the wear down, and serrated faces.** The black-metal finishes (`anodised_alloy`, `phosphate_parts`, and
`F.black_metal_life` itself) put pale dust on every groove floor and a bright thin line on every top corner. On most parts
that is the life of the finish; on some it is wrong, and these arguments say where (all off by default, and then the textures
are unchanged):

| argument | what it does |
|-|-|
| `dust`, `corners` | how much of the dust and of the corner line is kept everywhere: 1 as it was, 0 off |
| `dust_off`, `corners_off` | a `[Zone]` list or a mask: the dust or the corner line is removed there; a zone's strength is how much of it goes |
| `serrated` | a `[Zone]` list or a mask of anti-glare serrations (a sight ramp, a sight leaf): faces that are nothing but grooves and corners, where the finish would otherwise make bright silver bars. No dust and no corner wear there; the ridges are the black dye, the grooves dry and black. Laid over everything else |
| `serrated_ends` | zones of ridge ends where a sparse few keep the finish's own thin worn line |
| `serrated_metal` | how much of the ridge is metal: one number, or a list with one per zone of `serrated`. About 0.6 for a face seen at a grazing angle (as a coat, a dry black reads pale grey there), 0.15 for one that faces the eye (as all metal it is a black hole with no grooves); 0.4 by default |
| `serrated_colour`, `serrated_rough` | (ridge, groove) colours and roughness |

SmgG2's alloy row is the worked example (in SmgG2's `weapon.py`, not in this repository: `serrated=self.serrations`).

**The broad mottling apart from the fine variation.** `vary` (0 to 1) in the steel and polymer recipes is roughness as a main
channel: a broad drift over many cm, greasy smudges a few cm across, a millimetre-scale variation and sparse scuffs.
`vary_broad` is how much of the broad part (the drift, the smudges and, on steel, the patches of paler tone) is kept; `None`,
the default, means the same as `vary`. On a flat stamped wall the broad part reads as smudged paint: `vary=1, vary_broad=0.2`
keeps the fine variation and turns the mottling down. `moulded_polymer` and `rubber` take it by name, the steel finishes
through `**over`. `cloud` (an `S.worn_steel` argument: 1 by default, 0 in `anodised_alloy`) is the broad light-and-dark drift
in the steel's own colour, a separate thing: lower it for a clean bright finish.

### Edge masks by the centimetre

Opt-in. The bake's edge masks are worked out per texel, so on a denser UV island a bevel's
edge wear is thinner in cm. `edge_px_cm = 47.0` on a weapon recomputes them at `texture` time from the saved normal map with
each island's measured density (`surface.edges_by_cm`, `maps.edge_masks`): at 47 px/cm (on a 4096 sheet) the masks are as
baked; at twice that the curvature counts twice and its smoothing and the wide zone's blur are twice as many texels. The
number is the density the look was tuned at. The occlusion and the hollows stay as baked. It adds about two and a half
minutes to `texture` at 4096 (not re-timed with the figures in [stages.md](stages.md)). Off by default, and then nothing changes, to the byte. AssaultG3 tried it in place of its
`fp_convex()` and kept `fp_convex()` (the note at its `edge_px_cm`).
