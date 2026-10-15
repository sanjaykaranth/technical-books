#!/usr/bin/env python3
"""Build the typeset editions of MIT 6.5130 from raw/.

Outputs (in the course folder):
  Introduction-to-Program-Synthesis.pdf   the whole book (notes only)
  lectures/LNN-notes.pdf                  each lecture's notes on its own
  lectures/LNN-slides.pdf                 each lecture's full slide deck

Usage: build.py [book] [notes] [slides] [--only N,N]   (default: all three)
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "raw")
TEX = os.path.join(ROOT, "tex")
BUILD = os.path.join(ROOT, "build", "book")
LECTURES = os.path.join(ROOT, "lectures")
BOOK_PDF = os.path.join(ROOT, "Introduction-to-Program-Synthesis.pdf")
TECTONIC = os.path.expanduser("~/.local/bin/tectonic")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
N = 25

sys.path.insert(0, HERE)
import html2tex  # noqa: E402

# Pages on the course site that currently repeat an earlier lecture's notes.
DUPLICATE_PAGES = {23: 22, 25: 24}
# Pages whose tail repeats the next lecture verbatim: (heading where the copy starts, lecture).
DUPLICATE_TAILS = {7: ("Representing Sets and Symbolic Expressions", 8)}


def schedule():
    """Parse raw/lectures.txt into [(unit_title or None, lecture_no, title)]."""
    items, unit = [], None
    text = open(os.path.join(RAW, "lectures.txt"), encoding="utf-8").read()
    for entry in (e.strip() for e in text.split(";")):
        if not entry:
            continue
        m = re.match(r"Unit\s*\d+\s*:\s*(.+)", entry)
        if m:
            unit = m.group(1).strip()
            items.append(("unit", unit))
            continue
        m = re.match(r"Lecture\s+(\d+)\s*,\s*[^,]+,\s*(.+)", entry)
        if m:
            items.append(("lecture", int(m.group(1)), m.group(2).strip()))
    return items


def h1_title(n):
    page = open(os.path.join(RAW, f"Lecture{n}.htm"), encoding="utf-8", errors="ignore").read()
    m = re.search(r"<h1>\s*Lecture\s*\d+\s*:\s*([^<]+)", page)
    return m.group(1).strip().rstrip(".") if m else f"Lecture {n}"


def fix_bib(src, dst):
    """Copy biblio.bib, repairing entries that BibTeX rejects."""
    text = open(src, encoding="utf-8", errors="ignore").read()
    # A field name with an empty value followed by a stray '= {...}' line.
    text = re.sub(r"(\n\s*)(\w+)\s*=\s*\n?\s*=\s*", r"\1\2 = ", text)
    # crossref to proceedings entries that are not in the file.
    text = re.sub(r"\n\s*crossref\s*=\s*\{[^}]*\},?", "", text)
    open(dst, "w", encoding="utf-8").write(text)


def write_chapters():
    os.makedirs(BUILD, exist_ok=True)
    report = []
    for n in range(1, N + 1):
        out = os.path.join(BUILD, f"lecture{n:02d}.tex")
        if n in DUPLICATE_PAGES:
            tex = (f"\\chapter{{{html2tex.convert_text(h1_title(n))}}}\n\n\\sitenote{{The course website's "
                   f"page for this lecture currently repeats the notes of Lecture {DUPLICATE_PAGES[n]}, "
                   f"so no separate notes are included here. The slides for this lecture are in "
                   f"\\texttt{{lectures/L{n:02d}-slides.pdf}}.}}\n")
            report.append(f"L{n}: duplicate page, stub chapter")
        else:
            stop = DUPLICATE_TAILS.get(n, (None,))[0]
            tex, fg = html2tex.convert(RAW, n, BUILD, stop_at=stop)
            report.append(f"L{n}: {fg.count} figures, {fg.dropped} build frames dropped"
                          + (f", MISSING {fg.missing}" if fg.missing else ""))
        open(out, "w").write(tex)
    with open(os.path.join(BUILD, "macros.tex"), "w") as f:
        f.write("% Macros the notes define inside MathJax formulas (page-global there).\n")
        f.write("".join(d + "\n" for d in html2tex.MACROS.values()))
    fix_bib(os.path.join(RAW, "biblio.bib"), os.path.join(BUILD, "biblio.bib"))
    shutil.copy(os.path.join(TEX, "preamble.tex"), BUILD)
    print("\n".join(report))


def front_matter():
    today = date.today().strftime("%-d %B %Y")
    return rf"""
\frontmatter
\begin{{titlepage}}
\centering
\vspace*{{0.22\textheight}}
{{\Huge\bfseries Introduction to\\[0.6ex] Program Synthesis\par}}
\vspace{{3ex}}
{{\Large Lecture Notes\par}}
\vspace{{8ex}}
{{\Large\scshape Armando Solar-Lezama\par}}
\vspace{{1.5ex}}
{{\large with Theo X. Olausson\par}}
\vfill
{{\large MIT 6.5130, Fall 2025\par}}
\end{{titlepage}}

