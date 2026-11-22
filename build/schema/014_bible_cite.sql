-- The King James Version's verses a study note cites, in the Bible's pages (build/bibleref.py
-- store, from the links it made in the note's HTML; 2026-11-21): the KJV read
-- from its side, a verse's page naming the paragraphs whose notes cite it
-- (Tigran: "see if Urantia Book is quoting a given Bible verse, i.e. by
-- browsing from the Bible side").  The verses themselves are var/bible.db's;
-- `book` is its abbreviation.  A chapter cited whole has no verse; a run of
-- verses its first and last.  A note's `corrects` is not read.
CREATE TABLE bible_cite (
    footnote_id  INTEGER NOT NULL REFERENCES footnote(id),
    paragraph_id INTEGER NOT NULL REFERENCES paragraph(id),
    book         TEXT NOT NULL,
    chapter      INTEGER NOT NULL,
    verse        INTEGER,
    verse_end    INTEGER,
    CHECK ((verse IS NULL AND verse_end IS NULL) OR verse <= verse_end)
);
CREATE INDEX bible_cite_at ON bible_cite(book, chapter);
