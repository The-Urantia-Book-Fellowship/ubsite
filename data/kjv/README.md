# The King James Version

This directory is the site's copy of the King James Version (the Authorized Version, 1611, in the standard text of 1769), with the translators' marginal notes. `make kjv` builds `var/kjv.db` from it and from nothing else, and the site's `/kjv` pages and every link to a verse are drawn from that database.

**The copy is the master.** It was converted once, on 2026-11-21, from The British Study Edition's KJV (`../urantia-study-edition`, `tex/Gen.tex` … `tex/Rev.tex`, added in 7e652d3 of 2021-09-21 and never edited since; read at the commit `SOURCE.tsv` names, with each file's SHA-256). The edition is not read for it again: Tigran, 2026-11-21, "Since they are not going to change, you can just convert and copy them in whatever format you need into ubsite". A change here is a reviewed commit, like any change to `data/`.

## The files

- `books.tsv`: the 66 books in the KJV's order, a line to each: `n`, `abbr` (the edition's, Gen … Rev, which the addresses use for ever: `/kjv/Sol/2`), `testament` (OT, NT), `name` (the KJV's: I John, The Song of Solomon), `ref_name` (the name a reference writes: 1 John, Song of Solomon), `head` (the running head), `title` (the book's title page as the edition sets it, its lines separated by `\\`, the main one in `\bibtitlemain{…}`), `end` ("THE END OF THE PROPHETS." after Malachi, "THE END." after Revelation).
- `<abbr>.tsv`, a book to a file, a verse to a line: `chapter`, `verse`, `pilcrow` (¶ where the 1769 marks a paragraph), `head` (a psalm's title, or a letter of Psalm 119, set above the verse), `text`, `after` (an epistle's subscription, set after its last verse), `note` (the translators' marginal note, its glosses one after another, each `lemma: gloss.`, a lemma ending "..." standing for words of the verse that begin so).
- The text and the notes hold two macros and no others: `\bibemph{…}`, the words the translators supplied, which the KJV sets in italic, and `\textsc{…}`, the LORD in small capitals.
- `SOURCE.tsv`: the edition's repository and commit, and each book's file's SHA-256.
- `corrections.tsv` and `witness.tsv`: every difference from the edition (below).

## What differs from the edition

`python -m tools.kjv.convert --check` proves that the copy is the edition's text with these, and nothing else.

1. **The print-only macros are gone**: `\-` (19 hints of where a word may break, several wrong: "weig\-hed", "Eve\-ry"), `\tunemarkup{pgauraone}{\linebreak}` (1Ch 1:3), `\enlargethispage*` (Tit, Phi). The site hyphenates the KJV with Knuth's patterns, as it does the book.
2. **126 doubled stops in the notes**: whoever made the edition's copy ended every gloss with a full stop, also after a question or an "etc.": 117 "?." and 9 "..", taken out by a rule of the converter.
3. **`corrections.tsv`**, 56 slips mended, a line each with its reason: lemmas spelt otherwise than their verse ("combing:" at 1Sa 16:4, whose verse has "his coming"), slips in a gloss ("or, hat a great thing", 1Sa 12:24; "buglers" for "burglers", Eze 7:22), stops lost, and three notes of the New Testament moved to the verse their lemma stands in (Act 17:20 to 17:19, 1Co 5:12 to 6:12, 1Jo 1:10 to 2:10). Every slip was found by setting the copy beside the witness (below) and by a second check that needs none: a note's lemma must stand in its own verse.
4. **`witness.tsv`**, what the copy takes from eBible.org's KJV of the 1769 text, by Tigran's rulings of 2026-11-21 on what the comparison found (`python -m tools.kjv.merge`, which `--check` holds to the witness):
   - the 1769's paragraph marks, ¶, 2,970 of them, the last at Acts 20:36;
   - the 116 psalms' titles and Psalm 119's 22 letters, which the edition ran into the verse, set above it, and the 14 epistles' subscriptions set after their last verse, each in the copy's own words;
   - 109 notes of the Old Testament in the witness's words, where the copy's were worded otherwise ("houghed oxen" for the copy's "lamed oxen", Gen 49:6) or lacking (the repeated "And the evening…" at Gen 1:8, 13, 19, 23, 31), some of them a later editor's rather than the 1769's (Exo 26:4, "selvedge: an edge of cloth so woven that it cannot unravel"), as ruled. Not taken: a note whose lemma is not in its verse, the witness's own slip (Gen 18:1, 2Ch 6:29, 2Ch 6:32, Job 8:20), and 2Sa 23:8, where the witness's third gloss is garbled. The New Testament's notes are the copy's alone: the witness has none.

**Kept as the copy has them, by ruling**: names written as one word, "Bethel", "Beersheba", "Padanaram", where the 1769 prints "Beth-el", and "Caesar", "Judaea" for its "Cæsar", "Judæa", as the Urantia Book spells them; and the 21 verses whose words differ from the witness as one printing from another ("cannot" for "can not", Acts 7:29 "Midian" for "Madian", six subscriptions worded otherwise).

## The witness

eBible.org's King James Version with Apocrypha, the 1769 text, USFM, "Public Domain" by its own statement, "brought to you courtesy of the Crosswire Bible Society and eBible.org", which adds: "You may copy the King James Version of the Holy Bible freely." It is named by its address and SHA-256 in `sources.toml` (`[kjv_witness]`), fetched by `python -m tools.kjv.compare --fetch` into `var/kjv/witness/`, and never committed. `python -m tools.kjv.compare` writes every difference that remains to `var/kjv/compare.txt`.

Outside the United Kingdom the KJV is in the public domain; within it, the Crown's letters patent govern printing it and importing printed copies.
