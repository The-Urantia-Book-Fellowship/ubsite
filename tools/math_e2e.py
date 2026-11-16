"""A note's formulas on a phone, end to end in Chrome (build/texmath.py).

A browser sets a <math> as one box, which never breaks across lines, and a
note's card has no sideways scroll: on a phone the sum at 15:7.12 ran 332 px
past its card, its result out of reach, and three notes already live lost a
digit or three (found 2026-11-15, the cards having been looked at on a desktop
only).  So a formula a line may break in is built as several <math>, one a
piece, a <wbr/> between them (Tigran, 2026-11-15: "let it break a formula
after a relation or a binary operator").  This holds what no test of the
markup can:

- that the table of the forms each operator has in the browser's dictionary
  (texmath._FORMS) is the browser's: stating the form the table answers, for
  an operator first, in the middle or last in its row, draws what the browser
  drew with nothing said;
- that a formula in pieces stands, unbroken, exactly where it stood whole,
  every box of it: the corpora of the tests and every formula of the reviewed
  notes;
- that a line does break between the pieces, also in a span that does not
  wrap, where a formula is kept with the punctuation typed against it;
- that at 390, 360 and 320 px every formula of every study note's card is
  inside the card's text, and the card and the List of study notes do not
  scroll sideways;
- and that no piece of any note's formula, the translator's notes among them,
  is wider than a card's text at 320 px.  One that is cannot be mended here:
  the note is to be reworded, or the formula written as shorter ones.

    .venv/bin/python tools/math_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8136 with the visit counter off, and
leaves the dev server alone.  Not a gate, like preview_e2e.py:
tests/test_texmath.py holds the static facts.  Run it after a note with a
formula is added, and after a change to texmath.py or to the card's styles.
"""

from __future__ import annotations

import html
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import time
import tomllib
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import texmath  # noqa: E402

PORT = "8136"
BASE = "http://127.0.0.1:" + PORT
WIDTHS = (390, 360, 320)
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def formulas() -> list[tuple[str, str]]:
    """Every formula the converter is held to: the two corpora of the tests,
    and the reviewed notes' own, each once."""
    rows: list[tuple[str, str]] = []
    for path in sorted((ROOT / "data" / "study").glob("[0-9]*.toml")):
        for note in tomllib.loads(path.read_text(encoding="utf-8")).get("note", []):
            rows += [(note["at"], m) for m in re.findall(r"\$([^$]+)\$", note.get("tex", ""))]
    for name in ("study-math.tsv", "tr-math.tsv"):
        for line in (ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                ref, tex = line.split("\t", 1)
                rows.append((name.split("-")[0] + " " + ref, tex))
    seen: set[str] = set()
    return [(ref, tex) for ref, tex in rows if not (tex in seen or seen.add(tex))]


def stored() -> tuple[list[tuple[str, int]], list[str]]:
    """The study notes that hold a formula, as (section, number), and every
    <math> of every note in the database, the translator's too, each once."""
    db = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    notes = db.execute(
        "SELECT p.paper_n || ':' || p.section_n, sn.num FROM footnote f"
        " JOIN study_note sn ON sn.footnote_id = f.id JOIN paragraph p ON p.id = f.paragraph_id"
        " WHERE f.html LIKE '%<math%' ORDER BY p.paper_n, p.section_n, sn.num").fetchall()
    pieces: dict[str, None] = {}
    for (h,) in db.execute("SELECT html FROM footnote WHERE html LIKE '%<math%'"
                           " UNION ALL SELECT html_hy FROM tr_note WHERE html_hy LIKE '%<math%'"):
        # A figure's labels are boxes in a place drawn for them, not text.
        h = re.sub(r"<svg\b.*?</svg>", "", h, flags=re.S)
        for m in re.findall(r"<math\b.*?</math>", h, flags=re.S):
            pieces[m] = None
    db.close()
    return notes, list(pieces)


# The math font is fetched when a page first draws math: wait for it, or the
# measures are another font's.
FONT = """async () => { const t = document.createElement('p');
    t.innerHTML = '<math><mi>x</mi><mo>+</mo><mn>1</mn></math>'; document.body.appendChild(t);
    await document.fonts.load('16px "Garamond Math"', 'x+1'); await document.fonts.ready; t.remove();
    return [...document.fonts].some(f => /Garamond Math/.test(f.family) && f.status === 'loaded'); }"""

HOST = """(width) => { const h = document.createElement('div'); h.id = 'mhost'; h.className = 'note';
    h.style.cssText = 'position:absolute;left:0;top:0;visibility:hidden;width:' + width + 'px';
    document.body.appendChild(h); }"""

# The width of each row as its <math>.
WIDTHS_OF = """(rows) => { const h = document.getElementById('mhost');
    return rows.map(r => { const p = document.createElement('p'); p.innerHTML = '<math>' + r + '</math>'; h.appendChild(p);
        const w = p.querySelector('math').getBoundingClientRect().width; p.remove(); return w; }); }"""

# Every box of a formula whole and in pieces, from the paragraph's corner:
# the worst difference, in px.
SAME = """(pairs) => { const h = document.getElementById('mhost');
    const boxes = (s) => { const p = document.createElement('p'); p.innerHTML = 'x ' + s + ' y'; h.appendChild(p);
        const o = p.getBoundingClientRect();
        const out = [...p.querySelectorAll('math *')].map(e => { const r = e.getBoundingClientRect();
            return [r.left - o.left, r.top - o.top, r.width, r.height]; });
        out.push([0, 0, 0, o.height]); p.remove(); return out; };
    return pairs.map(([whole, cut]) => { const a = boxes(whole), b = boxes(cut);
        if (a.length !== b.length) return 1e9;
        let worst = 0;
        a.forEach((r, i) => r.forEach((v, k) => { worst = Math.max(worst, Math.abs(v - b[i][k])); }));
        return worst; }); }"""

# A paragraph 300 px wide with the formula in it: how many lines its pieces
# stand on, and how far any runs past the paragraph.
WRAP = """(s) => { const h = document.getElementById('mhost'); const p = document.createElement('p');
    p.style.width = '300px';
    p.innerHTML = 'The worlds of a superuniverse are counted so: ' + s + ' and that is the figure for them all.';
    h.appendChild(p);
    const o = p.getBoundingClientRect(), ms = [...p.querySelectorAll('math')].map(m => m.getBoundingClientRect());
    let lines = 1; ms.forEach((r, i) => { if (i && r.left < ms[i - 1].left) lines++; });
    const past = Math.max(...ms.map(r => r.right)) - o.right; p.remove(); return [lines, past]; }"""

# The open card: its formulas past its text's edges, and whether it scrolls sideways.
CARD = """() => { const pop = document.querySelector('.pop.st'), body = pop.querySelector('.body');
    const cs = getComputedStyle(body), r = body.getBoundingClientRect();
    const left = r.left + parseFloat(cs.paddingLeft), right = r.left + body.clientWidth - parseFloat(cs.paddingRight);
    const ms = [...body.querySelectorAll('math')].filter(m => !m.closest('svg'));
    let past = 0; ms.forEach(m => { const q = m.getBoundingClientRect(); past = Math.max(past, q.right - right, left - q.left); });
    return { n: ms.length, past: past, wide: body.scrollWidth - body.clientWidth, text: right - left,
             last: ms.length ? ms[ms.length - 1].textContent : '' }; }"""

# Each <math> set alone in the open card's own paragraph: its width.
IN_CARD = """(pieces) => { const body = document.querySelector('.pop.st .body');
    const p = document.createElement('p'); p.style.cssText = 'white-space:nowrap;visibility:hidden'; body.appendChild(p);
    const out = pieces.map(s => { p.innerHTML = s; return p.querySelector('math').getBoundingClientRect().width; });
    p.remove(); return out; }"""


def context(b, width: int, phone: bool):
    ctx = b.new_context(viewport={"width": width, "height": 844}, service_workers="block",
                        **({"is_mobile": True, "has_touch": True} if phone else {}))
    # A fresh context is a first visit, which the tour would meet (help.js).
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}")
    return ctx


