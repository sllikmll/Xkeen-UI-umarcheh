#!/bin/sh
set -eu
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

UI_ROOT="/www/unified-ui"
CGI_PATH="/www/cgi-bin/unified-ui-api"
CONF_DIR="/etc/unified-ui"
CONF_FILE="$CONF_DIR/openwrt.env"
BUILD_FILE="$CONF_DIR/BUILD.json"
UPDATE_SCRIPT="$CONF_DIR/openwrt-update.sh"
UNINSTALL_SCRIPT="$CONF_DIR/openwrt-uninstall.sh"
BACKUP_DIR="$CONF_DIR/backups"
PROFILE_FILE="/etc/mihomo/config.yaml"
VERSION="${UNIFIED_OPENWRT_VERSION:-dev-local}"
UPDATE_URL="${UNIFIED_OPENWRT_UPDATE_URL:-}"

mkdir -p "$UI_ROOT" "$CONF_DIR" /www/cgi-bin "$BACKUP_DIR"

_secret="$(sed -n "s/^[[:space:]]*secret:[[:space:]]*['\"]\{0,1\}\([^'\"#]*\)['\"]\{0,1\}[[:space:]]*\(#.*\)\{0,1\}$/\1/p" /etc/mihomo/config.yaml 2>/dev/null | head -1 | sed 's/[[:space:]]*$//')"
_secret_q="$(printf '%s' "$_secret" | sed "s/'/'\\''/g")"
_profile_q="$(printf '%s' "$PROFILE_FILE" | sed "s/'/'\\''/g")"
_version_q="$(printf '%s' "$VERSION" | sed "s/'/'\\''/g")"
_update_url_q="$(printf '%s' "$UPDATE_URL" | sed "s/'/'\\''/g")"
{
  printf "%s\n" "UNIFIED_UI_NAME='Unified UI OpenWrt'"
  printf "%s\n" "MIHOMO_CONTROLLER='http://127.0.0.1:9090'"
  printf "MIHOMO_SECRET='%s'\n" "$_secret_q"
  printf "%s\n" "MIHOMO_RUN_DIR='/etc/mihomo'"
  printf "%s\n" "MIHOMO_CONFIG='/etc/mihomo/config.yaml'"
  printf "%s\n" "MIHOMO_INIT='/etc/init.d/mihomo'"
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
curl_args="-fL --max-time 120"
curl $curl_args -o "$ARCHIVE" "$UPDATE_URL"
tar -xzf "$ARCHIVE" -C "$TMP_DIR"
INSTALLER="$(find "$TMP_DIR" -maxdepth 2 -type f -name install.sh | head -1)"
[ -n "$INSTALLER" ] || { echo "install.sh not found in update archive" >&2; exit 1; }
sh "$INSTALLER"
UPD
chmod 755 "$UPDATE_SCRIPT"

ROUTER_BYPASS_INIT="/etc/init.d/unified-ui-router-bypass"
cat > "$ROUTER_BYPASS_INIT" <<'BYPASS'
#!/bin/sh /etc/rc.common
START=99
USE_PROCD=0
apply_rules() {
  for p in 8986 8987 8988 8989 8996 8997 8998 8999; do while ip rule del pref "$p" 2>/dev/null; do :; done; done
  ip rule add pref 8986 ipproto udp dport 53 lookup main
  ip rule add pref 8987 ipproto tcp dport 53 lookup main
  ip rule add pref 8988 ipproto tcp dport 80 lookup main
  ip rule add pref 8989 ipproto tcp dport 443 lookup main
}
start() { apply_rules; }
restart() { apply_rules; }
BYPASS
chmod 755 "$ROUTER_BYPASS_INIT"
"$ROUTER_BYPASS_INIT" enable >/dev/null 2>&1 || true
"$ROUTER_BYPASS_INIT" start >/dev/null 2>&1 || true

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
MIHOMO_CONTROLLER="${MIHOMO_CONTROLLER:-http://127.0.0.1:9090}"
MIHOMO_SECRET="${MIHOMO_SECRET:-}"
MIHOMO_INIT="${MIHOMO_INIT:-/etc/init.d/mihomo}"
MIHOMO_CONFIG="${MIHOMO_CONFIG:-/etc/mihomo/config.yaml}"
MIHOMO_RUN_DIR="${MIHOMO_RUN_DIR:-/etc/mihomo}"
MIHOMO_PROFILE="${MIHOMO_PROFILE:-/etc/mihomo/config.yaml}"
UNIFIED_UI_BUILD_FILE="${UNIFIED_UI_BUILD_FILE:-/etc/unified-ui/BUILD.json}"
UNIFIED_UI_CONF_DIR="${UNIFIED_UI_CONF_DIR:-/etc/unified-ui}"
UNIFIED_UI_BACKUP_DIR="${UNIFIED_UI_BACKUP_DIR:-/etc/unified-ui/backups}"
UNIFIED_UI_VERSION="${UNIFIED_UI_VERSION:-dev-local}"
UNIFIED_UI_UPDATE_URL="${UNIFIED_UI_UPDATE_URL:-}"
UNIFIED_UI_AUTH_USER="${UNIFIED_UI_AUTH_USER:-admin}"
UNIFIED_UI_AUTH_PASSWORD="${UNIFIED_UI_AUTH_PASSWORD:-admin}"
UNIFIED_UI_SESSION_FILE="${UNIFIED_UI_SESSION_FILE:-/tmp/unified-ui-session.token}"
UNIFIED_UI_SESSION_COOKIE="UnifiedUIOpenWrtSession"

json_escape() {
  sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g; s/$/\\n/' | tr -d '\n' | sed 's/\\n$//'
}

hdr_json() {
  printf 'Status: %s\r\n' "${1:-200 OK}"
  printf 'Content-Type: application/json; charset=utf-8\r\n'
  printf 'Cache-Control: no-store\r\n\r\n'
}

hdr_json_cookie() {
  status="${1:-200 OK}"
  cookie_line="${2:-}"
  printf 'Status: %s\r\n' "$status"
  printf 'Content-Type: application/json; charset=utf-8\r\n'
  printf 'Cache-Control: no-store\r\n'
  [ -n "$cookie_line" ] && printf 'Set-Cookie: %s\r\n' "$cookie_line"
  printf '\r\n'
}

cookie_value() {
  name="$1"
  printf '%s' "${HTTP_COOKIE:-}" | tr ';' '\n' | sed 's/^ *//' | sed -n "s/^$name=//p" | head -1
}

session_token() {
  if [ -f "$UNIFIED_UI_SESSION_FILE" ]; then
    cat "$UNIFIED_UI_SESSION_FILE" 2>/dev/null || true
  fi
}

new_session_token() {
  mkdir -p "$(dirname "$UNIFIED_UI_SESSION_FILE")"
  token="$(dd if=/dev/urandom bs=24 count=1 2>/dev/null | base64 | tr -d '=+/\n' | cut -c1-32)"
  [ -n "$token" ] || token="$(date +%s)-$$"
  printf '%s' "$token" > "$UNIFIED_UI_SESSION_FILE"
  chmod 600 "$UNIFIED_UI_SESSION_FILE" 2>/dev/null || true
  printf '%s' "$token"
}

is_auth_path() {
  case "${PATH_INFO:-}" in
    /auth-login|/auth-check|/auth-logout) return 0 ;;
    *) return 1 ;;
  esac
}

