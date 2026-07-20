#!/usr/bin/env bash
set -euo pipefail

log() { printf '[unified-ui-docker] %s\n' "$*" >&2; }

mkdir -p /etc/mihomo/rules /etc/mihomo/profiles /etc/mihomo/templates /data/unified-ui /var/log/unified-ui

: "${UNIFIED_UI_AUTH_USER:=admin}"
: "${UNIFIED_UI_AUTH_PASSWORD:=admin}"
: "${UNIFIED_UI_SECRET_KEY:=}"
: "${MIHOMO_SUB_URL:=${SUB1:-}}"
: "${MIHOMO_MIXED_PORT:=7890}"
: "${MIHOMO_DNS_PORT:=1053}"
: "${MIHOMO_CONTROLLER:=0.0.0.0:9090}"
: "${MIHOMO_LOG_LEVEL:=info}"
: "${MIHOMO_ENABLE_TUN:=false}"

export UNIFIED_UI_STATE_DIR=/data/unified-ui
export UNIFIED_UI_DIR=/data/unified-ui
export MIHOMO_CONFIG=/etc/mihomo/config.yaml
export MIHOMO_CONFIG_FILE=/etc/mihomo/config.yaml
export MIHOMO_CONTROLLER_URL=http://127.0.0.1:9090
export MIHOMO_CONTROLLER_HOST=127.0.0.1
export MIHOMO_CONTROLLER_PORT=9090

python - <<'PY'
import os, json
from pathlib import Path
from werkzeug.security import generate_password_hash
state=Path('/data/unified-ui')
state.mkdir(parents=True, exist_ok=True)
auth=state/'auth.json'
user=os.environ.get('UNIFIED_UI_AUTH_USER','admin')
password=os.environ.get('UNIFIED_UI_AUTH_PASSWORD','admin')
if not auth.exists() and user and password:
    auth.write_text(json.dumps({'username':user,'password_hash':generate_password_hash(password)}, ensure_ascii=False, indent=2)+'\n')
    auth.chmod(0o600)
secret=os.environ.get('UNIFIED_UI_SECRET_KEY') or ''
if secret:
    (state/'secret.key').write_text(secret+'\n')
    (state/'secret.key').chmod(0o600)
PY

if [ ! -s /etc/mihomo/rules/manual-proxy.yaml ]; then
  cat > /etc/mihomo/rules/manual-proxy.yaml <<'YAML'
payload: []
YAML
fi

if [ ! -s /etc/mihomo/config.yaml ]; then
  log "creating default Mihomo config"
  python - <<'PY'
import os
from pathlib import Path
import yaml
sub = (os.environ.get('MIHOMO_SUB_URL') or os.environ.get('SUB1') or '').strip()
use = ['subscription_1'] if sub else None

def group(name):
    g={'name':name,'type':'select'}
    if use: g['use']=use
    g['proxies']=['DIRECT'] if name == 'Маршрутизация' else ['DIRECT','Маршрутизация']
    return g
cfg={
  'mixed-port': int(os.environ.get('MIHOMO_MIXED_PORT','7890')),
  'allow-lan': True,
  'bind-address': '*',
  'mode':'rule',
  'log-level': os.environ.get('MIHOMO_LOG_LEVEL','info'),
  'ipv6': False,
  'external-controller': os.environ.get('MIHOMO_CONTROLLER','0.0.0.0:9090'),
  'secret':'',
  'find-process-mode':'off',
  'profile': {'store-selected': True, 'store-fake-ip': False},
  'unified-delay': True,
  'tcp-concurrent': True,
  'dns': {
    'enable': True,
    'listen': f"0.0.0.0:{os.environ.get('MIHOMO_DNS_PORT','1053')}",
    'ipv6': False,
    'enhanced-mode': 'fake-ip',
    'fake-ip-range': '198.18.0.1/16',
    'default-nameserver': ['1.1.1.1','8.8.8.8'],
    'nameserver': ['https://1.1.1.1/dns-query','https://8.8.8.8/dns-query'],
  },
  'proxy-providers': {},
  'rule-providers': {'manual-proxy': {'type':'file','behavior':'classical','format':'yaml','path':'/etc/mihomo/rules/manual-proxy.yaml'}},
  'proxy-groups': [group(x) for x in ['Маршрутизация','Ручной список','YouTube','Telegram','Meta','GitHub','AI','Блок РФ','Для РФ недоступно','Остальное']],
  'rules': [
    'RULE-SET,manual-proxy,Ручной список',
    'DOMAIN-SUFFIX,ru,DIRECT', 'DOMAIN-SUFFIX,su,DIRECT', 'DOMAIN-SUFFIX,рф,DIRECT',
    'DOMAIN-SUFFIX,youtube.com,YouTube', 'DOMAIN-SUFFIX,googlevideo.com,YouTube', 'DOMAIN-SUFFIX,ytimg.com,YouTube',
    'DOMAIN-SUFFIX,telegram.org,Telegram', 'DOMAIN-SUFFIX,t.me,Telegram',
    'DOMAIN-SUFFIX,facebook.com,Meta', 'DOMAIN-SUFFIX,instagram.com,Meta',
    'DOMAIN-SUFFIX,github.com,GitHub', 'DOMAIN-SUFFIX,openai.com,AI', 'DOMAIN-SUFFIX,chatgpt.com,AI',
    'MATCH,Остальное'
  ]
}
if sub:
  cfg['proxy-providers']['subscription_1']={'type':'http','url':sub,'interval':3600,'path':'/etc/mihomo/profiles/subscription_1.yaml','health-check':{'enable':True,'url':'https://www.gstatic.com/generate_204','interval':300}}
