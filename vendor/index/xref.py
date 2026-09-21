"""The cross-reference target grammar -- one home, three consumers.

A `See`, a `See also` and a `q.v.` all name something the reader is expected to
find, and deciding whether they reach it needs the same four rules every time:
how a target is normalised for comparison, which list markers are decoration
rather than part of the name, when one target names more than one headword, and
what a `#a - #b` range means.

Those rules were in three places and not the same three.  `errata.py` had all
four; `check_xrefs.py` had the first; `check_tex.py` -- the gate that runs over
the master -- had only a bare string match, so it could not see `q.v.` at all
and reported the index's one documented range convention as a dead reference.
CLAUDE.md section 13 item 8 asked for exactly this module.

Nothing here knows about our data files or our .tex.  A caller supplies the set
of folded level-1 headwords; this decides what a target names.
"""

import re
import unicodedata


def fold(s):
    """The comparison key for a headword or a cross-reference target.

    The printing varies case and punctuation between a headword and the
    references to it, and neither variation is a defect -- so this forgives
    both.  A caller that needs to know whether the index *says* what it says,
    rather than whether a reader can get there, must compare exactly instead;
    see the CASE class in errata.py.
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]", " ", s.lower())).strip()


# List markers that are not part of the target: `4.', `6a.', `1st.', `A.', and
# the one combined form `6. & 7.' the printing uses on page 239.
RE_ITEM = re.compile(r"^(?:\d+[a-z]?\.|\d+(?:st|nd|rd|th)\.|[A-Z]\.)"
                     r"(?:\s*&\s*(?:\d+[a-z]?\.|\d+(?:st|nd|rd|th)\.))?\s*")

# `Master Spirit #1 - #7' names seven headwords, not one (CLAUDE.md section 8).
RE_HASH_RANGE = re.compile(r"^(.*?)#(\d+)\s*[-–]\s*#(\d+)$")


def readings(text):
    """Every string a target on this entry could be naming.

    The list marker is stripped speculatively rather than unconditionally: a
    lone capital and a period also spells the abbreviated headword (``A.`` for
    Adam), and stripping that would silently change what is being looked up.
    Both readings are offered and the caller keeps whichever resolves.
    """
    text = text.strip()
    out = [text]
    stripped = RE_ITEM.sub("", text).strip()
    if stripped and stripped != text:
        out.append(stripped)
    return out


def expand_range(target):
    """``X #a - #b`` -> ``[X #a, ..., X #b]``, or ``[]`` if it is not a range."""
    m = RE_HASH_RANGE.match(target.strip())
    if not m:
        return []
    stem, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
    if hi < lo or hi - lo > 30:
        return []
    return ["%s#%d" % (stem, n) for n in range(lo, hi + 1)]


# One target naming several headwords, joined by `and' or by a comma:
# `Secrets of Greatness and Souls of Goodness q.v.' is one entry pointing at
# two, and so is `1. Creator Sons, local universe Mother Spirits q.v.'
#
# The comma form is why this is written down rather than left to the caller.
# It used to resolve only by accident: fold() drops the comma, so
# `Creator Sons, local universe Mother Spirits' folded to the same string as
# the ancestor path `Creator Sons > local universe Mother Spirits' and matched
# that instead.  A coincidence that holds for one entry is not a rule, and the
# next comma-joined target would have been reported as a dead reference.
RE_CONJUNCTION = re.compile(r"\s+and\s+|\s*,\s*")


def resolves(heads, target, paths=None):
    """Does *target* name something a reader can find?

    *heads* is the set of folded level-1 headwords; *paths*, if given, the set
    of folded ancestor paths, which is what lets a qualified sub-entry
    (``Buddhism: doctrines``) resolve.

    Three ways to succeed, in the order they are tried: the target names a
    headword, with or without its list marker; it is a conjunction and every
    part names one; or it is a ``#a - #b`` range and every member exists.
    """
    for reading in readings(target):
        if fold(reading.split(":")[0]) in heads:
            return True
        if paths is not None and fold(reading) in paths:
            return True
        parts = [p.strip() for p in RE_CONJUNCTION.split(reading) if p.strip()]
        if len(parts) > 1 and all(fold(p) in heads for p in parts):
            return True
    members = expand_range(target)
    return bool(members) and all(fold(m) in heads for m in members)
