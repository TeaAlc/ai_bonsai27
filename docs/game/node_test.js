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
const MAX = 400;
function raf(cb) {
  if (frames >= MAX) return 0;
  frames++;
  return setTimeout(function () { cb(Date.now()); }, 16);
}

const context = vm.createContext({
  document: document, window: window, location: window.location, performance: window.performance,
  fetch: window.fetch, Image: window.Image, setTimeout: setTimeout, setInterval: setInterval,
  clearTimeout: clearTimeout, clearInterval: clearInterval, requestAnimationFrame: raf,
  console: console, Math: Math, Promise: Promise, Float32Array: Float32Array,
});
vm.runInContext(fs.readFileSync(__dirname + '/game.js', 'utf8'), context);
setTimeout(function () {
  process.stderr.write('OK: ran ' + frames + ' frames without crash\n');
  process.exit(frames > 50 ? 0 : 1);
}, MAX * 17 + 3000);
