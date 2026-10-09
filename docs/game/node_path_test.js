/* Deterministic headless test: runs game.js in Node with fake DOM + fake WebAudio.
   Exit 0 = N frames rendered without crash; exit 1 = runtime crash (stack in /tmp/node_test_err.txt). */
'use strict';
const fs = require('fs');
const vm = require('vm');

process.on('uncaughtException', function (e) {
  fs.writeFileSync('/tmp/node_test_err.txt', e.stack || String(e));
  process.stderr.write('CRASH: ' + (e.stack || e) + '\n');
  process.exit(1);
});

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
  createBuffer(c, l, s) { return { getChannelData: function () { return new Float32Array(Math.max(1, l || 44100)); }, sampleRate: 44100 }; }
  createBufferSource() { return node(); }
  createOscillator() { return { type: 'sine', frequency: { value: 0, setValueAtTime: function () {} }, gain: node(), start: function () {}, stop: function () {}, connect: function (d) { return node(); } }; }
  createGain() { return { gain: node(), connect: function (d) { return node(); } }; }
  createBiquadFilter() { return { type: 'lowpass', frequency: node(), Q: { value: 1 }, gain: node(), connect: function (d) { return node(); } }; }
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
  location: { search: '?t=1&hold=1', href: 'http://127.0.0.1:8891/', origin: 'http://127.0.0.1:8891', protocol: 'http:' },
  performance: { now: function () { return Date.now(); } },
  setInterval: setInterval, setTimeout: setTimeout,
  clearInterval: clearInterval, clearTimeout: clearTimeout,
  fetch: function () { return new Promise(function (r) { setTimeout(function () { r({ ok: true, text: function () { return Promise.resolve('ok'); } }); }, 0); }); },
  Image: function () { return { src: '', onload: null, onerror: null }; },
  AudioContext: FakeAudioContext,
  webkitAudioContext: undefined,
};
let frames = 0;
const MAX = 150;
function raf(cb) {
  if (frames >= MAX) return 0;
  frames++;
  return setTimeout(function () { cb(Date.now()); }, 10);
}

