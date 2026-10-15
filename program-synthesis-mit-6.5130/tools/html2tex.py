#!/usr/bin/env python3
"""Convert a lecture page from raw/ (the course's HTML + custom tags) to LaTeX.

The pages use a small vocabulary that the site's library.js expands at load
time: <codeblock>, <cite>, <slide>, <quote>, <aside>, <grammar>, <rule>,
<footnotes>, plus ordinary HTML and MathJax TeX ($...$, \\[...\\], \\(...\\)).
This script maps each of those to LaTeX. Text is never reworded.

Usage: html2tex.py RAW_DIR N OUT.tex [--figdir DIR]
"""
import html
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs  # noqa: E402

IMG_EXTS = ["png", "PNG", "pdf", "svg", "SVG"]

# --------------------------------------------------------------------------
# Escaping. Math is protected first, then text is escaped, then math restored.

TEXT_ESC = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}", "<": r"\textless{}", ">": r"\textgreater{}",
}
MATH_RE = re.compile(
    r"(\$\$.+?\$\$|\\\[.+?\\\]|\\\(.+?\\\)|(?<![\\$])\$(?!\$).+?(?<!\\)\$)", re.S)


UNI_MATH = {"λ": r"\lambda", "∧": r"\wedge", "∨": r"\vee", "−": "-", "∅": r"\emptyset",
            "→": r"\rightarrow", "←": r"\leftarrow", "⇒": r"\Rightarrow", "≤": r"\leq",
            "≥": r"\geq", "≠": r"\neq", "∀": r"\forall", "∃": r"\exists", "¬": r"\neg",
            "∈": r"\in", "×": r"\times", "⊢": r"\vdash", "⊥": r"\bot", "⊤": r"\top"}


def esc_text(s):
    return "".join(TEXT_ESC.get(c) or (f"\\ensuremath{{{UNI_MATH[c]}}}" if c in UNI_MATH else c) for c in s)


def esc_code(s):
    """Inline code: monospace, escaped, breakable."""
    return esc_text(s).replace(" ", "\\ ")


NEWCMD_RE = re.compile(r"\\(?:re)?newcommand\s*\{\\(\w+)\}(\[\d\])?\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})")


# MathJax macro definitions are page-global; LaTeX would scope them to the
# formula. They are collected here and written to macros.tex by the build.
MACROS = {}
DISPLAY_ENVS = r"(?:align|alignat|gather|multline|flalign|equation|eqnarray)\*?"


def fix_array(m):
    """MathJax accepts \\begin{array} without a column spec; LaTeX does not."""
    def add_spec(match):
        start = match.end()
        end = m.find("\\end{array}", start)
        body = m[start:end if end > 0 else len(m)]
        cols = max((row.count("&") for row in body.split("\\\\")), default=0) + 1
        return match.group(0) + "{" + "l" * cols + "}"
    m = re.sub(r"\\begin\{array\}(?!\s*\{)", add_spec, m)
    return wrap_desc_column(m)


def wrap_desc_column(m):
    """Grammar tables put long prose in a last \\mbox column, which cannot wrap.
    Make that column a paragraph column and let the prose wrap."""
    def fix(match):
        spec, body = match.group(1), match.group(2)
        rows = [r for r in re.split(r"\\\\", body) if r.strip()]
        lasts = [r.split("&")[-1].strip() for r in rows if "&" in r]
        if not lasts or not spec.endswith("l") or not all(x.startswith("\\mbox{") for x in lasts):
            return match.group(0)
        def cell_to_text(cell):
            # \mbox{prose} becomes plain prose; anything between is math.
            out, pos = [], 0
            for mb in re.finditer(r"\\mbox\{([^{}]*)\}", cell):
                math = cell[pos:mb.start()].strip()
                if math:
                    out.append(f"${math}$ ")
                out.append(mb.group(1))
                pos = mb.end()
            tail = cell[pos:].strip()
            if tail:
                out.append(f" ${tail}$")
            return "".join(out).strip()
        new_rows = []
        for r in re.split(r"(\\\\)", body):
            if "&" in r:
                head, last = r.rsplit("&", 1)
                r = head + "& " + cell_to_text(last.strip()) + "\n"
            new_rows.append(r)
        body = "".join(new_rows)
        return f"\\begin{{array}}{{{spec[:-1]}p{{0.42\\linewidth}}}}{body}\\end{{array}}"
    return re.sub(r"\\begin\{array\}\{([^}]*)\}(.*?)\\end\{array\}", fix, m, flags=re.S)


