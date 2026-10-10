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
its default's: a switch is a bool, the speed a number, the rest strings.
"""

from __future__ import annotations

# (key, kind, label, default, choices, hint).  kind: 'switch' (a checkbox),
# 'segmented' (a row of radio buttons), 'radio' (a list of them), 'select'.
# A choice is (value, label, hint, css class).
READING = [
    ("theme", "segmented", "Theme", "system",
     [("system", "System", "as this device is set", ""),
      ("light", "Light", "", ""),
      ("dark", "Dark", "", "")], ""),
    # 90% to 125% of the root size: everything set in rem follows, the margin
    # and the header too, as with the browser's zoom.
    ("size", "segmented", "Text size", "standard",
     [("smaller", "A", "Smaller", "a1"),
      ("standard", "A", "Standard", "a2"),
      ("larger", "A", "Larger", "a3"),
      ("largest", "A", "Largest", "a4")], ""),
    # UB Goudy is the book's own face.  Its x-height is small, and some readers
    # will want one that reads larger at the same size; the other two are the
    # device's own, so nothing more is downloaded.
    ("face", "radio", "Typeface", "goudy",
     [("goudy", "Goudy", "the book's own typeface", "face-goudy"),
      ("serif", "A plainer serif", "", "face-serif"),
      ("sans", "Sans-serif", "", "face-sans")], ""),
    # Measured keeps the line near 68 characters and the page in a frame of its
    # own; Full gives the text, the rail and the margin the whole window, for a
    # reader who minds empty screen more than a long line (Tigran, 2026-10-10).
    ("width", "segmented", "Width", "measure",
     [("measure", "Measured", "about 68 characters to a line", ""),
      ("full", "Full", "the whole width of the window", "")], ""),
]
SHOW = [
    ("redletter", "switch", "The words of Jesus in red", True, [], ""),
    ("paranum", "switch", "Paragraph references", True, [], "such as 0:1.2, beside each paragraph"),
    ("pilcrow", "switch", "Pilcrows", True, [], "where the 1955 text leaves a blank line"),
    ("margin", "switch", "Index entries beside the text", True, [], ""),
    ("notes", "switch", "The 1955 readings", True, [], ""),
]
SPEEDS = (0.8, 0.9, 1, 1.1, 1.25, 1.5)
LISTEN = [
    # The choices are the database's voices (app.voices), the browser's own,
    # then Off; '' is the first voice the section has.
    ("voice", "radio", "Listen with", "", [], ""),
    # Which of the browser's voices: its English ones, filled in by ub.js,
    # which also says which '' picks.  Shown only while that voice is chosen.
    ("bvoice", "select", "Browser voice", "", [("", "Automatic", "", "")], ""),
    ("rate", "select", "Speed", 1, [(r, f"{r}×", "", "") for r in SPEEDS], ""),
    ("follow", "switch", "Follow along", True, [], "keep the paragraph being read in view"),
    # Off, playing stops at the end of a section (Tigran, 2026-10-07); on, it
    # carries on, across papers, through the whole book (2026-10-08).
    ("onward", "switch", "Carry on into the next section", False, [], "and so on through the book"),
]


# A setting that means nothing while another is 'off': shown, greyed, and not
# to be changed (ub.js disables it).  With Listening off there is no speed to
# set (Tigran, 2026-10-08).
NEEDS = {"bvoice": "voice", "rate": "voice", "follow": "voice", "onward": "voice"}


def _item(key, kind, label, default, choices, hint) -> dict:
    return {"key": key, "kind": kind, "label": label, "default": default, "hint": hint,
            "needs": NEEDS.get(key, ""),
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
    return {s[0]: s[3] for s in READING + SHOW + LISTEN}
