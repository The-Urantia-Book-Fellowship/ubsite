-- ChangeLog.md (build/changelog.py), for the page /changelog: every block of
-- the file, a heading, a paragraph or an entry, in its order.  The hosts have
-- no .git, so each is dated here, by the commit that wrote it.
CREATE TABLE changelog (
  line INTEGER PRIMARY KEY,       -- in ChangeLog.md, from 1
  part TEXT NOT NULL CHECK (part IN ('intro', 'readers', 'developers', 'began')),
  version TEXT,                   -- 'Unreleased' or '1.2.0'; NULL outside a version
  released TEXT,                  -- the version's date, YYYY-MM-DD; NULL while unreleased
  heading TEXT,                   -- the ### it stands under, or is; NULL above any
  kind TEXT NOT NULL CHECK (kind IN ('h1', 'h2', 'h3', 'para', 'entry')),
  html TEXT NOT NULL,             -- its words, the file's Markdown made HTML; a
                                  -- version's heading is its name, 'Unreleased'
  text TEXT NOT NULL,             -- the same without the tags
  written TEXT NOT NULL           -- the day its commit was made, where it was made, YYYY-MM-DD
);
