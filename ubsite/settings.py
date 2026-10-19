"""Settings: what a reader may change, kept per browser, with no account.

Every setting is declared here, once:

  - base.html renders the dialog from SETTINGS;
  - the head script in base.html gets each default (`defaults`) and, before
    first paint, sets data-<key> on <html> for every stored value that differs
    from its default ('off' for a switch turned off, else the value itself);
  - ub.css keys its rules off those attributes: :root[data-size="larger"];
  - ub.js keeps the values in localStorage under 'ub_settings', runs the
    dialog, and announces each change as the event 'ub:settings', which
    listen.js follows.

So a new setting is an entry here and its rule in ub.css.  A value's type is
its default's: a switch is a bool, the speed a number, the rest strings.  A
setting in KEPT is remembered the same way but has no place in the dialog: it
is set where it is used.
"""

from __future__ import annotations

from markupsafe import Markup

# (key, kind, label, default, choices, hint).  kind: 'switch' (a checkbox),
# 'segmented' (a row of radio buttons), 'radio' (a list of them), 'select'.
# A choice is (value, label, hint, css class).
READING = [
    ("theme", "segmented", "Theme", "system",
     [("system", "System", "as this device is set", ""),
      ("light", "Light", "", ""),
      ("dark", "Dark", "", "")], ""),
    # 100% to 125% of the root size: everything set in rem follows, the margin
    # and the header too, as with the browser's zoom.  Until 2026-10-14 the
    # steps were 90%, 100% (Standard), 112.5% and 125% (Largest); Tigran found
    # 90% too small, and moved every name up a step, so Standard is 112.5%.
    # A stored 'largest' is read as 'larger' (ub.js stored(), ub.css).
    ("size", "segmented", "Text size", "standard",
     [("smaller", "A", "Smaller", "a2"),
      ("standard", "A", "Standard", "a3"),
      ("larger", "A", "Larger", "a4")], ""),
    # The leading: 1.05, 1.1 (the printed book's), 1.25 and 1.45 (ub.css).  It
    # was 1.55 for everyone, which Tigran found too open, worst on a phone; he
    # chose these steps and 1.25 for the default (2026-10-12).  A 1955 reading's
    # ring comes down as the lines close up, or it would run into the line
    # above.  Each choice is drawn, three bars as far apart as its lines (ub.css
    # .sp1 to .sp4), so its hint is its name.
    ("lead", "segmented", "Line spacing", "standard",
     [("tightest", "", "Tightest", "sp1"),
      ("tighter", "", "Tighter", "sp2"),
      ("standard", "", "Standard", "sp3"),
      ("looser", "", "Looser", "sp4")], ""),
    # UB Goudy is the book's own face.  Its x-height is small, and some readers
    # will want one that reads larger at the same size; the other two are the
    # device's own, so nothing more is downloaded.  Goudy's licence, the OFL,
    # is linked from its hint; until 2026-10-18 the footer named the face the
    # text was in, with it (Tigran).
    ("face", "radio", "Typeface", "goudy",
     [("goudy", "Goudy", Markup('the book’s own typeface (<a href="/static/fonts/OFL.txt">OFL&nbsp;1.1</a>)'),
       "face-goudy"),
      ("serif", "A plainer serif", "", "face-serif"),
      ("sans", "Sans-serif", "", "face-sans")], ""),
    # Measured keeps the line near 68 characters and the page in a frame of its
    # own; Full gives the text, the rail and the margin the whole window, for a
    # reader who minds empty screen more than a long line (Tigran, 2026-10-10).
    ("width", "segmented", "Width", "measure",
     [("measure", "Measured", "about 68 characters to a line", ""),
      ("full", "Full", "the whole width of the window", "")], ""),
    # Justified, as the book is, breaking a word only where the book lets it
    # (build/hyphen.py, paragraph.html_hy).  Ragged right for a reader who reads
    # better with even spaces: WCAG 1.4.8 asks that there be a way to it.
    ("align", "segmented", "Alignment", "justify",
     [("justify", "Justified", "hyphenated where the book hyphenates", ""),
      ("ragged", "Ragged right", "even spaces, no hyphens", "")], ""),
]
SHOW = [
    # Off, the site is the book alone, with its 1955 readings if they are on:
    # the margin, the box of what a whole section or paper cites, the Index
    # button, the index's lines in search and on the home page, and every link
    # to the index and the appendices (ub.css .ix).  Their own pages stay as
    # they are, for an address asked for.  Promised to the Fellowship on
    # 2026-10-17 (Tigran, 2026-10-18).
    ("index", "switch", "Index and appendices", True, [],
     "beside the text, in search results, and every link to them"),
    ("redletter", "switch", "Words of Jesus in red", True, [], ""),
    ("paranum", "switch", "Paragraph references", True, [], "such as 0:1.2, beside each paragraph"),
    # Where each paragraph begins in the 1955 first printing.  Obsolete as a way
    # to cite the book, so off unless a reader asks (Tigran, 2026-10-11).
    ("pages", "switch", "1955 page references", False, [], "such as (1109.3): page, and paragraph on it"),
    ("pilcrow", "switch", "Pilcrows", True, [], "where the 1955 text leaves a blank line"),
    # The British Study Edition's notes, each read, checked and edited before it
    # is shown (build/study.py, data/study/), numbered in each paper and opened
    # at their number as a 1955 reading is at its ring.  On by default
    # (Tigran, 2026-10-18), which a site may change (SITE_DEFAULTS).  Named
    # with the edition and its editor, in the hint (Tigran, the same day).
    ("studynotes", "switch", "Notes", True, [],
     "from The British Study Edition (ed. Tigran Aivazian)"),
    ("notes", "switch", "1955 readings", True, [], ""),
    # What the 1955 cards say, listed among the search results: the reading,
    # and the SRT Committee's reasons beneath it.  Off unless a reader asks
    # (Tigran, 2026-10-12).
    ("notesearch", "switch", "1955 readings in search results", False, [],
     "their wording, such as Badanon, and the committee\u2019s reasons"),
    # The browser's own, drawn from a title="", which no stylesheet can hide:
    # ub.js takes every title off the page while this is off, and puts them
    # back (Tigran, 2026-10-14).  The icons keep their aria-labels.
    ("tips", "switch", "Tooltips", True, [], "a few words on a button or a link, where the pointer rests"),
]
SPEEDS = (0.8, 0.9, 1, 1.1, 1.25, 1.5)
LISTEN = [
    # The choices are the database's voices (app.voices), the browser's own,
    # then Off; '' is the first voice the section has.
    ("voice", "radio", "Listen with", "", [], ""),
    # Which of the browser's voices: its English ones, filled in by ub.js,
    # which also says which '' picks.  Always shown, and greyed unless that
    # voice is chosen: until 2026-10-16 it was shown only then, and the dialog
    # jumped as the line came and went (Tigran).
    ("bvoice", "select", "Browser voice", "", [("", "Automatic", "", "")], ""),
    ("rate", "select", "Speed", 1, [(r, f"{r}×", "", "") for r in SPEEDS], ""),
    ("follow", "switch", "Follow along", True, [], "keep the paragraph being read in view"),
    # Off, playing stops at the end of a section (Tigran, 2026-10-07); on, it
    # carries on, across papers, through the whole book (2026-10-08).
    ("onward", "switch", "Carry on into the next section", False, [], "and so on through the book"),
]


