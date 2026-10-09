/* ==================================================================
   DWARF BUSTER — game.js
   Single-file CLASSIC script (NOT ES modules) so the game works with a
   double-click on index.html (file:// protocol, no CORS issues).

   Sections:
     1. CONFIG
     2. UTILS
     3. SEED RNG
     4. ASSET LOADER (optional real PNGs -> procedural fallback)
     5. SOUND ENGINE (WebAudio, fully synthesized)
     6. PARTICLES
     7. INPUT (keyboard + mouse)
     8. CAMERA + SHAKES
     9. WORLD (map layout, static layer, collision)
    10. PLAYER
    11. ENEMIES
    12. PROJECTILES (bullets / pellets / grenades)
    13. PICKUPS
    14. ART (procedural Canvas drawing)
    15. HUD (DOM updates)
    16. SCREENS + STATE MACHINE
    17. MAIN LOOP + BOOT + TEST MODES
   ================================================================== */
"use strict";

/* ------------------------------------------------------- 1. CONFIG ---- */
const CFG = {
  world:      { w: 2000, h: 1200 },
  canvas:     { w: 960,  h: 540  },
  fixedDt:    1 / 60,
  maxDt:      0.1,
  enemyBaseSpeed: 50,   /* enemy spd values are multipliers of this */

  player: {
    hp: 100, maxHp: 100,
    speed: 150, sprintMult: 1.35,
    sprintTime: 3, sprintRecover: 1.5,
    regen: 8, regenDelay: 3, regenMin: 40,   // 8/s HP when no hit for 3s and hp>40
    radius: 16,
  },
  weapons: [
    { name: 'Pistole',   dmg: 25, mag: 10, rate: 0.4,  range: 400, pellets: 1, spread: 0,   auto: false, color: '#f2c14e' },
    { name: 'Gewehr',    dmg: 35, mag: 30, rate: 0.25, range: 600, pellets: 1, spread: 0,   auto: true,  color: '#ff9933' },
    { name: 'Shotgun',   dmg: 15, mag: 5,  rate: 1.2,  range: 260, pellets: 5, spread: 0.7, auto: false, color: '#ff5533' },
  ],
  ammoMax: 40,
  grenade: {
    count: 4, maxCount: 8,
    throwR: 300, fuse: 1.5, blastR: 100, blastDmg: 80,
    cooldown: 1.2,
  },
  enemies: {
    zombie:  { hp: 80,  spd: 1.2, dmg: 8,  meleeR: 24, score: 100, loot: { ammo: [5,10], ammoP: .25, grenP: 0   } },
    soldier: { hp: 150, spd: 2.5, dmg: 5,  meleeR: 20, range: 320, rate: 2.2, score: 200, loot: { ammo: [10,20], ammoP: .30, grenP: .10 } },
    bossz:   { hp: 600, spd: 2.0, dmg: 16, meleeR: 34, score: 2000, lungeCd: 3.5 },   // zombie captain
    bossw:   { hp: 700, spd: 2.3, dmg: 14, meleeR: 34, score: 2000, lungeCd: 3.0, grenadeCd: 6 },
  },
  waves: [
    { zombies: 5,  soldiers: 0 },
    { zombies: 8,  soldiers: 3 },
    { zombies: 10, soldiers: 5, boss: 1 },
    { zombies: 12, soldiers: 6, boss: 1 },
    { zombies: 15, soldiers: 8, boss: 1 },
  ],
  overload: { at: 250, count: 20, speed: 1.4, wavesDone: 5 },
  spawnWarn: 4,         // seconds of spawn warning (blink + horn)
  pickups: { ttl: 8, ttlGold: 30 },
  combo: { window: 5, max: 9 },
  shake: { max: 14, decay: 6 },
  damageFlash: 0.2,
  waveGaps: [0, 45, 90, 140, 190],
};

const STATE = { MENU: 0, PLAYING: 1, PAUSED: 2, GAMEOVER: 3, VICTORY: 4 };
const W = CFG.world, C = CFG.canvas;

/* ----------------------------------------------------------- 2. UTILS --- */
function rand(a, b) { return a + Math.random() * (b - a); }
function irand(a, b) { return Math.floor(rand(a, b + 1)); }
function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
function lerp(a, b, t) { return a + (b - a) * t; }
function dist2(ax, ay, bx, by) { const dx = ax - bx, dy = ay - by; return dx * dx + dy * dy; }
function dist(ax, ay, bx, by) { return Math.sqrt(dist2(ax, ay, bx, by)); }
function ang(ax, ay, bx, by) { return Math.atan2(by - ay, bx - ax); }
function vecAdd(a, b) { return { x: a.x + b.x, y: a.y + b.y }; }
function vecSub(a, b) { return { x: a.x - b.x, y: a.y - b.y }; }
function vecLen(v) { return Math.sqrt(v.x * v.x + v.y * v.y); }
function vecNorm(v) { const l = vecLen(v) || 1; return { x: v.x / l, y: v.y / l }; }

function fmtTime(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return m + ':' + (s < 10 ? '0' : '') + s;
}

/* ---------------------------------------------------------- 3. SEED RNG */
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = (a << 21) ^ a;
    t = (t + (t >> 14)) ^ t;
    t = (t + (t << 3)) ^ t;
    return ((t >> 16) >>> 0) / 4294967296;
  };
}

/* ---------------------------------------------------- 4. ASSET LOADER -- */
/*
   OPTIONAL asset pipeline: if real PNGs exist in assets/sprites/, they
   are loaded via <img> (works from file://). On any failure the game
   falls back to 100 % procedural Canvas rendering. The loader never
   blocks the menu.
*/
const ASSETS = {
  ready: false,
  sprites: {},   // name -> loaded HTMLImageElement
  _queue: [],
};

function loadAssets() {
  const paths = [
    'player', 'player_run', 'zombie', 'soldier', 'boss',
    'bullet', 'grenade', 'ammo', 'gren', 'health', 'coin', 'ammoBox',
  ];
  let loaded = 0;
  for (const name of paths) {
    const img = new Image();
    const p = 'assets/sprites/' + name + '.png';
    img.onload = function () { ASSETS.sprites[name] = img; count(); };
    img.onerror = function () { /* fallback procedural */ };
    img.src = p;
  }
  function count() { loaded++; if (loaded >= paths.length) ASSETS.ready = true; }
  // Safety timeout (images don't exist on file:// -> just never fire)
  setTimeout(function () { if (!ASSETS.ready) ASSETS.ready = true; }, 800);
}
function drawAsset(name, g, x, y, s, flash) {
  const im = ASSETS.sprites && ASSETS.sprites[name];
  if (im && im.complete && im.naturalWidth > 0) {
    g.drawImage(im, x - s / 2, y - s / 2, s, s);
    if (flash && flash > 0) {
      g.save();
      g.fillStyle = 'rgba(255,255,255,' + Math.min(flash, 1) + ')';
      g.fillRect(x - s / 2, y - s / 2, s, s);
      g.restore();
    }
    return true;
  }
  return false;
}
function drawAssetAlt(g, names, x, y, s, flash) {
  for (let i = 0; i < names.length; i++) {
    if (drawAsset(names[i], g, x, y, s, flash)) return true;
  }
  return false;
}

/* --------------------------------------------------------- 5. SOUND ---- */
/*
   All sounds are synthesized at runtime via WebAudio. No audio files.
   - noise buffer (1s) shared by gunshots / explosion / thumps
   - music: procedural dark ambient drone (detuned saws + lowpass +
     LFO + sparse pentatonic notes, 60 BPM-ish)
   - ctx created on first user gesture (autoplay policy)
*/
const SFX = {
  ctx: null, noise: null, musicOn: false, musicTimer: null,
  init: function () {
    if (SFX.ctx) return;
    try {
      SFX.ctx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) { return; }
    if (SFX.ctx.state === 'suspended') {
      SFX.ctx.resume().catch(function () {});
    }
    // noise buffer
    const sr = SFX.ctx.sampleRate, len = sr;
    const buf = SFX.ctx.createBuffer(1, len, sr);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    SFX.noise = buf;
  },
  noiseSrc: function () {
    const ctx = SFX.ctx;
    if (!ctx || !SFX.noise) return null;
    const s = ctx.createBufferSource();
    s.buffer = SFX.noise;
    s.loop = true;
    return s;
  },
  /* helper: play a noise burst with filter envelope */
  _noiseBurst: function (dur, freq, q, gIn, gOut) {
    const ctx = SFX.ctx;
    if (!ctx) return;
    const s = SFX.noiseSrc();
    if (!s) return;
    const f = ctx.createBiquadFilter();
    f.type = 'lowpass'; f.frequency.value = freq; f.Q.value = q;
    const g = ctx.createGain();
    const t = ctx.currentTime;
    g.gain.setValueAtTime(gIn, t);
    g.gain.exponentialRampToValueAtTime(gOut, t + dur);
    s.connect(f).connect(g).connect(ctx.destination);
    s.start(t); s.stop(t + dur + .1);
  },
  _tone: function (freq, dur, type, gIn, gOut, t0) {
    const ctx = SFX.ctx;
    if (!ctx) return;
    const t = t0 || ctx.currentTime;
    const o = ctx.createOscillator();
    o.type = type || 'sawtooth'; o.frequency.value = freq;
    const g = ctx.createGain();
    g.gain.setValueAtTime(gIn, t);
    g.gain.exponentialRampToValueAtTime(gOut, t + dur);
    o.connect(g).connect(ctx.destination);
    o.start(t); o.stop(t + dur + .05);
  },
  click: function () { SFX._tone(520, .06, 'square', .12, .0001); SFX._tone(784, .08, 'square', .08, .0001); },
  shotPistol: function () {
    SFX._noiseBurst(.08, 2600, .8, .55, .001);
    SFX._tone(180, .18, 'sawtooth', .18, .001);
  },
  shotRifle: function () {
    SFX._noiseBurst(.09, 2200, .8, .6, .001);
    SFX._tone(160, .14, 'sawtooth', .2, .001);
    SFX._noiseBurst(.07, 2400, .8, .35, .001); // echo-ish second
  },
  shotShotgun: function () {
    SFX._noiseBurst(.16, 900, 1.0, .8, .001);
    SFX._noiseBurst(.16, 2600, .8, .35, .001);
    SFX._tone(90, .35, 'sine', .3, .001);      // thump
  },
  /* enemy rifle bullet: sharp high "pew" so you hear it before it lands */
  enemyShot: function () {
    SFX._noiseBurst(.05, 3200, .7, .45, .001);
    SFX._tone(1500, .05, 'square', .14, .002);
  },
  throwGren: function () { SFX._tone(240, .22, 'triangle', .25, .001); SFX._noiseBurst(.2, 1500, .5, .25, .001); },
  explode: function () {
    SFX._noiseBurst(.5, 600, 1.0, .9, .001);
    SFX._noiseBurst(.45, 2200, .8, .4, .001);
    SFX._tone(55, .6, 'sine', .5, .001);       // sub thump
  },
  hit: function () { SFX._noiseBurst(.06, 1800, .8, .3, .001); },
  playerHit: function () { SFX._tone(220, .25, 'sawtooth', .25, .001); SFX._tone(160, .3, 'sine', .2, .001); },
  pickupAmmo: function () { SFX._tone(880, .08, 'square', .15, .001); SFX._tone(1320, .1, 'square', .15, .001); },
  pickupHealth: function () { SFX._tone(520, .15, 'triangle', .2, .001); SFX._tone(660, .18, 'triangle', .18, .001); SFX._tone(1040, .24, 'triangle', .18, .001); },
  pickupGold: function () { for (let i = 0; i < 3; i++) SFX._tone(780 + i * 196, .12, 'square', .18, .001); },
  pickupGren: function () { SFX._tone(340, .12, 'square', .18, .001); SFX._tone(440, .16, 'square', .15, .001); },
  waveHorn: function () {
    SFX.ctx && SFX.ctx.currentTime;
    const t = SFX.ctx.currentTime;
    SFX._tone(110, .7, 'sawtooth', .3, .001, t);
    SFX._tone(110 * 1.5, .7, 'sawtooth', .22, .001, t + .05);
    SFX._tone(220, .9, 'sawtooth', .2, .001, t + .1);
    SFX._noiseBurst(.3, 800, 1.0, .25, .001);
  },
  bossRoar: function () {
    const t = SFX.ctx.currentTime;
    SFX._tone(70, 1.4, 'sawtooth', .4, .001, t);
    SFX._tone(96, 1.2, 'sawtooth', .3, .001, t + .1);
    SFX._noiseBurst(1.0, 2400, .6, .35, .001, t);
    SFX._tone(140, .8, 'square', .2, .001, t + .4);
  },
  ui: function () { SFX._tone(440, .06, 'square', .12, .001); },
  /* music: dark ambient drone (persistent, stoppable) */
  _drone: null, _notes: null,
  musicStart: function () {
    if (SFX._drone || !SFX.ctx) return;
    const ctx = SFX.ctx, t = ctx.currentTime;
    const out = ctx.createGain(); out.gain.value = .07; out.connect(ctx.destination);
    const f = ctx.createBiquadFilter();
    f.type = 'lowpass'; f.frequency.value = 420; f.Q.value = .6; f.connect(out);
    const lf = ctx.createOscillator(); lf.type = 'sine'; lf.frequency.value = .07;
    const lg = ctx.createGain(); lg.gain.value = 220;
    lf.connect(lg).connect(f.frequency);
    const o1 = ctx.createOscillator(); o1.type = 'sawtooth'; o1.frequency.value = 110;
    const o2 = ctx.createOscillator(); o2.type = 'sawtooth'; o2.frequency.value = 110 * Math.pow(2, 7 / 1200);
    const g1 = ctx.createGain(); g1.gain.value = .5; g1.connect(f);
    const g2 = ctx.createGain(); g2.gain.value = .5; g2.connect(f);
    o1.connect(g1); o2.connect(g2);
    o1.start(); o2.start(); lf.start();
    SFX._drone = { out: out, o1: o1, o2: o2, lf: lf };
    SFX._notes = setInterval(function () {
      if (!SFX.ctx) return;
      if (Math.random() < .4) {
        const notes = [220, 261.6, 293.7, 349.2, 440, 523.3];
        SFX._tone(notes[irand(0, notes.length - 1)], irand(3, 12) * .18, 'triangle', .09, .001);
      }
    }, 560);
  },
  musicStop: function () {
    if (SFX._drone) {
      const d = SFX._drone, t = SFX.ctx.currentTime;
      d.out.gain.setValueAtTime(d.out.gain.value, t);
      d.out.gain.exponentialRampToValueAtTime(.0001, t + .5);
      d.o1.stop(t + .6); d.o2.stop(t + .6); d.lf.stop(t + .6);
      SFX._drone = null;
    }
    if (SFX._notes) { clearInterval(SFX._notes); SFX._notes = null; }
  }
};

