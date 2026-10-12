/* ukm.js — โมดูลจาก ui_lab ฝังในหน้าเว็บเดิม (Shadow DOM) · สร้างอัตโนมัติโดย build_ukm.py อย่าแก้ตรงนี้ */
(function () {
'use strict';
var PAGE = location.pathname.split('/').pop() || 'index.html';
var AFTER_HERO = 'main > section.page-hero + section.section';
var CFG = {
  'monitoring.html': { plans: [{ anchor: '#stationGrid', pos: 'before', mods: ['station'], hide: '#stationGrid' },
    { anchor: '.table-card:has(#reservoirTableBody)', pos: 'before', mods: ['resTable'], hide: '.table-card:has(#reservoirTableBody)' },
    { anchor: 'section:has(#stationFilter)', pos: 'none', mods: [], hide: 'section:has(#stationFilter)' },
    { anchor: 'main > section:nth-last-of-type(2)', pos: 'none', mods: [], hide: 'main > section:nth-last-of-type(-n+2)' }], dock: true },
  'water-balance.html': { plans: [{ anchor: AFTER_HERO, pos: 'section-after', mods: ['daily'] }, { anchor: '.filter-bar', pos: 'after', mods: ['month'], hide: '#monthSummary' }] },
  'inflow-forecast.html': { plans: [{ anchor: AFTER_HERO, pos: 'section-after', mods: ['forecast'] }] } };
// หน้าแรก (index.html) และคาดการณ์น้ำท่วม (flood-forecast.html): ยังไม่ฝังโมดูล (ตัดออกตามที่ขอ)
var cfg = CFG[PAGE]; if (!cfg) return;
var CSS = "\n:host{display:block;--font:\"IBM Plex Sans Thai\",\"Sarabun\",system-ui,sans-serif;--ease:cubic-bezier(.32,.72,0,1);--ease-out:cubic-bezier(.16,1,.3,1);--r-shell:24px;--r-core:20px;--r-sm:14px;\n --accent:var(--teal-400,#2a9d8f);--accent-2:var(--amber-400,#e0a94f);--ok:#2a9d7f;--warn:#e0a94f;--crit:#d6453d;--rain:#4c5fd5;--up:#d9604f;--down:#2a9d7f;--flat:#6fa8c4;--bank:#8d5f3d;\n --core:var(--surface,#fff);--shell:rgba(var(--bd-rgb,157,201,201),.08);--line:var(--border,rgba(18,52,70,.1));--line-2:var(--border-strong,rgba(18,52,70,.2));--glass:rgba(var(--bg950-rgb,246,249,250),.8);\n --text:var(--text-300);--strong:var(--text-100);--muted:var(--text-500);--faint:var(--text-600);\n --sky-1:color-mix(in srgb,var(--accent) 30%,#fff);--sky-2:color-mix(in srgb,var(--accent) 7%,#fff);--water-1:color-mix(in srgb,var(--accent) 65%,#fff);--water-2:color-mix(in srgb,var(--accent) 100%,#000 18%);\n --hill-far:color-mix(in srgb,var(--accent) 16%,var(--sky-2));--hill-near:color-mix(in srgb,var(--accent) 30%,var(--sky-2));--land:color-mix(in srgb,var(--accent) 28%,#7a8a6a);--land-2:color-mix(in srgb,var(--accent) 22%,#5f6f55);\n --orb:#ffe29a;--orb-glow:rgba(255,214,130,.55);--shadow:rgba(22,66,88,.22);color:var(--text);font-family:var(--font);line-height:1.6}\n:host([data-mode=\"dark\"]){--core:color-mix(in srgb,var(--accent) 10%,#0d1e29);--bank:#c9945f;\n --sky-1:color-mix(in srgb,var(--accent) 38%,#050d14);--sky-2:color-mix(in srgb,var(--accent) 14%,#0a1a26);--water-1:var(--accent);--water-2:color-mix(in srgb,var(--accent) 100%,#000 45%);\n --hill-far:color-mix(in srgb,var(--accent) 22%,#07131b);--hill-near:color-mix(in srgb,var(--accent) 30%,#06111a);--land:color-mix(in srgb,var(--accent) 22%,#1c261f);--land-2:color-mix(in srgb,var(--accent) 18%,#141c17);\n --orb:#dfe9ff;--orb-glow:rgba(190,210,255,.35);--shadow:rgba(0,0,0,.5)}\n.hero{padding:6px 0 10px!important;overflow:visible!important}.hero h1{font-size:clamp(24px,3.4vw,38px)!important;margin:10px 0 6px!important}.hero p.sub{margin:0 0 10px!important}\n.sec{padding:20px 0!important}.wrap{padding:0!important;max-width:none!important}\n.card{background:var(--core)}\n*{box-sizing:border-box}\nh1,h2,h3{margin:0;color:var(--strong);font-weight:700;letter-spacing:.005em}\n.wrap{max-width:1180px;margin:0 auto;padding:0 20px}\n.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}\n.nav{position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:50;display:flex;align-items:center;gap:6px;padding:8px 10px 8px 14px;border-radius:999px;\n  background:var(--glass);backdrop-filter:blur(16px) saturate(1.4);-webkit-backdrop-filter:blur(16px) saturate(1.4);border:1px solid var(--line);box-shadow:0 10px 30px -12px var(--shadow);max-width:calc(100vw - 20px)}\n.brand{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--strong);font-size:14px;white-space:nowrap;margin-right:6px}\n.brand i{width:26px;height:26px;border-radius:9px;background:linear-gradient(160deg,var(--water-1),var(--water-2));display:inline-block;position:relative;overflow:hidden}\n.brand i::after{content:\"\";position:absolute;left:-30%;right:-30%;bottom:28%;height:10px;border-radius:50%;background:rgba(255,255,255,.55)}\n.nav a.lnk{font-size:13.5px;color:var(--muted);text-decoration:none;padding:5px 11px;border-radius:999px;white-space:nowrap;transition:background .2s,color .2s}\n.nav a.lnk:hover,.nav a.lnk.on{background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--accent)}\n.nav .scroller{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none}\n.btn-ico{width:34px;height:34px;border-radius:50%;border:1px solid var(--line-2);background:transparent;color:var(--text);cursor:pointer;display:grid;place-items:center;flex:none;transition:background .2s,transform .2s}\n.btn-ico:hover{background:color-mix(in srgb,var(--accent) 14%,transparent);transform:rotate(18deg)}\n.btn-ico svg{width:18px;height:18px}\n.theme-pop{position:fixed;top:68px;right:max(14px,calc(50% - 560px));z-index:60;width:292px;padding:16px;border-radius:20px;background:var(--core);border:1px solid var(--line-2);\n  box-shadow:0 24px 60px -18px var(--shadow);opacity:0;transform:translateY(-8px) scale(.97);pointer-events:none;transition:opacity .25s,transform .35s var(--ease-out)}\n.theme-pop.open{opacity:1;transform:none;pointer-events:auto}\n.theme-pop h4{margin:0 0 10px;font-size:13px;color:var(--strong)}\n.swatches{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}\n.sw{border:2px solid transparent;border-radius:14px;padding:8px 6px;background:var(--shell);cursor:pointer;font:inherit;font-size:12px;color:var(--text);display:flex;flex-direction:column;align-items:center;gap:6px;transition:transform .2s,border-color .2s}\n.sw:hover{transform:translateY(-2px)}\n.sw.on{border-color:var(--accent)}\n.sw b{width:34px;height:34px;border-radius:50%;display:block;box-shadow:inset 0 -8px 12px rgba(0,0,0,.14),0 3px 8px -3px rgba(0,0,0,.4)}\n.row{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:10px;font-size:12.5px;color:var(--muted)}\n.seg{position:relative;display:inline-flex;padding:3px;border-radius:999px;background:var(--shell);border:1px solid var(--line)}\n.seg button{position:relative;z-index:1;border:0;background:transparent;font:inherit;font-size:12.5px;color:var(--muted);padding:5px 13px;border-radius:999px;cursor:pointer;transition:color .25s}\n.seg button.on{color:var(--accent-ink,#fff)}\n.seg .ind{position:absolute;z-index:0;top:3px;bottom:3px;left:0;width:var(--w,40px);transform:translateX(var(--x,3px));border-radius:999px;background:var(--accent);transition:transform .45s var(--ease),width .45s var(--ease)}\ninput[type=color]{width:46px;height:30px;border:1px solid var(--line-2);border-radius:8px;background:transparent;padding:2px;cursor:pointer}\n.hero{position:relative;padding:92px 0 28px;overflow:hidden}\n.hero-grid{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:18px;align-items:stretch}\n.hero-copy{grid-column:1/-1}\n.live{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;padding:5px 12px;border-radius:999px;background:var(--glass);border:1px solid var(--line);color:var(--text)}\n.live i{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 0 var(--ok);animation:ping 2s infinite}\n.live.warn i{background:var(--warn);animation:none}\n.live.stale i{background:var(--crit);animation:none}\n.hero h1{font-size:clamp(30px,5vw,54px);line-height:1.12;margin:14px 0 8px}\n.hero h1 em{font-style:normal;color:var(--accent);position:relative;white-space:nowrap}\n.hero h1 em::after{content:\"\";position:absolute;left:0;right:0;bottom:-.08em;height:.16em;background:currentColor;opacity:.28;border-radius:99px;\n  -webkit-mask:radial-gradient(circle at 4px .08em,transparent 2.4px,#000 2.6px) 0 0/10px 100%;mask:radial-gradient(circle at 4px .08em,transparent 2.4px,#000 2.6px) 0 0/10px 100%}\n.hero p.sub{color:var(--muted);max-width:640px;margin:0 0 16px;font-size:15px}\n.scene{position:relative;border-radius:var(--r-shell);overflow:hidden;border:1px solid var(--line);background:var(--shell);box-shadow:0 30px 60px -34px var(--shadow);min-height:380px}\n.scene svg{display:block;width:100%;height:100%;min-height:380px}\n.scene .lbl{font-family:var(--font);font-size:15px;font-weight:600;fill:var(--strong);paint-order:stroke;stroke:var(--core);stroke-width:4px;stroke-linejoin:round}\n.scene .lbl.s{font-size:12px;font-weight:500}\n.readout{display:flex;flex-direction:column;gap:6px;border-radius:var(--r-shell);background:var(--core);border:1px solid var(--line);padding:22px 22px 18px;box-shadow:0 18px 40px -30px var(--shadow)}\n.readout small{color:var(--muted);font-size:13px}\n.readout .big{font-size:clamp(46px,7vw,72px);font-weight:800;line-height:1;color:var(--strong);font-variant-numeric:tabular-nums;letter-spacing:-.02em}\n.readout .big span{font-size:16px;font-weight:500;color:var(--muted);margin-left:6px;letter-spacing:0}\n.readout .delta{font-size:19px;font-weight:700}\n.readout .delta.ok{color:var(--ok)}\n.readout .delta.warn{color:var(--warn)}\n.readout .delta.crit{color:var(--crit)}\n.readout .note{margin-top:8px;border-radius:14px;padding:12px 14px;background:color-mix(in srgb,var(--accent) 9%,transparent);font-size:13px;color:var(--text)}\n.readout .note b{color:var(--strong)}\n@media(max-width:900px){.hero-grid{grid-template-columns:1fr}.scene,.scene svg{min-height:300px}}\n.wave-a{animation:waveX 9s linear infinite}\n.wave-b{animation:waveX 14s linear infinite reverse}\n.water-g{transition:transform 1.1s var(--ease)}\n.boat{animation:bob 3.6s ease-in-out infinite;transform-box:fill-box;transform-origin:50% 100%}\n.cloud{animation:drift 70s linear infinite}\n.cloud.c2{animation-duration:110s;animation-delay:-40s}\n.drop{stroke:var(--rain);stroke-width:2;stroke-linecap:round;opacity:0}\n.raining .drop{opacity:.7;animation:fall .9s linear infinite}\n.star{fill:#fff;opacity:0}\n:host([data-mode=\"dark\"]) .star{animation:twinkle 3s ease-in-out infinite}\n.foam{stroke:#fff;stroke-width:3;stroke-linecap:round;stroke-dasharray:14 12;opacity:0}\n.spilling .foam{opacity:.9;animation:flow .9s linear infinite}\n.sonar{transform-box:fill-box;transform-origin:center;animation:sonar 2s ease-out infinite}\n.sun-glow{animation:glow 6s ease-in-out infinite}\nsection.sec{padding:46px 0}\n.sec-head{margin-bottom:18px}\n.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700;display:flex;align-items:center;gap:8px}\n.eyebrow::before{content:\"\";width:18px;height:2px;background:var(--accent);border-radius:2px}\n.sec-head h2{font-size:clamp(24px,3.4vw,34px);margin:4px 0}\n.sec-head p{margin:0;color:var(--muted);font-size:14px;max-width:640px}\n.card{background:var(--core);border:1px solid var(--line);border-radius:var(--r-shell);padding:22px;position:relative;overflow:hidden;box-shadow:0 18px 40px -32px var(--shadow)}\n.card h3{font-size:15px;color:var(--muted);font-weight:500;margin-bottom:6px}\n.rv{opacity:0;transform:translateY(28px);filter:blur(6px);transition:opacity .9s var(--ease-out),transform .9s var(--ease-out),filter .9s var(--ease-out);transition-delay:var(--d,0s)}\n.rv.in{opacity:1;transform:none;filter:none}\n:host(.is-loading) [data-sk]{color:transparent!important;border-radius:10px;background:linear-gradient(90deg,var(--shell),color-mix(in srgb,var(--accent) 16%,transparent),var(--shell));background-size:200% 100%;animation:sk 1.2s linear infinite}\n.bento{display:grid;grid-template-columns:repeat(6,1fr);gap:14px}\n.b{grid-column:span 2}\n.b.w{grid-column:span 4}\n.b .num{font-size:clamp(34px,4.6vw,54px);font-weight:800;color:var(--strong);line-height:1.05;font-variant-numeric:tabular-nums}\n.b .num small{font-size:14px;font-weight:500;color:var(--muted);margin-left:6px}\n.b .cap{font-size:13px;color:var(--muted)}\n.trio{display:flex;gap:26px;flex-wrap:wrap;align-items:flex-end;margin:14px 0 12px}\n.trio .num.up{color:var(--up)}\n.trio .num.down{color:var(--down)}\n.trio .num.flat{color:var(--muted)}\n.ratio{display:flex;gap:6px;height:12px;margin:6px 0 10px}\n.ratio i{display:block;border-radius:99px;flex:var(--g,1) 1 0;min-width:10px;transition:flex .9s var(--ease)}\n.ratio .r-up{background:var(--up)}\n.ratio .r-down{background:var(--down)}\n.ratio .r-flat{background:var(--faint);opacity:.55}\n.waves-bg{position:absolute;inset:auto 0 0 0;height:60%;opacity:.5;pointer-events:none}\n.waves-bg path{fill:none;stroke:var(--up);stroke-width:2;opacity:.3;animation:waveX 18s linear infinite}\n.waves-bg path:nth-child(2){animation-duration:26s;animation-direction:reverse}\n.ring{width:120px;height:120px;flex:none}\n.ring .bg{stroke:var(--line-2);fill:none;stroke-width:12}\n.ring .fg{stroke:var(--accent);fill:none;stroke-width:12;stroke-linecap:round;transform:rotate(-90deg);transform-origin:50% 50%;stroke-dasharray:var(--c) 999;stroke-dashoffset:0;transition:stroke-dasharray 1.4s var(--ease-out)}\n.ring .ov{stroke:var(--crit)}\n.flexrow{display:flex;gap:16px;align-items:center}\n.alive-dot{position:absolute;top:22px;right:22px;width:14px;height:14px;border-radius:50%;background:var(--shell)}\n.alive .alive-dot{background:var(--crit)}\n.alive .alive-dot::after{content:\"\";position:absolute;inset:-1px;border-radius:50%;border:2px solid var(--crit);animation:sonar 2s ease-out infinite}\n.balance{display:flex;height:14px;border-radius:99px;overflow:hidden;background:var(--shell);margin:8px 0}\n.balance i{display:block;height:100%;transition:width 1.1s var(--ease)}\n.balance .in{background:var(--accent)}\n.balance .out{background:var(--accent-2)}\n@media(max-width:820px){.bento{grid-template-columns:repeat(2,1fr)}.b,.b.w{grid-column:span 2}}\n.chart-box{position:relative;width:100%}\n.chart-box svg{display:block;width:100%;height:auto;overflow:visible}\n.ax text{font-family:var(--font);font-size:12px;fill:var(--faint)}\n.grid line{stroke:var(--line)}\n.tt{position:absolute;pointer-events:none;background:var(--core);color:var(--text);border:1px solid var(--line-2);border-radius:12px;padding:8px 12px;font-size:12.5px;box-shadow:0 12px 30px -12px var(--shadow);opacity:0;transform:translateY(4px);transition:opacity .15s,transform .15s;z-index:5;white-space:nowrap}\n.tt.on{opacity:1;transform:none}\n.tt b{color:var(--strong)}\n.bar{transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);transition:transform .9s var(--ease-out);transition-delay:var(--d,0s)}\n.in .bar,.bars-in .bar{transform:scaleY(1)}\n.bar-lbl{font-family:var(--font);font-size:12px;fill:var(--strong);font-weight:700;text-anchor:middle}\n.bar-delta{font-family:var(--font);font-size:11.5px;font-weight:700;text-anchor:middle}\n.draw{stroke-dasharray:var(--len,2000);stroke-dashoffset:var(--len,2000);transition:stroke-dashoffset 2s var(--ease-out)}\n.drawn .draw{stroke-dashoffset:0}\n.fadein{opacity:0;transition:opacity .8s .9s}\n.drawn .fadein{opacity:1}\n.mascot{animation:bob 3s ease-in-out infinite;transform-box:fill-box;transform-origin:50% 100%}\n.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);margin-top:10px}\n.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}\ntable.st{width:100%;border-collapse:collapse;font-size:14px}\ntable.st th{font-size:12px;color:var(--faint);font-weight:600;text-align:right;padding:8px 10px;border-bottom:1px solid var(--line)}\ntable.st td{padding:12px 10px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}\ntable.st th:first-child,table.st td:first-child{text-align:left}\ntable.st tr:hover td{background:color-mix(in srgb,var(--accent) 6%,transparent)}\ntable.st tr:last-child td{border-bottom:0}\n.badge{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600}\n.badge.ok{background:color-mix(in srgb,var(--ok) 16%,transparent);color:var(--ok)}\n.badge.warn{background:color-mix(in srgb,var(--warn) 22%,transparent);color:color-mix(in srgb,var(--warn) 70%,var(--strong))}\n.badge.crit{background:color-mix(in srgb,var(--crit) 16%,transparent);color:var(--crit)}\n.spark{width:88px;height:26px;vertical-align:middle}\n.spark path{fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}\n.tbl-wrap{overflow-x:auto}\n.dock{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:45;width:min(640px,calc(100vw - 20px));display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:999px;\n  background:var(--glass);backdrop-filter:blur(16px) saturate(1.4);-webkit-backdrop-filter:blur(16px) saturate(1.4);border:1px solid var(--line);box-shadow:0 14px 40px -14px var(--shadow)}\n.dock .lbl{min-width:104px;line-height:1.2}\n.dock .lbl small{display:block;font-size:11px;color:var(--muted)}\n.dock .lbl b{font-size:14px;color:var(--strong)}\n.dock input[type=range]{flex:1;min-width:0;accent-color:var(--accent);height:24px;cursor:pointer}\n.play{width:40px;height:40px;border-radius:50%;border:0;background:var(--accent);color:#fff;cursor:pointer;display:grid;place-items:center;flex:none;transition:transform .2s}\n.play:hover{transform:scale(1.08)}\n.play svg{width:18px;height:18px}\n.live-btn{border:0;background:transparent;color:var(--accent);font:inherit;font-size:12.5px;font-weight:700;cursor:pointer;padding:6px 8px}\nfooter{padding:40px 0 110px;color:var(--faint);font-size:12.5px}\nfooter b{color:var(--muted)}\n@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.001s!important;animation-iteration-count:1!important;transition-duration:.001s!important}.rv{opacity:1;transform:none;filter:none}.bar{transform:none}.draw{stroke-dashoffset:0}.fadein{opacity:1}}\n.pdot .core{transform-box:fill-box;transform-origin:center;transform:scale(0);transition:transform .6s var(--ease-out);transition-delay:var(--d,0s)}\n.drawn .pdot .core{transform:scale(1)}\n.pdot text{font-family:var(--font)}\n.tick-lbl{font-family:var(--font);font-size:12px;fill:var(--faint)}\n.lvl-tag{transition:transform 1.1s var(--ease)}\n.pt-hit{cursor:pointer}\n:host([data-motion=\"reduce\"]) *,:host([data-motion=\"reduce\"]) *::before,:host([data-motion=\"reduce\"]) *::after{animation-duration:.001s!important;animation-iteration-count:1!important;transition-duration:.001s!important}\n:host([data-motion=\"reduce\"]) .rv{opacity:1;transform:none;filter:none}\n:host([data-motion=\"reduce\"]) .draw{stroke-dashoffset:0}\n:host([data-motion=\"reduce\"]) .fadein{opacity:1}\n:host([data-motion=\"reduce\"]) .pdot .core{transform:none}\n.nav a.lnk.on{font-weight:600}\n@media(max-width:640px){.nav .scroller{display:none}.hero{padding-top:80px}.dock .lbl{min-width:84px}}\n.mascot{animation:hop 1.1s ease-in-out infinite!important}\n.stbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:0 0 14px;justify-content:space-between}\n.sub-h{margin:26px 0 4px;font-size:15px;color:var(--muted);font-weight:600}\n.tele{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0 18px}\n.tile{background:var(--core);border:1px solid var(--line);border-radius:var(--r-core);padding:16px 16px 13px;position:relative;overflow:hidden;transition:transform .35s var(--ease-out),box-shadow .35s}\n.tile:hover{transform:translateY(-3px);box-shadow:0 16px 32px -22px var(--shadow)}\n.tile .t-top{display:flex;align-items:center;gap:9px;color:var(--muted);font-size:13px}\n.tile .t-ic{width:28px;height:28px;border-radius:9px;display:grid;place-items:center;background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--accent);flex:none}\n.tile .t-ic svg{width:16px;height:16px}\n.tile .t-num{font-size:28px;font-weight:800;color:var(--strong);line-height:1.15;margin-top:8px;font-variant-numeric:tabular-nums}\n.tile .t-num small{font-size:12.5px;font-weight:500;color:var(--muted);margin-left:5px}\n.tile .t-bar{height:6px;border-radius:99px;background:var(--shell);margin:10px 0 7px;overflow:hidden}\n.tile .t-bar i{display:block;height:100%;width:0;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent-2));transition:width 1.3s var(--ease-out)}\n.tile .t-bar.over i{background:linear-gradient(90deg,var(--accent),var(--crit))}\n.tile .t-sub{font-size:12px;color:var(--faint);line-height:1.45}\n@media(max-width:900px){.tele{grid-template-columns:repeat(2,1fr)}}\n.ratio .r-sp{background:var(--crit)}\n.ratio .r-rn{background:var(--rain)}\n.spark-big{width:100%;height:56px;margin:8px 0 2px;overflow:visible}\n.spark-big path{fill:none;stroke:var(--accent);stroke-width:2.8;stroke-linecap:round;stroke-linejoin:round}\n.bento .num.sm{font-size:clamp(26px,3vw,34px)}\n.ring .ov{stroke:var(--crit)}\n.capb{margin:10px 0 2px}\n.capn{font-size:clamp(40px,5vw,52px);font-weight:800;line-height:1;font-variant-numeric:tabular-nums;color:var(--accent);letter-spacing:-.02em}\n.capn.warn{color:var(--warn)}\n.capn.crit{color:var(--crit)}\n.capn small{font-size:14px;font-weight:600;color:var(--muted);margin-left:6px;letter-spacing:0}\n.captrack{position:relative;height:14px;border-radius:99px;background:var(--shell);margin-top:9px}\n.captrack i{position:absolute;top:0;bottom:0;border-radius:99px;transition:width 1.3s var(--ease-out),left 1.3s var(--ease-out)}\n.captrack .f{left:0;width:0;background:linear-gradient(90deg,var(--accent),var(--accent-2))}\n.captrack .o{width:0;background:var(--crit);border-radius:0 99px 99px 0}\n.captrack .m{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--strong);opacity:.55;border-radius:2px}\n.caplbl{font-size:11.5px;color:var(--faint);margin-top:6px}\n.tele.mini{grid-template-columns:1fr 1fr;gap:8px;margin:12px 0 0}\n.tele.mini .tile{padding:9px 11px 8px;border-radius:14px}\n.tele.mini .t-top{font-size:11.5px;gap:7px}\n.tele.mini .t-ic{width:22px;height:22px;border-radius:7px}\n.tele.mini .t-ic svg{width:13px;height:13px}\n.tele.mini .t-num{font-size:19px;margin-top:4px}\n.tele.mini .t-num small{font-size:11px;margin-left:3px}\n.tele.mini .t-bar{height:4px;margin:6px 0 0}\n.tele.mini .t-sub{display:none}\n.pctb{font-size:20px;font-weight:800;color:var(--accent);font-variant-numeric:tabular-nums}\n.pctb.warn{color:var(--warn)}\n.pctb.crit{color:var(--crit)}\n.mtrack{height:5px;border-radius:99px;background:var(--shell);margin:5px 0 0 auto;width:90px;overflow:hidden}\n.mtrack i{display:block;height:100%;border-radius:99px;background:var(--accent)}\ntable.st .rn{color:var(--strong);font-weight:700}\ntable.st td small{color:var(--faint)}\ntable.st .nodata{color:var(--faint);text-align:center!important}\n.hero-grid.stack{grid-template-columns:1fr;gap:14px}\n.stack .scene{min-height:0;aspect-ratio:900/420}\n.stack .scene svg{min-height:0;height:100%}\n.readout.wide{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);gap:8px 32px;align-items:start}\n.readout.wide .rcol{display:flex;flex-direction:column;gap:6px;min-width:0}\n.readout.wide .tele.mini{grid-template-columns:repeat(3,1fr);margin-top:10px}\n@media(max-width:900px){.readout.wide{grid-template-columns:1fr}.readout.wide .tele.mini{grid-template-columns:repeat(2,1fr)}.stack .scene{aspect-ratio:auto;min-height:280px}.stack .scene svg{min-height:280px}}\n.orb-g{transition:transform 1.4s var(--ease)}\n.scene.day{--sky-1:color-mix(in srgb,var(--accent) 30%,#fff);--sky-2:color-mix(in srgb,var(--accent) 7%,#fff);--water-1:color-mix(in srgb,var(--accent) 65%,#fff);--water-2:color-mix(in srgb,var(--accent) 100%,#000 18%);\n --hill-far:color-mix(in srgb,var(--accent) 16%,var(--sky-2));--hill-near:color-mix(in srgb,var(--accent) 30%,var(--sky-2));--land:color-mix(in srgb,var(--accent) 28%,#7a8a6a);--land-2:color-mix(in srgb,var(--accent) 22%,#5f6f55);\n --orb:#ffe29a;--orb-glow:rgba(255,214,130,.55);--core:#fbfdfe;--strong:#0b1c27;--muted:#5a7384;--faint:#6f8696}\n.scene.night{--sky-1:color-mix(in srgb,var(--accent) 36%,#040b12);--sky-2:color-mix(in srgb,var(--accent) 13%,#0a1a26);--water-1:var(--accent);--water-2:color-mix(in srgb,var(--accent) 100%,#000 50%);\n --hill-far:color-mix(in srgb,var(--accent) 20%,#07131b);--hill-near:color-mix(in srgb,var(--accent) 28%,#06111a);--land:color-mix(in srgb,var(--accent) 22%,#1c261f);--land-2:color-mix(in srgb,var(--accent) 18%,#141c17);\n --orb:#e6eeff;--orb-glow:rgba(190,210,255,.4);--core:#0d1e29;--strong:#eef8fa;--muted:#a9c0c8;--faint:#9fb5bd}\n.scene.dusk{--sky-1:color-mix(in srgb,#ff8f5e 55%,#3a4a7a);--sky-2:color-mix(in srgb,#ffd7a1 82%,var(--accent));--water-1:color-mix(in srgb,var(--accent) 62%,#ffb98a);--water-2:color-mix(in srgb,var(--accent) 100%,#1a1030 35%);\n --hill-far:color-mix(in srgb,#a45a6a 38%,var(--sky-2));--hill-near:color-mix(in srgb,#5a4a6a 55%,var(--sky-2));--land:color-mix(in srgb,var(--accent) 20%,#3b3a3a);--land-2:color-mix(in srgb,var(--accent) 16%,#2c2b2e);\n --orb:#ffc98a;--orb-glow:rgba(255,160,90,.6);--core:#fbf3ea;--strong:#2a1a24;--muted:#6a5a60;--faint:#7a6a70}\n.scene.night .star{animation:twinkle 3s ease-in-out infinite}\n.scene.dusk .star{opacity:.35}\n.scene{transition:background .6s}\n.capb{transition:opacity .3s}\n.capb.dim{opacity:.4}\n.dock{width:min(780px,calc(100vw - 20px));border-radius:30px}\n.dock .lbl{min-width:150px}\n.dock .lbl small{white-space:nowrap;max-width:230px;overflow:hidden;text-overflow:ellipsis}\n.dtrack{position:relative;flex:1;min-width:0;height:34px;border-radius:10px;overflow:hidden;background:var(--shell)}\n.dtrack svg{position:absolute;inset:0;width:100%;height:100%;display:block}\n.dtrack input[type=range]{position:absolute;inset:0;width:100%;height:100%;margin:0;background:transparent;-webkit-appearance:none;appearance:none;cursor:pointer}\n.dtrack input[type=range]::-webkit-slider-runnable-track{height:34px;background:transparent}\n.dtrack input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:6px;height:34px;border-radius:3px;background:var(--strong);box-shadow:0 0 0 2px var(--core)}\n.dtrack input[type=range]::-moz-range-track{height:34px;background:transparent}\n.dtrack input[type=range]::-moz-range-thumb{width:6px;height:34px;border:0;border-radius:3px;background:var(--strong);box-shadow:0 0 0 2px var(--core)}\n.capb.dim{opacity:1}\n@keyframes ping{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--ok) 60%,transparent)}70%,100%{box-shadow:0 0 0 9px transparent}}\n@keyframes waveX{to{transform:translateX(-200px)}}\n@keyframes bob{50%{transform:translateY(-4px) rotate(2.2deg)}}\n@keyframes drift{from{transform:translateX(-160px)}to{transform:translateX(1320px)}}\n@keyframes fall{from{transform:translateY(-50px)}to{transform:translateY(300px)}}\n@keyframes twinkle{50%{opacity:.9}}\n@keyframes flow{to{stroke-dashoffset:-26}}\n@keyframes sonar{from{transform:scale(.3);opacity:.9}to{transform:scale(2.4);opacity:0}}\n@keyframes glow{50%{opacity:.7}}\n@keyframes sk{to{background-position:-200% 0}}\n@keyframes hop{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}";
var TPL = {"hero": "<header class=\"hero\" id=\"top\">\n  <div class=\"wrap\">\n    <div class=\"hero-copy\">\n      <span class=\"live\" id=\"live\"><i></i><span id=\"liveText\" data-sk>กำลังโหลดข้อมูล…</span></span>\n      <h1>อ่างแม่นาเรือตอนนี้ <em id=\"heroState\" data-sk>…</em></h1>\n      <p class=\"sub\" id=\"heroSub\" data-sk>กำลังรวบรวมค่าจากสถานีโทรมาตรและบัญชีน้ำ</p>\n    </div>\n    <div class=\"hero-grid\" style=\"margin-top:6px\">\n      <div class=\"scene\" id=\"scene\" role=\"img\" aria-label=\"ภาพจำลองระดับน้ำในอ่างเก็บน้ำแม่นาเรือเทียบกับสันสปิลเวย์\"></div>\n      <aside class=\"readout\" id=\"readout\">\n        <small id=\"roName\" data-sk>อ่างเก็บน้ำแม่นาเรือ · RES002</small>\n        <div class=\"big\"><span id=\"roLevel\" data-sk>489.000</span><span>ม.รทก.</span></div>\n        <div class=\"delta\" id=\"roDelta\" data-sk>—</div>\n        <small id=\"roTrend\" data-sk>—</small>\n        <div class=\"capb\"><div class=\"capn\" id=\"roCapNW\"><span id=\"roCapN\">0</span><small>% ของความจุ</small></div><div class=\"captrack\"><i class=\"f\" id=\"roCapF\"></i><i class=\"o\" id=\"roCapO\"></i><b class=\"m\" id=\"roCapM\"></b></div><div class=\"caplbl\" id=\"roCapL\">เส้นขีด = 100% (ระดับสันสปิลเวย์)</div></div>\n        <div class=\"note\" id=\"roNote\" data-sk>—</div>\n      </aside>\n    </div>\n  </div>\n</header>", "kpi": "<section class=\"sec\" id=\"kpi\"><div class=\"wrap\">\n  <div class=\"sec-head rv\"><div class=\"eyebrow\">ตัวชี้วัดหลัก</div><h2>สรุปสถานการณ์ในหน้าเดียว</h2><p>ตัวเลขนับขึ้นเมื่อเลื่อนมาถึง แถบสัดส่วนและวงแหวนเคลื่อนไหวตามค่า</p></div>\n  <div class=\"bento\">\n    <div class=\"card b w rv\" id=\"bDir\" style=\"--d:.05s\">\n      <svg class=\"waves-bg\" viewBox=\"0 0 800 120\" preserveAspectRatio=\"none\" aria-hidden=\"true\"><path d=\"M0 40 q50 -30 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0\"/><path d=\"M0 80 q60 30 120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0\"/></svg>\n      <h3 id=\"dirTitle\">ทิศทางของน้ำ เทียบ 6 ชั่วโมงก่อน</h3>\n      <div class=\"trio\"><div><div class=\"num up\" data-num=\"up\">0</div><div class=\"cap\">กำลังขึ้น</div></div><div><div class=\"num down\" data-num=\"down\">0</div><div class=\"cap\">กำลังลด</div></div><div><div class=\"num flat\" data-num=\"flat\">0</div><div class=\"cap\">ทรงตัว</div></div></div>\n      <div class=\"ratio\" id=\"ratio\"><i class=\"r-up\"></i><i class=\"r-down\"></i><i class=\"r-flat\"></i></div>\n      <div class=\"cap\" id=\"dirAvg\">—</div>\n    </div>\n    <div class=\"card b rv\" id=\"bCap\" style=\"--d:.12s\">\n      <h3>ความจุอ่างแม่นาเรือ</h3>\n      <div class=\"flexrow\"><svg class=\"ring\" viewBox=\"0 0 120 120\" aria-hidden=\"true\"><circle class=\"bg\" cx=\"60\" cy=\"60\" r=\"48\"/><circle class=\"fg\" id=\"ringFg\" cx=\"60\" cy=\"60\" r=\"48\" style=\"--c:0\"/></svg>\n        <div><div class=\"num\"><span data-num=\"cap\" data-dec=\"1\">0</span><small>%</small></div><div class=\"cap\" id=\"capNote\">—</div></div></div>\n    </div>\n    <div class=\"card b rv\" id=\"bSpill\" style=\"--d:.05s\">\n      <span class=\"alive-dot\"></span>\n      <h3>น้ำล้นสปิลเวย์ (บัญชีน้ำวันล่าสุด)</h3>\n      <div class=\"num\"><span data-num=\"spill\">0</span><small>ลบ.ม.</small></div><div class=\"cap\" id=\"spillNote\">—</div>\n    </div>\n    <div class=\"card b rv\" id=\"bRain\" style=\"--d:.12s\">\n      <h3>ฝนสะสม 24 ชั่วโมง (สันอ่าง)</h3>\n      <div class=\"num\"><span data-num=\"rain\" data-dec=\"1\">0</span><small>มม.</small></div><div class=\"cap\" id=\"rainNote\">—</div>\n    </div>\n    <div class=\"card b w rv\" id=\"bBal\" style=\"--d:.19s\">\n      <h3>น้ำเข้า เทียบ น้ำออก (บัญชีน้ำวันล่าสุด)</h3>\n      <div class=\"trio\" style=\"margin-top:6px\"><div><div class=\"num\" style=\"color:var(--accent)\" data-num=\"in\">0</div><div class=\"cap\">ไหลเข้า (ลบ.ม.)</div></div><div><div class=\"num\" style=\"color:var(--accent-2)\" data-num=\"out\">0</div><div class=\"cap\">ระบายรวม ท่อ+ล้น (ลบ.ม.)</div></div></div>\n      <div class=\"balance\"><i class=\"in\" style=\"width:50%\"></i><i class=\"out\" style=\"width:50%\"></i></div>\n      <div class=\"cap\" id=\"balNote\">—</div>\n    </div>\n  </div>\n</div></section>", "levels": "<section class=\"sec\" id=\"levels\"><div class=\"wrap\">\n  <div class=\"sec-head rv\"><div class=\"eyebrow\">ระดับน้ำย้อนหลัง</div><h2>ระดับน้ำอ่างแม่นาเรือเทียบสันสปิลเวย์</h2><p>เส้นสีน้ำตาล = สันสปิลเวย์ · เส้นจุดไข่ปลา = ระดับน้ำรายชั่วโมง · แรเงาแดง = ส่วนที่สูงกว่าสัน · เลื่อนเมาส์เพื่อดูค่ารายชั่วโมง</p></div>\n  <div class=\"card rv\"><div class=\"chart-box\" id=\"lvBox\"></div><div class=\"legend\"><span><i style=\"background:var(--ok)\"></i>ต่ำกว่าสัน</span><span><i style=\"background:var(--warn)\"></i>ใกล้สัน (&lt; 0.10 ม.)</span><span><i style=\"background:var(--crit)\"></i>สูงกว่าสัน</span></div></div>\n</div></section>", "daily": "<section class=\"sec\" id=\"daily\"><div class=\"wrap\">\n  <div class=\"sec-head rv\"><div class=\"eyebrow\">เปรียบเทียบรายวัน</div><h2>14 วันที่ผ่านมา</h2><p>ตัวเลขเหนือแท่ง = ค่าของวัน · ตัวเลขสีเหนือค่า = เปลี่ยนจากวันก่อน (ส้มแดง = เพิ่ม, เขียว = ลด, ฟ้า = เท่าเดิม)</p></div>\n  <div class=\"card rv\">\n    <div style=\"display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:8px\">\n      <div><div class=\"cap\" id=\"dailyTitle\" style=\"color:var(--muted);font-size:13px\">—</div><div style=\"font-size:30px;font-weight:800;color:var(--strong)\" id=\"dailyBig\">—</div></div>\n      <div class=\"seg\" id=\"dailySeg\"><i class=\"ind\"></i><button data-k=\"inflow\" class=\"on\">น้ำไหลเข้า</button><button data-k=\"release\">น้ำระบาย</button><button data-k=\"rain\">ฝน</button><button data-k=\"volume\">ปริมาตร</button></div>\n    </div>\n    <div class=\"chart-box\" id=\"dailyBox\"></div>\n  </div>\n</div></section>", "forecast": "<section class=\"sec\" id=\"forecast\"><div class=\"wrap\">\n  <div class=\"sec-head rv\"><div class=\"eyebrow\">พยากรณ์น้ำไหลเข้าอ่าง</div><h2>1–7 วันข้างหน้า</h2><p>เส้นโค้งเรียบระหว่างจุดพยากรณ์ (เป็นค่าประมาณระหว่างจุด) · เส้นประ \"ตอนนี้\" คือค่าล่าสุดจากบัญชีน้ำ</p></div>\n  <div class=\"card rv\"><div class=\"chart-box\" id=\"fcBox\"></div><div class=\"cap\" id=\"fcNote\" style=\"font-size:12.5px;color:var(--faint);margin-top:6px\"></div></div>\n</div></section>", "stations": "<section class=\"sec\" id=\"stations\"><div class=\"wrap\">\n  <div class=\"sec-head rv\"><div class=\"eyebrow\">ทุกสถานี</div><h2>สถานีและอ่างเก็บน้ำในพื้นที่</h2><p>เส้นจิ๋วแสดงระดับน้ำ ~48 ชั่วโมงล่าสุด สีตามแนวโน้ม</p></div>\n  <div class=\"card rv tbl-wrap\"><table class=\"st\"><thead><tr><th>สถานี</th><th>ระดับน้ำ (ม.)</th><th>เส้นแนวโน้ม</th><th>6 ชม.</th><th>ฝน 24 ชม.</th><th>ความจุ</th><th>สถานะ</th></tr></thead><tbody id=\"stBody\"></tbody></table></div>\n</div></section>", "dock": "<div class=\"dock\" id=\"dock\" aria-label=\"ย้อนดูข้อมูล\">\n  <button class=\"play\" id=\"play\" aria-label=\"เล่น/หยุด\"><svg viewBox=\"0 0 24 24\" fill=\"currentColor\"><path id=\"playIc\" d=\"M8 5v14l11-7z\"/></svg></button>\n  <div class=\"lbl\"><small id=\"dockSub\">ย้อนดูข้อมูล</small><b id=\"dockLbl\">ปัจจุบัน</b></div>\n  <div class=\"dtrack\"><svg id=\"dockStrip\" viewBox=\"0 0 100 34\" preserveAspectRatio=\"none\" aria-hidden=\"true\"></svg><input type=\"range\" id=\"slider\" min=\"0\" max=\"0\" value=\"0\" aria-label=\"เลื่อนย้อนเวลา\"></div>\n  <button class=\"live-btn\" id=\"toLive\">ล่าสุด</button>\n</div>\n\n", "station": "<div class=\"sec\">\n  <div class=\"stbar\"><div class=\"seg\" id=\"stSeg\"><i class=\"ind\"></i></div><span class=\"live\" id=\"live\"><i></i><span id=\"liveText\" data-sk>กำลังโหลดข้อมูล…</span></span></div>\n  <div class=\"hero-grid stack\">\n    <div class=\"scene\" id=\"scene\" role=\"img\" aria-label=\"ภาพจำลองระดับน้ำเทียบสันสปิลเวย์\"></div>\n    <aside class=\"readout wide\" id=\"readout\">\n      <div class=\"rcol\"><small id=\"roName\" data-sk>—</small><div class=\"big\"><span id=\"roLevel\" data-sk>000.000</span><span>ม.รทก.</span></div><div class=\"delta\" id=\"roDelta\" data-sk>—</div><small id=\"roTrend\" data-sk>—</small>\n        <div class=\"capb\"><div class=\"capn\" id=\"roCapNW\"><span id=\"roCapN\">0</span><small>% ของความจุ</small></div><div class=\"captrack\"><i class=\"f\" id=\"roCapF\"></i><i class=\"o\" id=\"roCapO\"></i><b class=\"m\" id=\"roCapM\"></b></div><div class=\"caplbl\" id=\"roCapL\">เส้นขีด = 100% (ระดับสันสปิลเวย์)</div></div></div>\n      <div class=\"rcol\"><div class=\"note\" id=\"roNote\" data-sk>—</div><div class=\"tele mini rv\" id=\"teleBox\"></div></div>\n    </aside>\n  </div>\n  <div class=\"card rv\" style=\"margin-top:16px\"><h3 id=\"lvTitle\">ระดับน้ำย้อนหลังเทียบสันสปิลเวย์</h3><div class=\"chart-box\" id=\"lvBox\"></div><div class=\"legend\"><span><i style=\"background:var(--ok)\"></i>ต่ำกว่าสัน</span><span><i style=\"background:var(--warn)\"></i>ใกล้สัน (&lt; 0.10 ม.)</span><span><i style=\"background:var(--crit)\"></i>สูงกว่าสัน</span></div></div>\n</div>", "kwan": "<div class=\"sec\"><div class=\"stbar\"><span class=\"live\" id=\"live\"><i></i><span id=\"liveText\" data-sk>กำลังโหลดข้อมูล…</span></span><i id=\"kwanMark\" hidden></i></div>\n  <div class=\"hero-grid\"><div class=\"scene\" id=\"scene\" role=\"img\" aria-label=\"ภาพจำลองระดับน้ำกว๊านพะเยาเทียบตลิ่ง\"></div>\n    <aside class=\"readout\" id=\"readout\"><small id=\"roName\" data-sk>—</small><div class=\"big\"><span id=\"roLevel\" data-sk>000.000</span><span>ม.รทก.</span></div><div class=\"delta\" id=\"roDelta\" data-sk>—</div><small id=\"roTrend\" data-sk>—</small><div class=\"note\" id=\"roNote\" data-sk>—</div></aside></div></div>", "resTable": "<div class=\"sec\" style=\"padding:4px 0\"><div class=\"card rv tbl-wrap\"><table class=\"st\"><thead><tr><th>อ่างเก็บน้ำ</th><th>ระดับ spillway (ม.)</th><th>ความจุที่ spillway</th><th>ระดับน้ำปัจจุบัน (ม.)</th><th>เส้นแนวโน้ม</th><th>6 ชม.</th><th>% ความจุ</th><th>สถานะ</th></tr></thead><tbody id=\"resBody\"></tbody></table></div></div>", "month": "<div class=\"sec\" style=\"padding:4px 0 22px\"><div class=\"bento\" id=\"mBox\">\n  <div class=\"card b w rv\" style=\"--d:.03s\"><svg class=\"waves-bg\" viewBox=\"0 0 800 120\" preserveAspectRatio=\"none\" aria-hidden=\"true\"><path d=\"M0 40 q50 -30 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0\"/><path d=\"M0 80 q60 30 120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0\"/></svg>\n    <h3 id=\"mTitle\">สรุปน้ำเข้า–น้ำออกของเดือน</h3>\n    <div class=\"trio\"><div><div class=\"num\" style=\"color:var(--accent)\"><span id=\"mIn\">0</span></div><div class=\"cap\">น้ำไหลเข้ารวม (ลบ.ม.)</div></div><div><div class=\"num\" style=\"color:var(--accent-2)\"><span id=\"mOut\">0</span></div><div class=\"cap\">ระบายรวม ท่อ+ล้น (ลบ.ม.)</div></div><div><div class=\"num\" id=\"mNetBox\"><span id=\"mNet\">0</span></div><div class=\"cap\">ΔS สุทธิ (ลบ.ม.)</div></div></div>\n    <div class=\"balance\"><i class=\"in\" id=\"mBalIn\" style=\"width:50%\"></i><i class=\"out\" id=\"mBalOut\" style=\"width:50%\"></i></div><div class=\"cap\" id=\"mBalNote\">—</div></div>\n  <div class=\"card b rv\" style=\"--d:.1s\"><h3>ปริมาตรกักเก็บสิ้นเดือน</h3><div class=\"flexrow\"><svg class=\"ring\" viewBox=\"0 0 120 120\" aria-hidden=\"true\"><circle class=\"bg\" cx=\"60\" cy=\"60\" r=\"48\"/><circle class=\"fg\" id=\"mRingFg\" cx=\"60\" cy=\"60\" r=\"48\" style=\"--c:0\"/><circle class=\"fg ov\" id=\"mRingOv\" cx=\"60\" cy=\"60\" r=\"48\" style=\"--c:0\"/></svg>\n    <div><div class=\"num\"><span id=\"mCapN\">0</span><small>%</small></div><div class=\"cap\" id=\"mCapNote\">—</div></div></div></div>\n  <div class=\"card b rv\" id=\"mSpill\" style=\"--d:.05s\"><span class=\"alive-dot\"></span><h3>วันที่ล้นสปิลเวย์</h3><div class=\"num\"><span id=\"mSpD\">0</span><small>วัน</small></div>\n    <div class=\"ratio\" id=\"mDays\"><i class=\"r-sp\"></i><i class=\"r-rn\"></i><i class=\"r-flat\"></i></div><div class=\"cap\" id=\"mSpNote\">—</div><div class=\"num sm\" style=\"margin-top:8px\"><span id=\"mSpS\">0</span><small>ลบ.ม. น้ำล้นรวม</small></div></div>\n  <div class=\"card b rv\" style=\"--d:.1s\"><h3>ฝนสะสมทั้งเดือน</h3><div class=\"num\"><span id=\"mRain\">0</span><small>มม.</small></div><div class=\"cap\" id=\"mRainNote\">—</div></div>\n  <div class=\"card b rv\" id=\"mLvBox\" style=\"--d:.15s\"><h3>ระดับน้ำรายวัน (ม.รทก.)</h3><div class=\"num sm\"><span id=\"mLv1\">—</span> → <span id=\"mLv2\">—</span></div><svg id=\"mSpark\" class=\"spark-big\" viewBox=\"0 0 300 56\" preserveAspectRatio=\"none\"></svg><div class=\"cap\" id=\"mLvNote\">—</div></div>\n</div></div>"};
var NULL = new Proxy(function () {}, { get: function (t, k) { return k === Symbol.toPrimitive ? function () { return ''; } : k === 'length' ? 0 : NULL; }, set: function () { return true; }, apply: function () { return NULL; } });
var g = function (n) { return fetch('assets/data/' + n + '.json', { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error(n + ' ' + r.status); return r.json(); }); };
function loadData() {
  return Promise.all(['monitoring', 'water_ledger', 'inflow_6h_display', 'latest', 'flood_latest'].map(g)).then(function (a) {
    var mon = a[0], led = a[1], w6 = a[2], lat = a[3], fl = a[4];
    var stations = mon.stations.map(function (s) { var o = {}; ['station_code', 'name_th', 'spillway_msl', 'water_level', 'rainfall_1h', 'measure_datetime', 'storage_m3', 'storage_max_m3', 'capacity_pct', 'name_en', 'temperature', 'humidity', 'pressure', 'solar', 'distance_to_spillway_m'].forEach(function (k) { o[k] = s[k]; }); o.history = (s.history || []); o.rain = (s.rainfall_hourly || []).slice(-72); return o; });
    var ledger = led.rows.slice(-45).map(function (r) { return { date: r.date, level: r.water_level_m, volume: r.water_volume_m3, inflow: r.inflow_m3, release: (r.outlet_release_m3 || 0) + (r.spill_m3 || 0), spill: r.spill_m3 || 0, rain: r.rain_24h_mm || 0 }; });
    var allrows = led.rows.map(function (r) { return { date: r.date, year: r.year, month: r.month, level: r.water_level_m, volume: r.water_volume_m3, inflow: r.inflow_m3, outlet: r.outlet_release_m3 || 0, spill: r.spill_m3 || 0, rain: r.rain_24h_mm || 0, evap: r.evap_m3, infil: r.infiltration_m3, dS: r.delta_s_m3 }; });
    var inf = lat.forecasts.inflow.forecast, base = new Date(inf.as_of_date), day = function (h) { return new Date(base.getTime() + h * 864e5).toISOString().slice(0, 10); };
    var fc = [{ date: day(0), h: 0, v: inf.current_qin_m3_per_day }];
    for (var h = 1; h <= 7; h++) { var p = inf.horizons['h' + h]; if (p) fc.push({ date: day(h), h: h, v: p.prediction_m3_per_day, low: !!p.low_confidence }); }
    return { snapshot: new Date().toISOString(), monitoring_updated: mon.meta.updated, capacity_m3: 1625000, crest: 489.545, max_level_seen: Math.max.apply(null, led.rows.map(function (r) { return r.water_level_m; })),
      stations: stations, reservoirs: mon.reservoirs || [], ledger: ledger, allrows: allrows, windows: w6.windows, forecast: fc,
      kwan: { level: fl.kwan_now.level, change_3d: fl.kwan_now.change_3d, bank: fl.banks.Mae_Main1, bank_ronghai: fl.banks.RongHai, flag: fl.flags.overall, generated_at: fl.generated_at } };
  });
}
function run(D, ROOTS, HOSTS) {
  const $ = (s, r) => { if (r && r.querySelector) return r.querySelector(s) || NULL; for (const x of ROOTS) { const e = x.querySelector(s); if (e) return e; } return NULL; };
  const $$ = (s, r) => r && r.querySelectorAll ? [...r.querySelectorAll(s)] : ROOTS.flatMap(x => [...x.querySelectorAll(s)]);
  const reduced = () => document.documentElement.classList.contains('uk-reduce') || matchMedia('(prefers-reduced-motion: reduce)').matches;

const MON = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const fmt = (v, d = 0) => Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const sgn = (v, d = 3) => (v > 0 ? '+' : v < 0 ? '−' : '±') + Math.abs(v).toFixed(d);
const fmtK = v => { const a = Math.abs(v); return a >= 1e6 ? (v / 1e6).toFixed(3) + 'M' : a >= 1e3 ? (v / 1e3).toFixed(1) + 'k' : String(Math.round(v * 10) / 10); };
const p2 = n => String(n).padStart(2, '0');
const fmtDT = d => `${d.getDate()} ${MON[d.getMonth()]} ${p2(d.getHours())}:${p2(d.getMinutes())}`;
const fmtD = s => { const d = new Date(s + 'T00:00:00'); return `${d.getDate()} ${MON[d.getMonth()]}`; };
const safeLS = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };

function tween(from, to, dur, fn, ease) {
  ease = ease || (e => 1 - Math.pow(1 - e, 4)); // easeOutQuart
  if (reduced() || dur <= 0) { fn(to); return; }
  const t0 = performance.now();
  (function f(t) { const p = clamp((t - t0) / dur, 0, 1); fn(from + (to - from) * ease(p)); if (p < 1) requestAnimationFrame(f); })(t0);
}

function placeInd(seg) {
  const on = $('button.on', seg), ind = $('.ind', seg); if (!on || !ind) return;
  seg.style.setProperty('--x', on.offsetLeft + 'px'); seg.style.setProperty('--w', on.offsetWidth + 'px');
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



/* =============== BOOT (ukm) =============== */
function prepDraw(root) { $$('.draw', root).forEach(p => { try { p.style.setProperty('--len', Math.ceil(p.getTotalLength()) + 2); } catch (e) {} }); }
function sync() {
  const rt = document.documentElement, mode = rt.dataset.ukMode === 'dark' ? 'dark' : 'light';
  HOSTS.forEach(h => { h.dataset.mode = mode; h.dataset.motion = rt.classList.contains('uk-reduce') ? 'reduce' : 'normal'; });
  $$('.seg').forEach(placeInd);
}
buildScene(); initKPI(); buildLevels(); buildForecast(); buildTable(); buildResTable();
ROOTS.forEach(r => prepDraw(r));
bindTips('#dailyBox', '#dailyTT'); bindTips('#fcBox', '#fcTT');
{
  const st = status(R2.water_level, CREST);
  $('#heroState').textContent = st === 'crit' ? 'ล้นสปิลเวย์' : st === 'warn' ? 'ใกล้ล้น' : 'ปกติ';
  const L = D.ledger[D.ledger.length - 1];
  $('#heroSub').textContent = st === 'crit'
    ? `ระดับน้ำสูงกว่าสันสปิลเวย์ ${(R2.water_level - CREST).toFixed(3)} ม. มีน้ำล้นผ่านสปิลเวย์ ${fmt(L.spill)} ลบ.ม. ในวันที่ ${fmtD(L.date)}`
    : `ระดับน้ำต่ำกว่าสันสปิลเวย์ ${(CREST - R2.water_level).toFixed(3)} ม.`;
}
initDock(); updateLive(); setInterval(updateLive, 30000);
if (has('#stSeg')) initStations();
if (has('#kwanMark')) initKwan();
initMonth();
$('#dailySeg').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  $$('#dailySeg button').forEach(x => x.classList.toggle('on', x === b)); placeInd($('#dailySeg')); renderDaily(b.dataset.k);
});
window.addEventListener('uk-theme', sync); window.addEventListener('resize', () => $$('.seg').forEach(placeInd));
document.fonts && document.fonts.ready.then(() => $$('.seg').forEach(placeInd));
sync();
const finish = () => {
  HOSTS.forEach(h => h.classList.remove('is-loading')); $$('[data-sk]').forEach(n => n.removeAttribute('data-sk'));
  liveReadout(false);
  if (!reduced() && scene.waterG.animate) scene.waterG.animate([{ transform: `translateY(${yOf(ST.water_level) - Y_BASE + 170}px)` }, { transform: `translateY(${yOf(ST.water_level) - Y_BASE}px)` }], { duration: 1900, easing: 'cubic-bezier(.16,1,.3,1)' });
  initReveal(); $$('.seg').forEach(placeInd);
};
setTimeout(finish, reduced() ? 0 : 700);

}
function mount(D) {
  var ROOTS = [], HOSTS = [];
  function host(html, where) {
    var h = document.createElement('div'); h.className = 'ukm-host is-loading'; var sr = h.attachShadow({ mode: 'open' });
    var st = document.createElement('style'); st.textContent = CSS; sr.appendChild(st);
    var box = document.createElement('div'); box.innerHTML = html; while (box.firstChild) sr.appendChild(box.firstChild);
    where(h); ROOTS.push(sr); HOSTS.push(h); return h;
  }
  cfg.plans.forEach(function (p) {
    var anchor = null; try { anchor = document.querySelector(p.anchor); } catch (e) {} if (!anchor) return;
    var html = p.mods.map(function (m) { return TPL[m]; }).join('');
    if (p.hide) { var st = document.createElement('style'); st.textContent = p.hide + '{display:none!important}'; document.head.appendChild(st); }
    if (!p.mods.length) return;
    host(html, function (h) {
      if (p.pos === 'section-after') { var sec = document.createElement('section'); sec.className = 'section'; var w = document.createElement('div'); w.className = 'wrap'; w.appendChild(h); sec.appendChild(w); anchor.parentNode.insertBefore(sec, anchor.nextSibling); }
      else if (p.pos === 'before') anchor.parentNode.insertBefore(h, anchor);
      else anchor.parentNode.insertBefore(h, anchor.nextSibling);
    });
  });
  if (cfg.dock) host(TPL.dock, function (h) { document.body.appendChild(h); });
  if (!ROOTS.length) return;
  try { run(D, ROOTS, HOSTS); } catch (e) { console.error('ukm', e); }
}
function start() { loadData().then(mount).catch(function (e) { console.warn('ukm: โหลดข้อมูลไม่สำเร็จ', e); }); }
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
