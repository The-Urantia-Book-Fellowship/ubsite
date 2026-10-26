"""Work offline: the site, kept in a reader's browser.

A reader who turns on "Work offline" in Settings registers a service worker
(ubsite/static/sw.js) that downloads what this package builds, and answers the
site's addresses from it when the network does not.  It holds the book with
its margin index and 1955 readings, the index's concept pages, every
headword's reading path, the appendices and the lists, and a database to
search them by; not the recordings.

**The copy is the site's own pages.**  `python -m offline build` asks the app
for every page it will hold (offline/site.py), as a browser would, and cuts
each at fixed places in base.html into the build's shell, which every page
shares, and what is the page's own: its title, its head and scripts blocks and
its body.  A section page's left rail is lifted out of its body and kept once
for its paper.  The worker only joins strings (static/offline-core.js), and
`python -m offline check` has that same code join every page again, in Node,
and holds each to the page the server sends, byte for byte.  So there is no
second renderer: a page read offline is the page the site served for that
build.

**Search runs on SQLite**, in the browser, through SQLite's own WebAssembly
build (vendor/sqlite-wasm/): the queries of app.py's search(), on the same
FTS5 tables with the same tokenizer, in two small databases cut from ub.db
(offline/searchdb.py): the text's, which changes when the text does, and the
index's, which changes as the index is edited.  The results page is the one
thing drawn in JavaScript, and the check holds it to app.search() for every
query in its list, byte for byte.

**The translations beside the text** are each a download of their own,
which a reader chooses in Settings' Offline tab: a section's fragment, /tr/,
holds every translation it has, so each translation's share of it is kept
apart (pages.py), and listed apart in the manifest, and the worker joins the
shares of those kept.

**What is built** goes into var/offline/: manifest.json, which lists every
chunk by the hash of its bytes, and c/<hash>.gz, each chunk gzipped.  A copy
knows which build it is, so a worker learns that its copy is stale by asking
for the manifest, and fetches only the chunks that changed.  The browser keeps
each chunk gzipped, as it came, so the copy takes the room it took to
download.

pack.py is the only module here that writes, and only under var/offline/.
"""
