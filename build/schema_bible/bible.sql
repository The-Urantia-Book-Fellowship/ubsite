-- The Bible, var/bible.db (build/bible.py, `make bible`): the King James Version
-- from data/kjv/ and the Russian Synodal Bible from data/rsb/, and nothing else,
-- a database of its own beside ub.db, since it never changes with the book or
-- the index (Tigran, 2026-11-21: "a single bible.db").  Not build/schema/,
-- which db.create runs for ub.db.
--
-- A chapter of the site is a list of ROWS, each the verses of the two texts
-- that are the same words, keyed in the KJV's numbering (data/rsb/versification.tsv,
-- build/versify.py): a verse of each version is stored as its version numbers
-- it, with the row it stands in.

CREATE TABLE bible_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- The versions.  `key` is what a reader's setting `bible` stores, for ever.
-- The KJV is n 1: a row's base text, the one a page carries, is the KJV's
-- where the row has a verse of it, else the next version's.
CREATE TABLE bible_version (
  key    TEXT PRIMARY KEY,
  n      INTEGER NOT NULL UNIQUE,
  lang   TEXT NOT NULL,                 -- en, ru
  title  TEXT NOT NULL,                 -- King James Version; Синодальный перевод (data/bible.toml)
  label  TEXT NOT NULL,                 -- a column's short name: KJV; Синодальный
  by_en  TEXT NOT NULL,                 -- what it is and who made the copy, in English
  by_ru  TEXT NOT NULL                  -- and in Russian
);

-- The books, one to a book whichever versions have it, in the Contents'
-- order: the KJV's 39, the Synodal's eleven non-canonical between the
-- testaments (Tigran, 2026-11-21: "Between the testaments"), the KJV's 27.
-- `abbr` is the copies', and the address's for ever: /bible/Gen/1, /bible/Tob/1.
CREATE TABLE bible_book (
  id       INTEGER PRIMARY KEY,         -- 1..77
  abbr     TEXT NOT NULL UNIQUE,
  grp      TEXT NOT NULL CHECK (grp IN ('OT', 'DC', 'NT')),
  chapters INTEGER NOT NULL,            -- its pages: the KJV's chapters and any the Synodal has alone (Psa 151)
  en       TEXT NOT NULL                -- its name in English: the KJV's reference name, or data/bible.toml [names]
);