def fix_math(m):
    m = html.unescape(m)
    m = "".join(UNI_MATH[c] + " " if c in UNI_MATH else c for c in m)

    def hoist(d):
        nargs = int(d.group(2)[1]) if d.group(2) else 0
        MACROS.setdefault(d.group(1), f"\\gdef\\{d.group(1)}{''.join(f'#{i}' for i in range(1, nargs + 1))}{d.group(3)}")
        return ""
    m = NEWCMD_RE.sub(hoist, m)
    m = re.sub(r"\n\s*\n", "\n", m)  # blank lines are illegal inside math
    if m.startswith("$$"):
        m = "\\[" + m[2:-2] + "\\]"
    elif re.match(r"^\$\s*\n\s*\\begin\{array\}", m):
        m = "\\[" + m[1:-1] + "\\]"  # a table set on its own lines
    m = fix_array(m)
    # MathJax tolerates display environments inside \[ \]; LaTeX does not.
    inner = re.match(r"^\\\[\s*(\\begin\{(" + DISPLAY_ENVS + r")\}.*\\end\{\2\})\s*\\\]$", m, re.S)
    if inner:
        return inner.group(1)
    # Displays are shrunk only if wider than the text block (\fitdisplay).
    # A bare \\ outside any environment needs real display mode, so skip those.
    if m.startswith("\\["):
        outer = m[2:-2]
        while re.search(r"\\begin\{(\w+\*?)\}.*?\\end\{\1\}", outer, re.S):
            outer = re.sub(r"\\begin\{(\w+\*?)\}.*?\\end\{\1\}", "", outer, flags=re.S)
        if "\\\\" not in outer:
            return "\\fitdisplay{" + m[2:-2].strip() + "}"
    return m


def convert_text(s):
    """Escape a run of prose, preserving math spans."""
    s = html.unescape(s)
    out, pos = [], 0
    for m in MATH_RE.finditer(s):
        out.append(esc_text(s[pos:m.start()]))
        out.append(fix_math(m.group(0)))
        pos = m.end()
    out.append(esc_text(s[pos:]))
    t = "".join(out)
    t = re.sub(r'"([^"\n]*)"', r"``\1''", t)  # paired straight quotes
    t = t.replace('"', "''")
    return t


# --------------------------------------------------------------------------
# Figures

class Figures:
    def __init__(self, raw, figdir, lecture):
        self.raw, self.figdir, self.lecture = raw, figdir, lecture
        self.count = 0
        self.dropped = 0
        self.missing = []

    def render(self, inner):
        folder, frames = None, []
        for part in (x.strip() for x in inner.split(";")):
            if ":" in part:
                folder, part = (y.strip() for y in part.split(":", 1))
            if folder and part:
                frames.append((folder, part))
        paths, dropped, missing = figs.process_block(frames)
        self.dropped += dropped
        self.missing += missing
        if not paths:
            return ""
        self.count += 1
        # Frames are stacked (with page breaks allowed between them) so slide
        # text stays legible. slidefig and \slidewidth come from the book style.
        body = "\n\\par\\medskip\n".join(
            f"\\includegraphics[width={figs.width_fraction(p):.3f}\\slidewidth,height=0.42\\textheight,keepaspectratio]{{"
            + os.path.relpath(p, self.figdir) + "}" for p in paths)
        return "\n\\begin{slidefig}\n" + body + "\n\\end{slidefig}\n"


# --------------------------------------------------------------------------
# HTML walk

BLOCK_RAW = {"codeblock", "slide", "rule", "grammar", "script", "style",
             "footnotes", "iframe", "jsexample"}


