"""The interface in English and Russian (Tigran, 2026-10-25; ROADMAP item 15).

Every word the site says around the book -- its header, Settings, the margin's
folds, search, the lists -- is said in both languages in every page, and CSS
shows the reader's: `:root[data-lang="ru"]`, which base.html's head script sets
before first paint, as it sets every setting (settings.py `lang`).  So no
setting reaches the server, a flag tapped turns the page at once, and the
offline copy stays one copy for every reader.  The book, its index and its
appendices, the changelog and the API's documentation stay English.

The words are `ubsite/ru.toml`, one line to a string, keyed by its English:

    "Contents" = "Содержание"
    "Offline|tab" = "Офлайн"                       a context after |, where one
                                                   English says two things
    "{n} index entries" = { en = ["{n} index entry", "{n} index entries"],
                            ru = ["{n} запись указателя", "{n} записи указателя",
                                  "{n} записей указателя"] }
    "home:index" = { en = "…", ru = "…" }          a name, for a long one

A key and its words are HTML, written as the page has them.  A placeholder is
{name}, or {name:,} for a number grouped by thousands: 14,586 in English,
14 586 in Russian, where only five digits or more are grouped.  A plural
chooses its form by {n}.  Each language's rule is here and in static/l10n.js,
which tests/test_l10n.py holds to these.

In the page:
  t(x)          the words, as <x-en>…</x-en><x-ru lang="ru">…</x-ru>: custom
                elements, never spans, which a dozen rules in ub.css style
  ta(attr, x)   an attribute, attr="English" data-ru-attr="Русский", which
                ub.js sets: an attribute cannot hold an element
  tt(x)         the English alone as text, for <title> and <option>, beside
                ru(x), their data-ru="…"
`x` is a key, with its placeholders as keywords, or an L, the words already
made in each language (tr()), as a label app.py builds.  An unknown key fails.

Both are drawn since 2026-10-25, once Tigran had read the Russian (BILINGUAL).
UB_BILINGUAL=0 in the environment draws English alone, as every page was
before, byte for byte: to compare a page with one from before.
"""

from __future__ import annotations

import datetime
import functools
import json
import os
import pathlib
import re
import tomllib

from markupsafe import Markup, escape

CATALOG = pathlib.Path(__file__).with_name("ru.toml")
LANGS = ("en", "ru")
BILINGUAL = os.environ.get("UB_BILINGUAL", "1") != "0"

RE_SLOT = re.compile(r"\{(\w+)(:,)?\}")
RE_TAG = re.compile(r"<[^>]+>")

MONTHS = {
    "en": ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"),
    # A date says the month in the genitive: 18 октября.
    "ru": ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
           "сентября", "октября", "ноября", "декабря"),
}


def plural(n: int, lang: str) -> int:
    """Which form a count takes: English one, other; Russian one (1, 21, 101),
    few (2–4, 22–24) and many (5–20, 11–14, 25…), by its last two digits."""
    n = abs(n)
    if lang == "en":
        return 0 if n == 1 else 1
    if n % 10 == 1 and n % 100 != 11:
        return 0
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return 1
    return 2


def group(n: int, lang: str) -> str:
    """A number grouped by thousands: 14,586; in Russian 14 586 with a narrow
    no-break space, and a four-digit one not grouped, 1960."""
    if lang == "en":
        return f"{n:,}"
    s = str(abs(n))
    if len(s) >= 5:
        s = f"{abs(n):,}".replace(",", " ")
    return ("-" if n < 0 else "") + s


