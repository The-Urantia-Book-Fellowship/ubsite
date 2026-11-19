"""Settings: what a reader may change, kept per browser; and for a reader who
is signed in, kept with the account too, all but the device's own (DEVICE),
so that they are the same on every device (ubsite/account.py).  No page is
drawn by the server from a setting: a reader's are put on the page by the
browser, from its own copy, as below.

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
# 'translations' (the list of them, ordered, below), 'language' (a segmented
# row whose choices are each written in its own language, never translated).
# A choice is (value, label, hint, css class).
READING = [
    # The interface's language: "en", "ru", or until one is chosen "auto", the
    # browser's own, Russian where it is Russian (Tigran, 2026-10-25;
    # ubsite/l10n.py).  base.html's head script resolves it, as ubLang(), to
    # data-lang="ru" or nothing.  Set by the flags at the header's corner, and
    # since 2026-11-10 here too, first in the tab the dialog opens at, where a
    # reader in the wrong language finds it (Tigran: the flags are not shown
    # on a phone).  Each choice is written in its own language, so that it is
    # found without reading the other; shown only while the site draws both
    # (l10n.py BILINGUAL), and kept through ↺ (SPARED).
    ("lang", "language", "Interface language", "auto",
     [("en", "English", "", ""),
      ("ru", "Русский", "", "")], ""),
    ("theme", "segmented", "Theme", "system",
     [("system", "System", "as this device is set", ""),
      ("light", "Light", "", ""),
      ("dark", "Dark", "", "")], ""),
    # The interface, 100% to 125% of the root size: everything set in rem
    # follows, the header, the Contents, the margin, Settings, the player, as
    # with the browser's zoom.  It was Text size until 2026-11-10, when Tigran
    # asked for a size of the interface beside the text's: Text size below
    # sets the reading text, which this leaves as it is (ub.css --ui).
    #
    # Four steps, 90%, 100% (Standard), 112.5% and 125% (Tigran, 2026-11-16:
    # "The current 'Smaller' size of both text and interface size make
    # 'Standard' and add one degree smaller as 'Smaller'. And the current
    # 'Standard' => 'Larger', 'Larger' => 'Largest'").  They were these four
    # until 2026-10-14, when he found 90% too small and every name moved up a
    # step, Standard 112.5% and no 90%; so the names have moved twice, and a
    # choice is now kept as its size, "90" to "125", which no later move of
    # the names can change.  The names kept before are read as what they
    # meant, `smaller` 100% and `larger` 125% (ub.css, ub.js stored()): a
    # reader who chose a size keeps it, and one who never chose has Standard,
    # a step smaller than it was.
    ("uisize", "segmented", "Interface text size", "100",
     [("90", "A", "Smaller", "a1"),
      ("100", "A", "Standard", "a2"),
      ("112.5", "A", "Larger", "a3"),
      ("125", "A", "Largest", "a4")], ""),
    # The reading text, in the same steps: whatever is sized from ub.css
    # --size, the book's paragraphs and verse, the translations, a note's or a
    # 1955 reading's card, the running text of Help or the home page, and the
    # paper's and the sections' heads with it, whatever the interface's size
    # (ub.css --tx).  The root's size until 2026-11-10 (above), so a reader
    # who chose a larger size then keeps a larger text, the interface
    # Standard.  A `largest` kept from before 2026-10-14 is 125% too.
    ("size", "segmented", "Text size", "100",
     [("90", "A", "Smaller", "a1"),
      ("100", "A", "Standard", "a2"),
      ("112.5", "A", "Larger", "a3"),
      ("125", "A", "Largest", "a4")], ""),
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
    # Measured keeps the line near 70 characters (68 until 2026-11-10, which it
    # never was) and the page in a frame of its
    # own; Full gives the text, the rail and the margin the whole window, for a
    # reader who minds empty screen more than a long line (Tigran, 2026-10-10).
    ("width", "segmented", "Width", "measure",
     [("measure", "Measured", "about 70 characters to a line", ""),
      ("full", "Full", "the whole width of the window", "")], ""),
    # Justified, as the book is, breaking a word only where the book lets it
    # (build/hyphen.py, paragraph.html_hy).  Ragged right for a reader who reads
    # better with even spaces: WCAG 1.4.8 asks that there be a way to it.
    ("align", "segmented", "Alignment", "justify",
     [("justify", "Justified", "hyphenated where the book hyphenates", ""),
      ("ragged", "Ragged right", "even spaces, no hyphens", "")], ""),
    # No Tap to turn the page since 2026-11-17 (Tigran; `tappage`, a switch
    # from 2026-10-20, off by default): a tap on a paragraph names it, for the
    # running head and the bar at the foot, and a tap that turned the page
    # could name none.  A browser that kept it on reads as if it were off, the
    # key being no setting.  The keys, Space and Page Down among them, turn the
    # page as they did (ub.js turn()).
    # The paragraph a reference points to, shown in a card of the notes' kind
    # where the pointer rests on the reference, in a note's card or endnote, a
    # 1955 card, an index entry or a search result; on a phone a tap shows it
    # instead of going there, and the reference at the card's head goes
    # (Tigran, 2026-11-07, for checking the notes' references on a desktop).
    # Off unless a reader asks: a card at every rest of the pointer distracts a
    # reader who follows none.  No CSS rule: ub.js reads it (pvOn), and lifts
    # the paragraph from its section's page, so nothing reaches the server.
    ("preview", "switch", "Paragraph previews", False, [],
     "the paragraph a reference points to, in a card where the pointer rests; on a phone, at a tap"),
    # The whole paper on one page, /15 (templates/paper.html), with the two
    # paper buttons alone at its end, for reading the book straight through
    # with every distraction off (Tigran, 2026-10-30).  The one setting with
    # no CSS rule: its effect is where an address of the book goes, decided
    # before first paint by base.html's ubUnit, since no setting reaches the
    # server -- on, a section's address opens the whole paper at that section;
    # off, a paper's opens its first section, as the server itself sent it
    # until then.  ub.js puts links right as they are clicked, and shows the
    # page again in the other unit when the dialog closes after a change.
    ("whole", "switch", "Whole paper", False, [],
     "the paper on one page, section after section, with only the paper buttons at its end"),
    # The Foreword listed in Part I, as the first of its papers, wherever the
    # parts are listed: the home page, /read, the left rail, the quiz's page and
    # the recordings' tree in the Offline tab (Tigran, 2026-11-04: "by default
    # make Part I include Foreword").  Off, it stands on its own before the
    # parts, as the press prints it.  Each list carries it both ways and the
    # CSS shows one (ub.css .fwin, .fwout), so no page changes with it; the
    # left rail's Part I, open for the Foreword, is shut by a line of script
    # where the switch is off (templates/_rail.html).  A site's profile is to
    # be able to fix it and take the switch out of the dialog (INTEGRATION.md,
    # section 4); SITE_DEFAULTS sets a site's default meanwhile.
    ("foreword", "switch", "Foreword in Part I", True, [],
     "wherever the parts are listed; off, it stands on its own before them"),
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
    # at their number as a 1955 reading is at its ring.  On by default
    # (Tigran, 2026-11-02; on from 2026-10-18, off from 2026-10-19), which a
    # site may change (SITE_DEFAULTS).  Named with the edition and its editor,
    # in the hint (Tigran, 2026-10-18).
    ("studynotes", "switch", "Notes", True, [],
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
    # No Quiz board since 2026-11-18 (Tigran; `quizboard`, a switch from
    # 2026-10-28, on by default, which hid the offer after a quiz to put a name
    # on the board, and the links to it): the offer can be left unanswered, and
    # nothing is sent before a reader takes it.  A browser that kept it off
    # reads as if it had no such key.  With Quiz off there is still no offer
    # and no link (ub.css .qboard, quiz.js boardOn).
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
# Until 2026-11-16 a switch stood under the list, `compare`, "Translations in
# parallel columns": the English and each translation ticked side by side, a
# column each (ub.js cmpDraw), and with it off a fold under each paragraph.
# Tigran: "Let's get rid of the option ... on the wide enough screen
# translations should be shown in parallel columns anyway and on the narrow
# screens they should be shown sequentially", and not as a phone against a
# desktop: a tablet may have room for two columns, and a wide screen none
# with the Contents and the index open.  So the page is in columns wherever
# each column would be wide enough, and in folds where it would not (ub.js
# cmpFits, ub.css --mincol).  A `compare` kept in a browser is left where it
# is and read by no one: it is no key of these lists.  Its history: a setting
# since 2026-11-08, and until then a pill at the head of the text, "Compare
# translations", at an address of its own, /1:1/compare, which the tab kept
# as one moved about (2026-11-06); those addresses go to the page's own
# (app.py read_compare).
SPEEDS = (0.8, 0.9, 1, 1.1, 1.25, 1.5)
LISTEN = [
    # Every listening control, the English text's and each translation's, on
    # or off at once (Tigran, 2026-10-27).  Until then Off was one of the
    # English's voices, stored as voice "off", which ub.js and the head script
    # read as this turned off.
    ("listen", "switch", "Listening controls", True, [],
     "the play buttons beside each paragraph, for the English text and the translations"),
    # The voices: a menu against each text, the English first, then each
    # translation shown, by its short name (groups()).  Tigran, 2026-11-13,
    # the day after a translation came to have a recording, which stood in its
    # menu with the browser's voices: "If you put 'Grigory Voyner' in the same
    # list as browser voices, then so should be Merritt Horn", and "There is
    # no need for the separate 'English text' section.  Just give the menu
    # list of voices against each text, starting with English."  Until then
    # the English text's recordings and "Your browser's voice" were radio
    # buttons under "English text" (his heading of 2026-10-27, "so it is clear
    # that it refers to English text", the row's name now), the browser's
    # voices a menu of their own under them, "Browser voice", and the
    # translations' menus under "Voices for the translations".
    # A menu lists the recordings of its text, then the browser's voices in
    # its language by name, which ub.js fills in, the best first; and each
    # once: until that day the browser's began with "Automatic: Google
    # русский", beside "Google русский" (Tigran: "what is the difference ...?
    # That is confusing and waste of space"; there was none to hear).  With
    # nothing chosen a text is read by its first recording, or with none by
    # the first of the browser's voices.
    # Three settings are set by these menus, and this one draws them, with a
    # hidden input for each (base.html).  It is the English text's voice: ''
    # the first the section has, a recording's key, or "browser".
    ("voice", "voices", "Voices", "", [], ""),
    # Which of the browser's voices reads the English text, with `voice`
    # "browser": a voice's name, '' the best there is (ub.js score).
    ("bvoice", "part", "", "", [], ""),
    # And each translation's voice, which reads it from its ▶ in parallel
    # columns (Tigran, 2026-10-27: "Settings should allow to configure
    # different voices for different translations").  One value for them all,
    # as `translations` is: {key: a browser voice's name} as JSON, "browser"
    # for the browser's best where a recording is the default (Григорий
    # Войнер's of USGNY, 2026-11-12); only those not the default, "" for none.
    ("trvoices", "part", "", "", [], ""),
    ("rate", "select", "Speed", 1, [(r, f"{r}×", "", "") for r in SPEEDS], ""),
    ("follow", "switch", "Follow along", True, [], "keep the paragraph being read in view"),
    # Off, playing stops at the end of a section (Tigran, 2026-10-07); on, it
    # carries on, across papers, through the whole book (2026-10-08).
    ("onward", "switch", "Carry on into the next section", False, [], "and so on through the book"),
]
# Work offline has a tab, Offline, and no setting in it: what it holds is the
# worker's, not a reader's choice to store (base.html, the panel's own markup;
# static/offline.js).  The copy is every browser's, fetched by itself (a tick
# from 2026-10-30 to 2026-11-10, which downloaded it and let it go), and is
# updated by itself whenever the site is open and online, without a word
# since 2026-11-10 (What's new at its end, and the page reloaded once that
# was closed, until then; it is in the ?'s menu now).  Until 2026-10-30 a switch
# here, "Keep the offline copy up to date" (`autoupdate`, on by default), could
# turn that off, leaving Update now in the cloud's menu to the reader; Tigran
# had the menu's work moved into this tab, and the tick do both.  A stored
# `autoupdate` is ignored.  The switch is back since 2026-11-10, "Automatic
# updates", under Base (Tigran: with the copy every browser's, a reader must
# be able to keep the one they have), and is still no setting: the worker
# keeps it (sw.js meta.auto), which must know it before any script of the
# page runs, so the box has no name, nothing is stored here, and ↺ leaves it
# as it is, as it leaves the translations kept.  Shown only where Work
# offline can run: ub.js unhides the tab with the cloud.
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

# The device's own: what a reader signed in keeps on each device apart, where
# every other setting follows the account from one device to another (Tigran,
# 2026-11-18; ubsite/account.py, static/account.js).  The two text sizes, the
# line spacing and the width, which are chosen for a screen; the browser's
# voices, which are the device's; and what is folded.  Whole paper follows the
# account (his ruling the same day), and so does the language.  The browser
# sends none of these, and the server takes none (followed()).
DEVICE = ["uisize", "size", "lead", "width", "bvoice", "trvoices", "rail", "margin", "trtab", "toc"]


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

# The hosts whose pages offer to sign in (ubsite/account.py; Tigran,
# 2026-11-18): at Settings' foot, where the dialog says where a reader's
# settings are kept, and not in a tab of its own, a sixth tab running past the
# dialog's edge on a phone (his choice the same day).  Chosen in the page from
# location.hostname, as a site's defaults are, since the offline copy is one
# for every host and a stored page cannot know which host has accounts.  A
# host named here must have its var/account.toml, or the link leads to a 404.
# The dev server alone until signing in and what follows the account are
# deployed together.
ACCOUNT_HOSTS: list[str] = ["localhost"]


# A setting that means nothing while another is off ('off', or a switch turned
# off): shown, greyed, and not to be changed (ub.js disables it).  With
# Listening off there is no voice or speed to set (Tigran, 2026-10-08), and with
# the 1955 readings off no reading to search for, nor with the index or the
# study notes off any of theirs.  A pair is a setting that means something
# only while another has that value: none since 2026-11-13, when the menu of
# the browser's voices, which meant something while the browser's voice was
# chosen, went into the English text's own.  A setting whose own needs are
# not met greys those that need it too.  An empty list is unmet too
# (`translations` being '' with none ticked), which the switch for the
# translations in columns needed until 2026-11-16, and nothing does now.
NEEDS = {"voice": "listen", "rate": "listen",
         "follow": "listen", "onward": "listen", "notesearch": "notes",
         "indexsearch": "index", "studysearch": "studynotes"}


def _item(key, kind, label, default, choices, hint) -> dict:
    needs = NEEDS.get(key, "")
    needs, needs_is = needs if isinstance(needs, tuple) else (needs, "")
    return {"key": key, "kind": kind, "label": label, "default": default, "hint": hint,
            "needs": needs, "needs_is": needs_is,
            "choices": [{"value": v, "label": l, "hint": h, "cls": c} for v, l, h, c in choices]}


# The browser's own voice (the Web Speech API) is no recording: the browser
# speaks the text itself.  What it sounds like depends on the browser and the
# device -- Google's voices in Chrome, Microsoft's in Edge, Apple's in Safari --
# and nobody can check what it says (Tigran, 2026-10-08).


def groups(voices: list[dict], translations: list[dict] = ()) -> list[dict]:
    """The dialog's tabs, in order, each with its key for the ids (base.html).
    `voices` are app.voices() and `translations` app.translations(): the
    texts, each with a menu of its voices in Listening, the English first
    (its `value` '', and its name the interface's words; a translation's is
    its key and its short name, never translated)."""
    def recordings(of):
        return [{"key": v["key"], "label": v["label"],
                 "hint": v.get("credit") or ("an AI voice" if v["kind"] == "synthetic" else "")}
                for v in voices if v.get("tr") == of]
    items = [_item(*s) for s in LISTEN]
    for it in items:
        if it["kind"] == "voices":
            it["choices"] = [{"value": "", "label": "English text", "lang": "en", "rec": recordings(None)}] + [
                {"value": x["key"], "label": x["label"], "lang": x["lang"], "rec": recordings(x["key"])}
                for x in translations]
    return [{"key": "reading", "legend": "Reading", "items": [_item(*s) for s in READING]},
            {"key": "show", "legend": "Show", "items": [_item(*s) for s in SHOW]},
            {"key": "translations", "legend": "Translations", "items": [_item(*s) for s in TRANSLATIONS]},
            {"key": "listening", "legend": "Listening", "items": items},
            {"key": "offline", "legend": "Offline", "items": [_item(*s) for s in OFFLINE], "cls": "offline"}]


def defaults() -> dict:
    """{key: default} for every setting, for the head script and ub.js."""
    return {s[0]: s[3] for s in READING + SHOW + TRANSLATIONS + LISTEN + OFFLINE + KEPT}


def followed() -> dict:
    """{key: default} for the settings that follow an account: every one but
    the device's own (DEVICE), each of which must be a setting."""
    base = defaults()
    for k in DEVICE:
        if k not in base:
            raise ValueError(f"settings.DEVICE: {k!r} is no setting")
    return {k: v for k, v in base.items() if k not in DEVICE}


def site_defaults() -> dict:
    """SITE_DEFAULTS, each checked against the settings it names."""
    base = defaults()
    for host, d in SITE_DEFAULTS.items():
        for k, v in d.items():
            if k not in base or type(v) is not type(base[k]):
                raise ValueError(f"settings.SITE_DEFAULTS[{host!r}]: {k}={v!r}")
    return SITE_DEFAULTS
