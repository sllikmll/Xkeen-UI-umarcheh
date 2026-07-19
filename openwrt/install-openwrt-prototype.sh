#!/bin/sh
set -eu

UI_ROOT="/www/unified-ui"
CGI_PATH="/www/cgi-bin/unified-ui-api"
CONF_DIR="/etc/unified-ui"
CONF_FILE="$CONF_DIR/openwrt.env"
BUILD_FILE="$CONF_DIR/BUILD.json"
UPDATE_SCRIPT="$CONF_DIR/openwrt-update.sh"
UNINSTALL_SCRIPT="$CONF_DIR/openwrt-uninstall.sh"
BACKUP_DIR="$CONF_DIR/backups"
PROFILE_FILE="/etc/nikki/profiles/manual-mihomo.yaml"
VERSION="${UNIFIED_OPENWRT_VERSION:-dev-local}"
UPDATE_URL="${UNIFIED_OPENWRT_UPDATE_URL:-}"

mkdir -p "$UI_ROOT" "$CONF_DIR" /www/cgi-bin "$BACKUP_DIR"

_secret="$(uci -q get nikki.mixin.api_secret 2>/dev/null || true)"
_secret_q="$(printf '%s' "$_secret" | sed "s/'/'\\''/g")"
_profile_q="$(printf '%s' "$PROFILE_FILE" | sed "s/'/'\\''/g")"
_version_q="$(printf '%s' "$VERSION" | sed "s/'/'\\''/g")"
_update_url_q="$(printf '%s' "$UPDATE_URL" | sed "s/'/'\\''/g")"
{
  printf "%s\n" "UNIFIED_UI_NAME='Unified UI OpenWrt'"
  printf "%s\n" "MIHOMO_CONTROLLER='http://127.0.0.1:6060'"
  printf "MIHOMO_SECRET='%s'\n" "$_secret_q"
  printf "%s\n" "MIHOMO_RUN_DIR='/etc/nikki/run'"
  printf "%s\n" "MIHOMO_CONFIG='/etc/nikki/run/config.yaml'"
  printf "%s\n" "MIHOMO_INIT='/etc/init.d/nikki'"
  printf "MIHOMO_PROFILE='%s'\n" "$_profile_q"
  printf "%s\n" "UNIFIED_UI_ROOT='/www/unified-ui'"
  printf "%s\n" "UNIFIED_UI_CGI='/www/cgi-bin/unified-ui-api'"
  printf "%s\n" "UNIFIED_UI_CONF_DIR='/etc/unified-ui'"
  printf "%s\n" "UNIFIED_UI_BUILD_FILE='/etc/unified-ui/BUILD.json'"
  printf "%s\n" "UNIFIED_UI_BACKUP_DIR='/etc/unified-ui/backups'"
  printf "UNIFIED_UI_VERSION='%s'\n" "$_version_q"
  printf "UNIFIED_UI_UPDATE_URL='%s'\n" "$_update_url_q"
} > "$CONF_FILE"
chmod 600 "$CONF_FILE"

cat > "$BUILD_FILE" <<EOF
{
  "version": "${VERSION}",
  "release_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "update_url": "${UPDATE_URL}"
}
EOF
chmod 644 "$BUILD_FILE"

cat > "$UPDATE_SCRIPT" <<'UPD'
#!/bin/sh
set -eu
CONF_FILE="/etc/unified-ui/openwrt.env"
[ -f "$CONF_FILE" ] && . "$CONF_FILE"
UPDATE_URL="${UNIFIED_UI_UPDATE_URL:-}"
[ -n "$UPDATE_URL" ] || UPDATE_URL="$(jsonfilter -i /etc/unified-ui/BUILD.json -e '@.update_url' 2>/dev/null || true)"
if [ -z "$UPDATE_URL" ]; then
  echo "No update_url configured in /etc/unified-ui/BUILD.json or env." >&2
  exit 1
fi
TMP_DIR="/tmp/unified-ui-openwrt-update-$$"
ARCHIVE="$TMP_DIR/unified-ui-openwrt.tar.gz"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM
curl -fL --max-time 120 -o "$ARCHIVE" "$UPDATE_URL"
tar -xzf "$ARCHIVE" -C "$TMP_DIR"
INSTALLER="$(find "$TMP_DIR" -maxdepth 2 -type f -name install.sh | head -1)"
[ -n "$INSTALLER" ] || { echo "install.sh not found in update archive" >&2; exit 1; }
sh "$INSTALLER"
UPD
chmod 755 "$UPDATE_SCRIPT"

