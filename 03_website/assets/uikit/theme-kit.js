/* theme-kit.js — ธีมสี + ลูกเล่นแบบ drop-in (ไม่แก้โครงสร้างหน้าเดิม) */
(function(){
'use strict';
var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};
var clamp=function(v,a,b){return Math.min(b,Math.max(a,v))};
function h2r(h){h=h.replace('#','');return [0,2,4].map(function(i){return parseInt(h.substr(i,2),16)})}
function r2hsl(r,g,b){r/=255;g/=255;b/=255;var mx=Math.max(r,g,b),mn=Math.min(r,g,b),h=0,s=0,l=(mx+mn)/2;if(mx!==mn){var d=mx-mn;s=l>.5?d/(2-mx-mn):d/(mx+mn);h=mx===r?(g-b)/d+(g<b?6:0):mx===g?(b-r)/d+2:(r-g)/d+4;h*=60}return [h,s,l]}
function hsl2rgb(h,s,l){h=((h%360)+360)%360/360;if(s===0){var v=Math.round(l*255);return [v,v,v]}
  var q=l<.5?l*(1+s):l+s-l*s,p=2*l-q,f=function(t){t=(t+1)%1;return t<1/6?p+(q-p)*6*t:t<.5?q:t<2/3?p+(q-p)*(2/3-t)*6:p};
  return [f(h+1/3),f(h),f(h-1/3)].map(function(x){return Math.round(x*255)})}
var hex=function(c){return '#'+c.map(function(x){return ('0'+x.toString(16)).slice(-2)}).join('')};
var S=function(h,s,l){return hsl2rgb(h,s,l)};

var PAL=[
 {id:'ocean',n:'ฟ้าคราม',a:'#1f6f99',b:'#e0a94f',bg:200},
 {id:'lake',n:'ทะเลสาบ',a:'#2a9d8f',b:'#e0a94f',bg:193},
 {id:'emerald',n:'เขียวมรกต',a:'#1b8a6b',b:'#e08a1e',bg:160},
 {id:'violet',n:'ม่วงอเมทิสต์',a:'#6a4fc0',b:'#1fa28e',bg:256},
 {id:'sun',n:'ส้มพระอาทิตย์',a:'#d9692b',b:'#1f7fa8',bg:20},
 {id:'rose',n:'ชมพูบานเย็น',a:'#cf3f7f',b:'#2a8f98',bg:330},
 {id:'gold',n:'ทองสุริยา',a:'#b88a16',b:'#2a7f9e',bg:38}
];
var T={pal:'ocean',custom:'#1f6f99',mode:'light',reduce:0};
try{var sv=JSON.parse(localStorage.getItem('uk_theme2')||'{}');for(var k in sv)T[k]=sv[k]}catch(e){}
var VARS=['--teal-300','--teal-400','--teal-500','--teal-glow','--amber-400','--amber-300','--bg-950','--bg-900','--bg-800','--bg-700','--surface','--surface-hover','--text-100','--text-300','--text-500','--text-600','--border','--border-strong','--t3-rgb','--t4-rgb','--t5-rgb','--a4-rgb','--a3-rgb','--bg950-rgb','--bd-rgb','--w-rgb','--bg-glow-1','--bg-glow-2','--ok-400','--warn-400','--accent-ink'];
function modeNow(){if(T.mode==='dark')return 'dark';if(T.mode==='light')return 'light';var h=new Date().getHours();return(h>=18||h<6)?'dark':'light'}
function lum(c){var v=c.map(function(x){x/=255;return x<=.03928?x/12.92:Math.pow((x+.055)/1.055,2.4)});return .2126*v[0]+.7152*v[1]+.0722*v[2]}
function apply(save){
  var root=document.documentElement, st=root.style, mode=modeNow();
  VARS.forEach(function(v){st.removeProperty(v)});
  root.dataset.ukMode=mode; st.colorScheme=mode;
  var p=PAL.filter(function(x){return x.id===T.pal})[0]||PAL[0];
  if(T.pal==='custom'){var hs0=r2hsl.apply(null,h2r(T.custom));p={a:T.custom,b:hex(S(hs0[0]+165,clamp(hs0[1],.45,.8),.5)),bg:hs0[0]}}
  var rgb=function(c){return c.join(',')}, set=function(k,v){st.setProperty(k,v)};
  var a0=h2r(p.a),ah=r2hsl(a0[0],a0[1],a0[2]),b0=h2r(p.b),bh=r2hsl(b0[0],b0[1],b0[2]),H=p.bg;
  if(!(mode==='dark'&&p.id==='lake')){
    var t3,t4,t5,a4,a3;
    if(mode==='light'){
      t4=S(ah[0],ah[1],clamp(ah[2],.36,.48));t3=S(ah[0],ah[1],Math.max(clamp(ah[2],.36,.48)-.1,.26));t5=S(ah[0],ah[1],clamp(ah[2]-.04,.3,.42));
      a4=S(bh[0],bh[1],clamp(bh[2],.42,.56));a3=S(bh[0],bh[1],.38);
      var ink=S(H,.45,.2);
      set('--bg-950',hex(S(H,.55,.965)));set('--bg-900',hex(S(H,.5,.94)));set('--bg-800',hex(S(H,.4,.99)));set('--bg-700',hex(S(H,.4,.91)));
      set('--surface','rgba(255,255,255,.86)');set('--surface-hover','#ffffff');
      set('--text-100',hex(S(H,.6,.09)));set('--text-300',hex(S(H,.35,.22)));set('--text-500',hex(S(H,.2,.36)));set('--text-600',hex(S(H,.14,.47)));
      set('--border','rgba('+rgb(ink)+',.12)');set('--border-strong','rgba('+rgb(ink)+',.24)');set('--bd-rgb',rgb(ink));set('--w-rgb',rgb(ink));
      set('--bg950-rgb',rgb(S(H,.55,.965)));set('--bg-glow-1',hex(S(H,.7,.9)));set('--bg-glow-2',hex(S(H+40,.6,.93)));
      set('--ok-400','#1e9e6a');set('--warn-400','#b7791f');set('--teal-glow','rgba('+rgb(t4)+',.28)');
    }else{
      var L4=clamp(ah[2]+.12,.5,.66);
      t4=S(ah[0],ah[1],L4);t3=S(ah[0],ah[1],Math.min(L4+.14,.84));t5=S(ah[0],ah[1]*.95,Math.max(L4-.12,.26));
      a4=S(bh[0],bh[1],clamp(bh[2]+.1,.5,.66));a3=S(bh[0],bh[1],Math.min(clamp(bh[2]+.1,.5,.66)+.1,.85));
      var bg=function(l,s2){return S(H,s2||.62,l)};
      set('--bg-950',hex(bg(.07,.64)));set('--bg-900',hex(bg(.095,.58)));set('--bg-800',hex(bg(.13,.55)));set('--bg-700',hex(bg(.17,.52)));
      set('--text-100',hex(S(H,.25,.95)));set('--text-300',hex(S(H,.14,.8)));set('--text-500',hex(S(H,.1,.59)));set('--text-600',hex(S(H,.08,.47)));
      var bd=S(H,.22,.7);set('--border','rgba('+rgb(bd)+',.16)');set('--border-strong','rgba('+rgb(bd)+',.32)');set('--bd-rgb',rgb(bd));
      set('--bg950-rgb',rgb(bg(.07,.64)));set('--bg-glow-1',hex(S(H,.55,.17)));set('--bg-glow-2',hex(S(H-22,.5,.13)));set('--teal-glow','rgba('+rgb(t4)+',.35)');
    }
    set('--teal-400',hex(t4));set('--teal-300',hex(t3));set('--teal-500',hex(t5));set('--amber-400',hex(a4));set('--amber-300',hex(a3));
    set('--t3-rgb',rgb(t3));set('--t4-rgb',rgb(t4));set('--t5-rgb',rgb(t5));set('--a4-rgb',rgb(a4));set('--a3-rgb',rgb(a3));
    set('--accent-ink',lum(t4)>.45?'#0b1c27':'#ffffff');
  }else set('--accent-ink','#06161c');
  root.classList.toggle('uk-reduce',!!T.reduce);
  $$('#uk-sw button').forEach(function(b2){b2.classList.toggle('on',b2.dataset.id===T.pal)});
  $$('#uk-mode button').forEach(function(b2){b2.classList.toggle('on',b2.dataset.m===T.mode)});
  var cc=$('#uk-color');if(cc)cc.value=/^#[0-9a-f]{6}$/i.test(T.custom)?T.custom:'#1f6f99';
  var rt=$('#uk-reduce');if(rt){rt.classList.toggle('on',!!T.reduce);rt.textContent=T.reduce?'เปิดอยู่':'ปิดอยู่'}
  window.dispatchEvent(new CustomEvent('uk-theme',{detail:{mode:mode,accent:cssv('--teal-400'),accent2:cssv('--amber-400')}}));
  if(save)try{localStorage.setItem('uk_theme2',JSON.stringify(T))}catch(e){}
}
function cssv(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim()}
window.UK={accent:function(){return cssv('--teal-400')},accent2:function(){return cssv('--amber-400')},theme:T};

function buildUI(){
  var btn=document.createElement('button');btn.id='uk-btn';btn.setAttribute('aria-label','เปลี่ยนธีมสี');
  btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3a9 9 0 1 0 0 18c1.4 0 2-.8 2-1.7 0-.9-.6-1.3-.6-2.2 0-1 .8-1.6 1.8-1.6H17a4 4 0 0 0 4-4c0-4.4-4-8.5-9-8.5Z"/><circle cx="7.5" cy="11" r="1" fill="currentColor"/><circle cx="10.5" cy="7" r="1" fill="currentColor"/><circle cx="15" cy="7.5" r="1" fill="currentColor"/></svg>';
  var pop=document.createElement('div');pop.id='uk-pop';pop.setAttribute('role','dialog');
  pop.innerHTML='<h4>เลือกสีธีมเว็บ</h4><div id="uk-sw">'+PAL.map(function(p){return '<button data-id="'+p.id+'"><b style="background:linear-gradient(135deg,'+p.a+' 50%,'+p.b+' 50%)"></b>'+p.n+'</button>'}).join('')+'</div>'
   +'<div class="uk-row"><span>โหมด</span><span id="uk-mode"><button class="uk-tog" data-m="light">สว่าง</button> <button class="uk-tog" data-m="dark">มืด</button> <button class="uk-tog" data-m="auto">ตามเวลา</button></span></div>'
   +'<div class="uk-row"><span>สีที่เลือกเอง</span><input type="color" id="uk-color" value="#1f6f99"></div>'
   +'<div class="uk-row"><span>ลดการเคลื่อนไหว</span><button class="uk-tog" id="uk-reduce">ปิดอยู่</button></div>';
  document.body.appendChild(pop);document.body.appendChild(btn);
  btn.addEventListener('click',function(e){e.stopPropagation();pop.classList.toggle('open')});
  document.addEventListener('click',function(e){if(!pop.contains(e.target)&&e.target!==btn)pop.classList.remove('open')});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')pop.classList.remove('open')});
  $('#uk-sw').addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;T.pal=b.dataset.id;apply(true)});
  $('#uk-mode').addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;T.mode=b.dataset.m;apply(true)});
  $('#uk-color').addEventListener('input',function(e){T.pal='custom';T.custom=e.target.value;apply(true)});
  $('#uk-reduce').addEventListener('click',function(){T.reduce=T.reduce?0:1;apply(true)});
}