# Remembered like the rest, but set where it is used, not in the dialog.  The
# left rail folded away to the left on a wide screen, by the button at its head
# (templates/_rail.html); open by default.  A phone's rail is folded on every
# page and is not remembered (Tigran, 2026-10-13).  The index folded, by the
# button at the head of a section page and of a reading path
# (templates/_fold.html): away to the right on a wide screen, each box of
# entries to one line on a phone.  It was the dialog's "Index entries beside
# the text", which hid the index, until the button made it one more way to
# the same thing on every page that has an index (Tigran, 2026-10-13); its key
# and its values stay, so a reader who had it off finds the index folded.
# What hides the index is SHOW's `index` (2026-10-18), which leaves this as it
# was for when the index comes back.
KEPT = [
    ("rail", "kept", "Contents", "open", [], ""),
    ("margin", "kept", "Index", True, [], ""),
]


# A site's own defaults, by the host a page is read at, where they differ from
# those above: {"read.urantiabook.org": {"studynotes": False}}.  The Fellowship
# decides what its readers see on its site, and a reader can still change it
# (Tigran, 2026-10-17 and 18).  Chosen in the page, by base.html's head script
# from location.hostname, as the tab's icon is, since the offline copy is one
# for every host.  The CSS is written against the defaults above, whatever the
# host: a value is marked on <html> where it differs from those, and only what
# differs from the host's is stored, and ↺ restores the host's.  Empty until
# the Fellowship's site exists.
SITE_DEFAULTS: dict[str, dict] = {}


# A setting that means nothing while another is off ('off', or a switch turned
# off): shown, greyed, and not to be changed (ub.js disables it).  With
# Listening off there is no speed to set (Tigran, 2026-10-08), and with the 1955
# readings off no reading to search for.  A pair is a setting that means
# something only while another has that value: which of the browser's voices,
# while the browser's voice is chosen.
NEEDS = {"bvoice": ("voice", "browser"), "rate": "voice", "follow": "voice", "onward": "voice",
         "notesearch": "notes"}


def _item(key, kind, label, default, choices, hint) -> dict:
    needs = NEEDS.get(key, "")
    needs, needs_is = needs if isinstance(needs, tuple) else (needs, "")
    return {"key": key, "kind": kind, "label": label, "default": default, "hint": hint,
            "needs": needs, "needs_is": needs_is,
            "choices": [{"value": v, "label": l, "hint": h, "cls": c} for v, l, h, c in choices]}


# The browser's own voice (the Web Speech API): no recording, the browser
# speaks the text itself.  What it sounds like depends on the browser and the
# device -- Google's voices in Chrome, Microsoft's in Edge, Apple's in Safari --
# and nobody can check what it says (Tigran, 2026-10-08).
BROWSER = {"value": "browser", "label": "Your browser\u2019s voice", "cls": "v-browser",
           "hint": "spoken by this browser, which keeps the screen on while it reads"}


def groups(voices: list[dict]) -> list[dict]:
    """The dialog's fieldsets, in order."""
    items = [_item(*s) for s in LISTEN]
    items[0]["choices"] = [
        {"value": v["key"], "label": v["label"], "cls": "",
         "hint": v.get("credit") or ("an AI voice" if v["kind"] == "synthetic" else "")}
        for v in voices] + [BROWSER, {"value": "off", "label": "Off", "hint": "no listening controls", "cls": ""}]
    return [{"legend": "Reading", "items": [_item(*s) for s in READING]},
            {"legend": "Show", "items": [_item(*s) for s in SHOW]},
            {"legend": "Listening", "items": items}]


def defaults() -> dict:
    """{key: default} for every setting, for the head script and ub.js."""
    return {s[0]: s[3] for s in READING + SHOW + LISTEN + KEPT}


def site_defaults() -> dict:
    """SITE_DEFAULTS, each checked against the settings it names."""
    base = defaults()
    for host, d in SITE_DEFAULTS.items():
        for k, v in d.items():
            if k not in base or type(v) is not type(base[k]):
                raise ValueError(f"settings.SITE_DEFAULTS[{host!r}]: {k}={v!r}")
    return SITE_DEFAULTS