/* ------------------------------------------------------- 6. PARTICLES -- */
/*
   Pooled particle array, capped. Kinds:
     'blood'   - dark red circles, gravity-ish
     'flash'   - muzzle flash, fast fade
     'spark'   - orange bits
     'smoke'   - grey circles, rise
     'boom'    - big orange/red radial explosion
     'glow'    - small bright dot
     'text'    - floating damage/score text (x,y,vy,s,txt,col)
*/
const PARTS = {
  arr: [],
  max: 400,
  spawn(x, y, vx, vy, life, col, kind, size) {
    const p = { x: x, y: y, vx: vx || 0, vy: vy || 0, life: life, l: life, col: col || '#fff', kind: kind || 'glow', s: size || 4 };
    if (PARTS.arr.length < PARTS.max) PARTS.arr.push(p);
    else { const i = irand(0, PARTS.arr.length - 1); PARTS.arr[i] = p; }
  },
  update(dt) {
    const g = 320;
    for (let i = PARTS.arr.length - 1; i >= 0; i--) {
      const p = PARTS.arr[i];
      p.life -= dt;
      if (p.life <= 0) { PARTS.arr.splice(i, 1); continue; }
      const t = p.life / p.l;
      if (p.kind === 'blood' || p.kind === 'spark' || p.kind === 'boom') p.vy += g * 0.6 * dt;
      if (p.kind === 'smoke') p.vy -= 40 * dt;
      if (p.kind === 'text') p.vy -= 60 * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
  },
  /* explosion cloud */
  boom(x, y, n, col, s) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * 6.283, v = rand(60, 400);
      PARTS.spawn(x, y, Math.cos(a) * v, Math.sin(a) * v, rand(.5, 1.2),
        Math.random() < .6 ? col : '#ff5533', 'boom', rand(3, 14));
    }
  },
  blood(x, y, n) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * 6.283, v = rand(40, 180);
      PARTS.spawn(x, y, Math.cos(a) * v, Math.sin(a) * v - 40, rand(.4, .9),
        Math.random() < .7 ? '#8b0000' : '#a41212', 'blood', rand(2, 5));
    }
  },
  flash(x, y, col, ang) {
    PARTS.spawn(x, y, Math.cos(ang) * 120, Math.sin(ang) * 120, .12, col || '#fff', 'flash', 8);
    PARTS.spawn(x, y, Math.cos(ang) * 80 + 20, Math.sin(ang) * 80, .1, '#ffffcc', 'flash', 6);
  },
  smoke(x, y, n, col) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * 6.283;
      PARTS.spawn(x, y, Math.cos(a) * 30, Math.sin(a) * 30 - 20, rand(1, 2.5), col || '#999', 'smoke', rand(6, 14));
    }
  },
  float(x, y, txt, col) {
    PARTS.spawn(x, y, -rand(20, 60), -rand(80, 140), 1, col || '#ffd94d', 'text', txt);
  },
  text(x, y, txt, col, life) {
    PARTS.spawn(x, y, -10, -30, life || 1.2, col || '#fff', 'text', txt);
  },
};

/* -------------------------------------------------------- 7. INPUT ----- */
const IN = {
  keys: {},
  mx: 0, my: 0, mb: [false, false, false],
  mclick: false,
  init: function () {
    const K = {
      W: 'W', A: 'A', S: 'S', D: 'D',
      ArrowUp: 'W', ArrowLeft: 'A', ArrowDown: 'S', ArrowRight: 'D',
    };
    window.addEventListener('keydown', function (e) {
      let k = K[e.key] || e.key;
      if (k.length === 1) k = k.toUpperCase();
      if (k) {
        IN.keys[k] = true;
        e.preventDefault();
        IN.onKey(k);
      }
      if (e.key === ' ' || e.key === 'q' || e.key === 'Q' ||
          e.key === '1' || e.key === '2' || e.key === '3' ||
          e.key === 'p' || e.key === 'P' || e.key === 'r' || e.key === 'R') {
        e.preventDefault();
      }
    }, { passive: false });
    window.addEventListener('keyup', function (e) {
      let k = K[e.key] || e.key;
      if (k.length === 1) k = k.toUpperCase();
      if (k) IN.keys[k] = false;
    }, { passive: false });
    window.addEventListener('mousedown', function (e) {
      IN.mb[e.button] = true;
      if (e.button === 0) IN.mclick = true;
    }, { passive: false });
    window.addEventListener('mouseup', function (e) {
      IN.mb[e.button] = false;
    }, { passive: false });
    window.addEventListener('mousemove', function (e) {
      const r = $('game').getBoundingClientRect();
      IN.mx = (e.clientX - r.left) * (C.w / r.width);
      IN.my = (e.clientY - r.top) * (C.h / r.height);
    }, { passive: true });
    window.addEventListener('wheel', function (e) { e.preventDefault(); }, { passive: false });
    window.addEventListener('contextmenu', function (e) { e.preventDefault(); }, { passive: false });
  },
  /* player + world coords from mouse (set after camera update) */
  setMouse: function (x, y) { IN.mx = x; IN.my = y; },
  /* per-key callback for one-shot actions (fire, grenade, pause, restart) */
  onKey: function (k) {}
};

/* ------------------------------------------------------ 8. CAMERA ----- */
const CAM = {
  x: 0, y: 0,
  shake: 0, shakeMax: 14, shakeDecay: 6,
  /* follow a target (player), clamp to world */
  follow: function (x, y) {
    const tx = x - C.w / 2, ty = y - C.h / 2;
    this.x = lerp(this.x, tx, .12);
    this.y = lerp(this.y, ty, .12);
    /* clamp */
    this.x = clamp(this.x, 0, W.w - C.w);
    this.y = clamp(this.y, 0, W.h - C.h);
  },
  /* world -> screen */
  wx: function (x) { return x - this.x; },
  wy: function (y) { return y - this.y; },
  /* screen -> world (for mouse) */
  swx: function (x) { return x + this.x; },
  swy: function (y) { return y + this.y; },
  addShake: function (a) { this.shake = clamp(a + this.shake, 0, this.shakeMax); },
  tick: function (dt) {
    this.shake *= Math.max(0, 1 - this.shakeDecay * dt);
    if (this.shake < 1) this.shake = 0;
  },
  /* per-frame random jitter vector (call once per frame after tick) */
  offset: function (g) {
    g.save();
    if (this.shake > 0.5) {
      const sx = (Math.random() - .5) * this.shake * 2;
      const sy = (Math.random() - .5) * this.shake * 2;
      g.translate(sx, sy);
    }
  },
  restore: function (g) { g.restore(); },
};

