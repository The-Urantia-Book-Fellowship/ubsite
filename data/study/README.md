# Study notes, one reviewed paper at a time

This directory holds the British Study Edition's notes (`../urantia-study-edition`, its `\fnst` footnotes) as the site shows them. Each paper has one file, `NNN.toml`, made by hand from a draft and reviewed with Tigran; a paper without a file has no study notes on the site. The edition itself is never written to. `build/study.py` reads these files, and fails the build where one no longer describes the edition or Block's charts.

## The rules of the review

Every note is read, checked and edited, so that it asserts nothing a reader could not check. Decided with Tigran on 2026-10-18.

**Kept, once checked:**

- Bible references, and the King James wording where a note quotes it.
- A human source's own words, with the page, where Matthew Block's chart (or the source itself, where it is held) confirms them.
- What differs between the source's wording and the book's, where anyone can see it by putting the two side by side.
- Cross-references to other paragraphs (`\bibref`).
- Arithmetic, shown in full and recomputed.
- A scientific figure, with its date and a named source; a stale one is brought up to date or dropped.

**Rewritten against the press text:** anything about the study edition's own wording. The study text is British and metricated: 23:3.2 reads "299,789 kilometres" where the press reads "186,280 miles", so a note about the conversion says nothing about the text the site shows.

**Dropped, with the reason in `[[dropped]]`:** a 1955 reading the press's own `\fnc` gives, which the site already shows as a ring and a card. Only the press says what 1955 printed (§8, 2026-10-12). A study note giving a 1955 reading the press has no `\fnc` for is listed for the audit of the 1955 readings against the Guardian plates, and never called a press error without them (trap 21).

**Flagged, for Tigran to rule on one by one:**

- conjecture;
- a verdict in the first person ("I think", "I consider both very doubtful");
- an evaluation ("obvious", "excellent", "neat", "curious", "one of the greatest");
- a claim about the revelators' intent, knowledge or authorization;
- the editor's own experience offered as evidence.

**Each card stands alone.** A reader opens one note at a time. "Here and in the notes below…" becomes a credit line on each note (`credit = "block"`), and "see the note at 103:8.6" points to a note already on the site, or the note says what it needs itself.

**Human sources come from Block's current chart**, the one `../block-sources/MANIFEST.tsv` lists for the paper, never from the edition's citation of an older one. The file names that chart; a chart revised since fails the build until the notes are checked against it. Refreshing `../block-sources` (`../explore-tools/block_fetch.py`, which uses the network) is Tigran's call.

## How a paper is reviewed

1. `make data`, then `.venv/bin/python tools/study/draft.py N`. It writes `var/study/NNN.toml`, every note and source of the paper as the edition has them, each with its `origin` and, for a note, a proposed `after`; and beside each note, in comments, the press paragraph, the press's 1955 readings there, and what Block's chart sets beside it. `var/study/NNN.md` is the same, to read.
2. Each note is edited and checked, and the review written: each note's original and its proposed text, the reason for each change, and every flag with a proposed cut or rewording.
3. Tigran rules on the flags.
4. The file is saved here, the site built, and the paper looked at on the dev server.
5. It is committed only once Tigran has looked; `deploy.sh` refuses an uncommitted `data/study/`.

## The file

```toml
paper = 0
chart = "https://urantiabooksources.com/wp-content/uploads/2019/12/000.pdf"   # or "none"

[[source]]                          # a \bibitem carried
key = "Hartshorne"                  # what \cite names
origin = "1f3a…"                    # the \bibitem it was made from
tex = '''Charles Hartshorne, \emph{Man's Vision of God and the Logic of Theism} (Chicago: Willett, Clark \& Company, 1941).'''

[[note]]
at = "0:1.19"                       # the paragraph
after = "seven conceivable types"   # the press words the marker follows: once in the paragraph, whole words
origin = "9c2e…"                    # the \fnst it was made from
credit = "block"                    # the note rests on Block's chart; or a contributor's name; or none
tex = '''…'''

[[dropped]]                         # a note (at) or a source (key) not carried
at = "0:1.24"
origin = "77c1…"
why = "a 1955 reading: the press's \fnc{all other} at 0:1.24 gives it"
```

`origin` is 16 hex digits of the SHA-256 of what the edition has between the braces of the `\fnst`, or of a `\bibitem`'s key, a newline and its lines (`build/readers/study.py`). Every note and source of the paper is carried or dropped exactly once. Unknown keys fail.

**`tex` is the edition's macros, and no others** (`build/study_macros.py`): `\bibemph`, `\emph`, `\textit`, `\textsc`, `\bibtextul`, `\ts`, `\hyp{}`, `\,`, `\ldots`, `\'`, `\"`, `\ae`, `\mbox`, `\texttt`, `\textgreek`, `\textheb`, `\textarm`, `\textchinese`, `\cite`, `\bibref[1:2.9]{p001 2:9}`, `\myurl`, `\bibfrac`, and the escapes `\# \% \$ \&`. TeX's quotes: ``` ``a'' ``` is “a”, `` `a' `` is ‘a’, `Nave's` is Nave’s, `~` a space that does not break. A `%` must be `\%`. Math is `$...$`, inline, in the set `build/texmath.py` knows. **Hebrew is written in logical order** here, first word first: the edition writes it word by word reversed, for XeTeX without bidi, and the draft turns it round.

`\cite{key}` is set as `[1]`, numbered within the note, and the card lists the sources a note cites at its foot, in full.

A marker's number runs from 1 through the paper, in the order of the text, and the notes are listed in that order.
