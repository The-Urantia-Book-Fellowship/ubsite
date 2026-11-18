"""The home page's passage of the moment, the offer to install the site as an
app, and the offline copy's state on the home page's bar (Tigran's design of
2026-11-17, its third and fourth steps; DECISIONS.md, The home page).

The passages are data/passages.tsv, a list he reviews, held by the build to
the text (build/passage.py); the page carries them all and a line of script
shows one.  The banner and the bar's state are the shell's, the same in every
page and in the offline copy, shown by the stylesheet on the home page alone
and filled by script.  These hold the static facts; Chrome is driven through
them by tools/front_e2e.py and tools/offline_e2e.py, which are not gates.
Rendered through the app as ASGI, as test_appendix_pages does.
"""

import importlib.util
import json
import re
import sqlite3
import subprocess
import unittest

from test_appendix_pages import DB, ROOT, get

from build import passage

CSS = (ROOT / "ubsite" / "static" / "ub.css").read_text(encoding="utf-8")
JS = (ROOT / "ubsite" / "static" / "ub.js").read_text(encoding="utf-8")
OFF = (ROOT / "ubsite" / "static" / "offline.js").read_text(encoding="utf-8")
BASE = (ROOT / "ubsite" / "templates" / "base.html").read_text(encoding="utf-8")
TEXT = ("3. The weak indulge in resolutions, but the strong act. Life is but a day’s work—do it well. "
        "He said: “Fear not. I am with you.” And they went on, for the road was long.")


class TheWords(unittest.TestCase):
    """What the build takes for a passage: whole sentences of one paragraph."""

    def at(self, words):
        return passage.anchor(TEXT, words)

    def test_whole_sentences_are_taken(self):
        self.assertEqual(self.at("The weak indulge in resolutions, but the strong act.")[0], 3)
        self.assertIsNotNone(self.at("Life is but a day’s work—do it well.")[0])
        # After a list's label, and after the mark that opens a quotation; and
        # the mark that closes it may be left out, or kept.
        self.assertIsNotNone(self.at("Fear not. I am with you.")[0])
        self.assertIsNotNone(self.at("Fear not. I am with you.”")[0])
        self.assertIsNotNone(self.at("I am with you.")[0])

    def test_the_middle_of_a_sentence_is_refused(self):
        for words, why in (("but the strong act.", "begin a sentence"), ("The weak indulge in resolutions", "end a sentence"),
                           ("Fear not. I am", "end a sentence"), ("And they went on,", "end a sentence"),
                           ("The strong act.", "not in the paragraph"), (" Fear not.", "space"),
                           ("I am with you.” And they went on, for the road was long", "end a sentence")):
            with self.subTest(words=words):
                at, said = self.at(words)
                self.assertIsNone(at)
                self.assertIn(why, said)

    def test_words_that_occur_twice_are_refused(self):
        self.assertIn("more than once", passage.anchor("It is so. It is so.", "It is so.")[1])