/* -------------------------------------------------------- 9. WORLD ---- */
/*
   World: 2000x1200 post-apocalyptic village. Two roads cross at the
   centre (vertical x:930-1070, horizontal y:530-670). 6 ruined houses,
   trees, barrels, crates, fences, car wrecks, rubble. Static layer is
   pre-rendered once to an offscreen canvas -> per-frame we only draw
   that once with an offset.
*/
const WORLD = {
  staticCv: null,
  objs: [],      // {x,y,w,h,solid,type,rot?}
  spawnPts: [],  // [N,S,E,W] edges
  playerSpawn: { x: 1000, y: 600 },

  init: function () {
    this.objs = [];
    /* ruined houses (solid) */
    [[150, 120, 260, 190], [600, 90, 240, 170], [1340, 70, 260, 200],
     [1500, 700, 240, 170], [700, 860, 260, 190], [1300, 900, 240, 180],
     [250, 520, 200, 140], [1550, 140, 190, 130]]
      .forEach(function (a) { this.objs.push({ x: a[0], y: a[1], w: a[2], h: a[3], solid: true, type: 'house' }); }, this);
    /* trees (circle collision approx by AABB, drawn as tree) */
    [[450, 460, 90, 90], [1250, 410, 100, 100], [290, 740, 90, 90],
     [1710, 600, 95, 95], [500, 1050, 85, 85], [1610, 1010, 85, 85],
     [900, 150, 75, 75], [1150, 1030, 75, 75]]
      .forEach(function (a) { this.objs.push({ x: a[0], y: a[1], w: a[2], h: a[3], solid: true, type: 'tree' }); }, this);
    /* barrels & crates (solid) */
    [[500, 500, 26, 26], [1100, 520, 26, 26], [470, 900, 26, 26],
     [1490, 500, 30, 30], [560, 300, 30, 30], [1750, 420, 28, 28],
     [60, 300, 28, 28], [950, 1050, 30, 30]]
      .forEach(function (a, i) { this.objs.push({ x: a[0], y: a[1], w: a[2], h: a[3], solid: true, type: 'barrel' }); }, this);
    /* car wrecks (solid) */
    [[320, 340, 180, 70], [1620, 840, 180, 70], [80, 940, 180, 70],
     [1450, 280, 160, 65]]
      .forEach(function (a) { this.objs.push({ x: a[0], y: a[1], w: a[2], h: a[3], solid: true, type: 'car' }); }, this);
    /* rubble piles (solid) */
    [[800, 240, 90, 60], [1190, 900, 100, 70], [350, 600, 80, 50]]
      .forEach(function (a) { this.objs.push({ x: a[0], y: a[1], w: a[2], h: a[3], solid: true, type: 'rubble' }); }, this);
    /* fences (thin, solid) */
    [[150, 340, 220, 12], [420, 340, 12, 160], [1480, 280, 220, 12],
     [1350, 280, 12, 150], [500, 1050, 12, 180], [500, 1050, 180, 12]]
      .forEach(function (a) { this.objs.push({ x: a[0], y: a[1], w: a[2], h: a[3], solid: true, type: 'fence' }); }, this);

    /* spawn points at edges (slightly inside) */
    this.spawnPts = [
      { x: 1000, y: 40 },        { x: 1000, y: W.h - 40 },
      { x: 40, y: 600 },        { x: W.w - 40, y: 600 },
    ];

    this.preRender();
  },

  /* nearest solid AABB push-out for a circle; returns {x,y} */
  resolveCircle: function (cx, cy, r, maxIter) {
    let x = cx, y = cy, iters = maxIter || 3;
    while (iters-- > 0) {
      let pushed = false;
      for (let i = 0; i < this.objs.length; i++) {
        const o = this.objs[i];
        if (!o.solid) continue;
        const nx = clamp(x, o.x, o.x + o.w);
        const ny = clamp(y, o.y, o.y + o.h);
        const dx = nx - x, dy = ny - y;
        const d2 = dx * dx + dy * dy;
        if (d2 <= r * r) {
          if (dx === 0 && dy === 0) {
            /* circle centre inside the box: push out toward nearest face */
            const left = x - o.x, right = (o.x + o.w) - x;
            const top = y - o.y, bottom = (o.y + o.h) - y;
            const m = Math.min(left, right, top, bottom);
            if (m === left) x = o.x - r;
            else if (m === right) x = o.x + o.w + r;
            else if (m === top) y = o.y - r;
            else y = o.y + o.h + r;
          } else if (Math.abs(dx) >= Math.abs(dy)) {
            /* horizontal penetration: push along X */
            if (dx < 0) x = o.x + o.w + r;
            else if (dx > 0) x = o.x - r;
          } else {
            /* vertical penetration: push along Y */
            if (dy < 0) y = o.y + o.h + r;
            else if (dy > 0) y = o.y - r;
          }
          pushed = true;
        }
      }
      if (!pushed) break;
    }
    return { x: x, y: y };
  },

  /* pre-render the whole static world onto an offscreen canvas */
  preRender: function () {
    const cv = document.createElement('canvas');
    cv.width = W.w; cv.height = W.h;
    const g = cv.getContext('2d');
    this.staticCv = cv;
    const srnd = mulberry32(1337);

    /* ground */
    g.fillStyle = '#2e2a1e';
    g.fillRect(0, 0, W.w, W.h);
    /* dirt / grass noise */
    for (let i = 0; i < 9000; i++) {
      const x = srnd() * W.w, y = srnd() * W.h;
      const v = srnd();
      g.fillStyle = v < .5 ? '#33301f' : '#27241a';
      g.fillRect(x, y, 1 + Math.floor(srnd() * 2), 1 + Math.floor(srnd() * 2));
    }
    /* grass tufts (sparse) */
    g.strokeStyle = '#4a5530';
    for (let i = 0; i < 1400; i++) {
      const x = srnd() * W.w, y = srnd() * W.h;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + 3, y - 5); g.stroke();
    }
    /* roads */
    this.drawRoads(g, srnd);
    /* static objects (drawn with their own shadows first) */
    for (let i = 0; i < this.objs.length; i++) this.drawObj(g, this.objs[i], srnd);
  },

  drawRoads: function (g, srnd) {
    const VW = 140, VH = 140;
    /* asphalt */
    g.fillStyle = '#252220';
    g.fillRect(930, 0, VW, W.h);
    g.fillRect(0, 530, W.w, VH);
    /* crack lines */
    g.strokeStyle = '#1b1917'; g.lineWidth = 2;
    for (let i = 0; i < 60; i++) {
      const a = srnd() * 6.283, x = 930 + srnd() * VW, y = srnd() * W.h * .9 + 50;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * 24, y + Math.sin(a) * 24); g.stroke();
    }
    /* dashed lines */
    g.fillStyle = '#5a5550';
    for (let y = 40; y < W.h; y += 90) { g.fillRect(990, y, 24, 34); }
    for (let x = 40; x < W.w; x += 90) { g.fillRect(x, 585, 34, 24); }
    /* oil stains */
    g.fillStyle = 'rgba(10,14,10,.35)';
    for (let i = 0; i < 8; i++) {
      const x = srnd() * W.w, y = srnd() * W.h;
      g.beginPath(); g.ellipse(x, y, 40 + srnd() * 60, 25 + srnd() * 30, srnd() * 3, 0, 6.283); g.fill();
    }
  },
  drawObj: function (g, o, srnd) {
    const cx = o.x + o.w / 2, cy = o.y + o.h / 2;
    /* drop shadow */
    g.fillStyle = 'rgba(0,0,0,.3)';
    g.fillRect(cx - o.w / 2 - 6, cy + o.h / 2 - 4, o.w + 12, 8);

    switch (o.type) {
      case 'house': this.drawHouse(g, o, srnd); break;
      case 'tree':  this.drawTree(g, o, srnd); break;
      case 'barrel': this.drawBarrel(g, o, srnd); break;
      case 'car':   this.drawCar(g, o, srnd); break;
      case 'rubble': this.drawRubble(g, o, srnd); break;
      case 'fence': this.drawFence(g, o, srnd); break;
    }
  },
  drawHouse: function (g, o, srnd) {
    const w = o.w, h = o.h;
    g.fillStyle = '#6f6250';
    g.fillRect(o.x, o.y, w, h);
    g.fillStyle = '#5a4e3e'; g.fillRect(o.x, o.y, w, 10);
    /* broken roof */
    g.fillStyle = '#4a3f2e';
    g.fillRect(o.x, o.y, w, 22);
    for (let i = 0; i < 3; i++) {
      const rx = srnd() * w, rw = 40 + srnd() * 50;
      g.fillStyle = '#55483a';
      g.beginPath(); g.moveTo(rx, o.y - 10); g.lineTo(rx + rw, o.y - 2); g.lineTo(rx + rw, o.y); g.lineTo(rx, o.y); g.fill();
    }
    /* broken windows */
    g.fillStyle = '#1b1813';
    const wx = w / 4;
    for (let i = 0; i < 3; i++) {
      g.fillRect(o.x + wx * i + 18, o.y + 30, wx - 30, 55);
      g.fillStyle = 'rgba(255,255,255,.08)';
      g.fillRect(o.x + wx * i + 18, o.y + 30, wx - 30, 4);
      g.fillStyle = 'rgba(255,255,255,.08)';
      g.fillRect(o.x + wx * i + wx / 2, o.y + 30, 2, 55);
    }
    /* door */
    g.fillStyle = '#3a3020';
    g.fillRect(o.x + w / 2 - 20, o.y + h - 50, 40, 50);
    g.fillStyle = '#2a2318'; g.fillRect(o.x + w / 2 + 8, o.y + h - 40, 3, 3);
    /* rubble in front */
    g.fillStyle = '#5a4e3e';
    for (let i = 0; i < 6; i++) g.fillRect(o.x + srnd() * w, o.y + h - 14 + srnd() * 10, 12 + srnd() * 18, 8 + srnd() * 6);
  },
  drawTree: function (g, o, srnd) {
    const cx = o.x + o.w / 2, cy = o.y + o.h / 2;
    g.fillStyle = '#3a2a1a';
    g.fillRect(cx - 7, cy - 15, 14, 55);
    g.fillStyle = '#2e2418';
    for (let i = 0; i < 4; i++) {
      const a = srnd() * 6.283, r = 35 + srnd() * 25;
      g.beginPath(); g.ellipse(cx + Math.cos(a) * r * .6, cy - 20 + Math.sin(a) * r * .5, 30 + srnd() * 25, 22 + srnd() * 18, a, 0, 6.283); g.fill();
    }
  },
  drawBarrel: function (g, o, srnd) {
    const cx = o.x + o.w / 2, cy = o.y + o.h / 2;
    g.fillStyle = '#4a3a26';
    g.beginPath(); g.ellipse(cx, cy, o.w / 2 - 2, o.h / 2 - 2, 0, 0, 6.283); g.fill();
    g.fillStyle = srnd() < .5 ? '#8b5a26' : '#6a4520';
    g.beginPath(); g.ellipse(cx, cy - 4, o.w / 2 - 8, o.h / 2 - 8, 0, 0, 6.283); g.fill();
    g.strokeStyle = 'rgba(0,0,0,.4)'; g.stroke();
  },
  drawCar: function (g, o, srnd) {
    g.fillStyle = '#3d3328';
    g.fillRect(o.x, o.y, o.w, o.h);
    g.fillStyle = '#4a3f30';
    g.fillRect(o.x + 8, o.y + 8, o.w - 16, o.h - 16);
    g.fillStyle = '#1f1c18';
    g.fillRect(o.x + 20, o.y + o.h - 16, (o.w - 40) / 2, 16);
    g.fillRect(o.x + o.w - 20 - (o.w - 40) / 2, o.y + o.h - 16, (o.w - 40) / 2, 16);
    g.fillStyle = '#5a4530';
    for (let i = 0; i < 8; i++) {
      g.fillStyle = srnd() < .5 ? '#5a4530' : '#4a3828';
      g.fillRect(o.x + srnd() * (o.w - 10), o.y + srnd() * (o.h - 10), 4 + srnd() * 10, 4 + srnd() * 6);
    }
  },
  drawRubble: function (g, o, srnd) {
    g.fillStyle = '#5a4e3e';
    for (let i = 0; i < 10; i++) {
      const x = o.x + srnd() * o.w, y = o.y + srnd() * o.h, w = 10 + srnd() * 24, h = 8 + srnd() * 14;
      g.fillStyle = srnd() < .5 ? '#5a4e3e' : '#6a5e48';
      g.fillRect(x, y, w, h);
    }
  },
  drawFence: function (g, o, srnd) {
    g.fillStyle = '#4a3f2e';
    if (o.w > o.h) {
      g.fillRect(o.x, o.y, o.w, o.h);
      for (let x = o.x; x <= o.x + o.w; x += 40) {
        g.fillStyle = '#5a4e38'; g.fillRect(x - 3, o.y - 4, 6, o.h + 8);
      }
    } else {
      g.fillRect(o.x, o.y, o.w, o.h);
      for (let y = o.y; y <= o.y + o.h; y += 40) {
        g.fillStyle = '#5a4e38'; g.fillRect(o.x - 4, y - 3, o.w + 8, 6);
      }
    }
  },
};

/* =========================================================== PATH (A*) -- */
const PATH = {
  CS: 20,
  gridW: 0, gridH: 0,
  cells: null,
  DRX: [0, 1, 0, -1, 1, 1, -1, -1],
  DRY: [1, 0, -1, 0, 1, -1, 1, -1],
  heap: { a: [] },
  heapPush: function (e) {
    const h = PATH.heap; h.a.push(e);
    let i = h.a.length - 1;
    while (i > 0) { const p = (i - 1) >> 1; if (h.a[p].f <= h.a[i].f) break; [h.a[p], h.a[i]] = [h.a[i], h.a[p]]; i = p; }
  },
  heapPop: function () {
    const h = PATH.heap; if (!h.a.length) return null;
    const top = h.a[0]; const last = h.a.pop();
    if (h.a.length) { h.a[0] = last; let i = 0, n = h.a.length; for (;;) {
      let l = (i + 1) << 1, r = l + 1, m = l;
      if (r < n && h.a[r].f < h.a[l].f) m = r;
      if (m < n && h.a[m].f < h.a[i].f) { [h.a[m], h.a[i]] = [h.a[i], h.a[m]]; i = m; } else break;
    } }
    return top;
  },
  /* build the walkable grid once, after WORLD.init() */
  build: function () {
    this.CS = 20;
    this.gridW = Math.ceil(W.w / this.CS);
    this.gridH = Math.ceil(W.h / this.CS);
    const N = this.gridW * this.gridH;
    this.cells = new Uint8Array(N);
    const r = 14; /* effective radius for pathing (resolveCircle is the safety net) */
    for (let i = 0; i < WORLD.objs.length; i++) {
      const o = WORLD.objs[i];
      if (!o.solid) continue;
      const ox = o.x - r, oy = o.y - r, ow = o.w + 2 * r, oh = o.h + 2 * r;
      const cx0 = Math.max(0, Math.floor(ox / this.CS));
      const cx1 = Math.min(this.gridW - 1, Math.floor((ox + ow) / this.CS));
      const cy0 = Math.max(0, Math.floor(oy / this.CS));
      const cy1 = Math.min(this.gridH - 1, Math.floor((oy + oh) / this.CS));
      for (let cy = cy0; cy <= cy1; cy++) {
        for (let cx = cx0; cx <= cx1; cx++) {
          const cxc = cx * this.CS + this.CS / 2;
          const cyc = cy * this.CS + this.CS / 2;
          if (cxc > ox && cxc < ox + ow && cyc > oy && cyc < oy + oh) {
            this.cells[cy * this.gridW + cx] = 1;
          }
        }
      }
    }
  },
  /* world -> cell */
  cell: function (x, y) {
    let cx = Math.floor(x / this.CS), cy = Math.floor(y / this.CS);
    if (cx < 0) cx = 0; if (cx >= this.gridW) cx = this.gridW - 1;
    if (cy < 0) cy = 0; if (cy >= this.gridH) cy = this.gridH - 1;
    return { cx: cx, cy: cy, i: cy * this.gridW + cx };
  },
  /* cell -> world centre */
  cellW: function (c) { return { x: c.cx * this.CS + this.CS / 2, y: c.cy * this.CS + this.CS / 2 }; },
  /* nearest walkable cell to (x,y) */
  nearestWalkable: function (x, y) {
    const c = this.cell(x, y);
    if (!this.cells[c.i]) return c;
    const gW = this.gridW, gH = this.gridH, q = [c.i], seen = new Uint8Array(this.gridW * this.gridH);
    seen[c.i] = 1;
    for (let qi = 0; qi < q.length; qi++) {
      const i = q[qi], cx = i % gW, cy = (i / gW) | 0;
      for (let d = 0; d < 4; d++) {
        const nx = cx + this.DRX[d], ny = cy + this.DRY[d];
        if (nx < 0 || nx >= gW || ny < 0 || ny >= gH) continue;
        const ni = ny * gW + nx;
        if (seen[ni] || this.cells[ni]) continue;
        seen[ni] = 1; q.push(ni);
      }
    }
    for (let k = 1; k < q.length; k++) {
      if (!this.cells[q[k]]) { const i = q[k]; return { cx: i % gW, cy: (i / gW) | 0, i: i }; }
    }
    return c;
  },
  /* A*: returns array of cells [{cx,cy,i}, ...] from start to (nearest walkable to) goal, or null */
  pathfind: function (sx, sy, gx, gy) {
    const sc = this.cell(sx, sy), gc = this.cell(gx, gy);
    if (this.cells[sc.i]) return null;
    const goal = this.nearestWalkable(gx, gy);
    const gW = this.gridW, gH = this.gridH, N = gW * gH;
    if (this.cells[goal.i]) return null;
    if (sc.i === goal.i) return [{ cx: sc.cx, cy: sc.cy, i: sc.i }];
    const INF = 1e9, g = new Array(N).fill(INF), came = new Array(N).fill(-1);
    PATH.heap.a = [];
    const h = function (cx, cy) { return Math.abs(cx - goal.cx) + Math.abs(cy - goal.cy); };
    g[sc.i] = 0;
    PATH.heapPush({ i: sc.i, f: h(sc.cx, sc.cy) });
    const SQ = Math.SQRT2;
    while (PATH.heap.a.length) {
      const top = PATH.heapPop(), i = top.i, cx = i % gW, cy = (i / gW) | 0;
      if (i === goal.i) {
        const path = []; let cur = i;
        while (cur !== -1) { path.push({ cx: cur % gW, cy: (cur / gW) | 0, i: cur }); cur = came[cur]; }
        path.reverse();
        return path;
      }
      for (let d = 0; d < 8; d++) {
        const nx = cx + this.DRX[d], ny = cy + this.DRY[d];
        if (nx < 0 || nx >= gW || ny < 0 || ny >= gH) continue;
        const ni = ny * gW + nx;
        if (this.cells[ni]) continue;
        if (d >= 4) { /* don't cut diagonal corners */
          const sx2 = this.DRX[d] > 0 ? 1 : -1, sy2 = this.DRY[d] > 0 ? 1 : -1;
          const c1 = cy * gW + (cx + sx2), c2 = (cy + sy2) * gW + cx;
          if (this.cells[c1] || this.cells[c2]) continue;
        }
        const ng = g[i] + (d < 4 ? 1 : SQ);
        if (ng < g[ni]) {
          came[ni] = i; g[ni] = ng;
          PATH.heapPush({ i: ni, f: ng + h(nx, ny) });
        }
      }
    }
    return null;
  },
};

