#!/bin/sh
set -eu

UI_ROOT="/www/unified-ui"
CGI_PATH="/www/cgi-bin/unified-ui-api"
CONF_DIR="/etc/unified-ui"
CONF_FILE="$CONF_DIR/openwrt.env"

mkdir -p "$UI_ROOT" "$CONF_DIR" /www/cgi-bin

_secret="$(uci -q get nikki.mixin.api_secret 2>/dev/null || true)"
_secret_q="$(printf '%s' "$_secret" | sed "s/'/'\\''/g")"
{
  printf "%s\n" "UNIFIED_UI_NAME='Unified UI OpenWrt'"
  printf "%s\n" "MIHOMO_CONTROLLER='http://127.0.0.1:6060'"
  printf "MIHOMO_SECRET='%s'\n" "$_secret_q"
  printf "%s\n" "MIHOMO_RUN_DIR='/etc/nikki/run'"
  printf "%s\n" "MIHOMO_CONFIG='/etc/nikki/run/config.yaml'"
  printf "%s\n" "MIHOMO_INIT='/etc/init.d/nikki'"
} > "$CONF_FILE"
chmod 600 "$CONF_FILE"

cat > "$CGI_PATH" <<'CGI'
#!/bin/sh
CONF_FILE="/etc/unified-ui/openwrt.env"
[ -f "$CONF_FILE" ] && . "$CONF_FILE"
MIHOMO_CONTROLLER="${MIHOMO_CONTROLLER:-http://127.0.0.1:6060}"
MIHOMO_SECRET="${MIHOMO_SECRET:-}"
MIHOMO_INIT="${MIHOMO_INIT:-/etc/init.d/nikki}"
MIHOMO_CONFIG="${MIHOMO_CONFIG:-/etc/nikki/run/config.yaml}"

json_escape() {
  sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g; s/$/\\n/' | tr -d '\n' | sed 's/\\n$//'
}

hdr_json() {
  printf 'Status: %s\r\n' "${1:-200 OK}"
  printf 'Content-Type: application/json; charset=utf-8\r\n'
  printf 'Cache-Control: no-store\r\n\r\n'
}

mihomo_get() {
  path="$1"
  if [ -n "$MIHOMO_SECRET" ]; then
    header_name="Authorization"
    header_value="Bearer $MIHOMO_SECRET"
    curl -sS --max-time 8 -H "$header_name: $header_value" "$MIHOMO_CONTROLLER$path"
  else
    curl -sS --max-time 8 "$MIHOMO_CONTROLLER$path"
  fi
}

case "${PATH_INFO:-}" in
  /version)
    hdr_json
    mihomo_get /version || printf '{"ok":false,"error":"mihomo request failed"}'
    ;;
  /configs)
    hdr_json
    mihomo_get /configs || printf '{"ok":false,"error":"mihomo request failed"}'
    ;;
  /proxies)
    hdr_json
    mihomo_get /proxies || printf '{"ok":false,"error":"mihomo request failed"}'
    ;;
  /connections)
    hdr_json
    mihomo_get /connections || printf '{"ok":false,"error":"mihomo request failed"}'
    ;;
  /status)
    hdr_json
    pid="$(pidof mihomo 2>/dev/null || true)"
    ver="$(mihomo_get /version 2>/dev/null | jsonfilter -e '@.version' 2>/dev/null || true)"
    printf '{"ok":true,"pid":"%s","version":"%s","controller":"%s","config":"%s","config_exists":%s}' \
      "$pid" "$ver" "$MIHOMO_CONTROLLER" "$MIHOMO_CONFIG" "$([ -f "$MIHOMO_CONFIG" ] && echo true || echo false)"
    ;;
  /restart)
    before="$(pidof mihomo 2>/dev/null || true)"
    out="$($MIHOMO_INIT restart 2>&1)"
    sleep 3
    after="$(pidof mihomo 2>/dev/null || true)"
    hdr_json
    esc="$(printf '%s' "$out" | json_escape)"
    changed=false; [ "$before" != "$after" ] && changed=true
    printf '{"ok":true,"before":"%s","after":"%s","pid_changed":%s,"log":"%s"}' "$before" "$after" "$changed" "$esc"
    ;;
  *)
    hdr_json '404 Not Found'
    printf '{"ok":false,"error":"unknown endpoint","path":"%s"}' "${PATH_INFO:-}"
    ;;
