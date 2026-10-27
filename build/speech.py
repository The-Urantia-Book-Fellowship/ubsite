"""The text as it is to be spoken: what a synthetic voice reads.

A reader turns "1,000,000,000" into words without thinking; a voice model may
not, and each one guesses differently.  So the words are decided here, once, in
the build, where they can be gated: no digit survives, and nothing outside a
small set of characters.  The spoken text is stored beside the printed one
(table `speech`) with its SHA; a recording made from an older spoken text is
stale, and check_audio fails on it.

What changes, and why it is safe to change it:

  list marks      "1." -> "One.", "II." -> "Two.", "b." -> "B."   (the listmark span)
  powers          "2×10²⁷" -> "two times ten to the twenty-seventh"   (the sup span)
  dot leaders     "Superuniverses 7" -> "Superuniverses, seven."      (the leader span)
  ordinals        "611,121st" -> "six hundred eleven thousand one hundred twenty-first"
  fractions       "1/2,000th" -> "one two thousandth";  "365¼" -> "... and a quarter"
  years, rounds   a bare four-digit number -> "nineteen thirty-four", "twenty-five hundred"
  degrees         "75° to 90° F." -> "seventy-five degrees to ninety degrees Fahrenheit."
                  "70 degrees below zero F." -> "... below zero Fahrenheit."
  abbreviations   St. Saint, vs. versus, etc. et cetera
  regnal numbers  "Shalmaneser III" -> "Shalmaneser the Third"
  capitals        "I AM" -> "I Am", "DIVININGTON" -> "Divinington": a voice model may
                  spell a word in capitals letter by letter, as it would an acronym,
                  and the book has no acronyms.  Its capitals are emphasis (LOVE,
                  MIND), a few headings (ACKNOWLEDGMENT), and Paper 30's group names.
  brackets        "[Presented by ...]" loses its brackets; nothing else is removed

Everything else -- punctuation, quotation marks, dashes -- is left for the voice,
which pauses on them as a reader does.  The one punctuation added is the full stop
that ends a table row: without it Higgs TTS 3 read "Major sectors, seventy" as if
the list went on, level or rising and cut short (20 rows, three seeds each: the
pitch fell at the end in 19 of 60 readings without the stop, 50 of 60 with it).  A heading is spoken as he reads it:
"Two. The Reality of God."; an introduction as "Paper One. The Universal Father.",
after its part's line when the paper opens a part.
"""

from __future__ import annotations

import hashlib
import re

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen"
        " fourteen fifteen sixteen seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SCALES = ["", "thousand", "million", "billion", "trillion", "quadrillion"]
REGNAL = {"II": "the Second", "III": "the Third", "IV": "the Fourth"}
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
         "IX": 9, "X": 10, "XI": 11, "XII": 12}
FIRST_OF_PART = {1: 1, 32: 2, 57: 3, 120: 4}
# Every character a spoken text may contain -- with the accented Latin letters
# ("attachés", 122:10.4).  Anything else is a gate failure:
# a symbol the voice would have to guess at.
ALLOWED = re.compile(r"^[A-Za-zÀ-ÿ .,;:!?'\"\-—()’‘“”]*$")


