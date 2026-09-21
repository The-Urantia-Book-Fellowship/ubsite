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
})();
