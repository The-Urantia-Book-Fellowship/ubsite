-- read_pack.Reverse, materialized.  Filed by PRECISION, exactly as that class
-- does: a citation lands in exactly one of para / sec / paper.  Keeping them
-- apart is what lets the reader show a blanket citation once at the section
-- head instead of repeating it under all 470 of Paper 15's paragraphs.
CREATE TABLE para_citers (
  paragraph_id INTEGER NOT NULL REFERENCES paragraph(id),
  entry_id INTEGER NOT NULL REFERENCES index_entry(id),
  precision TEXT NOT NULL CHECK (precision IN ('para','sec','paper')),
  PRIMARY KEY (paragraph_id, entry_id, precision)
) WITHOUT ROWID;
CREATE INDEX para_citers_entry ON para_citers(entry_id);

CREATE TABLE para_density (
  paragraph_id INTEGER PRIMARY KEY REFERENCES paragraph(id),
  precise_citers INTEGER NOT NULL,
  section_citers INTEGER NOT NULL,
  paper_citers INTEGER NOT NULL,
  any_citers INTEGER NOT NULL,
  thin INTEGER NOT NULL,                      -- precise_citers = 0
  orphan INTEGER NOT NULL,                    -- any_citers = 0
  density REAL NOT NULL                       -- precise citers per 100 words
);
CREATE INDEX para_density_thin ON para_density(thin);

CREATE TABLE entry_stats (
  entry_id INTEGER PRIMARY KEY REFERENCES index_entry(id),
  n_citations INTEGER NOT NULL,
  n_targets INTEGER NOT NULL,
  n_paragraphs INTEGER NOT NULL,
  n_papers INTEGER NOT NULL,
  n_descendants INTEGER NOT NULL
);

-- The concept graph, at LEVEL-1 HEADWORD grain and paragraph precision only.
-- Over all 32,837 entries this explodes; over 4,736 roots it does not.  A
-- section- or paper-wide citation would make one paper emit a clique of its
-- every citer, so those are excluded outright.
CREATE TABLE cocitation (
  a_root_id INTEGER NOT NULL REFERENCES index_entry(id),
  b_root_id INTEGER NOT NULL REFERENCES index_entry(id),
  shared INTEGER NOT NULL,
  jaccard REAL NOT NULL,
  PRIMARY KEY (a_root_id, b_root_id),
  CHECK (a_root_id < b_root_id)
) WITHOUT ROWID;
CREATE INDEX cocitation_b ON cocitation(b_root_id);

CREATE TABLE build (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  built_at TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  degraded INTEGER NOT NULL DEFAULT 0
);
-- The commit each source repo was read at.  `dirty` means the inputs had
-- uncommitted changes, so the commit alone does not reproduce this database.
CREATE TABLE build_source (
  repo TEXT PRIMARY KEY,                      -- 'press' | 'index'
  commit_id TEXT NOT NULL,
  dirty INTEGER NOT NULL,
  rev TEXT NOT NULL,                          -- as sources.toml asked: 'worktree' or a revision
  committed_at TEXT,                          -- that commit's date, YYYY-MM-DD
  commit_url TEXT                             -- its page on the repo's host; NULL if none is set
);
CREATE TABLE source_file (
  id INTEGER PRIMARY KEY,
  repo TEXT NOT NULL, repo_commit TEXT, repo_dirty INTEGER NOT NULL,
  path TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL,
  UNIQUE (repo, path)
);
CREATE TABLE stat (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
