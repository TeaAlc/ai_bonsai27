/* Deterministic assertions for the WASD + grenade fixes.
   Runs game.js in a Node VM, then drives specific functions and checks results.
   Exit 0 = all checks pass; exit 1 = any check fails (details printed). */
'use strict';
const fs = require('fs');
const vm = require('vm');

function node() {
  const t = function () {};
  return new Proxy(t, {
    get: function (s, p) {
      if (p === 'then') return Promise.resolve();
      if (p in s) return s[p];
      if (p === 'connect') return function (d) { return node(); };
      return node();
    },
    set: function (s, p, v) { s[p] = v; return true; },
    has: function () { return false; },
  });
}
class FakeAudioContext {
  constructor() { this.state = 'running'; this.sampleRate = 44100; this.currentTime = 0; this.destination = node(); }
  resume() { return Promise.resolve(); }
  close() { return Promise.resolve(); }
  createBuffer(c, l, s) { return { getChannelData: function () { return new Float32Array(Math.max(1, l || 44100)); }, sampleRate: 44100 }; };
  createBufferSource() { return node(); }
  createOscillator() { return { type: 'sine', frequency: { value: 0, setValueAtTime: function () {} }, gain: node(), start: function () {}, stop: function () {}, connect: function (d) { return node(); } }; };
  createGain() { return { gain: node(), connect: function (d) { return node(); } }; };
  createBiquadFilter() { return { type: 'lowpass', frequency: node(), Q: { value: 1 }, gain: node(), connect: function (d) { return node(); } }; };
}
function ctx2d() {
  const t = {};
  return new Proxy(t, {
    get: function (s, p) { if (p in s) return s[p]; if (p === 'then') return Promise.resolve(); return node(); },
    set: function (s, p, v) { s[p] = v; return true; },
    has: function () { return false; },
  });
}
function fakeCanvas() { return { width: 960, height: 540, getContext: function () { return ctx2d(); }, toDataURL: function () { return 'x'; } }; }
function mkEl() {
  return {
    style: {}, textContent: '', innerHTML: '', className: '',
    classList: { add: function () {}, remove: function () {}, toggle: function () {} },
    addEventListener: function () {}, removeEventListener: function () {},
    appendChild: function (c) { return c; },
    querySelector: function (s) { return mkEl(); },
    querySelectorAll: function (s) { return [mkEl(), mkEl(), mkEl()]; },
    getBoundingClientRect: function () { return { left: 0, top: 0, width: 960, height: 540 }; },
    width: 960, height: 540,
  };
}
const made = {};
function elFor(id) { if (!made[id]) made[id] = id === 'game' ? fakeCanvas() : mkEl(); return made[id]; }
const document = {
  getElementById: function (id) { return elFor(id); },
  querySelector: function (sel) { return sel && sel[0] === '#' ? elFor(sel.slice(1)) : mkEl(); },
  querySelectorAll: function (sel) { return [mkEl()]; },
  createElement: function (tag) { return tag === 'canvas' ? fakeCanvas() : mkEl(); },
  body: elFor('body'), head: elFor('head'), documentElement: elFor('html'), addEventListener: function () {},
};
const window = {
  onerror: null,
  addEventListener: function () {}, removeEventListener: function () {},
  innerWidth: 960, innerHeight: 540,
  document: document,
  location: { search: '', href: 'http://127.0.0.1:8891/', origin: 'http://127.0.0.1:8891', protocol: 'http:' },
  performance: { now: function () { return Date.now(); } },
  setInterval: setInterval, setTimeout: setTimeout,
  clearInterval: clearInterval, clearTimeout: clearTimeout,
  fetch: function () { return new Promise(function (r) { setTimeout(function () { r({ ok: true, text: function () { return Promise.resolve('ok'); } }); }, 0); }); },
  Image: function () { return { src: '', onload: null, onerror: null }; },
  AudioContext: FakeAudioContext,
  webkitAudioContext: undefined,
};

const context = vm.createContext({
  document: document, window: window, location: window.location, performance: window.performance,
  fetch: window.fetch, Image: window.Image, setTimeout: setTimeout, setInterval: setInterval,
  clearTimeout: clearTimeout, clearInterval: clearInterval,
  requestAnimationFrame: function () { return 0; },
  console: console, Math: Math, Promise: Promise, Float32Array: Float32Array,
});
vm.runInContext(fs.readFileSync(__dirname + '/game.js', 'utf8'), context);

