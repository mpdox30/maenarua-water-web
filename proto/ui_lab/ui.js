/* Mae Na Rua UI Lab — prototype (ไม่ใช่ production). ไม่มี dependency ภายนอก; กราฟเป็น SVG เขียนเอง */
(function () {
'use strict';
const D = window.PROTO_DATA;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const MON = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const fmt = (v, d = 0) => Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const sgn = (v, d = 3) => (v > 0 ? '+' : v < 0 ? '−' : '±') + Math.abs(v).toFixed(d);
const fmtK = v => { const a = Math.abs(v); return a >= 1e6 ? (v / 1e6).toFixed(3) + 'M' : a >= 1e3 ? (v / 1e3).toFixed(1) + 'k' : String(Math.round(v * 10) / 10); };
const p2 = n => String(n).padStart(2, '0');
const fmtDT = d => `${d.getDate()} ${MON[d.getMonth()]} ${p2(d.getHours())}:${p2(d.getMinutes())}`;
const fmtD = s => { const d = new Date(s + 'T00:00:00'); return `${d.getDate()} ${MON[d.getMonth()]}`; };
const reduced = () => document.documentElement.dataset.motion === 'reduce' || matchMedia('(prefers-reduced-motion: reduce)').matches;
const safeLS = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };

function tween(from, to, dur, fn, ease) {
  ease = ease || (e => 1 - Math.pow(1 - e, 4)); // easeOutQuart
  if (reduced() || dur <= 0) { fn(to); return; }
  const t0 = performance.now();
  (function f(t) { const p = clamp((t - t0) / dur, 0, 1); fn(from + (to - from) * ease(p)); if (p < 1) requestAnimationFrame(f); })(t0);
}

/* =============== THEME =============== */
const PAL = [
  { id: 'blue', n: 'ฟ้าคราม', a: '#1f6f99', b: '#e0a94f' },
  { id: 'emerald', n: 'เขียวมรกต', a: '#1b8a6b', b: '#f0a23b' },
  { id: 'violet', n: 'ม่วงอเมทิสต์', a: '#6a4fc0', b: '#2fb8a3' },
  { id: 'sun', n: 'ส้มพระอาทิตย์', a: '#d9692b', b: '#2b8fb8' },
  { id: 'rose', n: 'ชมพูบานเย็น', a: '#cf3f7f', b: '#3aa0a8' },
  { id: 'gold', n: 'ทองสุริยา', a: '#b88a16', b: '#2a7f9e' }
];
const hex2rgb = h => { h = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(h.substr(i, 2), 16)); };
function rgb2hsl(r, g, b) {
  r /= 255; g /= 255; b /= 255; const mx = Math.max(r, g, b), mn = Math.min(r, g, b); let h = 0, s = 0; const l = (mx + mn) / 2;
  if (mx !== mn) { const d = mx - mn; s = l > .5 ? d / (2 - mx - mn) : d / (mx + mn);
    h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; }
  return [h, s, l];
}
const hsl = (h, s, l) => `hsl(${Math.round((h % 360 + 360) % 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%)`;
const lum = hex => { const [r, g, b] = hex2rgb(hex).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
const T = { pal: 'blue', custom: '#1f6f99', mode: 'auto', motion: '0' };
try { Object.assign(T, JSON.parse(safeLS.get('uilab_theme') || '{}')); } catch (e) {}
function isDark() {
  if (T.mode === 'dark') return true; if (T.mode === 'light') return false;
  const h = new Date().getHours(); return h >= 18 || h < 6; // auto = ตามเวลา (กลางคืน 18:00–06:00)
}
function applyTheme(save) {
  const root = document.documentElement;
  let a, b;
  if (T.pal === 'custom') {
    a = T.custom; const [h, s, l] = rgb2hsl(...hex2rgb(a)); b = hsl(h + 165, clamp(s, .45, .8), .55);
  } else { const p = PAL.find(x => x.id === T.pal) || PAL[0]; a = p.a; b = p.b; }
  root.style.setProperty('--accent', a); root.style.setProperty('--accent-2', b);
  root.style.setProperty('--accent-ink', lum(a) > .45 ? '#0b1c27' : '#ffffff');
  root.dataset.mode = isDark() ? 'dark' : 'light';
  root.dataset.motion = T.motion === '1' ? 'reduce' : 'normal';
  $$('#swatches .sw').forEach(b2 => b2.classList.toggle('on', b2.dataset.id === T.pal));
  $$('#modeSeg button').forEach(b2 => b2.classList.toggle('on', b2.dataset.m === T.mode));
  $$('#motionSeg button').forEach(b2 => b2.classList.toggle('on', b2.dataset.v === T.motion));
  $('#customColor').value = /^#[0-9a-f]{6}$/i.test(T.custom) ? T.custom : '#1f6f99';
  $$('.seg').forEach(placeInd);
  if (save) safeLS.set('uilab_theme', JSON.stringify(T));
}
function placeInd(seg) {
  const on = $('button.on', seg), ind = $('.ind', seg); if (!on || !ind) return;
  seg.style.setProperty('--x', on.offsetLeft + 'px'); seg.style.setProperty('--w', on.offsetWidth + 'px');
}
function initTheme() {
  $('#swatches').innerHTML = PAL.map(p => `<button class="sw" data-id="${p.id}"><b style="background:linear-gradient(135deg,${p.a} 50%,${p.b} 50%)"></b>${p.n}</button>`).join('');
  $('#swatches').addEventListener('click', e => { const b = e.target.closest('.sw'); if (!b) return; T.pal = b.dataset.id; applyTheme(true); });
  $('#customColor').addEventListener('input', e => { T.pal = 'custom'; T.custom = e.target.value; applyTheme(true); });
  $('#modeSeg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; T.mode = b.dataset.m; applyTheme(true); });
  $('#motionSeg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; T.motion = b.dataset.v; applyTheme(true); });
  const pop = $('#themePop'), btn = $('#themeBtn');
  const setOpen = o => { pop.classList.toggle('open', o); btn.setAttribute('aria-expanded', o); if (o) $$('.seg', pop).forEach(placeInd); };
  btn.addEventListener('click', e => { e.stopPropagation(); setOpen(!pop.classList.contains('open')); });
  document.addEventListener('click', e => { if (!pop.contains(e.target) && e.target !== btn) setOpen(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') setOpen(false); });
  applyTheme(false);
  matchMedia('(prefers-color-scheme: dark)').addEventListener && setInterval(() => { if (T.mode === 'auto') applyTheme(false); }, 60000);
}

/* =============== DATA HELPERS =============== */
const S = {}; D.stations.forEach(s => S[s.station_code] = s);
const R2 = S.RES002;
let ST = R2; // สถานีที่แสดงอยู่ (เปลี่ยนได้ด้วยตัวกรองในหน้า monitoring)
const CREST = D.crest, CAP = D.capacity_m3;
const short = s => s.name_th.replace('อ่างเก็บน้ำ', '');
const lastN = (arr, n) => arr.slice(Math.max(0, arr.length - n));
const delta6 = s => { const h = s.history; if (!h.length) return 0; const last = h[h.length - 1], t = new Date(last.t).getTime() - 6 * 3600e3; let ref = h[0]; for (let i = h.length - 1; i >= 0; i--) { if (new Date(h[i].t).getTime() <= t) { ref = h[i]; break; } } return last.level - ref.level; };
const rain24 = s => lastN(s.rain, 24).reduce((a, r) => a + (r.rain_mm || 0), 0);
const status = (lvl, crest) => { const d = lvl - crest; return d > 0.003 ? 'crit' : d > -0.10 ? 'warn' : 'ok'; };
const STATUS_TXT = { crit: 'เหนือสันสปิลเวย์', warn: 'ใกล้สัน', ok: 'ปกติ' };

/* =============== HERO SCENE =============== */
const Y0 = 380, Y1 = 80;
const G = { crest: CREST, E0: CREST - 2.045, E1: CREST + 1.455, max: D.max_level_seen, maxLabel: 'สูงสุดที่เคยบันทึก', crestWord: 'สันสปิลเวย์', damLabel: 'สันอ่าง (ภาพประกอบ)' };
const yOf = e => Y0 - (e - G.E0) / (G.E1 - G.E0) * (Y0 - Y1);
let Y_BASE = yOf(G.crest - 0.045);
const prng = (() => { let s = 7; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
function wavePath(y, amp, len, w, phase) {
  let d = `M${-200 + (phase || 0)},${y}`;
  for (let x = -200 + (phase || 0); x < w + 420; x += len) d += ` q${len / 4},${-amp} ${len / 2},0 t${len / 2},0`;
  return d + ` L${w + 440},${y + 700} L-220,${y + 700} Z`;
}
const PHASE_TXT = { day: 'กลางวัน', dusk: 'ช่วงเช้ามืด/พลบค่ำ', night: 'กลางคืน' };
function phaseOf(d) {
  const h = d.getHours() + d.getMinutes() / 60, day = h >= 6.5 && h < 17.5, dusk = (h >= 5.5 && h < 6.5) || (h >= 17.5 && h < 18.5), sun = h >= 5.5 && h < 18.5;
  const frac = sun ? (h - 5.5) / 13 : ((h < 5.5 ? h + 24 : h) - 18.5) / 11;
  return { cls: day ? 'day' : dusk ? 'dusk' : 'night', txt: day ? PHASE_TXT.day : dusk ? (h < 12 ? 'ช่วงเช้ามืด' : 'ช่วงพลบค่ำ') : PHASE_TXT.night, x: 110 + clamp(frac, 0, 1) * 680, y: 345 - Math.sin(Math.PI * clamp(frac, 0, 1)) * 295 };
}
let scene = {};
function buildScene() {
  Y_BASE = yOf(G.crest - 0.045);
  const yc = yOf(G.crest), yw = yOf(G.crest - 0.10), ym = yOf(G.max);
  const stars = Array.from({ length: 18 }, () => `<circle class="star" cx="${(prng() * 880 + 10).toFixed(0)}" cy="${(prng() * 150 + 8).toFixed(0)}" r="${(prng() * 1.4 + .6).toFixed(1)}" style="animation-delay:${(-prng() * 3).toFixed(1)}s"/>`).join('');
  const drops = Array.from({ length: 34 }, () => { const x = (prng() * 900).toFixed(0); return `<line class="drop" x1="${x}" y1="0" x2="${x - 5}" y2="15" style="animation-duration:${(.7 + prng() * .5).toFixed(2)}s;animation-delay:${(-prng() * 1.2).toFixed(2)}s"/>`; }).join('');
  const cloud = `<ellipse cx="0" cy="0" rx="46" ry="15"/><ellipse cx="-30" cy="6" rx="28" ry="11"/><ellipse cx="32" cy="7" rx="30" ry="11"/><ellipse cx="6" cy="-12" rx="26" ry="14"/>`;
  let ticks = ''; for (let e = Math.ceil(G.E0 * 2) / 2; e <= G.E1 + 0.001; e += 0.5) { const y = yOf(e); ticks += `<line x1="352" x2="${e % 1 === 0 ? 368 : 362}" y1="${y}" y2="${y}" style="stroke:var(--faint)" stroke-width="1.5"/><text class="tick-lbl" x="346" y="${y + 4}" text-anchor="end">${e.toFixed(1)}</text>`; }
  $('#scene').innerHTML = `
<svg viewBox="0 0 900 420" preserveAspectRatio="xMidYMid slice" id="sceneSvg">
<defs>
  <linearGradient id="gSky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--sky-1)"/><stop offset="1" style="stop-color:var(--sky-2)"/></linearGradient>
  <linearGradient id="gWater" gradientUnits="userSpaceOnUse" x1="0" y1="${Y_BASE}" x2="0" y2="${Y_BASE + 230}"><stop offset="0" style="stop-color:var(--water-1)"/><stop offset="1" style="stop-color:var(--water-2)"/></linearGradient>
  <radialGradient id="gOrb"><stop offset="0" style="stop-color:var(--orb-glow)"/><stop offset="1" style="stop-color:var(--orb-glow);stop-opacity:0"/></radialGradient>
  <clipPath id="basinClip"><rect x="0" y="0" width="700" height="420"/></clipPath>
</defs>
<rect width="900" height="420" fill="url(#gSky)"/>
${stars}
<g class="orb-g" id="orbG" style="transform:translate(170px,110px)"><circle class="sun-glow" cx="0" cy="0" r="74" fill="url(#gOrb)"/><circle cx="0" cy="0" r="22" style="fill:var(--orb)"/></g>
<path d="M0,230 C80,170 160,190 240,215 C320,240 400,160 520,180 C640,200 740,150 900,210 L900,420 L0,420Z" style="fill:var(--hill-far)"/>
<path d="M0,272 C100,232 200,262 300,287 C420,312 520,250 640,262 C740,272 820,242 900,264 L900,420 L0,420Z" style="fill:var(--hill-near)"/>
<g transform="translate(0,66)"><g class="cloud" style="fill:var(--core);opacity:.6">${cloud}</g></g>
<g transform="translate(0,128)"><g class="cloud c2" style="fill:var(--core);opacity:.45">${cloud}</g></g>
<g clip-path="url(#basinClip)"><g class="water-g" id="waterG">
  <path class="wave-b" d="${wavePath(Y_BASE - 3, 9, 200, 700, 40)}" style="fill:var(--water-1);opacity:.7"/>
  <g transform="translate(212,${Y_BASE})"><g class="boat"><path d="M-27,-3 L27,-3 L18,10 L-18,10Z" style="fill:var(--accent-2)"/><line x1="0" y1="-3" x2="0" y2="-44" style="stroke:var(--strong)" stroke-width="2"/><path d="M3,-42 L3,-9 L26,-9Z" style="fill:var(--core);stroke:var(--strong)" stroke-width="1.2"/><path d="M-3,-34 L-3,-9 L-17,-9Z" style="fill:var(--accent);opacity:.85"/></g></g>
  <path class="wave-a" d="${wavePath(Y_BASE, 6, 100, 700, 0)}" fill="url(#gWater)"/>
</g></g>
<path d="M0,420 L0,182 C60,178 112,238 190,300 C250,346 340,382 440,394 L440,420Z" style="fill:var(--land)"/>
<path d="M0,420 L0,246 C70,252 130,306 200,340 C270,372 350,396 440,404 L440,420Z" style="fill:var(--land-2);opacity:.7"/>
<path d="M430,398 L520,120 L580,120 L580,${yc} L700,${yc} L790,330 L900,330 L900,420 L430,420Z" style="fill:var(--land-2)"/>
<path d="M430,398 L520,120 L580,120 L580,${yc}" fill="none" style="stroke:var(--strong);opacity:.18" stroke-width="2"/>
<rect x="520" y="116" width="60" height="7" rx="3" style="fill:var(--core);stroke:var(--line-2)"/>
<rect x="580" y="${yc - 1}" width="120" height="7" rx="3" style="fill:var(--core);stroke:var(--line-2)"/>
<path d="M700,${yc + 3} L790,333 L800,333 L710,${yc + 3}Z" style="fill:var(--core);opacity:.85"/>
<g id="spillG"><path id="spillSheet" d="" style="fill:var(--water-1);opacity:.9"/>
  <path class="foam" d="M706,${yc - 3} L792,326"/><path class="foam" style="animation-delay:-.4s" d="M712,${yc - 9} L796,321"/></g>
<rect x="790" y="330" width="110" height="15" rx="6" style="fill:var(--water-1);opacity:.75"/>
<text class="lbl s" x="522" y="108" text-anchor="middle">${G.damLabel}</text>
<g>
  <line x1="0" x2="700" y1="${yc}" y2="${yc}" style="stroke:var(--crit)" stroke-width="1.8" stroke-dasharray="9 6"/>
  <text class="lbl s" x="14" y="${yc - 6}">${G.crestWord} ${G.crest.toFixed(3)} ม.</text>
  <line x1="0" x2="700" y1="${yw}" y2="${yw}" style="stroke:var(--warn)" stroke-width="1.5" stroke-dasharray="2 6" stroke-linecap="round"/>
  <text class="lbl s" x="14" y="${yw + 15}">เฝ้าระวัง ${(G.crest - .1).toFixed(3)} ม.</text>
  <line x1="0" x2="330" y1="${ym}" y2="${ym}" style="stroke:var(--faint)" stroke-width="1.2" stroke-dasharray="1 5" stroke-linecap="round"/>
  <text class="lbl s" x="14" y="${ym - 6}" style="fill:var(--muted)">${G.maxLabel} ${G.max.toFixed(3)} ม.</text>
</g>
<g id="gauge"><line x1="360" x2="360" y1="${Y1 - 6}" y2="${Y0 + 6}" style="stroke:var(--faint)" stroke-width="3" stroke-linecap="round"/>${ticks}
  <g class="lvl-tag" id="lvlTag" style="transform:translateY(${yOf(G.crest)}px)"><path d="M360,0 l12,-10 h62 a6,6 0 0 1 6,6 v8 a6,6 0 0 1 -6,6 h-62z" style="fill:var(--accent)"/><text id="lvlTagTxt" x="382" y="4.5" style="fill:var(--accent-ink,#fff);font:700 12.5px var(--font)">—</text></g>
</g>
<g id="rainG" style="pointer-events:none">${drops}</g>
</svg>`;
  scene.orb = $('#orbG'); scene.waterG = $('#waterG'); scene.tag = $('#lvlTag'); scene.tagTxt = $('#lvlTagTxt'); scene.sheet = $('#spillSheet'); scene.root = $('#scene'); scene.yc = yc;
}
let curLevel = null, prevCap = 0;
function setLevel(level, o) {
  o = o || {};
  const y = yOf(level), over = level - G.crest;
  scene.waterG.style.transform = `translateY(${y - Y_BASE}px)`;
  scene.tag.style.transform = `translateY(${y}px)`;
  scene.tagTxt.textContent = level.toFixed(3);
  const sp = over > 0.003; scene.root.classList.toggle('spilling', sp);
  const t = clamp(over * 90, 3, 24), yc = scene.yc;
  scene.sheet.setAttribute('d', sp ? `M700,${yc - t} L790,${330 - t} L790,330 L700,${yc}Z` : '');
  scene.root.classList.toggle('raining', !!o.rain);
  const ph = phaseOf(o.time || new Date()); ['day', 'dusk', 'night'].forEach(c => scene.root.classList.toggle(c, c === ph.cls)); scene.orb.style.transform = `translate(${ph.x.toFixed(0)}px,${ph.y.toFixed(0)}px)`;
  // readout
  const lv = $('#roLevel'); const from = curLevel == null ? level - 0.8 : curLevel;
  tween(from, level, o.instant ? 0 : 900, v => lv.textContent = v.toFixed(3)); curLevel = level;
  const st = status(level, G.crest), dl = $('#roDelta');
  dl.className = 'delta ' + st;
  dl.textContent = over > 0.003 ? `สูงกว่า${G.crestWord} ${over.toFixed(3)} ม.` : over > -0.10 ? `ต่ำกว่า${G.crestWord} ${(-over).toFixed(3)} ม. · ใกล้ล้น` : `ต่ำกว่า${G.crestWord} ${(-over).toFixed(3)} ม.`;
  $('#roName').textContent = o.name || 'อ่างเก็บน้ำแม่นาเรือ · RES002';
  $('#roTrend').textContent = o.trend || '';
  $('#roNote').innerHTML = o.note || '';
}
let RAT = null;
function ratingVol(h) { // ปริมาตร (ลบ.ม.) ณ ระดับน้ำ h: แม่นาเรือ = เส้นโค้งจากบัญชีน้ำจริง · อ่างอื่น = ประมาณเชิงเส้นรอบระดับปัจจุบัน
  if (ST === R2 && (D.allrows || []).length) {
    if (!RAT) { const m = new Map(); D.allrows.forEach(r => { if (r.level != null && r.volume != null) m.set(Math.round(r.level * 1000), r.volume); }); RAT = [...m.entries()].sort((a, b) => a[0] - b[0]).map(([k, v]) => [k / 1000, v]); }
    const R = RAT, n = R.length; if (n >= 2) { let i = 1; while (i < n - 1 && R[i][0] < h) i++; const [h0, v0] = R[i - 1], [h1, v1] = R[i]; return Math.max(0, v0 + (h - h0) * (v1 - v0) / ((h1 - h0) || 1e-9)); }
  }
  const vmax = ST.storage_max_m3 || 0, vnow = ST.storage_m3 || 0, hnow = ST.water_level, crest = G.crest, dh = crest - hnow;
  const slope = Math.abs(dh) > 0.02 ? (vmax - vnow) / dh : vmax / 3;
  return Math.max(0, vnow + (h - hnow) * slope);
}
function setCap(pct, instant) {
  if (!has('#roCapN')) return;
  const mx = Math.max(110, Math.ceil(pct / 10) * 10 + 5), n = $('#roCapN');
  tween(prevCap, pct, instant ? 0 : 700, v => n.textContent = v.toFixed(1)); prevCap = pct;
  $('#roCapNW').className = 'capn ' + (pct > 100 ? 'crit' : pct > 90 ? 'warn' : '');
  $('#roCapF').style.width = (Math.min(pct, 100) / mx * 100).toFixed(1) + '%';
  $('#roCapO').style.left = (100 / mx * 100).toFixed(1) + '%'; $('#roCapO').style.width = (Math.max(0, pct - 100) / mx * 100).toFixed(1) + '%';
  $('#roCapM').style.left = (100 / mx * 100).toFixed(1) + '%';
}
const capMax = () => ST === R2 ? CAP : (ST.storage_max_m3 || 1);
function liveReadout(instant) {
  if (ST.isKwan) {
    const k = D.kwan, c3 = k.change_3d, fl = { critical: 'วิกฤต', warning: 'เฝ้าระวัง', normal: 'ปกติ' }[k.flag] || k.flag;
    setLevel(ST.water_level, { instant, rain: false, name: `${ST.name_th} · ตลิ่ง ${k.bank.toFixed(3)} ม.`,
      trend: `3 วันที่ผ่านมา ${c3 > 0.004 ? 'ระดับขึ้น' : c3 < -0.004 ? 'ระดับลด' : 'ทรงตัว'} ${sgn(c3)} ม.`,
      note: `สถานะรวม <b>${fl}</b> · ตลิ่งฝั่งร้องไห้ ${k.bank_ronghai.toFixed(3)} ม. · ข้อมูล ${k.generated_at}` });
    return;
  }
  const d6 = delta6(ST), isMain = ST === R2, vol = isMain ? D.ledger[D.ledger.length - 1].volume : ST.storage_m3, capv = isMain ? CAP : ST.storage_max_m3;
  const raining = lastN(ST.rain, 2).some(r => r.rain_mm > 0);
  setLevel(ST.water_level, {
    instant, rain: raining, time: new Date(), name: `${ST.name_th} · ${ST.station_code}`,
    trend: `6 ชั่วโมงที่ผ่านมา ${d6 > 0.004 ? 'ระดับขึ้น' : d6 < -0.004 ? 'ระดับลด' : 'ทรงตัว'} ${sgn(d6)} ม.`,
    note: `ปริมาตร <b>${fmt(vol)}</b> / ${fmt(capv)} ลบ.ม. · ฝน 24 ชม. <b>${rain24(ST).toFixed(1)}</b> มม.`
  });
  setCap(ST.capacity_pct || 0, instant);
}

/* =============== KPI =============== */
const NUMS = {};
function initKPI() {
  const dirs = { up: [], down: [], flat: [] };
  D.stations.forEach(s => { const d = delta6(s); (d > 0.01 ? dirs.up : d < -0.01 ? dirs.down : dirs.flat).push(short(s)); });
  NUMS.up = dirs.up.length; NUMS.down = dirs.down.length; NUMS.flat = dirs.flat.length;
  $('#dirAvg').textContent = ['ขึ้น', 'ลด', 'ทรงตัว'].map((n, i) => { const l = [dirs.up, dirs.down, dirs.flat][i]; return l.length ? `${n}: ${l.join(', ')}` : ''; }).filter(Boolean).join(' · ');
  const L = D.ledger[D.ledger.length - 1];
  NUMS.cap = R2.capacity_pct; NUMS.spill = L.spill; NUMS.rain = rain24(R2); NUMS.in = L.inflow; NUMS.out = L.release;
  $('#capNote').textContent = `ปริมาตร ${fmt(L.volume)} / ${fmt(CAP)} ลบ.ม.${R2.capacity_pct > 100 ? ' · เกินความจุปกติ' : ''}`;
  $('#spillNote').textContent = L.spill > 0 ? `น้ำล้นผ่านสปิลเวย์ · บัญชีน้ำวันที่ ${fmtD(L.date)}` : `ไม่มีน้ำล้น · บัญชีน้ำวันที่ ${fmtD(L.date)}`;
  $('#bSpill').classList.toggle('alive', L.spill > 0);
  $('#rainNote').textContent = `ฝน 1 ชม. ล่าสุด ${(lastN(R2.rain, 1)[0] || {}).rain_mm || 0} มม. · บัญชีน้ำวันที่ ${fmtD(L.date)} ฝน ${L.rain} มม.`;
  const net = L.inflow - L.release;
  $('#balNote').textContent = `บัญชีน้ำวันที่ ${fmtD(L.date)} · สุทธิ ${net >= 0 ? '+' : '−'}${fmt(Math.abs(net))} ลบ.ม. (${net >= 0 ? 'ปริมาตรเพิ่ม' : 'ปริมาตรลด'}) · "ระบายรวม" นับน้ำล้นสปิลเวย์ด้วย`;
  // ring
  const C = 2 * Math.PI * 48, fg = $('#ringFg');
  if (R2.capacity_pct > 100) { const ov = fg.cloneNode(); ov.removeAttribute('id'); ov.setAttribute('class', 'fg ov'); ov.style.setProperty('--c', '0'); fg.after(ov); NUMS._ov = ov; }
}
function kpiIn(card) {
  $$('[data-num]', card).forEach(n => {
    const k = n.dataset.num, to = NUMS[k] || 0, dec = +(n.dataset.dec || 0);
    tween(0, to, 1500, v => n.textContent = fmt(v, dec));
  });
  if (card.id === 'bDir') {
    const m = { 'r-up': NUMS.up, 'r-down': NUMS.down, 'r-flat': NUMS.flat };
    for (const c in m) { const i = $('.' + c, card); i.style.setProperty('--g', m[c] || 0); if (!m[c]) i.style.display = 'none'; }
  }
  if (card.id === 'bCap') {
    const C = 2 * Math.PI * 48; $('#ringFg').style.setProperty('--c', (Math.min(R2.capacity_pct, 100) / 100 * C).toFixed(1));
    if (NUMS._ov) NUMS._ov.style.setProperty('--c', (clamp(R2.capacity_pct - 100, 0, 100) / 100 * C).toFixed(1));
  }
  if (card.id === 'bBal') {
    const L = D.ledger[D.ledger.length - 1], tot = L.inflow + L.release || 1;
    $('.balance .in', card).style.width = (L.inflow / tot * 100).toFixed(1) + '%'; $('.balance .out', card).style.width = (L.release / tot * 100).toFixed(1) + '%';
  }
}

/* =============== LEVEL HISTORY (ใช้เอฟเฟกต์แบบ river-profile: เส้นสันวาดเข้า + เส้นน้ำจุดไข่ปลา + แรเงาส่วนต่าง) =============== */
function smooth(pts, cmd) {
  if (pts.length < 2) return '';
  let d = `${cmd || 'M'}${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6], c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
}
let lvClip = null, lvW = 900, LV = null;
function lvCursor(t) {
  if (!has('#lvNow') || !LV) return; const g = $('#lvNow');
  const P = LV.pts, tt = t ? t.getTime() : NaN; if (!t || !P.length || tt < P[0].t || tt > P[P.length - 1].t) { g.style.opacity = 0; return; }
  let i = 1; while (i < P.length - 1 && P[i].t < tt) i++; const a = P[i - 1], b = P[i], f = b.t === a.t ? 0 : clamp((tt - a.t) / (b.t - a.t), 0, 1), lv = a.v + (b.v - a.v) * f, x = LV.xt(tt), y = LV.yv(lv);
  const lab = fmtDT(t), w = lab.length * 7.4 + 22, bx = clamp(x - w / 2, LV.xL - 6, LV.xR - w + 6);
  $('#lvNowL').setAttribute('x1', x); $('#lvNowL').setAttribute('x2', x); $('#lvNowD').setAttribute('cx', x); $('#lvNowD').setAttribute('cy', y);
  $('#lvNowB').setAttribute('x', bx); $('#lvNowB').setAttribute('width', w); $('#lvNowT').setAttribute('x', bx + w / 2); $('#lvNowT').textContent = lab; g.style.opacity = 1;
}
function buildLevels() {
  const H = ST.history, W = 900, HT = 360, xL = 62, xR = 868, yT = 40, yB = 290;
  const vals = H.map(h => h.level), lo0 = Math.min(...vals, G.crest), hi0 = Math.max(...vals, G.crest), pad = (hi0 - lo0) * .18 || .05;
  const lo = lo0 - pad, hi = hi0 + pad, yv = v => yB - (v - lo) / (hi - lo) * (yB - yT);
  const t0 = new Date(H[0].t).getTime(), t1 = new Date(H[H.length - 1].t).getTime(), xt = t => xL + (t - t0) / (t1 - t0) * (xR - xL);
  const pts = H.map(h => [xt(new Date(h.t).getTime()), yv(h.level)]), yc = yv(G.crest);
  const line = smooth(pts), area = line + ` L${pts[pts.length - 1][0].toFixed(1)},${yc.toFixed(1)} L${pts[0][0].toFixed(1)},${yc.toFixed(1)}Z`;
  let grid = '<g class="grid">', ax = '<g class="ax">';
  for (let i = 0; i <= 4; i++) { const v = lo + (hi - lo) * i / 4, y = yv(v); grid += `<line x1="${xL}" x2="${xR}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"/>`; ax += `<text x="${xL - 10}" y="${(y + 4).toFixed(1)}" text-anchor="end">${v.toFixed(2)}</text>`; }
  for (let t = new Date(t0), n = 0; t.getTime() <= t1; t = new Date(t.getTime() + 3600e3)) {
    if (t.getHours() === 0) { const x = xt(t.getTime()); grid += `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${yT}" y2="${yB}" style="stroke-dasharray:2 5"/>`; ax += `<text x="${x.toFixed(1)}" y="${yB + 22}" text-anchor="middle">${t.getDate()} ${MON[t.getMonth()]}</text>`; }
  }
  grid += '</g>'; ax += '</g>';
  const last = pts[pts.length - 1], over = ST.water_level - G.crest, col = 'var(--' + (status(ST.water_level, G.crest) === 'crit' ? 'crit' : status(ST.water_level, G.crest) === 'warn' ? 'warn' : 'ok') + ')';
  let imax = 0; vals.forEach((v, i) => { if (v > vals[imax]) imax = i; });
  const nearMax = Math.abs(pts[imax][0] - last[0]) < 190;
  $('#lvBox').innerHTML = `<svg viewBox="0 0 ${W} ${HT}" id="lvSvg" role="img" aria-label="ระดับน้ำ ${ST.station_code} ย้อนหลังเทียบสันสปิลเวย์">
  <defs><clipPath id="lvClip"><rect id="lvClipRect" x="0" y="0" width="0" height="${HT}"/></clipPath>
  <clipPath id="lvAbove"><rect x="0" y="0" width="${W}" height="${yc.toFixed(1)}"/></clipPath><clipPath id="lvBelow"><rect x="0" y="${yc.toFixed(1)}" width="${W}" height="${HT}"/></clipPath></defs>
  ${grid}${ax}
  <g clip-path="url(#lvClip)"><g clip-path="url(#lvAbove)"><path d="${area}" style="fill:var(--crit);opacity:.28"/></g><g clip-path="url(#lvBelow)"><path d="${area}" style="fill:var(--accent);opacity:.18"/></g>
    <path d="${line}" fill="none" style="stroke:var(--accent)" stroke-width="3.5" stroke-dasharray="1 8" stroke-linecap="round"/></g>
  <path class="draw" d="M${xL},${yc.toFixed(1)} L${xR},${yc.toFixed(1)}" fill="none" style="stroke:var(--bank)" stroke-width="3.5" stroke-linecap="round"/>
  <text class="ax fadein" x="${xR}" y="${(yc - 8).toFixed(1)}" text-anchor="end" style="fill:var(--bank);font:700 12.5px var(--font)">สันสปิลเวย์ ${G.crest.toFixed(3)} ม.</text>
  <g class="pdot" style="--d:1.9s"><circle class="sonar" cx="${last[0]}" cy="${last[1].toFixed(1)}" r="9" fill="none" style="stroke:${col}" stroke-width="2"/>
    <circle class="core" cx="${last[0]}" cy="${last[1].toFixed(1)}" r="9" style="fill:${col};stroke:var(--core)" stroke-width="3"/></g>
  <text class="fadein" x="${(last[0] - 16).toFixed(1)}" y="${(nearMax ? Math.min(yB - 6, last[1] + 30) : last[1] - 16).toFixed(1)}" text-anchor="end" style="fill:${col};font:700 14px var(--font);paint-order:stroke;stroke:var(--core);stroke-width:4px;stroke-linejoin:round">${ST.water_level.toFixed(3)} (${sgn(over, 2)})</text>
  <g class="pdot" style="--d:1.5s"><circle class="core" cx="${pts[imax][0].toFixed(1)}" cy="${pts[imax][1].toFixed(1)}" r="5.5" style="fill:var(--core);stroke:var(--accent)" stroke-width="3"/></g>
  <text class="ax fadein" x="${clamp(pts[imax][0], xL + 40, xR - 90).toFixed(1)}" y="${(pts[imax][1] - 14).toFixed(1)}" text-anchor="middle" style="fill:var(--strong);font:600 12.5px var(--font);paint-order:stroke;stroke:var(--core);stroke-width:4px;stroke-linejoin:round">สูงสุด ${vals[imax].toFixed(3)}</text>
  <g id="lvNow" style="opacity:0;transition:opacity .25s"><line id="lvNowL" y1="${yT - 4}" y2="${yB}" style="stroke:var(--accent-2)" stroke-width="2.6"/><circle id="lvNowD" r="7.5" style="fill:var(--accent-2);stroke:var(--core)" stroke-width="3"/><rect id="lvNowB" y="6" height="22" rx="9" style="fill:var(--strong)"/><text id="lvNowT" y="21.5" text-anchor="middle" style="fill:var(--core);font:700 12px var(--font)"></text></g>
  <g id="lvCross" style="opacity:0"><line id="lvCl" y1="${yT}" y2="${yB}" style="stroke:var(--line-2)" stroke-dasharray="3 4"/><circle id="lvCd" r="6" style="fill:var(--accent);stroke:var(--core)" stroke-width="2.5"/></g>
  <rect id="lvHit" x="${xL}" y="${yT}" width="${xR - xL}" height="${yB - yT}" fill="transparent"/></svg><div class="tt" id="lvTT"></div>`;
  lvClip = $('#lvClipRect'); LV = { xt, yv, xL, xR, W, pts: H.map(h => ({ t: new Date(h.t).getTime(), v: h.level })) };
  const svg = $('#lvSvg'), tt = $('#lvTT'), cr = $('#lvCross');
  $('#lvHit').addEventListener('mousemove', e => {
    const r = svg.getBoundingClientRect(), vx = (e.clientX - r.left) / r.width * W;
    let bi = 0, bd = 1e9; pts.forEach((p, i) => { const d = Math.abs(p[0] - vx); if (d < bd) { bd = d; bi = i; } });
    const p = pts[bi], h = H[bi], d = h.level - G.crest;
    cr.style.opacity = 1; $('#lvCl').setAttribute('x1', p[0]); $('#lvCl').setAttribute('x2', p[0]); $('#lvCd').setAttribute('cx', p[0]); $('#lvCd').setAttribute('cy', p[1]);
    tt.innerHTML = `<b>${fmtDT(new Date(h.t))}</b><br>ระดับ <b>${h.level.toFixed(3)}</b> ม.<br>${d > 0 ? 'สูงกว่าสัน' : 'ต่ำกว่าสัน'} ${Math.abs(d).toFixed(3)} ม.`;
    const bx = $('#lvBox').getBoundingClientRect(); let x = e.clientX - bx.left + 14; x = Math.min(x, bx.width - tt.offsetWidth - 4);
    tt.classList.add('on'); tt.style.left = Math.max(2, x) + 'px'; tt.style.top = Math.max(2, e.clientY - bx.top - 16 - tt.offsetHeight) + 'px';
  });
  $('#lvHit').addEventListener('mouseleave', () => { cr.style.opacity = 0; tt.classList.remove('on'); });
  lvW = W;
}
function levelsIn(box) { box.classList.add('drawn'); tween(0, lvW, 2200, v => lvClip.setAttribute('width', v.toFixed(0))); }

/* =============== DAILY BARS (+delta +mascot) =============== */
const DM = {
  inflow: { label: 'น้ำไหลเข้า', unit: 'ลบ.ม./วัน', dec: 0 },
  release: { label: 'น้ำระบายรวม (ท่อ+ล้น)', unit: 'ลบ.ม./วัน', dec: 0 },
  rain: { label: 'ฝน', unit: 'มม.', dec: 1 },
  volume: { label: 'ปริมาตรกักเก็บ', unit: 'ลบ.ม.', dec: 0 }
};
let dailyKey = 'inflow', dailyStarted = false;
const mascot = (x, y) => `<g transform="translate(${x},${y})"><g class="mascot"><path d="M0,-30 C10,-15 15,-8 15,0 A15,15 0 0 1 -15,0 C-15,-8 -10,-15 0,-30Z" style="fill:var(--accent);stroke:var(--core)" stroke-width="2"/>
  <ellipse cx="-5" cy="-9" rx="3" ry="6" fill="#fff" opacity=".55"/><circle cx="-5" cy="-1" r="2.2" fill="#fff"/><circle cx="5" cy="-1" r="2.2" fill="#fff"/><circle cx="-4.6" cy="-1" r=".9" fill="#0b1c27"/><circle cx="5.4" cy="-1" r=".9" fill="#0b1c27"/>
  <path d="M-4,5 Q0,9 4,5" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/></g></g>`;
function renderDaily(k) {
  dailyKey = k; const m = DM[k], rows = D.ledger.slice(-14), vals = rows.map(r => r[k]);
  const W = 900, H = 340, base = 290, left = 14, slot = (W - left * 2) / rows.length, bw = slot * .58, maxH = 168;
  const mx = Math.max(...vals, 1e-9);
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="กราฟแท่งรายวัน ${m.label}"><g class="grid">`;
  for (let i = 0; i <= 3; i++) { const y = base - maxH * i / 3 * 1; svg += `<line x1="${left}" x2="${W - left}" y1="${y}" y2="${y}"/>`; }
  svg += '</g>';
  let tips = '';
  rows.forEach((r, i) => {
    const v = vals[i], h = Math.max(2, v / mx * maxH), x = left + i * slot + (slot - bw) / 2, cx = x + bw / 2, top = base - h, last = i === rows.length - 1;
    const prev = i ? vals[i - 1] : null, d = prev == null ? null : v - prev;
    const dir = d == null ? null : Math.abs(d) < (k === 'rain' ? 0.05 : Math.max(1, Math.abs(prev) * 0.003)) ? 'flat' : d > 0 ? 'up' : 'down';
    const lift = last ? 36 : 0;
    const dtxt = dir == null ? '' : dir === 'flat' ? '● เท่าเดิม' : `${dir === 'up' ? '▲' : '▼'} ${d > 0 ? '+' : '−'}${k === 'rain' ? Math.abs(d).toFixed(1) : fmtK(Math.abs(d))}`;
    const tip = `<b>${fmtD(r.date)}</b><br>${m.label} <b>${fmt(v, m.dec)}</b> ${m.unit}${d == null ? '' : `<br>เทียบวันก่อน ${d > 0 ? '+' : '−'}${fmt(Math.abs(d), m.dec)}`}<br>ฝน ${r.rain} มม. · ระดับ ${r.level.toFixed(3)} ม.`;
    svg += `<g data-tip="${tip}"><rect class="bar" x="${x.toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="9" style="fill:var(--accent);opacity:${last ? 1 : .5};--d:${(i * .04).toFixed(2)}s;transform:scaleY(0)"/>
      <rect x="${(x - 4).toFixed(1)}" y="${(top - 60).toFixed(1)}" width="${(bw + 8).toFixed(1)}" height="${(h + 60).toFixed(1)}" fill="transparent"/></g>`;
    svg += `<text class="bar-lbl fadein" x="${cx.toFixed(1)}" y="${(top - 9 - lift).toFixed(1)}">${k === 'rain' ? v.toFixed(1) : fmtK(v)}</text>`;
    if (dtxt) svg += `<text class="bar-delta fadein" x="${cx.toFixed(1)}" y="${(top - 25 - lift).toFixed(1)}" style="fill:var(--${dir})">${dtxt}</text>`;
    if (last) svg += `<g class="fadein">${mascot(cx.toFixed(1), (top - 3).toFixed(1))}</g>`;
    svg += `<text class="ax" x="${cx.toFixed(1)}" y="${base + 20}" text-anchor="middle" style="fill:${last ? 'var(--strong)' : 'var(--faint)'};font:${last ? '700' : '400'} 12px var(--font)">${new Date(r.date + 'T00:00:00').getDate()}</text>`;
    if (i === 0 || new Date(r.date + 'T00:00:00').getDate() === 1) svg += `<text class="ax" x="${cx.toFixed(1)}" y="${base + 36}" text-anchor="middle">${MON[new Date(r.date + 'T00:00:00').getMonth()]}</text>`;
  });
  svg += `</svg><div class="tt" id="dailyTT"></div>`;
  const box = $('#dailyBox'); box.innerHTML = svg; box.classList.remove('drawn');
  const L = rows[rows.length - 1], prev = rows[rows.length - 2];
  $('#dailyTitle').textContent = `${m.label} · วันที่ ${fmtD(L.date)}`;
  $('#dailyBig').innerHTML = `${fmt(L[k], m.dec)} <small style="font-size:14px;color:var(--muted);font-weight:500">${m.unit}</small>`;
  if (dailyStarted) requestAnimationFrame(() => requestAnimationFrame(() => { $$('.bar', box).forEach(b => b.style.transform = 'scaleY(1)'); box.classList.add('drawn'); }));
}
function dailyIn() { dailyStarted = true; renderDaily(dailyKey); }

/* =============== FORECAST (cosine-interpolated curve) =============== */
function buildForecast() {
  const F = D.forecast, W = 900, H = 340, x0 = 70, x1 = 830, yb = 270, yt = 56;
  const mx = Math.max(...F.map(f => f.v)) * 1.12, y = v => yb - v / mx * (yb - yt), x = i => x0 + i * (x1 - x0) / (F.length - 1);
  const pts = []; for (let i = 0; i < F.length - 1; i++) for (let s = 0; s < 20; s++) { const t = s / 20, w = (1 - Math.cos(Math.PI * t)) / 2; pts.push([x(i + t), y(F[i].v + (F[i + 1].v - F[i].v) * w)]); }
  pts.push([x(F.length - 1), y(F[F.length - 1].v)]);
  const line = 'M' + pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' L');
  const area = line + ` L${x(F.length - 1)},${yb} L${x0},${yb}Z`;
  let grid = '<g class="grid">'; for (let i = 0; i <= 4; i++) { const v = mx * i / 4; grid += `<line x1="${x0 - 14}" x2="${x1 + 14}" y1="${y(v)}" y2="${y(v)}"/>`; }
  grid += '</g><g class="ax">'; for (let i = 0; i <= 4; i++) { const v = mx * i / 4; grid += `<text x="${x0 - 22}" y="${y(v) + 4}" text-anchor="end">${fmtK(v)}</text>`; } grid += '</g>';
  const dots = F.map((f, i) => {
    const now = i === 0, cx = x(i), cy = y(f.v);
    const tip = now ? `<b>ตอนนี้</b> (${fmtD(f.date)})<br>น้ำไหลเข้า ${fmt(f.v)} ลบ.ม./วัน<br>จากบัญชีน้ำล่าสุด` : `<b>${fmtD(f.date)} (+${f.h} วัน)</b><br>พยากรณ์ ${fmt(f.v)} ลบ.ม./วัน<br>${f.low ? 'ความเชื่อมั่นต่ำ' : 'ความเชื่อมั่นปกติ'}`;
    return `<g data-tip="${tip}">${now ? `<circle class="sonar" cx="${cx}" cy="${cy}" r="9" fill="none" style="stroke:var(--accent)" stroke-width="2"/>` : ''}
      <circle cx="${cx}" cy="${cy}" r="${now ? 8 : 6}" style="fill:${f.low && !now ? 'var(--core)' : 'var(--accent)'};stroke:${now ? 'var(--accent-2)' : 'var(--accent)'}" stroke-width="3" ${f.low && !now ? 'stroke-dasharray="3 2"' : ''} class="fadein"/>
      <circle cx="${cx}" cy="${cy}" r="20" fill="transparent"/>
      <text class="bar-lbl fadein" x="${cx}" y="${cy - 16}">${fmtK(f.v)}</text>
      <text class="ax" x="${cx}" y="${yb + 22}" text-anchor="middle" style="fill:${now ? 'var(--strong)' : 'var(--faint)'};font:${now ? '700' : '400'} 12px var(--font)">${now ? 'ตอนนี้' : '+' + f.h + ' วัน'}</text>
      <text class="ax" x="${cx}" y="${yb + 38}" text-anchor="middle">${fmtD(f.date)}</text></g>`;
  }).join('');
  $('#fcBox').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="กราฟพยากรณ์น้ำไหลเข้า">
  <defs><linearGradient id="gFc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--accent);stop-opacity:.35"/><stop offset="1" style="stop-color:var(--accent);stop-opacity:0"/></linearGradient></defs>
  ${grid}<line x1="${x0}" x2="${x0}" y1="${yt - 18}" y2="${yb}" style="stroke:var(--accent-2)" stroke-width="1.6" stroke-dasharray="5 5"/>
  <text class="ax" x="${x0 + 8}" y="${yt - 22}" style="fill:var(--accent-2);font-weight:700">ค่าจริงล่าสุด → พยากรณ์</text>
  <path class="fadein" d="${area}" fill="url(#gFc)"/><path class="draw" d="${line}" fill="none" style="stroke:var(--accent)" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
  ${dots}</svg><div class="tt" id="fcTT"></div>`;
  const nLow = F.filter(f => f.low).length;
  $('#fcNote').textContent = `หน่วย ลบ.ม./วัน · วงกลมโปร่งประ = พยากรณ์ความเชื่อมั่นต่ำ (${nLow} จาก ${F.length - 1} จุด) · เส้นโค้งระหว่างจุดเป็นการประมาณค่าเพื่อการแสดงผล ไม่ใช่ค่าพยากรณ์รายชั่วโมง`;
}

/* =============== STATION TABLE =============== */
function spark(vals, color) {
  const w = 88, h = 26, mn = Math.min(...vals), mxv = Math.max(...vals), rg = (mxv - mn) || 1;
  const d = vals.map((v, i) => `${i ? 'L' : 'M'}${(i / (vals.length - 1) * (w - 4) + 2).toFixed(1)},${(h - 3 - (v - mn) / rg * (h - 6)).toFixed(1)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}"><path class="draw" d="${d}" style="stroke:var(${color})"/></svg>`;
}
function buildTable() {
  const rows = D.stations.map(s => {
    const crest = s.station_code === 'RES002' ? CREST : s.spillway_msl, d6 = delta6(s), st = status(s.water_level, crest);
    const col = d6 > 0.01 ? '--up' : d6 < -0.01 ? '--down' : '--flat';
    return `<tr><td><b style="color:var(--strong)">${short(s)}</b><br><small style="color:var(--faint)">${s.station_code} · สันสปิลเวย์ ${crest.toFixed(3)}</small></td>
      <td>${s.water_level.toFixed(3)}</td><td>${spark(lastN(s.history, 48).map(h => h.level), col)}</td>
      <td style="color:var(${col})">${sgn(d6)}</td><td>${rain24(s).toFixed(1)} มม.</td><td>${s.capacity_pct.toFixed(1)}%</td><td><span class="badge ${st}">${STATUS_TXT[st]}</span></td></tr>`;
  });
  const k = D.kwan, kst = k.level > k.bank ? 'crit' : k.level > k.bank - .1 ? 'warn' : 'ok';
  rows.push(`<tr><td><b style="color:var(--strong)">กว๊านพะเยา</b><br><small style="color:var(--faint)">ตลิ่ง ${k.bank.toFixed(3)}</small></td><td>${k.level.toFixed(3)}</td><td style="color:var(--faint)">—</td>
    <td>${sgn(k.change_3d)} <small style="color:var(--faint)">(3 วัน)</small></td><td>—</td><td>—</td><td><span class="badge ${kst}">${kst === 'crit' ? 'เหนือตลิ่ง' : kst === 'warn' ? 'ใกล้ตลิ่ง' : 'ปกติ'}</span></td></tr>`);
  $('#stBody').innerHTML = rows.join('');
}

/* =============== TOOLTIP (delegated) =============== */
function bindTips(boxSel, ttSel) {
  const box = $(boxSel), tt = $(ttSel); if (!box || !tt) return;
  box.addEventListener('mousemove', e => {
    const g = e.target.closest('[data-tip]'); if (!g) { tt.classList.remove('on'); return; }
    tt.innerHTML = g.getAttribute('data-tip').replace(/&quot;/g, '"');
    const r = box.getBoundingClientRect(); let x = e.clientX - r.left + 14, y = e.clientY - r.top - 16;
    tt.classList.add('on'); x = Math.min(x, r.width - tt.offsetWidth - 4); tt.style.left = Math.max(2, x) + 'px'; tt.style.top = Math.max(2, y - tt.offsetHeight) + 'px';
  });
  box.addEventListener('mouseleave', () => tt.classList.remove('on'));
}

/* =============== LIVE BADGE =============== */
function updateLive() {
  const t = new Date(ST.measure_datetime || D.monitoring_updated), age = Date.now() - t.getTime(), mins = Math.max(0, Math.round(age / 60000));
  const ago = mins < 1 ? 'เมื่อสักครู่' : mins < 60 ? `${mins} นาทีที่แล้ว` : mins < 2880 ? `${Math.round(mins / 60)} ชม.ที่แล้ว` : `${Math.round(mins / 1440)} วันที่แล้ว`;
  const b = $('#live'); b.className = 'live' + (mins > 120 ? ' stale' : mins > 30 ? ' warn' : '');
  $('#liveText').textContent = `ข้อมูลโทรมาตร ${fmtDT(t)} · ${ago}${mins > 120 ? ' (snapshot เก่า)' : ''}`;
  $('#snap').textContent = fmtDT(new Date(D.snapshot));
}

/* =============== TIME DOCK (ย้อนดูข้อมูล: ระดับน้ำ + ฝน + กลางวัน/กลางคืน) =============== */
const DOCK = { series: [], timer: null };
function dockSeries() {
  if (ST === R2 && D.windows && D.windows.length) return D.windows.map(w => ({ t: new Date(w.window_end), s: new Date(w.window_start), level: w.water_level_end_m, lvStart: w.water_level_start_m, rain: w.rain_6h_mm || 0,
    note: `น้ำไหลเข้า <b>${fmt(w.q_in_6h_m3)}</b> ลบ.ม. · ระบายท่อ <b>${fmt(w.release_6h_m3)}</b> · ล้นสปิลเวย์ <b>${fmt(w.spill_6h_m3)}</b> · ฝน <b>${w.rain_6h_mm}</b> มม.` }));
  const H = (ST.history || []).filter(h => h.level != null).map(h => ({ t: new Date(h.t).getTime(), v: h.level })).sort((a, b) => a.t - b.t); if (H.length < 2) return [];
  const hr = 3600e3, end = H[H.length - 1].t, st = Math.max(H[0].t, end - 84 * hr), out = [];
  const levelAt = t => { let v = H[0].v; for (let i = 0; i < H.length; i++) { if (H[i].t <= t) v = H[i].v; else break; } return v; };
  const rainSum = (a, b) => (ST.rain || []).filter(r => { const x = new Date(r.t).getTime(); return x > a && x <= b; }).reduce((q, r) => q + (r.rain_mm || 0), 0);
  const mk = t => { const r6 = rainSum(t - 6 * hr, t); return { t: new Date(t), s: new Date(t - 6 * hr), level: levelAt(t), lvStart: levelAt(t - 6 * hr), rain: r6, note: `ฝน 6 ชม.ก่อนหน้า <b>${r6.toFixed(1)}</b> มม.` }; };
  for (let t = Math.ceil(st / hr) * hr; t < end; t += hr) out.push(mk(t));
  out.push(mk(end)); return out;
}
const PH_COL = { day: '#f6d77f', dusk: '#ee9a5a', night: '#27365a' };
function rebuildDock() {
  if (!has('#slider')) return;
  const sr = DOCK.series = dockSeries(), n = sr.length, sl = $('#slider'), svg = $('#dockStrip');
  sl.max = Math.max(0, n - 1); sl.value = sl.max; sl.disabled = n < 2; DOCK.stop && DOCK.stop();
  svg.setAttribute('viewBox', `0 0 ${Math.max(1, n)} 34`);
  svg.innerHTML = sr.map((p, i) => { const ph = phaseOf(p.t), hh = p.rain > 0 ? Math.min(20, 3 + p.rain * 0.9) : 0;
    return `<rect x="${i}" y="23" width="1.02" height="11" fill="${PH_COL[ph.cls]}" opacity=".9"/>${hh ? `<rect x="${i}" y="${(21 - hh).toFixed(1)}" width="1.02" height="${hh.toFixed(1)}" style="fill:var(--rain)" opacity=".85"/>` : ''}`; }).join('');
  $('#dockSub').textContent = n > 1 ? `ย้อนดู ${Math.round((sr[n - 1].t - sr[0].t) / 3600e3)} ชม. · ฟ้า = ฝน · เหลือง/น้ำเงิน = วัน/คืน` : 'ไม่มีข้อมูลย้อนหลังพอ';
  DOCK.apply && DOCK.apply(sl.max);
}
function initDock() {
  if (!has('#slider')) return;
  const sl = $('#slider'), lbl = $('#dockLbl'), play = $('#play'), icon = $('#playIc');
  const PLAY = 'M8 5v14l11-7z', PAUSE = 'M7 5h4v14H7zM13 5h4v14h-4z';
  const stop = DOCK.stop = () => { clearInterval(DOCK.timer); DOCK.timer = null; icon.setAttribute('d', PLAY); };
  const apply = DOCK.apply = i => {
    const sr = DOCK.series, n = sr.length; i = +i;
    if (!n || i >= n - 1) { const ph = phaseOf(new Date()); lbl.textContent = `ปัจจุบัน · ${ph.txt}`; $('#roCapL').textContent = 'เส้นขีด = 100% (ระดับสันสปิลเวย์)'; lvCursor(null); liveReadout(false); return; }
    const p = sr[i], dl = p.level - p.lvStart, ph = phaseOf(p.t), vol = ratingVol(p.level), capv = capMax(); lbl.textContent = `${fmtDT(p.t)} · ${ph.txt}`;
    setLevel(p.level, { rain: p.rain > 0, time: p.t, name: `ย้อนดู · ${fmtDT(p.s)} → ${fmtDT(p.t)}`,
      trend: `ใน 6 ชม. ระดับ ${dl > 0.004 ? 'ขึ้น' : dl < -0.004 ? 'ลด' : 'ทรงตัว'} ${sgn(dl)} ม.`,
      note: `ปริมาตร ${ST === R2 ? '' : '≈ '}<b>${fmt(vol)}</b> / ${fmt(capv)} ลบ.ม.<br>${p.note}` });
    setCap(vol / capv * 100, false); $('#roCapL').textContent = ST === R2 ? 'ปริมาตร ณ เวลานั้น (จากเส้นโค้งระดับ–ปริมาตรในบัญชีน้ำ)' : 'ปริมาตร ณ เวลานั้น (ประมาณจากระดับ)'; lvCursor(p.t);
  };
  sl.addEventListener('input', () => { stop(); apply(sl.value); });
  play.addEventListener('click', () => {
    if (DOCK.timer) { stop(); return; }
    if (+sl.value >= +sl.max) sl.value = 0;
    icon.setAttribute('d', PAUSE);
    DOCK.timer = setInterval(() => { sl.value = +sl.value + 1; apply(sl.value); if (+sl.value >= +sl.max) stop(); }, reduced() ? 900 : 380);
    apply(sl.value);
  });
  $('#toLive').addEventListener('click', () => { stop(); sl.value = sl.max; apply(sl.max); });
  rebuildDock();
}

/* =============== REVEAL / NAV =============== */
function initReveal() {
  const hooks = (card) => {
    kpiIn(card);
    if ($('#lvBox', card)) levelsIn($('#lvBox'));
    if ($('#dailyBox', card)) dailyIn();
    if ($('#fcBox', card)) $('#fcBox').classList.add('drawn');
    if ($('#stBody', card) || $('#resBody', card)) card.classList.add('drawn');
    if ($('#rainBox', card)) growRain();
  };
  const show = el => { if (el.classList.contains('in')) return; el.classList.add('in'); hooks(el); };
  const items = $$('.rv');
  if (!('IntersectionObserver' in window) || reduced()) { items.forEach(show); return; }
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { show(e.target); io.unobserve(e.target); } }), { threshold: .15 });
  items.forEach(i => io.observe(i));
  const links = $$('.nav a.lnk'), secs = links.map(a => $(a.getAttribute('href')));
  const so = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { const i = secs.indexOf(e.target); links.forEach((l, j) => l.classList.toggle('on', j === i)); } }), { rootMargin: '-40% 0px -55% 0px' });
  secs.forEach(s => s && so.observe(s));
}

/* =============== STATION MODULE (ตัวกรองอ่าง + ข้อมูลสถานีโทรมาตรครบ) =============== */
const has = sel => { const e = $(sel); return !!e && typeof e.nodeType === 'number'; };
const ICON = {
  drop: '<path d="M12 3c3 4 6 7 6 11a6 6 0 0 1-12 0c0-4 3-7 6-11Z"/>', temp: '<path d="M14 14V5a2 2 0 0 0-4 0v9a4 4 0 1 0 4 0Z"/>',
  hum: '<path d="M12 3c3 4 6 7 6 11a6 6 0 0 1-12 0c0-4 3-7 6-11Z"/><path d="M9 14a3 3 0 0 0 3 3"/>', gauge: '<path d="M4 16a8 8 0 1 1 16 0"/><path d="M12 16l4-5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>', ruler: '<path d="M3 17 17 3l4 4L7 21z"/><path d="M8 12l2 2M11 9l2 2M14 6l2 2"/>',
  tank: '<path d="M4 8c0-2 4-3 8-3s8 1 8 3v9c0 2-4 3-8 3s-8-1-8-3z"/><path d="M4 8c0 2 4 3 8 3s8-1 8-3"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'
};
const ic = k => `<span class="t-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICON[k]}</svg></span>`;
const agoTxt = t => { const m = Math.max(0, Math.round((Date.now() - new Date(t).getTime()) / 60000)); return m < 1 ? 'เมื่อสักครู่' : m < 60 ? `${m} นาทีที่แล้ว` : m < 2880 ? `${Math.round(m / 60)} ชม.ที่แล้ว` : `${Math.round(m / 1440)} วันที่แล้ว`; };
function setStationScale() {
  const s = ST, crest = s === R2 ? CREST : s.spillway_msl, hs = s.history.map(h => h.level).concat([s.water_level]);
  G.crest = crest; G.E0 = Math.min(crest - 2.045, Math.min(...hs) - 0.3); G.E1 = Math.max(crest + 1.455, Math.max(...hs) + 0.4);
  G.max = s === R2 ? Math.max(D.max_level_seen, ...hs) : Math.max(...hs); G.maxLabel = s === R2 ? 'สูงสุดที่เคยบันทึก' : 'สูงสุดในช่วงข้อมูลที่มี';
  G.crestWord = 'สันสปิลเวย์'; G.damLabel = 'สันอ่าง (ภาพประกอบ)';
  if (s.isKwan) { G.max = D.kwan.bank_ronghai; G.maxLabel = 'ตลิ่งฝั่งร้องไห้'; G.crestWord = 'ตลิ่ง'; G.damLabel = 'ขอบตลิ่ง (ภาพประกอบ)'; G.E0 = Math.min(G.E0, G.max - 0.3); }
}
function teleTiles() {
  const s = ST, crest = G.crest, f = (v) => v == null ? null : Number(v);
  const r1 = s.rainfall_1h || 0, r24 = rain24(s), r72 = lastN(s.rain, 72).reduce((a, r) => a + (r.rain_mm || 0), 0);
  const dist = s.distance_to_spillway_m != null ? s.distance_to_spillway_m : s.water_level - crest, cap = s.capacity_pct || 0;
  return [
    { k: 'drop', lb: 'ฝน 1 ชม.', v: r1, dec: 1, u: 'มม.', p: Math.min(1, r1 / 20), sub: `ฝน 24 ชม. ${r24.toFixed(1)} มม. · 72 ชม. ${r72.toFixed(1)} มม.` },
    { k: 'temp', lb: 'อุณหภูมิ', v: f(s.temperature), dec: 1, u: '°C', p: clamp((s.temperature - 10) / 30, 0, 1), sub: 'แถบเทียบช่วง 10–40 °C' },
    { k: 'hum', lb: 'ความชื้น', v: f(s.humidity), dec: 1, u: '%', p: clamp(s.humidity / 100, 0, 1), sub: s.humidity >= 85 ? 'อากาศชื้นมาก' : s.humidity < 50 ? 'อากาศแห้ง' : 'ความชื้นปกติ' },
    { k: 'gauge', lb: 'ความกดอากาศ', v: f(s.pressure), dec: 1, u: 'hPa', p: clamp((s.pressure - 940) / 50, 0, 1), sub: 'ที่ระดับสถานี · แถบเทียบช่วง 940–990' },
    { k: 'sun', lb: 'รังสีแสงอาทิตย์', v: f(s.solar), dec: 1, u: 'W/m²', p: clamp(s.solar / 1000, 0, 1), sub: 'แถบเทียบช่วง 0–1000 W/m²' },
    { k: 'ruler', lb: 'ห่างจากสันสปิลเวย์', v: dist, dec: 2, u: 'ม.', sign: true, p: clamp(1 - Math.abs(dist) / 2, 0, 1), sub: dist > 0.003 ? 'ระดับน้ำสูงกว่าสัน' : 'ระดับน้ำต่ำกว่าสัน', cls: dist > 0.003 ? 'over' : '' },
    { k: 'tank', lb: 'ปริมาตรกักเก็บ', v: cap, dec: 1, u: '% ความจุ', p: clamp(cap / 100, 0, 1), sub: `${fmt(s.storage_m3)} / ${fmt(s.storage_max_m3)} ลบ.ม.`, cls: cap > 100 ? 'over' : '' },
    { k: 'clock', lb: 'วัดล่าสุด', txt: fmtDT(new Date(s.measure_datetime)), sub: agoTxt(s.measure_datetime) + ' · อัปเดตทุก ~10 นาที' }
  ];
}
function buildTele() {
  if (!has('#teleBox')) return;
  $('#teleBox').innerHTML = teleTiles().filter(t => t.k !== 'clock' && t.k !== 'tank').map((t, i) => `<div class="tile" title="${t.sub}" style="--d:${(i * .05).toFixed(2)}s">
    <div class="t-top">${ic(t.k)}<span>${t.lb}</span></div>
    <div class="t-num">${t.txt ? `<span style="font-size:20px">${t.txt}</span>` : `<span class="cu" data-to="${t.v == null ? '' : t.v}" data-dec="${t.dec}" data-sign="${t.sign ? 1 : 0}">${t.v == null ? '—' : '0'}</span><small>${t.u}</small>`}</div>
    ${t.txt ? '' : `<div class="t-bar${t.cls ? ' ' + t.cls : ''}"><i data-p="${(t.p * 100).toFixed(1)}"></i></div>`}<div class="t-sub">${t.sub}</div></div>`).join('');
  $$('.cu', $('#teleBox')).forEach(n => { const to = parseFloat(n.dataset.to); if (!isFinite(to)) return; const dec = +n.dataset.dec, sg = n.dataset.sign === '1';
    tween(0, to, 1300, v => { n.textContent = sg ? (v > 0.0049 ? '+' : v < -0.0049 ? '−' : '') + fmt(Math.abs(v), dec) : fmt(v, dec); });
  });
  requestAnimationFrame(() => requestAnimationFrame(() => $$('.t-bar i', $('#teleBox')).forEach(i => i.style.width = i.dataset.p + '%')));
}
let rainBars = [];
function buildRain() {
  if (!has('#rainBox')) return;
  const R = lastN(ST.rain, 72), W = 900, H = 250, xL = 44, xR = 884, yB = 196, yT = 30, mx = Math.max(4, ...R.map(r => r.rain_mm || 0)), slot = (xR - xL) / Math.max(1, R.length), bw = slot * .72, tot = R.reduce((a, r) => a + (r.rain_mm || 0), 0);
  let g = '<g class="grid">', ax = '<g class="ax">';
  [0, .5, 1].forEach(f => { const y = yB - f * (yB - yT); g += `<line x1="${xL}" x2="${xR}" y1="${y}" y2="${y}"/>`; ax += `<text x="${xL - 8}" y="${y + 4}" text-anchor="end">${(mx * f).toFixed(mx < 10 ? 1 : 0)}</text>`; });
  let bars = '';
  R.forEach((r, i) => {
    const v = r.rain_mm || 0, x = xL + i * slot + (slot - bw) / 2, h = v / mx * (yB - yT), d = new Date(r.t);
    if (d.getHours() === 0) { ax += `<text x="${(x + bw / 2).toFixed(1)}" y="${yB + 20}" text-anchor="middle">${d.getDate()} ${MON[d.getMonth()]}</text>`; g += `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${yT}" y2="${yB}" style="stroke-dasharray:2 5"/>`; }
    if (v > 0) bars += `<g data-tip="<b>${fmtDT(d)}</b><br>ฝน <b>${v.toFixed(1)}</b> มม./ชม."><rect class="bar" x="${x.toFixed(1)}" y="${(yB - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(2, h).toFixed(1)}" rx="3" style="fill:var(--rain);transform:scaleY(0);--d:${(i * .012).toFixed(3)}s"/>
      <rect x="${(x - 1).toFixed(1)}" y="${yT}" width="${(bw + 2).toFixed(1)}" height="${yB - yT}" fill="transparent"/></g>`;
  });
  g += '</g>'; ax += '</g>';
  const mxv = Math.max(...R.map(r => r.rain_mm || 0), 0);
  $('#rainTitle').textContent = `ฝนรายชั่วโมง ${R.length} ชม.ล่าสุด · รวม ${tot.toFixed(1)} มม.${mxv > 0 ? ` · สูงสุด ${mxv.toFixed(1)} มม./ชม.` : ''}`;
  $('#rainBox').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="ฝนรายชั่วโมง">${g}${ax}${bars}${tot === 0 ? `<text x="${W / 2}" y="${(yB + yT) / 2}" text-anchor="middle" style="fill:var(--faint);font:14px var(--font)">ไม่มีฝนในช่วง ${R.length} ชั่วโมงที่ผ่านมา</text>` : ''}</svg><div class="tt" id="rainTT"></div>`;
}
function growRain() { requestAnimationFrame(() => requestAnimationFrame(() => $$('.bar', $('#rainBox')).forEach(b => b.style.transform = 'scaleY(1)'))); }
function surge() { if (!reduced() && scene.waterG.animate) scene.waterG.animate([{ transform: `translateY(${yOf(ST.water_level) - Y_BASE + 170}px)` }, { transform: `translateY(${yOf(ST.water_level) - Y_BASE}px)` }], { duration: 1500, easing: 'cubic-bezier(.16,1,.3,1)' }); }
function selectStation(code, first) {
  ST = S[code] || R2; setStationScale(); curLevel = null; prevCap = 0; buildScene(); liveReadout(true); if (!first) surge();
  buildLevels(); prepDraw($('#lvBox')); buildRain(); buildTele(); updateLive(); if (!first) rebuildDock();
  $$('#stSeg button').forEach(b => b.classList.toggle('on', b.dataset.c === code)); placeInd($('#stSeg'));
  const lc = $('#lvBox').closest && $('#lvBox').closest('.card'); if (lc && lc.classList && lc.classList.contains('in')) levelsIn($('#lvBox'));
  const rc = $('#rainBox').closest && $('#rainBox').closest('.card'); if (rc && rc.classList && rc.classList.contains('in')) growRain();
  $('#lvTitle').textContent = `ระดับน้ำย้อนหลังเทียบสันสปิลเวย์ · ${short(ST)}`;
}
function initStations() {
  $('#stSeg').innerHTML = '<i class="ind"></i>' + D.stations.map(s => `<button data-c="${s.station_code}">${short(s)}</button>`).join('');
  $('#stSeg').addEventListener('click', e => { const b = e.target.closest('button'); if (b) selectStation(b.dataset.c); });
  bindTips('#rainBox', '#rainTT'); selectStation('RES002', true);
}

function initKwan() {
  const k = D.kwan; ST = { isKwan: true, station_code: 'KWAN', name_th: 'กว๊านพะเยา', spillway_msl: k.bank, water_level: k.level, history: [], rain: [], capacity_pct: null, measure_datetime: String(k.generated_at).replace(' ', 'T') };
  setStationScale(); curLevel = null; buildScene(); liveReadout(true);
}

/* =============== RESERVOIR TABLE (แทนตารางรายชื่ออ่างเก็บน้ำ) =============== */
function buildResTable() {
  if (!has('#resBody')) return;
  $('#resBody').innerHTML = (D.reservoirs || []).map(r => {
    const s = r.station_code ? S[r.station_code] : null, nm = `<b class="rn">${r.name_th}</b><br><small>${r.name_en}</small>`;
    if (!s || s.water_level == null) return `<tr><td>${nm}</td><td>${r.spillway_msl.toFixed(2)}</td><td>${r.capacity_display}</td><td colspan="5" class="nodata">ยังไม่มีสถานีโทรมาตร</td></tr>`;
    const crest = s === R2 ? CREST : r.spillway_msl, d6 = delta6(s), st = status(s.water_level, crest), col = d6 > 0.01 ? '--up' : d6 < -0.01 ? '--down' : '--flat', pct = s.capacity_pct || 0;
    return `<tr><td>${nm}</td><td>${r.spillway_msl.toFixed(2)}</td><td>${r.capacity_display}</td><td><b>${s.water_level.toFixed(3)}</b></td><td>${spark(lastN(s.history, 48).map(h => h.level), col)}</td>
      <td style="color:var(${col})">${sgn(d6)}</td><td><span class="pctb ${pct > 100 ? 'crit' : pct > 90 ? 'warn' : ''}">${pct.toFixed(1)}%</span><div class="mtrack"><i style="width:${Math.min(pct, 100)}%"></i></div></td><td><span class="badge ${st}">${STATUS_TXT[st]}</span></td></tr>`;
  }).join('');
}

/* =============== MONTH SUMMARY MODULE (กล่องสรุปหัวตารางบัญชีน้ำ) =============== */
const MPREV = {};
const MTH = ['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม'];
function mTween(key, id, to, dec) { const el = $(id); const from = MPREV[key] == null ? 0 : MPREV[key]; MPREV[key] = to; tween(from, to, 1100, v => el.textContent = fmt(v, dec)); }
function renderMonth(ym) {
  const rows = (D.allrows || []).filter(r => `${r.year}-${String(r.month).padStart(2, '0')}` === ym); if (!rows.length) return;
  const sum = f => rows.reduce((a, r) => a + (f(r) || 0), 0), n = rows.length;
  const inflow = sum(r => r.inflow), out = sum(r => (r.outlet || 0) + (r.spill || 0)), spill = sum(r => r.spill), dS = sum(r => r.dS), rain = sum(r => r.rain);
  const spDays = rows.filter(r => r.spill > 0).length, rnDays = rows.filter(r => r.rain > 0.1 && !(r.spill > 0)).length, rest = n - spDays - rnDays;
  const lv = rows.map(r => r.level), last = rows[n - 1], first = rows[0], capPct = last.volume / CAP * 100;
  const mx = rows.reduce((a, r) => r.rain > a.rain ? r : a, rows[0]);
  $('#mTitle').textContent = `สรุปน้ำเข้า–น้ำออก · ${MTH[+ym.slice(5) - 1]} ${+ym.slice(0, 4) + 543} (${n} วัน)`;
  mTween('in', '#mIn', inflow, 0); mTween('out', '#mOut', out, 0); mTween('spill', '#mSpS', spill, 0); mTween('rain', '#mRain', rain, 1); mTween('spd', '#mSpD', spDays, 0); mTween('cap', '#mCapN', capPct, 1);
  const net = $('#mNet'), nv = MPREV.net == null ? 0 : MPREV.net; MPREV.net = dS; tween(nv, dS, 1100, v => net.textContent = (v >= 0 ? '+' : '−') + fmt(Math.abs(v), 0));
  $('#mNetBox').style.color = dS >= 0 ? 'var(--up)' : 'var(--down)';
  const tot = inflow + out || 1; $('#mBalIn').style.width = (inflow / tot * 100).toFixed(1) + '%'; $('#mBalOut').style.width = (out / tot * 100).toFixed(1) + '%';
  $('#mBalNote').textContent = `ปริมาตรเปลี่ยนสุทธิ ΔS ${dS >= 0 ? 'เพิ่มขึ้น' : 'ลดลง'} ${fmt(Math.abs(dS))} ลบ.ม. · "ระบายรวม" = ท่อ + ล้นสปิลเวย์`;
  const C = 2 * Math.PI * 48; $('#mRingFg').style.setProperty('--c', (Math.min(capPct, 100) / 100 * C).toFixed(1));
  let ov = $('#mRingOv'); ov.style.setProperty('--c', (clamp(capPct - 100, 0, 100) / 100 * C).toFixed(1));
  $('#mCapNote').textContent = `${fmt(last.volume)} / ${fmt(CAP)} ลบ.ม. ณ ${fmtD(last.date)}${capPct > 100 ? ' · เกินความจุปกติ' : ''}`;
  const rt = $('#mDays'), parts = [['r-sp', spDays], ['r-rn', rnDays], ['r-flat', rest]];
  parts.forEach(([c, v]) => { const i = $('.' + c, rt); i.style.setProperty('--g', v); i.style.display = v ? '' : 'none'; });
  $('#mSpNote').textContent = `จาก ${n} วัน · ล้นสปิลเวย์ ${spDays} · ฝนตกไม่ล้น ${rnDays} · อื่น ๆ ${rest} · รวมน้ำล้น ${fmt(spill)} ลบ.ม.`;
  $('#mSpill').classList.toggle('alive', spDays > 0);
  $('#mRainNote').textContent = rain > 0 ? `วันฝนตก ${rows.filter(r => r.rain > 0.1).length} วัน · สูงสุด ${mx.rain.toFixed(1)} มม. (${fmtD(mx.date)})` : 'ไม่มีฝนในเดือนนี้';
  $('#mLv1').textContent = first.level.toFixed(3); $('#mLv2').textContent = last.level.toFixed(3);
  $('#mLvNote').textContent = `เปลี่ยน ${sgn(last.level - first.level)} ม. · ต่ำสุด ${Math.min(...lv).toFixed(3)} · สูงสุด ${Math.max(...lv).toFixed(3)}`;
  const W = 300, H = 56, lo = Math.min(...lv), hi = Math.max(...lv), rg = (hi - lo) || 1, pts = lv.map((v, i) => [n > 1 ? i / (n - 1) * (W - 6) + 3 : W / 2, H - 5 - (v - lo) / rg * (H - 12)]);
  const sp = $('#mSpark'); sp.innerHTML = `<path class="draw" d="${smooth(pts)}"/><circle cx="${pts[n - 1][0].toFixed(1)}" cy="${pts[n - 1][1].toFixed(1)}" r="4" style="fill:var(--accent);stroke:var(--core)" stroke-width="2"/>`;
  const pth = $('.draw', sp); try { pth.style.setProperty('--len', Math.ceil(pth.getTotalLength()) + 2); } catch (e) {}
  const box = $('#mLvBox'); box.classList.remove('drawn'); requestAnimationFrame(() => requestAnimationFrame(() => box.classList.add('drawn')));
}
function initMonth() {
  const sel = document.getElementById('monthSelect'); if (!sel || !has('#mBox')) return;
  sel.addEventListener('change', () => renderMonth(sel.value));
  let n = 0; const iv = setInterval(() => { if (sel.value && (D.allrows || []).length) { renderMonth(sel.value); clearInterval(iv); } else if (++n > 80) clearInterval(iv); }, 250);
}

/* =============== BOOT =============== */
function prepDraw(root) {
  $$('.draw', root || document).forEach(p => { try { p.style.setProperty('--len', Math.ceil(p.getTotalLength()) + 2); } catch (e) {} });
}
function boot() {
  initTheme();
  buildScene(); initKPI(); buildLevels(); buildForecast(); buildTable();
  prepDraw();
  bindTips('#dailyBox', '#dailyTT'); bindTips('#fcBox', '#fcTT');
  // static texts
  const st = status(R2.water_level, CREST);
  $('#heroState').textContent = st === 'crit' ? 'ล้นสปิลเวย์' : st === 'warn' ? 'ใกล้ล้น' : 'ปกติ';
  const L = D.ledger[D.ledger.length - 1];
  $('#heroSub').textContent = st === 'crit'
    ? `ระดับน้ำสูงกว่าสันสปิลเวย์ ${(R2.water_level - CREST).toFixed(3)} ม. มีน้ำล้นผ่านสปิลเวย์ ${fmt(L.spill)} ลบ.ม. ในวันที่ ${fmtD(L.date)}`
    : `ระดับน้ำต่ำกว่าสันสปิลเวย์ ${(CREST - R2.water_level).toFixed(3)} ม.`;
  initDock(); updateLive(); setInterval(updateLive, 30000);
  // daily seg
  $('#dailySeg').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    $$('#dailySeg button').forEach(x => x.classList.toggle('on', x === b)); placeInd($('#dailySeg')); renderDaily(b.dataset.k);
  });
  $$('.seg').forEach(placeInd); window.addEventListener('resize', () => $$('.seg').forEach(placeInd));
  document.fonts && document.fonts.ready.then(() => $$('.seg').forEach(placeInd));
  // reveal after skeleton
  const finish = () => {
    document.body.classList.remove('is-loading'); $$('[data-sk]').forEach(n => n.removeAttribute('data-sk'));
    liveReadout(false);
    if (!reduced() && scene.waterG.animate) scene.waterG.animate([{ transform: `translateY(${yOf(ST.water_level) - Y_BASE + 170}px)` }, { transform: `translateY(${yOf(ST.water_level) - Y_BASE}px)` }], { duration: 1900, easing: 'cubic-bezier(.16,1,.3,1)' });
    initReveal();
  };
  setTimeout(finish, reduced() ? 0 : 900);
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
