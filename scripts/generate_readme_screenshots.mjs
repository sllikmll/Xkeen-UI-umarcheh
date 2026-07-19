import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from '@playwright/test';

const ROOT = process.cwd();
const DATA_DIR = process.env.XKEEN_SCREENSHOT_DATA_DIR || '/tmp/xkeen-live';
const OUT_DIR = path.join(ROOT, 'docs/screenshots');

async function readJson(name, fallback = {}) {
  try { return JSON.parse(await fs.readFile(path.join(DATA_DIR, name), 'utf8')); }
  catch { return fallback; }
}
function esc(v) { return String(v ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
function delayOf(proxy) {
  const h = Array.isArray(proxy?.history) ? proxy.history : [];
  const last = h[h.length - 1];
  return typeof last?.delay === 'number' ? `${last.delay} ms` : (proxy?.alive ? 'online' : '—');
}
function badge(text, cls='') { return `<span class="badge ${cls}">${esc(text)}</span>`; }
function nodeCard(name, p = {}, selected=false) {
  const alive = p.alive === true;
  const type = p.type || 'Proxy';
  return `<div class="node-card ${selected ? 'selected' : ''}">
    <div class="node-name">${esc(name)}</div>
    <div class="node-meta"><span>${esc(type)}</span><span class="dot ${alive ? 'ok' : 'bad'}"></span>${esc(delayOf(p))}</div>
  </div>`;
}
function selectorBlock(name, proxy, proxies, limit=16) {
  const all = Array.isArray(proxy?.all) ? proxy.all : [];
  const now = proxy?.now || all[0] || 'DIRECT';
  const visible = all.slice(0, limit);
  return `<section class="panel-card selector-section">
    <div class="section-head"><div><h2>${esc(name)}</h2><p>Сейчас: <b>${esc(now)}</b></p></div><button>Обновить все пинги</button></div>
    <div class="nodes-grid">${visible.map((n) => nodeCard(n, proxies[n] || {type:'Provider'}, n===now)).join('')}</div>
  </section>`;
}
function selectorList(selectors, proxies) {
  return selectors.map(([name, p]) => {
    const all = Array.isArray(p.all) ? p.all : [];
    const now = p.now || all[0] || 'DIRECT';
    return `<div class="selector-row"><div><b>${esc(name)}</b><span>${esc((p.type || 'Selector'))} · ${all.length} вариантов</span></div><select><option>${esc(now)}</option>${all.filter(x=>x!==now).slice(0,4).map(x=>`<option>${esc(x)}</option>`).join('')}</select><button>${esc(delayOf(proxies[now] || {}))}</button></div>`;
  }).join('');
}
function connectionRows(conns) {
  return conns.slice(0, 12).map((c) => {
    const m = c.metadata || {};
    const src = `${m.sourceIP || '172.16.0.x'}:${m.sourcePort || ''}`;
    const dst = m.host || m.destinationIP || m.destination || 'service.local';
    const chain = Array.isArray(c.chains) ? c.chains.join(' › ') : 'DIRECT';
    return `<tr><td>${esc(src)}</td><td>${esc(dst)}</td><td>${esc(m.network || 'tcp')}</td><td>${esc(c.rule || 'MATCH')}</td><td>${esc(chain)}</td><td><button>Разорвать</button></td></tr>`;
  }).join('');
}
function protocolCards(registry, proxies) {
  const labels = {wireguard:'WireGuard', amnezia:'Amnezia', hysteria2:'Hysteria2', vless:'VLESS', trojan:'Trojan', mieru:'Meiru', naiveproxy:'NaiveProxy'};
  return Object.entries(labels).map(([proto,label]) => {
    const items = (registry.connections || []).filter(c => c.protocol === proto);
    const item = items[0];
    const runtime = item ? proxies[item.name] : null;
    const status = item ? (item.mihomoSupported ? (runtime?.alive ? 'online' : 'imported') : 'staging') : 'empty';
    const used = item?.usedBySelectors?.length || 0;
    return `<div class="proto-card ${status}"><div class="proto-title">${esc(label)}</div><div class="proto-status">${esc(status)}</div><div class="proto-name">${esc(item?.name || 'Добавьте ссылку или файл')}</div><div class="proto-foot">${item ? `${used} selector’ов · ${esc(runtime?.type || 'registry')}` : 'link/file import'}</div></div>`;
  }).join('');
}
function frame({title, subtitle, active='Маршрутизация', body, side=''}) {
  const tabs = ['Маршрутизация','Mihomo','Соединения','DAT GeoIP / GeoSite','WireGuard','Amnezia','Hysteria2','VLESS','Trojan','Meiru','NaiveProxy','Интерфейс','Настройки','Mihomo Генератор'];
  return `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body>
  <div class="app">
    <header><div class="brand"><span class="logo"></span><b>Xkeen UI Unified</b></div><div class="top-actions"><span class="pill">v2.4.11-unified</span><span class="pill green">Mihomo v1.19.29</span><button>UI</button><button>DevTools</button><button class="danger">Выйти</button></div></header>
    <nav>${tabs.map(t=>`<span class="tab ${t===active?'active':''}">${esc(t)}</span>`).join('')}</nav>
    <main><div class="content ${side?'with-side':''}"><section class="hero"><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></section>${body}</div>${side ? `<aside>${side}</aside>` : ''}</main>
  </div></body></html>`;
}
const CSS = `
*{box-sizing:border-box} body{margin:0;background:#050b18;color:#e7eefc;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif} .app{width:1600px;height:1000px;padding:28px;background:radial-gradient(circle at 20% 0%,#19386d 0,#08152b 32%,#050b18 75%)}
header{height:70px;display:flex;align-items:center;justify-content:space-between;border:1px solid rgba(148,163,184,.16);background:rgba(8,18,38,.72);border-radius:22px;padding:0 20px;box-shadow:0 24px 80px rgba(0,0,0,.32)}.brand{display:flex;gap:12px;align-items:center;font-size:24px}.logo{width:18px;height:18px;border-radius:50%;background:#38f29b;box-shadow:0 0 26px #38f29b}.top-actions{display:flex;gap:10px;align-items:center}.pill,button{border:1px solid rgba(148,163,184,.2);background:rgba(15,31,63,.9);color:#dce8ff;border-radius:12px;padding:9px 12px;font-size:14px}.green{color:#8ff5b7}.danger{background:#471827;color:#ffc5d1}
nav{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}.tab{padding:10px 13px;border:1px solid rgba(148,163,184,.16);border-radius:14px;background:rgba(10,21,43,.78);color:#aebddd;font-size:14px}.tab.active{background:linear-gradient(135deg,#2563eb,#14b8a6);color:white;box-shadow:0 12px 34px rgba(37,99,235,.35)}
main{display:grid;grid-template-columns:1fr;gap:18px}.content.with-side{display:block} main:has(aside){grid-template-columns:minmax(0,1fr) 380px}.hero{margin-bottom:14px}.hero h1{font-size:36px;margin:0 0 8px}.hero p{margin:0;color:#9fb2d5;font-size:17px}.panel-card,aside{border:1px solid rgba(148,163,184,.16);border-radius:24px;background:rgba(7,17,35,.76);box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 24px 90px rgba(0,0,0,.28);padding:18px;margin-bottom:16px}.section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.section-head h2{margin:0;font-size:24px}.section-head p{margin:4px 0 0;color:#a9bad8}.nodes-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}.node-card{min-height:86px;border:1px solid rgba(148,163,184,.16);border-radius:18px;background:linear-gradient(135deg,rgba(16,33,68,.85),rgba(8,17,34,.9));padding:13px}.node-card.selected{border-color:#3cf2a1;box-shadow:0 0 0 1px rgba(60,242,161,.2),0 12px 30px rgba(20,184,166,.18)}.node-name{font-weight:700;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.node-meta{margin-top:16px;display:flex;gap:8px;align-items:center;color:#a9bad8;font-size:13px}.dot{width:8px;height:8px;border-radius:50%;display:inline-block}.ok{background:#41e391}.bad{background:#64748b}.selector-row{display:grid;grid-template-columns:240px 1fr 110px;gap:14px;align-items:center;border:1px solid rgba(148,163,184,.14);border-radius:16px;background:rgba(11,24,50,.7);padding:12px;margin-bottom:10px}.selector-row span{display:block;color:#94a3b8;font-size:13px;margin-top:3px}select{width:100%;border:1px solid rgba(148,163,184,.22);background:#08152b;color:#dce8ff;border-radius:12px;padding:10px}.manual pre,.dat pre{white-space:pre-wrap;background:#050b18;border-radius:16px;padding:14px;line-height:1.5;color:#b9d7ff;border:1px solid rgba(148,163,184,.12)}.proto-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.proto-card{min-height:160px;border:1px solid rgba(148,163,184,.16);border-radius:22px;padding:16px;background:linear-gradient(135deg,rgba(17,34,68,.88),rgba(7,16,33,.92))}.proto-card.online{border-color:#43e69a}.proto-card.imported{border-color:#60a5fa}.proto-card.staging{border-color:#f59e0b}.proto-title{font-size:22px;font-weight:800}.proto-status{display:inline-block;margin-top:10px;border-radius:999px;padding:5px 9px;background:rgba(148,163,184,.16);color:#cbd5e1}.proto-name{margin-top:18px;font-weight:700;color:#e2e8f0}.proto-foot{margin-top:12px;color:#94a3b8}.api-list{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.api-card{border:1px solid rgba(148,163,184,.14);border-radius:18px;padding:16px;background:rgba(10,22,45,.72)}table{width:100%;border-collapse:collapse;overflow:hidden;border-radius:16px}td,th{padding:12px;border-bottom:1px solid rgba(148,163,184,.12);text-align:left;font-size:14px}th{color:#9fb2d5}tr{background:rgba(8,18,38,.62)}.badge{display:inline-block;border-radius:999px;padding:6px 9px;margin:3px;background:rgba(96,165,250,.16);color:#bcd7ff}.badge.good{background:rgba(65,227,145,.14);color:#a9f6c7}.muted{color:#94a3b8}`;

async function render(name, html) {
  await fs.mkdir(OUT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  await page.setContent(html, { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(OUT_DIR, name), fullPage: false });
  await browser.close();
  console.log(name);
}

const version = await readJson('mihomo-version.json');
const pData = await readJson('mihomo-proxies.json');
const cData = await readJson('mihomo-connections.json');
const registry = await readJson('xkeen-protocol-registry.json');
const proxies = pData.proxies || {};
const selectors = Object.entries(proxies).filter(([,p]) => Array.isArray(p.all)).sort(([a],[b]) => a.localeCompare(b, 'ru'));
const priority = ['Ручной список','AI','CDN','Telegram','YouTube','GitHub','Discord','Twitter'];
const selPriority = priority.map(n => [n, proxies[n]]).filter(([,p]) => p);

await render('xkeen-routing-mihomo.png', frame({
  title: 'Маршрутизация Mihomo', active: 'Маршрутизация',
  subtitle: 'Runtime selector-группы, быстрые ping-и и ручной список в одной панели на 8088.',
  body: `${selectorBlock('AI', proxies.AI, proxies, 12)}${selectorBlock('CDN', proxies.CDN, proxies, 12)}`,
  side: `<h2>Ручной список</h2><p class="muted">/opt/etc/mihomo/rules/manual-proxy.yaml</p><div>${badge('DOMAIN-SUFFIX,2ip.ru','good')}${badge('DOMAIN-SUFFIX,codex.sale','good')}${badge('обновить provider')}</div><div class="manual"><pre>- DOMAIN-SUFFIX,2ip.ru\n- DOMAIN-SUFFIX,2ip.io\n- DOMAIN-SUFFIX,codex.sale</pre></div>`
}));
await render('xkeen-selectors-tiles.png', frame({
  title: 'Селекторы плитками', active: 'Маршрутизация', subtitle: 'Плиточный режим остаётся вариантом по умолчанию: удобно видеть задержки и активный сервер.',
  body: `${selectorBlock('Ручной список', proxies['Ручной список'], proxies, 18)}${selectorBlock('YouTube', proxies.YouTube, proxies, 12)}`
}));
await render('xkeen-selectors-list.png', frame({
  title: 'Селекторы списком', active: 'Маршрутизация', subtitle: 'Компактный режим: selector + dropdown, чтобы разместить много групп на одной странице.',
  body: `<section class="panel-card">${selectorList(selPriority, proxies)}</section>`
}));
await render('xkeen-protocol-connections.png', frame({
  title: 'Подключения по протоколам', active: 'WireGuard', subtitle: 'WireGuard, Amnezia, Hysteria2, VLESS, Trojan, Meiru и NaiveProxy импортируются ссылкой или файлом.',
  body: `<section class="panel-card"><div class="proto-grid">${protocolCards(registry, proxies)}</div></section><section class="panel-card"><div class="api-list"><div class="api-card"><b>Registry</b><p class="muted">${(registry.connections||[]).length} подключений</p></div><div class="api-card"><b>Mihomo runtime</b><p class="muted">${Object.keys(proxies).length} proxy/group</p></div><div class="api-card"><b>Version</b><p class="muted">${esc(version.version || 'v1.19.x')}</p></div></div></section>`
}));
await render('xkeen-connections-geodat.png', frame({
  title: 'Соединения и DAT GeoIP / GeoSite', active: 'Соединения', subtitle: 'Детальный список активных соединений, фильтрация по хостам и служебная вкладка DAT.',
  body: `<section class="panel-card"><table><thead><tr><th>Источник</th><th>Назначение</th><th>Сеть</th><th>Правило</th><th>Цепочка</th><th></th></tr></thead><tbody>${connectionRows(cData.connections || [])}</tbody></table></section>`,
  side: `<h2>DAT GeoIP / GeoSite</h2><p class="muted">Обновление, состав и редактирование источников.</p><div>${badge('GeoIP RU','good')}${badge('GeoSite','good')}${badge('MRS cache')}</div><div class="dat"><pre>ru@ipcidr\ncategory-ai@domain\nmanual-proxy@classical\nspeedtest@domain\nvodafone@ipcidr</pre></div>`
}));