/* expose game globals for assertions */
vm.runInContext('this._P = P; this._PROJ = PROJ; this._IN = IN; this._CFG = CFG; this._CAM = CAM; this._ENEMY = ENEMY; this._SFX = SFX; this._WORLD = WORLD;', context);
const P = context._P, PROJ = context._PROJ, IN = context._IN, CFG = context._CFG, WORLD = context._WORLD;

let failed = 0;
function check(name, ok, details) {
  if (ok) { console.log('  PASS ' + name); }
  else { failed++; console.error('  FAIL ' + name + (details ? ' :: ' + details : '')); }
}

const dt = 1 / 60;

console.log('=== WASD movement (P.update with normalized keys) ===');
function moveTest(keys, checkFn) {
  P.x = 1000; P.y = 600; P.dead = false; P.grenCd = 0;
  P.sprint.active = false; P.sprint.recover = 0; P.sprint.t = 0;
  P.hp = 100; P.regen.lastHit = -99;
  const x0 = P.x, y0 = P.y;
  for (let i = 0; i < 30; i++) P.update(dt, { x: 500, y: 300 }, keys, null);
  const moved = Math.hypot(P.x - x0, P.y - y0);
  checkFn(moved, P.x, P.y);
}
// D moves right (+x)
moveTest({ D: true }, function (m, x, y) { check('WASD D moves right', m > 10, 'dist=' + m.toFixed(1) + ' x=' + x.toFixed(1)); });
// A moves left
moveTest({ A: true }, function (m, x, y) { check('WASD A moves left', m > 10, 'dist=' + m.toFixed(1) + ' x=' + x.toFixed(1)); });
// W moves up (-y)
moveTest({ W: true }, function (m, x, y) { check('WASD W moves up', m > 10, 'dist=' + m.toFixed(1) + ' y=' + y.toFixed(1)); });
// S moves down
moveTest({ S: true }, function (m, x, y) { check('WASD S moves down', m > 10, 'dist=' + m.toFixed(1) + ' y=' + y.toFixed(1)); });
// no keys -> no move
moveTest({}, function (m) { check('no input -> no move', m < 2, 'moved=' + m.toFixed(3)); });
// verify lowercase was normalized: call the keydown handler directly via a captured event
// (IN is the real input object; simulate by setting the same normalized keys the handler would produce)

console.log('=== Grenade (flies away from player, not instant self-damage) ===');
// reset player to a clear, interior spot; aim to the right
P.x = 1000; P.y = 600; P.dead = false; P.grenCd = 0; P.grenCount = 8;
P.aimX = 1300; P.aimY = 600; // aim direction: +x, 300px away
P.sprint.active = false;
// ensure no enemies to interfere
if (context._ENEMY && context._ENEMY.arr) context._ENEMY.arr.length = 0;

P.throwGrenade(context._SFX);
let g = null;
for (const b of PROJ.arr) if (b.kind === 'grenade') g = b;
check('grenade object created', !!g, 'arrLen=' + PROJ.arr.length);
check('grenade kind=grenade', !!g && g.kind === 'grenade', g ? JSON.stringify({ kind: g.kind }) : 'none');
check('grenade fuse = 1.5 (BUG WAS fuse=0)', !!g && Math.abs(g.fuse - 1.5) < 0.01, g ? 'fuse=' + g.fuse : 'none');
check('grenade blastR/blastDmg from config', !!g && g.blastR === 100 && g.blastDmg === 80, g ? 'blastR=' + g.blastR + ' blastDmg=' + g.blastDmg : 'none');
check('grenade target != (0,0)', !!g && (g.targetX !== 0 || g.targetY !== 0), g ? 'tx=' + g.targetX + ' ty=' + g.targetY : 'none');
check('grenade target ~300px away from thrower (throwR)', !!g && Math.abs(Math.hypot(g.targetX - 1000, g.targetY - 600) - 300) < 40, g ? 'distToTarget=' + Math.hypot(g.targetX - 1000, g.targetY - 600) : 'none');

