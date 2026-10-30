-- The British Study Edition's quiz (build/quiz.py): its questions, each with
-- the id data/quiz/questions.tsv gives it for ever, and their answers in the
-- order quiz.tex gives them.  Their text is the edition's, its spelling made
-- American and its dates put in the book's order; `html` is that text set,
-- and its tags stripped give `text` back.
CREATE TABLE quiz_question (
  id INTEGER PRIMARY KEY,                    -- given once, never reused: answers are kept by it
  paper_n INTEGER NOT NULL,                  -- paper.n; check_db holds it to a paper
  ord INTEGER NOT NULL,                      -- its place among the paper's questions, from 1
  line INTEGER NOT NULL,                     -- of its \qstart in quiz.tex, at the commit read
  origin TEXT NOT NULL,                      -- 16 hex: SHA-256 of the question as written
  v INTEGER NOT NULL,                        -- the layout of its answers: what a stored answer means
  mask INTEGER NOT NULL,                     -- the right answers, bit n for answer n
  multi INTEGER NOT NULL,                    -- more than one answer is right
  text TEXT NOT NULL,
  html TEXT NOT NULL,
  -- What answers it, as reviewed: '-' not yet; 'text' a paragraph and words
  -- quoted from it, or paragraphs shown whole; 'note' a study note there;
  -- 'none' neither; 'drop' kept out.
  state TEXT NOT NULL CHECK (state IN ('-','text','note','none','drop')),
  -- The study note that answers it, once its paper's notes are reviewed
  -- (data/study/NNN.toml); until then the quiz shows its paragraph, quiz_ref's.
  footnote_id INTEGER REFERENCES footnote(id),
  UNIQUE (paper_n, ord)
);

-- The passages that answer a question, in the order ruled (data/quiz/
-- references.tsv): one or more for 'text', the note's paragraph for 'note'.
CREATE TABLE quiz_ref (
  question_id INTEGER NOT NULL REFERENCES quiz_question(id),
  n INTEGER NOT NULL,                        -- from 1
  paragraph_id INTEGER NOT NULL REFERENCES paragraph(id),
  -- The last of a run of one section's paragraphs shown whole, "0:3.2-8", from
  -- paragraph_id: `quote` is then their text, one to a line, and quote_at 0.
  paragraph_last_id INTEGER REFERENCES paragraph(id),
  quote TEXT NOT NULL,                       -- the paragraph's own words, once, whole words
  quote_at INTEGER NOT NULL,                 -- where in paragraph.text they begin
  quote_html TEXT NOT NULL,                  -- set as the paragraph sets them
  PRIMARY KEY (question_id, n)
);

CREATE TABLE quiz_answer (
  question_id INTEGER NOT NULL REFERENCES quiz_question(id),
  n INTEGER NOT NULL,                        -- from 0, in quiz.tex's order
  text TEXT NOT NULL,
  html TEXT NOT NULL,
  right INTEGER NOT NULL CHECK (right IN (0, 1)),
  PRIMARY KEY (question_id, n)
);

-- The papers that have questions the site asks, and how many.
CREATE TABLE quiz_paper (
  paper_n INTEGER PRIMARY KEY,
  n INTEGER NOT NULL
);