is_authenticated() {
  expected="$(session_token)"
  got="$(cookie_value "$UNIFIED_UI_SESSION_COOKIE")"
  [ -n "$expected" ] && [ -n "$got" ] && [ "$expected" = "$got" ]
}

require_auth_or_401() {
  if is_auth_path || is_authenticated; then return 0; fi
  hdr_json_cookie '401 Unauthorized'
  printf '{"ok":false,"authenticated":false,"error":"auth_required"}'
  exit 0
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

build_version() { jsonfilter -i "$UNIFIED_UI_BUILD_FILE" -e '@.version' 2>/dev/null || printf '%s' "$UNIFIED_UI_VERSION"; }
build_date() { jsonfilter -i "$UNIFIED_UI_BUILD_FILE" -e '@.release_date' 2>/dev/null || true; }
update_repo() { printf '%s' "${UNIFIED_UI_UPDATE_REPO:-sllikmll/Unified-UI}"; }
update_channel() { printf '%s' "${UNIFIED_UI_UPDATE_CHANNEL:-stable}"; }
update_branch() { printf '%s' "${UNIFIED_UI_UPDATE_BRANCH:-main}"; }

curl_github() {
  url="$1"
  curl -fsSL --max-time 20 "$url" 2>/tmp/unified-ui-gh.err
}

github_latest_json() {
  repo="$(update_repo)"
  tmp="/tmp/unified-ui-gh-latest-$$.json"
  if curl_github "https://api.github.com/repos/$repo/releases/latest" > "$tmp"; then
    tag="$(jsonfilter -i "$tmp" -e '@.tag_name' 2>/dev/null || true)"
    pub="$(jsonfilter -i "$tmp" -e '@.published_at' 2>/dev/null || true)"
    html="$(jsonfilter -i "$tmp" -e '@.html_url' 2>/dev/null || true)"
    assets="$(jsonfilter -i "$tmp" -e '@.assets[*].name' 2>/dev/null | awk 'BEGIN{printf "["} {gsub(/"/,"\\\""); if(NR>1)printf ","; printf "{\"name\":\"%s\"}",$0} END{printf "]"}')"
    rm -f "$tmp"
    [ -n "$assets" ] || assets='[]'
    printf '{"ok":true,"latest":{"kind":"stable","tag":"%s","published_at":"%s","url":"%s","assets":%s}}' "$(printf '%s' "$tag" | json_escape)" "$(printf '%s' "$pub" | json_escape)" "$(printf '%s' "$html" | json_escape)" "$assets"
  else
    err="$(cat /tmp/unified-ui-gh.err 2>/dev/null | json_escape)"
    rm -f "$tmp"
    printf '{"ok":false,"error":"github_unavailable","hint":"GitHub недоступен с роутера напрямую","meta":{"message":"%s"}}' "$err"
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


json_string_value() {
  key="$1"
  sed -n "s/.*\"$key\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -1
}

url_decode() {
  printf '%s' "$1" | sed 's/+/ /g; s/%2[Ff]/\//g; s/%3[Aa]/:/g; s/%20/ /g; s/%2[Dd]/-/g; s/%5[Ff]/_/g; s/%2[Ee]/./g'
}

query_param() {
  key="$1"
  qs="${QUERY_STRING:-}"
  if [ -z "$qs" ] && [ -n "${REQUEST_URI:-}" ]; then
    case "$REQUEST_URI" in *\?*) qs="${REQUEST_URI#*?}" ;; esac
  fi
  printf '%s' "$qs" | tr '&' '\n' | sed -n "s/^$key=//p" | head -1 | while IFS= read -r v; do url_decode "$v"; done
}

json_escape_str() {
  printf '%s' "$1" | json_escape
}

