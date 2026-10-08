-- Listening.  Every voice reduces to one shape: for each paragraph, a stretch of
-- one file.  Both readings are a file per section with offsets inside it, but
-- the player plays a queue of segments and never needs to know how they are filed.

CREATE TABLE audio_source (
  id INTEGER PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,                   -- 'mh', 'ai'
  label TEXT NOT NULL,                        -- 'Merritt Horn'
  kind TEXT NOT NULL CHECK (kind IN ('human','synthetic')),
  -- The directory the files are served from.  The same path here and on pi5;
  -- the app serves only names listed in audio_file, from under it.
  root TEXT NOT NULL,
  -- 'section' until a reading is aligned: its segments then start at a file's
  -- beginning and run to its end.  'paragraph' once every paragraph has its own.
  granularity TEXT NOT NULL CHECK (granularity IN ('section','paragraph')),
  revision TEXT,                              -- what made the segments: aligner, model, voice
  -- What must be said beside the audio wherever it plays: Boson AI's licence
  -- for Higgs TTS 3 requires its acknowledgment "displayed prominently
  -- together with the content".  NULL for Merritt Horn.
  credit TEXT,
  credit_url TEXT
);

CREATE TABLE audio_file (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES audio_source(id),
  name TEXT NOT NULL,                         -- under root: 'paper133/P133_02.mp3'
  bytes INTEGER NOT NULL,
  duration_ms INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  UNIQUE (source_id, name)
);

CREATE TABLE audio_segment (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES audio_source(id),
  section_id INTEGER NOT NULL REFERENCES section(id),
  -- NULL: the spoken heading, "1. The Father's Name", before the first paragraph.
  -- Until a reading is aligned, the heading segment is the whole file.
  paragraph_id INTEGER REFERENCES paragraph(id),
  file_id INTEGER NOT NULL REFERENCES audio_file(id),
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL,
  -- The share of the paragraph's words the aligner heard (human readings).
  match REAL,
  -- The speech text this audio was made from (synthetic readings): a segment
  -- whose sha differs from the current text's is stale, and the gate fails.
  speech_sha TEXT,
  ord INTEGER NOT NULL,                       -- playing order within the source
  CHECK (start_ms >= 0 AND end_ms > start_ms),
  UNIQUE (source_id, ord)
);
CREATE INDEX audio_segment_sec ON audio_segment(section_id, source_id, ord);

-- Paragraphs a reading does not contain (data/audio/mh-unread.tsv): no segment,
-- on the record, so the gate can tell a gap that is known from one that is not.
CREATE TABLE audio_unread (
  source_id INTEGER NOT NULL REFERENCES audio_source(id),
  paragraph_id INTEGER NOT NULL REFERENCES paragraph(id),
  why TEXT NOT NULL,
  PRIMARY KEY (source_id, paragraph_id)
);
CREATE UNIQUE INDEX audio_segment_para ON audio_segment(source_id, paragraph_id)
  WHERE paragraph_id IS NOT NULL;

-- The text as a voice is to read it (build/speech.py): numbers in words, list
-- marks spoken, brackets gone.  One row per section heading (paragraph_id NULL)
-- and per paragraph.  A synthetic recording carries the sha it was made from;
-- when the text changes, the sha does, and the recording is stale.
CREATE TABLE speech (
  id INTEGER PRIMARY KEY,
  section_id INTEGER NOT NULL REFERENCES section(id),
  paragraph_id INTEGER UNIQUE REFERENCES paragraph(id),
  text TEXT NOT NULL,
  sha TEXT NOT NULL
);
CREATE INDEX speech_sec ON speech(section_id);
