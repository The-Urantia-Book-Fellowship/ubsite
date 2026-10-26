# What this data makes possible

The survey that started the project, kept because the reasoning is worth more than the list. Ranked by what each unlocks against what it costs, given that in almost every case **the data already exists** — the work is presentation, not compilation.

Numbers here are measured from the current build, not estimated.
`[built]` marks what is done.

---

## The asset

Three corpora, one address space — `paper:section.paragraph`. The same `\vs` macro addresses `\vs p133 1:3` and `\vs Gen 1:1` alike.

| | |
|---|---|
| text | 14,586 paragraphs · 197 papers · 1,626 sections |
| index | 32,837 entries · 4,736 headwords · **50,758 references** |
| apparatus | 307 study footnotes · 54 human-source records · 24,974 KJV verses · 819 quiz questions · 84 figures |
| appendices | 436 dated events · 1,351 named beings, persons and places |

**The differentiator**: urantia.org has text and paragraph search, the Fellowship has a reader, Urantiapedia has a wiki and the Paramony's Bible cross-references, ubannotated has Katzen's study edition. *Nobody has the index as live data.* Roughly 3.5 curated concept links per paragraph, made by people over decades. Everything below leans on that.

---

## Tier 1 — unique, and the data is already there

**1. The annotated reader.** `[built]`
Every paragraph carries the index entries that cite it. On paper the index runs one way; here it runs both. This is the thing that started the project.

**2. Concept pages for all 4,736 headwords.** `[built]`
Each headword's subtree, its cited paragraphs, its cross-references resolved to links. An encyclopedia of the revelation that nobody had to write, because it was already written — editorially vetted, not machine-derived.

**3. The reading path.** `[built]`
A headword's subentry list is a hand-written outline of a topic across the whole book. Render each subentry as a heading with its cited paragraph verbatim beneath, in book order, and you have a topical anthology of the Urantia Papers compiled by a careful human. Four thousand seven hundred and thirty-six of them. Route `/i/<slug>/read`. Perhaps a day's work on top of what exists.
Built (2026-10-13): `/i/<slug>/read` for the 2,058 headwords citing three paragraphs or more, every one drawn once, in the order of the book, with the entries citing it beside it; `/i/<slug>/read/theme` reads the same paragraphs in the index's own groups, one chapter to each level-2 subentry, wherever there are two or more. Not the outline as printed, one heading to each subentry: most headwords are alphabetical lists, and read in that order the book jumps about.

**4. The chronology as an interactive timeline.** `[partly built]`
Appendix A: **436 dated events**, from *987,000,000,000 years ago* to *1200 A.D.*, each citing paragraphs. Already parsed, already sortable — `year_sort` is in the database and monotone in document order, which is itself the proof the parse is right. Log-scale scrub from the Andronover nebula to the crucifixion. Exists nowhere, in any form.
Built: `/appendix/A`, the list as printed, with a jump bar by period, and every event a chip beside the paragraphs it cites. Still to do: the timeline itself, on top of that page.

**5. Persons, beings and places.** `[partly built]`
Appendices B–F: 308 types of celestial being, 86 named celestial individuals, 429 named mortals, 72 celestial places, **456 terrestrial places — real geography**. Person pages with every appearance. And F is geocodable, so Jesus's Mediterranean journey (Papers 129–134) can be drawn on an actual map.
Built: `/appendix/B` … `/F` as printed. 1,332 of the 1,351 names are A–Z headwords, so the person pages already exist as concept pages, and each now says which appendix lists it. Still to do: the map.

**6. What the index does not see.**
**1,528 paragraphs (10.5%)** carry no citation naming them precisely; 10 are cited by nothing at all. Not a gimmick heatmap — a research page with the list. It is both a reader's guide to dense territory and an honest advertisement for the index's quality, and it feeds findings back into the index project.

---

## Tier 2 — high value, moderate work

**7. Blended search.** `[partly built]`
Index hits and text hits kept apart — never merged into one ranked list, because the scores are incommensurable and a merged list buries the curated result. Text hits default to book order, not relevance, because this is a book. Citation-aware: `101:4.2`, `Paper 61`, `76:2sec` jump rather than search.
Still to do: scopes (`index:` `bible:` `jesus:`), filters, `NEAR/n`, and sentence-boundary snippets.

**8. The words of Jesus.**
**1,267 red-letter spans**, already marked, and `ubdarkred` is defined as `{gray}{0.0}` — *black in print*. This site is the first place they have ever been red. Read end to end, searchable, each one citable.

