-- The text API (/api/v1, ubsite/api.py).  Everything it serves is made here,
-- at build time, so the route only selects and concatenates.

-- The Foundation's numbering beside ours (build/foundation.py), read from its
-- own HTML of the SRT.  The two differ in 107 paragraphs: it numbers the
-- `* * *` separators of 134:6 and 144:5, files 139's combined "9 and 10" under
-- 10, and does not number 0:12.10 ACKNOWLEDGMENT.  Its other data -- every
-- translation -- uses its numbers, so a site joining ours to it needs both.
CREATE TABLE uf_paragraph (
  paragraph_id INTEGER PRIMARY KEY REFERENCES paragraph(id),
  ref TEXT                                    -- '134:6.15'; NULL where it has none
);
CREATE TABLE uf_section (
  section_id INTEGER PRIMARY KEY REFERENCES section(id),
  ref TEXT                                    -- '139:10'
);

-- Text versions (build/versions.py).  ub.db remembers no earlier build, so the
-- history is kept in data/text/, checked in and append-only, and copied here.
CREATE TABLE text_version (
  n INTEGER PRIMARY KEY,
  made_on TEXT NOT NULL,                      -- YYYY-MM-DD
  press_commit TEXT NOT NULL,                 -- the press commit; '+dirty' if the tree was
  changed INTEGER NOT NULL,                   -- records new or different in this version
  removed INTEGER NOT NULL
);
-- One record per part, paper, section and paragraph: what /api/v1/text sends.
-- A rowid table: WITHOUT ROWID keeps whole rows in its B-tree, and these are
-- up to 10 KB each, which took 39 MB to hold 15.
CREATE TABLE text_unit (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('part','paper','section','paragraph')),
  key TEXT NOT NULL,                          -- '3', '101', '101:4', '101:4.2'
  ord INTEGER NOT NULL,                       -- reading order within its kind
  body TEXT NOT NULL,                         -- the record, as JSON, its hash included
  hash TEXT NOT NULL,
  version INTEGER NOT NULL REFERENCES text_version(n),   -- when this content first appeared
  UNIQUE (kind, key)
);
CREATE INDEX text_unit_version ON text_unit(version);
-- A record that existed once and does not now, and the version that removed it.
CREATE TABLE text_removed (
  kind TEXT NOT NULL,
  key TEXT NOT NULL,
  version INTEGER NOT NULL REFERENCES text_version(n),
  PRIMARY KEY (kind, key)
) WITHOUT ROWID;
