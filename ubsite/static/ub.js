// 15 KB budget, no dependencies. Everything here is an enhancement: the site is
// complete and correct with JavaScript off.
(function () {
  var b = document.querySelector('.theme');
  if (b) b.addEventListener('click', function () {
    var r = document.documentElement;
    var dark = matchMedia('(prefers-color-scheme: dark)').matches;
    var cur = r.dataset.theme || (dark ? 'dark' : 'light');
    var next = cur === 'dark' ? 'light' : 'dark';
    r.dataset.theme = next;
    try { localStorage.setItem('ub_theme', next); } catch (e) {}
  });

  // Bring the page's focus into view.  /61:7.18 renders the whole of 61:7 with
  // paragraph 18 marked .hit, and nothing in the address says where to scroll
  // -- a #fragment would, but then the permalink would stop being the
  // citation.  A margin chip opens /i/god#e…, which the browser scrolls to
  // itself.  Either way, scroll once more when the fonts are in: UB Goudy
  // loads with font-display: swap, the text reflows, and the first scroll
  // drifts.  Not if the reader has scrolled meanwhile.
  var focus = null;
  try {
    focus = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1)))
                          : document.querySelector('.hit');
  } catch (e) {}
  if (focus) {
    focus.scrollIntoView({ block: 'start' });
    var y = window.scrollY;
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () {
      if (window.scrollY === y) focus.scrollIntoView({ block: 'start' });
    });
  }
})();