class L:
    """A piece of the interface made in each language: HTML, by language.

    Never drawn by itself: `{{ x }}` and str(x) fail, so that one is never put
    in a page as English alone, or in an attribute as markup.  t(), ta() and
    tt() draw it.  `+` joins two, or one and a string (escaped) or Markup."""

    __slots__ = ("by",)

    def __init__(self, by: dict[str, Markup]):
        self.by = by

    def __getitem__(self, lang: str) -> Markup:
        return self.by[lang]

    @property
    def en(self) -> Markup:
        return self.by["en"]

    def __add__(self, other) -> L:
        o = other if isinstance(other, L) else L.same(other)
        return L({k: self.by[k] + o.by[k] for k in LANGS})

    def __radd__(self, other) -> L:
        return L.same(other) + self

    def __eq__(self, other) -> bool:
        return isinstance(other, L) and self.by == other.by

    def __hash__(self) -> int:
        return hash(tuple(self.by[k] for k in LANGS))

    def __str__(self) -> str:
        raise TypeError(f"{self.by['en']!r} is in two languages: draw it with t(), ta() or tt()")

    __html__ = __str__

    def __repr__(self) -> str:
        return f"L({self.by!r})"

    @staticmethod
    def same(x) -> L:
        """The same words in every language: a number, a name."""
        m = x if isinstance(x, Markup) else escape(str(x))
        return L({k: m for k in LANGS})


@functools.lru_cache(maxsize=2)
def _catalog(mtime_ns: int) -> dict[str, dict]:
    raw = tomllib.loads(CATALOG.read_text(encoding="utf-8"))
    out = {}
    for key, v in raw.items():
        if isinstance(v, str):
            v = {"ru": v}
        en = v.get("en", key.split("|", 1)[0])
        ru = v.get("ru")
        if isinstance(en, list) != isinstance(ru, list) and ru is not None:
            raise ValueError(f"ru.toml: {key!r} is a plural in one language only")
        out[key] = {"en": en, "ru": ru}
    return out


def catalog() -> dict[str, dict]:
    """ru.toml, {key: {"en": words, "ru": words}}, a plural's words a list.
    Read again when the file changes, as the dev server runs."""
    return _catalog(CATALOG.stat().st_mtime_ns)


USED: set[str] = set()


def _fill(words: str, lang: str, p: dict) -> Markup:
    def slot(m):
        name, grouped = m[1], m[2]
        if name not in p:
            raise KeyError(f"no value for {{{name}}} in {words!r}")
        v = p[name]
        if isinstance(v, L):
            return str(v[lang])
        if isinstance(v, bool) or not isinstance(v, int):
            return str(v if isinstance(v, Markup) else escape(v))
        return group(v, lang) if grouped else str(v)
    return Markup(RE_SLOT.sub(slot, words))


def tr(key: str, /, **p) -> L:
    """The words of `key` in each language, its placeholders filled."""
    entry = catalog().get(key)
    if entry is None:
        raise KeyError(f"ru.toml has no {key!r}")
    USED.add(key)
    by = {}
    for lang in LANGS:
        words = entry[lang]
        if words is None:
            if BILINGUAL:
                raise KeyError(f"ru.toml has no Russian for {key!r}")
            words = entry["en"]
            lang_rule = "en"
        else:
            lang_rule = lang
        if isinstance(words, list):
            if "n" not in p:
                raise KeyError(f"{key!r} is a plural, and has no n")
            words = words[plural(p["n"], lang_rule)]
        by[lang] = _fill(words, lang, p)
    return L(by)


def _l(x, p) -> L:
    return x if isinstance(x, L) else tr(x, **p)


def t(x, /, **p) -> Markup:
    """The words, in an element for each language; English alone until the
    Russian is turned on, or where the two are the same."""
    w = _l(x, p)
    if not BILINGUAL or w["en"] == w["ru"]:
        return w["en"]
    return Markup(f'<x-en>{w["en"]}</x-en><x-ru lang="ru">{w["ru"]}</x-ru>')


def _text(m: Markup) -> Markup:
    """Words as an attribute's value: no tags, escaped as Jinja escapes."""
    if RE_TAG.search(m):
        raise ValueError(f"markup cannot stand in an attribute: {m!r}")
    return escape(Markup(m).unescape())


