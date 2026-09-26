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

  // /61:7.18 renders the whole of 61:7 with paragraph 18 marked .hit.  Nothing
  // in the address says where to scroll -- a #fragment would, but it would
  // also make the permalink something other than the citation -- so the page
  // brings its own focus into view.  Again once the fonts are in: UB Goudy
  // loads with font-display: swap, the text reflows, and the first scroll
  // drifts.  Not if the reader has scrolled meanwhile, and never over an
  // explicit #fragment, which the browser has already honoured.
  var hit = document.querySelector('.hit');
  if (hit && !location.hash) {
    hit.scrollIntoView({ block: 'start' });
    var y = window.scrollY;
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () {
      if (window.scrollY === y) hit.scrollIntoView({ block: 'start' });
    });
  }
})();