**9. The quiz.**
819 questions, already written, already tagged by paper, at zero authoring cost. **83 are multi-answer** (1,002 correct flags) — a single-answer model marks correct responses wrong. Spaced repetition; per-paper self-test.

**10. The variorum layer.** `[partly built]`
180 `\fnc` first-edition readings `[imported]` + 84 study-edition variant notes + the index errata. "What the 1955 printing said here", as a toggle.
Built (2026-10-12): each 1955 reading is a ring in the text whose card carries the SRT Committee's decision and reasons (167 of the 180). Still to come: the study edition's variant notes, the index errata.

**11. Two editions, diffed.**
The press text is authoritative American; the British Study Edition is revised, metricated, Oxford-spelled and science-corrected. Both now hold at 14,586 paragraphs with identical numbering, so a paragraph-level diff is a join — and a genuinely novel scholarly object.

**12. Bible parallels.**
24,974 KJV verses in the same address space, plus 5,069 translators' marginal notes. The study footnotes already carry exact verse references, so "show me the scripture this paragraph is quoting" is a join, not a research project.

---

## Tier 3 — ambitious

**13. Sources and Antecedents.** *(the contentious one)*
54 human-source records across 19 papers — Eddington, Jeans, Baker, Peake, Knudson, Stetson — credited to Matthew Block's research. Four of those books are already held here as Project Gutenberg LaTeX (Eddington #29782 and #59248, Weyl
#43006, Whitehead #41568), so side-by-side reading is real for those.
**Rules, decided in advance**: titled *Sources and Antecedents*; opt-in and off by default; parallel reading, **never similarity scores or percentages**, because a score is a claim and invites a fight the site should not be in; scoped to the 54 records in this edition, not Block's full corpus; every claim links to primary evidence; the standfirst quotes the Papers' own account of the mandate to prefer the highest existing human concepts (0:12.12, 121:8.12–13).

**14. The concept graph.** `[partly built]`
9,721 co-citation pairs over level-1 headwords. The "cited alongside" strip exists. Do **not** build a force-directed graph of 4,736 nodes first — it will be pretty and say nothing. Earn it with the strip.

**15. Parallel translations.** `[under way]`
~15 translations sit in sibling directories, all `\vs`-addressed, so the address space is already language-independent — the hard part is done. The plan of work (Tigran, 2026-10-25), in two steps over several sessions, Russian first:

