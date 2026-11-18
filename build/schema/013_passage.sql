-- The passages of the moment (build/passage.py): what the home page shows one
-- of at each visit, from data/passages.tsv, a list Tigran reviews line by line
-- (DECISIONS.md, The home page).  Each is words of one paragraph, as that
-- paragraph sets them, its red letter and its italics, or the paragraph whole.
-- Empty where the list is: the home page then shows no passage.

CREATE TABLE passage (
  n            INTEGER PRIMARY KEY,            -- its place in the list, from 1
  paragraph_id INTEGER NOT NULL REFERENCES paragraph(id),
  ref          TEXT NOT NULL,                  -- '48:7.24', where the passage's link goes
  paper_n      INTEGER NOT NULL,
  title        TEXT NOT NULL,                  -- its paper's, which the link names
  start        INTEGER NOT NULL,               -- where the words begin in the paragraph's text
  text         TEXT NOT NULL,                  -- the words
  -- render(text, the paragraph's spans within it): stripping its tags gives
  -- `text` byte for byte (check_passage).
  html         TEXT NOT NULL,
  UNIQUE (paragraph_id, start)
);
