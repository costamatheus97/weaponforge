"""Soft variants of the AI decal pictures: a blurred halo under the crisp marks (a leak's stain, a scrape's abraded patch),
so they read at a texel of 0.2 to 0.4 mm. Same plain background as the source.

Usage: python soften.py --leak <leak picture> --leak-out <png> --scrape <scrape picture> --scrape-out <png>
  --leak        the chosen `texforge gen --name leak_src` candidate (the published sets used leak_src_src_2.png)
  --scrape      the chosen `texforge gen --name scrape_src` candidate (the published sets used scrape_src_src_2.png)
  --leak-out    where the soft leak goes (regenerate.sh: leak_src/leak_soft_src.png)
  --scrape-out  where the soft scrape goes (regenerate.sh: scrape_src/scrape_soft_src.png)
No randomness: the same input pictures give the same output."""
import argparse

import numpy as np
from PIL import Image, ImageFilter

ap = argparse.ArgumentParser(description='Soft variants of the leak and scrape decal pictures.')
ap.add_argument('--leak', required=True)
ap.add_argument('--leak-out', required=True)
ap.add_argument('--scrape', required=True)
ap.add_argument('--scrape-out', required=True)
args = ap.parse_args()


def blur(a, r):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0


# leak on white: darkness -> a soft brown stain round the drips, strongest near the top
src = np.asarray(Image.open(args.leak).convert('RGB'), np.float32) / 255.0
dark = 1.0 - src.mean(-1)
halo = blur(dark, 22)
halo = np.clip(halo / np.percentile(halo, 99.5), 0, 1) * 0.70
h = src.shape[0]
fall = np.clip(1.15 - np.linspace(0, 1, h)[:, None] * 0.9, 0.2, 1.0)        # thicker at the top, thinning down the run
halo = halo * fall
stain = np.array([0.30, 0.24, 0.17])
out = src * (1 - halo[..., None]) + stain * halo[..., None]
Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(args.leak_out)

# scrape on black: pale scratches -> a pale abraded patch under them
src = np.asarray(Image.open(args.scrape).convert('RGB'), np.float32) / 255.0
lum = src.mean(-1)
patch = blur(lum, 16)
patch = np.clip(patch / np.percentile(patch, 99.5), 0, 1) * 0.55
out = np.maximum(src, patch[..., None] * np.array([0.62, 0.62, 0.60]))
Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(args.scrape_out)
print('ok')