cat > "$UNINSTALL_SCRIPT" <<'UNINST'
#!/bin/sh
set -eu
rm -f /www/cgi-bin/unified-ui-api
rm -rf /www/unified-ui
rm -rf /etc/unified-ui
printf 'Unified UI OpenWrt removed.\n'
UNINST
chmod 755 "$UNINSTALL_SCRIPT"

cat > "$CGI_PATH" <<'CGI'
#!/bin/sh
CONF_FILE="/etc/unified-ui/openwrt.env"
[ -f "$CONF_FILE" ] && . "$CONF_FILE"
MIHOMO_CONTROLLER="${MIHOMO_CONTROLLER:-http://127.0.0.1:6060}"
MIHOMO_SECRET="${MIHOMO_SECRET:-}"
MIHOMO_INIT="${MIHOMO_INIT:-/etc/init.d/nikki}"
MIHOMO_CONFIG="${MIHOMO_CONFIG:-/etc/nikki/run/config.yaml}"
MIHOMO_RUN_DIR="${MIHOMO_RUN_DIR:-/etc/nikki/run}"
MIHOMO_PROFILE="${MIHOMO_PROFILE:-/etc/nikki/profiles/manual-mihomo.yaml}"
UNIFIED_UI_BUILD_FILE="${UNIFIED_UI_BUILD_FILE:-/etc/unified-ui/BUILD.json}"
UNIFIED_UI_BACKUP_DIR="${UNIFIED_UI_BACKUP_DIR:-/etc/unified-ui/backups}"
UNIFIED_UI_VERSION="${UNIFIED_UI_VERSION:-dev-local}"
UNIFIED_UI_UPDATE_URL="${UNIFIED_UI_UPDATE_URL:-}"

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

mihomo_req() {
  method="$1"
  path="$2"
  body="${3:-}"
  if [ -n "$MIHOMO_SECRET" ]; then
    header_name="Authorization"
    header_value="Bearer $MIHOMO_SECRET"
    if [ -n "$body" ]; then
      curl -sS --max-time 12 -X "$method" -H "$header_name: $header_value" -H 'Content-Type: application/json' --data "$body" "$MIHOMO_CONTROLLER$path"
    else
      curl -sS --max-time 12 -X "$method" -H "$header_name: $header_value" "$MIHOMO_CONTROLLER$path"
    fi
  else
    if [ -n "$body" ]; then
      curl -sS --max-time 12 -X "$method" -H 'Content-Type: application/json' --data "$body" "$MIHOMO_CONTROLLER$path"
    else
      curl -sS --max-time 12 -X "$method" "$MIHOMO_CONTROLLER$path"
    fi
  fi
}

read_body() {
  len="${CONTENT_LENGTH:-0}"
  case "$len" in ''|*[!0-9]*) len=0 ;; esac
  if [ "$len" -gt 0 ]; then
    dd bs=1 count="$len" 2>/dev/null
  fi
}

ui_update_url() {
  if [ -n "$UNIFIED_UI_UPDATE_URL" ]; then
    printf '%s' "$UNIFIED_UI_UPDATE_URL"
  elif [ -f "$UNIFIED_UI_BUILD_FILE" ]; then
    jsonfilter -i "$UNIFIED_UI_BUILD_FILE" -e '@.update_url' 2>/dev/null || true
  fi
}

