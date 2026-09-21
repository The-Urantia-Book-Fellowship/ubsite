-- Chronology events and appendix records SPECIALIZE index_entry rather than
-- living apart, so citations, cross-references and the reverse map cover them
-- for free -- which is what read_pack.py does, and why its reading pack can
-- show an appendix entry beside a paragraph without any special case.
CREATE TABLE index_entry (
  id INTEGER PRIMARY KEY,
  scope TEXT NOT NULL,                        -- 'az' | 'A'..'F'
  parent_id INTEGER REFERENCES index_entry(id),
  root_id INTEGER NOT NULL REFERENCES index_entry(id),
  level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 5),
  letter TEXT,                                -- the \idivider it falls under
  headword TEXT,                              -- level 1 only
  text TEXT NOT NULL,                         -- printed text, rendered
  -- Derived cache, like paragraph.html: keeps the italics uindex.sty gives
  -- \ab/\see/\qv/\cf/\versus, and makes every citation a link.  Gated:
  -- stripping its tags must return `text` byte for byte.
  text_html TEXT NOT NULL,
  text_expanded TEXT NOT NULL,                -- \ab{} expanded; the FTS column
  path TEXT NOT NULL,                         -- 'Adam > Eve > created'
  path_plain TEXT NOT NULL,                   -- same, citations stripped: the chip
  path_fold TEXT NOT NULL,
  qv INTEGER NOT NULL DEFAULT 0,
  source_file TEXT NOT NULL,
  source_line INTEGER NOT NULL,
  ord INTEGER NOT NULL,
  UNIQUE (source_file, source_line)           -- the 'where' read_pack dedupes on
);
CREATE INDEX index_entry_parent ON index_entry(parent_id);
CREATE INDEX index_entry_root   ON index_entry(root_id);
CREATE INDEX index_entry_path   ON index_entry(path_fold);

CREATE TABLE citation (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES index_entry(id) ON DELETE CASCADE,
  ord INTEGER NOT NULL,
  raw TEXT NOT NULL,                          -- verbatim inside \cit{}
  canonical TEXT NOT NULL,                    -- cite.fmt(), round-trips the grouping
  kind TEXT NOT NULL CHECK (kind IN ('para','sec','paper')),
  n_targets INTEGER NOT NULL
);
CREATE INDEX citation_entry ON citation(entry_id);

CREATE TABLE citation_target (
  id INTEGER PRIMARY KEY,
  citation_id INTEGER NOT NULL REFERENCES citation(id) ON DELETE CASCADE,
  entry_id INTEGER NOT NULL REFERENCES index_entry(id) ON DELETE CASCADE,
  paper INTEGER NOT NULL, section INTEGER, para INTEGER,
  precision TEXT NOT NULL CHECK (precision IN ('para','sec','paper')),
  paragraph_id INTEGER REFERENCES paragraph(id)
);
-- entry_stats runs three correlated subqueries per entry against this
-- table; without an entry_id index that is 34,600 entries x 50,758 rows
-- x 3, and the build does not finish.
CREATE INDEX citation_target_entry ON citation_target(entry_id);
CREATE INDEX citation_target_key ON citation_target(paper, section, para);
CREATE INDEX citation_target_pid ON citation_target(paragraph_id);

CREATE TABLE xref (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES index_entry(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('see','seealso')),
  ord INTEGER NOT NULL,
  target TEXT NOT NULL,
  target_fold TEXT NOT NULL,
  -- How the target resolves.  Most name a headword directly; a few are a
  -- conjunction ("Creator Sons, local universe Mother Spirits") and exactly one
  -- is a range ("Master Spirit #1 - #7") that resolves to seven headwords at
  -- once -- so a single head_entry_id cannot express every case, and `route`
  -- is what the gate requires to be non-null.
  route TEXT CHECK (route IN ('head','conjunction','range')),
  head_entry_id INTEGER REFERENCES index_entry(id),
  deep_entry_id INTEGER REFERENCES index_entry(id)
);
CREATE INDEX xref_entry ON xref(entry_id);

CREATE TABLE chronology_event (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES index_entry(id),
  ord INTEGER NOT NULL,
  year_label TEXT NOT NULL,                   -- '987,000,000,000 years ago', '1034 A.D.±'
  year_sort REAL,                             -- signed years relative to A.D. 1; NULL if unparsed
  approximate INTEGER NOT NULL DEFAULT 0,     -- the trailing ±
  month_label TEXT,                           -- NULL for a \chrontext: it hangs off the year
  text TEXT NOT NULL
);
CREATE INDEX chronology_sort ON chronology_event(year_sort);

CREATE TABLE appendix (
  letter TEXT PRIMARY KEY, name TEXT NOT NULL, title TEXT NOT NULL,
  n_entries INTEGER NOT NULL, n_events INTEGER NOT NULL
);