/* ---------------------------------------------------------- 10. PLAYER  */
const P = {
  x: 0, y: 0,
  hp: 100, maxHp: 100,
  aimX: 0, aimY: 0,      // mouse in world coords
  radius: 16,
  speed: 150,
  sprint: { active: false, t: 0, recover: 0 },
  regen: { lastHit: -99 },
  weapon: 0,             // index into CFG.weapons
  mag: 10,               // current mag
  reloadT: 0,
  fireT: 0,              // time since last shot
  grenCount: 4, grenCd: 0,
  hitFlash: 0, healGlow: 0,
  deathT: 0, dead: false,
  bob: 0,               // walk animation phase
  anim: { move: 0, shoot: 0, throw: 0 },
  inv: 0,               // invulnerability frames after big hit
  init: function () {
    const p = CFG.player;
    this.x = WORLD.playerSpawn.x; this.y = WORLD.playerSpawn.y;
    this.hp = p.maxHp;
    this.sprint = { active: false, t: 0, recover: 0 };
    this.regen = { lastHit: -99 };
    this.weapon = 0;
    this.mag = CFG.weapons[0].mag;
    this.fireT = 0; this.reloadT = 0;
    this.grenCount = CFG.grenade.count; this.grenCd = 0;
    this.hitFlash = 0; this.healGlow = 0;
    this.dead = false; this.deathT = 0;
    this.bob = 0;
    this.anim = { move: 0, shoot: 0, throw: 0 };
    this.inv = 0;
  },
  /* input-driven movement + aim */
  update(dt, mouse, keys, sfx) {
    if (this.dead) { this.deathT += dt; return; }
    const p = CFG.player;
    /* movement */
    const vx = (keys.A ? -1 : 0) + (keys.D ? 1 : 0);
    const vy = (keys.W ? -1 : 0) + (keys.S ? 1 : 0);
    let mv = (vx || vy) ? vecLen({ x: vx, y: vy }) : 0;
    let spd = p.speed;
    /* sprint */
    if (keys.Q && !this.sprint.active && this.sprint.recover <= 0 && (vx || vy)) {
      this.sprint.active = true; this.sprint.t = p.sprintTime;
    }
    if (this.sprint.active) {
      this.sprint.t -= dt;
      spd *= p.sprintMult;
      if (this.sprint.t <= 0) { this.sprint.active = false; this.sprint.recover = p.sprintRecover; }
    }
    if (this.sprint.recover > 0) this.sprint.recover -= dt;
    if (mv > 0.5) {
      const n = vecNorm({ x: vx / mv, y: vy / mv });
      this.x += n.x * spd * dt;
      this.y += n.y * spd * dt;
      this.bob = (this.bob + spd * dt * .02) % 6.283;
    }
    /* resolve vs world (solid AABB push-out) + world bounds */
    const res = WORLD.resolveCircle(this.x, this.y, this.radius, 3);
    this.x = res.x; this.y = res.y;
    this.x = clamp(this.x, this.radius, W.w - this.radius);
    this.y = clamp(this.y, this.radius, W.h - this.radius);
    /* aim follows mouse */
    const mxw = CAM.swx(mouse.x), myw = CAM.swy(mouse.y);
    this.aimX = mxw; this.aimY = myw;
    /* regen */
    if (this.hp < this.maxHp && (performance.now() / 1000 - this.regen.lastHit) > p.regenDelay) {
      const regen = Math.min(p.regen * dt, this.maxHp - this.hp);
      if (regen > 0) this.hp += regen;
    }
    this.hp = clamp(this.hp, 0, this.maxHp);
    if (this.hp <= 0) { this.dead = true; }
    this.hitFlash = Math.max(0, this.hitFlash - dt * 4);
    this.healGlow = Math.max(0, this.healGlow - dt * 2);
    this.inv = Math.max(0, this.inv - dt);
    this.anim.move = Math.min(1, this.anim.move + (mv ? dt * 6 : dt * 8));
    this.anim.shoot = Math.max(0, this.anim.shoot - dt * 4);
    this.anim.throw = Math.max(0, this.anim.throw - dt * 3);
    if (this.fireT > 0) this.fireT -= dt;
    if (this.reloadT > 0) this.reloadT -= dt;
    this.grenCd = Math.max(0, this.grenCd - dt);
  },
  shoot: function (sfx) {
    if (this.dead) return false;
    const w = CFG.weapons[this.weapon];
    if (!this.mag) {
      this.mag = w.mag;
      return false;
    }
    const mx = this.aimX - this.x, my = this.aimY - this.y;
    const d = Math.hypot(mx, my) || 1;
    const cos = mx / d, sin = my / d;
    for (let i = 0; i < w.pellets; i++) {
      const a = Math.atan2(sin, cos) + (i === 0 ? 0 : (Math.random() - .5) * w.spread);
      const bx = this.x + cos * (this.radius + 14);
      const by = this.y + sin * (this.radius + 14);
      PROJ.add(bx, by, a, {
        dmg: w.dmg, range: w.range,
        vx: Math.cos(a) * 900, vy: Math.sin(a) * 900,
        kind: 'bullet', magCost: 1,
      });
      PARTS.flash(bx, by, '#fff', a);
      if (w.pellets === 1) {
        SFX.shotPistol();
      } else if (this.weapon === 1) {
        SFX.shotRifle();
      } else {
        SFX.shotShotgun();
      }
    }
    this.mag -= w.pellets > 1 ? w.pellets : 1;
    this.fireT = w.rate;
    this.anim.shoot = 1;
    return true;
  },
  throwGrenade: function (sfx) {
    if (this.dead || this.grenCount <= 0 || this.grenCd > 0) return;
    this.grenCd = CFG.grenade.cooldown;
    const mx = this.aimX - this.x, my = this.aimY - this.y;
    const d = Math.hypot(mx, my) || 1;
    const a = Math.atan2(my / d, mx / d);
    const tx = clamp(this.x + Math.cos(a) * CFG.grenade.throwR, 40, W.w - 40);
    const ty = clamp(this.y + Math.sin(a) * CFG.grenade.throwR, 40, W.h - 40);
    PROJ.add(this.x, this.y, a, {
      kind: 'grenade',
      vx: 0, vy: 0,
      targetX: tx, targetY: ty,
      fuse: CFG.grenade.fuse,
      blastR: CFG.grenade.blastR, blastDmg: CFG.grenade.blastDmg,
    });
    this.grenCount--;
    this.anim.throw = 1;
    SFX.throwGren();
  },
  takeHit: function (dmg) {
    if (this.dead) return;
    this.hp -= dmg;
    this.regen.lastHit = performance.now() / 1000;
    this.inv = .3;
    this.hitFlash = 1;
    SFX.playerHit();
    CAM.addShake(5 + dmg * .15);
    PARTS.blood(this.x, this.y, 4);
    if (this.hp <= 0) { this.dead = true; this.deathT = 0; }
  },
  heal: function (amt, sfx) {
    if (this.dead) return;
    this.hp = clamp(this.hp + amt, 0, this.maxHp);
    this.healGlow = 1;
  },
  addAmmo: function (amt, sfx) {
    this.mag = clamp(this.mag + amt, 0, CFG.ammoMax);
  },
  addGren: function (amt) {
    this.grenCount = clamp(this.grenCount + amt, 0, CFG.grenade.maxCount);
  },
};