/* ---------- ลูกเล่นทั่วไป ---------- */
var REVEAL='.section-head,.nav-card,.kpi-card,.table-card,[class$="-card"]:not(.kpi-icon):not(.nav-card):not(.kpi-card):not(.table-card)';
function reveal(){
  var reduce=function(){return document.documentElement.classList.contains('uk-reduce')||matchMedia('(prefers-reduced-motion: reduce)').matches};
  if(!('IntersectionObserver' in window)||reduce())return;
  var els=$$(REVEAL).filter(function(e){return !e.closest('.site-header')&&!e.closest('#uk-pop')});
  var vh=innerHeight;
  els.forEach(function(e,i){
    var r=e.getBoundingClientRect();if(r.top>vh*1.5&&false)return;
    var sib=e.parentElement?Array.prototype.indexOf.call(e.parentElement.children,e):0;
    e.style.setProperty('--uk-d',(Math.min(sib,6)*.07).toFixed(2)+'s');e.classList.add('uk-rv');
  });
  var io=new IntersectionObserver(function(es){es.forEach(function(en){if(!en.isIntersecting)return;var e=en.target;e.classList.add('uk-in');io.unobserve(e);
    setTimeout(function(){e.classList.remove('uk-rv','uk-in');e.style.removeProperty('--uk-d')},1300)})},{threshold:.12});
  els.forEach(function(e){io.observe(e)});
}
function countUp(){
  var reduce=function(){return document.documentElement.classList.contains('uk-reduce')||matchMedia('(prefers-reduced-motion: reduce)').matches};
  function textNode(el){for(var n=el.firstChild;n;n=n.nextSibling){if(n.nodeType===3&&/\d/.test(n.nodeValue))return n}return null}
  function run(el){
    var tn=textNode(el);
    if(!tn){var raw=(el.textContent||'').trim();el.classList.toggle('uk-sk',/^[—–-]+$/.test(raw)||raw==='');return}
    el.classList.remove('uk-sk');
    var m=tn.nodeValue.match(/(-?[\d,]*\.?\d+)/);if(!m)return;
    var txt=m[1],to=parseFloat(txt.replace(/,/g,''));if(!isFinite(to))return;
    var dec=(txt.split('.')[1]||'').length,comma=txt.indexOf(',')>=0,key=tn.nodeValue;
    if(el._ukKey===key||reduce())return;el._ukKey=key;
    var pre=tn.nodeValue.slice(0,m.index),post=tn.nodeValue.slice(m.index+txt.length),t0=performance.now();
    (function f(t){var p=clamp((t-t0)/1300,0,1),v=to*(1-Math.pow(1-p,4)),s=v.toFixed(dec);
      if(comma){var q=s.split('.');q[0]=q[0].replace(/\B(?=(\d{3})+(?!\d))/g,',');s=q.join('.')}
      tn.nodeValue=pre+s+post;if(p<1)requestAnimationFrame(f);else{tn.nodeValue=key}})(t0);
  }
  var mo=new MutationObserver(function(ms){ms.forEach(function(m){if(m.target.nodeType===1)run(m.target)})});
  $$('.kpi-value').forEach(function(el){run(el);mo.observe(el,{childList:true})});
}
function init(){buildUI();apply(false);reveal();countUp()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
