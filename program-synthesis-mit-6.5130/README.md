# Introduction to Program Synthesis (MIT 6.5130, Fall 2025)

Course by Armando Solar-Lezama (with Theo X. Olausson). Original site: https://people.csail.mit.edu/asolar/SynthesisCourse/index.htm

Copyright of the course material belongs to its authors. The original site is the authoritative and current version.

## Layout

- `raw/`: an unmodified mirror of the course site as published: lecture pages (`LectureN.htm`), `library.js`, `style.css`, `lectures.txt`, slide images (`LectureN/SlideK.png`), inline figures (`Agents/`, `Sampling/`, ...), and the PowerPoint decks (`LectureN.pptx`, plus `LectureN-2025.pptx` where a 2025 revision exists).
- `tools/download_raw.py`: the script that produced `raw/` (plain HTTP, safe to re-run).

To browse `raw/` offline, serve it over HTTP (the pages load `lectures.txt` via XHR, which browsers block on `file://`):

```
cd raw && python3 -m http.server 8000
# open http://localhost:8000/index.htm
```

Coming next: a single-file PDF, and a folder with lecture notes and slides as separate per-lecture PDFs.