/* ---------------------------------------------------------- 11. ENEMIES  */
const ENEMY = {
  arr: [],
  add: function (type, x, y, opts) {
    const e = {
      type: type, x: x, y: y,
      hp: 0, maxHp: 0,
      spd: 0, dmg: 0, meleeR: 20,
      range: 0, rate: 2.2,
      aimX: 0, aimY: 0,
      hitFlash: 0, dead: false, deathT: 0,
      atkT: rand(0.5, 2),   /* attack cooldown */
      muzzleFlash: 0,
      lunge: 0, lungeT: 0, /* lunge windup */
      walkT: Math.random() * 6.283,
      bob: 0,
      score: 100,
      /* pathfinding */
      path: null, pathI: 0,
      pathX: 0, pathY: 0, pathPX: 0, pathPY: 0, pathT: 0,
      wantedMove: false, stuck: false,
      ideal: 280,
    };
    const c = CFG.enemies[type];
    e.hp = e.maxHp = c.hp;
    e.spd = c.spd * CFG.enemyBaseSpeed;
    e.dmg = c.dmg;
    e.meleeR = c.meleeR;
    e.range = c.range || 320;
    e.score = c.score;
    if (opts) {
      if (opts.speedMult) e.spd *= opts.speedMult;
    }
    if (type === 'soldier') e.ideal = 260 + rand(0, 40);
    if (type === 'bossw') { e.grenT = 4; e.grenCount = 3; e.spawnCd = 8; e.spawnCount = 2; }
    ENEMY.arr.push(e);
    return e;
  },
  /* circle-circle separation */
  separate: function () {
    for (let i = 0; i < this.arr.length; i++) {
      const a = this.arr[i];
      if (a.dead) continue;
      for (let j = i + 1; j < this.arr.length; j++) {
        const b = this.arr[j];
        if (b.dead) continue;
        const dx = a.x - b.x, dy = a.y - b.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < (a.meleeR + b.meleeR) * (a.meleeR + b.meleeR)) {
          const d = Math.sqrt(d2) || 1;
          const nx = dx / d, ny = dy / d;
          const push = (a.meleeR + b.meleeR) / 2 - d / 2;
          if (push > 0) {
            a.x += nx * push; a.y += ny * push;
            b.x -= nx * push; b.y -= ny * push;
          }
        }
      }
    }
  },
  /* ---- pathfinding (A*) helpers ---- */
  needPath: function (e) {
    if (!e.path) return true;
    if (e.pathI >= e.path.length - 1) return true;
    if (dist(P.x, P.y, e.pathPX, e.pathPY) > 60) return true;
    if (e.pathT > 0.5) return true;
    return false;
  },
  ensurePath: function (e, dt) {
    e.pathT = (e.pathT || 0) + dt;
    if (ENEMY.needPath(e)) {
      e.pathX = e.x; e.pathY = e.y; e.pathPX = P.x; e.pathPY = P.y;
      e.pathT = 0;
      const p = PATH.pathfind(e.x, e.y, P.x, P.y);
      if (p) { e.path = p.map(function (c) { return PATH.cellW(c); }); e.pathI = 0; }
      else { e.path = null; e.pathI = 0; }
    }
  },
  moveAlong: function (e, dt, factor) {
    if (e.path && e.pathI < e.path.length) {
      const w = e.path[e.pathI];
      const tx = w.x - e.x, ty = w.y - e.y;
      const td = Math.hypot(tx, ty) || 1;
      e.x += (tx / td) * e.spd * factor * dt;
      e.y += (ty / td) * e.spd * factor * dt;
      if (td < 24) e.pathI++;
    } else {
      /* no path / path exhausted: go straight at player (fallback) */
      const dxp = P.x - e.x, dyp = P.y - e.y;
      const dp = Math.hypot(dxp, dyp) || 1;
      e.x += (dxp / dp) * e.spd * factor * dt;
      e.y += (dyp / dp) * e.spd * factor * dt;
    }
  },
  backOff: function (e, dt, factor) {
    const dxp = P.x - e.x, dyp = P.y - e.y;
    const dp = Math.hypot(dxp, dyp) || 1;
    e.x -= (dxp / dp) * e.spd * factor * dt;
    e.y -= (dyp / dp) * e.spd * factor * dt;
  },
  update: function (dt, sfx) {
    for (let i = this.arr.length - 1; i >= 0; i--) {
      const e = this.arr[i];
      if (e.dead) { e.deathT += dt; continue; }
      e.walkT = (e.walkT + dt * 8) % 6.283;
      e.hitFlash = Math.max(0, e.hitFlash - dt * 4);
      e.muzzleFlash = Math.max(0, e.muzzleFlash - dt * 5);
      /* aim at player */
      e.aimX = P.x; e.aimY = P.y;
      const dx = P.x - e.x, dy = P.y - e.y;
      const d = Math.hypot(dx, dy) || 1;
      const na = Math.atan2(dy, dx);
      const nx = Math.cos(na), ny = Math.sin(na);

      switch (e.type) {
        case 'zombie': {
          e.atkT -= dt;
          ENEMY.ensurePath(e, dt);
          if (d > 40) {
            ENEMY.moveAlong(e, dt, 1.0);
            e.bob += e.spd * dt * .018;
          } else {
            e.bob += e.spd * dt * .01;
          }
          if (e.atkT <= 0 && d < 40) {
            P.takeHit(e.dmg, sfx);
            e.atkT = 2.5;
            PARTS.blood(P.x, P.y, 3);
          }
          break;
        }
        case 'soldier': {
          e.atkT -= dt;
          ENEMY.ensurePath(e, dt);
          if (d > e.ideal) { ENEMY.moveAlong(e, dt, 1.0); e.bob += e.spd * dt * .02; }
          else if (d < e.ideal - 80) { ENEMY.backOff(e, dt, 0.6); e.bob += e.spd * dt * .015; }
          else { ENEMY.moveAlong(e, dt, 0.25); e.bob += e.spd * dt * .01; }
          /* shoot with LOS check */
          if (d < e.range + 20 && e.atkT <= 0 && P.inv <= 0) {
            if (ENEMY.losOk(e)) {
              PROJ.fireAtPlayer(e.x, e.y, e.dmg);
              e.muzzleFlash = 1;
              SFX.enemyShot();
              e.atkT = e.rate;
            } else {
              e.atkT = 0.6;
            }
          }
          break;
        }
        case 'bossz': case 'bossw': {
          e.atkT -= dt;
          ENEMY.ensurePath(e, dt);
          if (e.type === 'bossw' && e.grenT !== undefined) {
            e.grenT -= dt;
            if (e.grenT <= 0 && e.grenCount > 0) {
              e.grenCount--;
              const a = na;
              PROJ.add(e.x + Math.cos(a) * 30, e.y + Math.sin(a) * 30, a, {
                kind: 'grenade', vx: 0, vy: 0,
                targetX: clamp(e.x + Math.cos(a) * 200, 40, W.w - 40),
                targetY: clamp(e.y + Math.sin(a) * 200, 40, W.h - 40),
                fuse: 1.6, blastR: 90, blastDmg: 60,
              });
              SFX.throwGren();
              e.grenT = CFG.enemies.bossw.grenadeCd;
              continue;
            }
          }
          /* lunge: negative = windup, positive = dash */
          if (e.lunge < 0) {
            e.lunge += dt;
            e.bob += e.spd * dt * .005;
          } else if (e.lunge > 0) {
            e.lunge -= dt;
            e.x += nx * e.spd * 3.5 * dt;
            e.y += ny * e.spd * 3.5 * dt;
            e.bob += e.spd * dt * .02;
            if (!P.dead && Math.hypot(P.x - e.x, P.y - e.y) < 60) P.takeHit(e.dmg, sfx);
          } else {
            if (e.atkT <= 0 && d < 140) { e.atkT = 2.5; e.lunge = -0.3; SFX.bossRoar(); }
            if (e.lunge === 0) { ENEMY.moveAlong(e, dt, d < 90 ? 1.0 : 0.7); e.bob += e.spd * dt * .012; }
          }
          if (e.type === 'bossw' && e.spawnCd !== undefined) {
            e.spawnCd -= dt;
            if (e.spawnCd <= 0 && e.spawnCount > 0) {
              e.spawnCount--;
              ENEMY.add('soldier', e.x + (Math.random() - .5) * 80, e.y + (Math.random() - .5) * 80);
              SFX.bossRoar();
              e.spawnCd = 10;
            }
          }
          break;
        }
      }

      /* collision vs world */
      const res = WORLD.resolveCircle(e.x, e.y, 18, 3);
      e.x = res.x; e.y = res.y;
      /* keep in world bounds */
      e.x = clamp(e.x, 20, W.w - 20);
      e.y = clamp(e.y, 20, W.h - 20);
    }
    /* remove dead */
    for (let i = this.arr.length - 1; i >= 0; i--) {
      const e = this.arr[i];
      if (e.dead && e.deathT > 1.4) this.arr.splice(i, 1);
    }
    this.separate();
  },
  /* LOS check: no static AABB between e and player */
  losOk: function (e) {
    const dx = P.x - e.x, dy = P.y - e.y;
    const d = Math.hypot(dx, dy) || 1;
    const steps = Math.max(1, Math.floor(d / 24));
    for (let s = 1; s < steps; s++) {
      const t = s / steps;
      const px = e.x + dx * t, py = e.y + dy * t;
      for (let i = 0; i < WORLD.objs.length; i++) {
        const o = WORLD.objs[i];
        if (!o.solid) continue;
        if (px > o.x && px < o.x + o.w && py > o.y && py < o.y + o.h) {
          return false;
        }
      }
    }
    return true;
  },
  hitEnemy: function (e, dmg) {
    if (e.dead) return;
    e.hp -= dmg;
    e.hitFlash = 1;
    if (e.hp <= 0) {
      e.dead = true;
      e.deathT = 0;
      SFX.hit();
      PARTS.blood(e.x, e.y, 12);
      PARTS.boom(e.x, e.y, 6, '#8b0000', 8);
      /* loot */
      const loot = CFG.enemies[e.type] && CFG.enemies[e.type].loot;
      if (loot) {
        if (Math.random() < (loot.ammoP || 0)) {
          const amt = irand(loot.ammo[0], loot.ammo[1]);
          PICKUP.spawn(e.x, e.y, 'ammo', amt);
        }
        if (Math.random() < (loot.grenP || 0)) {
          PICKUP.spawn(e.x, e.y, 'gren');
        }
      }
      SCORE.add(e.score, e.x, e.y);
    }
  },
  scoreAdd: function (score) {},
};

/* ---------------------------------------------------- 12. PROJECTILES -- */
const PROJ = {
  arr: [],
  add: function (x, y, ang, o) {
    const b = {
      x: x, y: y, ang: ang,
      vx: o.vx || 0, vy: o.vy || 0,
      kind: o.kind || 'bullet',
      dmg: o.dmg || 25,
      range: o.range || 400,
      fired: 0,
      magCost: o.magCost || 1,
      targetX: o.targetX || 0, targetY: o.targetY || 0,
      fuse: o.fuse || 0, blastR: o.blastR || 0, blastDmg: o.blastDmg || 0,
      vel: 900,
    };
    b.vel = Math.hypot(b.vx, b.vy) || 900;
    PROJ.arr.push(b);
  },
  /* fire a bullet AT the player, FROM the enemy at (ex,ey). The bullet spawns
     at the enemy's muzzle (in front of them, facing the player) and flies
     toward the player — same speed/look as the player's own bullets, yet it
     still collides only with the player. */
  fireAtPlayer: function (ex, ey, dmg) {
    const dx = P.x - ex, dy = P.y - ey;
    const d = Math.hypot(dx, dy) || 1;
    const a = Math.atan2(dy, dx);          /* enemy -> player */
    const v = 666;                       /* slower enemy bullets for more reaction time */
    const muzzle = Math.min(36, d);       /* spawn at the gun, never past the player */
    const b = { x: ex + Math.cos(a) * muzzle, y: ey + Math.sin(a) * muzzle,
                ang: a, vx: Math.cos(a) * v, vy: Math.sin(a) * v,
                kind: 'enemyBullet', dmg: dmg, range: 900, fired: 0, vel: v };
    PROJ.arr.push(b);
  },
  update: function (dt, sfx) {
    for (let i = PROJ.arr.length - 1; i >= 0; i--) {
      const b = PROJ.arr[i];
      if (b.kind === 'grenade') {
        /* throw arc toward target */
        const dx = b.targetX - b.x, dy = b.targetY - b.y;
        const d = Math.hypot(dx, dy) || 1;
        const step = 400 * dt;
        if (d > step) {
          b.x += (dx / d) * step;
          b.y += (dy / d) * step;
        }
        b.fuse -= dt;
        if (b.fuse <= 0) {
          this.explode(b.x, b.y, b.blastR || 100, b.blastDmg || 80, sfx);
          PARTS.smoke(b.x, b.y, 10, '#444');
          PROJ.arr.splice(i, 1);
        }
        continue;
      }
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      b.fired += dt;
      /* range limit */
      if (b.fired * b.vel > b.range) { PROJ.arr.splice(i, 1); continue; }
      /* vs player (only enemy bullets hit the player) */
      if (b.kind === 'enemyBullet') {
        if (dist(b.x, b.y, P.x, P.y) < P.radius + 4 && !P.dead) {
          P.takeHit(b.dmg, sfx);
          PROJ.arr.splice(i, 1);
          continue;
        }
      }
      /* vs enemies (only player bullets hit enemies) */
      if (b.kind !== 'enemyBullet') {
        let hit = false;
        for (let j = 0; j < ENEMY.arr.length; j++) {
          const e = ENEMY.arr[j];
          if (e.dead) continue;
          if (dist(b.x, b.y, e.x, e.y) < 20) {
            ENEMY.hitEnemy(e, b.dmg);
            PARTS.blood(e.x, e.y, 6);
            hit = true;
            break;
          }
        }
        if (hit) PROJ.arr.splice(i, 1);
      }
    }
  },
  explode: function (x, y, r, dmg, sfx) {
    if (sfx) sfx.explode();
    CAM.addShake(12);
    PARTS.boom(x, y, 28, '#ffaa00', 10);
    PARTS.smoke(x, y, 8, '#666');
    /* player only hurt if inside the blast radius (self-damage is real) */
    if (!P.dead && dist(P.x, P.y, x, y) < r) P.takeHit(dmg, sfx);
    for (let j = 0; j < ENEMY.arr.length; j++) {
      const e = ENEMY.arr[j];
      if (e.dead) continue;
      if (dist(e.x, e.y, x, y) < r) ENEMY.hitEnemy(e, dmg);
    }
  },
};

