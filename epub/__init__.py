"""The book as an EPUB 3: the whole site, offline, except listening.

A third view over `var/ub.db`, beside the site (`ubsite/`) and the database
itself.  It reads the same rows the site reads -- through `ubsite/queries.py`,
so the margin's rules exist once -- and draws them for an e-reader:

* the text, one file per paper, every paragraph with its reference as literal
  text, so that a reader's own search for `101:4.2` finds it;
* beneath each paragraph, the index entries that cite it (the site's margin);
* the 1955 readings as pop-up notes;
* the Index A-Z, each headword its whole concept page, every citation a link
  into the text; Appendices A-F; the four part dividers; an outline
  (the reader's own) down to every section, and no contents page.

    python -m epub build      -> var/epub/the-urantia-book.epub
    python -m epub check      every gate, epubcheck last

The same database gives a byte-identical file.  No red letter: e-ink draws it
as a muddy grey (Tigran, 2026-10-10); the spans stay in the markup, uncoloured.
"""
