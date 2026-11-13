// The chart of the personalities (templates/cosmology.html; build/cosmo.py,
// queries.cosmo): Alexander Alyuev's chart, which the server draws whole, the
// lines with it.  Nothing is laid out or routed here.  This chooses and shows:
//
//   a card or a unit's title chosen (its address, #michael, so that Back
//   undoes it and a link can name it) marks what the lines join it to, lets
//   the rest stand back, and shows its entry over the chart's corner; the
//   same card again, the entry's ×, Escape or a click on the empty chart
//   lets go.  A mouse over a card marks as much while it is there.
//
//   a chip of the legend, or of an entry, marks every card of that class,
//   group or function, and the lines among them.
//
//   the search box finds a unit or a personality by any of its names in
//   either language, and a chip by its own.
//
//   the chart is scaled by --cz, which the page's head set before first
//   paint: the slider, the two buttons, Ctrl + wheel or a trackpad's pinch
//   under the pointer, two fingers about the point between them, and Whole
//   chart.  It is moved by the window's own scrolling, a finger's or a
//   wheel's, and by a mouse's drag.
//
// Everything it needs is in the page: a card's data-id, data-u and data-k, a
// line's data-a and data-b, an entry's data-s.  Run once for a <main>, and
// again by ub.js for one that listen.js brings in while it plays.
(function () {
  'use strict';
  var root = document.documentElement, S = null, ZMAX = 2, FAR = 0.33;

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function norm(s) { return String(s).toLowerCase().replace(/ё/g, 'е').replace(/’/g, "'").trim(); }
  function all(el, sel) { return Array.prototype.slice.call(el.querySelectorAll(sel)); }

  function init() {
    var main = document.querySelector('main.cosmo');
    if (!main || main.dataset.on) return;
    main.dataset.on = '1';
    var T = window.ubT;
    var view = main.querySelector('.cview'), size = main.querySelector('.csize'),
        world = main.querySelector('.cworld'), tools = main.querySelector('.ctools'),
        W = parseFloat(size.style.getPropertyValue('--w')), H = parseFloat(size.style.getPropertyValue('--h'));
    var cards = {}, byPerson = {}, titles = {}, boxes = {}, up = {}, entries = {}, edges = [];
    all(world, '.cp').forEach(function (a) {
      cards[(a.classList.contains('ghost') ? '~' : '') + a.dataset.id] = a;
      (byPerson[a.dataset.id] = byPerson[a.dataset.id] || []).push(a);
      a.draggable = false;
    });
    all(world, '.cut').forEach(function (a) {
      titles[a.dataset.id] = a;
      up[a.dataset.id] = a.dataset.up || null;
      a.draggable = false;
    });
    all(world, '.cu').forEach(function (r) { boxes[r.dataset.u] = r; });
    all(world, '.ce').forEach(function (g) { edges.push({ el: g, a: g.dataset.a, b: g.dataset.b }); });
    // No card, title or entry keeps its id (cosmology.html, its scripts
    // block): data-id says what each is.  Again here, for a <main> that
    // listen.js brought in.
    all(main, '.ci, .cp, .cut').forEach(function (e) { e.dataset.id = e.dataset.id || e.id; e.removeAttribute('id'); });
    all(main, '.ci').forEach(function (e) { entries[e.dataset.id] = e; });
    var st = S = { main: main, sel: null, key: null, hover: null };

    // ---- marking ---------------------------------------------------------------
    function inUnit(card, unit) {
      for (var u = card.dataset.u; u; u = up[u]) if (u === unit) return true;
      return false;
    }
    function clearMarks() {
      // Not the lit arrowhead's own definition, which is named "on" too.
      all(world, '.on:not(marker), .rel').forEach(function (e) { e.classList.remove('on', 'rel'); });
      world.classList.remove('focus');
    }
    // What a line's end is drawn as: a card, or a unit's title and box.
    function endMark(end, cls) {
      if (cards[end]) cards[end].classList.add(cls);
      else if (titles[end]) { titles[end].classList.add(cls); if (boxes[end]) boxes[end].classList.add('on'); }
    }
    function mark(id) {
      clearMarks();
      if (!id) return;
      world.classList.add('focus');
      if (titles[id]) {
        // A unit: itself, all that stands in it, the lines that end at it and
        // those among its own.
        titles[id].classList.add('on');
        if (boxes[id]) boxes[id].classList.add('on');
        var mine = {};
        Object.keys(cards).forEach(function (k) {
          if (inUnit(cards[k], id)) { mine[k] = true; cards[k].classList.add('rel'); }
        });
        edges.forEach(function (e) {
          if (e.a === id || e.b === id) { e.el.classList.add('on'); endMark(e.a === id ? e.b : e.a, 'rel'); }
          else if (mine[e.a] && mine[e.b]) e.el.classList.add('on');
        });
        return;
      }
      var me = {};
      me[id] = me['~' + id] = true;
      (byPerson[id] || []).forEach(function (a) { a.classList.add('on'); });
      edges.forEach(function (e) {
        if (!me[e.a] && !me[e.b]) return;
        e.el.classList.add('on');
        endMark(me[e.a] ? e.b : e.a, 'rel');
      });
    }
    function markKey(k) {
      clearMarks();
      world.classList.add('focus');
      var mine = {};
      Object.keys(cards).forEach(function (id) {
        if ((' ' + cards[id].dataset.k + ' ').indexOf(' ' + k + ' ') >= 0) { mine[id] = true; cards[id].classList.add('rel'); }
      });
      edges.forEach(function (e) { if (mine[e.a] && mine[e.b]) e.el.classList.add('on'); });
      return Object.keys(mine).map(function (id) { return cards[id]; });
    }
    function remark() {
      if (st.hover) mark(st.hover);
      else if (st.sel) mark(st.sel);
      else if (st.key) markKey(st.key);
      else clearMarks();
    }

    // ---- the window -------------------------------------------------------------
    // The scale is the window's own, --cz on it: the page's head set the first
    // on the root, for the first paint, and a change there would have every
    // element of the page look at its styles again.
    function zoom() { return parseFloat(view.style.getPropertyValue('--cz') || root.style.getPropertyValue('--cz')) || 1; }
    function zmin() { return Math.min(1, view.clientWidth / W); }
    // As the page opens: the chart's whole width, where that leaves a name
    // legible, a window some 1,180 px wide or more; in a narrower one, a
    // phone's, three quarters of its size, and the window on a part of it.
    function zfirst() { var f = view.clientWidth / W; return f >= 0.62 ? Math.min(1, f) : 0.75; }
    var slider = main.querySelector('.zr');
    function setZoom(nz, fx, fy) {
      var z = zoom(), ox = size.offsetLeft - view.offsetLeft, oy = size.offsetTop - view.offsetTop, wx, wy;
      nz = clamp(nz, zmin(), ZMAX);
      if (fx == null) { fx = view.clientWidth / 2; fy = view.clientHeight / 2; }
      wx = (view.scrollLeft + fx - ox) / z;
      wy = (view.scrollTop + fy - oy) / z;
      view.style.setProperty('--cz', nz);
      view.classList.toggle('far', nz < FAR);
      ox = size.offsetLeft - view.offsetLeft;
      oy = size.offsetTop - view.offsetTop;
      view.scrollLeft = wx * nz + ox - fx;
      view.scrollTop = wy * nz + oy - fy;
      if (slider) slider.value = String(Math.round(100 * Math.log(nz / zmin()) / Math.log(ZMAX / zmin())) || 0);
    }
    // As tall as the screen leaves it, under the bar.
    function fitHeight() {
      var top = view.getBoundingClientRect().top + window.scrollY;
      view.style.height = Math.max(240, window.innerHeight - top - 8) + 'px';
    }
    // Into view, in the middle, unless it is in view already.
    function reveal(el, always) {
      var v = view.getBoundingClientRect(), r = el.getBoundingClientRect(), pad = 12,
          on = entries[st.sel] && entries[st.sel].classList.contains('on') ? entries[st.sel].getBoundingClientRect() : null,
          // What the entry covers is not in view: its side of the window, or its foot.
          right = on && on.left > v.left + 40 ? on.left : v.right, bottom = on && on.left <= v.left + 40 ? on.top : v.bottom;
      if (!always && r.left >= v.left + pad && r.right <= right - pad && r.top >= v.top + pad && r.bottom <= bottom - pad) return;
      view.scrollTo({ left: view.scrollLeft + r.left + r.width / 2 - (v.left + right) / 2,
                      top: view.scrollTop + r.top + r.height / 2 - (v.top + bottom) / 2, behavior: 'smooth' });
    }

    // ---- choosing ---------------------------------------------------------------
    function show(id) {
      all(main, '.ci.on').forEach(function (e) { e.classList.remove('on'); });
      var e = id && entries[id], x;
      if (!e) return;
      if (!e.querySelector('.x')) {
        x = document.createElement('button');
        x.type = 'button';
        x.className = 'x';
        x.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></svg>';
        T.attr(x, 'aria-label', 'Close');
        T.attr(x, 'title', 'Close');
        e.insertBefore(x, e.firstChild);
      }
      e.classList.add('on');
      e.scrollTop = 0;
    }
    function select(id, fly) {
      st.sel = id && entries[id] ? id : null;
      st.key = null;
      st.hover = null;
      chips();
      show(st.sel);
      remark();
      if (st.sel && fly) reveal(titles[st.sel] || cards[st.sel] || cards['~' + st.sel]);
    }
    // The address names what is chosen: #michael, or a card's own, #c-michael,
    // which a page elsewhere links to.
    function named() {
      var h = '';
      try { h = decodeURIComponent(location.hash.slice(1)); } catch (e) {}
      if (!entries[h] && /^[cgu]-/.test(h)) h = h.slice(2);
      return entries[h] ? h : null;
    }
    function letGo() {
      if (location.hash) history.pushState(history.state, '', location.pathname + location.search);
      select(null);
    }
    function chips() {
      all(main, '.cchip').forEach(function (c) { c.classList.toggle('on', c.dataset.k === st.key); });
    }
    function filter(k) {
      if (location.hash) history.pushState(history.state, '', location.pathname + location.search);
      st.sel = st.hover = null;
      st.key = st.key === k ? null : k;
      show(null);
      chips();
      var found = st.key ? markKey(st.key) : (clearMarks(), []);
      var v = view.getBoundingClientRect();
      if (found.length && !found.some(function (a) {
        var r = a.getBoundingClientRect();
        return r.right > v.left && r.left < v.right && r.bottom > v.top && r.top < v.bottom;
      })) reveal(found[0], true);
    }
    st.fromHash = function () { select(named(), true); };
    st.letGo = letGo;

    main.addEventListener('click', function (ev) {
      var t = ev.target, a, c;
      if (st.dragged) { st.dragged = false; ev.preventDefault(); return; }
      if (t.closest('.ci .x')) return letGo();
      if ((c = t.closest('.cchip'))) { ev.preventDefault(); return filter(c.dataset.k); }
      if ((a = t.closest('.cp, .cut'))) {
        // The one chosen, again: let go.  Any other goes to its address, and
        // the address chooses it.
        if (a.dataset.id === st.sel) { ev.preventDefault(); letGo(); }
        return;
      }
      if (t.closest('.cview') && !t.closest('a, button, input') && (st.sel || st.key)) {
        if (st.key) filter(st.key); else letGo();
      }
    });
    // A mouse over a card or a title marks what it is joined to, for as long.
    world.addEventListener('pointerover', function (ev) {
      var a = ev.pointerType === 'mouse' && !st.pan && ev.target.closest('.cp, .cut');
      if (a && a.dataset.id !== st.hover) { st.hover = a.dataset.id; remark(); }
    });
    world.addEventListener('pointerout', function (ev) {
      var a = ev.pointerType === 'mouse' && ev.target.closest('.cp, .cut');
      if (a && st.hover && !(ev.relatedTarget && a.contains(ev.relatedTarget))) { st.hover = null; remark(); }
    });

    // ---- moving and scaling -------------------------------------------------------
    // A mouse's drag moves the chart; a finger's is the window's own scrolling.
    view.addEventListener('pointerdown', function (ev) {
      if (ev.pointerType !== 'mouse' || ev.button || ev.target.closest('.ci, input, button')) return;
      st.pan = { x: ev.clientX, y: ev.clientY, l: view.scrollLeft, t: view.scrollTop, id: ev.pointerId, moved: false };
    });
    view.addEventListener('pointermove', function (ev) {
      var p = st.pan;
      if (!p || ev.pointerId !== p.id) return;
      if (!p.moved && Math.abs(ev.clientX - p.x) + Math.abs(ev.clientY - p.y) < 5) return;
      if (!p.moved) {
        p.moved = true;
        view.classList.add('drag');
        try { view.setPointerCapture(p.id); } catch (e) {}
        if (st.hover) { st.hover = null; remark(); }
      }
      view.scrollLeft = p.l - (ev.clientX - p.x);
      view.scrollTop = p.t - (ev.clientY - p.y);
    });
    function endPan(ev) {
      var p = st.pan;
      if (!p || ev.pointerId !== p.id) return;
      st.pan = null;
      view.classList.remove('drag');
      // The click that ends a drag chooses nothing.
      if (p.moved) { st.dragged = true; setTimeout(function () { st.dragged = false; }, 0); }
    }
    view.addEventListener('pointerup', endPan);
    view.addEventListener('pointercancel', endPan);
    world.addEventListener('dragstart', function (ev) { ev.preventDefault(); });
    view.addEventListener('wheel', function (ev) {
      if (!ev.ctrlKey && !ev.metaKey) return;
      var r = view.getBoundingClientRect();
      ev.preventDefault();
      setZoom(zoom() * Math.exp(-ev.deltaY * (ev.deltaMode ? 0.05 : 0.0025)), ev.clientX - r.left, ev.clientY - r.top);
    }, { passive: false });
    // Two fingers scale the chart about the point between them, while the
    // window's own scrolling goes on moving it.  The browser's pinch, which
    // scales the whole page, header and all, is not asked for on the chart
    // (ub.css .cview, touch-action).
    var pinch = null;
    function spread(t) { return Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY); }
    view.addEventListener('touchstart', function (ev) {
      pinch = ev.touches.length === 2 ? { d: spread(ev.touches) || 1, z: zoom() } : null;
    }, { passive: true });
    view.addEventListener('touchmove', function (ev) {
      var t = ev.touches, r;
      if (!pinch || t.length !== 2) return;
      r = view.getBoundingClientRect();
      setZoom(pinch.z * spread(t) / pinch.d, (t[0].clientX + t[1].clientX) / 2 - r.left,
              (t[0].clientY + t[1].clientY) / 2 - r.top);
    }, { passive: true });
    view.addEventListener('touchend', function (ev) { if (ev.touches.length < 2) pinch = null; }, { passive: true });
    view.addEventListener('touchcancel', function () { pinch = null; }, { passive: true });
    if (slider) slider.addEventListener('input', function () {
      setZoom(zmin() * Math.pow(ZMAX / zmin(), slider.value / 100));
    });
    main.querySelector('.zin').addEventListener('click', function () { setZoom(zoom() * 1.25); });
    main.querySelector('.zout').addEventListener('click', function () { setZoom(zoom() / 1.25); });
    main.querySelector('.zfit').addEventListener('click', function () {
      setZoom(zmin());
      view.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
    });
    var far = main.querySelector('.cfar input');
    far.addEventListener('change', function () { world.classList.toggle('showfar', far.checked); });
    far.closest('.cfar').hidden = false;

    // ---- the search box -----------------------------------------------------------
    var box = main.querySelector('.cq'), list = main.querySelector('.cres'), items = [], cur = 0;
    var KINDS = { group: T.k('category|chart'), func: T.k('function|chart'), 'class': T.k('class of origin|chart') };
    function candidates() {
      var out = [];
      all(main, '.clegend .cchip').forEach(function (c) {
        var name = c.cloneNode(true);
        all(name, 'i, small').forEach(function (n) { n.remove(); });
        out.push({ key: c.dataset.k, s: norm(name.textContent), name: name.innerHTML, color: c.style.getPropertyValue('--k'),
                   hint: T(KINDS[c.dataset.k.split(':')[0]]) });
      });
      all(main, '.ci').forEach(function (e) {
        var where = e.querySelector('.cwhere a:last-child');
        out.push({ id: e.dataset.id, s: norm(e.dataset.s), name: e.querySelector('h2').innerHTML,
                   color: e.style.getPropertyValue('--c'), hint: where ? where.innerHTML : '' });
      });
      return out;
    }
    var pool = null;
    function draw() {
      var q = norm(box.value);
      pool = pool || candidates();
      items = q ? pool.filter(function (i) { return i.s.indexOf(q) >= 0; }) : [];
      cur = 0;
      list.innerHTML = items.map(function (i, n) {
        return '<li role="option" data-n="' + n + '"' + (n ? '' : ' class="on"') + '><i' + (i.key ? ' class="key"' : '') +
               ' style="--k:' + T.esc(i.color) + '"></i><span>' + i.name + '</span><small>' + i.hint + '</small></li>';
      }).join('') || (q ? '<li class="none">' + T('Nothing found') + '</li>' : '');
      list.hidden = !q;
    }
    function pick(i) {
      if (!i) return;
      list.hidden = true;
      box.blur();
      if (i.key) { st.key = null; filter(i.key); }
      else if (i.id === st.sel) reveal(titles[i.id] || cards[i.id], true);
      else location.hash = '#' + i.id;
    }
    box.addEventListener('input', draw);
    box.addEventListener('focus', function () { if (box.value) draw(); });
    box.addEventListener('blur', function () { setTimeout(function () { list.hidden = true; }, 150); });
    box.addEventListener('keydown', function (ev) {
      var rows = all(list, 'li[data-n]');
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        if (!rows.length) return;
        ev.preventDefault();
        cur = (cur + (ev.key === 'ArrowDown' ? 1 : -1) + rows.length) % rows.length;
        rows.forEach(function (r, n) { r.classList.toggle('on', n === cur); });
        rows[cur].scrollIntoView({ block: 'nearest' });
      } else if (ev.key === 'Enter') { ev.preventDefault(); pick(items[cur]); }
      else if (ev.key === 'Escape') { ev.stopPropagation(); box.value = ''; list.hidden = true; box.blur(); }
    });
    // mousedown, before the box's blur hides the list.
    list.addEventListener('mousedown', function (ev) {
      var li = ev.target.closest('li[data-n]');
      ev.preventDefault();
      if (li) pick(items[+li.dataset.n]);
    });

    // ---- as the page opens --------------------------------------------------------
    tools.hidden = false;
    fitHeight();
    setZoom(zfirst(), 0, 0);
    st.layout = function () { fitHeight(); setZoom(zoom()); };
    var first = named(), start = world.querySelector('.cp'), ubox = start && boxes[start.dataset.u];
    if (first) select(first, true);
    else if (ubox && size.offsetWidth > view.clientWidth)
      // A window narrower than the chart opens on its first unit, the Trinity's.
      view.scrollLeft = Math.max(0, parseFloat(ubox.getAttribute('x')) * zoom() - 10);
  }

  window.addEventListener('hashchange', function () { if (S && S.main.isConnected) S.fromHash(); });
  window.addEventListener('resize', function () { if (S && S.main.isConnected) S.layout(); });
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape' || !S || !S.main.isConnected || (!S.sel && !S.key)) return;
    if (document.querySelector('dialog[open]')) return;
    S.letGo();
  });
  window.ubCosmo = init;
  init();
})();