const context = vm.createContext({
  document: document, window: window, location: window.location, performance: window.performance,
  fetch: window.fetch, Image: window.Image, setTimeout: setTimeout, setInterval: setInterval,
  clearTimeout: clearTimeout, clearInterval: clearInterval, requestAnimationFrame: raf,
  console: console, Math: Math, Promise: Promise, Float32Array: Float32Array,
});
vm.runInContext(fs.readFileSync(__dirname + '/game.js', 'utf8'), context);
setTimeout(function () {
  console.log('OK: ran ' + frames + ' frames without crash\n');
  try {
    var PATH = vm.runInContext('PATH', context);
    var WORLD = vm.runInContext('WORLD', context);
    var ENEMY = vm.runInContext('ENEMY', context);
    console.log('PATH gridWxH =', PATH.gridW + 'x' + PATH.gridH);
    console.log('  ENEMY type:', typeof ENEMY, 'ENEMY.list:', ENEMY ? (typeof ENEMY.list) : 'n/a');
    /* connectivity flood-fill from (10,30) */
    var gw = PATH.gridW, gh = PATH.gridH, N = gw * gh;
    var seen = new Uint8Array(N); var q = [30 * gw + 10]; seen[30 * gw + 10] = 1; var reach = 0;
    for (var qi = 0; qi < q.length; qi++) { var i = q[qi]; var cx = i % gw; var cy = (i / gw) | 0; reach++;
      for (var d = 0; d < 8; d++) { var dx = [0,1,0,-1,1,1,-1,-1][d], dy = [1,0,-1,0,1,-1,1,-1][d];
        var nx = cx + dx, ny = cy + dy; if (nx < 0 || nx >= gw || ny < 0 || ny >= gh) continue;
        var ni = ny * gw + nx; if (seen[ni] || PATH.cells[ni]) continue;
        if (d >= 4) { var sx2 = dx > 0 ? 1 : -1, sy2 = dy > 0 ? 1 : -1; var c1 = cy * gw + cx + sx2, c2 = (cy + sy2) * gw + cx; if (PATH.cells[c1] || PATH.cells[c2]) continue; }
        seen[ni] = 1; q.push(ni); }
    }
    console.log('  reachable cells from (200,600) =', reach, 'of', N);
    /* compare calling conventions */
    var r_vm = vm.runInContext('PATH.pathfind(100,100,1900,1100)', context);
    console.log('  VM-call (100,100)->(1900,1100):', r_vm ? r_vm.length : 'NULL');
    console.log('  Node-call (100,100)->(1900,1100):', (PATH.pathfind(100,100,1900,1100) ? 'len'+(PATH.pathfind(100,100,1900,1100).length):'NULL'));
    console.log('  VM-call (200,600)->(1800,600):', vm.runInContext('PATH.pathfind(200,600,1800,600)', context) ? 'FOUND' : 'NULL');
    var r2_vm = vm.runInContext('PATH.pathfind(200,600,1800,600)', context);
    console.log('  VM-call (200,600)->(1800,600) len:', r2_vm ? r2_vm.length : 'NULL');
    /* check a few goal cells */
    var cells2check = [[1800,600],[200,100],[1800,900],[200,900],[500,600],[1500,600]]; var cc=[0];
    cells2check.forEach(function(pt){ var cx=Math.floor(pt[0]/20),cy=Math.floor(pt[1]/20); var i=cy*gw+cx; cc.push((seen[i]?'R':'X')+(PATH.cells[i]?'B':'.')); });
    console.log('  goal cells (1800,600)(200,100)(1800,900)(200,900)(500,600)(1500,600):', cc.slice(1).join(' '));
    /* cell at start (10,30) */
    console.log('  start cell (10,30) blocked?', PATH.cells[30*gw+10], 'reachable?', seen[30*gw+10]);
    console.log('  sample cell (50,30) blocked?', PATH.cells[30*gw+50], 'reachable?', seen[30*gw+50]);
    var blocked = 0; for (var i = 0; i < PATH.cells.length; i++) if (PATH.cells[i]) blocked++;
    console.log('  blocked cells =', blocked, 'of', PATH.gridW * PATH.gridH);
    function pf(a, b) { var r = PATH.pathfind(a, b); return r ? r.length : 'NULL'; }
    console.log('  path (200,600)->(1800,600):', pf(200, 600, 1800, 600));
    console.log('  path (200,600)->(200,100):', pf(200, 600, 200, 100));
    console.log('  path (1800,100)->(1800,900):', pf(1800, 100, 1800, 900));
    function check(a, b) { var r = PATH.pathfind(a, b); if (!r) return { len: 'NULL' }; var bad = 0; r.forEach(function (c) { if (PATH.cells[c.cy * PATH.gridW + c.cx]) bad++; }); return { len: r.length, badCells: bad }; }
    console.log('  check (200,600)->(1800,600):', JSON.stringify(check(200, 600, 1800, 600)));
    console.log('  check (200,600)->(200,100):', JSON.stringify(check(200, 600, 200, 100)));
    console.log('  check (1800,100)->(1800,900):', JSON.stringify(check(1800, 100, 1800, 900)));
    if (ENEMY && ENEMY.list && WORLD && WORLD.objs) {
      var objs = WORLD.objs; var inObj = 0;
      ENEMY.list.forEach(function (e) {
        for (var j = 0; j < objs.length; j++) {
          var o = objs[j]; if (!o.solid) continue;
          if (e.x > o.x - 3 && e.x < o.x + o.w + 3 && e.y > o.y - 3 && e.y < o.y + o.h + 3) { inObj++; break; }
        }
      });
      console.log('  enemies =', ENEMY.list.length, 'inside solid object =', inObj, '(should be ~0)');
    } else {
      console.log('  ENEMY.list/WORLD.objs:', (ENEMY && ENEMY.list ? 'list-OK' : 'missing'), (WORLD && WORLD.objs ? 'objs-OK' : 'missing'));
    }
    process.exit(0);
  } catch (e) {
    console.log('INSPECT ERROR:'); console.log(e.stack);
    process.exit(2);
  }
}, MAX * 12 + 2500);