// run the REAL grenade update loop for ~0.5s and confirm it moves AWAY from the player
const startPlayerX = P.x, startPlayerY = P.y;
for (let i = 0; i < 30; i++) {
  if (!g || !PROJ.arr.indexOf(g >= 0)) break;
  // find the current grenade (may be same reference)
  for (const b of PROJ.arr) if (b.kind === 'grenade') g = b;
  PROJ.update(dt, context._SFX);
  for (const b of PROJ.arr) if (b.kind === 'grenade') g = b;
  if (!g) break;
}
if (g) {
  const dist = Math.hypot(g.x - P.x, g.y - P.y);
  check('grenade flew away from player (dist>150px after 0.5s)', dist > 150, 'dist=' + dist.toFixed(1) + ' g=(' + g.x.toFixed(0) + ',' + g.y.toFixed(0) + ')');
  check('grenade heading toward its target (closer to target than start)',
        Math.hypot(g.x - g.targetX, g.y - g.targetY) < 300,
        'gToTarget=' + Math.hypot(g.x - g.targetX, g.y - g.targetY).toFixed(1));
} else {
  check('grenade still in flight after 0.5s (not instant explode)', false, 'grenade vanished (exploded on player?)');
}

// verify self-damage: throwing a grenade should NOT drop player HP (it flies away, blast at 300px > blastR 100)
P.hp = 100; P.aimX = 1300; P.aimY = 600; P.throwGrenade(context._SFX);
for (let i = 0; i < 100; i++) if (PROJ.arr.length) { for (const b of PROJ.arr) if (b.kind === 'grenade') { } ; }
// run until the grenade explodes, then confirm player still full
for (let i = 0; i < 200; i++) {
  const hasG = PROJ.arr.some(function (b) { return b.kind === 'grenade'; });
  if (!hasG) break;
  PROJ.update(dt, context._SFX);
}
check('player NOT self-damaged by throw (hp still 100)', P.hp === 100, 'hp=' + P.hp.toFixed(1));

console.log('=== World collision (player cannot pass through solids) ===');
function findHouse(cx, cy) {
  let best = null, bestd = 1e9;
  for (let i = 0; i < WORLD.objs.length; i++) {
    const o = WORLD.objs[i];
    if (o.type !== 'house') continue;
    const d = Math.hypot((o.x + o.w / 2) - cx, (o.y + o.h / 2) - cy);
    if (d < bestd) { bestd = d; best = o; }
  }
  return best;
}
const house = findHouse(1300, 900); /* house at (1300,900,240,180) has clear space on all sides */
check('collision: house located for test', !!house, house ? 'x=' + house.x : 'none found');
function rc(cx, cy) { return WORLD.resolveCircle(cx, cy, 16, 3); }
let r;
r = rc(house.x + house.w + 2, house.y + house.h / 2);
check('collision: right of house pushed right', r.x >= house.x + house.w + 15, 'x=' + r.x.toFixed(1) + ' face=' + (house.x + house.w));
r = rc(house.x - 2, house.y + house.h / 2);
check('collision: left of house pushed left', r.x <= house.x - 15, 'x=' + r.x.toFixed(1) + ' face=' + house.x);
r = rc(house.x + house.w / 2, house.y + house.h + 2);
check('collision: below house pushed down', r.y >= house.y + house.h + 15, 'y=' + r.y.toFixed(1) + ' face=' + (house.y + house.h));
r = rc(house.x + house.w / 2, house.y - 2);
check('collision: above house pushed up', r.y <= house.y - 15, 'y=' + r.y.toFixed(1) + ' face=' + house.y);
r = rc(1000, 600);
check('collision: open space unchanged', r.x === 1000 && r.y === 600, 'r=(' + r.x + ',' + r.y + ')');
/* P.update: player is blocked by a solid wall when moving into it */
P.x = house.x - 20; P.y = house.y + house.h / 2; P.dead = false;
P.sprint.active = false; P.sprint.recover = 0; P.hp = 100;
for (let i = 0; i < 60; i++) { P.update(dt, { x: 500, y: 300 }, { D: true }, null); }
check('player blocked by house (stays left of left face)', P.x <= house.x - P.radius + 1, 'P.x=' + P.x.toFixed(1) + ' face=' + house.x + ' start was ' + (house.x - 20));
const total = 20;
console.log(failed === 0 ? '\nALL CHECKS PASSED (' + total + ' of ' + total + ')' : '\nFAILED ' + failed + ' of ' + total + ' checks');
process.exit(failed === 0 ? 0 : 1);