openwrt_fs_safe_path() {
  p="$1"
  [ -n "$p" ] || p="/tmp"
  case "$p" in
    /opt/var|/opt/var/*|/opt/etc|/opt/etc/*) p="/etc" ;;
  esac
  case "$p" in
    /*) ;;
    *) p="/$p" ;;
  esac
  # Keep this intentionally conservative for the browser file manager.
  case "$p" in
    /|/etc|/etc/*|/tmp|/tmp/*|/www|/www/*|/root|/root/*|/rom|/rom/*|/overlay|/overlay/*|/mnt|/mnt/*) printf '%s' "$p" ;;
    *) printf '/tmp' ;;
  esac
}

rule_provider_file() {
  name="$1"
  case "$name" in
    manual-proxy|manual-proxy@classical|manual|Ручной*) printf '%s/rules/manual-proxy.yaml' "$MIHOMO_RUN_DIR" ;;
    *) printf '%s/rules/%s.yaml' "$MIHOMO_RUN_DIR" "$name" ;;
  esac
}

PROXY_REGISTRY="${UNIFIED_UI_CONF_DIR:-/etc/unified-ui}/proxy-connections.json"
proxy_protocols_json() {
  printf '[{"id":"wireguard","label":"WireGuard"},{"id":"amnezia","label":"Amnezia"},{"id":"hysteria2","label":"Hysteria2"},{"id":"vless","label":"VLESS"},{"id":"trojan","label":"Trojan"},{"id":"mieru","label":"Mieru"},{"id":"naiveproxy","label":"NaiveProxy"}]'
}
selector_names_json() {
  awk '
    /^proxy-groups:/ { in_groups=1; next }
    in_groups && /^[a-zA-Z0-9_-]+:/ { in_groups=0 }
    in_groups && /^[[:space:]]*-[[:space:]]*name:/ {
      sub(/^[[:space:]]*-[[:space:]]*name:[[:space:]]*/, "");
      gsub(/^["'"'"']|["'"'"']$/, "");
      gsub(/\\/, "\\\\"); gsub(/"/, "\\\"");
      print "\"" $0 "\"";
    }
  ' "$MIHOMO_PROFILE" 2>/dev/null | awk 'BEGIN{printf "["} {if(NR>1)printf ","; printf "%s",$0} END{printf "]"}'
}
registry_json() {
  if [ -f "$PROXY_REGISTRY" ]; then cat "$PROXY_REGISTRY"; else printf '{"connections":[]}'; fi
}

require_auth_or_401

