-- The SRT Committee's reasons for the changes to the 1955 text (build/srt.py),
-- read from the snapshot of the Fellowship's page in data/srt/.  One row for
-- each change the committee considered; an entry of the page -- one place in
-- the book -- holds one change or several.  Every change is kept, whatever was
-- decided; the site shows those a 1955 note points to (footnote.srt_item_id).
CREATE TABLE srt_item (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,             -- the entry's anchor on the page, 'U41_4_4': its link
  n INTEGER NOT NULL,             -- the change's place under that anchor, from 1
  label TEXT NOT NULL,            -- the place as the page names it, in the FOUNDATION's
                                  -- numbering: '41:4.4', 'Contents xiii', 'Part IV'
  paragraph_id INTEGER REFERENCES paragraph(id),   -- ours; NULL for a heading, a part, the contents
  page TEXT,                      -- its 1955 page and paragraph, '460.1'
  decision TEXT NOT NULL CHECK (decision IN
    ('adopted','rejected','no-action','informational','no-decision')),
  verdict TEXT NOT NULL,          -- the decision as the page prints it: 'No action required'
  -- "1955 text" as the page quotes it, the changed words in <mark class="chg">.
  -- NOT the 1955 text: the page misquotes it (85:4.1, 90:2.9), and only the
  -- press says what 1955 printed.  Used to pair a note with its change; shown nowhere.
  then_text TEXT NOT NULL,
  then_html TEXT NOT NULL,
  review_text TEXT,               -- what was proposed
  why_text TEXT NOT NULL,         -- the reasons; empty when the decision is all there is
  why_html TEXT NOT NULL,         -- derived cache, links rewritten to our paragraphs
  see_id INTEGER REFERENCES srt_item(id),   -- the note it refers to: "See SRT note for 89:3.1"
  why_html_hy TEXT NOT NULL,      -- why_html with the book's soft hyphens, for a 1955 card
  UNIQUE (name, n)
);
CREATE INDEX srt_item_para ON srt_item(paragraph_id);