@unittest.skipUnless(DB.exists(), "var/ub.db has not been built")
class TheList(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    def test_the_database_holds_the_list_and_each_is_its_paragraph_s_words(self):
        listed = [(ref, q) for _, ref, q, _ in passage.rows()]
        rows = self.con.execute("SELECT x.ref, x.text, x.html, x.start, p.text, x.title, g.title FROM passage x"
                                " JOIN paragraph p ON p.id = x.paragraph_id JOIN paper g ON g.n = x.paper_n ORDER BY x.n").fetchall()
        self.assertEqual(len(rows), len(listed), "var/ub.db is older than data/passages.tsv")
        for (ref, text, html, start, para, title, paper), (lref, quote) in zip(rows, listed):
            with self.subTest(ref=ref):
                self.assertEqual(ref, lref)
                self.assertEqual(para[start:start + len(text)], text)
                self.assertEqual(text, para if quote == "¶" else quote)
                self.assertEqual(re.sub(r"<[^>]+>", "", html).replace("&amp;", "&"), text)
                self.assertLessEqual(len(text), passage.LONGEST)
                self.assertEqual(title, paper)

    def test_what_is_committed_was_ruled(self):
        """`apply.py rule --accept` makes a list for a look at the page before
        Tigran has ruled, and says so in it: such a list is never committed."""
        r = subprocess.run(["git", "show", "HEAD:data/passages.tsv"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            self.skipTest("data/passages.tsv is not committed yet")
        self.assertNotIn("NOT YET RULED", r.stdout)

    def test_the_page_carries_them_all_and_shows_the_first(self):
        raw = get("/", raw=True)[2]
        rows = [list(r) for r in self.con.execute("SELECT ref, title, html FROM passage ORDER BY n")]
        box = re.search(r'<section class="fpass">.*?</section>', raw, re.S)
        if not rows:
            return self.assertIsNone(box)
        box = box.group(0)
        self.assertIn(f'<p class="fpq">{rows[0][2]}</p>', box)
        self.assertIn(f'<a href="/{rows[0][0]}"><span class="fpr">{rows[0][0]}</span> · <span class="fpt">{rows[0][1]}</span></a>', box)
        data = re.search(r'<script type="application/json" class="fpdata">(.*?)</script>', box, re.S).group(1)
        self.assertEqual(json.loads(data), rows)
        # Nothing of a passage can close the script it is carried in.
        self.assertNotIn("</", data)
        self.assertIn("<x-en>Passage of the moment</x-en>", box)
        # The line of script: any but the one shown last, a key of its own.
        script = box[box.index("</script>") + 9:]
        self.assertIn("localStorage.getItem('ub_passage')", script)
        self.assertIn("while (key === last);", script)
        self.assertEqual(len(re.findall(r"localStorage\.\w+Item\('(\w+)'", script)), 2)
        # Before the parts' cards, and on no other page.
        self.assertLess(raw.index('<section class="fpass">'), raw.index('<ol class="front-toc">'))
        for url in ("/1:1", "/read", "/help"):
            self.assertNotIn("fpass", get(url, raw=True)[2], url)

    def test_its_reference_is_a_way_there_and_no_preview(self):
        self.assertIn("a.closest('.pop.pv, .fbar, .fpass')", JS)
        self.assertRegex(CSS, r"\.fpq \{[^}]*color: var\(--text\);")


class TheRulings(unittest.TestCase):
    """tools/passages/apply.py reads var/passages/review.md: a part of it that
    Tigran took whole says so in a line that quotes him, and that part alone
    is taken by it."""

    def test_a_part_taken_as_proposed_is_that_part_alone(self):
        spec = importlib.util.spec_from_file_location("passages_apply", ROOT / "tools" / "passages" / "apply.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        block = "## {n}. 1:1.{n} · The Universal Father (Part I)\n\n> {w}\n\nRuling: {r}\n\n"
        src = ("# First\n\nsome words\n\nTaken as proposed: Tigran, 2026-11-18: \"...\"\n\n"
               + block.format(n=1, w="A.", r="") + block.format(n=2, w="B.", r="no")
               + "# More\n\nRuling them is his.\n\n" + block.format(n=3, w="C.", r="")
               + "# And more\n\nTaken as proposed:\n\n" + block.format(n=4, w="D.", r=""))
        got = [(m[2], tool.proposed_of(body), whole, re.findall(r"^Ruling:(.*)$", body, re.M)[0].strip())
               for m, body, whole in tool.blocks(src)]
        # The line with no words after it takes nothing: it is his word or nothing.
        self.assertEqual(got, [("1:1.1", "A.", True, ""), ("1:1.2", "B.", True, "no"), ("1:1.3", "C.", False, ""),
                               ("1:1.4", "D.", False, "")])


class TheBanner(unittest.TestCase):
    def test_the_shell_has_it_before_the_header_in_both_languages(self):
        ban = re.search(r'<div class="appban"[^>]*>.*?</div>', BASE, re.S).group(0)
        self.assertLess(BASE.index('<div class="appban"'), BASE.index('<header class="top">'))
        self.assertIn("{{ t('Install as an app: it works fully offline and updates itself.') }}", ban)
        self.assertIn("""<button type="button" class="abgo">{{ t('Install') }}</button>""", ban)
        self.assertIn("""class="abno" {{ ta('aria-label', 'Not now') }}""", ban)
        # ub.css lets nothing override the attribute ([hidden]), so it is
        # hidden by its own rule, and shown by data-install on the home page.
        self.assertNotIn("hidden", ban.split(">")[0])
        self.assertIn("[hidden] { display: none !important; }", CSS)
        self.assertIn(".appban { display: none; }", CSS)
        self.assertIn(":root[data-install] body:has(> main.front) > .appban { display: flex;", CSS)

    def test_the_head_script_shows_it_in_a_tab_on_the_home_page_alone(self):
        head = BASE[:BASE.index("<body>")]
        self.assertIn("localStorage.getItem('ub_install')", head)
        self.assertIn("location.pathname === '/' && ib !== 'no' && ib !== 'done' && (ib === 'offered' || ios)", head)
        self.assertIn("!matchMedia('(display-mode: standalone)').matches && navigator.standalone !== true) r.dataset.install", head)

    def test_the_script_keeps_what_is_known_and_its_cross_is_for_good(self):
        self.assertIn("if (appBan && !appIn && appKnown() !== 'no') {\n      appKeep('offered');", JS)
        self.assertIn("window.addEventListener('appinstalled', function () {\n    window.ubInstall = null;\n    appKeep('done');", JS)
        self.assertIn("appBan.querySelector('.abno').addEventListener('click', function () {\n      appKeep('no');", JS)
        self.assertIn("appKeep(c && c.outcome === 'accepted' ? 'done' : null);", JS)
        # A key of its own, and no setting: Restore the defaults leaves it.
        self.assertIn("APP = 'ub_install'", JS)
        from ubsite import settings
        self.assertNotIn("install", [k[0] for k in settings.READING + settings.KEPT])


class TheCopysState(unittest.TestCase):
    def test_the_bar_has_it_on_every_page_and_shows_it_on_the_home_page(self):
        bar = re.search(r'<nav class="fbar".*?</nav>', BASE, re.S).group(0)
        self.assertIn('<button type="button" class="fstate" data-st="" hidden>{{ chrome.state_svg() }}'
                      '<span class="fsl"></span><span class="fss"></span></button>', bar)
        self.assertIn('<span class="fprog" hidden></span>', bar)
        chrome = (ROOT / "ubsite" / "templates" / "_chrome.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'<svg class="(fs-\w+)"', chrome), ["fs-ok", "fs-down", "fs-stale", "fs-off"])
        self.assertIn(".fbar .fstate, .fbar .fprog { display: none; }", CSS)
        self.assertIn("main.front ~ .fbar .fstate:not([hidden]) { display: flex;", CSS)
        for st in ("ok", "down", "stale", "off"):
            self.assertIn(f'.fstate[data-st="{st}"] .fs-{st}', CSS)

    def test_offline_js_says_it_from_what_the_worker_says(self):
        self.assertIn("function show(s) {\n    last = s;\n    barState(s);", OFF)
        self.assertIn("panel.dataset.net = on ? 'on' : 'off';\n    barState(last);", OFF)
        for words in ("Offline copy up to date", "Offline copy out of date", "Offline copy out of date · Update now ({s})",
                      "Downloading the offline copy: {a} of {b}", "Offline · reading from the copy of {d}"):
            self.assertIn(f"T('{words}'", OFF)
        self.assertIn("window.ubSettings.open('offline')", OFF)
        self.assertIn("window.ubSettings.open = function (tab) {", JS)


if __name__ == "__main__":
    unittest.main()
