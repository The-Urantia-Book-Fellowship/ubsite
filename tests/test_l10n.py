"""The interface in English and Russian (ubsite/l10n.py, ru.toml, l10n.js).

Every word around the book is in the page in both languages, and CSS shows the
reader's; an attribute carries its Russian beside it, data-ru-<name>, which
ub.js puts in place.  Held here:

  - the catalog: each entry in both languages, the plurals with their forms,
    the same placeholders and the same markup in each, every entry used;
  - the rules, in Python and in the script that the offline copy draws with,
    which must agree, or the copy's pages would not be the server's;
  - the pages: English alone until the Russian is turned on (BILINGUAL), and
    with it, no markup where markup cannot stand, and a shell with nothing
    left in English in its Russian view but names.

Page tests are skipped when var/ub.db has not been built, and the scripts'
when Node is not installed.
"""

import contextlib
import html
import json
import pathlib
import re
import shutil
import subprocess
import tomllib
import unittest

from test_appendix_pages import DB, ROOT, en, get
from ubsite import l10n, settings

CATALOG = tomllib.loads((ROOT / "ubsite" / "ru.toml").read_text(encoding="utf-8"))
RE_SLOT = re.compile(r"\{(\w+)(?::,)?\}")
RE_TAG = re.compile(r"<(/?[a-z][\w-]*)([^>]*)>")
RE_HREF = re.compile(r'\b(?:href|class)="([^"]*)"')


@contextlib.contextmanager
def drawn(both: bool = True):
    """Both languages drawn, as since 2026-10-25, or English alone
    (UB_BILINGUAL=0)."""
    was = l10n.BILINGUAL
    l10n.BILINGUAL = both
    try:
        yield
    finally:
        l10n.BILINGUAL = was


def forms(v) -> list[str]:
    return v if isinstance(v, list) else [v]


def entries():
    """(key, English forms, Russian forms) for every entry."""
    for key, v in CATALOG.items():
        v = {"ru": v} if isinstance(v, str) else v
        yield key, forms(v.get("en", key.split("|", 1)[0])), forms(v.get("ru"))


def skeleton(words: str) -> list:
    """What a sentence's markup is: its tags, each with its href and class."""
    return sorted((m[1], tuple(RE_HREF.findall(m[2]))) for m in RE_TAG.finditer(words))


class Catalog(unittest.TestCase):
    def test_every_entry_is_in_both_languages(self):
        for key, en, ru in entries():
            with self.subTest(key=key):
                self.assertTrue(all(ru) and all(en), "an empty form")
                if len(en) > 1 or len(ru) > 1:
                    self.assertEqual((len(en), len(ru)), (2, 3), "a plural: [one, other], [one, few, many]")

    def test_placeholders_are_the_same(self):
        for key, en, ru in entries():
            with self.subTest(key=key):
                want = set(RE_SLOT.findall(en[0]))
                for w in en + ru:
                    self.assertEqual(set(RE_SLOT.findall(w)), want, w)

    def test_markup_is_the_same(self):
        """So that what CSS assembles of a sentence (.ix, .n1955, .nst) holds in
        Russian, and a link goes where the English one does."""
        for key, en, ru in entries():
            with self.subTest(key=key):
                for w in ru + en[1:]:
                    self.assertEqual(skeleton(w), skeleton(en[0]), w)

    def test_no_id_in_the_words(self):
        """Both languages stand in the page: an id would be there twice."""
        for key, en, ru in entries():
            for w in en + ru:
                self.assertNotIn("id=", w, key)

    def test_every_entry_is_used(self):
        """Each key stands in the code, as a literal, or is one of those named by
        data: a tab's (settings.py, '|tab'), a voice's (the database), what
        ub.css draws itself (css:, below)."""
        literals = set()
        for f in [*(ROOT / "ubsite" / "templates").glob("*.html"), *(ROOT / "ubsite").glob("*.py"),
                  *(ROOT / "offline").glob("*.py"), *(ROOT / "ubsite" / "static").glob("*.js")]:
            src = f.read_text(encoding="utf-8")
            for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"", src):
                s = m[1] if m[1] is not None else m[2]
                literals.add(re.sub(r"\\u([0-9a-fA-F]{4})", lambda e: chr(int(e[1], 16)),
                                    s.replace("\\'", "'").replace('\\"', '"')))
        tabs = {g["legend"] + "|tab" for g in settings.groups([])}
        voices = {"Merritt Horn"}
        for key in CATALOG:
            with self.subTest(key=key):
                self.assertTrue(key in literals or key in tabs or key in voices or key.startswith("css:")
                                or key == l10n.NUMBER_WORDS, "named nowhere")

    def test_what_ub_css_draws_is_the_catalog(self):
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text(encoding="utf-8")
        for key in ("css:show", "css:fold"):
            for lang in ("en", "ru"):
                self.assertIn(f'content: "{CATALOG[key][lang]}"', css, key)
        for lang, attr in (("en", "data-copy"), ("ru", "data-copy-ru")):
            before, after = CATALOG["css:copy"][lang].split("{d}")
            self.assertIn(f'content: "{before}" attr({attr}) "{after}"', css)

    def test_scripts_name_their_keys_as_literals(self):
        """l10n.script_keys() finds a key by its quotes: single, always."""
        for f in (ROOT / "ubsite" / "static").glob("*.js"):
            self.assertIsNone(re.search(r"\bT(?:\.\w+)?\(\s*\"", f.read_text()), f.name)