case "${PATH_INFO:-}" in
  /auth-check)
    hdr_json
    if is_authenticated; then printf '{"ok":true,"authenticated":true,"user":"%s"}' "$(printf '%s' "$UNIFIED_UI_AUTH_USER" | json_escape)"; else printf '{"ok":true,"authenticated":false}'; fi
    ;;
  /auth-login)
    body="$(read_body)"
    user="$(printf '%s' "$body" | jsonfilter -e '@.username' 2>/dev/null || true)"
    pass="$(printf '%s' "$body" | jsonfilter -e '@.password' 2>/dev/null || true)"
    if [ "$user" = "$UNIFIED_UI_AUTH_USER" ] && [ "$pass" = "$UNIFIED_UI_AUTH_PASSWORD" ]; then
      token="$(new_session_token)"
      hdr_json_cookie '200 OK' "$UNIFIED_UI_SESSION_COOKIE=$token; Path=/; HttpOnly; SameSite=Lax"
      printf '{"ok":true,"authenticated":true,"user":"%s"}' "$(printf '%s' "$UNIFIED_UI_AUTH_USER" | json_escape)"
    else
      hdr_json_cookie '403 Forbidden'
      printf '{"ok":false,"authenticated":false,"error":"bad_credentials"}'
    fi
    ;;
  /auth-logout)
    rm -f "$UNIFIED_UI_SESSION_FILE" 2>/dev/null || true
    hdr_json_cookie '200 OK' "$UNIFIED_UI_SESSION_COOKIE=deleted; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
    printf '{"ok":true,"authenticated":false}'
    ;;
  /version)
    hdr_json
    mihomo_get /version || printf '{"ok":false,"error":"mihomo request failed"}'
    ;;
  /ui-status)
    hdr_json
    printf '{"ok":true,"managed":"openwrt","running":true,"service":"uhttpd","label":"Unified UI static + CGI","version":"%s"}' "$(build_version | json_escape)"
    ;;
  /update-info)
    hdr_json
    ver="$(build_version | json_escape)"; dt="$(build_date | json_escape)"; repo="$(update_repo | json_escape)"; ch="$(update_channel | json_escape)"; br="$(update_branch | json_escape)"; upd="$(ui_update_url | json_escape)"
    printf '{"ok":true,"build":{"version":"%s","built_utc":"%s","channel":"%s","repo":"%s","update_url":"%s"},"settings":{"repo":"%s","channel":"%s","branch":"%s"},"capabilities":{"curl":true,"tar":true,"tar_exclude":true,"sha256sum":true},"security":{"warnings":[],"will_block_run":false}}' "$ver" "$dt" "$ch" "$repo" "$upd" "$repo" "$ch" "$br"
    ;;
  /update-check)
    hdr_json
    latest_payload="$(github_latest_json)"
    case "$latest_payload" in
      *'"ok":true'*)
        ver="$(build_version)"; tag="$(printf '%s' "$latest_payload" | sed -n 's/.*"tag":"\([^"]*\)".*/\1/p')"
        avail=false; [ -n "$tag" ] && [ "$tag" != "$ver" ] && [ "$tag" != "v$ver" ] && avail=true
        latest_inner="$(printf '%s' "$latest_payload" | sed -n 's/^.*"latest":\(.*\)}$/\1/p')"
        [ -n "$latest_inner" ] || latest_inner='null'
        repo="$(update_repo | json_escape)"; ch="$(update_channel | json_escape)"; br="$(update_branch | json_escape)"
        printf '{"ok":true,"repo":"%s","channel":"%s","branch":"%s","current":{"version":"%s"},"latest":%s,"update_available":%s,"stale":false,"security":{"warnings":[],"will_block_run":false}}' "$repo" "$ch" "$br" "$(printf '%s' "$ver" | json_escape)" "$latest_inner" "$avail"
        ;;
      *) printf '%s' "$latest_payload" ;;
    esac
    ;;
  /update-status)
    hdr_json
    printf '{"ok":true,"status":{"state":"idle","step":"","error":"","op":""},"lock":{"locked":false},"log_tail":[]}'
    ;;
  /env)
    hdr_json
    printf '{"ok":true,"items":[{"key":"UNIFIED_UI_AUTH_USER","current":"%s","configured":"%s","effective":"%s"},{"key":"UNIFIED_UI_UPDATE_REPO","current":"%s","configured":"%s","effective":"%s"},{"key":"UNIFIED_UI_UPDATE_CHANNEL","current":"%s","configured":"%s","effective":"%s"}]}' "$(printf '%s' "$UNIFIED_UI_AUTH_USER" | json_escape)" "$(printf '%s' "$UNIFIED_UI_AUTH_USER" | json_escape)" "$(printf '%s' "$UNIFIED_UI_AUTH_USER" | json_escape)" "$(update_repo | json_escape)" "$(update_repo | json_escape)" "$(update_repo | json_escape)" "$(update_channel | json_escape)" "$(update_channel | json_escape)" "$(update_channel | json_escape)"
    ;;
  /env-save)
    hdr_json
    printf '{"ok":true,"saved":false,"message":"OpenWrt env editing is read-only in this build"}'
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
  /fs-list|/fs-list-path/*)
    hdr_json
    target="$(query_param target)"
    if [ -z "$target" ]; then target=local; fi
    case "${PATH_INFO:-}" in
      /fs-list-path/*) path_req="${PATH_INFO#/fs-list-path/}"; path_req="$(url_decode "$path_req")" ;;
      *) path_req="$(query_param path)" ;;
    esac
    if [ "$target" != "local" ]; then
      printf '{"ok":false,"error":"remote file manager disabled on OpenWrt","code":"remote_disabled"}'
      exit 0
    fi
    path_safe="$(openwrt_fs_safe_path "$path_req")"
    if [ ! -e "$path_safe" ]; then path_safe="/tmp"; fi
    if [ ! -d "$path_safe" ]; then
      printf '{"ok":false,"error":"not_a_directory","path":"%s"}' "$(json_escape_str "$path_safe")"
      exit 0
    fi
    real="$(cd "$path_safe" 2>/dev/null && pwd -P || printf '%s' "$path_safe")"
    items_file="/tmp/unified-ui-fs-items-$$.jsonl"
    : > "$items_file"
    for f in "$path_safe"/* "$path_safe"/.[!.]* "$path_safe"/..?*; do
      [ -e "$f" ] || [ -L "$f" ] || continue
      name="${f##*/}"
      [ "$name" = "." ] && continue
      [ "$name" = ".." ] && continue
      type=file
      link_dir=false
      if [ -L "$f" ]; then
        type=link
        [ -d "$f" ] && link_dir=true
      elif [ -d "$f" ]; then
        type=dir
      fi
      size=0
      if [ -f "$f" ] && [ ! -L "$f" ]; then size="$(wc -c < "$f" 2>/dev/null | tr -d ' ')"; fi
      [ -n "$size" ] || size=0
      ename="$(json_escape_str "$name")"
      printf '{"name":"%s","type":"%s","size":%s,"mtime":0,"perm":"","link_dir":%s}\n' "$ename" "$type" "$size" "$link_dir" >> "$items_file"
    done
    items="$(awk 'BEGIN{printf "["} {if(NR>1)printf ","; printf "%s",$0} END{printf "]"}' "$items_file")"
    rm -f "$items_file"
    esc_path="$(json_escape_str "$path_safe")"
    esc_real="$(json_escape_str "$real")"
    printf '{"ok":true,"target":"local","path":"%s","realpath":"%s","roots":["/","/etc","/tmp","/www","/root","/rom","/overlay","/mnt"],"items":%s}' "$esc_path" "$esc_real" "$items"
    ;;
  /proxy-connections)
    hdr_json
    mkdir -p "$UNIFIED_UI_CONF_DIR"
    reg="$(registry_json)"
    conns="$(printf '%s' "$reg" | jsonfilter -e '@.connections' 2>/dev/null || true)"
    [ -n "$conns" ] || conns='[]'
    printf '{"ok":true,"connections":%s,"count":0,"selectors":%s,"protocols":%s,"registry":"%s"}' "$conns" "$(selector_names_json)" "$(proxy_protocols_json)" "$PROXY_REGISTRY"
    ;;
  /proxy-connections-import)
    body="$(read_body)"
    proto="$(printf '%s' "$body" | jsonfilter -e '@.protocol' 2>/dev/null || true)"
    name="$(printf '%s' "$body" | jsonfilter -e '@.name' 2>/dev/null || true)"
    content="$(printf '%s' "$body" | jsonfilter -e '@.content' 2>/dev/null || true)"
    [ -n "$proto" ] || proto=unknown
    [ -n "$name" ] || name="$proto-$(date +%s)"
    id="$(printf '%s-%s' "$proto" "$name" | tr -cs 'A-Za-z0-9_.-' '-' | sed 's/^-//;s/-$//')"
    esc_id="$(printf '%s' "$id" | json_escape)"
    esc_name="$(printf '%s' "$name" | json_escape)"
    esc_proto="$(printf '%s' "$proto" | json_escape)"
    esc_content="$(printf '%s' "$content" | json_escape)"
    mkdir -p "$UNIFIED_UI_CONF_DIR"
    tmp="$PROXY_REGISTRY.tmp.$$"
    printf '{"connections":[{"id":"%s","name":"%s","protocol":"%s","protocolLabel":"%s","enabled":true,"mihomoSupported":false,"selectors":[],"usedBySelectors":[],"proxyYaml":"# OpenWrt registry staging only\\n# Apply full YAML via Mihomo editor for now.","rawContent":"%s"}]}' "$esc_id" "$esc_name" "$esc_proto" "$esc_proto" "$esc_content" > "$tmp"
    mv "$tmp" "$PROXY_REGISTRY"
    chmod 600 "$PROXY_REGISTRY"
    hdr_json '201 Created'
    printf '{"ok":true,"connection":{"id":"%s","name":"%s","protocol":"%s","protocolLabel":"%s","enabled":true,"mihomoSupported":false,"selectors":[],"usedBySelectors":[],"proxyYaml":"# OpenWrt registry staging only"},"replaced":false}' "$esc_id" "$esc_name" "$esc_proto" "$esc_proto"
    ;;
  /proxy-connections-apply)
    hdr_json
    printf '{"ok":true,"changed":false,"count":0,"message":"OpenWrt: registry сохранён. Для генерации native YAML используй Mihomo editor; backend генератор протоколов ещё lightweight."}'
    ;;
  /proxy-connections-preview)
    hdr_json
    printf '{"ok":true,"block":"# OpenWrt proxy-connections registry\\n# Native YAML generation for protocol tabs is not enabled in CGI mode yet.\\n# Use Mihomo editor or Proxy Tools for direct YAML insertion."}'
    ;;
  /proxy-connections-item/*)
    id="${PATH_INFO#/proxy-connections-item/}"
    hdr_json
    if [ "${REQUEST_METHOD:-GET}" = "DELETE" ]; then
      rm -f "$PROXY_REGISTRY"
      printf '{"ok":true,"id":"%s","removedName":"%s","apply":{"ok":true,"changed":false,"count":0}}' "$id" "$id"
    else
      printf '{"ok":true,"id":"%s"}' "$id"
    fi
    ;;

  /api-raw)
    hdr_json
    raw_path="$(printf '%s' "${QUERY_STRING:-}" | sed -n 's/^path=//p' | sed 's/%2F/\//g; s/%2f/\//g')"
    printf '{"ok":false,"error":"OpenWrt compat endpoint not mapped","path":"%s"}' "$raw_path"
    ;;
  /rule-provider/*)
    provider="${PATH_INFO#/rule-provider/}"
    provider="$(printf '%s' "$provider" | sed 's/%40/@/g; s/%20/ /g')"
    file="$(rule_provider_file "$provider")"
    if [ "${REQUEST_METHOD:-GET}" = "POST" ]; then
      body="$(read_body)"
      content="$(printf '%s' "$body" | jsonfilter -e '@.content' 2>/dev/null || true)"
      mkdir -p "$(dirname "$file")" "$UNIFIED_UI_BACKUP_DIR"
      if [ -f "$file" ]; then cp "$file" "$UNIFIED_UI_BACKUP_DIR/rule-provider-$(basename "$file")-$(date +%Y%m%d-%H%M%S).bak"; fi
      printf '%s\n' "$content" > "$file"
      esc_content="$(printf '%s' "$content" | json_escape)"
      hdr_json
      printf '{"ok":true,"provider":"%s","path":"%s","editable":true,"content":"%s"}' "$provider" "$file" "$esc_content"
    else
      hdr_json
      if [ -f "$file" ]; then content="$(cat "$file")"; else content='payload:'; fi
      esc_content="$(printf '%s' "$content" | json_escape)"
      printf '{"ok":true,"provider":"%s","path":"%s","editable":true,"content":"%s","meta":{"type":"file"}}' "$provider" "$file" "$esc_content"
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


BUNDLED_UI_DIR="$SCRIPT_DIR/www/unified-ui"
install_openwrt_auth_pages() {
  if [ -f "$UI_ROOT/index.html" ] && [ ! -f "$UI_ROOT/app.html" ]; then
    mv "$UI_ROOT/index.html" "$UI_ROOT/app.html"
  fi
  if [ -f "$UI_ROOT/app.html" ] && ! grep -q 'openwrt-auth-guard' "$UI_ROOT/app.html"; then
    tmp="$UI_ROOT/app.html.tmp.$$"
    awk '
      BEGIN{done=0}
      /<head[^>]*>/ && !done { print; print "<script id=\"openwrt-auth-guard\">(async()=>{try{const r=await fetch(\x27/cgi-bin/unified-ui-api/auth-check\x27,{cache:\x27no-store\x27});const d=await r.json().catch(()=>({}));if(!d.authenticated) location.replace(\x27/unified-ui/\x27);}catch(e){location.replace(\x27/unified-ui/\x27);}})();</script>"; done=1; next }
      {print}
    ' "$UI_ROOT/app.html" > "$tmp" && mv "$tmp" "$UI_ROOT/app.html"
  fi
  cat > "$UI_ROOT/index.html" <<'HTML'
<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Unified UI — вход</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 30% 15%,rgba(37,99,235,.28),transparent 34%),linear-gradient(135deg,#020617,#071126 55%,#020617);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#e5eefc}.card{width:min(420px,calc(100vw - 32px));padding:28px;border-radius:28px;border:1px solid rgba(96,165,250,.22);background:linear-gradient(180deg,rgba(8,18,43,.94),rgba(2,8,23,.92));box-shadow:0 28px 80px rgba(0,0,0,.48),inset 0 1px 0 rgba(255,255,255,.06)}h1{margin:0 0 8px;font-size:30px;letter-spacing:-.04em}.dot{display:inline-block;width:10px;height:10px;border-radius:999px;background:#22c55e;box-shadow:0 0 18px #22c55e;margin-left:8px}.sub{margin:0 0 22px;color:#93a4bf}.field{margin:13px 0}label{display:block;margin:0 0 7px;color:#b8c7df;font-size:13px}input{width:100%;height:44px;border-radius:14px;border:1px solid rgba(148,163,184,.24);background:#020817;color:#eef6ff;padding:0 13px;font-size:15px}button{width:100%;height:46px;margin-top:16px;border:0;border-radius:999px;background:linear-gradient(135deg,#2563eb,#06b6d4);color:white;font-weight:800;cursor:pointer;box-shadow:0 16px 35px rgba(37,99,235,.28)}.err{display:none;margin-top:14px;padding:11px 13px;border-radius:14px;border:1px solid rgba(248,113,113,.35);background:rgba(127,29,29,.32);color:#fecaca}.hint{margin-top:16px;color:#64748b;font-size:12px}</style></head><body><form class="card" id="f"><h1>Unified UI<span class="dot"></span></h1><p class="sub">Вход в панель OpenWrt</p><div class="field"><label>Логин</label><input name="username" autocomplete="username" value="admin"></div><div class="field"><label>Пароль</label><input name="password" type="password" autocomplete="current-password" autofocus></div><button>Войти</button><div class="err" id="err">Неверный логин или пароль</div><div class="hint">Тестовый дефолт, если env не переопределён: admin/admin.</div></form><script>
(async()=>{try{const r=await fetch('/cgi-bin/unified-ui-api/auth-check',{cache:'no-store'});const d=await r.json();if(d.authenticated) location.replace('/unified-ui/app.html');}catch(e){}})();
document.getElementById('f').addEventListener('submit',async e=>{e.preventDefault();const fd=new FormData(e.currentTarget);const r=await fetch('/cgi-bin/unified-ui-api/auth-login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:fd.get('username'),password:fd.get('password')})});const d=await r.json().catch(()=>({}));if(r.ok&&d.authenticated) location.replace('/unified-ui/app.html'); else document.getElementById('err').style.display='block';});
</script></body></html>
HTML
}

install_logout_fallback() {
  rm -rf /www/logout
  mkdir -p /www/logout
  cat > /www/logout/index.html <<'HTML'
<!doctype html><meta charset="utf-8"><title>Unified UI — выход</title><script>(async()=>{try{await fetch('/cgi-bin/unified-ui-api/auth-logout',{method:'POST',cache:'no-store'});}catch(e){} location.replace('/unified-ui/');})();</script><a href="/unified-ui/">Unified UI</a>
HTML
  chmod 755 /www/logout
  chmod 644 /www/logout/index.html
}
if [ -f "$BUNDLED_UI_DIR/index.html" ]; then
  rm -rf "$UI_ROOT"
  mkdir -p "$UI_ROOT"
  cp -a "$BUNDLED_UI_DIR/." "$UI_ROOT/"
  install_openwrt_auth_pages
  chmod -R a+rX "$UI_ROOT"
  install_logout_fallback
  printf 'Installed Unified UI OpenWrt full panel:\n  %s\n  %s\n  update: %s\n' "$UI_ROOT/index.html" "$CGI_PATH" "$UPDATE_URL"
  exit 0
fi

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
    table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}th{color:#bcd0ea}.pill{display:inline-flex;border-radius:999px;padding:3px 8px;background:#162944;color:#bdd2ef;font-size:12px}.online{background:rgba(61,220,151,.18);color:#8dffc8}.offline{background:rgba(255,93,108,.18);color:#ff9ba5}pre,textarea{white-space:pre-wrap;word-break:break-word;background:#08111e;border:1px solid var(--line);border-radius:12px;padding:10px;max-height:420px;overflow:auto}.hidden{display:none}select,input,textarea{background:#091728;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:7px;max-width:100%}.btn.small{padding:5px 8px;font-size:12px}.protocol-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.protocol-tab{border:1px solid var(--line);background:#091728;color:var(--text);border-radius:999px;padding:7px 10px;cursor:pointer}.protocol-tab.active{background:#1d9bf0;color:#001524;font-weight:800}.import-box{width:100%;min-height:120px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.toast{position:fixed;right:16px;bottom:16px;background:#10233d;border:1px solid var(--line);border-radius:12px;padding:10px 12px;box-shadow:0 20px 50px rgba(0,0,0,.35);z-index:20}.cfg{width:100%;min-height:520px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;line-height:1.45;resize:vertical}
  </style>
</head>
<body>
<header><h1><span class="dot"></span>Unified UI <span class="muted">OpenWrt / Standalone Mihomo</span></h1><div class="tabs"><button class="tab active" data-view="status">Статус</button><button class="tab" data-view="selectors">Маршрутизация</button><button class="tab" data-view="protocols">Подключения</button><button class="tab" data-view="connections">Соединения</button><button class="tab" data-view="config">Конфиг</button><button class="tab" data-view="raw">Raw API</button></div></header>
<main>
  <section id="view-status" class="view grid"><div class="card"><h2>Состояние Mihomo</h2><div id="status" class="kv muted">Загрузка…</div><div class="toolbar"><button class="btn primary" onclick="loadAll()">Обновить</button><button class="btn warn" onclick="restartMihomo()">Restart Mihomo</button></div></div><div class="card"><h2>OpenWrt адаптер</h2><p class="muted">Максимально близкая к Keenetic схема: standalone Mihomo + Unified UI OpenWrt backend.</p><pre id="restartLog">Пока без рестартов.</pre></div></section>
  <section id="view-selectors" class="view hidden"><div class="card"><h2>Селекторы / группы</h2><div class="toolbar"><button class="btn primary" onclick="loadProxies()">Обновить</button><button class="btn" onclick="pingVisible()">Обновить все пинги</button></div><div class="muted" id="proxySummary"></div><div id="groups"></div></div></section>
  <section id="view-protocols" class="view hidden"><div class="card"><h2>Подключения по протоколам</h2><p class="muted">Список берётся из standalone Mihomo `/etc/mihomo/config.yaml`. Импорт добавляет proxy-блок в YAML-редактор, затем жми “Сохранить и применить”.</p><div class="protocol-tabs" id="protocolTabs"></div><div class="grid"><div class="card"><h2 id="protocolTitle">VLESS</h2><div id="protocolList" class="muted">Загрузка…</div></div><div class="card"><h2>Добавить подключение</h2><select id="protocolImportType"><option>VLESS</option><option>WireGuard</option><option>Amnezia</option><option>Hysteria2</option><option>Trojan</option><option>Mieru</option><option>NaiveProxy</option></select><textarea id="protocolImportText" class="import-box" placeholder="Вставь vless://, trojan://, hysteria2:// или WireGuard/Amnezia config"></textarea><div class="toolbar"><button class="btn primary" onclick="importProtocolConnection()">Добавить в конфиг</button><button class="btn" onclick="loadConfigEditor()">Перечитать YAML</button><button class="btn warn" onclick="saveConfig(true)">Сохранить и применить</button></div><pre id="protocolImportLog">Импорт пока не запускался.</pre></div></div></div></section>
  <section id="view-connections" class="view hidden"><div class="card"><h2>Активные соединения</h2><div class="toolbar"><button class="btn primary" onclick="loadConnections()">Обновить соединения</button><button class="btn warn" onclick="closeAllConnections()">Разорвать все</button><input id="connFilter" placeholder="Фильтр host/IP/process" oninput="renderConnections()"></div><div id="connections"></div></div></section>
  <section id="view-config" class="view hidden"><div class="card"><h2>Редактор /etc/mihomo/config.yaml</h2><div class="muted" id="configMeta">Загрузка…</div><div class="toolbar"><button class="btn primary" onclick="loadConfigEditor()">Перечитать</button><button class="btn" onclick="validateConfig()">Проверить</button><button class="btn" onclick="saveConfig(false)">Сохранить</button><button class="btn warn" onclick="saveConfig(true)">Сохранить и применить</button></div><textarea id="configEditor" class="cfg" spellcheck="false"></textarea><pre id="configLog">Пока тихо.</pre></div></section>
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
async function loadProxies(){const data=await get('/proxies'); proxyCache=data.proxies||{}; const proxies=proxyCache; const groups=Object.values(proxies).filter(p=>Array.isArray(p.all)); const nodes=Object.values(proxies).filter(p=>!Array.isArray(p.all)); visibleNodeNames=[...new Set(groups.flatMap(g=>g.all||[]).filter(n=>proxies[n] && !Array.isArray(proxies[n].all)))]; $('#proxySummary').textContent=`Групп: ${groups.length} · узлов/служебных proxy: ${nodes.length}`; $('#groups').innerHTML=groups.map((g,idx)=>`<h3>${esc(g.name)} <span class="pill">${esc(g.type)}</span> <span class="muted">сейчас: ${esc(g.now||'')}</span></h3><div class="toolbar"><select id="sel-${idx}">${optionList(g)}</select><button class="btn primary small" onclick="selectProxy(${JSON.stringify(g.name)}, document.getElementById('sel-${idx}').value)">Применить выбор</button></div><table><thead><tr><th>Proxy</th><th>Тип</th><th>Статус</th><th>Ping</th><th>Действия</th></tr></thead><tbody>${(g.all||[]).map(n=>{const p=proxies[n]||{}; const alive=p.alive===false?'offline':'online'; return `<tr><td>${esc(n)}</td><td>${esc(p.type||'')}</td><td><span class="pill ${alive}">${alive}</span></td><td><button class="btn small" onclick="pingProxy(${JSON.stringify(n)})">${esc(latency(p))}</button></td><td><button class="btn primary small" onclick="selectProxy(${JSON.stringify(g.name)}, ${JSON.stringify(n)})">Выбрать</button></td></tr>`}).join('')}</tbody></table>`).join(''); renderProtocols();}
async function loadConnections(){try{const d=await get('/connections'); connectionCache=d.connections||[]; renderConnections();}catch(e){$('#connections').textContent=e.message;}}
function renderConnections(){const q=($('#connFilter')?.value||'').toLowerCase(); const arr=connectionCache.filter(c=>JSON.stringify(c).toLowerCase().includes(q)); $('#connections').innerHTML=`<p class="muted">Соединений: ${arr.length} / ${connectionCache.length}</p><table><thead><tr><th>Host</th><th>Source</th><th>Process</th><th>Rule</th><th>Chains</th><th>Upload/Download</th><th></th></tr></thead><tbody>${arr.slice(0,300).map(c=>`<tr><td>${esc(c.metadata?.host||c.metadata?.destinationIP||'')}</td><td>${esc(c.metadata?.sourceIP||'')}:${esc(c.metadata?.sourcePort||'')}</td><td>${esc(c.metadata?.process||'')}</td><td>${esc(c.rule||'')}</td><td>${esc((c.chains||[]).join(' → '))}</td><td>${esc(c.upload||0)} / ${esc(c.download||0)}</td><td><button class="btn warn small" onclick="closeConnection(${JSON.stringify(c.id)})">Разорвать</button></td></tr>`).join('')}</tbody></table>`;}
async function closeConnection(id){try{await post('/connection-close',{id});toast('Соединение разорвано');await loadConnections();}catch(e){toast('Ошибка разрыва: '+e.message)}}
async function closeAllConnections(){try{await post('/connections-close-all',{});toast('Все соединения разорваны');await loadConnections();}catch(e){toast('Ошибка: '+e.message)}}
async function loadConfigEditor(){try{const d=await get('/config-get'); $('#configEditor').value=d.content||''; $('#configMeta').textContent=`${d.path} · UI ${d.ui_version||''}`; $('#configLog').textContent='Конфиг перечитан.';}catch(e){$('#configMeta').textContent=e.message; $('#configLog').textContent=e.message;}}
async function validateConfig(){try{const d=await post('/config-validate',{content:$('#configEditor').value}); $('#configLog').textContent=(d.ok?'VALID OK\n':'VALID FAIL\n')+(d.output||''); toast(d.ok?'Конфиг валиден':'В конфиге ошибка');}catch(e){$('#configLog').textContent=e.message; toast('Validation error: '+e.message)}}
async function saveConfig(apply){try{const d=await post('/config-save',{content:$('#configEditor').value,apply:!!apply}); $('#configLog').textContent=JSON.stringify(d,null,2); toast(apply?'Сохранено и применено':'Сохранено'); if(apply) await loadStatus();}catch(e){$('#configLog').textContent=e.message; toast('Save error: '+e.message)}}

const PROTOCOLS=[['VLESS',['vless']],['WireGuard',['wireguard']],['Amnezia',['wireguard','amnezia']],['Hysteria2',['hysteria2','hysteria']],['Trojan',['trojan']],['Mieru',['mieru']],['NaiveProxy',['naiveproxy','naive']]];
let activeProtocol='VLESS';
function initProtocolTabs(){const box=$('#protocolTabs'); if(!box) return; box.innerHTML=PROTOCOLS.map(([n])=>`<button class="protocol-tab ${n===activeProtocol?'active':''}" onclick="setProtocol('${n}')">${esc(n)}</button>`).join('')}
function setProtocol(n){activeProtocol=n; initProtocolTabs(); renderProtocols();}
function protocolMatches(proxy, name){const type=String(proxy?.type||'').toLowerCase(); const [label,types]=PROTOCOLS.find(([n])=>n===name)||[name,[]]; if(label==='Amnezia') return /amnezia|awg/i.test(proxy?.name||'') || /amnezia|awg/i.test(proxy?.server||''); return types.includes(type);}
function renderProtocols(){initProtocolTabs(); const title=$('#protocolTitle'); const list=$('#protocolList'); if(!title||!list) return; title.textContent=activeProtocol; const proxies=Object.values(proxyCache||{}).filter(p=>!Array.isArray(p.all)&&protocolMatches(p,activeProtocol)); list.innerHTML=`<p class="muted">Найдено: ${proxies.length}</p><table><thead><tr><th>Имя</th><th>Тип</th><th>Сервер</th><th>Ping</th><th>Статус</th></tr></thead><tbody>${proxies.map(p=>`<tr><td>${esc(p.name)}</td><td>${esc(p.type)}</td><td>${esc(p.server||p.xudp||'')}</td><td><button class="btn small" onclick="pingProxy(${JSON.stringify(p.name)})">${esc(latency(p))}</button></td><td><span class="pill ${p.alive===false?'offline':'online'}">${p.alive===false?'offline':'online'}</span></td></tr>`).join('')}</tbody></table>`;}
function yamlQuote(v){return String(v??'').replace(/'/g,"''");}
function appendProxyYaml(block){const ed=$('#configEditor'); if(!ed.value.trim()) { toast('Сначала перечитай YAML'); return; } let y=ed.value; if(!/^proxies:\s*$/m.test(y)){ y += '\nproxies:\n'; } const pos=y.search(/^proxy-groups:\s*$/m); if(pos>=0){ y=y.slice(0,pos).replace(/\s*$/,'\n')+block+'\n'+y.slice(pos); } else { y=y.replace(/\s*$/,'\n')+block+'\n'; } ed.value=y; $('#protocolImportLog').textContent='Добавлено в YAML. Проверь и нажми “Сохранить и применить”.';}
function parseUriProxy(text,typeHint){const raw=text.trim(); let u; try{u=new URL(raw)}catch(e){return null} const scheme=u.protocol.replace(':','').toLowerCase(); const name=decodeURIComponent((raw.split('#')[1]||`${scheme}-${u.hostname}`).trim()); const q=Object.fromEntries([...u.searchParams.entries()]); if(scheme==='vless'){return `  - name: '${yamlQuote(name)}'\n    type: vless\n    server: ${u.hostname}\n    port: ${u.port||443}\n    uuid: ${u.username}\n    network: ${q.type||'tcp'}\n    tls: ${q.security==='reality'||q.security==='tls'?'true':'false'}\n    udp: true\n    servername: ${q.sni||q.servername||u.hostname}\n    client-fingerprint: ${q.fp||'chrome'}\n    reality-opts:\n      public-key: ${q.pbk||''}\n      short-id: ${q.sid||''}\n`;}
 if(scheme==='trojan'){return `  - name: '${yamlQuote(name)}'\n    type: trojan\n    server: ${u.hostname}\n    port: ${u.port||443}\n    password: ${u.username}\n    sni: ${q.sni||q.peer||u.hostname}\n    udp: true\n`;}
 if(scheme==='hysteria2'||scheme==='hy2'){return `  - name: '${yamlQuote(name)}'\n    type: hysteria2\n    server: ${u.hostname}\n    port: ${u.port||443}\n    password: ${u.username||q.auth||''}\n    sni: ${q.sni||u.hostname}\n    skip-cert-verify: ${q.insecure==='1'||q.insecure==='true'?'true':'false'}\n`;}
 return null;}
function parseWireGuard(text,typeHint){const m=k=>(text.match(new RegExp('^\\s*'+k+'\\s*=\\s*(.+)$','mi'))||[])[1]?.trim(); const name=(text.match(/^\s*Name\s*=\s*(.+)$/mi)||[])[1] || `${typeHint||'WireGuard'}-imported`; const ep=m('Endpoint')||''; const [host,port]=(ep||':').split(':'); const addr=(m('Address')||'10.0.0.2/32').split(',')[0].replace(/\/.*$/,''); return `  - name: '${yamlQuote(name)}'\n    type: wireguard\n    server: ${host}\n    port: ${port||51820}\n    ip: ${addr}\n    private-key: ${m('PrivateKey')||''}\n    public-key: ${m('PublicKey')||''}\n    udp: true\n    mtu: ${m('MTU')||1420}\n`;}
function importProtocolConnection(){const type=$('#protocolImportType').value; const text=$('#protocolImportText').value.trim(); if(!text){toast('Вставь ссылку или конфиг');return} let block=parseUriProxy(text,type); if(!block && /PrivateKey\s*=|PublicKey\s*=|Endpoint\s*=/i.test(text)) block=parseWireGuard(text,type); if(!block){$('#protocolImportLog').textContent='Не распознал формат. Поддержано сейчас: vless://, trojan://, hysteria2:///hy2://, WireGuard/Amnezia WG config.'; return;} appendProxyYaml(block);}

async function loadRaw(){for(const [id,path] of [['#rawConfigs','/configs'],['#rawVersion','/version']]){try{$(id).textContent=JSON.stringify(await get(path),null,2)}catch(e){$(id).textContent=e.message}}}
async function restartMihomo(){ $('#restartLog').textContent='Перезапускаю…'; try{const d=await get('/restart'); $('#restartLog').textContent=JSON.stringify(d,null,2); await new Promise(r=>setTimeout(r,1200)); loadAll(); }catch(e){$('#restartLog').textContent=e.message;} }
async function loadAll(){await loadStatus(); await Promise.allSettled([loadProxies(),loadConnections(),loadRaw(),loadConfigEditor()]);}
loadAll(); setInterval(loadStatus,10000);
</script>
</body>
</html>
HTML

printf 'Installed Unified UI OpenWrt:\n  %s\n  %s\n  update: %s\n' "$UI_ROOT/index.html" "$CGI_PATH" "$UPDATE_URL"