class Converter(HTMLParser):
    def __init__(self, figs):
        super().__init__(convert_charrefs=False)
        self.figs = figs
        self.out = []
        self.raw_tag = None
        self.raw_buf = []
        self.list_stack = []
        self.href_stack = []
        self.code_depth = 0
        self.text_buf = []

    # buffering so that math spanning tags-free text is matched whole
    def flush(self):
        if self.text_buf:
            s = "".join(self.text_buf)
            self.text_buf = []
            if self.code_depth:
                self.out.append(esc_code(html.unescape(s)))
            else:
                self.out.append(convert_text(s))

    def emit(self, s):
        self.flush()
        self.out.append(s)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.raw_tag:
            self.raw_buf.append(self.get_starttag_text())
            return
        a = dict(attrs)
        if tag in BLOCK_RAW:
            self.flush()
            self.raw_tag, self.raw_buf = tag, []
        elif tag == "h1":
            self.emit("\n\\chapter{")
        elif tag == "h2":
            self.emit("\n\\section{")
        elif tag == "h3":
            self.emit("\n\\subsection{")
        elif tag == "h4":
            self.emit("\n\\paragraph{")
        elif tag == "p":
            self.emit("\n\n")
        elif tag == "br":
            self.emit("\\\\\n")
        elif tag == "b":
            self.emit("\\textbf{")
        elif tag in ("i", "em"):
            self.emit("{\\em ")
        elif tag == "quote":
            self.emit("\n\\begin{quote}\\itshape\n")
        elif tag == "code":
            self.emit("\\code{")
            self.code_depth += 1
        elif tag == "cite":
            self.flush()
            self.raw_tag, self.raw_buf = "cite", []
        elif tag == "a":
            href = a.get("href", "")
            if href.startswith("http"):
                self.emit("\\href{" + href.replace("%", "\\%").replace("#", "\\#") + "}{")
                self.href_stack.append(True)
            else:
                self.href_stack.append(False)
        elif tag in ("ul", "ol"):
            env = "itemize" if tag == "ul" else "enumerate"
            self.list_stack.append(env)
            self.emit(f"\n\\begin{{{env}}}\n")
        elif tag == "li":
            self.emit("\n\\item ")
        elif tag == "aside":
            self.emit("\n\\begin{aside}\n")
        elif tag == "center":
            self.emit("\n\\begin{center}\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.raw_tag:
            if tag == self.raw_tag:
                inner = "".join(self.raw_buf)
                t, self.raw_tag = self.raw_tag, None
                self.raw_block(t, inner)
            else:
                self.raw_buf.append(f"</{tag}>")
            return
        if tag in ("h1", "h2", "h3", "h4"):
            self.emit("}\n")
        elif tag in ("b", "i", "em"):
            self.emit("}")
        elif tag == "quote":
            self.emit("\n\\end{quote}\n")
        elif tag == "code":
            self.flush()
            self.code_depth -= 1
            self.out.append("}")
        elif tag == "a":
            if self.href_stack and self.href_stack.pop():
                self.emit("}")
        elif tag in ("ul", "ol"):
            env = self.list_stack.pop() if self.list_stack else "itemize"
            self.emit(f"\n\\end{{{env}}}\n")
        elif tag == "aside":
            self.emit("\n\\end{aside}\n")
        elif tag == "center":
            self.emit("\n\\end{center}\n")

    def handle_startendtag(self, tag, attrs):
        if self.raw_tag:
            self.raw_buf.append(self.get_starttag_text())
        elif tag.lower() == "p":
            self.emit("\n\n")
        elif tag.lower() == "br":
            self.emit("\\\\\n")

    def handle_data(self, data):
        if self.raw_tag:
            self.raw_buf.append(data)
        else:
            self.text_buf.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")

    def handle_comment(self, data):
        pass

    def raw_block(self, tag, inner):
        if tag == "codeblock":
            code = html.unescape(inner).expandtabs(4).strip("\n")
            code = re.sub(r"\n\s*\n(\s*\n)+", "\n\n", code)
            # Symbols the monospace font lacks are set in math (escapeinside).
            code = "".join(f"(*@\\ensuremath{{{UNI_MATH[c]}}}@*)" if c in UNI_MATH else c for c in code)
            self.out.append("\n\\begin{lstlisting}\n" + code + "\n\\end{lstlisting}\n")
        elif tag == "cite":
            keys = ",".join(k.strip() for k in html.unescape(inner).split(","))
            if self.out:
                self.out[-1] = self.out[-1].rstrip()
            self.out.append(f"~\\cite{{{keys}}}")
        elif tag == "slide":
            self.out.append(self.figs.render(html.unescape(inner)))
        elif tag == "rule":
            top, bot = (html.unescape(x).replace("->", r"\rightarrow")
                        for x in inner.split("---", 1))
            self.out.append(f"\n\\[\\frac{{{top.strip()}}}{{{bot.strip()}}}\\]\n")
        elif tag == "grammar":
            rows = [convert_text(r.strip()) for r in inner.split(";;") if r.strip()]
            self.out.append("\n\\begin{center}\\begin{tabular}{l}\n" +
                            " \\\\\n".join(rows) + "\n\\end{tabular}\\end{center}\n")
        # script, style, footnotes (bibliography placeholder), iframe: dropped


def extract_content(page):
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    m = re.search(r'<div class="content">(.*)', page, re.S)
    body = m.group(1) if m else page
    return body


def convert(raw, n, figdir, stop_at=None):
    """stop_at: an <h2> heading at which to end the lecture (used where a page
    repeats the following lecture's text)."""
    page = open(os.path.join(raw, f"Lecture{n}.htm"), encoding="utf-8", errors="ignore").read()
    if stop_at:
        cut = page.find(f"<h2>{stop_at}")
        foot = page.find("<footnotes>")
        if cut > 0:
            page = page[:cut] + (page[foot:] if foot > cut else "")
    figs = Figures(raw, figdir, n)
    c = Converter(figs)
    c.feed(extract_content(page))
    c.close()
    c.flush()
    tex = "".join(c.out)
    # Chapter title: drop the "Lecture N:" prefix and any trailing slide link text.
    tex = re.sub(r"\\chapter\{\s*Lecture\s*\d+\s*:\s*", r"\\chapter{", tex, count=1)
    tex = re.sub(r"\s*\\href\{[^}]*\}\{\(slides\)\}\s*\}", "}", tex, flags=re.I)
    tex = re.sub(r"\s*\(slides\)\s*\}", "}", tex, flags=re.I)
    tex = re.sub(r"[ \t]+\n", "\n", tex)
    tex = re.sub(r"\n{3,}", "\n\n", tex)
    return tex.strip() + "\n", figs


if __name__ == "__main__":
    raw, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    figdir = sys.argv[sys.argv.index("--figdir") + 1] if "--figdir" in sys.argv else os.path.dirname(os.path.abspath(out))
    tex, fg = convert(raw, n, figdir)
    with open(out, "w") as f:
        f.write(tex)
    print(f"Lecture {n}: {fg.count} figures, {fg.dropped} build frames dropped; missing: {fg.missing or 'none'}")