/* ---------------------------------------------------------- 13. PICKUPS -- */
const PICKUP = {
  arr: [],
  spawn: function (x, y, type, amt) {
    const ttl = type === 'coin' ? 30 : 8;
    PICKUP.arr.push({ x: x, y: y, type: type, ttl: ttl, l: ttl, amt: amt || 1, bob: Math.random() * 6.283, rot: Math.random() * 6.283 });
  },
  update: function (dt, sfx) {
    for (let i = PICKUP.arr.length - 1; i >= 0; i--) {
      const p = PICKUP.arr[i];
      p.ttl -= dt;
      p.bob += dt * 4;
      p.rot += dt * .6;
      if (p.ttl <= 0) { PICKUP.arr.splice(i, 1); continue; }
      if (P.dead) continue;
      if (dist(p.x, p.y, P.x, P.y) < 28) {
        this.collect(p, sfx);
        PICKUP.arr.splice(i, 1);
      }
    }
  },
  collect: function (p, sfx) {
    switch (p.type) {
      case 'ammo': P.addAmmo(p.amt); if (sfx) sfx.pickupAmmo(); break;
      case 'gren': P.addGren(1); if (sfx) sfx.pickupGren(); break;
      case 'health': P.heal(30, sfx); if (sfx) sfx.pickupHealth(); break;
      case 'coin': SCORE.addGold(); break;
      case 'ammoBox': P.addAmmo(10); if (sfx) sfx.pickupAmmo(); break;
    }
  },
  spawnWaveEnd: function () {
    const types = ['ammo', 'ammo', 'ammo', 'gren', 'health', 'coin'];
    for (let i = 0; i < 3; i++) {
      const t = types[irand(0, types.length - 1)];
      const amt = t === 'ammo' ? irand(5, 10) : 1;
      PICKUP.spawn(
        clamp(100 + irand(0, 1800), 40, W.w - 40),
        clamp(100 + irand(0, 1000), 40, W.h - 40),
        t, amt
      );
    }
  },
};

/* ------------------------------------------------------------ SCORE ---- */
const SCORE = {
  pts: 0, goldMult: 1, goldTimer: 0,
  kills: 0, combo: 0, comboT: 0,
  add: function (pts, x, y) {
    this.kills++;
    this.combo++;
    this.comboT = CFG.combo.window;
    if (this.combo >= 3) {
      const el = $('combo');
      el.textContent = this.combo + ' COMBO!';
      el.classList.add('show');
      setTimeout(function () { el.classList.remove('show'); }, 1200);
    }
    const bonus = this.combo >= 3 ? Math.floor(this.combo * 5) : 0;
    const total = Math.round(pts * this.goldMult) + bonus;
    this.pts += total;
    if (x !== undefined) PARTS.float(x, y - 20, '+' + total, '#ffd94d');
  },
  addGold: function () {
    this.goldMult = Math.min(5, this.goldMult + .5);
    this.goldTimer = CFG.pickups.ttlGold;
    this.pts += 25;
    PARTS.float(P.x, P.y - 30, '+gold ×' + this.goldMult.toFixed(1), '#ffd94d');
    SFX.pickupGold();
  },
  tick: function (dt) {
    this.comboT = Math.max(0, this.comboT - dt);
    if (this.comboT <= 0) this.combo = 0;
    this.goldTimer = Math.max(0, this.goldTimer - dt);
    if (this.goldTimer <= 0) this.goldMult = 1;
  },
  reset: function () {
    this.pts = 0; this.goldMult = 1; this.goldTimer = 0;
    this.kills = 0; this.combo = 0; this.comboT = 0;
  },
};

/* ------------------------------------------------------------- 14. ART -- */
/*
   100 % procedural Canvas-Rendering (kein Sprite-Sheet). Alle Entitäten
   werden pro-Frame gezeichnet mit Walk-Bob, Head-Wiggle, Gun-Recoil,
   Hit-Flash. Optional: wenn assets/sprites/*.png geladen sind, werden
   die Images stattdessen verwendet (drawAsset oben).
*/
function drawShadow(g, x, y, r) {
  g.fillStyle = 'rgba(0,0,0,.28)';
  g.beginPath();
  g.ellipse(x, y + 4, r * 1.3, r * .55, 0, 0, 6.283);
  g.fill();
}

function drawPlayer(g) {
  const p = P;
  if (p.dead) {
    g.save();
    g.globalAlpha = Math.max(0, 1 - p.deathT * 1.2);
    const a = Math.atan2(p.aimY - p.y, p.aimX - p.x);
    g.translate(p.x, p.y);
    g.rotate(a);
    /* fallen */
    g.fillStyle = p.hitFlash > .5 ? '#fff' : '#4a2a1a';
    g.beginPath(); g.ellipse(0, 0, 16, 22, a, 0, 6.283); g.fill();
    g.fillStyle = '#8b0000';
    g.beginPath(); g.ellipse(0, 6, 12, 10, a, 0, 6.283); g.fill();
    g.restore();
    return;
  }
  const w = CFG.weapons[p.weapon];
  const aimA = Math.atan2(p.aimY - p.y, p.aimX - p.x);
  const bobY = Math.sin(p.bob * 2) * 2;
  const bobX = Math.cos(p.bob * 2) * 1;
  const flash = p.hitFlash > 0;

  g.save();
  g.translate(p.x + bobX, p.y + bobY);
  g.rotate(aimA);
  /* shadow */
  g.save(); g.rotate(-aimA); drawShadow(g, 0, 0, 16); g.restore();

  /* image fallback (real sprite in assets/sprites/) */
  if (drawAssetAlt(g, ['player_run', 'player'], 0, 0, 42, p.hitFlash)) { g.restore(); return; }

  /* body (blue tunic) */
  const bodyColor = flash ? '#fff' : (p.dead ? '#555' : '#2e5e8c');
  g.fillStyle = bodyColor;
  g.beginPath(); g.ellipse(0, 0, 13, 10, 0, 0, 6.283); g.fill();
  /* belt */
  g.fillStyle = '#3a2a1a';
  g.fillRect(-8, -2, 16, 4);
  /* legs (walk cycle) */
  g.fillStyle = '#222';
  const sw = Math.sin(p.bob * 2.5);
  g.fillRect(-8, -6, 5, 6);
  g.fillRect(3, 6, 5, 6);

  /* head (beard + hat) */
  g.fillStyle = '#8a7a60';
  g.beginPath(); g.ellipse(6, -1, 7, 6, 0, 0, 6.283); g.fill();
  /* beard */
  g.fillStyle = '#a56a20';
  g.beginPath(); g.ellipse(7, 1, 5, 4, 0, 0, 6.283); g.fill();
  /* hat (blue beanie) */
  g.fillStyle = flash ? '#fff' : '#1e3e5e';
  g.fillRect(1, -6, 12, 6);
  g.fillStyle = flash ? '#fff' : '#2e5e8c';
  g.fillRect(1, -8, 12, 3);
  /* eye (glare) */
  g.fillStyle = '#fff';
  g.fillRect(9, -2, 3, 2);

  /* gun arm */
  const swing = p.anim.shoot ? 2 : 0;
  const rx = -swing * 2 + 14;
  g.fillStyle = flash ? '#fff' : '#c8c2b2';
  g.fillRect(10, -2, 10, 4);
  /* weapon shape */
  g.fillStyle = flash ? '#fff' : w.color;
  if (p.weapon === 0) {
    /* pistol */
    g.fillRect(18, -3, 10, 6);
    g.fillRect(18, 3, 10, 3);
  } else if (p.weapon === 1) {
    /* rifle */
    g.fillRect(14, -2, 24, 4);
    g.fillRect(22, 2, 2, 6);
    g.fillStyle = flash ? '#fff' : '#222';
    g.fillRect(30, -3, 6, 4);
  } else {
    /* shotgun */
    g.fillStyle = flash ? '#fff' : '#8a7a5e';
    g.fillRect(16, -5, 22, 8);
    g.fillStyle = flash ? '#fff' : '#444';
    g.fillRect(26, -4, 12, 2);
    g.fillRect(26, 2, 12, 2);
  }
  g.restore();
}

function drawEnemy(g, e) {
  if (e.dead) {
    /* corpse: dark stain */
    g.save();
    g.globalAlpha = Math.max(0, 1 - e.deathT * 0.8);
    g.fillStyle = '#2a0a0a';
    g.beginPath(); g.ellipse(e.x, e.y + 4, 18, 12, 0, 0, 6.283); g.fill();
    g.restore();
    return;
  }
  const dx = P.x - e.x, dy = P.y - e.y;
  const a = Math.atan2(dy, dx);
  const bobY = Math.sin(e.walkT * 1.2) * 1.5;
  const flash = e.hitFlash > 0;
  g.save();
  g.translate(e.x, e.y + bobY);
  g.rotate(a);

  drawShadow(g, 0, 0, 18);

  /* image fallback (real sprite in assets/sprites/) */
  if (drawAssetAlt(g, [e.type === 'bossz' || e.type === 'bossw' ? 'boss' : e.type], 0, 0, 38, e.hitFlash)) { g.restore(); return; }

  const bodyC = flash ? '#fff' : (e.type === 'zombie' ? '#5a6a4a' : e.type === 'soldier' ? '#4a5a4a' : e.type === 'bossz' ? '#6a7a5a' : '#5a504a');
  g.fillStyle = bodyC;
  g.beginPath(); g.ellipse(0, 0, 14, 10, 0, 0, 6.283); g.fill();

  if (e.type === 'zombie') {
    /* ragged shirt + arms out */
    g.fillStyle = flash ? '#fff' : '#3a4a3a';
    g.fillRect(-6, -10, 6, 6);
    g.fillRect(2, -10, 6, 6);
    /* head */
    g.fillStyle = flash ? '#fff' : '#a5b57a';
    g.beginPath(); g.ellipse(7, 0, 6, 5, 0, 0, 6.283); g.fill();
    /* eye */
    g.fillStyle = '#ff3333';
    g.fillRect(10, -1, 2, 2);
    /* blood */
    g.fillStyle = '#8b0000';
    g.fillRect(2, -3, 6, 3);
  } else if (e.type === 'soldier') {
    /* helmet + rifle */
    g.fillStyle = flash ? '#fff' : '#3a3a2a';
    g.fillRect(-4, -8, 8, 6);
    g.fillStyle = flash ? '#fff' : '#888';
    g.beginPath(); g.ellipse(6, 0, 5, 4, 0, 0, 6.283); g.fill();
    /* rifle */
    g.fillStyle = flash ? '#fff' : '#4a4a3a';
    g.fillRect(10, -2, 26, 5);
    g.fillStyle = flash ? '#fff' : '#222';
    g.fillRect(32, -3, 4, 6);
    /* armband */
    g.fillStyle = flash ? '#fff' : '#5a2a1a';
    g.fillRect(-8, -4, 4, 10);
    /* muzzle flash: shows WHERE a shot fired from (replaces the old red line) */
    if (e.muzzleFlash > 0) {
      g.save();
      g.globalAlpha = e.muzzleFlash;
      g.fillStyle = 'rgba(255,235,140,0.6)';
      g.beginPath(); g.ellipse(37, 0.5, 11, 11, 0, 0, 6.283); g.fill();
      g.fillStyle = 'rgba(255,255,220,0.9)';
      g.beginPath(); g.ellipse(37, 0.5, 6, 6, 0, 0, 6.283); g.fill();
      g.fillStyle = '#fff';
      g.beginPath(); g.ellipse(37, 0.5, 3, 3, 0, 0, 6.283); g.fill();
      g.restore();
    }
  } else {
    /* boss (both captains) */
    /* bigger body, armor, weapon */
    const isBossW = e.type === 'bossw';
    g.fillStyle = flash ? '#fff' : (isBossW ? '#4a3a2a' : '#3a4a3a');
    g.fillRect(-10, -10, 20, 20);
    g.fillStyle = flash ? '#fff' : (isBossW ? '#5a4a2a' : '#4a5a4a');
    g.fillRect(-14, -6, 28, 12);
    /* head */
    g.fillStyle = flash ? '#fff' : (isBossW ? '#9a8a7a' : '#a5b57a');
    g.beginPath(); g.ellipse(6, 0, 8, 7, 0, 0, 6.283); g.fill();
    /* eyes */
    g.fillStyle = flash ? '#fff' : (isBossW ? '#ff8800' : '#ff3333');
    g.fillRect(10, -2, 4, 3);
    g.fillRect(4, -2, 4, 3);
    /* weapon */
    g.fillStyle = flash ? '#fff' : '#3a3a3a';
    if (isBossW) {
      /* axe */
      g.fillRect(12, -3, 22, 6);
      g.fillStyle = flash ? '#fff' : '#aaa';
      g.fillRect(30, -8, 10, 14);
    } else {
      /* club */
      g.fillRect(12, -3, 22, 6);
      g.fillStyle = flash ? '#fff' : '#2a1a0a';
      g.beginPath(); g.ellipse(34, 0, 8, 8, 0, 0, 6.283); g.fill();
    }
    /* shoulder pads */
    g.fillStyle = flash ? '#fff' : '#6a6a6a';
    g.fillRect(-16, -12, 8, 8);
    g.fillRect(8, -12, 8, 8);
  }
  g.restore();
}

