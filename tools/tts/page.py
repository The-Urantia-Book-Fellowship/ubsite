"""The listening test as a page: each passage's text beside Merritt Horn and the
voices still in the running, one row each, with a star per passage to say which
one reads it best.

    python3 -m tools.tts.page higgs3_mature higgs3_belinda    # -> var/tts/bakeoff/index.html

Published as a private artifact with the clips beside it: the page names them
relatively, <voice>/<passage>.mp3, as they lie in var/tts/bakeoff/.  The text is
the database's stored paragraph HTML, so it is set as the site sets it -- red
letter, dot leaders, list marks.  Stdlib only.
"""

from __future__ import annotations

import html
import json
import pathlib
import sqlite3
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "var" / "tts" / "bakeoff"
BOOK_HOURS = 121.4                     # Merritt Horn's reading, measured 2026-10-07

# Who each candidate is, for the table and the row labels.
WHO = {
    "higgs3_mature": ("Mature", "Higgs TTS 3", "a man, from a voice Higgs v2 drew from a description"),
    "higgs3_belinda": ("Belinda", "Higgs TTS 3", "a woman, from Boson AI's sample voice"),
    "higgs3_michael": ("Michael", "Higgs TTS 3", "a man, from Kokoro's Michael"),
    "am_michael": ("Michael", "Kokoro", "American man"),
    "higgs3_belinda_heard": ("Belinda, before", "as you heard it", ""),
    "higgs3_mature_heard": ("Mature, before", "as you heard it", ""),
    "higgs3_mature_hum": ("Mature, before", "with the hum", ""),
}
# A clip from an earlier round beside the new one, where the change is the point.
BEFORE = {"0:0.1": ["higgs3_mature_hum"], "15:2.10-16": ["higgs3_belinda_heard"]}

# This round's introduction; rewritten for each round of the test.
LEDE = """  <header class="lede">
    <p class="eyebrow">ubsite · listening, step 4 · the final two, round three</p>
    <h1>Which voice should read the book?</h1>
    <p>Mature and Belinda again, beside Merritt Horn. Mature is made afresh, and both voices now
       pass a word-by-word check. Star the one you would rather hear for each passage. The stars
       start over for this round, stay in this browser, and are counted in the table.</p>
    <ul>
      <li><strong>Mature's noise was a hum, and it is gone.</strong> Mature is cloned from a short
        clip, and a clone copies the room as well as the voice. That clip carried a 120 Hz hum,
        the mark of mains electricity, and Mature reproduced it in about one pause in five. The
        clip is now cleaned before cloning. Under 0:0.1, Mature with the hum is kept for
        comparison; it is plainest under "designated by these numerous".</li>
      <li><strong>Every sentence is now checked by ear.</strong> Whisper listens to each piece as
        it is made, and any piece with a word left out, changed or added is made again. The
        re-made Mature had first dropped "great" from "there exists great confusion", read
        "designated" as "delegated", and garbled the psalm's first line. All of that was caught
        and re-made. In the clips here, Whisper hears every word of both voices, apart from what
        it mishears in Merritt Horn too: the coined names, which it spells by ear.</li>
      <li><strong>From earlier today:</strong> table rows end as sentences, so "70" and
        "7,000,000,000" are no longer cut off (Belinda's 15:2 as you first heard it is kept for
        comparison), and every clip is at one even loudness.</li>
    </ul>
  </header>
"""

