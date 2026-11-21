-- The King James Version, var/kjv.db (build/kjv.py, `make kjv`), from data/kjv/
-- alone: a database of its own, beside ub.db, since it never changes with the
-- book or the index (Tigran, 2026-11-21).  Not build/schema/, which db.create
-- runs for ub.db.

CREATE TABLE kjv_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- The 66 books in the KJV's order.  `abbr` is the edition's, and the address's
-- for ever: /kjv/Gen/1, /kjv/Sol/2.
CREATE TABLE kjv_book (
  id          INTEGER PRIMARY KEY,            -- 1..66
  abbr        TEXT NOT NULL UNIQUE,
  testament   TEXT NOT NULL CHECK (testament IN ('OT', 'NT')),
  name        TEXT NOT NULL,                  -- the KJV's: I John, The Song of Solomon
  ref_name    TEXT NOT NULL,                  -- a reference's: 1 John, Song of Solomon
  title       TEXT NOT NULL,                  -- its title page, the lines joined: the first book of moses, called genesis
  title_lines TEXT NOT NULL,                  -- the same as JSON, [[line, main], ...]: main is the line set large
  end_text    TEXT NOT NULL,                  -- THE END OF THE PROPHETS. (Mal), THE END. (Rev), or ''
  chapters    INTEGER NOT NULL,
  verses      INTEGER NOT NULL
);

-- A verse.  Its `text` is plain, `html` render(text, spans), `html_hy` with the
-- soft hyphens Knuth's patterns allow (build/hyphen.py), and the note's mark,
-- an empty a.fn, at the text's end.  A psalm's title or a letter of Psalm 119
-- is its `head`, set above it; an epistle's subscription its `after`, set
-- after it; `pilcrow` the 1769's paragraph mark at its head.
CREATE TABLE kjv_verse (
  id         INTEGER PRIMARY KEY,             -- 1.. in the Bible's order
  book       INTEGER NOT NULL REFERENCES kjv_book(id),
  chapter    INTEGER NOT NULL,
  verse      INTEGER NOT NULL,
  pilcrow    INTEGER NOT NULL CHECK (pilcrow IN (0, 1)),
  head       TEXT NOT NULL,
  head_html  TEXT NOT NULL,
  text       TEXT NOT NULL,
  html       TEXT NOT NULL,
  html_hy    TEXT NOT NULL,
  after      TEXT NOT NULL,
  after_html TEXT NOT NULL,
  UNIQUE (book, chapter, verse)
);

-- What a part of a verse, or its note, marks: the supplied words (italic), the
-- LORD (small capitals), the note's mark.  Code-point offsets into that part.
CREATE TABLE kjv_span (
  verse_id INTEGER NOT NULL REFERENCES kjv_verse(id),
  part     TEXT NOT NULL CHECK (part IN ('head', 'text', 'after', 'note')),
  start    INTEGER NOT NULL,
  "end"    INTEGER NOT NULL,
  kind     TEXT NOT NULL CHECK (kind IN ('supplied', 'sc', 'fnref')),
  CHECK (0 <= start AND start <= "end")
);
CREATE INDEX kjv_span_verse ON kjv_span(verse_id);

-- The translators' marginal note, at most one to a verse, its glosses one
-- after another ("lemma: gloss.").
CREATE TABLE kjv_note (
  verse_id INTEGER PRIMARY KEY REFERENCES kjv_verse(id),
  text     TEXT NOT NULL,
  html     TEXT NOT NULL,
  html_hy  TEXT NOT NULL
);

-- Search, with ub.db's tokenizer: the verse's words, its title and
-- subscription with them (rowid = kjv_verse.id), and the notes (rowid =
-- verse_id).  Each its own copy; the database is immutable after the build.
CREATE VIRTUAL TABLE kjv_verse_fts USING fts5(
  text, tokenize='unicode61 remove_diacritics 2');
CREATE VIRTUAL TABLE kjv_note_fts USING fts5(
  text, tokenize='unicode61 remove_diacritics 2');
