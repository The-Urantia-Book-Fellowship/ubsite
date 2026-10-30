# The quiz, as the site asks it

The British Study Edition's Cosmic Citizenship Quiz, `tex/quiz.tex` in `../urantia-study-edition`: 817 questions on 126 of the 197 papers, 51 of them with more than one right answer (819 and 53 until Tigran's mends of 2026-10-29). The site asks it one question at a time, at the end of each paper that has questions and at `/quiz` (Tigran, 2026-10-28). `build/quiz.py` reads it at the commit `sources.toml` pins and holds it to the files here; the edition itself is never written to. Its slips are mended there, by Tigran.

## `questions.tsv` and `references.tsv`, the ledgers

One line for each question in `questions.tsv`, and in `references.tsv` one line for each passage that answers it, both kept by `tools/quiz/apply.py`, never edited by hand:

| column | |
|---|---|
| `id` | given once, 1 to 819 in `quiz.tex`'s order to begin with, never reused or renumbered: the browser and the board keep answers by it, as a headword keeps its slug |
| `paper` | the paper whose questions it is among; it never changes |
| `origin` | 16 hex digits of the SHA-256 of the question as written (its `\qstart` to its `\qstop`, whitespace collapsed): a question edited upstream fails the build until its line is ruled on |
| `v` | the layout of its answers, from 1: what an answer stored by position means. It moves on when the answers' number, order or rightness changes, and an answer given under the old layout is never marked against the new one |
| `state` | what answers it: `-` not yet reviewed; `text` one or more passages of the text, in `references.tsv`; `note` a study note of the edition's; `none` neither; `drop` the question kept out; `gone` deleted upstream, its id kept |

And in `references.tsv`, for a `text` question one line per passage, in the order they are shown, and for a `note` one line, its paragraph:

| column | |
|---|---|
| `id` | the question's |
| `n` | from 1, the order shown |
| `ref` | the paragraph, `32:2.11`, or a run of one section's paragraphs shown whole, `0:3.2-8` |
| `quote` | the paragraph's own words, as the text has them, which occur there once and are whole words; or `¶`: the paragraph, or the run, shown whole, as a list given an item to a paragraph is best shown (Tigran, 2026-10-29, of the seven Absolutes at 0:3.2-8); for a `note`, the note's origin, as `build/study.py` keys notes |

A question may be answered by several passages, not adjoining, each quoted or whole (Tigran, 2026-10-29, ruling 13:1.1 and 13:2.7-8 for the spheres forever forbidden, and 13:1.5-6 for the secrets of Divinington). No length is refused: the build warns where over 1,000 characters would be shown under one question, so that a section ruled by a slip is noticed (his choice, the same day; until then a paragraph was held to 320 characters and a run to 640).

Two questions with one origin are paired with lines in order: `quiz.tex` asks Paper 137's question about the bride at Cana twice, at its lines 5930 and 5940 (d6c3206), and those are ids 749 and 750.

Seven questions are dropped until a figure is on the site: the Foreword's Q40–Q46 (ids 40–46) ask about the "Existential Flower", which is the edition's `images/Existential-Flower.jpg`, redrawn as `images/reality.pdf`, the figure it sets at 0:3.10, "The Seven Absolutes and the structure of reality" (Tigran, 2026-10-29). When it is, they are ruled again.