def table_and_pieces(b) -> None:
    ctx = context(b, 1200, False)
    pg = ctx.new_page()
    pg.goto(BASE + "/11:8")
    ok(pg.evaluate(FONT), "the math font is loaded before anything is measured")
    pg.evaluate(HOST, 20000)

    print("\nThe table of forms against the browser's own dictionary")
    cases = []
    for ch in texmath._FORMS:
        e = html.escape(ch, quote=False)
        st = ' stretchy="false"' if ch in texmath.FENCES else ""
        for placed, row in (("prefix", "{}<mn>1</mn>"), ("infix", "<mn>1</mn>{}<mn>1</mn>"), ("postfix", "<mn>1</mn>{}")):
            form = texmath._form(ch, placed)
            cases.append((ch, placed, form, row.format(f"<mo{st}>{e}</mo>"),
                          row.format(f'<mo{st} form="{form}">{e}</mo>')))
    unsaid = pg.evaluate(WIDTHS_OF, [c[3] for c in cases])
    said = pg.evaluate(WIDTHS_OF, [c[4] for c in cases])
    wrong = [f"{c[0]} placed as a {c[1]} is not the {c[2]} the table says ({u:.2f} px, {s:.2f} stated)"
             for c, u, s in zip(cases, unsaid, said) if abs(u - s) > 0.01]
    ok(not wrong, "%d operators, each first, in the middle and last in a row: the form the table answers"
       " draws what the browser drew unsaid%s" % (len(texmath._FORMS), "".join("\n        " + w for w in wrong)))
    # The check can tell: a wrong form does move something.
    a, c = pg.evaluate(WIDTHS_OF, ['<mn>1</mn><mo form="infix">+</mo><mn>1</mn>', '<mn>1</mn><mo form="prefix">+</mo><mn>1</mn>'])
    ok(a - c > 1, "and a form misstated is seen: a + stated a prefix is %.1f px narrower" % (a - c))

    print("\nA formula in pieces stands where it stood whole")
    rows = formulas()
    pairs = [(ref, tex, texmath.convert(tex), texmath.convert(tex, breaks=True)) for ref, tex in rows]
    cut = [p for p in pairs if p[2] != p[3]]
    ok(all("<wbr/>" not in p[2] for p in pairs), "%d formulas, none broken unless asked" % len(pairs))
    worst = pg.evaluate(SAME, [[p[2], p[3]] for p in cut])
    off = [f"{p[0]} ${p[1]}$: {w:.2f} px" for p, w in zip(cut, worst) if w > 0.01]
    ok(not off, "%d of them with a place to break: in pieces every box is where it was, to 0.01 px (worst %.3f)%s"
       % (len(cut), max(worst), "".join("\n        " + o for o in off)))

    print("\nA line breaks between the pieces")
    longest = max(cut, key=lambda p: len(p[3]))
    whole = pg.evaluate(WRAP, longest[2])
    ok(whole[0] == 1 and whole[1] > 100, "whole, $%s…$ runs %d px past a paragraph 300 px wide" % (longest[1][:24], whole[1]))
    lines, past = pg.evaluate(WRAP, longest[3])
    ok(lines > 1 and past < 0.5, "in pieces it stands on %d lines and inside it" % lines)
    lines, past = pg.evaluate(WRAP, '<span class="nobreak">(' + longest[3] + '),</span>')
    ok(lines > 1 and past < 0.5, "and kept with the punctuation typed against it, in a span that does not wrap, on %d" % lines)
    lines, past = pg.evaluate(WRAP, '<span class="nobreak">(' + longest[3].replace("<wbr/>", "") + '),</span>')
    ok(lines == 1 and past > 100, "which the <wbr/> is for: without it that one runs %d px past" % past)
    ctx.close()