function drawProjectile(g) {
  for (let i = 0; i < PROJ.arr.length; i++) {
    const b = PROJ.arr[i];
    g.save();
    if (b.kind === 'grenade') {
      /* small green ball with spark when fuse low */
      const r = 6;
      if (!drawAssetAlt(g, ['grenade'], b.x, b.y, 14, 0)) {
        g.fillStyle = '#3a5a2a';
        g.beginPath(); g.ellipse(b.x, b.y, r, r, 0, 0, 6.283); g.fill();
        g.fillStyle = '#2a4a1a';
        g.beginPath(); g.ellipse(b.x - 2, b.y - 3, 4, 2.5, 0, 0, 6.283); g.fill();
      }
      /* fuse spark */
      if (b.fuse > 0) {
        const spark = b.fuse > 0.5 ? 1 : Math.random() * 2;
        g.fillStyle = b.fuse < 0.5 ? '#fff' : '#ffaa00';
        g.globalAlpha = spark;
        g.fillRect(b.x - 1, b.y - r - 3, 2, 5);
        g.globalAlpha = 1;
        if (b.fuse < 0.5 && Math.random() > .7) {
          PARTS.spawn(b.x, b.y - r - 2, 0, -20, .3, '#ffaa00', 'glow', 3);
        }
      }
    } else {
      /* bullet streak */
      if (!drawAssetAlt(g, ['bullet'], b.x, b.y, 12, 0)) {
        /* Player & enemy bullets share ONE identical look (same colour/size).
           Enemy fire is additionally telegraphed by a bright muzzle flash at
           the shooter + the high "pew", so you see WHERE it came from and can dodge.
           and dodgeable. */
        g.strokeStyle = '#ffd94d';
        g.lineWidth = 2;
        g.lineCap = 'round';
        g.beginPath();
        g.moveTo(b.x, b.y);
        g.lineTo(b.x - Math.cos(b.ang) * 10, b.y - Math.sin(b.ang) * 10);
        g.stroke();
        g.fillStyle = '#fff';
        g.beginPath(); g.ellipse(b.x, b.y, 2.5, 2.5, 0, 0, 6.283); g.fill();
      }
    }
    g.restore();
  }
}

function drawPickup(g) {
  for (let i = 0; i < PICKUP.arr.length; i++) {
    const p = PICKUP.arr[i];
    const alpha = clamp(p.ttl / p.l, 0, 1);
    const glow = Math.sin(p.bob) * .5 + .5;
    const gx = p.x + Math.sin(p.rot) * 4;
    const gy = p.y + Math.cos(p.rot) * 4;
    g.save();
    g.globalAlpha = Math.max(.3, alpha * .8);
    /* soft glow */
    g.fillStyle = 'rgba(255,210,80,' + glow * .2 + ')';
    g.beginPath(); g.ellipse(p.x, p.y, 18, 14, 0, 0, 6.283); g.fill();

    /* image fallback (real sprite in assets/sprites/) */
    if (drawAssetAlt(g, [p.type === 'ammoBox' ? 'ammoBox' : p.type], p.x, p.y, 22, 0)) { g.restore(); continue; }

    switch (p.type) {
      case 'ammo':
        g.fillStyle = '#6a4a2a';
        g.fillRect(p.x - 8, p.y - 6, 16, 12);
        g.fillStyle = '#8a6a3a';
        g.fillRect(p.x - 6, p.y - 4, 12, 8);
        g.fillStyle = '#f2c14e';
        g.fillRect(p.x - 2, p.y - 3, 4, 6);
        break;
      case 'gren':
        g.fillStyle = '#4a6a3a';
        g.beginPath(); g.ellipse(p.x, p.y, 8, 8, 0, 0, 6.283); g.fill();
        g.fillStyle = '#5a7a4a';
        g.beginPath(); g.ellipse(p.x, p.y - 2, 6, 5, 0, 0, 6.283); g.fill();
        g.fillStyle = '#f2c14e';
        g.fillRect(p.x - 1, p.y - 8, 2, 4);
        break;
      case 'health':
        g.fillStyle = '#8b0000';
        g.fillRect(p.x - 8, p.y - 8, 16, 16);
        g.fillStyle = '#fff';
        g.fillRect(p.x - 5, p.y - 2, 10, 3);
        g.fillRect(p.x - 2, p.y - 5, 3, 9);
        break;
      case 'coin':
        g.fillStyle = '#ffd94d';
        g.beginPath(); g.ellipse(p.x, p.y, 8, 6, 0, 0, 6.283); g.fill();
        g.fillStyle = '#f2a92e';
        g.beginPath(); g.ellipse(p.x, p.y, 5, 4, 0, 0, 6.283); g.fill();
        break;
      case 'ammoBox':
        g.fillStyle = '#3a2a1a';
        g.fillRect(p.x - 12, p.y - 10, 24, 20);
        g.fillStyle = '#5a4a2a';
        g.fillRect(p.x - 9, p.y - 7, 18, 14);
        g.fillStyle = '#f2c14e';
        g.font = 'bold 11px monospace';
        g.textAlign = 'center';
        g.textBaseline = 'middle';
        g.fillText('AMMO', p.x, p.y + 1);
        break;
    }
    g.restore();
  }
}

function drawParticles(g) {
  for (let i = 0; i < PARTS.arr.length; i++) {
    const p = PARTS.arr[i];
    const t = p.life / p.l;
    g.save();
    g.globalAlpha = Math.min(1, t * 1.5);
    if (p.kind === 'blood') {
      g.fillStyle = p.col;
      g.beginPath(); g.ellipse(p.x, p.y, p.s * t, p.s * t, 0, 0, 6.283); g.fill();
    } else if (p.kind === 'flash') {
      g.fillStyle = p.col;
      g.beginPath(); g.ellipse(p.x, p.y, p.s * t, p.s * t, 0, 0, 6.283); g.fill();
    } else if (p.kind === 'spark') {
      g.strokeStyle = p.col;
      g.lineWidth = 2;
      g.beginPath(); g.moveTo(p.x, p.y); g.lineTo(p.x - p.vx * .02, p.y - p.vy * .02); g.stroke();
    } else if (p.kind === 'smoke') {
      g.fillStyle = p.col;
      g.globalAlpha *= .35;
      g.beginPath(); g.ellipse(p.x, p.y, p.s * (1 - t) * 1.5, p.s * (1 - t) * 1.5, 0, 0, 6.283); g.fill();
    } else if (p.kind === 'boom') {
      g.fillStyle = p.col;
      g.globalAlpha = t;
      g.beginPath(); g.ellipse(p.x, p.y, p.s * (1 - t) * 2, p.s * (1 - t) * 2, 0, 0, 6.283); g.fill();
    } else if (p.kind === 'glow') {
      g.fillStyle = p.col;
      g.globalAlpha = t;
      g.beginPath(); g.ellipse(p.x, p.y, p.s, p.s, 0, 0, 6.283); g.fill();
    } else if (p.kind === 'text') {
      g.fillStyle = p.col;
      const fs = (typeof p.s === 'number') ? Math.max(10, p.s - 2) : 14;
      g.font = 'bold ' + fs + 'px monospace';
      g.textAlign = 'center';
      g.textBaseline = 'middle';
      g.fillText(p.s, p.x, p.y);
    }
    g.restore();
  }
}

/* ------------------------------------------------------------- 15. HUD -- */
function $(sel) { return document.getElementById(sel); }
const HUD = {
  el: {
    hp: $('hphp'), hpTxt: $('hptxt'),
    wave: $('hwave'), time: $('htime'),
    score: $('hscore'), mult: $('hmult'),
    weapon: $('hweapon'), mag: $('hmag'),
    ammo: $('hammo'), gren: $('hgren'),
    sprint: $('hsprint'),
    slots: document.querySelectorAll('.slot'),
  },
  flashEl: $('flash'), healEl: $('healglow'), victoryEl: $('victoryglow'),
  update: function () {
    const p = CFG.player;
    const w = CFG.weapons[P.weapon];
    HUD.el.hp.style.width = (P.hp / P.maxHp * 100) + '%';
    HUD.el.hp.style.background = P.hp / P.maxHp > .5 ? 'var(--hp)' : 'var(--danger)';
    HUD.el.hpTxt.textContent = Math.ceil(P.hp) + ' / ' + P.maxHp;
    HUD.el.wave.textContent = WAVE.n + ' / 5';
    HUD.el.time.textContent = fmtTime(WAVE.time);
    HUD.el.score.textContent = SCORE.pts;
    HUD.el.mult.textContent = '×' + SCORE.goldMult.toFixed(1);
    HUD.el.weapon.textContent = w.name;
    HUD.el.mag.textContent = P.mag + ' / ' + w.mag;
    HUD.el.ammo.textContent = P.mag;
    HUD.el.gren.textContent = P.grenCount;
    HUD.el.sprint.style.width = (P.sprint.active ? 1 : (1 - P.sprint.recover / p.sprintRecover)) * 100 + '%';
    for (let i = 0; i < HUD.el.slots.length; i++) {
      HUD.el.slots[i].classList.toggle('active', i === P.weapon);
    }
    /* damage flash / heal glow via opacity class */
    HUD.flashEl.style.opacity = P.hitFlash > 0 ? P.hitFlash : 0;
    HUD.healEl.style.opacity = P.healGlow > 0 ? P.healGlow : 0;
  },
  flash: function (color) {
    /* handled by P.hitFlash */
  },
};

/* --------------------------------------------------------- 16. SCREENS -- */
const SCREEN = {
  show: function (id) {
    ['menu', 'pause', 'gameover', 'victory'].forEach(function (n) {
      $(n).classList.toggle('show', n === id);
    });
    $('hud').style.display = id ? 'none' : '';
  },
  hide: function () {
    ['menu', 'pause', 'gameover', 'victory'].forEach(function (n) {
      $(n).classList.remove('show');
    });
    $('hud').style.display = '';
  },
  gameOver: function () {
    SCORE.pts = 0;
    $('goWave').textContent = 'Bert fiel in der Wellen ' + WAVE.n;
    $('goStats').textContent = 'SCORE: ' + SCORE.pts + ' · TIME: ' + fmtTime(WAVE.time) + ' · KILLS: ' + SCORE.kills;
    SCREEN.show('gameover');
  },
  victory: function () {
    $('viText').textContent = 'Der Heli fliegt ab. Bert lebt — für heute.';
    $('viStats').textContent = 'SCORE: ' + SCORE.pts + ' · TIME: ' + fmtTime(WAVE.time) + ' · KILLS: ' + SCORE.kills;
    SCREEN.show('victory');
  },
  menu: function () {
    SCREEN.show('menu');
  },
  pause: function () {
    SCREEN.show('pause');
  },
};