if os.environ.get('MIHOMO_ENABLE_TUN','').lower() in ('1','true','yes','on'):
  cfg['tun']={'enable':True,'stack':'system','auto-route':True,'auto-detect-interface':True,'strict-route':False}
Path('/etc/mihomo/config.yaml').write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')
PY
fi

python - <<'PY'
import os
from pathlib import Path
import yaml
cfg_path = Path('/etc/mihomo/config.yaml')
enable = os.environ.get('MIHOMO_ENABLE_TUN','').lower() in ('1','true','yes','on')
try:
    cfg = yaml.safe_load(cfg_path.read_text(encoding='utf-8')) or {}
except Exception as exc:
    raise SystemExit(f'cannot read /etc/mihomo/config.yaml for TUN normalization: {exc}')
changed = False
if enable:
    desired = {
        'enable': True,
        'stack': 'system',
        'auto-route': True,
        'auto-detect-interface': True,
        'strict-route': False,
        'dns-hijack': ['any:53'],
    }
    if cfg.get('tun') != desired:
        backup = cfg_path.with_suffix(cfg_path.suffix + '.pre-tun.bak')
        if not backup.exists():
            backup.write_text(cfg_path.read_text(encoding='utf-8'), encoding='utf-8')
        cfg['tun'] = desired
        changed = True
else:
    # Do not remove an existing manual tun block. Disabled env only means no auto-injection.
    pass
if changed:
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')
    print('[unified-ui-docker] TUN full-system routing enabled in /etc/mihomo/config.yaml', flush=True)
PY

if [ "$(printf '%s' "$MIHOMO_ENABLE_TUN" | tr '[:upper:]' '[:lower:]')" = "true" ] || [ "$MIHOMO_ENABLE_TUN" = "1" ]; then
  if [ ! -e /dev/net/tun ]; then
    log "WARNING: MIHOMO_ENABLE_TUN=true but /dev/net/tun is missing. Compose needs devices: /dev/net/tun:/dev/net/tun"
  fi
  if ! grep -qw CapEff /proc/self/status 2>/dev/null; then :; fi
fi

log "validating Mihomo config"
mihomo -t -d /etc/mihomo -f /etc/mihomo/config.yaml

log "starting Mihomo"
mihomo -d /etc/mihomo -f /etc/mihomo/config.yaml > /var/log/unified-ui/mihomo.log 2>&1 &
MIHOMO_PID=$!

for i in $(seq 1 45); do
  curl -fsS http://127.0.0.1:9090/version >/dev/null 2>&1 && break
  sleep 1
  kill -0 "$MIHOMO_PID" 2>/dev/null || { log "Mihomo exited early"; tail -200 /var/log/unified-ui/mihomo.log >&2 || true; exit 1; }
  [ "$i" = 45 ] && { log "Mihomo controller not ready"; tail -200 /var/log/unified-ui/mihomo.log >&2 || true; exit 1; }
done

log "starting Unified UI on :${UNIFIED_UI_PORT:-8088}"
cd /app/unified-ui
python run_server.py > /var/log/unified-ui/ui.log 2>&1 &
UI_PID=$!

term() {
  log "stopping"
  kill "$UI_PID" "$MIHOMO_PID" 2>/dev/null || true
  wait || true
}
trap term TERM INT

while true; do
  kill -0 "$MIHOMO_PID" 2>/dev/null || { log "Mihomo died"; tail -120 /var/log/unified-ui/mihomo.log >&2 || true; exit 1; }
  kill -0 "$UI_PID" 2>/dev/null || { log "Unified UI died"; tail -120 /var/log/unified-ui/ui.log >&2 || true; exit 1; }
  sleep 5
done
