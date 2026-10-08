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
    """Fill `speech`: one row per section heading and per paragraph."""
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
