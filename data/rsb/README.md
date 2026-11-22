# The Russian Synodal Bible

This directory is the site's copy of the Russian Synodal Bible (Синодальный перевод, 1876), in Tigran Aivazian's edition made for Bibles.org.uk, with its notes. `make bible` builds it into `var/bible.db` beside the King James Version (`data/kjv/`), and the site's `/bible` pages show the two side by side, a verse to a row.

**The copy is the master.** It was converted once, on 2026-11-21, from Tigran's edition (`../russian-synodal-bible`, whose text has not changed since 2016; read at the commit `SOURCE.tsv` names, with each file's SHA-256), as the KJV's was from the study edition (Tigran, 2026-11-21: "you can just convert and copy them in whatever format you need into ubsite"). The edition is not read for it again. A change here is a reviewed commit, like any change to `data/`.

## What it holds

The Synodal Bible as printed (Tigran, 2026-11-21: "Synodal as printed"): its 66 books and the eleven it prints as non-canonical, marked * in its contents (2 and 3 Ezra, Tobit, Judith, Wisdom, Sirach, the Epistle of Jeremiah, Baruch, 1 to 3 Maccabees), with the Greek's additions inside books (Daniel 3:24–90 and chapters 13 and 14, Psalm 151, the Prayer of Manasseh as 2 Chronicles 37, Esther's opening and its words in brackets). Not the edition's Acts 29, Sonnini's "lost chapter", which is no Synodal Bible's, nor the apocrypha it prints after the Bible (1 Enoch, Jubilees, the Testaments of the Twelve Patriarchs and the rest).

## The files

- `books.tsv`: the 77 books in the edition's order, a line to each: `n`, `abbr` (the edition's, the KJV copy's for the 66: Gen … Rev, and Tob, Sir, 1Ma … for the rest, which the addresses use for ever), `group` (OT, DC for the non-canonical, NT), `name` (its contents' name: Бытие, 1-я Царств), `ref` (the abbreviation a reference writes: Быт, 1 Цар), `title` (the title page, its lines separated by `\\`, a line set large in `\bibtitlemain{…}`, a note at the end of its line).
- `<abbr>.tsv`, a book to a file, a verse to a line: `chapter`, `verse` as the edition numbers it (a psalm's title is its verse 0 or 1; 3 Ezra 7 numbers seventy verses between 35 and 36 "(36)" to "(105)", kept so), `pilcrow` (¶ where the edition opens a paragraph, `\rsbpar`), `head` (a heading over the verse: «Молитва Манассии…» over 2 Chronicles 37, «Предисловие» over Sirach's prologue), `text`.
- The text holds three macros and no others: `\bibemph{…}`, the words supplied, set in italic; `\fns{…}`, a note, where it stands; and `\rsbpar`, where a paragraph opens inside a verse (twelve, Genesis 35:22 the first). What TeX wrote for a character is the character: the stress mark (U+0301, 694 of them, «чт́о»), « », the em dash after a no-break space, the ellipsis. The words in square brackets are the edition's: words of the Greek, or the Slavonic's, which the Hebrew has not.
- `SOURCE.tsv`: the edition's repository and commit, and each book's file's SHA-256.
- `versification.tsv`: where its numbering differs from the KJV's (below).
- `corrections.tsv`, when there is one: slips mended in the copy, each with its reason. None so far: the conversion found no word of both alphabets and no gap in any chapter's numbering.

`python -m tools.rsb.convert --check` proves that the copy is the edition's text with those corrections, and nothing else.

## The numbering, `versification.tsv`

A chapter of the site's Bible is a list of rows, each a verse of the KJV and the Synodal's verse that is the same words, the row's address the KJV's (`build/versify.py`). The two number alike in most chapters but not all: 188 of them differ, 148 in the Psalms, which the Synodal numbers as the Greek does (its 22 is the KJV's 23) and in which it counts a title as a verse. The file says only where they differ, a line to a run, with its reason:

- `Psa 9:22-39 → Psa 10:1-18`: the same verses, numbered otherwise, one to one;
- `Psa 3:1 → Psa 3:0`: a psalm's title, which the KJV sets apart above verse 1;
- `2Co 13:12 → 2Co 13:12-13`, `1Sa 20:42-43 → 1Sa 20:42`: one verse of one text is two of the other's;
- `Dan 3:24-90 → + Dan 3:23`: the Synodal's alone, rows after the KJV's 3:23; `Psa 151:0-7 → own`, a chapter of its own;
- `- → Sol 1:1`: the KJV's alone (the Song's title, which the Synodal prints as the book's).

Every verse of both texts must stand in exactly one row, which the build requires. A book only the Synodal has is its own numbering and needs no line.

The table was made by `python -m tools.rsb.versify` from SIL's standard versification files (github.com/sillsdev/libpalaso, `SIL.Scripture/Resources/`, MIT; `rso` the Synodal with its non-canonical books, `eng` the English Bibles'), each of which maps its numbering to the Hebrew's: composed through the Hebrew's, they say which KJV verse each Synodal verse is. Neither is this edition's exactly, and they have slips of their own (rso's "PSA 89:2-6 = PSA 90:1-6", five verses to six), so the result was held to two checks that need no witness: every verse of both copies placed, and each chapter's verses aligned again by their lengths alone, as Gale and Church align sentences, a chapter at a time. Where those disagreed the two texts were read side by side, and 29 runs were set right by the reading (22 lines "read:" in the file: Daniel 5 and 6, which this edition numbers as the KJV does; Psalms 86, 89, 114 and 115; Revelation 20:7–9; the Greek's verses at Proverbs 13:14 and 18:8, rows of their own). The files are named by address and SHA-256 in `sources.toml` (`[rsb_vrs]`), fetched by `python -m tools.rsb.versify --fetch` into `var/rsb/vrs/`, and never committed; `var/rsb/review.md` is the last review.

## Its rights

The Synodal translation of 1876 is in the public domain. The edition, its corrections and its notes, are Tigran's, shown here by Tigran's word.
