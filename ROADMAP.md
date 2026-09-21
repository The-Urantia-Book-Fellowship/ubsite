# What this data makes possible

The survey that started the project, kept because the reasoning is worth more
than the list. Ranked by what each unlocks against what it costs, given that in
almost every case **the data already exists** — the work is presentation, not
compilation.

Numbers here are measured from the current build, not estimated.
`[built]` marks what is done.

---

## The asset

Three corpora, one address space — `paper:section.paragraph`. The same `\vs`
macro addresses `\vs p133 1:3` and `\vs Gen 1:1` alike.

| | |
|---|---|
| text | 14,586 paragraphs · 197 papers · 1,626 sections |
| index | 32,837 entries · 4,736 headwords · **50,758 references** |
| apparatus | 307 study footnotes · 54 human-source records · 24,974 KJV verses · 819 quiz questions · 84 figures |
| appendices | 437 dated events · 1,351 named beings, persons and places |

**The differentiator**: urantia.org has text and paragraph search, the
Fellowship has a reader, Urantiapedia has a wiki and the Paramony's Bible
cross-references, ubannotated has Katzen's study edition. *Nobody has the index
as live data.* Roughly 3.5 curated concept links per paragraph, made by people
over decades. Everything below leans on that.

---

## Tier 1 — unique, and the data is already there

**1. The annotated reader.** `[built]`
Every paragraph carries the index entries that cite it. On paper the index runs
one way; here it runs both. This is the thing that started the project.

**2. Concept pages for all 4,736 headwords.** `[built]`
Each headword's subtree, its cited paragraphs, its cross-references resolved to
links. An encyclopedia of the revelation that nobody had to write, because it
was already written — editorially vetted, not machine-derived.

**3. The reading path.** *(not built — the best idea here and nearly free)*
A headword's subentry list is a hand-written outline of a topic across the whole
book. Render each subentry as a heading with its cited paragraph verbatim
beneath, in book order, and you have a topical anthology of the Urantia Papers
compiled by a careful human. Four thousand seven hundred and thirty-six of them.
Route `/i/<slug>/read`. Perhaps a day's work on top of what exists.

**4. The chronology as an interactive timeline.**
Appendix A: **437 dated events**, from *987,000,000,000 years ago* to *1200
A.D.*, each citing paragraphs. Already parsed, already sortable — `year_sort` is
in the database and monotone in document order, which is itself the proof the
parse is right. Log-scale scrub from the Andronover nebula to the crucifixion.
Exists nowhere, in any form.

**5. Persons, beings and places.**
Appendices B–F: 308 types of celestial being, 86 named celestial individuals,
429 named mortals, 72 celestial places, **456 terrestrial places — real
geography**. Person pages with every appearance. And F is geocodable, so Jesus's
Mediterranean journey (Papers 129–134) can be drawn on an actual map.

**6. What the index does not see.**
**1,528 paragraphs (10.5%)** carry no citation naming them precisely; 10 are
cited by nothing at all. Not a gimmick heatmap — a research page with the list.
It is both a reader's guide to dense territory and an honest advertisement for
the index's quality, and it feeds findings back into the index project.

---

## Tier 2 — high value, moderate work

**7. Blended search.** `[partly built]`
Index hits and text hits kept apart — never merged into one ranked list, because
the scores are incommensurable and a merged list buries the curated result.
Text hits default to book order, not relevance, because this is a book.
Citation-aware: `101:4.2`, `Paper 61`, `76:2sec` jump rather than search.
Still to do: scopes (`index:` `bible:` `jesus:`), filters, `NEAR/n`, and
sentence-boundary snippets.

**8. The words of Jesus.**
**1,267 red-letter spans**, already marked, and `ubdarkred` is defined as
`{gray}{0.0}` — *black in print*. This site is the first place they have ever
been red. Read end to end, searchable, each one citable.

**9. The quiz.**
819 questions, already written, already tagged by paper, at zero authoring cost.
**83 are multi-answer** (1,002 correct flags) — a single-answer model marks
correct responses wrong. Spaced repetition; per-paper self-test.

**10. The variorum layer.**
177 `\fnc` first-edition readings `[imported]` + 84 study-edition variant notes +
the index errata. "What the 1955 printing said here", as a toggle.

**11. Two editions, diffed.**
The press text is authoritative American; the British Study Edition is revised,
metricated, Oxford-spelled and science-corrected. Both now hold at 14,586
paragraphs with identical numbering, so a paragraph-level diff is a join — and a
genuinely novel scholarly object.

**12. Bible parallels.**
24,974 KJV verses in the same address space, plus 5,069 translators' marginal
notes. The study footnotes already carry exact verse references, so "show me the
scripture this paragraph is quoting" is a join, not a research project.

---

## Tier 3 — ambitious

**13. Sources and Antecedents.** *(the contentious one)*
54 human-source records across 19 papers — Eddington, Jeans, Baker, Peake,
Knudson, Stetson — credited to Matthew Block's research. Four of those books are
already held here as Project Gutenberg LaTeX (Eddington #29782 and #59248, Weyl
#43006, Whitehead #41568), so side-by-side reading is real for those.
**Rules, decided in advance**: titled *Sources and Antecedents*; opt-in and off
by default; parallel reading, **never similarity scores or percentages**, because
a score is a claim and invites a fight the site should not be in; scoped to the
54 records in this edition, not Block's full corpus; every claim links to
primary evidence; the standfirst quotes the Papers' own account of the mandate
to prefer the highest existing human concepts (0:12.12, 121:8.12–13).

**14. The concept graph.** `[partly built]`
9,721 co-citation pairs over level-1 headwords. The "cited alongside" strip
exists. Do **not** build a force-directed graph of 4,736 nodes first — it will be
pretty and say nothing. Earn it with the strip.

**15. Parallel translations.**
~15 translations sit in sibling directories, all `\vs`-addressed, so the address
space is already language-independent — the hard part is done. The index stays
English; a Russian reader gets Russian text with English index chips, clearly
labelled. That is honest, and still more than anyone else offers.

**16. A public API and stable permalinks.** `[partly built]`
`/101:4.2` resolves. `/api/v1/reverse/101:4.2` — the entries citing a paragraph —
and `cite.parse` as a service would make the data a commons. Blocked on the
licence question: CC BY-NC-SA forecloses most of what an API is for.

**17. Reader-proposed index entries** for the thin paragraphs, feeding the next
printing. The website becomes an instrument for editing the book.

---

## What not to build

- **No discussion forum or comments.** Every site in this space has died of its
  comment section.
- **No accounts before they are needed.** Anonymous, cookie-scoped preferences
  carry a long way.
- **No "AI search".** The index *is* the semantic layer, made by people, and it
  is the entire differentiator. Burying it under an embedding model would be the
  single worst decision available here.
- **Do not re-derive the Paramony.** Urantiapedia has 13,000 Bible↔UB
  cross-references. Differentiate or link out.

---

## Offline

The book is the book. `make press` in the press project already imposes text and
index into one 2,192-page press file. An EPUB export from `ub.db` is cheap when
wanted, but it competes with a printed volume that is better at being a book.
The web is for what print cannot do: the reverse index, the timeline, the map,
search, and the diff.