esac
CGI
chmod +x "$CGI_PATH"

cat > "$UI_ROOT/index.html" <<'HTML'
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Unified UI — OpenWrt</title>
  <style>
    :root{color-scheme:dark;--bg:#07111f;--panel:#0d1b2e;--line:#20344f;--text:#e8f0fb;--muted:#94a9c6;--accent:#39a8ff;--ok:#3ddc97;--bad:#ff5d6c;--warn:#ffb84d}
    *{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at top left,#123a63 0,#07111f 38%,#050a12 100%);color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}
    header{position:sticky;top:0;z-index:5;background:rgba(7,17,31,.92);backdrop-filter:blur(14px);border-bottom:1px solid var(--line);padding:14px 18px;display:flex;gap:14px;align-items:center;justify-content:space-between}
    h1{font-size:18px;margin:0}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--ok);box-shadow:0 0 16px var(--ok);margin-right:8px}.tabs{display:flex;gap:8px;flex-wrap:wrap}.tab{border:1px solid var(--line);background:#0b1728;color:var(--text);border-radius:10px;padding:8px 11px;cursor:pointer}.tab.active{background:linear-gradient(135deg,#168bff,#42d392);border-color:transparent;color:#001524;font-weight:800}
    main{padding:18px;display:grid;gap:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.card{background:rgba(13,27,46,.88);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:0 20px 60px rgba(0,0,0,.22)}
    .card h2{margin:0 0 10px;font-size:16px}.muted{color:var(--muted);font-size:13px}.kv{display:grid;grid-template-columns:120px 1fr;gap:8px;font-size:13px}.btn{border:0;border-radius:10px;padding:9px 12px;cursor:pointer;font-weight:800;background:#18314f;color:var(--text)}.btn.primary{background:linear-gradient(135deg,#168bff,#42d392);color:#001524}.btn.warn{background:#5a3510;color:#ffd9a3}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
    table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}th{color:#bcd0ea}.pill{display:inline-flex;border-radius:999px;padding:3px 8px;background:#162944;color:#bdd2ef;font-size:12px}.online{background:rgba(61,220,151,.18);color:#8dffc8}.offline{background:rgba(255,93,108,.18);color:#ff9ba5}pre{white-space:pre-wrap;word-break:break-word;background:#08111e;border:1px solid var(--line);border-radius:12px;padding:10px;max-height:420px;overflow:auto}.hidden{display:none}
  </style>
</head>
<body>
<header><h1><span class="dot"></span>Unified UI <span class="muted">OpenWrt / Nikki / Mihomo</span></h1><div class="tabs"><button class="tab active" data-view="status">Статус</button><button class="tab" data-view="selectors">Маршрутизация</button><button class="tab" data-view="connections">Соединения</button><button class="tab" data-view="raw">Raw API</button></div></header>
<main>
  <section id="view-status" class="view grid"><div class="card"><h2>Состояние Mihomo</h2><div id="status" class="kv muted">Загрузка…</div><div class="toolbar"><button class="btn primary" onclick="loadAll()">Обновить</button><button class="btn warn" onclick="restartMihomo()">Restart Nikki/Mihomo</button></div></div><div class="card"><h2>OpenWrt адаптер</h2><p class="muted">Лёгкий backend без Python: uhttpd CGI → Mihomo API :6060 с secret из UCI Nikki.</p><pre id="restartLog">Пока без рестартов.</pre></div></section>
  <section id="view-selectors" class="view hidden"><div class="card"><h2>Селекторы / группы</h2><div class="muted" id="proxySummary"></div><div id="groups"></div></div></section>
  <section id="view-connections" class="view hidden"><div class="card"><h2>Активные соединения</h2><div class="toolbar"><button class="btn primary" onclick="loadConnections()">Обновить соединения</button></div><div id="connections"></div></div></section>
  <section id="view-raw" class="view hidden grid"><div class="card"><h2>/configs</h2><pre id="rawConfigs"></pre></div><div class="card"><h2>/version</h2><pre id="rawVersion"></pre></div></section>
</main>
<script>
const API='/cgi-bin/unified-ui-api';
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function get(path){const r=await fetch(API+path,{cache:'no-store'}); if(!r.ok) throw new Error(path+' HTTP '+r.status); return r.json();}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.view').forEach(v=>v.classList.add('hidden'));$('#view-'+b.dataset.view).classList.remove('hidden');});
async function loadStatus(){try{const s=await get('/status');$('#status').innerHTML=`<b>PID</b><span>${esc(s.pid||'нет')}</span><b>Version</b><span>${esc(s.version||'unknown')}</span><b>Controller</b><span>${esc(s.controller)}</span><b>Config</b><span>${esc(s.config)} · ${s.config_exists?'есть':'нет'}</span>`;}catch(e){$('#status').textContent=e.message;}}
function latency(p){const h=p.history||[]; const last=h[h.length-1]; return typeof last?.delay==='number'?last.delay+' ms':'—';}
async function loadProxies(){const data=await get('/proxies'); const proxies=data.proxies||{}; const groups=Object.values(proxies).filter(p=>Array.isArray(p.all)); const nodes=Object.values(proxies).filter(p=>!Array.isArray(p.all)); $('#proxySummary').textContent=`Групп: ${groups.length} · узлов/служебных proxy: ${nodes.length}`; $('#groups').innerHTML=groups.map(g=>`<h3>${esc(g.name)} <span class="pill">${esc(g.type)}</span> <span class="muted">сейчас: ${esc(g.now||'')}</span></h3><table><thead><tr><th>Proxy</th><th>Тип</th><th>Статус</th><th>Ping</th></tr></thead><tbody>${(g.all||[]).map(n=>{const p=proxies[n]||{}; const alive=p.alive===false?'offline':'online'; return `<tr><td>${esc(n)}</td><td>${esc(p.type||'')}</td><td><span class="pill ${alive}">${alive}</span></td><td>${esc(latency(p))}</td></tr>`}).join('')}</tbody></table>`).join('');}
async function loadConnections(){try{const d=await get('/connections'); const arr=d.connections||[]; $('#connections').innerHTML=`<p class="muted">Соединений: ${arr.length}</p><table><thead><tr><th>Host</th><th>Process</th><th>Rule</th><th>Chains</th><th>Upload/Download</th></tr></thead><tbody>${arr.slice(0,300).map(c=>`<tr><td>${esc(c.metadata?.host||c.metadata?.destinationIP||'')}</td><td>${esc(c.metadata?.process||'')}</td><td>${esc(c.rule||'')}</td><td>${esc((c.chains||[]).join(' → '))}</td><td>${esc(c.upload||0)} / ${esc(c.download||0)}</td></tr>`).join('')}</tbody></table>`;}catch(e){$('#connections').textContent=e.message;}}
async function loadRaw(){for(const [id,path] of [['#rawConfigs','/configs'],['#rawVersion','/version']]){try{$(id).textContent=JSON.stringify(await get(path),null,2)}catch(e){$(id).textContent=e.message}}}
async function restartMihomo(){ $('#restartLog').textContent='Перезапускаю…'; try{const d=await get('/restart'); $('#restartLog').textContent=JSON.stringify(d,null,2); await new Promise(r=>setTimeout(r,1200)); loadAll(); }catch(e){$('#restartLog').textContent=e.message;} }
async function loadAll(){await loadStatus(); await Promise.allSettled([loadProxies(),loadConnections(),loadRaw()]);}
loadAll(); setInterval(loadStatus,10000);
</script>
</body>
</html>
HTML

printf 'Installed Unified UI OpenWrt prototype:\n  /www/unified-ui/index.html\n  %s\n' "$CGI_PATH"
