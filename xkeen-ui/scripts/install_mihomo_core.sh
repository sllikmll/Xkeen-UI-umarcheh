#!/bin/sh
set -e

# Install standalone Mihomo core for unified Xkeen UI + Mihomo setups.
# Defaults are intentionally conservative: user config is backed up/not overwritten,
# and the core is installed from the user's fork so releases can be pinned/customized.

MIHOMO_REPO="${XKEEN_MIHOMO_REPO:-sllikmll/mihomo}"
MIHOMO_FALLBACK_REPO="${XKEEN_MIHOMO_FALLBACK_REPO:-MetaCubeX/mihomo}"
MIHOMO_TAG="${XKEEN_MIHOMO_TAG:-latest}"
MIHOMO_BIN="${XKEEN_MIHOMO_BIN:-/opt/sbin/mihomo}"
MIHOMO_ROOT="${MIHOMO_ROOT:-/opt/etc/mihomo}"
MIHOMO_FORCE="${XKEEN_INSTALL_MIHOMO_FORCE:-0}"
MIHOMO_START="${XKEEN_INSTALL_MIHOMO_START:-1}"
MIHOMO_CONTROLLER="${XKEEN_MIHOMO_CONTROLLER:-0.0.0.0:9090}"
MIHOMO_TEST_URL="${XKEEN_MIHOMO_TEST_URL:-https://www.gstatic.com/generate_204}"
TMP_DIR="${TMPDIR:-/opt/tmp}"
PYTHON_BIN="${PYTHON_BIN:-/opt/bin/python3}"

log() { echo "[*] $*"; }
warn() { echo "[!] $*"; }

have() { command -v "$1" >/dev/null 2>&1; }

ensure_dirs() {
  mkdir -p "$TMP_DIR" /opt/sbin "$MIHOMO_ROOT" "$MIHOMO_ROOT/profiles" "$MIHOMO_ROOT/rules" \
    "$MIHOMO_ROOT/proxy_providers" "$MIHOMO_ROOT/rule_providers" /opt/var/log/mihomo /opt/var/run
}

arch_asset_regex() {
  arch="$(uname -m 2>/dev/null || echo unknown)"
  case "$arch" in
    aarch64|arm64) echo 'mihomo-linux-arm64-.*[.]gz$' ;;
    armv7*|armv7l) echo 'mihomo-linux-armv7-.*[.]gz$' ;;
    armv6*|armv6l) echo 'mihomo-linux-armv6-.*[.]gz$' ;;
    x86_64|amd64) echo 'mihomo-linux-amd64-.*[.]gz$' ;;
    i386|i686) echo 'mihomo-linux-386-.*[.]gz$' ;;
    mips64el|mips64le) echo 'mihomo-linux-mips64le-.*[.]gz$' ;;
    mips64) echo 'mihomo-linux-mips64-.*[.]gz$' ;;
    mipsel|mipsle) echo 'mihomo-linux-mipsle-softfloat-.*[.]gz$' ;;
    mips) echo 'mihomo-linux-mips-softfloat-.*[.]gz$' ;;
    *) echo '' ;;
  esac
}

