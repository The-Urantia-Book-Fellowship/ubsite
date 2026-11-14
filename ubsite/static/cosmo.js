// The chart of the personalities (templates/cosmology.html; build/cosmo.py,
// queries.cosmo), drawn from Alexander Alyuev's data, which the server draws
// whole, the lines with it.  Nothing is laid out or routed here.  This
// chooses, shows and moves:
//
//   a card or a unit's title chosen (its address, #michael, so that Back
//   undoes it and a link can name it) marks what the lines join it to, lets
//   the rest stand back, and shows its entry under the line's end, or on a
//   phone as a strip along the foot, which a tap opens whole; the same card
//   again, the entry's ×, Escape or a click on the empty chart lets go.  A
//   mouse over a card marks as much while it is there, and while nothing is
//   chosen (Tigran, 2026-11-14: what was chosen went dark under the pointer).
//
//   a chip of the legend, or of an entry, marks every card of that class,
//   group or function, and the lines among them.
//
//   the search box finds a unit or a personality by any of its names in
//   either language, and a chip by its own.
//
//   the page itself scrolls, both ways, as a page of the text does (Tigran,
//   2026-11-14; ub.css :root.cchart): the wheel, the keys, a finger, the
//   browser's own bars, with nothing here for any of them.  Here: a mouse's
//   drag; the line's four arrows, a third of the screen a press and on while
//   held; and the small map at the corner of a wide screen.
//
//   the chart is scaled by --cz, which the page's head set before first
//   paint: the line's two buttons, + and - on the keys, Ctrl + wheel or a
//   trackpad's pinch under the pointer, anywhere on the page's <main>, two
//   fingers about the point between them, and Whole chart, its whole width.
//
//   the scale and the place are kept in this entry of the history, so that
//   Back from a place in the text returns to the chart as it was left.
//
// Everything it needs is in the page: a card's data-id, data-u and data-k, a
// line's data-a and data-b, an entry's data-s.  Run once for a <main>, and
// again by ub.js for one that listen.js brings in while it plays.
(function () {
  'use strict';
  var root = document.documentElement, S = null, ZMAX = 2, FAR = 0.33;

  // The page as the chart's, which the page's own head script does before
  // first paint, here for a chart brought in while listening: the least scale
  // in the viewport, the class, the window's width; and undone on leaving.
  function chartMode(on) {
    var m = document.querySelector('meta[name="viewport"]');
    if (on) {
      if (m && m.content.indexOf('minimum-scale') < 0) m.content += ', minimum-scale=1';
      root.classList.add('cchart');
      root.style.setProperty('--cvw', root.clientWidth + 'px');
    } else {
      if (m) m.content = m.content.replace(/,\s*minimum-scale=1/, '');
      root.classList.remove('cchart');
      root.style.removeProperty('--cvw');
      root.style.removeProperty('--cz');
    }
  }
  function phone() { return window.matchMedia('(max-width: 44rem)').matches; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function norm(s) { return String(s).toLowerCase().replace(/ё/g, 'е').replace(/’/g, "'").trim(); }
  function all(el, sel) { return Array.prototype.slice.call(el.querySelectorAll(sel)); }

  function init() {
    var main = document.querySelector('main.cosmo');
    if (!main || main.dataset.on) return;
    main.dataset.on = '1';
    chartMode(true);
    var T = window.ubT;
    var view = main.querySelector('.cview'), size = main.querySelector('.csize'),
        world = main.querySelector('.cworld'), tools = main.querySelector('.ctools'),
        bar = main.querySelector('.cbar'), legend = main.querySelector('.clegend'),
        W = parseFloat(size.style.getPropertyValue('--w')), H = parseFloat(size.style.getPropertyValue('--h'));
    // The page scrolls, so the chart is nothing to focus for the keys; and the
    // entries hang from the line, to follow it (ub.css .cbar > .cinfos).
    view.removeAttribute('tabindex');
    bar.appendChild(main.querySelector('.cinfos'));
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
    var st = S = { main: main, sel: null, key: null, hover: null, tall: false, legend: legend };

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

    // ---- the page and the scale -------------------------------------------------
    // The scale is the chart's own, --cz on it: the page's head set the first
    // on the root, for the first paint, and a change there would have every
    // element of the page look at its styles again.
    function zoom() { return parseFloat(view.style.getPropertyValue('--cz') || root.style.getPropertyValue('--cz')) || 1; }
    function width() { return root.clientWidth; }
    function zmin() { return Math.min(1, width() / W); }
    // As the page opens: the chart's whole width, where that leaves a name
    // legible, a window some 1,180 px wide or more; in a narrower one, a
    // phone's, three quarters of its size, and the window on a part of it.
    function zfirst() { var f = width() / W; return f >= 0.62 ? Math.min(1, f) : 0.75; }
    // The line's foot on the screen: under it the window is the chart's.
    function lineFoot() { return Math.max(0, bar.getBoundingClientRect().bottom); }
    function scale(nz) {
      view.style.setProperty('--cz', nz);
      view.classList.toggle('far', nz < FAR);
    }
    // To a scale, about a point of the screen: the pointer, the place between
    // two fingers, or the middle of what the window shows of the chart.
    function setZoom(nz, fx, fy) {
      var z = zoom(), r = size.getBoundingClientRect(), wx, wy;
      nz = clamp(nz, zmin(), ZMAX);
      if (fx == null) { fx = width() / 2; fy = (lineFoot() + window.innerHeight) / 2; }
      wx = (fx - r.left) / z;
      wy = (fy - r.top) / z;
      scale(nz);
      r = size.getBoundingClientRect();
      window.scrollBy({ left: r.left + wx * nz - fx, top: r.top + wy * nz - fy, behavior: 'instant' });
      moved();
    }
    // Into view, in the middle of what the entry leaves of the window, unless
    // it is in view already.
    function reveal(el, always) {
      var r = el.getBoundingClientRect(), pad = 12, top = lineFoot(), right = width(), bottom = window.innerHeight,
          on = main.querySelector('.ci.on'), o = on && on.getBoundingClientRect();
      // What the entry covers is not in view: its side of the window, or on a
      // phone its foot.
      if (o && o.width > right * 0.7) bottom = o.top; else if (o) right = o.left;
      if (!always && r.left >= pad && r.right <= right - pad && r.top >= top + pad && r.bottom <= bottom - pad) return;
      window.scrollBy({ left: r.left + r.width / 2 - right / 2, top: r.top + r.height / 2 - (top + bottom) / 2,
                        behavior: 'smooth' });
    }
    // After the page has moved or the chart been scaled: the room under the
    // line, which an entry and the legend may be as tall as; the map; and,
    // once it rests, this entry of the history, for Back.
    var ticking = 0, keeping = 0, room = -1;
    function tick() {
      ticking = 0;
      if (!main.isConnected) return;
      var r = Math.round(window.innerHeight - lineFoot());
      if (r !== room) { room = r; main.style.setProperty('--croom', r + 'px'); }
      drawMap();
    }
    function keep() {
      if (!main.isConnected) return;
      try {
        history.replaceState(Object.assign({}, history.state, {
          cosmo: { z: zoom(), x: Math.round(window.scrollX), y: Math.round(window.scrollY) } }), '');
      } catch (e) {}
    }
    function moved() {
      if (!ticking) ticking = requestAnimationFrame(tick);
      clearTimeout(keeping);
      keeping = setTimeout(keep, 250);
    }
    st.moved = moved;
    st.keep = keep;

    // ---- the map ----------------------------------------------------------------
    // The units' boxes again, small, at the window's corner on a wide screen
    // (ub.css .cmap): where the window stands on the chart, what is chosen,
    // and a click or a drag in it to go there.
    var NS = 'http://www.w3.org/2000/svg', map = document.createElementNS(NS, 'svg'), mapUnits = {}, mapWin, mapAt,
        wide = window.matchMedia('(min-width: 62rem)');
    function shape(name, cls) {
      var e = document.createElementNS(NS, name);
      e.setAttribute('class', cls);
      return map.appendChild(e);
    }
    map.setAttribute('class', 'cmap');
    map.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    map.setAttribute('aria-hidden', 'true');
    map.setAttribute('focusable', 'false');
    all(world, '.cu').forEach(function (r) {
      var u = shape('rect', 'cmu');
      ['x', 'y', 'width', 'height'].forEach(function (a) { u.setAttribute(a, r.getAttribute(a)); });
      u.setAttribute('rx', 30);
      u.style.setProperty('--c', r.style.getPropertyValue('--c'));
      mapUnits[r.dataset.u] = u;
    });
    mapWin = shape('rect', 'cmw');
    mapAt = shape('circle', 'cma');
    mapAt.setAttribute('r', 75);
    main.appendChild(map);
    function drawMap() {
      if (!wide.matches) return;
      var z = zoom(), r = size.getBoundingClientRect(),
          x = clamp(-r.left / z, 0, W), y = clamp((lineFoot() - r.top) / z, 0, H),
          x2 = clamp((width() - r.left) / z, 0, W), y2 = clamp((window.innerHeight - r.top) / z, 0, H),
          card = st.sel && !titles[st.sel] && (cards[st.sel] || cards['~' + st.sel]), b;
      mapWin.setAttribute('x', x);
      mapWin.setAttribute('y', y);
      mapWin.setAttribute('width', Math.max(0, x2 - x));
      mapWin.setAttribute('height', Math.max(0, y2 - y));
      Object.keys(mapUnits).forEach(function (id) { mapUnits[id].classList.toggle('on', id === st.sel); });
      mapAt.style.display = card ? '' : 'none';
      if (card) {
        b = card.getBoundingClientRect();
        mapAt.setAttribute('cx', (b.left + b.width / 2 - r.left) / z);
        mapAt.setAttribute('cy', (b.top + b.height / 2 - r.top) / z);
      }
    }
    function mapGo(ev) {
      var b = map.getBoundingClientRect(), z = zoom(), r = size.getBoundingClientRect(),
          px = (ev.clientX - b.left) / b.width * W, py = (ev.clientY - b.top) / b.height * H;
      window.scrollBy({ left: r.left + px * z - width() / 2,
                        top: r.top + py * z - (lineFoot() + window.innerHeight) / 2, behavior: 'instant' });
    }
    map.addEventListener('pointerdown', function (ev) {
      if (ev.button) return;
      ev.preventDefault();
      try { map.setPointerCapture(ev.pointerId); } catch (e) {}
      st.mapping = true;
      mapGo(ev);
    });
    map.addEventListener('pointermove', function (ev) {
      if (st.mapping && (ev.buttons & 1)) mapGo(ev); else st.mapping = false;
    });
    map.addEventListener('pointerup', function () { st.mapping = false; });
    map.addEventListener('pointercancel', function () { st.mapping = false; });

    // ---- choosing ---------------------------------------------------------------
    function button(cls, d) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = cls;
      b.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="' + d + '"/></svg>';
      return b;
    }
    // A phone's entry is a strip along the foot until it is opened whole, and
    // stays as the reader left the last one (ub.css .ci.on.tall).
    function tall(e) {
      var m = e.querySelector('.cmore');
      e.classList.toggle('tall', st.tall);
      if (st.tall) { T.attr(m, 'aria-label', 'Fold the entry'); T.attr(m, 'title', 'Fold the entry'); }
      else { T.attr(m, 'aria-label', 'Open the entry'); T.attr(m, 'title', 'Open the entry'); }
      m.setAttribute('aria-expanded', st.tall ? 'true' : 'false');
      e.scrollTop = 0;
    }
    function show(id) {
      all(main, '.ci.on').forEach(function (e) { e.classList.remove('on'); });
      var e = id && entries[id], x;
      if (!e) return;
      if (!e.querySelector('.x')) {
        x = button('x', 'M3.5 3.5l9 9M12.5 3.5l-9 9');
        T.attr(x, 'aria-label', 'Close');
        T.attr(x, 'title', 'Close');
        e.insertBefore(button('cmore', 'M3.5 10L8 5.5l4.5 4.5'), e.firstChild);
        e.insertBefore(x, e.firstChild);
      }
      e.classList.add('on');
      tall(e);
    }
    function select(id, fly) {
      st.sel = id && entries[id] ? id : null;
      st.key = null;
      st.hover = null;
      chips();
      show(st.sel);
      remark();
      var el = st.sel && (titles[st.sel] || cards[st.sel] || cards['~' + st.sel]), r;
      if (el && fly) {
        // From so far that no name can be read, the whole chart on a phone,
        // back to the scale the page opens at, about what was chosen.
        if (zoom() < FAR) {
          r = el.getBoundingClientRect();
          setZoom(Math.max(zfirst(), FAR), r.left + r.width / 2, r.top + r.height / 2);
        }
        reveal(el);
      }
      moved();
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
      var top = lineFoot(), right = width(), bottom = window.innerHeight;
      if (found.length && !found.some(function (a) {
        var r = a.getBoundingClientRect();
        return r.right > 0 && r.left < right && r.bottom > top && r.top < bottom;
      })) reveal(found[0], true);
      moved();
    }
    st.fromHash = function () { select(named(), true); };
    st.letGo = letGo;

    main.addEventListener('click', function (ev) {
      var t = ev.target, a, c;
      if (st.dragged) { st.dragged = false; ev.preventDefault(); return; }
      if (t.closest('.ci .x')) return letGo();
      if ((c = t.closest('.ci .cmore'))) { st.tall = !st.tall; return tall(c.parentNode); }
      if ((c = t.closest('.cchip'))) {
        ev.preventDefault();
        // On a phone the legend lies over the chart it has just marked.
        if (phone() && legend.contains(c)) legend.open = false;
        return filter(c.dataset.k);
      }
      // A phone's strip, tapped anywhere but on a link: opened whole.
      if ((c = t.closest('.ci.on')) && !st.tall && phone() && !t.closest('a, button')) { st.tall = true; return tall(c); }
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
    // A mouse over a card or a title marks what it is joined to, for as long,
    // while nothing is chosen: what is chosen stays lit.
    world.addEventListener('pointerover', function (ev) {
      if (ev.pointerType !== 'mouse' || st.pan || st.sel || st.key) return;
      var a = ev.target.closest('.cp, .cut');
      if (a && a.dataset.id !== st.hover) { st.hover = a.dataset.id; remark(); }
    });
    world.addEventListener('pointerout', function (ev) {
      var a = ev.pointerType === 'mouse' && ev.target.closest('.cp, .cut');
      if (a && st.hover && !(ev.relatedTarget && a.contains(ev.relatedTarget))) { st.hover = null; remark(); }
    });

    // ---- moving and scaling -------------------------------------------------------
    // A mouse's drag moves the page; a finger's is the browser's own scrolling.
    // It ends with the button, whatever became of its pointerup: Chrome sends
    // none after a press on a scrollbar.
    view.addEventListener('pointerdown', function (ev) {
      if (ev.pointerType !== 'mouse' || ev.button) return;
      st.pan = { x: ev.clientX, y: ev.clientY, id: ev.pointerId, moved: false };
    });
    view.addEventListener('pointermove', function (ev) {
      var p = st.pan;
      if (!p || ev.pointerId !== p.id) return;
      if (!(ev.buttons & 1)) return endPan(ev);
      if (!p.moved && Math.abs(ev.clientX - p.x) + Math.abs(ev.clientY - p.y) < 5) return;
      if (!p.moved) {
        p.moved = true;
        view.classList.add('drag');
        try { view.setPointerCapture(p.id); } catch (e) {}
        if (st.hover) { st.hover = null; remark(); }
      }
      window.scrollBy({ left: p.x - ev.clientX, top: p.y - ev.clientY, behavior: 'instant' });
      p.x = ev.clientX;
      p.y = ev.clientY;
    });
    function endPan(ev) {
      var p = st.pan;
      if (!p || ev.pointerId !== p.id) return;
      st.pan = null;
      view.classList.remove('drag');
      // The click that ends a drag chooses nothing.
      if (p.moved && ev.type === 'pointerup') { st.dragged = true; setTimeout(function () { st.dragged = false; }, 0); }
    }
    view.addEventListener('pointerup', endPan);
    view.addEventListener('pointercancel', endPan);
    world.addEventListener('dragstart', function (ev) { ev.preventDefault(); });
    // Ctrl + wheel, or a trackpad's pinch, anywhere on the page's <main>: the
    // chart's scale, about the pointer where it is on the chart, and never the
    // browser's own zoom, over an entry or the line either.
    main.addEventListener('wheel', function (ev) {
      if (!ev.ctrlKey && !ev.metaKey) return;
      var on = ev.target.closest('.cview');
      ev.preventDefault();
      setZoom(zoom() * Math.exp(-ev.deltaY * (ev.deltaMode ? 0.05 : 0.0025)), on ? ev.clientX : null, on ? ev.clientY : null);
    }, { passive: false });
    // Two fingers scale the chart about the point between them, while the
    // browser's own scrolling goes on moving the page.  The browser's pinch,
    // which scales the whole page, header and all, is not asked for on the
    // chart (ub.css .cview, touch-action).
    var pinch = null;
    function spread(t) { return Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY); }
    view.addEventListener('touchstart', function (ev) {
      pinch = ev.touches.length === 2 ? { d: spread(ev.touches) || 1, z: zoom() } : null;
    }, { passive: true });
    view.addEventListener('touchmove', function (ev) {
      var t = ev.touches;
      if (!pinch || t.length !== 2) return;
      setZoom(pinch.z * spread(t) / pinch.d, (t[0].clientX + t[1].clientX) / 2, (t[0].clientY + t[1].clientY) / 2);
    }, { passive: true });
    view.addEventListener('touchend', function (ev) { if (ev.touches.length < 2) pinch = null; }, { passive: true });
    view.addEventListener('touchcancel', function () { pinch = null; }, { passive: true });
    // A button of the line: once to a press, and on, frame by frame, while it
    // is held down.
    function press(btn, once, held) {
      var wait = 0, frame = 0, ran = false, last = 0;
      function stop() { clearTimeout(wait); cancelAnimationFrame(frame); wait = frame = 0; }
      function go(now) {
        if (!main.isConnected) return stop();
        held(Math.min(0.05, (now - last) / 1000));
        last = now;
        frame = requestAnimationFrame(go);
      }
      btn.addEventListener('pointerdown', function (ev) {
        if (ev.button) return;
        stop();
        ran = false;
        wait = setTimeout(function () { ran = true; last = performance.now(); frame = requestAnimationFrame(go); }, 350);
      });
      ['pointerup', 'pointercancel', 'pointerleave', 'blur'].forEach(function (e) { btn.addEventListener(e, stop); });
      btn.addEventListener('contextmenu', function (ev) { if (ran) ev.preventDefault(); });
      btn.addEventListener('click', function () { if (ran) ran = false; else once(); });
    }
    // An arrow: a third of what the window shows, or some 900 px a second.
    all(main, '.cpan .cbtn').forEach(function (b) {
      var x = +b.dataset.x || 0, y = +b.dataset.y || 0;
      press(b, function () {
        window.scrollBy({ left: x * width() / 3, top: y * Math.max(120, (window.innerHeight - lineFoot()) / 3),
                          behavior: 'smooth' });
      }, function (dt) { window.scrollBy({ left: x * 900 * dt, top: y * 900 * dt, behavior: 'instant' }); });
    });
    st.zoomBy = function (f) { setZoom(zoom() * f); };
    // The chart's whole width, about where the window stands.
    st.fit = function () { setZoom(zmin()); };
    press(main.querySelector('.zin'), function () { st.zoomBy(1.25); }, function (dt) { st.zoomBy(Math.exp(1.1 * dt)); });
    press(main.querySelector('.zout'), function () { st.zoomBy(0.8); }, function (dt) { st.zoomBy(Math.exp(-1.1 * dt)); });
    main.querySelector('.zfit').addEventListener('click', st.fit);
    var far = main.querySelector('.cfar input');
    far.addEventListener('change', function () { world.classList.toggle('showfar', far.checked); });
    far.closest('.cfar').hidden = false;

    // ---- the search box -----------------------------------------------------------
    // On a phone the box is a magnifier in the line, which opens it across the
    // line (.open); it shuts on its ×, on a pick, or left empty.
    var find = main.querySelector('.cfind'), box = main.querySelector('.cq'), list = main.querySelector('.cres'),
        items = [], cur = 0;
    function shut() { find.classList.remove('open'); box.value = ''; list.hidden = true; }
    // The box is in the line, which is in view wherever the page stands: the
    // page is not to move for it.
    st.find = function () { if (phone()) find.classList.add('open'); box.focus({ preventScroll: true }); };
    main.querySelector('.cqb').addEventListener('click', st.find);
    main.querySelector('.cqx').addEventListener('click', shut);
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
      if (find.classList.contains('open')) shut(); else list.hidden = true;
      box.blur();
      if (i.key) { st.key = null; filter(i.key); }
      else if (i.id === st.sel) reveal(titles[i.id] || cards[i.id], true);
      else location.hash = '#' + i.id;
    }
    box.addEventListener('input', draw);
    box.addEventListener('focus', function () { if (box.value) draw(); });
    box.addEventListener('blur', function () {
      setTimeout(function () { list.hidden = true; if (!box.value) find.classList.remove('open'); }, 150);
    });
    box.addEventListener('keydown', function (ev) {
      var rows = all(list, 'li[data-n]');
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        if (!rows.length) return;
        ev.preventDefault();
        cur = (cur + (ev.key === 'ArrowDown' ? 1 : -1) + rows.length) % rows.length;
        rows.forEach(function (r, n) { r.classList.toggle('on', n === cur); });
        rows[cur].scrollIntoView({ block: 'nearest' });
      } else if (ev.key === 'Enter') { ev.preventDefault(); pick(items[cur]); }
      else if (ev.key === 'Escape') { ev.stopPropagation(); shut(); box.blur(); }
    });
    // mousedown, before the box's blur hides the list.
    list.addEventListener('mousedown', function (ev) {
      var li = ev.target.closest('li[data-n]');
      ev.preventDefault();
      if (li) pick(items[+li.dataset.n]);
    });

    // ---- as the page opens --------------------------------------------------------
    // At the scale and the place this entry of the history was left at, by
    // Back or a reload, the browser's own putting back being asked not to:
    // it knows the place and not the scale.  Else at the opening scale, with
    // what the address names brought into view; and a window narrower than
    // the chart on its first unit, the Trinity's.
    tools.hidden = false;
    var kept = null, first = named(), start = world.querySelector('.cp'), ubox = start && boxes[start.dataset.u];
    try { kept = history.state && history.state.cosmo; } catch (e) {}
    try { history.scrollRestoration = 'manual'; } catch (e) {}
    st.w = width();
    if (kept && kept.z > 0) {
      scale(clamp(kept.z, zmin(), ZMAX));
      window.scrollTo({ left: kept.x || 0, top: kept.y || 0, behavior: 'instant' });
      select(first, false);
    } else {
      setZoom(zfirst(), 0, 0);
      if (first) select(first, true);
      else if (ubox && size.offsetWidth > width())
        window.scrollTo({ left: Math.max(0, parseFloat(ubox.getAttribute('x')) * zoom() - 10), top: 0, behavior: 'instant' });
    }
    // The window's width again; the scale held to it where it has changed, and
    // not when a phone's address bar has come or gone.
    st.layout = function () {
      var w = width();
      root.style.setProperty('--cvw', w + 'px');
      if (w !== st.w) { st.w = w; setZoom(zoom()); }
      moved();
    };
    moved();
  }

  window.addEventListener('hashchange', function () { if (S && S.main.isConnected) S.fromHash(); });
  window.addEventListener('resize', function () { if (S && S.main.isConnected) S.layout(); });
  window.addEventListener('scroll', function () { if (S && S.main.isConnected) S.moved(); }, { passive: true });
  // On leaving for another page, the place as it is now, whatever the last rest was.
  window.addEventListener('pagehide', function () { if (S && S.main.isConnected) S.keep(); });
  // The legend shuts on a click anywhere else, as the header's ? does.
  document.addEventListener('click', function (ev) {
    if (S && S.main.isConnected && S.legend.open && !S.legend.contains(ev.target)) S.legend.open = false;
  });
  // Escape shuts the legend, or lets go; + and - scale, 0 is the whole chart,
  // / the search box.  Not in a field, nor under a dialog.
  document.addEventListener('keydown', function (ev) {
    var t = ev.target, k = ev.key;
    if (!S || !S.main.isConnected || document.querySelector('dialog[open]')) return;
    if (k === 'Escape') {
      if (S.legend.open) S.legend.open = false;
      else if (S.sel || S.key) S.letGo();
      return;
    }
    if (ev.defaultPrevented || ev.ctrlKey || ev.metaKey || ev.altKey ||
        (t.closest && t.closest('input, textarea, select, [contenteditable]'))) return;
    if (k === '+' || k === '=') S.zoomBy(1.25);
    else if (k === '-' || k === '_' || k === '−') S.zoomBy(0.8);
    else if (k === '0') S.fit();
    else if (k === '/') S.find();
    else return;
    ev.preventDefault();
  });
  // Brought in by listen.js while it plays, the chart is ub.js's to start
  // (ubCosmo); left that way, the page is put back as a page of the text.
  document.addEventListener('ub:swap', function () {
    if (!document.querySelector('main.cosmo') && root.classList.contains('cchart')) chartMode(false);
  });
  window.ubCosmo = init;
  init();
})();