validate_profile_content() {
  tmp="/tmp/unified-ui-validate-$$.yaml"
  cat > "$tmp"
  out="$({ /usr/bin/mihomo -t -d "$MIHOMO_RUN_DIR" -f "$tmp"; } 2>&1)"
  code=$?
  rm -f "$tmp"
  printf '%s\n__EXIT__%s' "$out" "$code"
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
    upd="$(ui_update_url)"
    printf '{"ok":true,"pid":"%s","version":"%s","ui_version":"%s","controller":"%s","config":"%s","config_exists":%s,"profile":"%s","profile_exists":%s,"update_url":"%s"}' \
      "$pid" "$ver" "$UNIFIED_UI_VERSION" "$MIHOMO_CONTROLLER" "$MIHOMO_CONFIG" "$([ -f "$MIHOMO_CONFIG" ] && echo true || echo false)" "$MIHOMO_PROFILE" "$([ -f "$MIHOMO_PROFILE" ] && echo true || echo false)" "$upd"
    ;;
  /select)
    body="$(read_body)"
    group_enc="$(printf '%s' "$body" | jsonfilter -e '@.groupEncoded' 2>/dev/null || true)"
    name="$(printf '%s' "$body" | jsonfilter -e '@.name' 2>/dev/null || true)"
    if [ -z "$group_enc" ] || [ -z "$name" ]; then
      hdr_json '400 Bad Request'
      printf '{"ok":false,"error":"groupEncoded and name are required"}'
      exit 0
    fi
    name_json="$(printf '%s' "$name" | json_escape)"
    hdr_json
    mihomo_req PUT "/proxies/$group_enc" "{\"name\":\"$name_json\"}" || printf '{"ok":false,"error":"mihomo select failed"}'
    ;;
  /delay)
    body="$(read_body)"
    name_enc="$(printf '%s' "$body" | jsonfilter -e '@.nameEncoded' 2>/dev/null || true)"
    test_url="$(printf '%s' "$body" | jsonfilter -e '@.url' 2>/dev/null || true)"
    timeout="$(printf '%s' "$body" | jsonfilter -e '@.timeout' 2>/dev/null || true)"
    [ -n "$timeout" ] || timeout=5000
    [ -n "$test_url" ] || test_url='https://www.gstatic.com/generate_204'
    if [ -z "$name_enc" ]; then
      hdr_json '400 Bad Request'
      printf '{"ok":false,"error":"nameEncoded is required"}'
      exit 0
    fi
    hdr_json
    mihomo_req GET "/proxies/$name_enc/delay?timeout=$timeout&url=$test_url" || printf '{"ok":false,"error":"mihomo delay failed"}'
    ;;
  /connection-close)
    body="$(read_body)"
    id="$(printf '%s' "$body" | jsonfilter -e '@.id' 2>/dev/null || true)"
    if [ -z "$id" ]; then
      hdr_json '400 Bad Request'
      printf '{"ok":false,"error":"id is required"}'
      exit 0
    fi
    hdr_json
    mihomo_req DELETE "/connections/$id" || printf '{"ok":false,"error":"mihomo close connection failed"}'
    ;;
  /connections-close-all)
    hdr_json
    mihomo_req DELETE "/connections" || printf '{"ok":false,"error":"mihomo close all failed"}'
    ;;
  /config-get)
    hdr_json
    if [ ! -f "$MIHOMO_PROFILE" ]; then
      printf '{"ok":false,"error":"profile not found","path":"%s"}' "$MIHOMO_PROFILE"
      exit 0
    fi
    content="$(cat "$MIHOMO_PROFILE")"
    esc_content="$(printf '%s' "$content" | json_escape)"
    upd="$(ui_update_url)"
    printf '{"ok":true,"path":"%s","ui_version":"%s","update_url":"%s","content":"%s"}' "$MIHOMO_PROFILE" "$UNIFIED_UI_VERSION" "$upd" "$esc_content"
    ;;
  /config-validate)
    body="$(read_body)"
    content="$(printf '%s' "$body" | jsonfilter -e '@.content' 2>/dev/null || true)"
    if [ -z "$content" ]; then
      hdr_json '400 Bad Request'
      printf '{"ok":false,"error":"content is required"}'
      exit 0
    fi
    result="$(printf '%s' "$content" | validate_profile_content || true)"
    code="$(printf '%s' "$result" | sed -n 's/^__EXIT__//p' | tail -1)"
    out="$(printf '%s' "$result" | sed '/^__EXIT__/d')"
    esc_out="$(printf '%s' "$out" | json_escape)"
    hdr_json
    if [ "${code:-1}" = "0" ]; then
      printf '{"ok":true,"exit_code":0,"output":"%s"}' "$esc_out"
    else
      printf '{"ok":false,"exit_code":%s,"output":"%s"}' "${code:-1}" "$esc_out"
    fi
    ;;
  /config-save)
    body="$(read_body)"
    content="$(printf '%s' "$body" | jsonfilter -e '@.content' 2>/dev/null || true)"
    apply="$(printf '%s' "$body" | jsonfilter -e '@.apply' 2>/dev/null || true)"
    [ -n "$apply" ] || apply=false
    if [ -z "$content" ]; then
      hdr_json '400 Bad Request'
      printf '{"ok":false,"error":"content is required"}'
      exit 0
    fi
    result="$(printf '%s' "$content" | validate_profile_content || true)"
    code="$(printf '%s' "$result" | sed -n 's/^__EXIT__//p' | tail -1)"
    out="$(printf '%s' "$result" | sed '/^__EXIT__/d')"
    esc_out="$(printf '%s' "$out" | json_escape)"
    hdr_json
    if [ "${code:-1}" != "0" ]; then
      printf '{"ok":false,"error":"validation failed","exit_code":%s,"output":"%s"}' "${code:-1}" "$esc_out"
      exit 0
    fi
    mkdir -p "$UNIFIED_UI_BACKUP_DIR"
    ts="$(date +%Y%m%d-%H%M%S)"
    backup="$UNIFIED_UI_BACKUP_DIR/manual-mihomo-$ts.yaml"
    cp "$MIHOMO_PROFILE" "$backup"
    printf '%s' "$content" > "$MIHOMO_PROFILE"
    chmod 644 "$MIHOMO_PROFILE"
    before="$(pidof mihomo 2>/dev/null || true)"
    changed=false
    if [ "$apply" = "true" ] || [ "$apply" = "1" ]; then
      restart_out="$($MIHOMO_INIT restart 2>&1 || true)"
      sleep 3
      after="$(pidof mihomo 2>/dev/null || true)"
      [ "$before" != "$after" ] && changed=true
      esc_restart="$(printf '%s' "$restart_out" | json_escape)"
      printf '{"ok":true,"saved":true,"applied":true,"backup":"%s","before":"%s","after":"%s","pid_changed":%s,"validation_output":"%s","restart_log":"%s"}' "$backup" "$before" "$after" "$changed" "$esc_out" "$esc_restart"
    else
      printf '{"ok":true,"saved":true,"applied":false,"backup":"%s","validation_output":"%s"}' "$backup" "$esc_out"
    fi
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
    .card h2{margin:0 0 10px;font-size:16px}.muted{color:var(--muted);font-size:13px}.kv{display:grid;grid-template-columns:140px 1fr;gap:8px;font-size:13px}.btn{border:0;border-radius:10px;padding:9px 12px;cursor:pointer;font-weight:800;background:#18314f;color:var(--text)}.btn.primary{background:linear-gradient(135deg,#168bff,#42d392);color:#001524}.btn.warn{background:#5a3510;color:#ffd9a3}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
    table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}th{color:#bcd0ea}.pill{display:inline-flex;border-radius:999px;padding:3px 8px;background:#162944;color:#bdd2ef;font-size:12px}.online{background:rgba(61,220,151,.18);color:#8dffc8}.offline{background:rgba(255,93,108,.18);color:#ff9ba5}pre,textarea{white-space:pre-wrap;word-break:break-word;background:#08111e;border:1px solid var(--line);border-radius:12px;padding:10px;max-height:420px;overflow:auto}.hidden{display:none}select,input,textarea{background:#091728;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:7px;max-width:100%}.btn.small{padding:5px 8px;font-size:12px}.toast{position:fixed;right:16px;bottom:16px;background:#10233d;border:1px solid var(--line);border-radius:12px;padding:10px 12px;box-shadow:0 20px 50px rgba(0,0,0,.35);z-index:20}.cfg{width:100%;min-height:520px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;line-height:1.45;resize:vertical}
  </style>
</head>
<body>
<header><h1><span class="dot"></span>Unified UI <span class="muted">OpenWrt / Nikki / Mihomo</span></h1><div class="tabs"><button class="tab active" data-view="status">Статус</button><button class="tab" data-view="selectors">Маршрутизация</button><button class="tab" data-view="connections">Соединения</button><button class="tab" data-view="config">Конфиг</button><button class="tab" data-view="raw">Raw API</button></div></header>
<main>
  <section id="view-status" class="view grid"><div class="card"><h2>Состояние Mihomo</h2><div id="status" class="kv muted">Загрузка…</div><div class="toolbar"><button class="btn primary" onclick="loadAll()">Обновить</button><button class="btn warn" onclick="restartMihomo()">Restart Nikki/Mihomo</button></div></div><div class="card"><h2>OpenWrt адаптер</h2><p class="muted">Лёгкий backend без Python: uhttpd CGI → Mihomo API :6060 + safe editor для manual-mihomo.yaml.</p><pre id="restartLog">Пока без рестартов.</pre></div></section>
  <section id="view-selectors" class="view hidden"><div class="card"><h2>Селекторы / группы</h2><div class="toolbar"><button class="btn primary" onclick="loadProxies()">Обновить</button><button class="btn" onclick="pingVisible()">Обновить все пинги</button></div><div class="muted" id="proxySummary"></div><div id="groups"></div></div></section>
  <section id="view-connections" class="view hidden"><div class="card"><h2>Активные соединения</h2><div class="toolbar"><button class="btn primary" onclick="loadConnections()">Обновить соединения</button><button class="btn warn" onclick="closeAllConnections()">Разорвать все</button><input id="connFilter" placeholder="Фильтр host/IP/process" oninput="renderConnections()"></div><div id="connections"></div></div></section>
  <section id="view-config" class="view hidden"><div class="card"><h2>Редактор manual-mihomo.yaml</h2><div class="muted" id="configMeta">Загрузка…</div><div class="toolbar"><button class="btn primary" onclick="loadConfigEditor()">Перечитать</button><button class="btn" onclick="validateConfig()">Проверить</button><button class="btn" onclick="saveConfig(false)">Сохранить</button><button class="btn warn" onclick="saveConfig(true)">Сохранить и применить</button></div><textarea id="configEditor" class="cfg" spellcheck="false"></textarea><pre id="configLog">Пока тихо.</pre></div></section>
  <section id="view-raw" class="view hidden grid"><div class="card"><h2>/configs</h2><pre id="rawConfigs"></pre></div><div class="card"><h2>/version</h2><pre id="rawVersion"></pre></div></section>
</main>
<script>
const API='/cgi-bin/unified-ui-api';
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let proxyCache={}; let connectionCache=[]; let visibleNodeNames=[];
function toast(msg){let t=document.createElement('div');t.className='toast';t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.remove(),2800)}
async function get(path){const r=await fetch(API+path,{cache:'no-store'}); if(!r.ok) throw new Error(path+' HTTP '+r.status); return r.json();}
async function post(path, body={}){const r=await fetch(API+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'}); if(!r.ok) throw new Error(path+' HTTP '+r.status); const txt=await r.text(); return txt?JSON.parse(txt):{};}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.view').forEach(v=>v.classList.add('hidden'));$('#view-'+b.dataset.view).classList.remove('hidden');});
async function loadStatus(){try{const s=await get('/status');$('#status').innerHTML=`<b>PID</b><span>${esc(s.pid||'нет')}</span><b>Mihomo</b><span>${esc(s.version||'unknown')}</span><b>UI version</b><span>${esc(s.ui_version||'')}</span><b>Controller</b><span>${esc(s.controller)}</span><b>Config</b><span>${esc(s.config)} · ${s.config_exists?'есть':'нет'}</span><b>Profile</b><span>${esc(s.profile)} · ${s.profile_exists?'есть':'нет'}</span>`;}catch(e){$('#status').textContent=e.message;}}
function latency(p){const h=p.history||[]; const last=h[h.length-1]; return typeof last?.delay==='number'?last.delay+' ms':'—';}
function optionList(g){return (g.all||[]).map(n=>`<option value="${esc(n)}" ${n===g.now?'selected':''}>${esc(n)}</option>`).join('')}
async function selectProxy(group,name){try{await post('/select',{group,groupEncoded:encodeURIComponent(group),name});toast(`Выбрано: ${group} → ${name}`);await loadProxies();}catch(e){toast('Ошибка выбора: '+e.message)}}
async function pingProxy(name){try{const d=await post('/delay',{name,nameEncoded:encodeURIComponent(name),timeout:5000,url:'https://www.gstatic.com/generate_204'});toast(`${name}: ${d.delay??'нет ответа'} ms`);await loadProxies();}catch(e){toast('Ping error: '+name+' · '+e.message)}}
async function pingVisible(){for(const n of visibleNodeNames.slice(0,80)){await pingProxy(n)}}
async function loadProxies(){const data=await get('/proxies'); proxyCache=data.proxies||{}; const proxies=proxyCache; const groups=Object.values(proxies).filter(p=>Array.isArray(p.all)); const nodes=Object.values(proxies).filter(p=>!Array.isArray(p.all)); visibleNodeNames=[...new Set(groups.flatMap(g=>g.all||[]).filter(n=>proxies[n] && !Array.isArray(proxies[n].all)))]; $('#proxySummary').textContent=`Групп: ${groups.length} · узлов/служебных proxy: ${nodes.length}`; $('#groups').innerHTML=groups.map((g,idx)=>`<h3>${esc(g.name)} <span class="pill">${esc(g.type)}</span> <span class="muted">сейчас: ${esc(g.now||'')}</span></h3><div class="toolbar"><select id="sel-${idx}">${optionList(g)}</select><button class="btn primary small" onclick="selectProxy(${JSON.stringify(g.name)}, document.getElementById('sel-${idx}').value)">Применить выбор</button></div><table><thead><tr><th>Proxy</th><th>Тип</th><th>Статус</th><th>Ping</th><th>Действия</th></tr></thead><tbody>${(g.all||[]).map(n=>{const p=proxies[n]||{}; const alive=p.alive===false?'offline':'online'; return `<tr><td>${esc(n)}</td><td>${esc(p.type||'')}</td><td><span class="pill ${alive}">${alive}</span></td><td><button class="btn small" onclick="pingProxy(${JSON.stringify(n)})">${esc(latency(p))}</button></td><td><button class="btn primary small" onclick="selectProxy(${JSON.stringify(g.name)}, ${JSON.stringify(n)})">Выбрать</button></td></tr>`}).join('')}</tbody></table>`).join('');}
async function loadConnections(){try{const d=await get('/connections'); connectionCache=d.connections||[]; renderConnections();}catch(e){$('#connections').textContent=e.message;}}
function renderConnections(){const q=($('#connFilter')?.value||'').toLowerCase(); const arr=connectionCache.filter(c=>JSON.stringify(c).toLowerCase().includes(q)); $('#connections').innerHTML=`<p class="muted">Соединений: ${arr.length} / ${connectionCache.length}</p><table><thead><tr><th>Host</th><th>Source</th><th>Process</th><th>Rule</th><th>Chains</th><th>Upload/Download</th><th></th></tr></thead><tbody>${arr.slice(0,300).map(c=>`<tr><td>${esc(c.metadata?.host||c.metadata?.destinationIP||'')}</td><td>${esc(c.metadata?.sourceIP||'')}:${esc(c.metadata?.sourcePort||'')}</td><td>${esc(c.metadata?.process||'')}</td><td>${esc(c.rule||'')}</td><td>${esc((c.chains||[]).join(' → '))}</td><td>${esc(c.upload||0)} / ${esc(c.download||0)}</td><td><button class="btn warn small" onclick="closeConnection(${JSON.stringify(c.id)})">Разорвать</button></td></tr>`).join('')}</tbody></table>`;}
async function closeConnection(id){try{await post('/connection-close',{id});toast('Соединение разорвано');await loadConnections();}catch(e){toast('Ошибка разрыва: '+e.message)}}
async function closeAllConnections(){try{await post('/connections-close-all',{});toast('Все соединения разорваны');await loadConnections();}catch(e){toast('Ошибка: '+e.message)}}
async function loadConfigEditor(){try{const d=await get('/config-get'); $('#configEditor').value=d.content||''; $('#configMeta').textContent=`${d.path} · UI ${d.ui_version||''}`; $('#configLog').textContent='Конфиг перечитан.';}catch(e){$('#configMeta').textContent=e.message; $('#configLog').textContent=e.message;}}
async function validateConfig(){try{const d=await post('/config-validate',{content:$('#configEditor').value}); $('#configLog').textContent=(d.ok?'VALID OK\n':'VALID FAIL\n')+(d.output||''); toast(d.ok?'Конфиг валиден':'В конфиге ошибка');}catch(e){$('#configLog').textContent=e.message; toast('Validation error: '+e.message)}}
async function saveConfig(apply){try{const d=await post('/config-save',{content:$('#configEditor').value,apply:!!apply}); $('#configLog').textContent=JSON.stringify(d,null,2); toast(apply?'Сохранено и применено':'Сохранено'); if(apply) await loadStatus();}catch(e){$('#configLog').textContent=e.message; toast('Save error: '+e.message)}}
async function loadRaw(){for(const [id,path] of [['#rawConfigs','/configs'],['#rawVersion','/version']]){try{$(id).textContent=JSON.stringify(await get(path),null,2)}catch(e){$(id).textContent=e.message}}}
async function restartMihomo(){ $('#restartLog').textContent='Перезапускаю…'; try{const d=await get('/restart'); $('#restartLog').textContent=JSON.stringify(d,null,2); await new Promise(r=>setTimeout(r,1200)); loadAll(); }catch(e){$('#restartLog').textContent=e.message;} }
async function loadAll(){await loadStatus(); await Promise.allSettled([loadProxies(),loadConnections(),loadRaw(),loadConfigEditor()]);}
loadAll(); setInterval(loadStatus,10000);
</script>
</body>
</html>
HTML

printf 'Installed Unified UI OpenWrt:\n  %s\n  %s\n  update: %s\n' "$UI_ROOT/index.html" "$CGI_PATH" "$UPDATE_URL"
