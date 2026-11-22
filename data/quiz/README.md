# The quiz, as the site asks it

The site's quiz, one question at a time, at the end of each paper that has questions and at `/quiz` (Tigran, 2026-10-28). Its questions are the files here, `NNN.toml`, a file to each paper that has a question, and `build/quiz.py` reads them alone.

They began as the British Study Edition's Cosmic Citizenship Quiz, `tex/quiz.tex` in `../urantia-study-edition`, which the build read from 2026-10-28, its spelling made American by a table, each question held to a ledger of ids and rulings kept here. On 2026-11-22 Tigran gave the edition up: "we don't need to import questions from that quiz.tex anymore, as I no longer wish to maintain the British Study Edition -- its essence will migrate into ubsite." So `tools/quiz/convert.py` converted it once, from quiz.tex at 0a1f055 and this directory's ledger at 0696b8d, as the KJV was converted into `data/kjv/`, and these files have been the master since: the edition is never read for the quiz again. Converted, its 817 questions gave the database's quiz tables row for row as quiz.tex had. The same day Paper 1, which had one question, was given 28 more, written for the site from a reading of the paper and its study notes.

## A paper's file

```toml
paper = 1
gone = [361]                 # only where an id was deleted: see below

[[question]]
id = 58
q = 'What is man’s choicest (in fact, the only possible) gift to God?'
a = [
  'consecration of will',
  'prayer',
  'meditation',
  'helping the poor',
]
right = ['consecration of will']
refs = ['1:1.2 «The affectionate dedication of the human will ...»']
```

The file is named for its paper and says so, `paper = 1`; the paper's questions are asked in the file's order. Nothing else may stand in a file, nor in a question, and every refusal is the build's: a key it does not know, a right answer that is none of the answers, fewer than two answers or more than nine, two answers with the same words, an id given twice.

| key | |
|---|---|
| `id` | given once and never reused, nor renumbered: the browser and the board keep answers by it, as a headword keeps its slug. A new question takes the next id after the highest of all the files, `gone` included |
| `v` | the layout of its answers, 1 when absent: what an answer stored by position means. Raise it when the answers' number, their order or which are right changes, and an answer given under the old layout is never marked against the new. Mending an answer's words leaves it |
| `q` | the question |
| `a` | its answers, in the order shown |
| `right` | the right answers, by their words; more than one makes the question a set, chosen together |
| `refs` | what answers it: the passages of the text shown under it once answered, in order (below) |
| `note` | or a study note answers it: its paragraph and its origin, `'32:2.12 8fbb4aa5e5c51c7f'` |
| `state` | or `'none'`, nothing answers it, or `'drop'`, the question kept out. A question with none of `refs`, `note` and `state` is not yet reviewed, and is asked with nothing shown under it |
| `shuffle` | `false` to show its answers as written each time, `true` to shuffle them, where the rule below would say otherwise; mostly absent |
| `gone` | the paper's ids whose questions were deleted, kept so that they are never given again: 361, 373, 401, 596 and 790, deleted upstream; 750, the edition's question about the wedding at Cana asked a second time; and 33 of the 40 dropped in 2026-10 (below), all three deleted here on 2026-11-22 |

A paper's questions are asked in a new order each time, and each question's answers too (Tigran, 2026-11-22), but where their order means something: yes and no, three or more numbers that rise ("1 year, 2 years, 3 years, 5 years, 12 years", one answer such as "unknown" allowed), the days of the week, or an answer of three words at most that names the others ("Both", "All three", "All of them"). The build decides by that rule (`build/quiz.py fixed_order`), 193 of the 804 asked on 2026-11-22, and `shuffle` overrules it for a question. An answer is kept by its place in the file, whatever order it was shown in, so the shuffle changes nothing for `v`.

`tests/test_quiz.py` holds the rules of `id` and `v` against the last commit: every id there is here, in the same paper, an id gone stays gone, and a question whose answers' layout changed has a higher `v`.

