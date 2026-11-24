"""The quiz's board, end to end, in Chrome (ubsite/board.py, static/quiz.js;
Tigran, 2026-11-18: each site its own board, and no switch for it in Settings).

Two sites, each the app on a port of its own with a board of its own, as
ubsite.ddns.net and ubsite.sigmaai.au are: Settings has no Quiz board row;
nothing is asked of a board before a quiz ends, and nothing sent before a
name is given; a quiz finished brings the offer, a name joins, and the place
is said; the board's page lists the line, this browser's marked; a later quiz
sends its answers and makes no second offer; the other site's board is its
own, empty, with no file made; a browser that holds a token from another
board (as one that joined from the other site, when one site kept the board
for both) is offered again, and its first answers go with the name, those it
had marked sent among them; a browser that kept the old switch off is offered
all the same; with Quiz off there is no offer, no link and no request; a name
taken on one board is free on the other; and no page asks any site but its
own, of the board or of anything.

    .venv/bin/python tools/quiz_e2e.py        (after make data)

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8141 and :8142 with the visit counter off,
no offline copy, and each board in a temporary directory: it leaves the dev
server and var/quiz.db alone.  Not a gate: tests/test_board.py and
tests/test_quiz.py hold the static facts.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
A, B = "http://127.0.0.1:8141", "http://127.0.0.1:8142"
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def until(pg, js: str, ms: int = 5000) -> bool:
    """Whether `js` comes true within `ms` (polled: CLAUDE.md trap 41)."""
    end = time.time() + ms / 1000
    while time.time() < end:
        if pg.evaluate(js):
            return True
        pg.wait_for_timeout(100)
    return bool(pg.evaluate(js))


# What a reader of English is shown of an element: the interface's words stand
# in both languages (CLAUDE.md trap 33).
SAID = """(sel) => { const el = document.querySelector(sel); if (!el || !el.getClientRects().length) return null;
  const c = el.cloneNode(true); c.querySelectorAll('x-ru').forEach(x => x.remove()); return c.textContent.trim(); }"""
SHOWN = "(sel) => { const el = document.querySelector(sel); return !!el && el.getClientRects().length > 0; }"
KEPT = "() => JSON.parse(localStorage.getItem('ub_quiz') || 'null')"


def fresh(b, seed: str = "", **kw):
    """A first visit, with the tour seen (help.js) and no worker, so that every
    page is the server's; `seed` is run before each page's own scripts."""
    ctx = b.new_context(viewport={"width": 1100, "height": 900}, service_workers="block", **kw)
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); %s } catch (e) {}" % seed)
    asked: list[str] = []
    ctx.on("request", lambda r: asked.append(r.method + " " + r.url))
    return ctx, asked


# Which of the page's questions is asked now: a paper's come in a new order
# each time (quiz.js shuffle), so it is found by its words.
NOW = """() => { const qs = JSON.parse(document.getElementById('ub-quiz').textContent).q,
  t = document.querySelector('.quizrun .qq').textContent, d = document.createElement('div');
  return qs.findIndex(q => { d.innerHTML = q.q; return d.textContent === t; }); }"""


# Each question's answers as last shown, by their places as written (data-k).
SEEN: dict[int, list[int]] = {}


def take(pg, base: str, paper: int, wrong: int = 0, go: bool = True) -> list[int]:
    """A paper's quiz, answered to its score: right, but the first `wrong`
    asked.  The ids in the order asked."""
    if go:
        pg.goto(f"{base}/quiz/{paper}")
    qs = pg.evaluate("() => JSON.parse(document.getElementById('ub-quiz').textContent).q")
    order = []
    for i in range(len(qs)):
        k = pg.evaluate(NOW)
        q = qs[k]
        order.append(q["id"])
        SEEN[q["id"]] = pg.evaluate("() => [...document.querySelectorAll('.quizrun .qopt')].map(b => +b.dataset.k)")
        mask = q["m"]
        if i < wrong:                       # one answer that is not the set
            mask = next(1 << k for k in range(len(q["a"])) if 1 << k != q["m"])
        multi = bin(q["m"]).count("1") > 1
        for k in range(len(q["a"])):
            if mask >> k & 1:
                pg.click(f'.quizrun .qopt[data-k="{k}"]')
        if multi:
            pg.click(".quizrun .qcheck")
        pg.click(".quizrun .qnext")
    pg.wait_for_selector(".quizrun .qbig")
    return order


def board_asks(asked: list[str]) -> list[str]:
    return [a for a in asked if "/quiz/board/" in a]


def lines(base: str) -> list[dict]:
    with urllib.request.urlopen(base + "/quiz/board/lines", timeout=5) as r:
        return json.loads(r.read())["lines"]


def run(tmp: pathlib.Path) -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)

        print("Settings, and a quiz to its end, on the first site")
        ctx, asked = fresh(b)
        pg = ctx.new_page()
        pg.goto(A + "/quiz/32")
        ok(pg.evaluate("() => !document.querySelector('dialog.settings [name=quizboard]') &&"
                       " !!document.querySelector('dialog.settings [name=quiz]')"),
           "Settings has Quiz, and no Quiz board")
        ok("quizboard" not in pg.content().replace("quiz quizboard", ""), "and the page says nothing of such a setting")
        ok(pg.evaluate(SHOWN, ".qtoboard a"), "the link to the board stands under the questions")
        take(pg, A, 32, wrong=1)
        ok(pg.evaluate(SAID, ".qscore p:nth-of-type(2)") == "5 of 6 right", "six answered, one wrong: 5 of 6 right")
        ok(until(pg, "!!document.querySelector('.qjoinbox form.qjoin')"), "the offer follows the score")
        ok(pg.evaluate(SAID, ".qjoin h2") == "Put your name on the board?", "in its words")
        ok(not board_asks(asked), "nothing was asked of a board, or sent, before a name is given")
        ok(not (tmp / "a" / "quiz.db").exists(), "and the site has made no board yet")
        pg.fill("#qname", "Ganid")
        pg.click(".qjoin button[type=submit]")
        ok(until(pg, "!!document.querySelector('.qplace')"), "a name given, the place is said")
        ok(pg.evaluate(SAID, ".qplace") == "Ganid is on the board, in place 1 of 1. See the board", "Ganid, 1 of 1")
        ok(board_asks(asked) == [f"POST {A}/quiz/board/join"], "by one POST, to this site's own board")
        k = pg.evaluate(KEPT)
        ok(bool(k and k.get("token")) and k.get("line") == 1 and len(k["sent"]) == 6 and "pending" not in k,
           "the browser keeps its token and line, and what it has sent")
        token = k["token"]
        ok((tmp / "a" / "quiz.db").exists(), "the first name made the site's board")

        print("the board's page")
        pg.click(".qplace a")
        ok(until(pg, "!!document.querySelector('.boardrun table')"), "See the board goes to it")
        row = pg.evaluate("() => [...document.querySelectorAll('.boardrun tbody tr')].map(tr =>"
                          " [tr.className, ...[...tr.cells].map(c => c.textContent)])")
        ok(row == [["you", "1", "Ganid", "5", "6", "1"]], f"one line, this browser's: Ganid, 5 right of 6, one paper ({row})")
        ok(f"GET {A}/quiz/board/lines" in asked, "read from this site")

        print("a later quiz")
        del asked[:]
        take(pg, A, 33)
        ok(until(pg, "!!document.querySelector('.qplace')"), "its answers go to the board, and the place is said")
        ok(not pg.evaluate(SHOWN, ".qjoin"), "with no second offer")
        ok(board_asks(asked) == [f"POST {A}/quiz/board/answers"], "by one POST of what had not been sent")
        ok(lines(A)[0]["answered"] == 6 + pg.evaluate("() => JSON.parse(document.getElementById('ub-quiz').textContent).count"),
           "which the board has counted")
        ok(not [a for a in asked if not a.split(" ", 1)[1].startswith(A + "/")], "no page asked any site but its own")
        ctx.close()

        print("the other site: a board of its own")
        ok(lines(B) == [], "its lines are its own: none")
        ok(not (tmp / "b" / "quiz.db").exists(), "and it has made no file for the asking")
        ctx, asked = fresh(b)
        pg = ctx.new_page()
        pg.goto(B + "/quiz/board")
        ok(until(pg, "!!document.querySelector('.boardrun p:not(.qwait)')") and
           pg.evaluate(SAID, ".boardrun p") == "No one is on the board yet.", "its page says no one is on it yet")
        ctx.close()

        print("a browser on the board the other site kept, come to this one")
        # As ubsite.ddns.net's readers are who joined while ubsite.sigmaai.au
        # kept the one board: a token this board has never had, and every first
        # answer marked sent.
        seed = ("if (!localStorage.getItem('ub_quiz')) localStorage.setItem('ub_quiz', JSON.stringify({v: 1, best: {},"
                " first: {'366.1': 2, '367.1': 7, '368.1': 8}, sent: {'366.1': 1, '367.1': 1, '368.1': 1},"
                " token: '%s', line: 1, name: 'Ganid'}));" % token)
        ctx, asked = fresh(b, seed)
        pg = ctx.new_page()
        take(pg, B, 33)
        ok(until(pg, "!!document.querySelector('.qjoinbox form.qjoin')"), "the board does not know it: offered again")
        k = pg.evaluate(KEPT)
        ok("token" not in k and "line" not in k and k["sent"] == {}, "its token forgotten, and nothing counted as sent")
        ok([a.split("/quiz/board/")[1] for a in board_asks(asked)] == ["answers"] and
           not (tmp / "b" / "quiz.db").exists(), "after one POST, which made nothing")
        pg.fill("#qname", "Ganid")
        pg.click(".qjoin button[type=submit]")
        ok(until(pg, "!!document.querySelector('.qplace')") and
           pg.evaluate(SAID, ".qplace") == "Ganid is on the board, in place 1 of 1. See the board",
           "the same name is free here, and joins: 1 of 1")
        got = lines(B)
        ok(len(got) == 1 and got[0]["answered"] == 4 and got[0]["right"] == 4,
           f"with every first answer the browser keeps, the three it had marked sent too ({got})")
        ok(not [a for a in asked if not a.split(" ", 1)[1].startswith(B + "/")], "no page asked any site but its own")
        ok(len(lines(A)) == 1 and lines(A)[0]["answered"] == 7, "and the first site's board is as it was")
        ctx.close()

        print("a browser that kept the old switch off")
        ctx, asked = fresh(b, "localStorage.setItem('ub_settings', JSON.stringify({quizboard: false}));")
        pg = ctx.new_page()
        take(pg, A, 33)
        ok(until(pg, "!!document.querySelector('.qjoinbox form.qjoin')") and pg.evaluate(SHOWN, ".qjoin"),
           "is offered all the same")
        ok(pg.evaluate("() => !('quizboard' in document.documentElement.dataset)"), "the key being no setting")
        ok(pg.evaluate(SHOWN, ".qtoboard a"), "and has the link to the board")
        ok(not board_asks(asked), "nothing sent for the offer left unanswered")
        pg.fill("#qname", "ganid")
        pg.click(".qjoin button[type=submit]")
        ok(until(pg, "!!document.querySelector('.qjoin .qmsg').textContent") and
           pg.evaluate(SAID, ".qjoin .qmsg") == "That name is taken: choose another.", "a name taken on this board is refused")
        ctx.close()

        print("a paper's questions in a new order each time")
        ctx, asked = fresh(b, "localStorage.setItem('ub_settings', JSON.stringify({quiz: false}));")
        pg = ctx.new_page()
        first = take(pg, A, 1, wrong=3)
        page = [q["id"] for q in pg.evaluate("() => JSON.parse(document.getElementById('ub-quiz').textContent).q")]
        ok(sorted(first) == sorted(page) and len(first) == 29, "Paper 1's 29 questions, each asked once")
        ok(first != page, "not in the page's order")
        missed = pg.evaluate("() => [...document.querySelectorAll('.qmissed li span')].map(s => s.textContent)")
        texts = pg.evaluate("""(ids) => { const qs = JSON.parse(document.getElementById('ub-quiz').textContent).q,
          d = document.createElement('div');
          return ids.map(i => { d.innerHTML = qs.find(q => q.id === i).q; return d.textContent; }); }""",
                            [i for i in page if i in first[:3]])
        ok(missed == texts, "the three missed, to read again in the page's order, not the order asked")
        pg.click(".quizrun .qagain")
        second = take(pg, A, 1, go=False)
        ok(sorted(second) == sorted(page) and second != first, "Again: the same questions, in another order")
        shuffled = [i for i in page if SEEN[i] != sorted(SEEN[i])]
        ok(len(shuffled) >= 20, f"and their answers shuffled: {len(shuffled)} of 29 shown out of their written order")
        ok(all(sorted(SEEN[i]) == list(range(len(SEEN[i]))) for i in page), "each answer shown once")
        take(pg, A, 0)
        qs0 = pg.evaluate("() => JSON.parse(document.getElementById('ub-quiz').textContent).q")
        fixed = [q["id"] for q in qs0 if q.get("f")]
        ok(fixed and all(SEEN[i] == list(range(len(SEEN[i]))) for i in fixed),
           f"the Foreword's {len(fixed)} whose order means something (yes and no, rising numbers) as written")
        pg.click(".quizrun .qagain")
        q = qs0[pg.evaluate(NOW)]
        first_shown = pg.evaluate("() => +document.querySelector('.quizrun .qopt').dataset.k")
        pg.keyboard.press("1")
        got = pg.evaluate("""() => { const b = document.querySelector('.quizrun .qopt');
          return b.getAttribute('aria-pressed') === 'true' || b.classList.contains('ok') || b.classList.contains('bad'); }""")
        ok(got, f"the key 1 chooses the first answer shown, its place as written {first_shown}")
        ctx.close()

        print("Quiz off")
        ctx, asked = fresh(b, "localStorage.setItem('ub_settings', JSON.stringify({quiz: false}));")
        pg = ctx.new_page()
        take(pg, A, 33)
        pg.wait_for_timeout(600)
        ok(not pg.evaluate("() => !!document.querySelector('.qjoinbox')"), "a quiz asked for by its address ends with no offer")
        ok(not pg.evaluate(SHOWN, ".qtoboard"), "no link to the board")
        ok(not board_asks(asked), "and nothing asked of it")
        ctx.close()

        print("in Russian")
        ctx, asked = fresh(b, "localStorage.setItem('ub_settings', JSON.stringify({lang: 'ru'}));")
        pg = ctx.new_page()
        pg.set_viewport_size({"width": 320, "height": 700})
        take(pg, A, 33)
        ok(until(pg, "!!document.querySelector('.qjoinbox form.qjoin')"), "the offer, on a phone of 320 px")
        ok(pg.evaluate("() => [...document.querySelectorAll('.qjoin h2 x-ru')].some(x => x.getClientRects().length)"
                       " && ![...document.querySelectorAll('.qjoin h2 x-en')].some(x => x.getClientRects().length)"),
           "in Russian")
        ok(pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"),
           "and no wider than the window")
        ctx.close()
        b.close()
    return 1 if fails else 0


SERVE = """
import pathlib, sys
import uvicorn
import ubsite.app as A
A.OFFLINE = pathlib.Path(sys.argv[1])
uvicorn.run(A.app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        servers = []
        try:
            for name, base in (("a", A), ("b", B)):
                # Each site's board beside it, as var/quiz.db is on a host.
                env = dict(os.environ, UB_VISITS="off", UB_MEANING="off", UB_BOARD_DB=str(tmp / name / "quiz.db"))
                servers.append(subprocess.Popen(
                    [str(ROOT / ".venv" / "bin" / "python"), "-c", SERVE, str(ROOT / "var" / "no-offline-copy"),
                     base.rsplit(":", 1)[1]], cwd=ROOT, env=env))
            for base in (A, B):
                for _ in range(100):
                    try:
                        urllib.request.urlopen(base + "/healthz", timeout=1)
                        break
                    except OSError:
                        time.sleep(0.2)
            return run(tmp)
        finally:
            for s in servers:
                s.terminate()
                s.wait()


if __name__ == "__main__":
    rc = main()
    print("FAILED: " + "; ".join(fails) if fails else "all good")
    sys.exit(rc)
