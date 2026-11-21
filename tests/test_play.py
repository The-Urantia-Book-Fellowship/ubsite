"""A paragraph's ▶ and the time beside it (Tigran, 2026-11-17: "for the blue
play triangle button we give quite a lot of space, but the button itself is
quite small", and of the room to its right, "maybe you can think of something
to utilise that bit of space"; his choice, the triangle larger, the whole
line a button, with the paragraph's reading time).

The time is the recording's, from where the ▶ starts to the paragraph's end,
at the speed chosen; listen.js puts it on the button as an attribute and the
stylesheet draws it, as the 1955 page is drawn, so that the button has no
text and a copy of the paragraph never takes it (CLAUDE.md §6).  These hold
the static facts, and that Help's example carries what a page would show;
tools/play_e2e.py drives it in Chrome, and is not a gate.
"""

import re
import sqlite3
import unittest

from test_appendix_pages import DB, ROOT, get

CSS = (ROOT / "ubsite" / "static" / "ub.css").read_text()
LISTEN = (ROOT / "ubsite" / "static" / "listen.js").read_text()
WIDE = ':root:not([data-paranum="off"], [data-pages="true"])'


class PlayButton(unittest.TestCase):
    def test_the_time_is_an_attribute_and_never_text(self):
        place = LISTEN[LISTEN.index("function place(p, i, label, to) {"):LISTEN.index("// A paragraph can be started only once")]
        self.assertIn("for (var ms = 0, j = i; to >= i && j <= to; j++) ms += (PV.segs[j][3] - PV.segs[j][2]) || 0;", place)
        self.assertIn("if (ms > 0) { pb.dataset.ms = ms; pb.dataset.t = clock(ms); }", place)
        for text in ("textContent", "innerHTML", "createTextNode", "appendChild(document"):
            self.assertNotIn(text, place)
        self.assertIn(WIDE + " .stk > .playp[data-t]::after { content: attr(data-t);", CSS)

    def test_a_sections_first_counts_its_heading(self):
        # Its ▶ starts at the heading, i - 1, and the time runs to its own end, i.
        self.assertIn("place(p, i - 1, T.k('Listen to this section, from its heading'), i);", LISTEN)
        self.assertIn("else place(p, i, T.tr('Listen from {r}', { r: s[0] }), i);", LISTEN)
        # A reading not cut at the paragraph has none.
        self.assertIn("if (p0) place(p0, 0, T.k('Listen to this section'));", LISTEN)

    def test_it_follows_the_speed(self):
        self.assertIn("var n = Math.max(1, Math.round(ms / rate() / 1000));", LISTEN)
        self.assertIn("return (n >= 3600 ? Math.floor(n / 3600) + ':' + ('0' + Math.floor(n / 60) % 60).slice(-2)\n"
                      "                      : Math.floor(n / 60)) + ':' + ('0' + n % 60).slice(-2);", LISTEN)
        rate = LISTEN[LISTEN.index("if (what === 'rate') {"):LISTEN.index("// A translation's voice changed while it is heard")]
        # The bar's time left with it (drawLeft, by render; a phone's, 2026-11-21).
        self.assertIn("render();", rate)
        self.assertIn("    drawKeep();\n    drawLeft();\n", LISTEN[LISTEN.index("function render() {"):])
        self.assertIn("var c = clock(ms), wide = ", LISTEN[LISTEN.index("function drawLeft() {"):])
        # The first text's too, where a recording reads it (trPlay, 2026-11-20).
        self.assertIn("controls.concat(trTimes).forEach(function (c) { if (c.dataset.ms) c.dataset.t = clock(+c.dataset.ms); });", rate)

    def test_a_translations_has_none(self):
        # trButton makes the button alone: its time is timed()'s, given where
        # it stands, in a column (trPlay) and in the fold (foldPlay, since
        # 2026-11-21), and only where a recording reads the text.
        tr = LISTEN[LISTEN.index("function trButton(t, line) {"):LISTEN.index("// The first texts' buttons with a time")]
        self.assertNotIn("dataset.t", tr)
        self.assertNotIn("clock(", tr)
        timed = LISTEN[LISTEN.index("function timed(b, t, ref) {"):LISTEN.index("// In Compare, in each of its cells")]
        self.assertIn("(PV && PV.kind !== 'browser' ? PV : null) : RECS[kk] ? voiceOf(P, kk) : null;", timed)
        self.assertIn("timed(b, q.dataset.k, q.dataset.ref);", LISTEN[LISTEN.index("function trPlay(root) {"):])
        self.assertIn("timed(b, t, line.dataset.ref);", LISTEN[LISTEN.index("function foldPlay(panel) {"):])

    def test_the_triangle_is_larger_and_alone_faint(self):
        self.assertIn(".playp svg { width: 1.1rem; height: 1.1rem; opacity: .45; transition: opacity .15s; }", CSS)
        base = re.search(r"\n\.playp \{([^}]*)\}", CSS).group(1)
        self.assertIn("width: 1.4rem; height: 1.4rem;", base)
        self.assertNotIn("opacity", base)
        # Nothing dims the button itself: the time in it is the reference's grey.
        for rule in re.findall(r"[^{}\n]*\.playp[^{}]*\{[^}]*opacity[^}]*\}", CSS):
            self.assertRegex(rule.split("{")[0], r"\.playp[^,{]*svg\s*(,|$)", rule)

    def test_the_whole_line_is_the_button(self):
        m = re.search(re.escape(WIDE) + r" p\.t:not\(\.opening, \.verse\) \.stk > \.playp \{([^}]*)\}", CSS)
        self.assertIsNotNone(m)
        for decl in ("width: calc(100% + .375rem);", "height: var(--lh);", "margin: 0 0 0 -.375rem;",
                     "justify-content: space-between;"):
            self.assertIn(decl, m.group(1))

    def test_the_time_is_set_as_the_reference_is(self):
        m = re.search(re.escape(WIDE) + r" \.stk > \.playp\[data-t\]::after \{([^}]*)\}", CSS)
        for decl in ("color: var(--faint);", "white-space: nowrap;", "font-variant-numeric: lining-nums tabular-nums;"):
            self.assertIn(decl, m.group(1))
        # On the line's baseline as the 1955 page stands on it.
        self.assertIn(WIDE + " p.t:not(.opening, .verse) .stk > .playp::after {\n"
                      "  align-self: flex-start; position: relative; top: calc(.2rem + var(--ref)); }", CSS)
        self.assertIn(':root[data-pages="true"] .pg { display: block; position: relative; top: calc(.2rem + var(--ref));', CSS)

    def test_room_under_the_shortest_references(self):
        self.assertIn(':root:not([data-pages="true"]) main:has(.playp[data-t]) p.t:not(.opening, .verse) .num {\n'
                      "  min-width: max(calc(var(--refw, 9) * 1ch + .4rem), 2.9rem); }", CSS)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class HelpExample(unittest.TestCase):
    def test_play_times_are_the_recordings(self):
        from ubsite import app
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        sid = con.execute("SELECT id FROM section WHERE paper_n=101 AND n=4").fetchone()[0]
        got = app.play_times(app.section_audio(con, sid))
        rows = con.execute(
            "SELECT p.ref, g.end_ms - g.start_ms FROM audio_segment g JOIN audio_source s ON s.id=g.source_id"
            " LEFT JOIN paragraph p ON p.id=g.paragraph_id WHERE s.key='mh' AND g.section_id=? ORDER BY g.ord", (sid,)).fetchall()
        want, head = {}, 0
        for ref, ms in rows:
            if ref is None:
                head = ms
                continue
            n = max(1, int((ms + head) / 1000 + .5))
            want[ref], head = f"{n // 60}:{n % 60:02d}", 0
        self.assertEqual(len(want), 10)
        self.assertEqual(got, want)
        self.assertRegex(got["101:4.1"], r"^\d:\d\d$")

    def test_help_draws_it_in_its_example(self):
        body = get("/help", raw=True)[2]
        m = re.search(r'<span class="stk"><span class="num">(\d+:\d+\.\d+)</span><span class="playp" aria-hidden="true" data-t="(\d:\d\d)">', body)
        self.assertIsNotNone(m)
        from ubsite import app
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        paper, sec = app.HELP_EXAMPLE
        sid = con.execute("SELECT id FROM section WHERE paper_n=? AND n=?", (paper, sec)).fetchone()[0]
        self.assertEqual(m.group(2), app.play_times(app.section_audio(con, sid))[m.group(1)])
        # And says what the figures are, in both languages.
        from ubsite import l10n
        words = l10n.catalog()["help:text:1"]
        self.assertIn("the figures beside it", words["en"])
        self.assertIn("цифры рядом", words["ru"])


if __name__ == "__main__":
    unittest.main()