def _under_1000(n: int) -> list[str]:
    out = []
    if n >= 100:
        out += [ONES[n // 100], "hundred"]
        n %= 100
    if n >= 20:
        out.append(TENS[n // 10] + (f"-{ONES[n % 10]}" if n % 10 else ""))
    elif n or not out:
        out.append(ONES[n])
    return out


def cardinal(n: int) -> str:
    """375 -> 'three hundred seventy-five'; 10234601 -> 'ten million two hundred
    thirty-four thousand six hundred one'.  American, without 'and'."""
    if n == 0:
        return "zero"
    groups, words = [], []
    while n:
        groups.append(n % 1000)
        n //= 1000
    for i in range(len(groups) - 1, -1, -1):
        if groups[i]:
            words += _under_1000(groups[i]) + ([SCALES[i]] if SCALES[i] else [])
    return " ".join(words)


def ordinal(n: int) -> str:
    words = cardinal(n)
    head, _, last = words.rpartition(" ")
    hy, _, unit = last.rpartition("-")
    irregular = {"one": "first", "two": "second", "three": "third", "five": "fifth",
                 "eight": "eighth", "nine": "ninth", "twelve": "twelfth"}
    if unit in irregular:
        unit = irregular[unit]
    elif unit.endswith("y"):
        unit = unit[:-1] + "ieth"
    else:
        unit += "th"
    last = f"{hy}-{unit}" if hy else unit
    return f"{head} {last}" if head else last


def year(n: int) -> str:
    """A bare four-digit number, as a year or a round figure is said:
    1934 'nineteen thirty-four', 1806 'eighteen oh six', 2500 'twenty-five
    hundred', 8000 'eight thousand'.  In the book these are all dates B.C. or
    A.D., or round figures like 1200° F."""
    hi, lo = divmod(n, 100)
    if n % 1000 == 0:
        return cardinal(n)
    if lo == 0:
        return f"{cardinal(hi)} hundred"
    if lo < 10:
        return f"{cardinal(hi)} oh {ONES[lo]}"
    return f"{cardinal(hi)} {cardinal(lo)}"


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def speak(text: str, spans=()) -> str:
    """The printed paragraph -> the spoken one.  `spans` are (start, end, kind)."""
    # Span-based edits first, from the end backwards so offsets stay valid.
    edits = []
    for start, end, kind in spans:
        mark = text[start:end]
        if kind == "listmark":
            # "1." "II." "A." "b." -- and "“3." where a numbered saying opens a quotation.
            m = re.fullmatch(r"(“?)(\d+|[IVX]+|[A-Za-z])\.", mark)
            if not m:
                raise ValueError(f"list mark {mark!r} is no number, numeral or letter")
            q, v = m.groups()
            n = int(v) if v.isdigit() else ROMAN.get(v)
            # A letter stays a letter, capital, for the voice to name.
            said = _cap(cardinal(n)) if n else v.upper()
            edits.append((start, end, f"{q}{said}."))
        elif kind == "dotleader":
            edits.append((start, end, ","))
        elif kind == "sup" and mark.isdigit():
            # A power: the base is the digits just before it.  "2×1027" is 2×10^27.
            b = start
            while b > 0 and text[b - 1].isdigit():
                b -= 1
            edits.append((b, end, f"{cardinal(int(text[b:start]))} to the {ordinal(int(mark))}"))
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    if any(kind == "dotleader" for _s, _e, kind in spans) and text.rstrip()[-1:] not in ".!?;:":
        text = text.rstrip() + "."

    t = text.replace("\xa0", " ").replace("[", "").replace("]", "")
    t = t.replace("×", " times ")
    t = re.sub(r"\bSt\. ", "Saint ", t)
    t = re.sub(r"\bvs\. ", "versus ", t)
    t = re.sub(r"\betc\.", "et cetera", t)
    # Degrees: "1200° F. is" -- the period ends the sentence only when a capital follows.
    t = re.sub(r"°\s*F\.(?=\s+[a-z])", " degrees Fahrenheit", t)
    t = re.sub(r"°\s*F\.", " degrees Fahrenheit.", t)
    t = re.sub(r"°", " degrees", t)
    t = re.sub(r"\bzero F\.(?=\s+[a-z])", "zero Fahrenheit", t)
    t = re.sub(r"\bzero F\.", "zero Fahrenheit.", t)
    t = re.sub(r"(?<=[a-z] )(II|III|IV)\b", lambda m: REGNAL[m[1]], t)
    t = re.sub(r"\b[A-Z][A-Z]+\b", lambda m: m[0].capitalize(), t)
    t = re.sub(r"(\d{1,2}):00\s*(A\.M\.|P\.M\.)", lambda m: f"{cardinal(int(m[1]))} {m[2]}", t)
    t = re.sub(r"(\d+)/([\d,]+)(?:st|nd|rd|th)\b",
               lambda m: f"{cardinal(_num(m[1]))} {ordinal(_num(m[2]))}", t)
    t = re.sub(r"(\d+)¼", lambda m: f"{cardinal(int(m[1]))} and a quarter", t)
    t = re.sub(r"\b(\d)-(\d)-(\d)\b", lambda m: "-".join(ONES[int(d)] for d in m.groups()), t)
    t = re.sub(r"\b(\d{1,3}(?:,\d{3})+|\d+)(st|nd|rd|th)\b", lambda m: ordinal(_num(m[1])), t)
    t = re.sub(r"\b\d{1,3}(?:,\d{3})+\b", lambda m: cardinal(_num(m[0])), t)
    t = re.sub(r"(?<![\d,])\b\d{4}\b(?![\d,])", lambda m: year(int(m[0])), t)
    t = re.sub(r"\b\d+\b", lambda m: cardinal(int(m[0])), t)
    return re.sub(r"  +", " ", t).strip()


def heading(paper: int, n: int, title: str | None, combined: int | None,
            paper_title: str, part: tuple[int, str] | None) -> str:
    """What is said before a section's first paragraph."""
    if n:
        num = _cap(cardinal(n)) + (f" and {cardinal(combined)}" if combined else "")
        return speak(f"{num}. {title}.")
    if paper == 0:
        return "Foreword."
    lead = f"Part {_cap(cardinal(part[0]))}. {part[1]}. " if part else ""
    return speak(f"{lead}Paper {_cap(cardinal(paper))}. {paper_title}.")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def derive(con) -> int:
    """Fill `speech`: one row per section heading and per paragraph.  The
    translations' spoken text is `derive_tr`'s, below."""
    spans = {}
    for pid, s, e, kind in con.execute(
            "SELECT paragraph_id, start, \"end\", kind FROM span"
            " WHERE kind IN ('listmark','dotleader','sup')"):
        spans.setdefault(pid, []).append((s, e, kind))
    parts = dict(con.execute("SELECT n, title FROM part"))
    rows = []
    for sid, p, n, title, cw, ptitle in con.execute(
            "SELECT s.id, s.paper_n, s.n, s.title, s.combined_with, pa.title"
            " FROM section s JOIN paper pa ON pa.id = s.paper_id ORDER BY s.id"):
        part = (FIRST_OF_PART[p], parts[FIRST_OF_PART[p]]) if p in FIRST_OF_PART else None
        h = heading(p, n, title, cw, ptitle, part if n == 0 else None)
        rows.append((sid, None, h, sha(h)))
    for pid, sid, text in con.execute("SELECT id, section_id, text FROM paragraph ORDER BY ord"):
        s = speak(text, spans.get(pid, ()))
        rows.append((sid, pid, s, sha(s)))
    con.executemany("INSERT INTO speech (section_id, paragraph_id, text, sha) VALUES (?,?,?,?)",
                    rows)
    return len(rows)


# ---- The translations ------------------------------------------------------------
#
# What the browser's voice reads of a translation (Tigran, 2026-10-27): each
# paragraph as the translator wrote it, with only what a voice would trip on
# changed.  It is made from the paragraph's HTML (tr_paragraph.html_hy), which
# keeps what its text has lost: a power's <sup>, a table row's leader, a list's
# label.  Unlike the English, the numbers stay digits.  A Russian numeral takes
# its case from the words around it, "в 1934 году", "к 6000 году", which a
# browser's Russian voice reads better than a table here could, and no
# recording is made from it yet.  So, for Russian (`speak_ru`):
#
#   stress, hyphens   U+0301, the soft hyphen and the word joiner go: a voice
#                     must not break "бо́льших" at its mark
#   digit groups      "611 121", "100 000" -> 611121, 100000: one number, not two
#   list marks        a Latin numeral -> its number: "IV." -> "4."
#   dot leaders       "Сверхвселенные 7" -> "Сверхвселенные, 7.", as the English
#   powers            "2 х 10<sup>27</sup>" -> "2 умножить на 10 в 27-й степени";
#                     "см<sup>3</sup>" -> "кубический сантиметр"; any other fails
#   fractions         "3⁠1⁄8" -> "3 и 1/8", "2½" -> "2 с половиной"
#   degrees           "90°F." -> "90 градусов по Фаренгейту."
#   abbreviations     т.д., т.п., н.э., г. after a year (году after в or к,
#                     else года), км, км/с, лат.; a stop that also ended the
#                     sentence is kept
#   capitals          "Я ЕСТЬ" -> "Я Есть", a heading in capitals in lower
#                     case: a voice may spell out a word in capitals
#   brackets          lose their brackets, as the English's do
#
# A heading is spoken as the English's is, in the translation's words: "1. Имя
# Отца.", "Документ 1. Всеобщий Отец." after its part's line where the paper
# opens a part, and over the Foreword its title alone.  Each language a
# translation is in needs its function here, or the build fails.

RU_PARTS = {1: "Часть первая", 2: "Часть вторая", 3: "Часть третья", 4: "Часть четвёртая"}
RE_TAG = re.compile(r"<(/?)([a-z]+)((?: [a-z-]+=\"[^\"]*\")*)>")
# The markup a translation's HTML may hold (build/tr_html.py, tr_macros.py):
# anything else fails.  The note markers are empty, so drop with their tags.
TAGS = {"em": {""}, "sup": {""}, "a": {"fn"},
        "span": {"mark", "leader", "sc", "frac"}}
# Every character a translation's spoken text may contain: its own letters, the
# Latin ones of the words it quotes ("fīat"), digits, and the punctuation a
# voice pauses on.  Anything else is a gate failure (check_audio).
ALLOWED_TR = {"ru": re.compile(r"^[А-Яа-яЁёA-Za-zÀ-ÖØ-öø-ÿĀ-ž0-9 .,;:!?'\"\-–—()«»„“”‘’…/%]*$")}
# A stop after the abbreviation that also ends the sentence is kept for it.
ENDS = r"(?=\s+[«„“\"(]?[А-ЯЁA-Z]|\s*$)"
RU_ABBR = [(r"(\b[вкВК]\s+)?(\d+)\s*г\.",
            lambda m: f"{m[1] or ''}{m[2]} {'году' if m[1] else 'года'}"),
           (r"\bн\.\s*э\.", "нашей эры"),
           (r"\bт\.\s*д\.", "так далее"),
           (r"\bт\.\s*п\.", "тому подобное"),
           (r"\bкм/с\b", "километров в секунду"),
           (r"\bкм\b", "километров"),
           (r"\bлат\.", "латинского")]


def _sentence(s: str) -> str:
    """A heading set in capitals, in lower case after its first letter."""
    return s[:1] + s[1:].lower() if s == s.upper() else s


def speak_ru(html: str, where: str = "") -> str:
    """A Russian paragraph's HTML -> what a voice is to read."""
    h = html.replace("\xad", "").replace("́", "")
    for m in RE_TAG.finditer(h):
        cls = re.search(r'class="([^"]*)"', m[3])
        if m[2] not in TAGS or (not m[1] and (cls[1] if cls else "") not in TAGS[m[2]]):
            raise ValueError(f"{where}: {m[0]!r} is no markup the spoken text knows")
    leader = '<span class="leader"></span>' in h
    h = re.sub(r'\s*<span class="leader"></span>\s*', ", ", h)
    h = re.sub(r'<span class="mark">(«?)([IVX]+)\.</span>',
               lambda m: f"{m[1]}{ROMAN[m[2]]}.", h)
    h = re.sub(r'(\d)[⁠ \xa0 ]?<span class="frac">(\d+)⁄(\d+)</span>', r"\1 и \2/\3", h)
    h = re.sub(r'<span class="frac">(\d+)⁄(\d+)</span>', r"\1/\2", h)
    h = re.sub(r"(\d)\s*[×х]\s*10<sup>(\d+)</sup>", r"\1 умножить на 10 в \2-й степени", h)
    h = re.sub(r"\b10<sup>(\d+)</sup>", r"10 в \1-й степени", h)
    h = h.replace("см<sup>3</sup>", "кубический сантиметр")
    if "<sup>" in h:
        raise ValueError(f"{where}: a power the spoken text cannot say: {h[h.index('<sup>') - 12:][:30]!r}")
    t = re.sub(r"<[^>]+>", "", h).replace("⁠", "")
    if leader and t.rstrip()[-1:] not in ".!?;:":
        t = t.rstrip() + "."
    t = re.sub(r"(?<![\d,])(\d{1,3})((?:[ \xa0 ]\d{3})+)(?!\d)",
               lambda m: m[1] + re.sub(r"\D", "", m[2]), t)
    t = t.replace("\xa0", " ").replace(" ", " ").replace("[", "").replace("]", "")
    t = re.sub(r"(\d)\s+[×х]\s+(\d)", r"\1 умножить на \2", t)
    t = t.replace("½", " с половиной").replace("¼", " с четвертью")
    t = re.sub(r"\s*°\s*F(?![A-Za-z])", " градусов по Фаренгейту", t)
    t = re.sub(r"\s*°", " градусов", t)
    for pat, words in RU_ABBR:
        stop = (lambda m, w=words: (w(m) if callable(w) else w) + ".")
        t = re.sub(pat + ENDS, stop, t)
        t = re.sub(pat, words, t)
    # Capitals: a Latin numeral stays, which a Russian voice reads ("XX века").
    t = re.sub(r"\b[А-ЯЁ][А-ЯЁ]+\b", lambda m: m[0].capitalize(), t)
    t = re.sub(r"\b(?![IVXLC]+\b)[A-Z][A-Z]+\b", lambda m: m[0].capitalize(), t)
    return re.sub(r"  +", " ", t).strip()


def heading_ru(paper: int, n: int, combined: int | None, title: str | None,
               word: str, paper_title: str | None, part: str | None) -> str | None:
    """What is said before a section's first paragraph, in Russian: None
    where the translation has no title for it."""
    if n:
        if not title:
            return None
        num = f"{n} и {combined}" if combined else str(n)
        title = _sentence(re.sub(r"^(?:\d+(?: и \d+)?|[IVX]+)\.\s+", "", title))
        return speak_ru(f"{num}. {title.rstrip('.')}.")
    if not paper_title:
        return None
    title = _sentence(paper_title).rstrip(".")
    if paper == 0:
        return speak_ru(f"{title}.")
    lead = f"{RU_PARTS[FIRST_OF_PART[paper]]}. {part.rstrip('.')}. " if part else ""
    return speak_ru(f"{lead}{_sentence(word)} {paper}. {title}.")


SPEAK = {"ru": (speak_ru, heading_ru)}


def derive_tr(con) -> dict[str, int]:
    """Fill `tr_speech`, each translation's spoken text: one row per paragraph
    it has, and a heading per section it has, where it titles it.  {key: rows}."""
    from .render import strip_tags
    parts = {(k, n): strip_tags(h) for k, n, h in con.execute(
        "SELECT translation, n, html FROM tr_toc WHERE kind = 'part'")}
    heads = {(k, p, s, kind): t for k, p, s, kind, t in con.execute(
        "SELECT translation, paper_n, section_n, kind, text FROM tr_heading")}
    out = {}
    for key, lang, word in con.execute("SELECT key, lang, paper FROM translation ORDER BY ord").fetchall():
        if lang not in SPEAK:
            raise ValueError(f"translation {key}: no spoken text for its language, {lang} (build/speech.py SPEAK)")
        para, head = SPEAK[lang]
        rows = []
        for sid, p, n, cw in con.execute(
                "SELECT DISTINCT s.id, s.paper_n, s.n, s.combined_with FROM tr_paragraph t"
                " JOIN paragraph g ON g.id = t.paragraph_id JOIN section s ON s.id = g.section_id"
                " WHERE t.translation = ? ORDER BY s.id", (key,)).fetchall():
            h = head(p, n, cw, heads.get((key, p, n, "section")), word,
                     heads.get((key, p, None, "title")),
                     parts.get((key, FIRST_OF_PART[p])) if p in FIRST_OF_PART else None)
            if h:
                rows.append((key, sid, None, h))
        for pid, sid, ref, html in con.execute(
                "SELECT t.paragraph_id, g.section_id, g.ref, t.html_hy FROM tr_paragraph t"
                " JOIN paragraph g ON g.id = t.paragraph_id WHERE t.translation = ? ORDER BY g.ord",
                (key,)).fetchall():
            rows.append((key, sid, pid, para(html, f"{key} {ref}")))
        con.executemany("INSERT INTO tr_speech (translation, section_id, paragraph_id, text)"
                        " VALUES (?,?,?,?)", rows)
        out[key] = len(rows)
    return out
