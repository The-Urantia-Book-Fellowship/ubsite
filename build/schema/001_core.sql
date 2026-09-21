PRAGMA application_id = 0x55425354;   -- 'UBST'
PRAGMA user_version   = 1;

CREATE TABLE edition (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,                  -- 'press' | 'study'
  title TEXT NOT NULL,
  variety TEXT NOT NULL CHECK (variety IN ('authoritative','study')),
  source_repo TEXT NOT NULL,
  source_commit TEXT,
  source_dirty INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE part (
  n INTEGER PRIMARY KEY, title TEXT NOT NULL,
  first_paper INTEGER NOT NULL, last_paper INTEGER NOT NULL
);

CREATE TABLE paper (
  id INTEGER PRIMARY KEY,
  edition_id INTEGER NOT NULL REFERENCES edition(id),
  n INTEGER NOT NULL,
  part_n INTEGER REFERENCES part(n),
  title TEXT NOT NULL,
  author TEXT,                                -- the revelatory author
  source_file TEXT NOT NULL,
  UNIQUE (edition_id, n)
);

CREATE TABLE section (
  id INTEGER PRIMARY KEY,
  edition_id INTEGER NOT NULL REFERENCES edition(id),
  paper_id INTEGER NOT NULL REFERENCES paper(id),
  paper_n INTEGER NOT NULL,
  n INTEGER NOT NULL,                         -- 0 = the untitled introduction
  title TEXT,                                 -- NULL iff n = 0
  -- \usectiontwo{9 and 10}: one printed heading spanning two section numbers.
  -- p139's paragraphs all run 139:9.x and the text jumps straight to 11, so
  -- section 10 is a label, not a container.  Only sections that hold paragraphs
  -- get a row; the second number is recorded here.
  combined_with INTEGER,
  UNIQUE (edition_id, paper_n, n)
);

CREATE TABLE paragraph (
  id INTEGER PRIMARY KEY,
  edition_id INTEGER NOT NULL REFERENCES edition(id),
  section_id INTEGER NOT NULL REFERENCES section(id),
  paper_n INTEGER NOT NULL, section_n INTEGER NOT NULL, para_n INTEGER NOT NULL,
  ref TEXT NOT NULL,                          -- '133:2.1'
  srt_id TEXT NOT NULL,                       -- 'U133_2_1', the SRT anchor
  ord INTEGER NOT NULL,                       -- reading order within the edition
  src TEXT NOT NULL CHECK (src IN ('vs','poetry','vsmark')),
  gap_before REAL NOT NULL DEFAULT 0,         -- \pc: a 1955 blank-line group start
  text TEXT NOT NULL,
  -- A DERIVED CACHE: render(text, spans).  Stored so no consumer needs a
  -- renderer and they cannot drift; check_roundtrip regenerates it and
  -- asserts stripping its tags returns `text` byte for byte.
  html TEXT NOT NULL,
  word_count INTEGER NOT NULL,
  source_line INTEGER NOT NULL,
  UNIQUE (edition_id, paper_n, section_n, para_n),
  UNIQUE (edition_id, ord)
);
CREATE INDEX paragraph_ref ON paragraph(edition_id, ref);
-- The reverse map joins section- and paper-precision citations onto every
-- paragraph they cover.  Without these, each of the 2,254 section-precision
-- targets scans all 14,586 paragraphs: tens of millions of comparisons, and
-- the build never finishes.
CREATE INDEX paragraph_sec ON paragraph(paper_n, section_n);
CREATE INDEX paragraph_paper ON paragraph(paper_n);

-- Code-point offsets into paragraph.text.  The source of truth for markup;
-- the HTML the site serves is derived from these, never the other way round.
CREATE TABLE span (
  id INTEGER PRIMARY KEY,
  paragraph_id INTEGER NOT NULL REFERENCES paragraph(id) ON DELETE CASCADE,
  start INTEGER NOT NULL,
  "end" INTEGER NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN
    ('em','redletter','supplied','sup','sc','ul','listmark','dotleader',
     'lang','link','fnref','url','nobreak')),
  attr TEXT,
  ord INTEGER NOT NULL,
  CHECK ("end" >= start)
);
CREATE INDEX span_para ON span(paragraph_id, start);
CREATE INDEX span_kind ON span(kind);

CREATE TABLE footnote (
  id INTEGER PRIMARY KEY,
  edition_id INTEGER NOT NULL REFERENCES edition(id),
  kind TEXT NOT NULL CHECK (kind IN ('variant-1955','study','bible-marginal')),
  paragraph_id INTEGER REFERENCES paragraph(id),
  anchor INTEGER,                             -- code-point offset in paragraph.text
  ord INTEGER NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX footnote_para ON footnote(paragraph_id);
