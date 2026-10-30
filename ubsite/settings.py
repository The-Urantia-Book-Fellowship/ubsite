"""Settings: what a reader may change, kept per browser, with no account.

Every setting is declared here, once:

  - base.html renders the dialog from them, a tab to each group (groups());
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
# 'segmented' (a row of radio buttons), 'radio' (a list of them), 'select',
# 'translations' (the list of them, ordered, below).
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
    # A tap on the text turns the page, on a phone or a tablet, as the volume
    # keys would in a reading app: Chrome never lets a web page have them
    # (Tigran, 2026-10-20).  Off unless a reader asks, since a tap on the text
    # otherwise does nothing, and may be made without meaning it.  The keys,
    # Space and Page Down among them, turn it always (ub.js turn()).
    ("tappage", "switch", "Tap to turn the page", False, [],
     "on a phone or a tablet: the lower half of the screen goes on, the upper half back"),
]
SHOW = [
    # Off, the site is the book alone, with its 1955 readings if they are on:
    # the margin, the box of what a whole section or paper cites, the Index
    # button, the index's lines in search and on the home page, and every link
    # to the index and the appendices (ub.css .ix).  Their own pages stay as
    # they are, for an address asked for.  Promised to the Fellowship on
    # 2026-10-17 (Tigran, 2026-10-18).
    ("index", "switch", "Index and appendices", True, [],
     "beside the text, and every link to them"),
    # The index among the search results, Headwords and In the index, while
    # the index is shown: off, a reader who searches finds the book and leaves
    # the index beside it.  /search?in=index still answers an address asked
    # for (Tigran, 2026-10-28).
    ("indexsearch", "switch", "Index and appendices in search results", True, [],
     "headwords, and the entries the words are found in"),
    ("redletter", "switch", "Words of Jesus in red", True, [], ""),
    ("paranum", "switch", "Paragraph references", True, [], "such as 0:1.2, beside each paragraph"),
    # Where each paragraph begins in the 1955 first printing.  Obsolete as a way
    # to cite the book, so off unless a reader asks (Tigran, 2026-10-11).
    ("pages", "switch", "1955 page references", False, [], "such as (1109.3): page, and paragraph on it"),
    ("pilcrow", "switch", "Pilcrows", True, [], "where the 1955 text leaves a blank line"),
    # The British Study Edition's notes, each read, checked and edited before it
    # is shown (build/study.py, data/study/), numbered in each paper and opened
    # at their number as a 1955 reading is at its ring.  Off unless a reader
    # asks (Tigran, 2026-10-19; on from 2026-10-18), which a site may change
    # (SITE_DEFAULTS).  Named with the edition and its editor, in the hint
    # (Tigran, 2026-10-18).
    ("studynotes", "switch", "Notes", False, [],
     "from The British Study Edition (ed. Tigran Aivazian)"),
    # The study notes among the search results, while the notes are shown;
    # /search?in=study still answers (Tigran, 2026-10-28).
    ("studysearch", "switch", "Notes in search results", True, [], ""),
    ("notes", "switch", "1955 readings", True, [], ""),
    # What the 1955 cards say, listed among the search results: the reading,
    # and the SRT Committee's reasons beneath it.  Off unless a reader asks
    # (Tigran, 2026-10-12).
    ("notesearch", "switch", "1955 readings in search results", False, [],
     "their wording, such as Badanon, and the committee\u2019s reasons"),
    # The translations ticked under Translations among the search results,
    # each a list of its own.  Here and not in that tab, since it is about
    # search, and never greyed: with none ticked it has nothing to hide (Tigran,
    # 2026-10-28).  /search?in=ud still answers.
    ("trsearch", "switch", "Translations in search results", True, [],
     "those ticked under Translations, their words and their translators\u2019 notes"),
    # The British Study Edition's quiz (build/quiz.py): the invitation after
    # the last paragraph of each paper that has questions, and its line on the
    # home page.  /quiz and /quiz/N answer an address asked for, as the index's
    # pages do (Tigran, 2026-10-28).
    ("quiz", "switch", "Quiz", True, [], "questions at the end of a paper, and on the home page"),
    # Its board (ubsite/board.py): after a quiz, the offer to put a name on it,
    # and the links to it; off, quiz.js sends nothing at all (Tigran,
    # 2026-10-28).  A site may turn it off (SITE_DEFAULTS).
    ("quizboard", "switch", "Quiz board", True, [], "the offer to put your name on it, and the links to it"),
    # The browser's own, drawn from a title="", which no stylesheet can hide:
    # ub.js takes every title off the page while this is off, and puts them
    # back (Tigran, 2026-10-14).  The icons keep their aria-labels.
    ("tips", "switch", "Tooltips", True, [], "a few words on a button or a link, where the pointer rests"),
]
# The translations shown beside the text (ROADMAP item 15, step 2; Tigran,
# 2026-10-26): those a reader ticks, in the order they set, the keys of
# data/translations.toml separated by spaces, which a fold's tabs follow.  None
# unless a reader asks: until one is ticked, every page is as it was.  A string,
# not a list, so that every path here and in ub.js takes it as it takes the
# rest.  The dialog draws the list of them from the database (app.py
# translations()), and ub.js keeps it.
TRANSLATIONS = [
    ("translations", "translations", "Translations", "", [], ""),
]
SPEEDS = (0.8, 0.9, 1, 1.1, 1.25, 1.5)
LISTEN = [
    # Every listening control, the English text's and each translation's, on
    # or off at once (Tigran, 2026-10-27).  Until then Off was one of the
    # English's voices, stored as voice "off", which ub.js and the head script
    # read as this turned off.
    ("listen", "switch", "Listening controls", True, [],
     "the play buttons beside each paragraph, for the English text and the translations"),
    # How the English text is read (Tigran, 2026-10-27: "so it is clear that it
    # refers to English text"): the database's voices (app.voices), then the
    # browser's own; '' is the first voice the section has.
    ("voice", "radio", "English text", "", [], ""),
    # Which of the browser's voices: its English ones, filled in by ub.js,
    # which also says which '' picks.  Always shown, and greyed unless that
    # voice is chosen: until 2026-10-16 it was shown only then, and the dialog
    # jumped as the line came and went (Tigran).
    ("bvoice", "select", "Browser voice", "", [("", "Automatic", "", "")], ""),
    # And each translation's, which reads it aloud from its ▶ in Compare
    # (Tigran, 2026-10-27): a menu for each, of the browser's voices in its
    # language, filled in by ub.js, shown while it is ticked (groups()).  One
    # value for them all, as `translations` is: {key: voice's name} as JSON,
    # only those not Automatic, "" for none.
    ("trvoices", "trvoices", "Browser voices for the translations", "", [], ""),
    ("rate", "select", "Speed", 1, [(r, f"{r}×", "", "") for r in SPEEDS], ""),
    ("follow", "switch", "Follow along", True, [], "keep the paragraph being read in view"),
    # Off, playing stops at the end of a section (Tigran, 2026-10-07); on, it
    # carries on, across papers, through the whole book (2026-10-08).
    ("onward", "switch", "Carry on into the next section", False, [], "and so on through the book"),
]
# Work offline has a tab, Offline, and no setting in it: what it holds is the
# worker's, not a reader's choice to store (base.html, the panel's own markup;
# static/offline.js).  The copy's tick downloads it and lets it go, and a kept
# copy is updated by itself whenever the site is open and online, then What's
# new, and the page reloaded once that is closed.  Until 2026-10-30 a switch
# here, "Keep the offline copy up to date" (`autoupdate`, on by default), could
# turn that off, leaving Update now in the cloud's menu to the reader; Tigran
# had the menu's work moved into this tab, and the tick do both.  A stored
# `autoupdate` is ignored.  Shown only where Work offline can run: ub.js
# unhides the tab with the cloud.
OFFLINE: list[tuple] = []


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
    # The interface's language, set by the flags at the header's corner:
    # "en", "ru", or until a flag is tapped "auto", the browser's own, Russian
    # where it is Russian (Tigran, 2026-10-25; ubsite/l10n.py).  base.html's
    # head script resolves it, as ubLang(), to data-lang="ru" or nothing.
    ("lang", "kept", "Language", "auto", [], ""),
    # The tab last chosen in a fold of translations, which the next fold opens
    # at (Tigran, 2026-10-26): a translation's key, "all", or "" for the first.
    ("trtab", "kept", "Translation", "", [], ""),
    # The contents in the left rail as a translation gives them, chosen on the
    # rail's line (Tigran, 2026-10-27; ub.js tocApply): a translation's key, or
    # "" for the book's own.  One no longer ticked reads as "".
    ("toc", "kept", "Contents", "", [], ""),
]
# Kept through ↺ "Restore the defaults": a reader who chose Russian and resets
# the settings is not handed an English page (Tigran, 2026-10-25).
SPARED = ["lang"]


# A site's own defaults, by the host a page is read at, where they differ from
# those above: {"read.urantiabook.org": {"pages": True}}.  The Fellowship
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
# Listening off there is no voice or speed to set (Tigran, 2026-10-08), and with
# the 1955 readings off no reading to search for, nor with the index or the
# study notes off any of theirs.  A pair is a setting that means something
# only while another has that value: which of the browser's voices, while the
# browser's voice is chosen.  A setting whose own needs are not met greys
# those that need it too: the browser's voices with Listening off.
NEEDS = {"voice": "listen", "bvoice": ("voice", "browser"), "trvoices": "listen", "rate": "listen",
         "follow": "listen", "onward": "listen", "notesearch": "notes",
         "indexsearch": "index", "studysearch": "studynotes", "quizboard": "quiz"}


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


def groups(voices: list[dict], translations: list[dict] = ()) -> list[dict]:
    """The dialog's tabs, in order, each with its key for the ids (base.html).
    `translations` are app.translations(), each with a menu of its own in
    `trvoices`; with none, it is not drawn."""
    items = [_item(*s) for s in LISTEN]
    for it in items:
        if it["key"] == "voice":
            it["choices"] = [
                {"value": v["key"], "label": v["label"], "cls": "",
                 "hint": v.get("credit") or ("an AI voice" if v["kind"] == "synthetic" else "")}
                for v in voices] + [BROWSER]
        if it["kind"] == "trvoices":
            it["choices"] = [{"value": x["key"], "label": x["label"], "lang": x["lang"]} for x in translations]
    items = [it for it in items if it["kind"] != "trvoices" or it["choices"]]
    return [{"key": "reading", "legend": "Reading", "items": [_item(*s) for s in READING]},
            {"key": "show", "legend": "Show", "items": [_item(*s) for s in SHOW]},
            {"key": "translations", "legend": "Translations", "items": [_item(*s) for s in TRANSLATIONS]},
            {"key": "listening", "legend": "Listening", "items": items},
            {"key": "offline", "legend": "Offline", "items": [_item(*s) for s in OFFLINE], "cls": "offline"}]


def defaults() -> dict:
    """{key: default} for every setting, for the head script and ub.js."""
    return {s[0]: s[3] for s in READING + SHOW + TRANSLATIONS + LISTEN + OFFLINE + KEPT}


def site_defaults() -> dict:
    """SITE_DEFAULTS, each checked against the settings it names."""
    base = defaults()
    for host, d in SITE_DEFAULTS.items():
        for k, v in d.items():
            if k not in base or type(v) is not type(base[k]):
                raise ValueError(f"settings.SITE_DEFAULTS[{host!r}]: {k}={v!r}")
    return SITE_DEFAULTS
