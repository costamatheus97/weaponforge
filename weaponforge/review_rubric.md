# Which crop reads better?

You see two crops, A and B, of the same game weapon from the same camera, lights and exposure. Say which one reads more
like a real, made weapon at the size it is shown, or that they are the same. Judge only what differs between them.

## Better: what was kept on AssaultG3

- Round holes and aperture rims that are clean circles, with a flat land round an aperture rather than grooves running into it.
- Detail a maker would put there and that belongs to a part: screws in counterbores, pins with heads and clips, a castellated
  nut, turned rings, a cross-bolt. Placed with the part's edges and recesses, not over them.
- Materials that read apart: anodised alloy, rubber, polymer, phosphate or blued steel, each with its own sheen.
- Wear where hands and use put it: edges that stand out or are handled, grime round controls, pins and shut lines, a magazine
  floor worn to metal. Elsewhere the surface stays even.
- Polymer that is a deep, slightly varied colour, darker and polished where it is held.
- Lettering, numerals and pictograms that can be read from where the crop is taken: on a side wall seen along the gun, letters
  wide enough that the word is read, not only its shape.
- Anti-glare serrations (a sight ramp, a sight leaf) that are the darkest thing round the sights: dark ridges, darker dry
  grooves.
- Texture that is sharp at this size, with no blur, no seam and no colour bleeding across an edge.
- Machining that is subtle: a shallow pocket reads as a soft dark shape, not as clutter.

## Worse: what was turned back

- A patch of stripes, flutes or grooves laid over a surface with ragged or staggered ends, crowding a screw or a recess
  (it reads as arbitrary, not designed).
- A wavy bright smear where a groove catches the light; serrations that read as bright silver bars.
- A flat stamped wall mottled in broad soft patches, which reads as smudged paint.
- A tint or film that reads as rust, or as a pale dirty veil over the metal.
- A stair of groove ends round a hole, which reads as noise.
- A hump, plate or wedge standing off a surface that should blend into it.
- Polymer that is chalky, bleached or one flat tone; a pale line outlining every edge (it reads as a toy).
- A dark line that reads as a crack; a decal broken into slivers.
- Round parts close to the eye with visible flat sides; blur; a visible UV seam.

## Two kinds of crop that are not a detail

- A crop named `side_outline` (you are not told the name, but you will see it) is a flat grey silhouette on near-black, from the
  weapon's left, from one camera for both. There is no surface to judge: prefer the outline with the cleaner, more deliberate
  shape (a clear profile, parts that stand out of it on purpose, no stub or lump that reads as a mistake) and say "same" when the
  outlines match.
- A crop of a whole side wall (a large, flat face) is judged on what is on it: the lettering, the shut lines, the wear and the
  colour, and on the face staying one clean plane where a plane is meant.

## Answer

Write one JSON object and nothing else:

    {"better": "a" | "b" | "same", "confidence": 0.0 to 1.0, "why": "one sentence naming what you saw"}

Answer "same" when they differ only by noise or by something none of the points above covers. Use about 0.5 when you are
unsure and 0.9 or more only when the difference is plain at a glance.
