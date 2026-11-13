"""Decal source pictures drawn by hand (Pillow): a stencilled rack number, a blank label with a hand-written number, a
paint-pen witness mark. Each on a plain background for `texforge decal --image`.

Usage: python make_decals.py --out <folder> [--fonts <folder>] [--bold-font <file>] [--hand-font <file>]
  --out        where the three pictures are written (stencil_07_src.png, label_14_src.png, witness_src.png); made if missing
  --fonts      a folder holding arialbd.ttf (Arial Bold) and Inkfree.ttf (Ink Free), the two fonts the original sets were
               drawn with (a Windows Fonts folder has both)
  --bold-font  the font of the stencilled 07 (instead of arialbd.ttf); --hand-font  the hand-written 14 (instead of Inkfree.ttf)

Without the original fonts it falls back to freely available ones it can find (Liberation Sans Bold, DejaVu Sans Bold; for
the hand-written number DejaVu Sans Oblique, else the same bold), else Pillow's own font, and says which it used: the
stencil and the label then differ a little in their lettering. The witness mark has no lettering.

The same seed (7) and the same order of random draws as the run that made the original sets: with numpy 1.26.4 and Pillow
10.4.0 (texforge's environment) and the two original font files the pictures come out byte for byte the same."""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ap = argparse.ArgumentParser(description='Draw the hand-made decal source pictures (stencil 07, label 14, witness mark).')
ap.add_argument('--out', required=True, help='output folder')
ap.add_argument('--fonts', help='folder holding arialbd.ttf and Inkfree.ttf (the original fonts)')
ap.add_argument('--bold-font', help='font file for the stencilled 07 (default: arialbd.ttf in --fonts, else a free bold font)')
ap.add_argument('--hand-font', help='font file for the hand-written 14 (default: Inkfree.ttf in --fonts, else a free font)')
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
OUT = args.out
FREE_DIRS = ('/usr/share/fonts', '/usr/local/share/fonts', os.path.expanduser('~/.fonts'), os.path.expanduser('~/.local/share/fonts'),
             '/Library/Fonts', '/System/Library/Fonts', os.path.expanduser('~/Library/Fonts'))


def find_free(names):
    for top in FREE_DIRS:
        for folder, _dirs, files in os.walk(top):
            for n in names:
                if n in files:
                    return os.path.join(folder, n)
    return None


def font_file(given, original, free):
    """The font to draw with: the one given, else the original in --fonts, else a free one found on this machine, else None
    (Pillow's own)."""
    if given:
        if not os.path.isfile(given):
            raise SystemExit('make_decals.py: no font file %s' % given)
        return given
    if args.fonts:
        path = os.path.join(args.fonts, original)
        if not os.path.isfile(path):
            raise SystemExit('make_decals.py: %s not found in --fonts %s' % (original, args.fonts))
        return path
    path = find_free(free)
    print('make_decals.py: %s not given; drawing with %s instead: the lettering differs a little from the original sets'
          % (original, path or "Pillow's own font"))
    return path


BOLD = font_file(args.bold_font, 'arialbd.ttf', ('LiberationSans-Bold.ttf', 'DejaVuSans-Bold.ttf'))
HAND = font_file(args.hand_font, 'Inkfree.ttf', ('DejaVuSans-Oblique.ttf', 'LiberationSans-Italic.ttf', 'LiberationSans-Bold.ttf',
                                                  'DejaVuSans-Bold.ttf'))


def truetype(path, size):
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
rng = np.random.default_rng(7)