download_url() {
  url="$1"
  out="$2"
  if have curl; then
    curl -fL --connect-timeout 20 --max-time 240 -o "$out" "$url"
  elif have wget; then
    wget -O "$out" "$url"
  elif [ -x "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" - "$url" "$out" <<'PY'
import shutil, sys, urllib.request
url, out = sys.argv[1:3]
req = urllib.request.Request(url, headers={"User-Agent": "xkeen-ui-mihomo-installer"})
with urllib.request.urlopen(req, timeout=240) as r, open(out, "wb") as f:
    shutil.copyfileobj(r, f)
PY
  else
    return 1
  fi
}

resolve_asset_url() {
  if [ -n "${XKEEN_MIHOMO_ASSET_URL:-}" ]; then
    echo "$XKEEN_MIHOMO_ASSET_URL"
    return 0
  fi

  regex="${XKEEN_MIHOMO_ASSET_REGEX:-$(arch_asset_regex)}"
  if [ -z "$regex" ]; then
    warn "Не знаю asset Mihomo для архитектуры $(uname -m 2>/dev/null || echo unknown)."
    warn "Задай XKEEN_MIHOMO_ASSET_URL вручную."
    return 1
  fi

  if [ "$MIHOMO_TAG" = "latest" ]; then
    api="https://api.github.com/repos/$MIHOMO_REPO/releases/latest"
  else
    api="https://api.github.com/repos/$MIHOMO_REPO/releases/tags/$MIHOMO_TAG"
  fi

  if [ ! -x "$PYTHON_BIN" ]; then
    warn "Python нужен для выбора release asset Mihomo."
    return 1
  fi

  "$PYTHON_BIN" - "$MIHOMO_REPO" "$MIHOMO_FALLBACK_REPO" "$MIHOMO_TAG" "$regex" <<'PY'
import json, re, sys, urllib.error, urllib.request
repo, fallback_repo, tag, regex = sys.argv[1:5]
pat = re.compile(regex)

def api_url(repo_name: str) -> str:
    if tag == "latest":
        return f"https://api.github.com/repos/{repo_name}/releases/latest"
    return f"https://api.github.com/repos/{repo_name}/releases/tags/{tag}"

def pick(repo_name: str) -> str:
    api = api_url(repo_name)
    req = urllib.request.Request(api, headers={"User-Agent": "xkeen-ui-mihomo-installer", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.load(r)
    assets = data.get("assets") or []
    # Prefer plain .gz over distro packages and avoid go120/go123 special builds unless that is the only match.
    matches = [a for a in assets if pat.search(a.get("name", "")) and a.get("browser_download_url")]
    if not matches:
        raise RuntimeError(f"no asset matches {regex!r} in {repo_name}")
    plain = [a for a in matches if "go120" not in a.get("name", "") and "go123" not in a.get("name", "")]
    return (plain or matches)[0]["browser_download_url"]

errors = []
for candidate in [repo, fallback_repo]:
    if not candidate:
        continue
    try:
        print(pick(candidate))
        raise SystemExit(0)
    except Exception as exc:
        errors.append(f"{candidate}: {exc}")
raise SystemExit("; ".join(errors))
PY
}

decompress_gz() {
  src="$1"
  dst="$2"
  if have gzip; then
    gzip -dc "$src" > "$dst"
  elif [ -x "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" - "$src" "$dst" <<'PY'
import gzip, shutil, sys
src, dst = sys.argv[1:3]
with gzip.open(src, 'rb') as i, open(dst, 'wb') as o:
    shutil.copyfileobj(i, o)
PY
  else
    return 1
  fi
}

install_binary() {
  if [ -x "$MIHOMO_BIN" ] && [ "$MIHOMO_FORCE" != "1" ]; then
    log "Mihomo уже установлен: $MIHOMO_BIN"
    "$MIHOMO_BIN" -v 2>/dev/null | head -n 1 || true
    return 0
  fi

  asset_url="$(resolve_asset_url)"
  log "Скачиваю Mihomo: $asset_url"
  tmp_gz="$TMP_DIR/mihomo.$$.gz"
  tmp_bin="$TMP_DIR/mihomo.$$"
  rm -f "$tmp_gz" "$tmp_bin" 2>/dev/null || true
  download_url "$asset_url" "$tmp_gz"
  decompress_gz "$tmp_gz" "$tmp_bin"
  chmod 755 "$tmp_bin"
  if ! "$tmp_bin" -v >/dev/null 2>&1; then
    warn "Скачанный Mihomo не запускается на этой архитектуре."
    rm -f "$tmp_gz" "$tmp_bin" 2>/dev/null || true
    return 1
  fi
  if [ -x "$MIHOMO_BIN" ]; then
    ts="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo no-date)"
    cp -f "$MIHOMO_BIN" "$MIHOMO_BIN.bak-$ts" 2>/dev/null || true
  fi
  mv -f "$tmp_bin" "$MIHOMO_BIN"
  rm -f "$tmp_gz" 2>/dev/null || true
  log "Установлен Mihomo: $MIHOMO_BIN"
  "$MIHOMO_BIN" -v 2>/dev/null | head -n 1 || true
}

write_default_config_if_missing() {
  cfg="$MIHOMO_ROOT/profiles/default.yaml"
  if [ ! -f "$cfg" ]; then
    log "Создаю минимальный Mihomo config: $cfg"
    cat > "$cfg" <<EOF
mixed-port: 7890
redir-port: 5000
tproxy-port: 5001
allow-lan: true
mode: rule
log-level: info
external-controller: $MIHOMO_CONTROLLER
external-ui: zashboard
external-ui-url: https://github.com/Zephyruso/zashboard/releases/latest/download/dist.zip
profile:
  store-selected: true
  store-fake-ip: true
geodata-mode: true
geox-url:
  geoip: https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip.dat
  geosite: https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geosite.dat
  mmdb: https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip.metadb
  asn: https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/GeoLite2-ASN.mmdb
proxy-groups:
  - name: DIRECT
    type: select
    proxies:
      - DIRECT
rules:
  - MATCH,DIRECT
EOF
  fi

  if [ -L "$MIHOMO_ROOT/config.yaml" ] || [ ! -e "$MIHOMO_ROOT/config.yaml" ]; then
    ln -sf "profiles/default.yaml" "$MIHOMO_ROOT/config.yaml"
  elif [ -f "$MIHOMO_ROOT/config.yaml" ] && [ ! -f "$MIHOMO_ROOT/profiles/default.yaml" ]; then
    cp -f "$MIHOMO_ROOT/config.yaml" "$MIHOMO_ROOT/profiles/default.yaml"
    ln -sf "profiles/default.yaml" "$MIHOMO_ROOT/config.yaml" 2>/dev/null || true
  fi
}

write_restart_script() {
  script="$MIHOMO_ROOT/restart-mihomo.sh"
  cat > "$script" <<EOF
#!/bin/sh
export PATH=/opt/bin:/opt/sbin:/sbin:/bin:/usr/sbin:/usr/bin
ROOT="${MIHOMO_ROOT}"
CFG="${MIHOMO_ROOT}/config.yaml"
BIN="${MIHOMO_BIN}"
LOGDIR="/opt/var/log/mihomo"
mkdir -p "\$LOGDIR" /opt/var/run
if pidof mihomo >/dev/null 2>&1; then
  killall mihomo >/dev/null 2>&1 || true
  sleep 2
fi
if pidof mihomo >/dev/null 2>&1; then
  killall -9 mihomo >/dev/null 2>&1 || true
  sleep 1
fi
"\$BIN" -t -d "\$ROOT" -f "\$CFG" || exit 1
nohup "\$BIN" -d "\$ROOT" -f "\$CFG" >> "\$LOGDIR/stdout.log" 2>> "\$LOGDIR/stderr.log" < /dev/null &
echo \$! > /opt/var/run/mihomo.pid
sleep 2
pidof mihomo >/dev/null 2>&1 || exit 1
EOF
  chmod 755 "$script"
}

write_ui_env_defaults() {
  env_file="/opt/etc/xkeen-ui/devtools.env"
  mkdir -p "$(dirname "$env_file")"
  touch "$env_file"
  "$PYTHON_BIN" - "$env_file" "$MIHOMO_ROOT" "$MIHOMO_BIN" <<'PY'
import os, re, sys
path, root, bin_path = sys.argv[1:4]
entries = {
    "MIHOMO_ROOT": root,
    "MIHOMO_VALIDATE_CMD": f"{bin_path} -t -d {{root}} -f {{config}}",
    "XKEEN_RESTART_CMD": f"{root}/restart-mihomo.sh",
    "MIHOMO_RESTART_CMD": f"{root}/restart-mihomo.sh",
    "MIHOMO_RESTART_TIMEOUT": "90",
    "XKEEN_MIHOMO_REPO": os.environ.get("XKEEN_MIHOMO_REPO", "sllikmll/mihomo"),
    "XKEEN_MIHOMO_FALLBACK_REPO": os.environ.get("XKEEN_MIHOMO_FALLBACK_REPO", "MetaCubeX/mihomo"),
}
try:
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
except FileNotFoundError:
    lines = []
out = []
seen = set()
for line in lines:
    key = None
    m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=", line)
    if m:
        key = m.group(1)
    if key in entries:
        if key not in seen:
            val = entries[key].replace("'", "'\\''")
            out.append(f"export {key}='{val}'")
            seen.add(key)
        continue
    out.append(line)
for key, val in entries.items():
    if key not in seen:
        val = val.replace("'", "'\\''")
        out.append(f"export {key}='{val}'")
with open(path + ".tmp", "w", encoding="utf-8") as f:
    f.write("\n".join(out).rstrip() + "\n")
os.replace(path + ".tmp", path)
PY
}

start_and_verify() {
  if ! "$MIHOMO_BIN" -t -d "$MIHOMO_ROOT" -f "$MIHOMO_ROOT/config.yaml"; then
    warn "Mihomo config validation failed; core installed but not started."
    return 1
  fi
  if [ "$MIHOMO_START" != "1" ]; then
    log "XKEEN_INSTALL_MIHOMO_START=$MIHOMO_START — Mihomo не запускаю."
    return 0
  fi
  sh "$MIHOMO_ROOT/restart-mihomo.sh"
  if [ -x "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" - <<'PY' || true
import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:9090/version', timeout=5) as r:
        print('[*] Mihomo API:', r.read().decode('utf-8', 'replace').strip())
except Exception as e:
    print('[!] Mihomo API check failed:', e)
PY
  fi
}

main() {
  ensure_dirs
  install_binary
  write_default_config_if_missing
  write_restart_script
  write_ui_env_defaults
  start_and_verify || true
  log "Mihomo unified install завершён."
}

main "$@"
