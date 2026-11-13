"""Russian words as the aligner compares them.

Whisper's words and the text's meet as tokens (tools/align/align.py).  In
Russian two things differ from the English:

*   The spelling is the text's but for ё, which Whisper writes or not as it
    pleases, and the stress mark, which a translation may carry.  Nothing else
    is folded: no British and American, no "Forward" for the Foreword.

*   **A number is one token, `#`, whatever its form.**  The translations'
    spoken text keeps its numbers in digits, since a Russian numeral agrees in
    case and gender with what it counts and the build does not decline
    (DECISIONS.md, Listening); the reader says "двадцать шесть", "Глава
    первая", "тысяча девятьсот тридцать четвёртом", and Whisper writes any of
    them in words or in digits as it likes.  Spelling a number out to compare
    it is therefore hopeless, and unnecessary: where a number stands in the
    text a number is heard.  So a run of digits, and each word that is a
    numeral, cardinal or ordinal in any of its forms, is `#` on both sides.
    A list's mark, "1.", is then its paragraph's first word heard, which the
    cut's cap needs (CLAUDE.md trap 16), and "Глава первая. Имя Отца." meets
    the heading's "1. Имя Отца."

    The numerals are a closed set, made here from their stems and endings.
    Words that only look like one are left alone: "сорока" the bird is the
    genitive of forty all the same, and costs nothing, a word of the text and
    the same word heard being `#` alike.
"""

from __future__ import annotations

import re

# A number in digits with what is written against it ("1-й", "10-го", "2,5"),
# or a word.  Latin too: a name the text leaves in it.
RE_TOKEN = re.compile(r"[0-9]+(?:[.,][0-9]+)*(?:-[а-я]{1,3}(?![а-я]))?|[a-zа-я]+")


def _forms() -> set[str]:
    out: set[str] = set()
    # One, two, three, four, and both: every form.
    out |= set("один одна одно одни одного одной одному одним одном одну одних одними одною".split())
    out |= set("два две двух двум двумя".split())
    out |= set("три трех трем тремя".split())
    out |= set("четыре четырех четырем четырьмя".split())
    # Five to twenty, and thirty: the third declension.
    for w in ("пять шесть семь восемь девять десять одиннадцать двенадцать тринадцать четырнадцать"
              " пятнадцать шестнадцать семнадцать восемнадцать девятнадцать двадцать тридцать").split():
        stem = w[:-1]
        out |= {w, stem + "и", stem + "ью"}
    out |= {"восьми", "восьмью", "восемью"}
    out |= set("сорок сорока девяносто девяноста сто ста полтора полторы полутора".split())
    # Fifty to eighty: both halves decline.
    for a, b in (("пять", "пяти"), ("шесть", "шести"), ("семь", "семи"), ("восемь", "восьми")):
        out |= {a + "десят", b + "десяти", a[:-1] + "ьюдесятью"}
    out |= set("двести двухсот двумстам двумястами двухстах триста трехсот тремстам тремястами трехстах"
               " четыреста четырехсот четыремстам четырьмястами четырехстах".split())
    for a, b in (("пять", "пяти"), ("шесть", "шести"), ("семь", "семи"), ("восемь", "восьми"),
                 ("девять", "девяти")):
        out |= {a + "сот", b + "сот", b + "стам", a[:-1] + "ьюстами", b + "стах"}
    out |= set("тысяча тысячи тысяче тысячу тысячей тысячью тысяч тысячам тысячами тысячах".split())
    for w in ("миллион", "миллиард", "триллион", "квадриллион", "квинтиллион", "секстиллион",
              "септиллион", "октиллион"):
        out |= {w + e for e in ("", "а", "у", "ом", "е", "ы", "ов", "ам", "ами", "ах")}
    # The ordinals: an adjective's endings on each stem.
    hard = "ый ая ое ые ого ой ому ым ом ую ых ыми ою".split()
    stressed = "ой ая ое ые ого ому ым ом ую ых ыми ою".split()
    for stem in ("перв четверт пят девят десят одиннадцат двенадцат тринадцат четырнадцат пятнадцат"
                 " шестнадцат семнадцат восемнадцат девятнадцат двадцат тридцат пятидесят шестидесят"
                 " семидесят восьмидесят девяност сот двухсот трехсот четырехсот пятисот шестисот"
                 " семисот восьмисот девятисот тысячн миллионн миллиардн").split():
        out |= {stem + e for e in hard}
    for stem in "втор шест седьм восьм сороков нулев".split():
        out |= {stem + e for e in stressed}
    out |= {"трет" + e for e in "ий ья ье ьи ьего ьей ьему ьим ьем ью ьих ьими ьею".split()}
    out |= {"ноль", "нуль", "ноля", "нуля"}
    return out


NUMERALS = frozenset(_forms())


def fold(text: str) -> str:
    return text.lower().replace("ё", "е").replace("́", "").replace("­", "")


# A Roman numeral, which in a Russian text is all a word of these Latin letters
# is: the label of 30:1.2, "I.", which he reads "Первое." and Whisper writes
# either way.  As a word it left the cut after the label, not before it.
RE_ROMAN = re.compile(r"[ivxl]+")


def tokens(text: str) -> list[str]:
    """The text's words in order, lower case, ё as е, each number as `#`."""
    return ["#" if w[0].isdigit() or w in NUMERALS or RE_ROMAN.fullmatch(w) else w
            for w in RE_TOKEN.findall(fold(text))]