A question answered by a study note (the Excalibur question at 32, by the edition's note at 32:2.12) shows that note as the site shows it, once the paper's notes are reviewed into `data/study/NNN.toml`, whatever the reader's Notes setting, since it is the answer; until then it shows the paragraph and its reference, never a note not yet reviewed.

When the edition changes, the build says which question has no line and which line no question:

- `apply.py new`: the questions no line names get the next ids, unreviewed. It refuses while a line names a question the edition no longer has.
- `apply.py same ID LINE`: line `ID` is the question now at `quiz.tex:LINE`, as edited; add `--answers` if its answers changed, which moves `v` on. It goes back to unreviewed.
- `apply.py gone ID`: the question was deleted; its id stays taken.

## How a paper is reviewed

1. `make data`, then `.venv/bin/python tools/quiz/draft.py N`. It writes `var/quiz/review-NNN.md`: each question as the site shows it, with the changes from `quiz.tex` marked, its right answers, its slips, up to three candidate paragraphs and the edition's notes, each with the sentence that matched, and one proposed. It never overwrites a review.
2. Tigran writes his ruling on each question's `Ruling:` line: `yes`, a candidate's number or several (`6 and 1`; in words, "No, the correct candidate is 1"), the passages to show in order (`13:1.1 and 13:2.7-8`, `13:1.5 «words» and 13:1.6`, `text 0:3.2-8`; in words, "No, the correct reference is 0:3.2-8": a reference with «words» after it quotes them, one without is shown whole, and "or" is no ruling), `note 32:2.12`, `none` or `drop`, a reason after it if he likes. His lines are never overwritten.
3. `.venv/bin/python tools/quiz/apply.py rule N` writes the rulings into the ledgers, or lists what it cannot read and writes nothing.
4. `make data` holds each reference to its paragraph, and the paper is looked at on the dev server.
5. It is committed only once Tigran has looked; `deploy.sh` refuses an uncommitted `data/quiz/`.

### Many papers at once

Ruling paper by paper was too slow for the 114 papers left after the Foreword, Papers 1–12 and 32: the vast majority of proposals are plainly right (Tigran, 2026-10-29). So the rest are ruled from one file, `var/quiz/doubtful.md`, which holds only the questions in doubt, and everything else is accepted as proposed:

1. Every paper is drafted (step 1 above), each question with a `Checked:` line from a first reading saying why the proposal answers it.
2. A second reading, independent of the first, grades every question of every paper not yet ruled into `var/quiz/grades/NNN.tsv` (`id`, `grade`, `alt`, `reason`): `A`, the passage plainly answers it; `B`, only by inference, in part, with a wrong answer supported too, or with a better passage found; `C`, not answered. `alt` is a better reference in the ruling vocabulary, a run of paragraphs where a list is given one to a paragraph. The second reading is trusted by `tools/quiz/doubt.py calibrate N…` on papers already ruled: a changed ruling must come out B or C.
3. `.venv/bin/python tools/quiz/doubt.py make` writes `var/quiz/doubtful.md`: every question graded B, C or P, proposed by a note or by nothing, or named in `var/quiz/flags.md` §2, §3 or §5, as its review has it, with the second reading's grade and reason, its `alt` as one more candidate (and for a C or a P, the proposal), and `Why here:`. The rest are counted as plain; those the first reading hedged over are listed at its end, one line each. It never overwrites the file; `make --again` makes it anew from the grades as they stand, carrying every ruling in it over by id and keeping the old file as `doubtful.prev.md`, which is how the second reading's proposals of several passages (`P`) reached it on 2026-10-29.
4. Tigran rules in `doubtful.md` alone, as in a review; a blank ruling accepts what `Proposed:` says.
5. `.venv/bin/python tools/quiz/apply.py rule pending --accept --doubts` writes every paper with a line unreviewed: a question in `doubtful.md` as ruled there, every other as proposed. `apply.py check pending --doubts` holds it all to the build's rules first. Then `make data`, `make check`, a look, and the commit.

Done on 2026-10-30: 122 of the 677 questions were in doubt, and Tigran accepted 88 as proposed, changed 3 and dropped 31, among them Paper 138's only question, which leaves 125 papers with a quiz. Every question is reviewed: 774 by the text, 3 by a study note, 40 dropped.

## The text: `american.tsv` and `words.tsv`

The quiz is British, and the text beside it the press's American. `american.tsv` rewrites the quiz's spelling into the book's own, word for word, case kept: `centre` is `center`, `coordinate` the book's `co-ordinate`. Each word it writes must be a word of the book, and an entry nothing uses fails the build. Dates are put in the book's order by `build/quiz.py` itself, with the no-break space the book sets beside the era: "25 March 7 B.C." is "March 25, 7 B.C.", "Tuesday 4 April 30 A.D." is "Tuesday, April 4, A.D. 30".

Then every word the site shows must be a word of the book, as its search index sees it, or a word `words.tsv` allows and says why: a `name` (Excalibur, Fomalhaut), a word of ordinary `english` the book happens not to use (porridge), a `distractor` made up for a wrong answer (Avalonia), an `abbreviation` (NGC). An allowed word nothing uses fails, and so does one the book has after all.

## `tests/known-quiz-slips.tsv`

What is neither is a slip of the edition's, and so is a metric unit where the press gives miles or inches (trap 31), a date left British, a time on the 24-hour clock, the "~" of "~135 million", and the duplicate. The build requires the list to be exactly what it finds: a new slip fails, and so does one mended upstream and still listed. A slip that is a matter of wording (the units, the times, "~") is put to Tigran in its paper's review; his rewrite, once ruled, goes in `american.tsv` as a phrase.