/* ------------------------------------------------------------ 17. WAVES -- */
const WAVE = {
  n: 1, time: 0, active: false, overload: false,
  phase: 0,        /* 0 = warning, 1 = spawning, 2 = between waves */
  spawnT: 0,       /* phase timer */
  spawnQ: 0,       /* enemies left to spawn (not boss) */
  rem: null,       /* {z: rem zombies, s: rem soldiers} */
  lastStep: 0,     /* spawn cadence counter */
  start: function (n) {
    WAVE.n = n;
    WAVE.active = true;
    WAVE.phase = 0;
    if (n === 6) {
      /* OVERLOAD: continuous spawn, victory at CFG.overload.at */
      WAVE.overload = true;
      WAVE.spawnT = 2;
      return;
    }
    WAVE.overload = false;
    WAVE.rem = null;
    const c = CFG.waves[n - 1] || { zombies: 0, soldiers: 0, boss: 0 };
    WAVE.rem = { z: c.zombies, s: c.soldiers };
    WAVE.spawnQ = c.zombies + c.soldiers;
    WAVE.spawnT = CFG.spawnWarn;
    WAVE.lastStep = 0;
    SFX.waveHorn();
    for (let i = 0; i < 4; i++) {
      const p = WORLD.spawnPts[i];
      PARTS.text(p.x, p.y, '⚠', '#ff3333', 2);
    }
  },
  /* spawn one regular enemy at the wave edges */
  spawnOne: function () {
    const pt = WORLD.spawnPts[irand(0, 3)];
    const ox = (Math.random() - .5) * 60, oy = (Math.random() - .5) * 60;
    const r = WAVE.rem;
    let type;
    if (r.z <= 0) type = 'soldier';
    else if (r.s <= 0) type = 'zombie';
    else {
      const tot = r.z + r.s;
      type = (Math.random() < r.z / tot) ? 'zombie' : 'soldier';
    }
    if (type === 'zombie') r.z--; else r.s--;
    ENEMY.add(type, pt.x + ox, pt.y + oy, {});
  },
  update: function (dt) {
    WAVE.time += dt;
    if (GAME.state !== STATE.PLAYING) return;
    if (WAVE.overload) {
      WAVE.spawnT -= dt;
      if (WAVE.spawnT <= 0 && ENEMY.arr.length < 30) {
        if (Math.random() < .6) {
          ENEMY.add('zombie', irand(150, 1850), irand(150, 1050), { speedMult: CFG.overload.speed });
        } else {
          ENEMY.add('soldier', irand(150, 1850), irand(150, 1050), { speedMult: CFG.overload.speed });
        }
        WAVE.spawnT = 2;
      }
      if (WAVE.time >= CFG.overload.at) {
        GAME.state = STATE.VICTORY;
        SCREEN.victory();
        SFX.musicStop();
        GAME.stop();
      }
      return;
    }
    if (WAVE.phase === 0) {
      WAVE.spawnT -= dt;
      if (WAVE.spawnT <= 0) {
        WAVE.phase = 1; WAVE.spawnT = 0; WAVE.lastStep = 0;
        /* boss spawns right at wave start (dramatic) */
        if (CFG.waves[WAVE.n - 1] && CFG.waves[WAVE.n - 1].boss > 0) {
          const pt = WORLD.spawnPts[irand(0, 3)];
          const t = WAVE.n === 4 ? 'bossw' : 'bossz';
          ENEMY.add(t, pt.x, pt.y, {});
          SFX.bossRoar();
        }
      }
    } else if (WAVE.phase === 1) {
      if (WAVE.spawnQ > 0) {
        WAVE.spawnT -= dt;
        const step = WAVE.spawnT < 0 ? Math.floor(-WAVE.spawnT / 0.6) : 0;
        if (step > WAVE.lastStep) {
          WAVE.lastStep = step;
          if (WAVE.spawnQ > 0) {
            WAVE.spawnOne();
            WAVE.spawnQ--;
          }
        }
      } else {
        WAVE.phase = 2;
        WAVE.spawnT = 7;
        PICKUP.spawnWaveEnd();
      }
    } else if (WAVE.phase === 2) {
      WAVE.spawnT -= dt;
      if (WAVE.spawnT <= 0 && WAVE.n < 6) {
        WAVE.start(WAVE.n + 1);
      }
    }
  },
};

/* -------------------------------------------------------- 18. GAME LOOP -- */
const GAME = {
  state: STATE.MENU,
  raf: null,
  lastT: 0,
  acc: 0,
  start: function () {
    GAME.lastT = performance.now();
    GAME.raf = requestAnimationFrame(GAME.loop);
  },
  stop: function () {
    GAME.raf = null;
  },
  loop: function (now) {
    const dt = Math.min((now - GAME.lastT) / 1000, CFG.maxDt);
    GAME.lastT = now;
    GAME.acc += dt;
    while (GAME.acc >= CFG.fixedDt) {
      GAME.update(CFG.fixedDt);
      GAME.acc -= CFG.fixedDt;
    }
    GAME.render();
    GAME.raf = requestAnimationFrame(GAME.loop);
  },
  update: function (dt) {
    if (GAME.state === STATE.PLAYING) {
      SCORE.tick(dt);
      /* input */
      if (IN.keys.R) { IN.keys.R = false; GAME.state = STATE.MENU; SCREEN.menu(); SFX.musicStop(); GAME.stop(); }
      if (IN.keys.P) { IN.keys.P = false; GAME.state = STATE.PAUSED; SCREEN.pause(); SFX.ui(); }
      /* fire */
      if (IN.mb[0] && !P.dead) {
        if (P.fireT <= 0) P.shoot(SFX);
      }
      /* grenade */
      if (IN.mb[1] || IN.keys[' '] || IN.keys.G) {
        if (P.grenCd <= 0) P.throwGrenade(SFX);
      }
      P.update(dt, { x: IN.mx, y: IN.my }, IN.keys, SFX);
      ENEMY.update(dt, SFX);
      PROJ.update(dt, SFX);
      PICKUP.update(dt, SFX);
      PARTS.update(dt);
      CAM.tick(dt);
      CAM.follow(P.x, P.y);
      WAVE.update(dt);
      /* death check */
      if (P.dead && P.deathT > 1.5) {
        GAME.state = STATE.GAMEOVER;
        SCREEN.gameOver();
        SFX.musicStop();
        GAME.stop();
      }
    }
  },
  render: function () {
    const g = gameCtx;
    g.save();
    /* background (screen space) */
    g.fillStyle = '#0b0a08';
    g.fillRect(0, 0, C.w, C.h);
    /* camera + shake transform (everything below is world space) */
    g.translate(-CAM.x, -CAM.y);
    if (CAM.shake > 0.5) {
      g.translate((Math.random() - .5) * CAM.shake * 2, (Math.random() - .5) * CAM.shake * 2);
    }
    /* static world */
    if (WORLD.staticCv) {
      g.drawImage(WORLD.staticCv, 0, 0);
    }
    drawPickup(g);
    for (let i = 0; i < ENEMY.arr.length; i++) drawEnemy(g, ENEMY.arr[i]);
    drawProjectile(g);
    drawPlayer(g);
    drawParticles(g);
    g.restore();
    /* state banner (debug) - only shown in test mode */
    if (typeof TEST_MODE !== 'undefined' && TEST_MODE && GAME.state !== STATE.PLAYING) {
      g.save();
      g.fillStyle = 'rgba(0,0,0,.4)';
      g.fillRect(0, 0, C.w, 40);
      g.fillStyle = '#f2c14e';
      g.font = 'bold 16px monospace';
      g.textAlign = 'left';
      g.textBaseline = 'middle';
      g.fillText('STATE: ' + STATE_NAMES[GAME.state] + '  wave=' + WAVE.n + '  time=' + WAVE.time.toFixed(1) + 's  kills=' + SCORE.kills, 8, 20);
      g.restore();
    }
    if (typeof TEST_MODE !== 'undefined' && TEST_MODE) {
      g.save();
      g.fillStyle = '#ffd94d';
      g.font = '11px monospace';
      g.fillText('state=' + STATE_NAMES[GAME.state] + ' wave=' + WAVE.n + ' enemies=' + ENEMY.arr.length + ' hp=' + Math.ceil(P.hp) + ' time=' + WAVE.time.toFixed(1) + ' kills=' + SCORE.kills + ' combo=' + SCORE.combo, 6, 14);
      g.fillStyle = '#ff444d';
      g.font = '10px monospace';
      g.fillText((typeof errText !== 'undefined') ? errText : 'no js errors', 6, C.h - 8);
      g.restore();
    }
    HUD.update();
  },
  inputKey: function (key) {
    IN.onKey = function (k) {
      if (GAME.state === STATE.MENU) {
        if (k === ' ' || k === 'Enter') GAME.startGame();
      } else if (GAME.state === STATE.GAMEOVER || GAME.state === STATE.VICTORY) {
        if (k === 'R' || k === ' ' || k === 'Enter') GAME.startGame();
      }
    };
  },
  startGame: function () {
    P.init();
    ENEMY.arr = [];
    PROJ.arr = [];

    PICKUP.arr = [];
    SCORE.reset();
    PARTS.arr = [];
    WAVE.n = 1;
    WAVE.time = 0;
    WAVE.active = false;
    CAM.x = W.w / 2 - C.w / 2;
    CAM.y = W.h / 2 - C.h / 2;
    CAM.shake = 0;
    GAME.state = STATE.PLAYING;
    SCREEN.hide();
    SFX.init();
    SFX.musicStart();
    SFX.ui();
    WAVE.start(1);
    GAME.start();
  },
};

/* ============================================================= BOOT ---- */
const STATE_NAMES = { 0: 'MENU', 1: 'PLAYING', 2: 'PAUSED', 3: 'GAMEOVER', 4: 'VICTORY' };
const gameCanvas = $('game');
const gameCtx = gameCanvas.getContext('2d');
let errText = '';
let dbgName = '';
window.onerror = function (msg, url, ln) {
  errText = msg + ' (line ' + ln + ')' + (errText ? ' || ' + errText : '');
  errText = errText.slice(0, 500);
  if (location.search.indexOf('shot=1') >= 0 && dbgName) {
    fetch('/dbg?name=' + dbgName + '_err', { method: 'POST', body: errText }).catch(function () {});
  }
};
function dbgPost() {
  if (!dbgName || !fetch) return;
  try {
    fetch('/dbg?name=' + dbgName, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: JSON.stringify({
        state: STATE_NAMES[GAME.state], wave: WAVE.n, phase: WAVE.phase,
        enemies: ENEMY.arr.length, bullets: PROJ.arr.length, grenades: GRN.arr.length,
        pickups: PICKUP.arr.length, hp: P.hp, pos: [P.x | 0, P.y | 0],
        time: WAVE.time, kills: SCORE.kills, score: SCORE.score,
        combo: SCORE.combo, comboMult: SCORE.comboMult, err: errText
      })
    }).catch(function () {});
  } catch (e) { errText = 'dbg throw: ' + String(e) + ' ' + errText; }
}

WORLD.init();
PATH.build();
IN.init();
IN.onKey = GAME.inputKey();
loadAssets();

/* button bindings */
$('btnStart').addEventListener('click', function () { GAME.startGame(); });
$('btnResume').addEventListener('click', function () { GAME.state = STATE.PLAYING; SCREEN.hide(); SFX.ui(); });
$('btnRestart').addEventListener('click', function () { GAME.startGame(); });
$('btnPlayAgain').addEventListener('click', function () { GAME.startGame(); });
$('hud').style.display = 'none';
/* weapon slot click */
(function () {
  const slots = $('hud').querySelectorAll('.slot');
  for (let i = 0; i < slots.length; i++) {
    (function (el) {
      el.addEventListener('click', function () {
        P.weapon = parseInt(el.dataset.w, 10);
        P.mag = CFG.weapons[P.weapon].mag;
        SFX.ui();
      });
    })(slots[i]);
  }
})();

/* ---- TEST MODE ---- */
function parseTestMode() {
  const m = /t=(\d)/.exec(location.search);
  return m ? parseInt(m[1], 10) : 0;
}
const TEST_MODE = parseTestMode();
if (TEST_MODE) {
  const d = $('debug');
  d.className += ' show';
  setInterval(function () {
    d.textContent = 'TEST ' + TEST_MODE + ' | ' + STATE_NAMES[GAME.state] +
      ' | wave=' + WAVE.n + ' | enemies=' + ENEMY.arr.length +
      ' | hp=' + Math.ceil(P.hp) + ' | time=' + WAVE.time.toFixed(1) + 's | proj=' + PROJ.arr.length;
  }, 500);
  const holdM = /hold=(\d+(?:\.\d+)?)/.exec(location.search);
  const holdS = holdM ? parseFloat(holdM[1]) : 0;
  if (holdS > 0) {
    const img = document.createElement('img');
    img.src = '/img?hold=' + holdS;
    img.style.display = 'none';
    document.body.appendChild(img);
  }
  setTimeout(function () {
    GAME.startGame();
    if (TEST_MODE === 2) {
      /* kill Bert through the real death pipeline */
      setTimeout(function () { P.takeHit(P.maxHp + 1); }, 2000);
    } else if (TEST_MODE === 3) {
      setTimeout(function () { WAVE.start(6); WAVE.time = CFG.overload.at + 1; }, 1500);
    } else {
      /* t=1: auto-play with random actions (god-mode so the bot never dies, keeps action going) */
      /* true god-mode: also clear death so the bot never permanently dies */
      setInterval(function () {
        if (P) { P.hp = P.maxHp; P.dead = false; P.deathT = 0; P.inv = 0; }
      }, 100);
      setInterval(function () {
        IN.mx = Math.random() * C.w;
        IN.my = Math.random() * C.h;
        IN.mb[0] = true;
        if (Math.random() < .1) IN.mb[1] = true;
      }, 150);
      setInterval(function () {
        IN.mb[0] = false;
        IN.mb[1] = false;
      }, 150 + Math.random() * 400);
    }
  }, 300);
}

/* initial render: draw the village behind the menu overlay */
GAME.state = STATE.MENU;
GAME.raf = requestAnimationFrame(GAME.loop);
