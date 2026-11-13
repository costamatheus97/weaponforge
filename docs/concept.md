# Showing the concept

The first of the person's four approvals is the concept, and it comes before any builder is written. "Show the concept" means
a defined set of things, so that two agents show the same thing and the person has something to choose from:

1. **The brief**: `weapons/<id>/BRIEF.md`, written from the person's answers to `CRAFT.md`'s questions (section 1).
2. **Two or three side outlines**, to scale, that **differ in kind**: not three versions of one idea with different
   proportions, but three different answers to "what is the one thing a player remembers about its outline?" (a long slotted
   shroud against a short one hung low against one stamping from end to end; the magazine in front of the trigger, behind it,
   or raked; a stock that is wire, wood or moulded). Each is drawn from the weapon's left, muzzle pointing the
   same way in all (the sketch below puts +X, the muzzle, on the right), at one scale in centimetres (say the scale), as a **filled silhouette**, with the **parts in flat material
   colours** so the person can see where each material goes (the receiver, the furniture, the magazine, the pad). Mark the
   datums that the brief fixes (the grip's origin, the bore line, the sight line) and the overall length and height.
3. **A recommendation**: which one, and the reasons in a few lines, with the risk of the choice. The person may still pick
   another, or ask for parts of one on another (say which).
4. **What each outline differs in**: a short table with a column per candidate and a row per difference (what the receiver
   is, what the shroud or fore-end is, where the furniture colour goes, what the support hand holds, the magazine, the
   stock, the overall length and height). (SmgG2's brief, not in this repository, has one under "Outline: three candidates".)

Where the pictures go: every candidate as its own PNG, and one sheet with all of them side by side, in
**`<asset root>/<id>/ref/`**. The folder does not exist until you make it, and `weaponforge new` refuses an id whose asset
folder already exists, so run `new` first and make `ref/` after it. Keep the candidates the person did not choose: they are
the record of what was offered. After approval, copy the chosen one under a clear name (`chosen.png`) in the same folder and
say in the brief which it is and what the person changed ("Outline C as approved"). The brief has a place for both
(`BRIEF.md`, "Outline: candidates and the chosen one").

## Drawing them

A small script is enough, and it is the agent's own: outlines as lists of `(x, z)` points in centimetres in the weapon frame
(origin in the grip, +X toward the muzzle), one polygon per part, each with a flat colour from the brief's materials. It needs
nothing from the pipeline, and no Blender. This is a sketch of the whole of it (Pillow); make the polygons from the datums the
brief fixes:

    from PIL import Image, ImageDraw

    PX_PER_CM = 20                                  # one scale for every candidate; write it on the sheet
    LO, HI = (-45.0, -18.0), (30.0, 12.0)           # the drawing's box, cm: (x, z)

    def to_px(x, z):                                # +X to the right, +Z up
        return ((x - LO[0]) * PX_PER_CM, (HI[1] - z) * PX_PER_CM)

    def draw(name, parts):                          # parts: [(colour, [(x, z), ...]), ...]
        w, h = int((HI[0] - LO[0]) * PX_PER_CM), int((HI[1] - LO[1]) * PX_PER_CM)
        img = Image.new('RGB', (w, h), (235, 235, 232))
        d = ImageDraw.Draw(img)
        for colour, pts in parts:
            d.polygon([to_px(x, z) for x, z in pts], fill=colour)
        d.line([to_px(0, LO[1]), to_px(0, HI[1])], fill=(200, 60, 60))      # the grip's origin
        img.save(name + '.png')                     # run it from <asset root>/<id>/ref/
        return img

    receiver = [(-20, 4), (-20, 9), (18, 9), (18, 4)]
    draw('candidate_a', [((60, 62, 66), receiver)])

Look at the sheet before showing it: the outlines must be legible at a glance, in the same scale, and different enough that
the person is choosing between ideas and not between details. After approval, the chosen outline is also the thing to lay
over the model's filled side outline before approval 2 (`CRAFT.md`, section 2, "A silhouette is judged as a silhouette").

Pictures made with an image generator may be used for feel only, and only if the person agrees to it (`PLAYBOOK.md`,
section 2, item 10); they do not replace the to-scale outlines, which carry the sizes the brief promises.
