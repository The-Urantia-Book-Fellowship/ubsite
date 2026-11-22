"""Unit conversions and the charts, in Chrome (templates/units.html,
static/units.js, templates/charts.html; DECISIONS.md, Unit conversions).

    .venv/bin/python tools/units_e2e.py

Not a gate: it needs Chrome.  It runs the app itself on 127.0.0.1:8143 with
the visit counter off and no offline copy to offer.

  both directions: a number typed in any row of a table, the papers' unit or
  a familiar one, writes every other row of it, each as the server writes
  that value (queries.unit_number), the row typed in tinted, the address
  naming it; the time in Urantia years, days, hours, minutes and seconds;
  what is no number marked and changing nothing; a row left written as the
  rest are;

  in Russian: a number typed with a narrow space and a decimal comma, the
  values written so, and written again in English when the language changes;

  the examples from the text: a tap puts the figure in its table and lights
  the row the book gives it in too, with Whole paper off and on; an address
  naming a unit and a value opens the table so, with the row in view; the
  paragraph's link goes to the paragraph, and with Paragraph previews on the
  mouse resting on it shows the paragraph in a card;

  no page wider than its window, and no value wider than its field, at 320,
  390, 836 and 1280 px, in both languages, at the four Interface text sizes;

  a <main> brought in as listen.js brings one while it plays: its script
  loaded by ub.js, and the table working;

  /charts: the chart's line first, with its credit, then Unit conversions;
  the home page's tile goes there.
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ubsite.queries import unit_number      # noqa: E402

PORT = 8143
BASE = f"http://127.0.0.1:{PORT}"
CHROME = "/usr/bin/google-chrome"
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


SEEN = "try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_install', 'no'); } catch (e) {}"
VALUES = """(g) => Object.fromEntries([...document.querySelectorAll('section[data-g="' + g + '"] tr[data-u]')]
  .map(t => [t.dataset.u, t.querySelector('input').value]))"""
SRC = "() => [...document.querySelectorAll('tr.ucsrc')].map(t => t.dataset.u)"
OVER = """() => ({page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  fields: [...document.querySelectorAll('tr[data-u] input')].filter(i => i.scrollWidth > i.clientWidth + 1).map(i => i.closest('tr').dataset.u + ' ' + i.value)})"""


def fresh(b, w=1280, h=900, settings=None):
    ctx = b.new_context(viewport={"width": w, "height": h}, service_workers="block")
    ctx.add_init_script(SEEN + (" try { localStorage.setItem('ub_settings', %s); } catch (e) {}"
                                % json.dumps(json.dumps(settings)) if settings else ""))
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    return ctx, pg


def mid(loc):
    """A click at the middle of a link's box: Playwright clicks a link of
    several boxes in its first, here the opening quote's, which hangs out
    of it."""
    loc.scroll_into_view_if_needed()
    box = loc.bounding_box()
    loc.click(position={"x": box["width"] / 2, "y": box["height"] / 2})


def sizes() -> dict:
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    return {k: (g, s, o) for k, g, s, o in con.execute("SELECT key, group_key, scale, offset FROM unit")}


def expect(U, k, v, lang="en") -> dict:
    g, s, o = U[k]
    base = (v + o) * s
    return {u: unit_number(v if u == k else base / su - ou, lang) for u, (gu, su, ou) in U.items() if gu == g}


def run() -> int:
    U = sizes()
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)

        print("both directions, in English")
        ctx, pg = fresh(b)
        pg.goto(BASE + "/units")
        pg.wait_for_function("() => window.ubUnits")
        ok(pg.evaluate(VALUES, "time") == expect(U, "phday", 1), "the time opens at one Paradise-Havona day, every row as the server writes it")
        ok(pg.evaluate(SRC) == ["phday", "jmile", "vlimit", "gradant", "fahrenheit"], "each table's opening row is its source")
        for k, v, typed, at in (("jday", 3, "3", "3"), ("year", 1, "1", "1"), ("second", 1e9, "1e9", "1000000000"),
                                ("uvday", 2.5, "2.5", "2.5")):
            pg.locator(f'tr[data-u="{k}"] input').fill(typed)
            # The row typed in keeps what was typed, until it is left.
            ok(pg.evaluate(VALUES, "time") == {**expect(U, k, v), k: typed}, f"{typed} typed as {k}: every other row follows")
            ok(pg.evaluate("location.hash") == f"#{k}={at}", f"and the address names it, #{k}={at}")
        pg.locator('tr[data-u="jday"] input').fill("3")
        ok(pg.evaluate("document.querySelector('.ucut').innerText")
           == "In Urantia time: 8 days, 20 hours, 47 minutes, 15 seconds", "three Jerusem days in Urantia time")
        ok(pg.evaluate(SRC)[0] == "jday", "the row typed in is the source")
        pg.locator('tr[data-u="phday"] input').fill("1")
        ok(pg.evaluate("document.querySelector('.ucut').innerText")
           == "In Urantia time: 999 years, 365 days, 5 hours, 52 minutes, 56.875 seconds",
           "a Paradise-Havona day: 3⅛ seconds short of the next minute, as 14:1.12 says")
        before = pg.evaluate(VALUES, "time")
        pg.locator('tr[data-u="hour"] input').fill("abc")
        ok(pg.locator('tr[data-u="hour"] input').get_attribute("aria-invalid") == "true", "what is no number is marked")
        after = pg.evaluate(VALUES, "time")
        ok({k: v for k, v in after.items() if k != "hour"} == {k: v for k, v in before.items() if k != "hour"},
           "and changes nothing")
        pg.locator('tr[data-u="mile"] input').fill("1000.50")
        ok(pg.evaluate(VALUES, "distance") == {**expect(U, "mile", 1000.5), "mile": "1000.50"},
           "a mile row typed in: the distances follow")
        pg.locator('tr[data-u="mile"] input').press("Enter")
        ok(pg.locator('tr[data-u="mile"] input').input_value() == "1,000.5", "left, it is written as the rest are")
        pg.locator('tr[data-u="kelvin"] input').fill("-1")
        ok(pg.locator('tr[data-u="kelvin"] input').get_attribute("aria-invalid") == "true", "nothing colder than absolute zero")
        pg.locator('tr[data-u="celsius"] input').fill("-40")
        ok(pg.locator('tr[data-u="fahrenheit"] input').input_value() == "−40", "−40 °C is −40 °F")
        pg.locator('tr[data-u="parsec"] input').fill("1")
        ok(pg.locator('tr[data-u="inch"] input').input_value() == unit_number(U["parsec"][1] / U["inch"][1], "en")
           and "× 10^" in pg.locator('tr[data-u="inch"] input').input_value(), "a parsec in inches, as a power of ten")
        pg.locator('tr[data-u="inch"] input').fill(pg.locator('tr[data-u="inch"] input').input_value())
        ok(abs(float(pg.locator('tr[data-u="parsec"] input').input_value()) - 1) < 1e-9, "and read back as written")
        pg.locator('tr[data-u="inch"] input').fill("1.2148336935 × 10⁻³")
        ok(pg.locator('tr[data-u="inch"] input').get_attribute("aria-invalid") is None
           and pg.locator('tr[data-u="mile"] input').input_value() == unit_number(1.2148336935e-3 * U["inch"][1] / U["mile"][1], "en"),
           "and a power of ten as pasted from elsewhere, 10⁻³")
        ok(not pg.errors, "no error: " + "; ".join(pg.errors))
        ctx.close()

        print("in Russian")
        ctx, pg = fresh(b, 390, 800, {"lang": "ru"})
        pg.goto(BASE + "/units")
        pg.wait_for_function("() => window.ubUnits")
        ok(pg.evaluate(VALUES, "time") == expect(U, "phday", 1, "ru"), "the values as Russian writes them")
        pg.locator('tr[data-u="mile"] input').fill("1 000,5")
        ok(pg.evaluate(VALUES, "distance") == {**expect(U, "mile", 1000.5, "ru"), "mile": "1 000,5"},
           "1 000,5 miles typed: the distances follow")
        pg.locator('tr[data-u="mile"] input').fill("1 000,5")
        ok(pg.evaluate(VALUES, "distance") == {**expect(U, "mile", 1000.5, "ru"), "mile": "1 000,5"},
           "and with an ordinary space")
        pg.locator('tr[data-u="mile"] input').press("Enter")
        ok(pg.locator('tr[data-u="mile"] input').input_value() == "1000,5", "left, written as Russian writes it")
        pg.locator('tr[data-u="jday"] input').fill("3")
        ok(pg.evaluate("document.querySelector('.ucut').innerText")
           == "По урантийскому времени: 8 дней, 20 часов, 47 минут, 15 секунд", "the time in Urantia time, in Russian")
        pg.evaluate("window.ubSettings.set('lang', 'en')")
        pg.wait_for_timeout(100)
        ok(pg.evaluate(VALUES, "distance") == expect(U, "mile", 1000.5, "en"), "the language turned: written in English")
        ok(not pg.errors, "no error: " + "; ".join(pg.errors))
        ctx.close()

        print("examples, addresses, references")
        for whole in (False, True):
            say = " (Whole paper on)" if whole else ""
            ctx, pg = fresh(b, 1280, 900, {"whole": True} if whole else None)
            pg.goto(BASE + "/units")
            pg.wait_for_function("() => window.ubUnits")
            mid(pg.locator('a.ucgo[href="#sysyear=25000"]'))
            v = pg.evaluate(VALUES, "time")
            ok(v["sysyear"] == "25,000" and v["year"] == unit_number(25000 * U["sysyear"][1] / U["year"][1], "en"),
               "54:6.6's twenty-five thousand years of system time: " + v["year"] + " Urantia years" + say)
            ok(pg.evaluate("document.querySelector('tr.ucto') && document.querySelector('tr.ucto').dataset.u") == "year",
               "the row the book gives it in is lit" + say)
            ok(pg.evaluate("location.pathname + location.hash") == "/units#sysyear=25000", "the address names it" + say)
            mid(pg.locator('a.ucgo[href="#fahrenheit=6000"]'))
            ok(pg.locator('tr[data-u="fahrenheit"] input').input_value() == "6,000", "the sun's surface, 6,000 °F" + say)
            with pg.expect_navigation():
                pg.locator('tr[data-u="jmile"] .ucdef a').click()
            ok(pg.evaluate("location.pathname + location.hash") in ("/46:1.2", "/46#46:1.2"),
               "the paragraph's link goes there: " + pg.evaluate("location.pathname + location.hash") + say)
            ok(not pg.errors, "no error" + say + ": " + "; ".join(pg.errors))
            ctx.close()
        ctx, pg = fresh(b, 390, 700)
        pg.goto(BASE + "/units#nbyear=10000")
        pg.wait_for_function("() => window.ubUnits")
        pg.wait_for_timeout(300)
        r = pg.evaluate("(() => { const r = document.querySelector('tr[data-u=\"nbyear\"]').getBoundingClientRect(); return [r.top, r.bottom, innerHeight]; })()")
        ok(pg.locator('tr[data-u="nbyear"] input').input_value() == "10,000" and 0 <= r[0] and r[1] <= r[2],
           "opened at #nbyear=10000: the table so, the row in view")
        ok(pg.evaluate(VALUES, "time")["year"] == unit_number(10000 * U["nbyear"][1] / U["year"][1], "en"),
           "43:3.2's ten thousand standard years: about 50,000 Urantia years")
        ctx.close()
        ctx, pg = fresh(b, 1280, 900, {"preview": True})
        pg.goto(BASE + "/units")
        pg.wait_for_function("() => window.ubUnits")
        pg.locator('tr[data-u="gradant"] .ucdef a').hover()
        pg.wait_for_timeout(800)
        ok(pg.evaluate("(document.querySelector('.pop.pv .pvref a') || {}).textContent") == "46:1.2"
           and pg.evaluate("location.pathname") == "/units",
           "with Paragraph previews on, the mouse resting on the reference shows its paragraph in a card")
        ctx.close()

        print("widths, languages, sizes")
        for lang in ("en", "ru"):
            for w in (320, 390, 836, 1280):
                for size in ("90", "100", "112.5", "125"):
                    ctx, pg = fresh(b, w, 800, {"lang": lang, "uisize": size})
                    pg.goto(BASE + "/units#parsec=1")
                    pg.wait_for_function("() => window.ubUnits")
                    pg.locator('tr[data-u="vsolitary"] input').fill("1")
                    pg.locator('tr[data-u="ton"] input').fill("2e27")
                    o = pg.evaluate(OVER)
                    ok(o["page"] <= 0 and not o["fields"],
                       f"{lang} {w} px, {size}%: no page wider than the window, no value wider than its field"
                       + (f" ({o})" if o["page"] > 0 or o["fields"] else ""))
                    ctx.close()

        print("brought in as listen.js brings a page")
        ctx, pg = fresh(b)
        pg.goto(BASE + "/lists")
        pg.evaluate("""() => fetch('/units').then(r => r.text()).then(h => {
            const doc = new DOMParser().parseFromString(h, 'text/html');
            document.querySelector('main').replaceWith(document.adoptNode(doc.querySelector('main')));
            history.pushState({}, '', '/units');
            document.dispatchEvent(new CustomEvent('ub:swap')); })""")
        pg.wait_for_function("() => window.ubUnits")
        pg.locator('tr[data-u="jday"] input').fill("3")
        ok(pg.evaluate(VALUES, "time") == expect(U, "jday", 3), "its script loaded by ub.js, and the table works")
        ok(not pg.errors, "no error: " + "; ".join(pg.errors))
        ctx.close()

        print("the charts")
        ctx, pg = fresh(b)
        pg.goto(BASE + "/")
        with pg.expect_navigation():
            pg.locator('ul.ftiles a[href="/charts"]').click()
        hrefs = pg.evaluate("[...document.querySelectorAll('main.charts a.minicard')].map(a => a.getAttribute('href'))")
        ok(pg.evaluate("location.pathname") == "/charts", "the home page's tile goes to /charts")
        ok(hrefs[:1] == ["/cosmology"] and "/units" in hrefs, f"the chart first, then Unit conversions: {hrefs}")
        ok("Data source by Alexander Alyuev" in pg.evaluate("document.querySelector('main.charts').innerText"),
           "the chart's credit as ruled")
        ok(pg.evaluate("[...document.querySelectorAll('.minipic')].every(s => { const r = s.getBoundingClientRect(); return r.width > 300 && Math.abs(r.width / r.height - 1.6) < .02; })"),
           "each card's picture 16:10, over 300 px wide")
        with pg.expect_navigation():
            pg.locator('a.minicard[href="/units"] .minipic').click()
        ok(pg.evaluate("location.pathname") == "/units", "a click on the calculator's picture goes there")
        ctx.close()
        for w, lang, theme in ((390, "en", "light"), (320, "ru", "dark"), (836, "ru", "light")):
            ctx, pg = fresh(b, w, 800, {"lang": lang, "theme": theme})
            pg.goto(BASE + "/charts")
            pg.wait_for_timeout(300)
            r = pg.evaluate("""() => ({over: document.documentElement.scrollWidth - document.documentElement.clientWidth,
              cols: new Set([...document.querySelectorAll('.minicard')].map(a => Math.round(a.getBoundingClientRect().left))).size,
              ru: [...document.querySelectorAll('.minipic text')].filter(t => t.getClientRects().length).map(t => t.textContent)})""")
            want = 2 if w >= 640 else 1
            # Russian: a decimal comma and no point; English: a point, and no narrow space.
            nums = r["ru"]
            as_lang = (all("." not in x for x in nums) and any("," in x for x in nums)) if lang == "ru" \
                else (all("\u202f" not in x for x in nums) and any("." in x for x in nums))
            ok(r["over"] <= 0 and r["cols"] == want and nums and as_lang,
               f"/charts at {w} px, {lang}, {theme}: no sideways scroll, {want} to a row, the numbers as {lang} writes them")
            ctx.close()
        b.close()
    return 1 if fails else 0


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
                            str(ROOT / "var" / "no-offline-copy"), str(PORT)], cwd=ROOT, env=env)
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
    print("FAILED: " + "; ".join(fails) if fails else "all good")
    sys.exit(rc)