-- A version's book: its names, its title page, its own order.
CREATE TABLE bible_book_text (
  version     TEXT NOT NULL REFERENCES bible_version(key),
  book        INTEGER NOT NULL REFERENCES bible_book(id),
  n           INTEGER NOT NULL,         -- its place in the version's own order
  name        TEXT NOT NULL,            -- the KJV's I John, The Song of Solomon; the Synodal's 1-е Иоанна
  ref_name    TEXT NOT NULL,            -- a reference's: 1 John, Song of Solomon; 1 Ин, Песн
  title       TEXT NOT NULL,            -- its title page, the lines joined
  title_lines TEXT NOT NULL,            -- the same as JSON, [[line, main], ...]: main is a line set large
  title_note  TEXT NOT NULL,            -- the note on a title line (the Synodal's «У Евреев: …»), or ''
  title_note_at INTEGER NOT NULL,       -- the line it follows, or -1
  end_text    TEXT NOT NULL,            -- THE END OF THE PROPHETS. (Mal), THE END. (Rev), or ''
  chapters    INTEGER NOT NULL,
  verses      INTEGER NOT NULL,
  PRIMARY KEY (version, book)
);

-- A verse, numbered as its version numbers it.  `kind` 'title' is the KJV's
-- psalm title, set apart above its verse 1 (data/kjv/: the verse's head),
-- stored as a row 0 of its own so that the Synodal's title, a numbered verse,
-- stands beside it; a letter of Psalm 119 stays its verse's head.  `alt` 1 is
-- 3 Ezra 7's second series, "(36)" to "(105)".  The row: (rc, rv, rs) in the
-- KJV's numbering, rs 0 for a row with a KJV verse or a title's, 1.. for the
-- Synodal's own after the KJV's (rc, rv); a page is a book's chapter rc.
-- `text` is plain, `html` render(text, spans), `html_hy` with soft hyphens
-- (build/hyphen.py: Knuth's patterns, or hyph-ru) and the notes' marks.
CREATE TABLE bible_verse (
  id         INTEGER PRIMARY KEY,
  version    TEXT NOT NULL REFERENCES bible_version(key),
  book       INTEGER NOT NULL REFERENCES bible_book(id),
  chapter    INTEGER NOT NULL,
  verse      INTEGER NOT NULL,
  alt        INTEGER NOT NULL CHECK (alt IN (0, 1)),
  kind       TEXT NOT NULL CHECK (kind IN ('verse', 'title')),
  rc         INTEGER NOT NULL,
  rv         INTEGER NOT NULL,
  rs         INTEGER NOT NULL,
  pilcrow    INTEGER NOT NULL CHECK (pilcrow IN (0, 1)),
  head       TEXT NOT NULL,
  head_html  TEXT NOT NULL,
  text       TEXT NOT NULL,
  html       TEXT NOT NULL,
  html_hy    TEXT NOT NULL,
  after      TEXT NOT NULL,
  after_html TEXT NOT NULL,
  UNIQUE (version, book, chapter, verse, alt, kind)
);
CREATE INDEX bible_verse_row ON bible_verse(book, rc, rv, rs);

-- What a part of a verse or a note marks: the supplied words (italic), the
-- LORD (small capitals), a note's mark, a paragraph opening inside a verse.
-- Code-point offsets into that part.
CREATE TABLE bible_span (
  verse_id INTEGER NOT NULL REFERENCES bible_verse(id),
  part     TEXT NOT NULL CHECK (part IN ('head', 'text', 'after', 'note')),
  start    INTEGER NOT NULL,
  "end"    INTEGER NOT NULL,
  kind     TEXT NOT NULL CHECK (kind IN ('supplied', 'sc', 'fnref', 'pilcrow')),
  CHECK (0 <= start AND start <= "end")
);
CREATE INDEX bible_span_verse ON bible_span(verse_id);

-- A note: the KJV's translators' marginal note, at most one to a verse, at
-- its end; the Synodal's, where it stands in its verse or its heading.  `key`
-- names it in a page's ids: fn<key> the card, fnref<key> its mark.
CREATE TABLE bible_note (
  id       INTEGER PRIMARY KEY,
  verse_id INTEGER NOT NULL REFERENCES bible_verse(id),
  part     TEXT NOT NULL CHECK (part IN ('head', 'text')),
  n        INTEGER NOT NULL,
  key      TEXT NOT NULL UNIQUE,
  text     TEXT NOT NULL,
  html     TEXT NOT NULL,
  html_hy  TEXT NOT NULL,
  UNIQUE (verse_id, n)
);

-- Search, with ub.db's tokenizer, a pair to a version: its verses' words with
-- their titles and subscriptions (rowid = bible_verse.id), and its notes
-- (rowid = bible_note.id).  The Synodal's with ё read as е, as Russian search
-- reads them and as the translations' are (004_fts.sql): each is its own
-- copy, folded one letter for one, so a snippet stands where the text does.
CREATE VIRTUAL TABLE bible_kjv_fts USING fts5(
  text, tokenize='unicode61 remove_diacritics 2');
CREATE VIRTUAL TABLE bible_kjv_note_fts USING fts5(
  text, tokenize='unicode61 remove_diacritics 2');
CREATE VIRTUAL TABLE bible_rsb_fts USING fts5(
  text, tokenize='unicode61 remove_diacritics 2');
CREATE VIRTUAL TABLE bible_rsb_note_fts USING fts5(
  text, tokenize='unicode61 remove_diacritics 2');
