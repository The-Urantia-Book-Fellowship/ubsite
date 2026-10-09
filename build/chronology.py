"""Parse an Appendix A year label into something sortable.

The labels are free text and deliberately various -- '987,000,000,000 years
ago', '8 B.C.', '200 to 300 A.D.', '1034 A.D.±'.  The note printed in the volume
says a trailing ± means the date is approximate.

A range ('100,000 to 85,000 years ago', '200 to 300 A.D.') sorts by its first
endpoint -- the earliest -- so the timeline places it where it begins.

Returns (year_sort, approximate) where year_sort is signed years relative to
A.D. 1, or (None, ...) when the label does not match the grammar -- in which
case the caller reports it rather than guessing.  A timeline that silently
invents a coordinate is worse than one that admits a gap.
"""

from __future__ import annotations

import re

RE_AGO = re.compile(r"^([\d,]+)(?:\s+to\s+[\d,]+)?\s+years?\s+ago$", re.I)
RE_ERA = re.compile(r"^(?:(?:about|circa|c\.)\s+)?([\d,]+)"
                    r"(?:\s+to\s+[\d,]+)?\s*(B\.C\.|A\.D\.)$", re.I)

# "years ago" is measured from the present; the revelation was indited in 1934/5
# and the volume's own chronology is reckoned that way.
PRESENT = 1934


def parse_year(label: str) -> tuple[float | None, bool]:
    s = label.strip()
    # '±' is the volume's own marker for an approximate date; '?' is the same
    # editorial uncertainty the citation grammar spells the same way (45:4.5?).
    approx = False
    while s and s[-1] in "±?":
        approx = True
        s = s[:-1].strip()

    m = RE_AGO.match(s)
    if m:
        return -(float(m.group(1).replace(",", "")) - PRESENT), approx

    m = RE_ERA.match(s)
    if m:
        n = float(m.group(1).replace(",", ""))
        return (-n if m.group(2).upper() == "B.C." else n), approx

    return None, approx


# A heading in print stands above its events; a chip or a search hit has none,
# so the date goes on the line.  Seven events are finished by that heading --
# "Paul dies prior to" under 82 A.D., "Zacharias dies by" under July of 12 A.D.
# -- and a date set in front of them reads as nonsense, so for those it follows.
# Recognised by the last word, from a closed list; data/ has no other signal.
RE_READS_ON = re.compile(r"\b(?:by|until|till|from|to|since|before|after)$")


def one_line(year: str, month: str | None, text: str) -> tuple[str, bool]:
    """(the event with its date, whether the date follows it).

    A day takes a comma before its year, "January 14, 26 A.D."; a month alone
    takes "of", because "December, 25 A.D." reads as nothing and "December
    25 A.D." as a day that is not meant.
    """
    if not month:
        date = year
    elif re.search(r"\d", month):
        date = f"{month}, {year}"
    else:
        date = f"{month} of {year}"
    if RE_READS_ON.search(text):
        return f"{text} {date}", True
    return f"{date}: {text}", False
