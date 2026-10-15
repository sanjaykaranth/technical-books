#!/usr/bin/env python3
"""Mirror the raw material of MIT 6.5130 (Fall 2025) into ../raw.

Fetches the course pages, their scripts and styles, every locally referenced
image, the slide image folders (LectureN/SlideK.*) and the PowerPoint decks.
Plain HTTP only, no browser. Safe to re-run: existing files are skipped.
"""
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://people.csail.mit.edu/asolar/SynthesisCourse/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw")
N_LECTURES = 25
SUFFIXES = ["png", "PNG", "svg", "SVG"]


def fetch(path):
    """Return bytes for BASE+path, or None on 404."""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(BASE + path, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2)
        except Exception:
            time.sleep(2)
    print(f"  failed: {path}", file=sys.stderr)
    return None


def save(path, data):
    dest = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)


def get(path):
    dest = os.path.join(OUT, path)
    if os.path.exists(dest):
        return open(dest, "rb").read()
    data = fetch(path)
    if data is not None:
        save(path, data)
    return data


def local_refs(html):
    """Relative src/href targets in a page (skip anchors and absolute URLs)."""
    refs = set()
    for m in re.finditer(rb'(?:src|href)\s*=\s*["\']([^"\'#]+)["\']', html):
        ref = m.group(1).decode("utf-8", "ignore").strip()
        if re.match(r"^[a-z]+:", ref, re.I) or ref.startswith("//"):
            continue
        refs.add(ref.lstrip("./"))
    return refs


def slide_folder(n):
    """Download LectureN/SlideK.* until 4 consecutive misses."""
    k, misses, got = 1, 0, 0
    while misses < 4:
        found = False
        for s in SUFFIXES:
            path = f"Lecture{n}/Slide{k}.{s}"
            if os.path.exists(os.path.join(OUT, path)) or fetch_and_save(path):
                found = True
                got += 1
                break
        misses = 0 if found else misses + 1
        k += 1
    return n, got


def fetch_and_save(path):
    data = fetch(path)
    if data is None:
        return False
    save(path, data)
    return True


def main():
    os.makedirs(OUT, exist_ok=True)
    pages = ["index.htm", "TOC.htm"] + [f"Lecture{i}.htm" for i in range(1, N_LECTURES + 1)]
    support = ["lectures.txt", "library.js", "style.css", "biblio.bib",
               "icons/grow.png", "icons/shrink.png", "icons/next.png", "icons/bar.png"]

    refs = set()
    for p in pages + support:
        data = get(p)
        print(f"{'ok ' if data else 'missing'} {p}")
        if data and p.endswith(".htm"):
            refs |= local_refs(data)
    # Inline slide references like "Lecture7:Slide5" are expanded by library.js;
    # the full folders below cover them.
    refs -= set(pages) | set(support)
    print(f"\n{len(refs)} other local references")
    with ThreadPoolExecutor(8) as ex:
        for ref, ok in zip(sorted(refs), ex.map(lambda r: get(r) is not None, sorted(refs))):
            if not ok:
                print(f"  missing ref: {ref}")

    decks = []
    for i in range(1, N_LECTURES + 1):
        decks += [f"Lecture{i}.pptx", f"Lecture{i}-2025.pptx"]
    with ThreadPoolExecutor(6) as ex:
        found = [d for d, data in zip(decks, ex.map(get, decks)) if data]
    print(f"\n{len(found)} decks: {' '.join(found)}")

    with ThreadPoolExecutor(6) as ex:
        for n, got in ex.map(slide_folder, range(1, N_LECTURES + 1)):
            print(f"Lecture{n}/: {got} slide images")

    # Inline figures: <slide>Folder:Name; Name2</slide>, expanded by library.js
    # into Folder/Name.{SVG,svg,png,PNG}. Folders are not always LectureN.
    inline = set()
    for p in pages:
        html = open(os.path.join(OUT, p), encoding="utf-8", errors="ignore").read()
        for block in re.findall(r"<slide>(.*?)</slide>", html, re.S):
            folder = None
            for part in (x.strip() for x in block.split(";")):
                if ":" in part:
                    folder, part = (y.strip() for y in part.split(":", 1))
                if folder and part:
                    inline.add(f"{folder}/{part}")

    def get_inline(stem):
        if any(os.path.exists(os.path.join(OUT, f"{stem}.{s}")) for s in SUFFIXES):
            return stem, True
        for s in ["SVG", "svg", "png", "PNG"]:  # library.js tries SVG first
            if fetch_and_save(f"{stem}.{s}"):
                return stem, True
        return stem, False

    with ThreadPoolExecutor(8) as ex:
        missing = [s for s, ok in ex.map(get_inline, sorted(inline)) if not ok]
    print(f"\n{len(inline)} inline figures, {len(missing)} missing: {missing}")


if __name__ == "__main__":
    main()
