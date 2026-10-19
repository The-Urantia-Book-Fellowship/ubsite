# Study notes, one reviewed paper at a time

This directory holds the British Study Edition's notes (`../urantia-study-edition`, its `\fnst` footnotes) as the site shows them. Each paper has one file, `NNN.toml`, made by hand from a draft and reviewed with Tigran; a paper without a file has no study notes on the site. The edition itself is never written to. `build/study.py` reads these files, and fails the build where one no longer describes the edition or Block's charts.

## The rules of the review

Every note is read, checked and edited, so that it asserts as fact nothing a reader could not check; an opinion is said as the editor's, with its reasons. Decided with Tigran on 2026-10-18.

**Kept, once checked:**

- Bible references, and the King James wording where a note quotes it.
- A human source's own words, with the page, where Matthew Block's chart (or the source itself, where it is held) confirms them.
- What differs between the source's wording and the book's, where anyone can see it by putting the two side by side.
- Cross-references to other paragraphs (`\bibref`).
- Arithmetic, shown in full and recomputed.
- A scientific figure, with its date and a named source; a stale one is brought up to date or dropped.

**Rewritten against the press text:** anything about the study edition's own wording. The study text is British and metricated: 23:3.2 reads "299,789 kilometres" where the press reads "186,280 miles", so a note about the conversion says nothing about the text the site shows.

**Dropped, with the reason in `[[dropped]]`:** a 1955 reading the press's own `\fnc` gives, which the site already shows as a ring and a card. Only the press says what 1955 printed (§8, 2026-10-12). These are dropped without a ruling (Tigran, 2026-10-19: "All 1955 reading notes from the British Study Edition you can silently ignore as we have the complete 1955 apparatus already"); the review lists them as dropped, and asks nothing. A study note giving a 1955 reading the press has no `\fnc` for is listed for the audit of the 1955 readings against the Guardian plates, and never called a press error without them (trap 21).

**A valid opinion is welcome** (Tigran, ruling on Paper 0, 2026-10-18): "Reflections in the first person make the notes lively and personal. This is a feature, not a bug. I said I don't want opinionated notes, but a valid opinion is perfectly acceptable." So a reflection or a reading of the text stays, in the first person, as the editor's, with its reasons. What does not stay as it is:

- **An unjustified assertion stated as fact** is hedged, said as what it is, a conjecture or a reading ("perhaps to reflect", "may be a coined word"), or else rewritten to what can be shown. Paper 0's notes on the lower-case "deity" and the capitals of "DEITY" stayed, with "perhaps".
- **A factual error** is corrected: Part IV is the midwayers', not the system's.
- **A verdict with no reason** ("the reason … is obvious") and **a digression from the text** (Tolstoy, at the word "English") go.

Every such change is proposed in the review and ruled on by Tigran, note by note, each numbered F1… in the order of the text.

**Each card stands alone.** A reader opens one note at a time, so "Here and in the notes below…" becomes a credit line on each note (`credit = "block"`). Block is credited on a note that rests on a human source his chart identifies, never on one that only gives a Bible reference, though his chart may give the verse too: the editor recognised those himself (Tigran, 2026-10-19).

**A source is cited as bibliographies cite it**: author, title, place, publisher, year, without the degrees and honours a title page or Block's chart gives ("Orville J. Nave", not "Orville J. Nave, A.M., D.D., LL.D."; Tigran, 2026-10-19).

**A note may point to a note still to come** (Tigran, ruling on Paper 0, 2026-10-19). 0:5.11's "see the note at 103:8.6" stays as the edition has it, and its link opens 103:8.6, where the note will stand once Paper 103 is reviewed. What the note there is to give, where Tigran has said, is in the comment above the pointing note in its file; `tools/study/draft.py` puts every reviewed note that links into a paper at the head of that paper's draft, so that it is read with the comment when the paper's turn comes.

**Human sources come from Block's current chart**, the one `../block-sources/MANIFEST.tsv` lists for the paper, never from the edition's citation of an older one. The file names that chart, and its date as Block gives it on its first page, "WORK-IN-PROGRESS (MARCH 14, 2023)", which a note's credit shows (Tigran, 2026-10-19): the address's month is only when the chart was uploaded, July 2023 for that one. The draft proposes the date from the chart, and `tests/test_study.py` holds it there. A chart revised since fails the build until the notes are checked against it. Refreshing `../block-sources` (`../explore-tools/block_fetch.py`, which uses the network) is Tigran's call.

**A work a note quotes is a source, cited in full, even where the edition does not list it and Block only compares it** (Tigran, 2026-10-19, of Ellen G. White in Paper 1: "Block says 'compare', but I say it is an obvious source"). It is added as a `[[source]]` with `origin = "none"`, checked in the original, page and words, and the original is kept in `../block-sources/originals/`, whose `MANIFEST.tsv` gives the official address it was downloaded from. The note then cites it as any other, `White~\cite{White1892}, p.~225`, without "Compare".

## How a paper is reviewed

1. `make data`, then `.venv/bin/python tools/study/draft.py N`. It writes `var/study/NNN.toml`, every note and source of the paper as the edition has them, each with its `origin` and, for a note, a proposed `after`; and beside each note, in comments, the press paragraph, the press's 1955 readings there, and what Block's chart sets beside it; and at its head, the reviewed notes of other papers that link into this one. `var/study/NNN.md` is the same, to read.
2. Each note is edited and checked, and the review written: each note's original and its proposed text, the reason for each change, and every flag with a proposed cut or rewording.
3. Tigran rules on the flags.
4. The file is saved here, the site built, and the paper looked at on the dev server.
5. It is committed only once Tigran has looked; `deploy.sh` refuses an uncommitted `data/study/`.

## The file

```toml
paper = 0
chart = "https://urantiabooksources.com/wp-content/uploads/2019/12/000.pdf"   # or "none"
chart_date = 2019-12-04             # the chart's date as Block gives it on its first page; none without a chart

[[source]]                          # a \bibitem carried
key = "Hartshorne"                  # what \cite names: the author's surname, the Bibliography's order
origin = "1f3a…"                    # the \bibitem it was made from; "none" for a work the review adds
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

**Ties as the accepted usage:** `~` after a title or an abbreviation (`Dr~Sadler`, `Sir~Arthur`, `p.~8`) and inside a reference (`Psalms~104:2`), never through a whole name: words tied together break as one, and `Sir~Arthur~S.\,Eddington` left a gap at the end of the line before it. The build warns of three words or more tied together that are no chapter and verse, and of any tied run longer than 24 characters (`study-long-tie`).

`\cite{key}` is set as `[1]`, numbered within the note, and the card lists the sources a note cites at its foot, in full.

**A key names one work, in every paper** (`build/study.py` `one_work_one_key`): the Bibliography, `/lists/bibliography`, lists each work once, in the order of its key, with every note that cites it, in whichever paper (Tigran, 2026-10-19). So a key begins with the author's surname, as the edition's do (`p001Knudson1`), and a work cited again in a later paper is carried there with the same key and the same `tex`; two works by one author take keys that tell them apart (`Eddington1920`, `Eddington1928`). A key used for two works, or two keys for one, fails the build.

A marker's number runs from 1 through the paper, in the order of the text, and the notes are listed in that order.