1. **The interface in Russian.** `[built]` (2026-10-25) Switched by a UK and a Russian flag at the header's top right, and in the browser's language until a flag is tapped. Both languages are in every page and CSS shows one, as the index switch hides the index, so no setting reaches the server and the offline copy stays one copy for every reader. Everything a reader sees is translated but the book, its index and appendices, the changelog and the API's documentation. A Paper is «Документ», and the site's name «Книга Урантии».
2. **Translations beside the text.** `[designed; the data built]` (Tigran, 2026-10-26, from a mockup on real text, 1:1 and 140:4: https://claude.ai/artifact/1M39hNkGJcmScQyZVjUGp9, whose version 1 compares six layouts: a fold line, a mark beside ▶, open under every paragraph, facing columns, the translation first, and a page of its own). The English stays the text, and the index stays English. The Russian ones first:
   - Tigran's own, «Урантийские документы», in `../ud`: Papers 0 to 40, and 41, 43, 195 and 196 in part, 3,579 paragraphs at 51f3039, with 346 notes of its own (`\fnst`). Its numbering is the study edition's before 2026-09-21: the ten separators numbered, and no 0:12.10, so 14,595 lines to our 14,586;
   - the late Lila's, with Sergey Prokopov's corrections (urantia.nyc), in `../urantia-ru`: the whole book, no notes, numbered as ours but for 0:12.10, which it sets as a heading, and 144:5, which it numbers as the Foundation does. Its rights are settled: the site is the Fellowship's (Tigran, 2026-10-26);
   - the Foundation's, from the latest HTML on urantia.org, never the old copy in `../urantia-rus`, joined by `uf_ref` (trap 18 in CLAUDE.md). Its rights are still to settle: the translation is the Foundation's copyright.

   As designed:
   - **A reader chooses them in Settings**, in a tab of its own, Translations («Переводы»): first those shown, in the reader's order, numbered, each with ↑ and ↓; then the others, by language, a tick adding one at the end of the order. **None is shown by default**: until a reader ticks one, every page is as it is now.
   - **A fold under each paragraph**, "› 3 translations", counting the translations ticked that have the paragraph; none, no fold. Opened, under the paragraph, one translation at a time in tabs in the reader's order, and All, which stacks them; the tab chosen opens the next fold. On a phone a paragraph's index entries and its translations fold to one line, "› 2 index entries · 3 translations", each half opening its own box.
   - **Compare**, a toggle in the middle of the row at the head of the text, between the Contents' button and the Index's, draws the page again in place: the English and each translation ticked, a column each, one row to a paragraph, which the grid aligns as it aligns a paragraph and its index entries. A column is headed by its work and translator and, under that, its own paper and section titles; a translation that has no paragraph in the section has no column, as it has no tab, and a section none has has no Compare. On a phone each paragraph stands with its translations under it, each named. The transport bar is at the foot. **Compare folds nothing**: the Contents and the Index stay as the reader left them (Tigran: "let's not second-guess him").
   - **Compare has an address of its own**, `/1:1/compare`, in the same tab, never a new one: Back leaves it, a reload or a link keeps it, and the transport bar and the Contents keep it on (⏭ to `/1:2/compare`). The paragraph at the top of the window stays there as Compare turns on or off.
   - **A translator's note is a card at its number**, as a study note is: numbered through its paper, "Note 6" («Примечание 6»), with a line naming its translation; shown whenever its translation is.

   Ruled (Tigran, 2026-10-26): a page carries which translations each paragraph has, so that a fold's count needs nothing fetched, but not their text, since each translation is two to three times the English in bytes and there will be more. A section's translations come in one request when a fold or Compare first needs them, kept by the browser under the build's version as `/rail/N` is, so no setting reaches the server; offline, each translation is a download of its own, in chunks as the spoken text is.

   The data is built (2026-10-26, `build/translation.py`): both are in `var/ub.db`, every paragraph under ours, the press's numbering, which the English uses (Tigran: map everything to it). Where a source numbers otherwise, `tests/known-tr-numbering.tsv` says how, and a gate holds it to exactly that list, with its separators and list labels where ours are. Each is hyphenated as its own TeX would set it (Tigran): hyph-ru and its own exception list. The Cyrillic typeface of step 1 sets them, its subset widened by the stress mark U+0301, which `ud` writes (признаю́т).

   Still to settle: whether search reaches them. Neither Russian translation marks the red letter.

**16. A public API and stable permalinks.** `[text built]`
`/101:4.2` resolves. **`/api/v1/text`** (2026-10-11) is built: a versioned sync of the whole text, which other sites use to keep their copies in step. It serves the text as public domain, and gives each paragraph the Foundation's numbering beside ours. Still to come: `/api/v1/reverse/101:4.2`, the entries citing a paragraph, and `cite.parse` as a service. Together they would make the data a commons. The index's licence is settled (2026-10-14): CC BY-NC-SA 4.0, with the edition as a whole, so they can be built, the licence marked on what they send. NC still rules out commercial reuse.

**17. Reader-proposed index entries** for the thin paragraphs, feeding the next printing. The website becomes an instrument for editing the book.

---

## What not to build

- **No discussion forum or comments.** Every site in this space has died of its comment section.
- **No accounts before they are needed.** Anonymous, cookie-scoped preferences carry a long way.
- **No "AI search".** The index *is* the semantic layer, made by people, and it is the entire differentiator. Burying it under an embedding model would be the single worst decision available here.
- **Do not re-derive the Paramony.** Urantiapedia has 13,000 Bible↔UB cross-references. Differentiate or link out.

---

## Offline

The book is the book. `make press` in the press project already imposes text and index into one 2,192-page press file, and print is better at being a book. The web is for what print cannot do: the reverse index, the timeline, the map, search, and the diff.

**The EPUB** `[retired]` (built 2026-10-10, retired 2026-10-19) earned its place by doing one of those things offline: the reverse index. Beneath every paragraph stand the entries that cite it, and every citation in the index opens its paragraph, so the index runs both ways on an e-reader as on the site. `make epub`, from `ub.db` alone. It was cheap, as predicted, because every hard part was already in the database; the work was the index's presentation without a margin, the gates, and trying it on real readers. What it could not carry: the site's search (a reader's own finds the literal `101:4.2` at every paragraph), the Show switches, listening (EPUB 3 Media Overlays could carry the aligned reading, but even the 32 kbps transcode is 1.7 GB), and freshness: it was a snapshot, dated by its source commits. Retired on 2026-10-19 (Tigran): Work offline now keeps the whole site in the browser, the reverse index, search and the reading paths with it, in the site's own typography, and a second view to keep working cost time on every feature. The last commit that builds it is tagged `epub-last`.
