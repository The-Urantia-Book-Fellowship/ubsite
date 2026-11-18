# The home page's part pictures

The four pictures of the home page's part cards (`ubsite/templates/home.html`, `ol.front-toc`), one to a part of the book, as Tigran made them on 2026-11-17 and put them here on 2026-11-18: `partI.jpeg`, `partII.jpeg`, `partIII.jpeg` and `partIV.jpeg`, each 2752 × 1536 and about 3 MB. They are kept unchanged and under the names they came with.

**The masters are not committed.** No reader is sent them, and at 12.8 MB they would be a fifth of the repository again; `.gitignore` leaves `*.jpeg` out, as it leaves out the Foundation's zips, and `MANIFEST.tsv` names each by its SHA-256, size and dimensions. A clone has the served files and can do everything but make them again.

**What the site serves** is made from them by `tools/make_art.py`, run by hand, and committed: `ubsite/static/art/part<N>-640.webp` and `part<N>-1280.webp`, about half a megabyte for all eight. Two widths, since what a screen needs follows its pixels and not its kind: an ordinary desk monitor takes the 640, a phone or a dense laptop the 1280, and the browser chooses (`srcset`). `MANIFEST.tsv` names each served file too, with the settings it was made by, and `tests/test_art.py` holds the files to it.

**A new or changed picture** is: the master here under its part's name, `.venv/bin/python tools/make_art.py`, a look at the home page at a desk's width and a phone's (`tools/art_e2e.py` measures the words against the picture under them), and a commit of the served files and the manifest. A card's dark ground under its picture, shown until the picture arrives, is the mean colour of the picture's lower third, written by hand in `ub.css` (`.fp1` to `.fp4`).

**The words are the page's, never the picture's.** A card's name, its part's number and its papers are set over the picture by the page, in English and in Russian, so a picture carries no letter.