def noise(h, w, sigma):
    n = Image.fromarray((rng.random((h, w)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(sigma))
    a = np.asarray(n, np.float32)
    return (a - a.mean()) / (a.std() + 1e-6)


# ---- 1. stencil "07": white paint through a stencil, bridges in the glyphs, a little overspray and paint lost in specks
W, H = 1400, 900
mask = Image.new('L', (W, H), 0)
d = ImageDraw.Draw(mask)
font = truetype(BOLD, 620)
d.text((W // 2, H // 2 + 20), '07', font=font, fill=255, anchor='mm')
box = mask.getbbox()
x0, y0, x1, y1 = box
mid = (x0 + x1) // 2
zx = (x0 + mid) // 2                                         # the middle of the 0
d.rectangle((zx - 20, y0 - 5, zx + 20, y0 + 95), fill=0)     # the 0's top and bottom bridges
d.rectangle((zx - 20, y1 - 95, zx + 20, y1 + 5), fill=0)
sx = mid + (x1 - mid) // 2                                   # the 7: a bridge where the bar meets the stroke
d.rectangle((sx + 40, y0 - 5, sx + 82, y0 + 110), fill=0)
m = np.asarray(mask, np.float32) / 255.0
spray = np.asarray(mask.filter(ImageFilter.GaussianBlur(9)), np.float32) / 255.0
m = np.clip(np.maximum(m, spray * 0.35), 0, 1)               # overspray just outside the stencil's edge
m *= np.clip(1.0 - np.clip(noise(H, W, 2.0) - 1.6, 0, 1) * 1.5, 0, 1)    # paint missing in specks
m *= np.clip(0.90 + 0.08 * noise(H, W, 25), 0.75, 1.0)       # thinner and thicker paint
paint = np.array([0.84, 0.82, 0.76])
img = (m[..., None] * paint * 255).astype(np.uint8)
Image.fromarray(img).save(os.path.join(OUT, 'stencil_07_src.png'))

# ---- 2. a blank label, hand-written "14", a torn-off corner and dirt along its edge, on blue
W, H = 1300, 900
bg = np.array([0.0, 0.10, 0.85])
lab = Image.new('L', (W, H), 0)
d = ImageDraw.Draw(lab)
L, T, R, B = 110, 120, 1190, 780
d.rounded_rectangle((L, T, R, B), radius=40, fill=255)
tear = [(R - 330, B + 10)]                                  # the lower right corner torn off along a ragged line
for i in range(1, 30):
    t = i / 30.0
    x = R - 330 + t * 340 + rng.normal(0, 7)
    y = B + 10 - t * 300 + rng.normal(0, 7)
    tear.append((x, y))
tear += [(R + 20, B - 290), (R + 20, B + 20)]
d.polygon(tear, fill=0)
a = np.asarray(lab, np.float32) / 255.0
edge = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(18)), np.float32) / 255.0
rim = np.clip((1.0 - edge) * 2.4 - 0.30, 0, 1) * a * 0.85                  # 1 near the label's edge, inside it
paper = np.array([0.68, 0.65, 0.56])
dirt = np.array([0.36, 0.31, 0.24])
grime = np.clip(rim * (0.8 + 0.4 * noise(H, W, 12)) + 0.22 * np.clip(noise(H, W, 45), 0, 2), 0, 1)
col = paper * (1 - grime[..., None]) + dirt * grime[..., None]
col *= (1.0 + 0.04 * noise(H, W, 1.5))[..., None]           # the paper's own fibre
ink = Image.new('L', (W, H), 0)
di = ImageDraw.Draw(ink)
di.text(((L + R) // 2 - 60, (T + B) // 2 + 10), '14', font=truetype(HAND, 470), fill=255, anchor='mm')
k = np.asarray(ink.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255.0 * a
k *= np.clip(0.93 + 0.07 * noise(H, W, 6), 0, 1)              # a felt marker going dry in places
col = col * (1 - k[..., None]) + np.array([0.05, 0.05, 0.06]) * k[..., None]
out = bg * (1 - a[..., None]) + col * a[..., None]
Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'label_14_src.png'))

# ---- 3. a paint-pen witness mark: one short wobbly stroke, top to bottom, on black
W, H = 300, 1300
st = Image.new('L', (W, H), 0)
d = ImageDraw.Draw(st)
pts = [(W / 2 + 10 * np.sin(y / 170.0) + rng.normal(0, 1.5), y) for y in range(110, H - 110, 10)]
d.line(pts, fill=255, width=78, joint='curve')
d.ellipse((pts[0][0] - 39, 71, pts[0][0] + 39, 149), fill=255)
d.ellipse((pts[-1][0] - 39, pts[-1][1] - 39, pts[-1][0] + 39, pts[-1][1] + 39), fill=255)
m = np.asarray(st.filter(ImageFilter.GaussianBlur(2)), np.float32) / 255.0
m *= np.clip(1.0 - np.clip(noise(H, W, 2.5) - 1.3, 0, 1) * 1.2, 0, 1)
pen = np.array([0.86, 0.80, 0.30])                            # a yellow paint pen
Image.fromarray((m[..., None] * pen * 255).astype(np.uint8)).save(os.path.join(OUT, 'witness_src.png'))
print('ok')