class Rules(unittest.TestCase):
    def test_russian_plural(self):
        for n, form in ((0, 2), (1, 0), (2, 1), (4, 1), (5, 2), (11, 2), (12, 2), (14, 2), (21, 0),
                        (22, 1), (25, 2), (101, 0), (104, 1), (111, 2), (112, 2), (1001, 0)):
            self.assertEqual(l10n.plural(n, "ru"), form, n)
        self.assertEqual([l10n.plural(n, "en") for n in (0, 1, 2)], [1, 0, 1])

    def test_grouping(self):
        self.assertEqual([l10n.group(n, "en") for n in (196, 1960, 14586)], ["196", "1,960", "14,586"])
        self.assertEqual([l10n.group(n, "ru") for n in (196, 1960, 14586, 1234567)],
                         ["196", "1960", "14 586", "1 234 567"])

    def test_dates(self):
        d = l10n.date("2026-10-18")
        self.assertEqual((d["en"], d["ru"]), ("October 18, 2026", "18 октября 2026 г."))

    @unittest.skipUnless(shutil.which("node"), "Node is not installed")
    def test_python_and_the_script_agree(self):
        """The script the offline copy draws with makes what the templates make,
        in both languages: its numbers, plurals and dates, and the words."""
        from ubsite import app
        ns = list(range(0, 2001)) + [10 ** k + d for k in range(3, 8) for d in (-1, 0, 1)]
        cases = [("({a:,}–{b:,} of {n:,})", {"a": 101, "b": 200, "n": 14586}),
                 ("{n} subentries", {"n": 22}), ("Appendix {x}, {title}", {"x": "C", "title": "A & B"}),
                 ("All results for “{q}”", {"q": "<x> 'y'"}), ("nothing", {})]
        with drawn():
            src = app.l10n_js()[0].decode()
            want = [str(l10n.t(k, **p)) for k, p in cases]
            want_a = str(l10n.ta("aria-label", "The 1955 readings"))
        js = src + """
const T = globalThis.ubT, ns = %s, cases = %s;
console.log(JSON.stringify({
  plural: ns.map(n => [T.plural(n, 'en'), T.plural(n, 'ru')]),
  group: ns.map(n => [T.group(n, 'en'), T.group(n, 'ru')]),
  date: T.date('2026-10-18T00:00:00Z', true),
  words: cases.map(c => T(c[0], c[1])),
  a: T.a('aria-label', 'The 1955 readings')}));""" % (json.dumps(ns), json.dumps(cases, ensure_ascii=False))
        got = json.loads(subprocess.run(["node", "-"], input=js, capture_output=True, text=True,
                                        check=True).stdout)
        self.assertEqual(got["plural"], [[l10n.plural(n, "en"), l10n.plural(n, "ru")] for n in ns])
        self.assertEqual(got["group"], [[l10n.group(n, "en"), l10n.group(n, "ru")] for n in ns])
        self.assertEqual(got["date"], {"en": "October 18, 2026", "ru": "18 октября 2026 г."})
        self.assertEqual(got["words"], want)
        self.assertEqual(got["a"], want_a)


