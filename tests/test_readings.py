"""The readings, more than one, and one of a translation (2026-11-12).

Merritt Horn's reading of the English was the only one until Григорий
Войнер's of the translation urantia-ru (USGNY) came.  These hold what a second
reading needs of the build, the app and the player: that each is filed by its
own rule (sources.toml `name`), that a file no rule claims fails, that a
translation's reading says whose it is everywhere a voice is listed and is
never offered for the English text, and that the aligner's Russian meets a
number in any form.  Rendered through the app as ASGI, as test_whole does;
the database's facts skipped when var/ub.db has not been built.
"""

import json
import re
import sqlite3
import unittest

from test_appendix_pages import DB, ROOT, get
from build import audio, config
from build.problems import Report
from tools.align import ru
from tools.align.align import align, heard, tokens
from ubsite import settings

AUDIO = re.compile(r'id="ub-audio">(.*?)</script>', re.S)
TRS = re.compile(r'id="ub-translations">(.*?)</script>', re.S)


class Sources(unittest.TestCase):
    def test_every_human_reading_says_how_it_is_filed(self):
        for key, src in config.audio().items():
            if src["kind"] != "human":
                continue
            with self.subTest(key=key):
                rule = re.compile(src["name"])
                self.assertLessEqual({"paper", "section"}, set(rule.groupindex))
                self.assertTrue(src["glob"].endswith(".mp3"))

    def test_the_russian_reading_is_of_usgny_and_filed_flat(self):
        v = config.audio()["voyner"]
        self.assertEqual((v["translation"], v["kind"], v["label"]), ("urantia-ru", "human", "Grigory Voyner"))
        self.assertEqual(v["glob"], "*.mp3")
        rule = re.compile(v["name"])
        self.assertEqual(rule.match("139-09-10.mp3").group("paper", "section", "with"), ("139", "09", "10"))
        self.assertEqual(rule.match("07-07.mp3").group("paper", "section", "with"), ("07", "07", None))
        # A paper in one digit is no name of the rule's: 7-07.mp3 is 75:7 again.
        self.assertIsNone(rule.match("7-07.mp3"))
        self.assertIsNone(config.audio()["mh"]["translation"])

    def test_the_lists_name_what_is_left_out(self):
        over = audio._optional(audio.DATA / "voyner-overrides.tsv")
        # Three second copies under another section's name, none of them used.
        self.assertEqual([(name, start) for name, start, _why in over],
                         [("7-07.mp3", "-"), ("19-00.mp3", "-"), ("50-00.mp3", "-")])
        # And the two sections the copies stand in for are on the record as
        # unread, every paragraph of each.
        unread = set(audio.unread("voyner"))
        self.assertEqual(unread, {f"19:0.{n}" for n in range(1, 10)} | {"50:0.1", "50:0.2"})
        self.assertEqual({r[0] for r in audio._optional(audio.DATA / "mh-overrides.tsv")},
                         {"paper000/P000_13.mp3", "paper040/P040_11.mp3", "paper041/P041_11.mp3"})


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Claims(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    def claims(self, key, src=None):
        report = Report()
        got = audio.claims(self.con, key, src or config.audio()[key], audio.files(key), report)
        return got, [(p.code, p.where) for p in report.problems]

    def test_each_reading_claims_every_section_once(self):
        sections = {sid for (sid,) in self.con.execute("SELECT id FROM section")}
        # Григорий Войнер's has no file for 19:0 or 50:0 (voyner-unread.tsv).
        lacks = {sid for (sid,) in self.con.execute(
            "SELECT id FROM section WHERE (paper_n, n) IN ((19, 0), (50, 0))")}
        self.assertEqual(len(lacks), 2)
        for key, extra, missing in (("mh", 1, set()), ("voyner", 0, lacks)):   # the Acknowledgment's own track
            with self.subTest(key=key):
                got, problems = self.claims(key)
                self.assertEqual(problems, [])
                self.assertEqual({sid for sid, _pid in got.values()}, sections - missing)
                self.assertEqual(len(got), len(sections) - len(missing) + extra)

    def test_a_file_no_rule_claims_fails_without_its_line(self):
        # The same files under a key with no overrides: 7-07.mp3 is nobody's.
        src = dict(config.audio()["voyner"])
        report = Report()
        files = audio.files("voyner")
        audio.claims(self.con, "nobody", src, files, report)
        self.assertEqual([(p.code, p.where) for p in report.problems], [("audio-unclaimed", "7-07.mp3")])

    def test_two_files_for_one_place_fail(self):
        src = dict(config.audio()["voyner"], name=r"^0?(?P<paper>\d{1,3})-(?P<section>\d{2})(?:-(?P<with>\d{2}))?\.mp3$")
        report = Report()
        audio.claims(self.con, "nobody", src, audio.files("voyner"), report)
        self.assertIn("audio-claimed-twice", {p.code for p in report.problems})

    def test_139_s_nine_and_ten_is_one_file_in_each(self):
        nine = self.con.execute("SELECT id FROM section WHERE paper_n = 139 AND n = 9").fetchone()[0]
        for key, name in (("mh", "paper139/P139_09-10.mp3"), ("voyner", "139-09-10.mp3")):
            self.assertEqual(self.claims(key)[0][name], (nine, None))

    def test_the_database_says_which_text_each_reads(self):
        rows = self.con.execute("SELECT key, kind, translation FROM audio_source ORDER BY id").fetchall()
        self.assertEqual(rows, [("mh", "human", None), ("voyner", "human", "urantia-ru")])
        # A translation's reading is cut at our paragraphs, those it has.
        self.assertEqual(self.con.execute(
            "SELECT COUNT(*) FROM audio_segment g JOIN audio_source s ON s.id = g.source_id"
            " WHERE s.key = 'voyner' AND g.paragraph_id IS NOT NULL AND NOT EXISTS ("
            "  SELECT 1 FROM tr_paragraph t WHERE t.translation = s.translation"
            "   AND t.paragraph_id = g.paragraph_id)").fetchone()[0], 0)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Pages(unittest.TestCase):
    def test_a_page_s_voices_say_whose_they_are(self):
        for path in ("/15:3", "/15"):
            with self.subTest(path=path):
                j = json.loads(AUDIO.search(get(path, raw=True)[2])[1])
                self.assertEqual(list(j["voices"]), ["mh", "voyner"])
                self.assertNotIn("tr", j["voices"]["mh"])
                v = j["voices"]["voyner"]
                self.assertEqual((v["tr"], v["lang"], v["label"], v["credit"]), ("urantia-ru", "ru", "Grigory Voyner", None))
                self.assertTrue(all(f.startswith("/audio/voyner/15-") for f in v["files"]), v["files"])

    def test_the_translation_lists_its_recording(self):
        trs = {x["key"]: x for x in json.loads(TRS.search(get("/15:3", raw=True)[2])[1])}
        self.assertEqual(trs["urantia-ru"]["voices"], [{"key": "voyner", "label": "Grigory Voyner"}])
        self.assertEqual((trs["ud"]["voices"], trs["uf-ru"]["voices"]), ([], []))

    def test_the_second_encode_is_in_no_list_the_app_serves(self):
        # /audio/<key>/<name> serves only a name of audio_file (test_offline
        # asks it): 7-07.mp3 is in the directory and its list, and not there.
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        names = {n for (n,) in con.execute("SELECT f.name FROM audio_file f JOIN audio_source s"
                                           " ON s.id = f.source_id WHERE s.key = 'voyner'")}
        for stray in ("7-07.mp3", "19-00.mp3", "50-00.mp3"):
            self.assertIn(stray, audio.files("voyner"))
            self.assertNotIn(stray, names)
        self.assertLessEqual({"07-07.mp3", "75-07.mp3", "139-09-10.mp3", "192-00.mp3", "50-04.mp3"}, names)
        self.assertEqual(len(names), 1624)

    def test_settings_keep_it_from_the_english_text(self):
        """Settings' Voices: a menu against each text, the English first; a
        text's recordings in its own menu and no other's."""
        from ubsite import app as A
        groups = {g["key"]: g for g in settings.groups(A.voices(), A.translations())}
        items = {it["key"]: it for it in groups["listening"]["items"]}
        self.assertEqual(items["voice"]["label"], "Voices")
        texts = items["voice"]["choices"]
        self.assertEqual([(c["value"], c["label"], c["lang"]) for c in texts],
                         [("", "English text", "en"), ("ud", "Aivazian", "ru"), ("urantia-ru", "USGNY", "ru"),
                          ("uf-ru", "UF-RUS", "ru")])
        self.assertEqual({c["value"]: [v["key"] for v in c["rec"]] for c in texts},
                         {"": ["mh"], "ud": [], "urantia-ru": ["voyner"], "uf-ru": []})
        # The two settings the menus set besides have no control of their own.
        self.assertEqual({k: items[k]["kind"] for k in ("bvoice", "trvoices")}, {"bvoice": "part", "trvoices": "part"})
        body = get("/15:3", raw=True)[2]
        rows = re.findall(r'<label class="row set-bvoice" data-k="([^"]*)" data-lang="(\w+)"([^>]*)>(.*?)</label>', body, re.S)
        self.assertEqual([(k, lang) for k, lang, _a, _b in rows],
                         [("", "en"), ("ud", "ru"), ("urantia-ru", "ru"), ("uf-ru", "ru")])
        menu = {k: (attrs, inner) for k, _lang, attrs, inner in rows}
        options = {k: re.findall(r'<option value="([^"]*)"( data-rec| class="any")', inner) for k, (_a, inner) in menu.items()}
        # The English text's: its recording by its key, then what stands for
        # the browser's voices until it has listed them.  Shown from the first.
        self.assertEqual(options[""], [("mh", " data-rec"), ("browser", ' class="any"')])
        self.assertIn('<option value="mh" data-rec data-ru="Мерритт Хорн">Merritt Horn</option>', menu[""][1])
        self.assertIn('data-rec="mh"', menu[""][0])
        self.assertNotIn("hidden", menu[""][0])
        # A translation's: the recording first, and the default, the value
        # with nothing stored; hidden until ub.js finds it ticked.
        self.assertEqual(options["urantia-ru"], [("", " data-rec"), ("browser", ' class="any"')])
        self.assertIn('<option value="" data-rec data-ru="Григорий Войнер">Grigory Voyner</option>', menu["urantia-ru"][1])
        self.assertIn('data-rec="voyner"', menu["urantia-ru"][0])
        self.assertIn("hidden", menu["urantia-ru"][0])
        self.assertEqual(options["uf-ru"], [("", ' class="any"')])
        self.assertNotIn("data-rec", menu["uf-ru"][0])
        # No voice is a radio button any more, the browser's have no menu of
        # their own, and none is listed twice (Tigran, 2026-11-13).
        dialog = body[body.index('<dialog class="settings"'):body.index("</dialog>")]
        for gone in ('type="radio" name="voice"', '<select name="bvoice"', "Automatic<", "v-browser"):
            self.assertNotIn(gone, dialog)
        for name in ("Merritt Horn", "Grigory Voyner"):                # its menu, and the Offline tab's recordings
            self.assertEqual(dialog.count(f">{name}<"), 2, name)

    def test_the_offline_tab_names_its_translation(self):
        body = get("/15:3", raw=True)[2]
        row = re.search(r'<details class="recvoice" data-key="voyner">.*?</summary>', body, re.S)[0]
        self.assertIn('<span class="rpt">· USGNY</span>', row)
        self.assertNotIn("rpt", re.search(r'<details class="recvoice" data-key="mh">.*?</summary>', body, re.S)[0])

    def test_the_player_never_takes_it_for_the_english(self):
        js = (ROOT / "ubsite" / "static" / "listen.js").read_text()
        choose = js[js.index("function choose(d)"):js.index("// Offline a recording cannot be had")]
        self.assertIn("!d.voices[want].tr", choose)
        self.assertIn("if (!d.voices[v].tr) return v;", choose)
        # Its ▶ plays the voice Settings asks for, the recording by default.
        play = js[js.index("function trButton(t, line)"):js.index("document.addEventListener('ub:cmp'")]
        self.assertIn("trKey(P, t)", play)
        self.assertNotIn("'browser:' + t", play)

    def test_its_play_button_stands_in_the_fold_as_in_the_columns(self):
        # Tigran, 2026-11-13: "On the phone there is no play triangle at all,
        # except against English text": a phone shows a translation in the
        # fold under its paragraph, and the columns alone had a ▶.  ub.js says
        # which line names one translation and that the fold is drawn; listen.js
        # makes the same button for both.
        js = (ROOT / "ubsite" / "static" / "listen.js").read_text()
        ub = (ROOT / "ubsite" / "static" / "ub.js").read_text()
        draw = ub[ub.index("function trDraw(tf, ks, tab)"):ub.index("function arriveTr()")]
        self.assertIn("(cur === 'all' ? '' : ' data-play=\"' + cur + '\"')", draw)
        self.assertIn("'<p class=\"who\" data-play=\"' + k + '\">'", draw)
        self.assertIn("new CustomEvent('ub:trfold', { detail: panel })", draw)
        # A tab is a button that names one: the ▶ in their row is not a tab.
        self.assertIn("closest('.trfold, .trtabs button[data-tab]')", ub)
        fold = js[js.index("function foldPlay(panel)"):js.index("// ---- the bar")]
        self.assertIn("trButton(t, panel.querySelector('p.rt[data-k=\"' + t + '\"][data-ref]'))", fold)
        self.assertIn("document.addEventListener('ub:trfold', function (ev) { foldPlay(ev.detail); });", fold)
        self.assertEqual(js.count("function trButton("), 1)


class Russian(unittest.TestCase):
    def test_a_number_is_a_number_in_any_form(self):
        self.assertEqual(tokens("1. Имя Отца.", "ru"), ["#", "имя", "отца"])
        self.assertEqual(tokens("Глава первая. Имя Отца.", "ru"), ["глава", "#", "имя", "отца"])
        self.assertEqual(tokens("Им было по двадцать шесть лет", "ru"), ["им", "было", "по", "#", "#", "лет"])
        self.assertEqual(tokens("в 1934 году, 2-й и 10-го; 2,5 раза", "ru"),
                         ["в", "#", "году", "#", "и", "#", "#", "раза"])
        for w in ("одного", "двух", "тремя", "четырёх", "пятью", "восьми", "сорока", "девяноста", "ста",
                  "двухсот", "пятьюстами", "тысячами", "миллионов", "первая", "второго", "третьей",
                  "четвёртом", "седьмая", "сороковой", "сотый", "двадцатому"):
            self.assertEqual(tokens(w, "ru"), ["#"], w)
        for w in ("глава", "текст", "отец", "семья", "столетие", "первоисточник", "троица", "единый"):
            self.assertEqual(tokens(w, "ru"), [w], w)

    def test_a_roman_numeral_is_a_number_too(self):
        # 30:1.2's label, "I.", which he reads "Первое.": as a word it left
        # the cut after the label.  The Russian и is a word still.
        self.assertEqual(tokens("I. Существа триединого происхождения", "ru")[:2], ["#", "существа"])
        self.assertEqual(tokens("II. и XIV, IV", "ru"), ["#", "и", "#", "#"])
        self.assertEqual(tokens("Первое. Существа", "ru"), ["#", "существа"])

    def test_a_window_to_hear_again_reaches_over_the_transcript_s_silence(self):
        # 42:12.2-7, six items of a list, were read from 37 s to 61 s and
        # heard by nobody: their cuts stood at 61.3-62.0 s, and fifteen
        # seconds before that is still inside what was lost.
        from tools.align.transcribe import window
        words = [[t, t + 0.9, "слово", 1] for t in range(0, 31)] + [
            [34.7, 37.3, "стремится.", 1], [61.2, 61.3, "к", 1], [61.3, 67.0, "выполнению", 1],
            [68.3, 71.1, "творческий.", 1]] + [[t, t + 0.9, "слово", 1] for t in range(72, 400)]
        lo, hi = window(words, 61.3, 61.4, 400.0)
        self.assertEqual((round(lo, 1), round(hi, 1)), (36.3, 76.4))
        # A transcript that stops short is silent to the file's end, and the
        # window goes there: what was dropped would be in it.
        self.assertEqual(window(words[:35], 61.3, 61.4, 400.0)[1], 400.0)
        # With no silence near, fifteen seconds either side, within the file.
        dense = [[t, t + 0.9, "слово", 1] for t in range(0, 100)]
        self.assertEqual(window(dense, 50.0, 55.0, 100.0), (35.0, 70.0))
        self.assertEqual(window(dense, 5.0, 96.0, 100.0), (0.0, 100.0))

    def test_the_spelling_is_the_text_s_but_for_yo_and_the_stress(self):
        self.assertEqual(tokens("Всё ещё призна́ют Бог-Отец", "ru"), ["все", "еще", "признают", "бог", "отец"])
        self.assertEqual(ru.fold("Сверх­вселенная"), "сверхвселенная")

    def test_whisper_s_words_are_cut_as_the_text_s(self):
        toks, times = heard([[0, 1, "Бог", 1], [1, 2, "-Отец", 1], [2, 3, "26", 1], [3, 4, "лет.", 1]], "ru")
        self.assertEqual(toks, ["бог", "отец", "#", "лет"])
        self.assertEqual(times, [(0, 1), (1, 2), (2, 3), (3, 4)])

    def test_english_is_as_it_was(self):
        self.assertEqual(tokens("The Foreword of counsellors"), ["the", "forward", "of", "counselors"])
        with self.assertRaises(ValueError):
            tokens("ein Wort", "de")

    def test_a_list_s_mark_is_its_paragraph_s_first_word(self):
        # Two list items read with a longer pause after each number than
        # before it (CLAUDE.md trap 16): each cut still comes before its
        # number, since the number is heard as the paragraph's first word.
        text = {"1:1.1": "1. Семь Духов-Мастеров.", "1:1.2": "2. Семь Верховных Распорядителей."}
        words = [[0.5, 0.9, "1.", 1], [1.6, 2.0, "Семь", 1], [2.0, 2.5, "духов", 1], [2.5, 3.2, "мастеров.", 1],
                 [3.5, 3.9, "2.", 1], [4.7, 5.1, "Семь", 1], [5.1, 5.8, "верховных", 1],
                 [5.8, 6.8, "распорядителей.", 1]]
        sil = [(0.0, 0.5), (0.9, 1.6), (3.2, 3.5), (3.9, 4.7), (6.8, 8.0)]
        got = align(text, "x.mp3", ["1:1.1", "1:1.2"], words, 8.0, sil, "ru")
        self.assertEqual([(r, m) for r, _a, _b, m in got], [("1:1.1", 1.0), ("1:1.2", 1.0)])
        cut = got[1][1]
        self.assertTrue(3.2 <= cut <= 3.9, cut)


class Edition(unittest.TestCase):
    """The reading reads its translation as it stood when it was recorded
    (tools/align/edition.py): the aligner matches it to the text there."""

    def test_the_russian_reading_names_the_commits_its_text_lies_between(self):
        commits = config.audio()["voyner"]["edition"]
        self.assertEqual(len(commits), 2)
        for c in commits:
            self.assertRegex(c, r"^[0-9a-f]{7,40}$")
        self.assertEqual(config.audio()["mh"]["edition"], ())

    def test_a_paragraph_is_read_as_the_commit_nearer_what_was_heard_has_it(self):
        """The first commit named, unless what was heard is nearer a later
        one; and a line of verse is weighed with the line before it, or two
        commits that divide a sentence otherwise each give it the same words."""
        import sqlite3
        from unittest import mock
        from tools.align import edition
        con = sqlite3.connect(":memory:")
        con.executescript("CREATE TABLE paragraph (id INTEGER PRIMARY KEY, ref TEXT);"
                          "CREATE TABLE tr_paragraph (paragraph_id INTEGER, translation TEXT);")
        refs = ["1:1.1", "1:1.2", "1:1.3", "1:1.4"]
        for i, r in enumerate(refs):
            con.execute("INSERT INTO paragraph VALUES (?, ?)", (i, r))
            con.execute("INSERT INTO tr_paragraph VALUES (?, 'x')", (i,))
        at = {"new": {"1:1.1": "Отличным от стремления", "1:1.2": "Дабы мы служили ему безбоязненно",
                      "1:1.3": "Служить Ему в святости и правде"},
              "old": {"1:1.1": "В отличие от стремления", "1:1.2": "Служить Ему,",
                      "1:1.3": "В святости и правде", "1:1.4": "Только здесь"}}

        class V:
            translation = "x"
            src = {"edition": ("new", "old")}
        heard = {"1:1.1": tokens("в отличие от стремления", "ru"), "1:1.2": tokens("служить", "ru"),
                 "1:1.3": tokens("ему в святости и правде", "ru")}
        with mock.patch.object(edition, "paragraphs", lambda v, con, c: (at[c], [])):
            words, where = edition.read(V, con, heard)
            first, _ = edition.read(V, con, {})
        self.assertEqual(where, {"1:1.1": "old", "1:1.2": "old", "1:1.3": "old", "1:1.4": "old"})
        self.assertEqual(words["1:1.3"], "В святости и правде")
        self.assertEqual([first[r] for r in refs], [at["new"][r] for r in refs[:3]] + ["Только здесь"])

    def test_a_paragraph_of_tex_as_words(self):
        from tools.align.edition import RE_VS, plain
        tex = ("\\upaper{1}{Отец Всего Сущего}\n"
               "\\vs p001 1:4 \\P\\ Вблизи центра, долгое\\hyp{}долгое\\bibnobreakspace{}путешествие"
               "\\fnst{Примечание \\bibemph{со} скобками.} к \\bibemph{Раю} --- и далее.\n"
               "\\vs p001 1:5 \\ublistelem{1.}\\bibnobreakspace Семь Духов.\n")
        got = {f"{int(m[1])}:{m[2]}.{m[3]}": plain(m[4]) for m in RE_VS.finditer(tex)}
        self.assertEqual(got, {"1:1.4": "Вблизи центра, долгое-долгое путешествие к Раю --- и далее.",
                               "1:1.5": "1. Семь Духов."})
        self.assertEqual(tokens(got["1:1.5"], "ru"), ["#", "#", "духов"])

    def test_another_paragraph_s_words_are_not_the_same_place(self):
        from tools.align.edition import SAME, likeness
        a = "Вблизи центра вселенной вселенных Отец Всего Сущего обычно известен по имени"
        self.assertGreater(likeness(a, a.replace("по имени", "под именами")), 0.8)
        self.assertLess(likeness(a, "Благослови нас в пути нашем и веди нас к свету"), SAME)


if __name__ == "__main__":
    unittest.main()
