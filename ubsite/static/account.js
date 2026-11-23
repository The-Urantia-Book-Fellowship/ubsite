// What follows a reader's account (Tigran, 2026-11-18; DECISIONS.md,
// Accounts): the settings, all but the device's own (settings.py DEVICE), the
// place last read and the bookmarks, the same on every device signed in.  Run
// by ub.js only for a reader who is signed in: one with no account runs none
// of it, and asks the server nothing.
//
// The browser's copy stays the working copy, ub_settings, ub_place and
// ub_marks as ub.js keeps them: what a page is drawn from before it is
// painted, and what works offline.  The server holds a replica (account.py,
// the table `item`), and this is the exchange between the two, one address,
// POST /account/sync: the browser says what changed here since last time and
// the last of the account's running numbers it saw, and is answered with
// everything changed since that number.  The same call with nothing changed
// is how a device learns of the others.  The order is the server's, never
// this browser's clock.
//
// What changed here is found by comparison, not by hooks.  Beside the three
// keys the browser keeps ub_sync: whose account and which database, the
// server's number, when, and `base`, the things as they stood at the last
// exchange (the settings' values; of the place and each bookmark, its
// paragraph and its time).  An exchange compares that with what is stored
// now, the stored values themselves and not the settings with their defaults
// filled in, which would make a default changed in settings.py look like the
// reader's choice.  So a change made in another tab, or on a page of an older
// copy whose script knows nothing of accounts, or offline, is found all the
// same, and sent when the connection returns.  One exchange at a time across
// the tabs (navigator.locks); and what comes is put in a thing at a time,
// storage read afresh, so that a change made during the round trip is not
// written over: it differs from the new base, and goes with the next.
//
// An answer may never be heard: the exchange sent as a page is left outlives
// its page, and a network fails either way.  So what is sent is noted first
// (`sent`, in ub_sync), and whatever stands noted is said again in the next
// exchange, as it then is, changed since or not: the server may or may not
// have taken it the first time, and takes a thing said twice as said once.
// Without that, a setting sent as a page was left and put back on the next
// would never be sent as put back, the browser's base not knowing it had gone.
//
// When: as a page loads or comes back into view, if the last exchange was
// over five minutes ago; three seconds after a setting or a bookmark changes;
// and as the page goes out of view with something changed, which is how the
// place leaves a device: it moves with every paragraph, and never starts an
// exchange by itself.  And whenever the account's menu is opened, for a
// reader who will not wait.
//
// A device that has never exchanged with the account sends everything it has
// and says so (`first`), and the server settles it (account.py sync()): the
// account's settings replace this device's where the account has had an
// exchange before, every bookmark of both is kept, and the place is the
// newer.  Where the browser holds another account's things, the reader is
// asked first, and they are replaced, never merged: the other's are safe with
// their account.
(function () {
  'use strict';
  var S = window.ubSettings, T = window.ubT, DEF = window.ubDefaults || {}, OWN = window.ubOwn || [];
  if (!S || !S.take || !S.kept || !T || !window.fetch || !window.Promise || window.ubFollow) return;
  var KEY = 'ub_sync', RE_REF = /^(\d+):(\d+)\.(\d+)$/,
      EVERY = 5 * 60 * 1000,   // an exchange as a page loads, if the last was longer ago than this
      SOON = 3000,             // after a setting or a bookmark changes
      TURN = 500,              // changes to an exchange: more go in further turns
      LEAVING = 60000,         // bytes: a request that may outlive its page is no larger (the browsers' limit is 64 KB)
      // The version of the exchange this script speaks: which settings it
      // knows to follow the account (settings.py LATE, by the version that
      // first knew each).  The server tells a script nothing of a setting
      // later than its version, and takes nothing from it on one: the first
      // script, which named no version, noted whatever it was sent and said
      // of a setting it did not keep that it was back at its default.  Raised
      // whenever a setting comes to follow the account: 4 with biblesearch,
      // 5 with bible, the Bible's texts in order, 6 with gestures.
      V = 6;
  var timer = 0, running = null, declined = false;

  function get(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } }
  function put(k, v) {
    try {
      if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v));
    } catch (e) {}
  }
  function str(v) { return typeof v === 'string' ? v : ''; }
  // As long as it is sent: a Russian title is two bytes to a letter.
  function bytes(s) { return window.TextEncoder ? new TextEncoder().encode(s).length : s.length * 3; }
  function when(x) { return x && +x.at || 0; }
  function blank() { return { set: {}, place: null, marks: {} }; }
  // Who is signed in, as the browser keeps it (ub_who: base.html ubMe).
  function who() {
    var w = get('ub_who');
    return w && typeof w === 'object' && typeof w.id === 'number' && typeof w.email === 'string' ? w : null;
  }
  // The last exchange, as it was left.
  function state() {
    var sy = get(KEY), b = sy && sy.base;
    if (!sy || typeof sy !== 'object' || typeof sy.n !== 'number' || !b || typeof b !== 'object') return null;
    if (!b.set || typeof b.set !== 'object') b.set = {};
    if (!b.marks || typeof b.marks !== 'object') b.marks = {};
    if (!b.place || typeof b.place !== 'object') b.place = null;
    return sy;
  }
  function follows(k) { return k in DEF && OWN.indexOf(k) < 0; }
  function order(a, b) {
    var x = RE_REF.exec(a.ref), y = RE_REF.exec(b.ref);
    return x[1] - y[1] || x[2] - y[2] || x[3] - y[3];
  }
  // The bookmarks the browser keeps, those that name a paragraph.
  function kept() {
    var m = get('ub_marks');
    return Array.isArray(m) ? m.filter(function (x) { return x && typeof x.ref === 'string' && RE_REF.test(x.ref); }) : [];
  }
  // The browser's copy as it stands: the settings that follow the account,
  // as stored; the place; the bookmarks by their paragraphs.
  function here() {
    var s = S.kept(), st = blank(), p = get('ub_place'), k;
    for (k in s) if (follows(k) && s[k] !== DEF[k] && typeof s[k] === typeof DEF[k]) st.set[k] = s[k];
    if (p && typeof p === 'object' && typeof p.ref === 'string' && RE_REF.test(p.ref))
      st.place = { ref: p.ref, title: str(p.title), at: when(p), v: str(p.v) };
    kept().forEach(function (x) { st.marks[x.ref] = { title: str(x.title), q: str(x.q), at: when(x), v: str(x.v) }; });
    return st;
  }
  function samePlace(a, b) { return a && b ? a.ref === b.ref && a.at === b.at : !a && !b; }
  // What differs between the last exchange and now, as it is sent: [kind,
  // key, value], null for a bookmark removed or a setting back at its
  // default.  The place is never removed.
  function changed(base, now) {
    var ch = [], k;
    for (k in now.set) if (now.set[k] !== base.set[k]) ch.push(['set', k, now.set[k]]);
    // Only of a setting this script keeps: one it does not know is not its to
    // call back to its default (note, below, which no longer takes one in).
    for (k in base.set) if (follows(k) && !(k in now.set)) ch.push(['set', k, null]);
    if (now.place && !samePlace(now.place, base.place)) ch.push(['place', '', now.place]);
    for (k in now.marks) if (base.marks[k] !== now.marks[k].at) ch.push(['mark', k, now.marks[k]]);
    for (k in base.marks) if (!now.marks[k]) ch.push(['mark', k, null]);
    return ch;
  }
  // A thing as it now stands, as it is sent: for what was sent before and
  // not answered for.
  function stands(now, kind, key) {
    if (kind === 'set') return follows(key) ? ['set', key, key in now.set ? now.set[key] : null] : null;
    if (kind === 'mark') return RE_REF.test(key) ? ['mark', key, now.marks[key] || null] : null;
    return kind === 'place' && now.place ? ['place', '', now.place] : null;
  }
  // What this exchange says: what differs from the base, and what was said
  // before with no answer heard.
  function saying(sy, now) {
    var ch = changed(sy.base, now), has = {};
    ch.forEach(function (c) { has[c[0] + ' ' + c[1]] = true; });
    (Array.isArray(sy.sent) ? sy.sent : []).forEach(function (x) {
      var c = Array.isArray(x) && !has[x[0] + ' ' + x[1]] && stands(now, x[0], x[1]);
      if (c) { has[c[0] + ' ' + c[1]] = true; ch.push(c); }
    });
    return ch;
  }
  // One change, sent or come, put on the base.
  function note(base, c) {
    var v = c[2];
    if (c[0] === 'set') {
      if (!follows(c[1])) return;
      if (v === null) delete base.set[c[1]]; else base.set[c[1]] = v;
    }
    else if (c[0] === 'place') { if (v && RE_REF.test(v.ref)) base.place = { ref: v.ref, at: when(v) }; }
    else if (c[0] === 'mark') { if (v === null) delete base.marks[c[1]]; else base.marks[c[1]] = when(v); }
  }
  // What came, put into the browser's copy, each thing only where it stands
  // as it stood when the exchange began (`snap`).  how.sets: the account's
  // settings replace this device's, one left out being its default.
  // how.all: everything is the account's, and nothing here is kept.
  function bring(ch, snap, how) {
    var fresh = here(), sets = {}, any = false, marks = null, wrote = false, k;
    if (how.all) {
      put('ub_marks', null);
      put('ub_place', null);
      fresh.marks = {};
      fresh.place = null;
      snap = fresh;
      wrote = true;
    }
    if (how.sets) for (k in fresh.set) { sets[k] = null; any = true; }
    ch.forEach(function (c) {
      var kind = c[0], key = c[1], v = c[2];
      if (kind === 'set') {
        if (follows(key) && (how.sets || fresh.set[key] === snap.set[key])) { sets[key] = v; any = true; }
      } else if (kind === 'place') {
        if (v && RE_REF.test(v.ref) && samePlace(fresh.place, snap.place)) {
          put('ub_place', { ref: v.ref, title: str(v.title), at: when(v), v: str(v.v) });
          wrote = true;
        }
      } else if (kind === 'mark' && RE_REF.test(key) && when(fresh.marks[key]) === when(snap.marks[key]) &&
                 !fresh.marks[key] === !snap.marks[key]) {
        if (!marks) { marks = {}; kept().forEach(function (x) { marks[x.ref] = x; }); }
        if (v) marks[key] = { ref: key, title: str(v.title), q: str(v.q), at: when(v), v: str(v.v) };
        else delete marks[key];
      }
    });
    if (marks) {
      marks = Object.keys(marks).map(function (r) { return marks[r]; }).sort(order);
      put('ub_marks', marks.length ? marks : null);
      wrote = true;
    }
    // The settings last: Whole paper come from another device moves the page.
    if (any) S.take(sets); else if (wrote) document.dispatchEvent(new Event('ub:brought'));
  }

  // One exchange.  It answers whether there is more to send.
  function turn(opt, again) {
    var me = who(), sy = state(), first = false, all = false, snap, ch, send, body;
    if (!me) return Promise.resolve(false);
    // Another database than the one last exchanged with, the host's restored
    // or made anew: this device starts over with it.
    if (sy && me.db && sy.db !== me.db) sy = null;
    if (sy && sy.id !== me.id) {
      // Another account's things, on a computer two people use.
      if (declined || (opt && opt.leaving)) return Promise.resolve(false);
      if (!window.confirm(T.text('sync:other?', { name: me.name }))) {
        // No one is signed in from now, so that no other tab asks the same;
        // ub.js tells the server.
        declined = true;
        put('ub_who', null);
        document.dispatchEvent(new CustomEvent('ub:acct', { detail: 'out' }));
        return Promise.resolve(false);
      }
      sy = null;
      all = true;
    }
    if (!sy) { first = true; sy = { id: me.id, db: null, n: 0, base: blank() }; }
    snap = here();
    ch = all ? [] : saying(sy, snap);
    send = ch.slice(0, TURN);
    // `was`: the version of the script that made what is kept of the last
    // exchange, 1 where it named none.  A setting that script did not know
    // is new to this browser, and the server sends it whatever its number.
    body = JSON.stringify({ first: first, db: sy.db, n: sy.n, v: V, was: (sy.v | 0) >= 1 ? sy.v | 0 : 1, ch: send });
    // Noted as sent before it goes.  Not on a first exchange, which has
    // nothing kept to note it in, and is begun again whole if it fails.
    if (!first && ch.length) {
      sy.sent = ch.map(function (c) { return [c[0], c[1]]; });
      put(KEY, sy);
    }
    return fetch('/account/sync', { method: 'POST', credentials: 'same-origin', cache: 'no-store',
                                    keepalive: !!(opt && opt.leaving) && bytes(body) < LEAVING,
                                    headers: { 'Content-Type': 'application/json' }, body: body })
      .then(function (r) {
        // The session has ended, here or from another device: no one is signed in.
        if (r.status === 401) { document.dispatchEvent(new CustomEvent('ub:acct', { detail: 'gone' })); return null; }
        if (!r.ok) throw r;
        return r.json();
      }).then(function (got) {
        var base, replace;
        if (!got) return false;
        if (got.restart) {
          // The server's number is behind this browser's, or its database
          // another: begun again as a first exchange, once.
          put(KEY, null);
          return again ? false : turn(opt, true);
        }
        if (!Array.isArray(got.ch) || typeof got.n !== 'number') return false;
        replace = first && (all || got.had === true);
        base = first ? blank() : sy.base;
        // The base: what was sent is as the server has it, or comes back
        // in its answer as the server has it instead.
        send.forEach(function (c) { if (!(replace && c[0] === 'set')) note(base, c); });
        got.ch.forEach(function (c) { if (Array.isArray(c)) note(base, c); });
        // Signed out meanwhile, or the account deleted: nothing is put in.
        if (!who() || who().id !== me.id) return false;
        bring(got.ch.filter(Array.isArray), snap, { all: all, sets: replace });
        // Answered for: nothing stands noted as sent but what waits its turn.
        put(KEY, { id: got.id, db: got.db, n: got.n, t: Date.now(), v: V, base: base,
                   sent: ch.slice(send.length).map(function (c) { return [c[0], c[1]]; }) });
        // Everything here was another's: the page read again as it now is.
        if (all) location.reload();
        return ch.length > send.length;
      });
  }
  function lock(f) {
    return navigator.locks && navigator.locks.request ? navigator.locks.request(KEY, f) : f();
  }
  // Exchanges until there is no more to send, one run at a time; a failure
  // waits for the next occasion.  As a page is left there is one exchange,
  // asked for at once and with no lock waited for: a page on its way out
  // gets no later turn.
  function run(opt) {
    if (running) return running;
    var turns = 0, go = function () {
      return turn(opt).then(function (more) { return more && ++turns < 20 ? go() : null; });
    };
    running = (opt && opt.leaving ? turn(opt) : Promise.resolve().then(function () { return lock(go); }))
      .catch(function () {}).then(function () { running = null; });
    return running;
  }
  // Something here to send, `but` the place where it alone is not to count;
  // or time to ask what the other devices changed.
  function dirty(but) {
    var me = who(), sy = state();
    return !!me && (!sy || sy.id !== me.id ||
                    saying(sy, here()).some(function (c) { return !(but && c[0] === 'place'); }));
  }
  function due() {
    var me = who(), sy = state();
    return !!me && (!sy || sy.id !== me.id || !(Date.now() - (+sy.t || 0) < EVERY));
  }
  function soon() {
    clearTimeout(timer);
    timer = setTimeout(function () { if (dirty()) run(); }, SOON);
  }
  function leaving() { if (dirty()) run({ leaving: true }); }

  document.addEventListener('ub:settings', soon);
  document.addEventListener('ub:kept', function (ev) { if (ev.detail === 'mark') soon(); });
  // Out of view, the place goes with whatever else changed; a phone locked
  // on one long page says no more than this.  Back in view, the others'.
  document.addEventListener('visibilitychange', function () { if (document.hidden) leaving(); else if (due()) run(); });
  addEventListener('pagehide', leaving);
  addEventListener('pageshow', function (ev) { if (ev.persisted && due()) run(); });
  addEventListener('online', function () { if (dirty()) soon(); });
  // Signed in, on this page or in another tab; signed out stops it, there
  // being no one to ask for.
  document.addEventListener('ub:who', function () { if (due()) run(); });
  addEventListener('storage', function (ev) { if (ev.key === 'ub_who' && due()) run(); });

  // For ub.js, as it signs a reader out.  Before: what has not been sent
  // yet goes first, and is not waited for long.  After, where the reader
  // asked for it, on a computer that is not their own: what followed the
  // account is taken out of this browser too, the settings that follow it,
  // the bookmarks and the place, the device's own settings staying; and the
  // page is read again as it then is.
  window.ubFollow = {
    // And as the account's menu is opened: an exchange now, whenever the
    // last was, so that a reader with a device in each hand need not wait.
    now: function () { return run(); },
    flush: function () {
      clearTimeout(timer);
      if (!dirty()) return Promise.resolve();
      return Promise.race([run(), new Promise(function (ok) { setTimeout(ok, 4000); })]);
    },
    forget: function () {
      var s = S.kept(), sets = {}, k;
      clearTimeout(timer);
      for (k in s) if (follows(k)) sets[k] = null;
      put('ub_marks', null);
      put('ub_place', null);
      put(KEY, null);
      S.take(sets);
      location.reload();
    }
  };
  // As the page loads: time to ask; or something waits that the last page
  // did not send, a change made as it was left, or made offline.  Not the
  // place alone, which went as that page was left and whose answer no page
  // was there to hear.
  if (due()) run(); else if (dirty(true)) soon();
})();
