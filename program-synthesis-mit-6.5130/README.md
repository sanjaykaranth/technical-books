# Introduction to Program Synthesis (MIT 6.5130, Fall 2025)

Course by Armando Solar-Lezama (with Theo X. Olausson). Original site: https://people.csail.mit.edu/asolar/SynthesisCourse/index.htm

Copyright of the course material belongs to its authors. The original site is the authoritative and current version.

## Three formats

1. **`Introduction-to-Program-Synthesis.pdf`**: the lecture notes typeset as a book (classic textbook layout, LaTeX). It has three units as parts, 25 lectures as chapters, numbered figures from the slides the notes embed, typeset code and math, and one numbered reference list. Animated slide sequences show their final frame. The text is not reworded.
2. **`lectures/`**: one folder entry per lecture, with notes and slides separate:
   - `LNN-notes.pdf`: that lecture's chapter on its own, with its references.
   - `LNN-slides.pdf`: the full slide deck. The source is the 2025 PowerPoint where one exists (vector), else a deck matching the site's slide images, else the site's images.
3. **`raw/`**: an unmodified mirror of the course site: lecture pages, `library.js`, `style.css`, `lectures.txt`, `biblio.bib`, slide images (`LectureN/SlideK.png`), inline figures (`Agents/`, `Sampling/`, ...), and the PowerPoint decks.

## Known issues on the course site

The book handles these as follows:
- The Lecture 23 and 25 pages repeat the notes of Lectures 22 and 24, so those chapters hold a short note and the slides cover them.
- The Lecture 7 page ends with the full text of Lecture 8; it is printed once, in Lecture 8.

## Rebuilding

Requirements: Python 3 with Pillow, Google Chrome (headless, for SVG figures and image-only decks), Keynote (pptx to PDF), and [Tectonic](https://tectonic-typesetting.github.io/) at `~/.local/bin/tectonic`.

```
python3 tools/download_raw.py           # refresh raw/ (plain HTTP)
python3 tools/build.py                  # book + lectures/ notes + slides
python3 tools/build.py book             # just the book
python3 tools/build.py notes --only 7   # one lecture's notes
```

- `tools/html2tex.py` converts a lecture page and the site's custom tags (`<codeblock>`, `<cite>`, `<slide>`, ...) to LaTeX.
- `tools/figs.py` rasterises SVG figures, drops animation build-up frames and crops margins.
- `tex/preamble.tex` holds the book style.

To browse `raw/` offline, serve it over HTTP: `cd raw && python3 -m http.server 8000`.