The text is TeX in the book's own spelling and order of dates ("March 25, 7~B.C."), set with the study edition's macros (`build/quiz_macros.py`, a closed table held to what the questions use: `\hyp{}`, `\ldots`, `\ts{th}`, `\bibemph{}`, a few more, and `$\alpha$`, `$\tau$`, `$\infty$`) and its expander. Quotation marks and apostrophes are the characters themselves, “ ” ‘ ’, which keeps every string a plain TOML literal, `'...'`, in which a backslash is only a backslash; a string holding an ASCII `'` needs `"..."` or `'''...'''`, and TeX's `` '' `` and `'` would be set the same.

## What answers a question

`refs` is one or more passages, in the order shown, each as a ruling words it: `1:1.2 «quoted words»` quotes them, the paragraph's own words, which occur there once and are whole words; a reference alone, `1:2.9`, shows its paragraph whole, and so does a run of one section's paragraphs, `0:3.2-8`, as a list given an item to a paragraph is best shown (Tigran, 2026-10-29, of the seven Absolutes at 0:3.2-8). Several passages need not adjoin (his ruling of 13:1.1 and 13:2.7-8 for the spheres forever forbidden, the same day). No length is refused: the build warns where over 1,000 characters would be shown under one question, so that a section given by a slip is noticed.

A question answered by a study note (the Excalibur question, 370, by the note at 32:2.12; 829 by the note at 1:0.1 on Psalms 33:6) shows that note as the site shows it, once its paper's notes are reviewed into `data/study/NNN.toml`, whatever the reader's Notes setting, since it is the answer; until then it shows the paragraph and its reference, never a note not yet reviewed. The origin is the one `build/study.py` keys notes by, and the build finds the note by it in the study edition, where every note not yet reviewed still stands.

The Foreword's Q40–Q46 (ids 40–46) are dropped until a figure is on the site: they ask about the "Existential Flower", which is the edition's `images/Existential-Flower.jpg`, redrawn as `images/reality.pdf`, the figure it sets at 0:3.10, "The Seven Absolutes and the structure of reality" (Tigran, 2026-10-29). When it is, they are ruled again. They are the only questions dropped: the other 33 dropped in October, Tigran ruled on 2026-11-22, were deleted, their ids kept in their papers' `gone`. Eleven had every answer right, so nothing to choose (174, 195, 210, 211, 219, 245, 283, 362, 434, 568, 595); seven rested on what the book does not say (55, 237, 238, 663, 728, 751, 815); seven were ambiguous, or had a wrong answer partly true (111, 267, 599, 661, 755, 777, 794); five asked one fact, the sacred spheres' light, five ways (146–150); and three were answerable but ruled out (220, 284, 717). Paper 138, whose only question was 751, has no quiz.

The edition's questions were reviewed in 2026-10, each given its passages from a draft that proposed candidates (Paper 32's on 10-28, the Foreword's and Papers 1–12's on 10-29, the other 114 papers' on 10-30 from one file of the questions in doubt), by tools retired with the conversion: `tools/quiz/draft.py`, `apply.py` and `doubt.py`, in the history before it. A question written here is written with its passages.

## `words.tsv`

Every word the site shows must be a word of the book, as its search index sees it, or a word `words.tsv` allows and says why: a `name` (Excalibur, Fomalhaut), a word of ordinary `english` the book happens not to use (porridge), a `distractor` made up for a wrong answer (Avalonia), an `abbreviation` (NGC). An allowed word nothing uses fails, and so does one the book has after all. A misspelling is caught so.

## `tests/known-quiz-slips.tsv`

What is neither is a slip, and so is a date in the British order, a "~" for about, and a question asked twice. The build requires the list to be exactly what it finds: a new slip fails, and so does one mended here and still listed. The edition's 63 came over with it and went the same day, by Tigran's ruling ("Keep metric units and 24h times and fix the rest"): 25 misspellings mended (mater, worls, Mezozoic, Boom of Psalms ...), the four dates of 703 put in the book's order, 479's "~135 million" made "about 135 million", and 750, the same question as 749, deleted; the 23 metric units where the press gives miles (trap 31) and the 9 times on the 24-hour clock stay as written, and are no slips since. The list is empty.
