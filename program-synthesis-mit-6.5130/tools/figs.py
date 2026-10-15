#!/usr/bin/env python3
"""Prepare inline slide figures for print.

For each <slide> block in the notes:
  * SVG frames are rasterised (headless Chrome, 1920 px wide).
  * Frames that are only a build-up step of the next frame (all of their ink
    reappears unchanged in the next frame) are dropped, so an animation prints
    as its final state while genuinely different slides are all kept.
  * Uniform margins around the content are cropped.
Processed images are cached under build/figs/.
"""
import json
import os
import subprocess
import tempfile

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "raw")
OUT = os.path.join(ROOT, "build", "figs")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
EXTS = ["png", "PNG", "svg", "SVG"]


def source(folder, name):
    for e in EXTS:
        p = os.path.join(RAW, folder, f"{name}.{e}")
        if os.path.exists(p):
            return p
    return None


def rasterise_svg(svg, png):
    os.makedirs(os.path.dirname(png), exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        page = os.path.join(d, "f.html")
        with open(page, "w") as f:
            f.write("<html><body style='margin:0;background:#fff'>"
                    f"<img src='file://{svg}' style='width:1920px;display:block'></body></html>")
        shot = os.path.join(d, "s.png")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--allow-file-access-from-files", "--default-background-color=ffffffff",
                        "--window-size=1920,1200", f"--user-data-dir={os.path.join(d, 'profile')}", f"--screenshot={shot}", f"file://{page}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        im = Image.open(shot).convert("RGB")
        im.save(png)


def load(folder, name):
    """RGB image for a frame (rasterising SVGs once), or None."""
    src = source(folder, name)
    if src is None:
        return None, None
    if src.lower().endswith(".svg"):
        png = os.path.join(OUT, "svg", folder, name + ".png")
        if not os.path.exists(png):
            rasterise_svg(src, png)
        src = png
    return Image.open(src).convert("RGB"), src


def ink(im, tol=24):
    """Mask of pixels that differ from the background (top-left pixel)."""
    bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
    d = ImageChops.difference(im, bg).convert("L")
    return d.point(lambda v: 255 if v > tol else 0)


def is_build_of(a, b):
    """True if b shows everything a shows, plus more (an animation step)."""
    if a.size != b.size:
        return False
    ma = ink(a)
    na = ma.histogram()[255]
    if na == 0:
        return True
    changed = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 40 else 0)
    lost = ImageChops.multiply(changed, ma)  # a's ink that changed in b
    nlost = lost.convert('L').point(lambda v: 255 if v else 0).histogram()[255]
    nb = ink(b).histogram()[255]
    return nlost <= 0.01 * na and nb > na


def crop(im, pad_frac=0.025):
    box = ink(im).getbbox()
    if not box:
        return im
    w, h = im.size
    pad = int(pad_frac * w)
    l, t, r, b = box
    return im.crop((max(0, l - pad), max(0, t - pad), min(w, r + pad), min(h, b + pad)))


CACHE = os.path.join(OUT, "blocks.json")
_cache = None


def process_block(frames):
    """Cached wrapper around _process_block (comparisons are slow)."""
    global _cache
    if _cache is None:
        _cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    key = ";".join(f"{f}:{n}" for f, n in frames)
    hit = _cache.get(key)
    if hit and all(os.path.exists(p) for p in hit[0]):
        return hit[0], hit[1], hit[2]
    res = _process_block(frames)
    _cache[key] = list(res)
    os.makedirs(OUT, exist_ok=True)
    json.dump(_cache, open(CACHE, "w"), indent=0)
    return res


def _process_block(frames):
    """frames: [(folder, name)] -> (list of processed image paths, dropped count, missing)."""
    loaded, missing = [], []
    for folder, name in frames:
        im, _ = load(folder, name)
        if im is None:
            missing.append(f"{folder}/{name}")
        else:
            loaded.append((folder, name, im))
    # Drop exact repeats (the site sometimes lists a frame twice in a row).
    dedup = []
    for item in loaded:
        if dedup and dedup[-1][2].size == item[2].size and \
                ImageChops.difference(dedup[-1][2], item[2]).getbbox() is None:
            continue
        dedup.append(item)
    loaded_n, loaded = len(loaded), dedup
    keep = []
    for i, (folder, name, im) in enumerate(loaded):
        if i + 1 < len(loaded) and is_build_of(im, loaded[i + 1][2]):
            continue
        keep.append((folder, name, im))
    paths = []
    for folder, name, im in keep:
        out = os.path.join(OUT, "crop", folder, name + ".png")
        if not os.path.exists(out):
            os.makedirs(os.path.dirname(out), exist_ok=True)
            crop(im).save(out, optimize=True)
        paths.append(out)
    return paths, loaded_n - len(keep), missing


def width_fraction(crop_path):
    """Width of a cropped figure relative to its full slide (for consistent scale)."""
    rel = os.path.relpath(crop_path, os.path.join(OUT, "crop"))
    folder, fname = os.path.split(rel)
    name = os.path.splitext(fname)[0]
    src = source(folder, name)
    if src and src.lower().endswith(".svg"):
        src = os.path.join(OUT, "svg", folder, name + ".png")
    try:
        return min(1.0, Image.open(crop_path).width / Image.open(src).width)
    except Exception:
        return 1.0