def ta(attr: str, x, /, **p) -> Markup:
    """`attr` in English, and its Russian as data-ru-<attr> for ub.js to set."""
    w = _l(x, p)
    out = f'{attr}="{_text(w["en"])}"'
    if BILINGUAL and w["en"] != w["ru"]:
        out += f' data-ru-{attr}="{_text(w["ru"])}"'
    return Markup(out)


def tt(x, /, **p) -> Markup:
    """The English alone, as text: what <title> and <option> hold."""
    return _text(_l(x, p)["en"])


def ru(x, /, **p) -> Markup:
    """The Russian of <title> or an <option>, as data-ru="…", with a space
    before it; nothing until the Russian is turned on."""
    w = _l(x, p)
    if not BILINGUAL or w["en"] == w["ru"]:
        return Markup("")
    return Markup(f' data-ru="{_text(w["ru"])}"')


def num(n: int) -> L:
    """A number grouped by thousands, in each language's way."""
    return L({k: Markup(group(n, k)) for k in LANGS})


def dec(x: float) -> L:
    """A decimal, 1.25; in Russian with a comma, 1,25."""
    s = str(x)
    return L({"en": Markup(s), "ru": Markup(s.replace(".", ","))})


def date(iso: str, year: bool = True) -> L:
    """"October 18, 2026" in English, as the site writes a date (Tigran,
    2026-10-18); «18 октября 2026 г.» in Russian."""
    d = datetime.date.fromisoformat(iso)
    en = f"{MONTHS['en'][d.month - 1]} {d.day}" + (f", {d.year}" if year else "")
    ru_ = f"{d.day} {MONTHS['ru'][d.month - 1]}" + (f" {d.year} г." if year else "")
    return L({"en": Markup(en), "ru": Markup(ru_)})


NUMBER_WORDS = "zero one two three four five six seven eight nine ten eleven twelve"


def words(n: int) -> L:
    """A count up to twelve in words, "three", as a reading path names a fold;
    above, the number."""
    if n > 12:
        return L.same(n)
    w = tr(NUMBER_WORDS)
    return L({k: Markup(w[k].split()[n]) for k in LANGS})


# How a script names an entry (ubsite/l10n.js): a literal, so that it can be
# found here, and the script sent only the words it uses.
RE_SCRIPT_KEY = re.compile(
    r"""\bT(?:\.(?:text|tr|k))?\(\s*'((?:[^'\\\n]|\\.)*)'"""
    r"""|\bT\.(?:attr\([^,()]+,|a\()\s*'[\w-]+',\s*'((?:[^'\\\n]|\\.)*)'""")
RE_JS_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|.)")


def script_keys(sources: list[str]) -> set[str]:
    """Every key the scripts name, from their text."""
    out = set()
    for src in sources:
        for m in RE_SCRIPT_KEY.finditer(src):
            k = m[1] if m[1] is not None else m[2]
            out.add(RE_JS_ESCAPE.sub(lambda e: chr(int(e[1][1:], 16)) if e[1][0] == "u" and len(e[1]) == 5
                                     else e[1], k))
    return out


def script_catalog(keys) -> str:
    """What static l10n.js is handed for __CATALOG__: whether both languages
    are drawn, and the entries named, each {en, ru}; in a fixed order, so that
    the same words make the same file (CLAUDE.md trap 29)."""
    cat = catalog()
    missing = sorted(k for k in keys if k not in cat)
    if missing:
        raise KeyError(f"ru.toml has no {missing!r}, which the scripts name")
    return json.dumps({"bilingual": BILINGUAL, "words": {k: cat[k] for k in sorted(keys)}},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def install(env) -> None:
    """The helpers, as globals of the site's Jinja environment."""
    env.globals.update(t=t, ta=ta, tt=tt, ru=ru, tr=tr, num=num, dec=dec, date=date, words=words, same=L.same)