def cards(b, width: int, notes: list[tuple[str, int]], pieces: list[str]) -> None:
    print("\nA phone %d px wide" % width)
    ctx = context(b, width, True)
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    seen, bad, text, at = 0, [], 0.0, None
    for section, num in notes:
        if section != at:
            pg.goto(BASE + "/" + section)
            pg.wait_for_timeout(400)
            if at is None:
                pg.evaluate(FONT)
            at = section
        mark = pg.locator('a.fn[data-k="st"][data-n="%d"]' % num).first
        mark.scroll_into_view_if_needed()
        pg.evaluate("scrollBy(0, 200)")      # the mark in the window's upper half, its card on the screen
        pg.wait_for_timeout(100)
        mark.tap()
        pg.locator(".pop.st").first.wait_for(state="visible", timeout=5000)
        pg.wait_for_timeout(250)
        c = pg.evaluate(CARD)
        seen += c["n"]
        text = c["text"]
        if c["past"] > 0.5 or c["wide"] > 0:
            bad.append("%s note %d: %.0f px past its text, the card %d px too wide" % (section, num, c["past"], c["wide"]))
        if width == WIDTHS[-1] and (section, num) == notes[-1]:
            wide = [(w, p) for w, p in zip(pg.evaluate(IN_CARD, pieces), pieces) if w > text]
            ok(not wide, "no piece of any note's formula, %d of them, is wider than a card's text, %.0f px%s"
               % (len(pieces), text, "".join("\n        %.0f px: %s" % (w, re.sub(r"<[^>]+>", "", p)) for w, p in wide)))
        mark.tap()
        pg.wait_for_timeout(120)
    ok(not bad, "%d cards with a formula, %d <math> in them: each inside its card's text, %.0f px, and no card"
       " scrolls sideways%s" % (len(notes), seen, text, "".join("\n        " + x for x in bad)))
    pg.goto(BASE + "/lists/notes")
    pg.wait_for_timeout(600)
    over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(over <= 0, "the List of study notes does not scroll sideways" + (" (%d px)" % over if over > 0 else ""))
    ok(not errors, "no script error" + ("".join("\n        " + e for e in errors)))
    ctx.close()


def run() -> int:
    notes, pieces = stored()
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        table_and_pieces(b)
        for width in WIDTHS:
            cards(b, width, notes, pieces)
        b.close()
    return 1 if fails else 0


# The server with no offline copy to offer (the manifest a 404), so that no page
# registers the worker and fetches the copy, 48 MB to each fresh context
# (tools/runhead_e2e.py NO_COPY).
NO_COPY = """
import pathlib, sys
import uvicorn
import ubsite.app as A
A.OFFLINE = pathlib.Path(sys.argv[1])
uvicorn.run(A.app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
"""


def main() -> int:
    env = dict(os.environ, UB_VISITS="off")
    srv = subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-c", NO_COPY,
                            str(ROOT / "var" / "no-offline-copy"), PORT], cwd=ROOT, env=env)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(BASE + "/healthz", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        return run()
    finally:
        srv.terminate()
        srv.wait()


if __name__ == "__main__":
    rc = main()
    print("FAILED: " + "; ".join(f.split("\n")[0] for f in fails) if fails else "all good")
    sys.exit(rc)