\thispagestyle{{empty}}
\vspace*{{\fill}}
{{\small\noindent
\textcopyright\ Armando Solar-Lezama, 2018, 2025. \textcopyright\ Theo X. Olausson, 2025. All rights reserved.

\medskip\noindent
These are the lecture notes of MIT 6.5130, \emph{{Introduction to Program Synthesis}}, as published on the
course website, \url{{https://people.csail.mit.edu/asolar/SynthesisCourse/}}. The text, code, mathematics,
figures and references are taken from the website without rewording; only the presentation has been
changed. Figures are slides that the notes embed; where a figure on the website steps through an
animation, only its final frame is shown here. The website's page for Lecture 7 ends with the full
text of Lecture 8; that text is printed once, in Lecture 8. The complete slide decks are published
separately, one file per lecture.

\medskip\noindent
Typeset on {today}. The website is the authoritative and current version.\par}}
\cleardoublepage
\tableofcontents
\mainmatter
"""


def write_book():
    body = []
    for item in schedule():
        if item[0] == "unit":
            body.append(f"\\part{{{html2tex.convert_text(item[1])}}}")
        else:
            body.append(f"\\input{{lecture{item[1]:02d}}}")
    doc = ("\\documentclass[11pt,openright]{book}\n\\input{preamble}\n\\begin{document}\n"
           + front_matter() + "\n".join(body) +
           "\n\\backmatter\n\\cleardoublepage\\phantomsection\\addcontentsline{toc}{chapter}{References}\n"
           "\\bibliographystyle{unsrtnat}\n\\bibliography{biblio}\n\\end{document}\n")
    open(os.path.join(BUILD, "book.tex"), "w").write(doc)
    compile_tex("book.tex")
    shutil.copy(os.path.join(BUILD, "book.pdf"), BOOK_PDF)
    print(f"book -> {BOOK_PDF}")


def write_notes(only):
    os.makedirs(LECTURES, exist_ok=True)
    titles = {i[1]: i[2] for i in schedule() if i[0] == "lecture"}
    for n in only:
        name = f"L{n:02d}-notes"
        cites = "\\bibliographystyle{unsrtnat}\n\\bibliography{biblio}\n" \
            if "\\cite" in open(os.path.join(BUILD, f"lecture{n:02d}.tex")).read() else ""
        doc = ("\\documentclass[11pt,openany]{book}\n\\input{preamble}\n"
               "\\renewcommand{\\bibname}{References}\n"
               "\\begin{document}\n"
               f"\\setcounter{{chapter}}{{{n - 1}}}\n\\input{{lecture{n:02d}}}\n"
               + cites + "\\end{document}\n")
        open(os.path.join(BUILD, name + ".tex"), "w").write(doc)
        compile_tex(name + ".tex")
        shutil.copy(os.path.join(BUILD, name + ".pdf"), os.path.join(LECTURES, name + ".pdf"))
        print(f"notes L{n} ({titles.get(n, '')})")


def compile_tex(name):
    r = subprocess.run([TECTONIC, "-X", "compile", "--keep-logs", name], cwd=BUILD,
                       capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("error")]
    if r.returncode != 0:
        raise SystemExit(f"{name} failed:\n" + "\n".join(errs[:10]))


# ---------------------------------------------------------------- slides

def slide_count_pptx(path):
    out = subprocess.run(["unzip", "-l", path], capture_output=True, text=True).stdout
    return len(re.findall(r"ppt/slides/slide\d+\.xml$", out, re.M))


def slide_images(n):
    files = glob.glob(os.path.join(RAW, f"Lecture{n}", "Slide*.*"))
    return sorted(files, key=lambda f: int(re.search(r"Slide(\d+)", f).group(1)))


def keynote_pdf(pptx, pdf):
    script = f'''
tell application "Keynote"
  set d to open POSIX file "{pptx}"
  export d to POSIX file "{pdf}" as PDF with properties {{PDF image quality:Best, skipped slides:false}}
  close d saving no
end tell'''
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True)


def images_pdf(images, pdf):
    with tempfile.TemporaryDirectory() as d:
        page = os.path.join(d, "s.html")
        with open(page, "w") as f:
            f.write("<html><head><style>@page{size:10in 5.625in;margin:0}body{margin:0}"
                    "img{display:block;width:10in;height:5.625in;object-fit:contain;"
                    "page-break-after:always}</style></head><body>")
            for im in images:
                f.write(f"<img src='file://{im}'>")
            f.write("</body></html>")
        # Own profile dir so it can run alongside other headless Chrome jobs.
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={os.path.join(d, 'profile')}",
                        "--allow-file-access-from-files", "--virtual-time-budget=15000",
                        f"--print-to-pdf={pdf}", f"file://{page}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not os.path.exists(pdf):
            raise RuntimeError(f"Chrome did not write {pdf}")


def write_slides(only):
    """Prefer the 2025 deck; else a pptx that matches the site's slide images
    (vector, sharper); else the site's slide images; else any pptx."""
    os.makedirs(LECTURES, exist_ok=True)
    for n in only:
        out = os.path.join(LECTURES, f"L{n:02d}-slides.pdf")
        new = os.path.join(RAW, f"Lecture{n}-2025.pptx")
        old = os.path.join(RAW, f"Lecture{n}.pptx")
        imgs = slide_images(n)
        if os.path.exists(new):
            keynote_pdf(new, out); src = "2025 deck"
        elif os.path.exists(old) and imgs and slide_count_pptx(old) == len(imgs):
            keynote_pdf(old, out); src = "deck (matches site images)"
        elif imgs:
            images_pdf(imgs, out); src = f"site images ({len(imgs)})"
        elif os.path.exists(old):
            keynote_pdf(old, out); src = "deck"
        else:
            src = "NONE"
        print(f"slides L{n}: {src}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = list(range(1, N + 1))
    if "--only" in sys.argv:
        only = [int(x) for x in sys.argv[sys.argv.index("--only") + 1].split(",")]
        args = [a for a in args if not re.match(r"^[\d,]+$", a)]
    what = set(args) or {"book", "notes", "slides"}
    if what & {"book", "notes"}:
        write_chapters()
    if "book" in what:
        write_book()
    if "notes" in what:
        write_notes(only)
    if "slides" in what:
        write_slides(only)