STYLE = """
/* A listening sheet in the site's own paper and ink: the passage on the left,
   the voices that read it on the right, one row each, the human reading first. */
:root {
  --paper: oklch(0.972 0.008 85);
  --ink:   oklch(0.24 0.012 60);
  --faint: oklch(0.52 0.010 70);
  --rule:  oklch(0.88 0.010 80);
  --link:  oklch(0.40 0.09 250);
  --flame: oklch(0.62 0.13 76);
  --jesus: oklch(0.44 0.15 25);
  --tint:  oklch(0.94 0.02 250);
  --serif: "Sorts Mill Goudy", "Goudy Old Style", Georgia, serif;
  --ui: system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: oklch(0.185 0.008 70); --ink: oklch(0.90 0.010 85); --faint: oklch(0.66 0.010 75);
    --rule: oklch(0.30 0.010 75); --link: oklch(0.74 0.08 250); --flame: oklch(0.80 0.12 82);
    --jesus: oklch(0.70 0.12 28); --tint: oklch(0.26 0.03 250); color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: oklch(0.185 0.008 70); --ink: oklch(0.90 0.010 85); --faint: oklch(0.66 0.010 75);
  --rule: oklch(0.30 0.010 75); --link: oklch(0.74 0.08 250); --flame: oklch(0.80 0.12 82);
  --jesus: oklch(0.70 0.12 28); --tint: oklch(0.26 0.03 250); color-scheme: dark;
}
body { background: var(--paper); color: var(--ink); font: 1.12rem/1.55 var(--serif);
       font-variant-numeric: lining-nums;
       padding-inline: 16px; padding-block: 2rem 4rem; }
.wrap { max-width: 72rem; margin: 0 auto; display: grid; gap: 2.4rem; }
h1 { font-weight: 400; font-size: 2.3rem; line-height: 1.1; margin: 0; text-wrap: balance; }
.lede { display: grid; gap: .7rem; max-width: 64ch; }
.lede p { margin: 0; }
.eyebrow { font: 600 .74rem/1 var(--ui); letter-spacing: .12em; text-transform: uppercase; color: var(--faint); margin: 0 0 .6rem; }

/* The readers, with what each costs and the listener's stars so far. */
.legend { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font: .9rem/1.4 var(--ui); }
th, td { text-align: left; padding: .45rem .8rem .45rem 0; border-bottom: 1px solid var(--rule); white-space: nowrap; }
thead th { font-weight: 600; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--faint); }
tbody th { font: 1.05rem var(--serif); }
tbody tr.human th, tbody tr.human td { color: var(--faint); }
th.num, td.num { font-variant-numeric: tabular-nums; text-align: right; }
td.tally { color: var(--flame); font-weight: 700; }
.note { font: .85rem/1.45 var(--ui); color: var(--faint); margin: .6rem 0 0; max-width: 72ch; }

.passage { border-top: 1px solid var(--rule); padding-top: 1.2rem; display: grid; gap: .9rem; }
.passage h2 { font-weight: 400; font-size: 1.45rem; margin: 0; text-wrap: balance; }
.cite { font: 600 .82rem var(--ui); color: var(--link); letter-spacing: .02em; margin-right: .5rem;
        font-variant-numeric: tabular-nums; }
.pair { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr); gap: 1.6rem; align-items: start; }
@media (max-width: 52rem) { .pair { grid-template-columns: minmax(0, 1fr); } }

.text { min-width: 0; }
.text summary { cursor: pointer; font: .85rem var(--ui); color: var(--link); }
.text p { margin: .6rem 0 0; }
.text .ref { font: .72rem var(--ui); color: var(--faint); margin-right: .3rem; }
.text .jesus { color: var(--jesus); }
.text .mark { font-variant-numeric: lining-nums; }
.text .leader { display: inline-block; width: 3rem; border-bottom: 1px dotted var(--faint);
                margin: 0 .35rem; transform: translateY(-.28em); }

.players { list-style: none; margin: 0; padding: 0; display: grid; gap: .1rem; min-width: 0; }
.players li { display: grid; grid-template-columns: 9.5rem minmax(0, 1fr) 2rem; gap: .6rem;
              align-items: center; padding: .25rem .4rem; border-radius: 4px; }
.players li.human { background: var(--tint); margin-bottom: .4rem; }
.players li.before { margin-top: .4rem; border-top: 1px dashed var(--rule); border-radius: 0; }
.players li.before .who { color: var(--faint); }
.lede ul { margin: 0; padding-left: 1.2rem; display: grid; gap: .5rem; }
.players li.playing { outline: 1px solid var(--link); }
.who { font-size: 1rem; line-height: 1.2; }
.who small { display: block; font: .72rem var(--ui); color: var(--faint); }
audio { width: 100%; height: 2.1rem; }
.star { font: 1.2rem/1 var(--ui); background: none; border: 0; padding: .2rem; cursor: pointer;
        color: var(--rule); border-radius: 4px; }
.star:hover { color: var(--faint); }
.star[aria-pressed="true"] { color: var(--flame); }
.star:focus-visible, summary:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; }
@media (max-width: 30rem) {
  .players li { grid-template-columns: minmax(0, 1fr) 2rem; }
  .players li audio { grid-column: 1 / -1; grid-row: 2; }
}
"""

SCRIPT = """
(function () {
  // One clip at a time: starting one pauses the rest.
  document.addEventListener('play', function (ev) {
    document.querySelectorAll('audio').forEach(function (a) {
      if (a !== ev.target) a.pause();
      a.closest('li').classList.toggle('playing', a === ev.target);
    });
  }, true);

  // One star per passage, kept in this browser only.
  var KEY = '%(key)s', stars = {};
  try { stars = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) {}
  function render() {
    document.querySelectorAll('.star').forEach(function (b) {
      b.setAttribute('aria-pressed', String(stars[b.dataset.passage] === b.dataset.voice));
    });
    document.querySelectorAll('.tally').forEach(function (td) {
      var n = 0;
      for (var p in stars) if (stars[p] === td.dataset.voice) n++;
      td.textContent = n;
    });
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('.star');
    if (!b) return;
    var p = b.dataset.passage;
    if (stars[p] === b.dataset.voice) delete stars[p]; else stars[p] = b.dataset.voice;
    try { localStorage.setItem(KEY, JSON.stringify(stars)); } catch (e) {}
    render();
  });
  render();
})();
"""