class Settings(unittest.TestCase):
    def test_the_language_is_kept_and_spared(self):
        self.assertEqual(settings.defaults()["lang"], "auto")
        self.assertIn("lang", [k[0] for k in settings.KEPT])
        self.assertEqual(settings.SPARED, ["lang"])


PAGES = ["/", "/101:4", "/101:10", "/144:3", "/i/humor", "/i/humor/read", "/search?q=jesus", "/lists",
         "/lists/1955", "/appendix/A", "/part/1", "/0:0.0-1", "/nothing"]


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Pages(unittest.TestCase):
    def test_english_alone_is_the_english_of_both(self):
        """UB_BILINGUAL=0 draws English alone, as every page was before both
        were: which is what en() makes of a page in both, as the tests read
        them.  The script's address alone differs, its words being others."""
        script = re.compile(r'/l10n\.js\?v=\w+|data-v="\w+"')
        for p in PAGES:
            with drawn(False):
                alone = get(p, raw=True)[2]
            both = get(p, raw=True)[2]
            with self.subTest(page=p):
                self.assertNotIn("<x-ru", alone)
                self.assertIsNone(re.search(r'\sdata-ru(-[\w-]+)?="', alone))
                self.assertEqual(script.sub("", en(both)), script.sub("", alone))

    def test_both_with_it(self):
        with drawn():
            body = get("/101:4", raw=True)[2]
            lists = get("/lists", raw=True)[2]
        self.assertIn('<x-ru lang="ru">Документ 101</x-ru>', body)
        self.assertIn('<span class="langs" hidden>', body)
        self.assertIn('<title data-ru="Списки">Lists</title>', lists)

    def test_no_markup_where_it_cannot_stand(self):
        """Not in an attribute, the title, a menu's option, nor the player's JSON."""
        with drawn():
            for p in PAGES:
                body = get(p, raw=True)[2]
                with self.subTest(page=p):
                    self.assertIsNone(re.search(r'="[^"]*<x-', body))
                    self.assertIsNone(re.search(r"<(title|option)\b[^>]*>[^<]*<x-", body))
                    for j in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', body, re.S):
                        self.assertNotIn("x-en", j)

    def test_the_russian_shell_says_nothing_in_english_but_names(self):
        """The header, the offline menu, Settings and the footer, as a reader of
        Russian sees them: x-en gone, every data-ru-<name> in its place."""
        with drawn():
            body = get("/", raw=True)[2]
        shell = body[body.index("<header"):body.index("</dialog>")] + body[body.index("<footer"):]
        shell = re.sub(r"<x-en>.*?</x-en>", "", shell, flags=re.S)
        shell = re.sub(r"<(script|svg)\b.*?</\1>", "", shell, flags=re.S)
        said = []
        for tag in re.findall(r"<[^>]+>", shell):
            ru = dict(re.findall(r'data-ru-([\w-]+)="([^"]*)"', tag))
            for name in ("title", "aria-label", "placeholder"):
                m = re.search(rf'\s{name}="([^"]*)"', tag)
                if m:
                    said.append(ru.get(name, m[1]))
            m = re.search(r'\sdata-ru="([^"]*)"', tag)
            if m:
                said.append(m[1])
        shell = re.sub(r"<option\b[^>]*\sdata-ru=[^>]*>[^<]*</option>", "", shell)
        said.append(re.sub(r"<[^>]+>", " ", shell))
        words = set(re.findall(r"[A-Za-z]{2,}", html.unescape(" ".join(said))))
        names = {"Ctrl", "OFL", "CC", "BY", "NC", "SA", "Goudy", "Uversa", "Press", "The", "Urantia", "Book",
                 "British", "Study", "Edition", "Badanon", "English", "localhost"}
        self.assertEqual(words - names, set())


if __name__ == "__main__":
    unittest.main()