def seconds(f: pathlib.Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(f)], capture_output=True, text=True,
                                check=True).stdout)


def refs(spec: str) -> list[str]:
    head, tail = spec.rsplit(".", 1)
    a, _, b = tail.partition("-")
    return [f"{head}.{n}" for n in range(int(a), int(b or a) + 1)]


def main(argv: list[str]) -> int:
    voices = argv or ["higgs3_mature", "higgs3_belinda"]
    meta = json.loads((OUT / "bakeoff.json").read_text())
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    para = dict(con.execute("SELECT ref, html FROM paragraph WHERE edition_id ="
                            " (SELECT id FROM edition WHERE code = 'press')"))
    names = [s["id"].replace(":", "_") for s in meta["samples"]]
    length = {v: sum(seconds(OUT / v / f"{n}.mp3") for n in names) for v in ["mh", *voices]}

    def heard(v: str) -> str:
        h = meta["heard"].get(v, {})
        return f"{100 * sum(h.values()) / len(h):.0f}%" if h else "–"

    rows = [f'<tr class="human"><th scope="row">Merritt Horn</th><td>the Uversa Press DVD</td>'
            f'<td>the human reading</td><td class="num">{BOOK_HOURS:.0f} h</td><td class="num">–</td>'
            f'<td class="num">{heard("mh")}</td><td class="num"></td></tr>']
    for v in voices:
        name, model, what = WHO[v]
        # The book is as much longer in this voice as the nine passages are.
        hours = BOOK_HOURS * length[v] / length["mh"]
        rows.append(f'<tr><th scope="row">{name}</th><td>{model}</td><td>{html.escape(what)}</td>'
                    f'<td class="num">{hours:.0f} h</td><td class="num">{hours / meta["rtf"][v]:.0f} h</td>'
                    f'<td class="num">{heard(v)}</td>'
                    f'<td class="num tally" data-voice="{v}">0</td></tr>')

    passages = []
    for k, s in enumerate(meta["samples"], 1):
        spec, n = s["id"], s["id"].replace(":", "_")
        text = "".join(f'<p><span class="ref">{r}</span> {para[r]}</p>' for r in refs(spec))
        li = [f'<li class="human"><span class="who">Merritt Horn <small>the human reading</small></span>'
              f'<audio controls preload="none" src="mh/{n}.mp3"></audio><span></span></li>']
        for v in voices:
            name, model, what = WHO[v]
            li.append(f'<li><span class="who">{name} <small>{model}</small></span>'
                      f'<audio controls preload="none" src="{v}/{n}.mp3"></audio>'
                      f'<button type="button" class="star" id="star-{n}-{v}" data-voice="{v}"'
                      f' data-passage="{n}" aria-pressed="false"'
                      f' aria-label="Prefer {name} for {spec}">★</button></li>')
        for v in BEFORE.get(spec, []):
            name, model, _what = WHO[v]
            li.append(f'<li class="before"><span class="who">{name} <small>{model}</small></span>'
                      f'<audio controls preload="none" src="{v}/{n}.mp3"></audio><span></span></li>')
        passages.append(f"""<section class="passage" id="p{k}">
  <header><h2><span class="cite">{spec}</span> {html.escape(s["what"])}</h2></header>
  <div class="pair">
    <details class="text" open><summary>The text</summary>{text}</details>
    <ol class="players">{"".join(li)}</ol>
  </div>
</section>""")

    page = f"""<title>ubsite Voice Trial</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sorts+Mill+Goudy:ital@0;1&display=swap">
<style>{STYLE}</style>

<div class="wrap">
{LEDE}
  <section class="legend" aria-labelledby="cands">
    <p class="eyebrow" id="cands">The readers</p>
    <table>
      <thead><tr><th scope="col">Voice</th><th scope="col">Model</th><th scope="col">Cloned from</th>
        <th scope="col" class="num">Length</th><th scope="col" class="num">GPU time</th>
        <th scope="col" class="num">Heard</th><th scope="col" class="num">Your stars</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
    <p class="note">Length is the whole book read at the voice's pace in these passages. GPU time
      is how long this machine's RTX 3090 takes to make it, retries included, plus an hour or two
      for Whisper to check it. Heard is the share of
      each passage's words that Whisper recognised when it listened back, averaged over the nine.
      Whisper does not know the coined names, so 30:2's list scores low for every reader,
      Merritt Horn included.</p>
  </section>

{chr(10).join(passages)}
</div>

<script>{SCRIPT % {"key": "voicetrial-final3-stars"}}</script>
"""
    (OUT / "index.html").write_text(page)
    print(OUT / "index.html", {v: round(length[v]) for v in length})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
