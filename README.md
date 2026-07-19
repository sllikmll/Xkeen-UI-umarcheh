# Unified UI

**Unified UI** — единая веб-панель для управления Mihomo/маршрутизацией на роутерах.

Теперь проект поддерживает две целевые платформы:

| Платформа | Где живёт UI | Runtime | Для чего |
|---|---:|---|---|
| **Keenetic / Entware** | `http://<router-ip>:8088/` | Python/Flask + standalone Mihomo | Полная серверная панель с backend’ом, registry, installer’ом и self-update |
| **OpenWrt** | `http://<router-ip>/unified-ui/` | Static full-panel snapshot + CGI API + standalone Mihomo | Максимально близкая к Keenetic версия без тяжёлого Python stack на маленьком overlay |

Не Xkeen UI, не Nikki-wrapper, не отдельный Zashboard. Это одна панель для маршрутизации, селекторов, подключений, подписок и протоколов.

---

## Возможности

| Раздел | Что делает |
|---|---|
| **Маршрутизация** | Runtime-переключение selector-групп Mihomo, режим плиток/списков, ping одного узла и всех узлов |
| **Mihomo** | Редактирование активного `config.yaml`, обновление подписок, YAML-инструменты |
| **Соединения** | Активные Mihomo connections, фильтрация, детали, принудительный разрыв соединений |
| **DAT GeoIP / GeoSite** | Обновление, просмотр состава, работа с локальными списками/rule-provider payload |
| **WireGuard / Amnezia / Hysteria2 / VLESS / Trojan / Mieru / NaiveProxy** | Импорт подключений ссылкой или файлом и добавление в selector’ы |
| **Mihomo Генератор** | Встроенный генератор конфига без iframe и без отдельной страницы |

---

## Runtime selectors

Вкладка **Маршрутизация** работает с Mihomo API напрямую:

- режим **Плитки** — карточки нод/служебных proxy;
- режим **Списки** — компактные строки `selector + dropdown`, чтобы много групп помещалось на одной странице;
- ping рядом с узлом;
- клик по ping обновляет задержку конкретного узла;
- кнопка обновления всех ping’ов;
- поддержка provider-нод из `/providers/proxies`;
- inspector rule-provider показывает конечный payload, включая decoded `.mrs` cache, где это возможно.

---

## Managed proxy-подключения

Вкладки протоколов позволяют добавлять подключения вручную:

- **WireGuard** — `.conf` / `wireguard://`, injection как `type: wireguard`;
- **Amnezia / AWG** — `.conf`, WireGuard-compatible outbound, AWG-метаданные сохраняются в registry;
- **VLESS** — `vless://`, injection как `type: vless`;
- **Trojan** — `trojan://`, injection как `type: trojan`;
- **Hysteria2** — `hy2://` / `hysteria2://`, injection как `type: hysteria2`;
- **NaiveProxy** — `naive+https://`, HTTP/TLS outbound;
- **Mieru** — staging/registry для внешнего runtime, без native Mihomo injection.

При удалении подключения Unified UI должен автоматически:

1. удалить запись из registry;
2. удалить generated proxy из managed-блока;
3. удалить имя proxy из selector-групп;
4. применить config;
5. реально перезапустить Mihomo;
6. проверить, что runtime перечитал конфиг.

Restart считается успешным только если PID Mihomo изменился. Просто “процесс всё ещё жив” — не успех, а дешёвый фокус.

---

# Установка

## Вариант 1 — Keenetic / Entware

### Что нужно заранее

- установлен Entware;
- есть shell-доступ к роутеру;
- свободен порт `8088` или доступен запасной порт;
- желательно уже иметь рабочий Mihomo/XKeen-конфиг, но installer может поставить standalone Mihomo сам.

### Быстрая установка

```sh
cd /opt
curl -fL -o unified-ui-routing.tar.gz \
  "https://github.com/sllikmll/Unified-UI/releases/latest/download/unified-ui-routing.tar.gz"
tar -xzf unified-ui-routing.tar.gz
cd unified-ui
sh install.sh
```

После установки:

```text
http://<IP_роутера>:8088/
```

Если `8088` занят, installer попробует запасные порты.

### Что ставит Keenetic installer

- Python-панель Flask/gevent;
- bundled wheelhouse для Python-зависимостей с fallback во внешний PyPI;
- standalone Mihomo core;
- layout `/opt/etc/mihomo`;
- symlink `config.yaml -> profiles/default.yaml`;
- `/opt/etc/mihomo/restart-mihomo.sh`;
- env-команды validate/restart для панели;
- optional `xk-geodat`;
- optional proxy-client artifacts для внешних runtime;
- init-сервис `/opt/etc/init.d/S99unified-ui001`.

### Опции установки Keenetic

Отключить установку Mihomo:

```sh
UNIFIED_INSTALL_MIHOMO=0 sh install.sh
```

Принудительно переустановить Mihomo:

```sh
UNIFIED_INSTALL_MIHOMO_FORCE=1 sh install.sh
```

Задать repo/tag Mihomo:

```sh
UNIFIED_MIHOMO_REPO=sllikmll/mihomo \
UNIFIED_MIHOMO_TAG=v1.19.29 \
sh install.sh
```

### Обновление Keenetic

Через панель:

```text
Настройки → Проверить обновления → Установить
```

Или вручную:

```sh
/opt/etc/unified-ui/scripts/update_unified_ui.sh
```

Для ручного выбора repo/channel:

```sh
UNIFIED_UI_UPDATE_REPO=sllikmll/Unified-UI \
UNIFIED_UI_UPDATE_CHANNEL=main \
/opt/etc/unified-ui/scripts/update_unified_ui.sh
```

---

## Вариант 2 — OpenWrt / standalone Mihomo

OpenWrt-сборка — это full-panel snapshot той же Unified UI, но без установки Flask/Python на роутер. На маленьком OpenWrt overlay это важно: Python stack съест место быстрее, чем кот сосиску.

### Что нужно заранее

- OpenWrt с `apk` или совместимым shell-окружением;
- `uhttpd` с `/www` и `/cgi-bin`;
- пакет `mihomo-meta` или установленный `/usr/bin/mihomo`;
- активный конфиг Mihomo в `/etc/mihomo/config.yaml`;
- controller Mihomo на `127.0.0.1:9090`;
- mixed proxy обычно на `7890`.

Если раньше стоял Nikki, его надо убрать и перейти на standalone Mihomo.

### Быстрая установка OpenWrt

```sh
cd /tmp
curl -fL -o unified-ui-openwrt.tar.gz \
  "https://github.com/sllikmll/Unified-UI/releases/latest/download/unified-ui-openwrt.tar.gz"
rm -rf unified-ui-openwrt
tar -xzf unified-ui-openwrt.tar.gz -C /tmp
sh /tmp/unified-ui-openwrt/install.sh
```

После установки:

```text
http://<IP_роутера>/unified-ui/
```

### Что ставит OpenWrt installer

- `/www/unified-ui/index.html` — full-panel snapshot Unified UI;
- `/www/unified-ui/static/` — нужные assets панели;
- `/www/unified-ui/openwrt-fetch-compat.js` — compatibility layer для `/api/...`;
- `/www/cgi-bin/unified-ui-api` — CGI API для статуса, config save/validate, restart, provider/manual list;
- `/etc/unified-ui/openwrt.env`;
- `/etc/unified-ui/BUILD.json`;
- `/etc/unified-ui/openwrt-update.sh`;
- backups в `/etc/unified-ui/backups/`.

OpenWrt-версия **не ставит Python/Flask**, не тянет Nikki и не использует LuCI/Nikki UI.

### Удаление Nikki перед переходом на Mihomo

Сначала проверь зависимости:

```sh
apk del --simulate nikki luci-app-nikki luci-i18n-nikki-ru
```

Потом, если всё нормально:

```sh
/etc/init.d/nikki stop || true
/etc/init.d/nikki disable || true
apk del nikki luci-app-nikki luci-i18n-nikki-ru
rm -rf /etc/nikki
rm -f /etc/init.d/nikki
```

`mihomo-meta` оставь.

### Базовые настройки Mihomo для OpenWrt

В `/etc/mihomo/config.yaml` должны быть примерно такие runtime-поля:

```yaml
mixed-port: 7890
allow-lan: true
bind-address: '*'
mode: rule
ipv6: false
external-controller: '0.0.0.0:9090'
secret: 'CHANGE_ME_OR_KEEP_EXISTING'
```

Если используется TUN:

```yaml
tun:
  enable: true
  stack: system
  device: Mihomo
  auto-route: true
  auto-detect-interface: true
```

Перед рестартом всегда валидируй:

```sh
/usr/bin/mihomo -t -d /etc/mihomo -f /etc/mihomo/config.yaml
```

Рестарт:

```sh
/etc/init.d/mihomo restart
```

Проверка:

```sh
pidof mihomo
netstat -lntup | grep -E '7890|9090'
```

### Обновление OpenWrt

Через UI:

```text
Настройки → Проверить обновления → Установить
```

Или вручную:

```sh
sh /etc/unified-ui/openwrt-update.sh
```

---

# Release assets

| Asset | Для чего |
|---|---|
| `unified-ui-routing.tar.gz` | Keenetic / Entware |
| `unified-ui-routing.tar.gz.sha256` | checksum Keenetic-архива |
| `unified-ui-openwrt.tar.gz` | OpenWrt full-panel snapshot |
| `unified-ui-openwrt.tar.gz.sha256` | checksum OpenWrt-архива |

Latest URLs:

```text
https://github.com/sllikmll/Unified-UI/releases/latest/download/unified-ui-routing.tar.gz
https://github.com/sllikmll/Unified-UI/releases/latest/download/unified-ui-routing.tar.gz.sha256
https://github.com/sllikmll/Unified-UI/releases/latest/download/unified-ui-openwrt.tar.gz
https://github.com/sllikmll/Unified-UI/releases/latest/download/unified-ui-openwrt.tar.gz.sha256
```

Текущий проверенный релиз:

```text
https://github.com/sllikmll/Unified-UI/releases/tag/v2.4.33-openwrt-full-panel
```

---

# Важные пути

## Keenetic / Entware

| Путь | Назначение |
|---|---|
| `/opt/etc/unified-ui` | Код панели |
| `/opt/var/lib/unified-ui` | State/registry |
| `/opt/etc/mihomo/config.yaml` | Активный config Mihomo |
| `/opt/etc/mihomo/profiles/default.yaml` | Default profile |
| `/opt/etc/mihomo/rules/manual-proxy.yaml` | Ручной список |
| `/opt/etc/mihomo/restart-mihomo.sh` | Реальный restart Mihomo |
| `/opt/etc/init.d/S99unified-ui001` | Init-сервис панели |

## OpenWrt

| Путь | Назначение |
|---|---|
| `/www/unified-ui` | Static full-panel UI |
| `/www/cgi-bin/unified-ui-api` | CGI API bridge |
| `/etc/unified-ui` | env/build/update/backups |
| `/etc/mihomo/config.yaml` | Активный config Mihomo |
| `/etc/mihomo/rules/manual-proxy.yaml` | Ручной список/provider file |
| `/etc/init.d/mihomo` | Init-сервис Mihomo |

---

# Перенос конфигурации Keenetic → OpenWrt

Если OpenWrt показывает меньше групп, чем Keenetic, проблема обычно не в UI, а в бедном `/etc/mihomo/config.yaml`.

Рабочая схема миграции:

1. сделать backup обоих конфигов;
2. взять с Keenetic богатые секции:
   - `proxy-groups`;
   - `rule-providers`;
   - `rules`;
   - `sniffer` / `geox-url` / routing metadata;
3. сохранить OpenWrt runtime:
   - `mixed-port`;
   - `bind-address`;
   - `secret`;
   - `tun`;
   - `external-controller`;
   - `ipv6: false`;
4. заменить пути `/opt/etc/mihomo` → `/etc/mihomo`;
5. сохранить OpenWrt URL подписки, не подставлять Keenetic URL;
6. сохранить OpenWrt local proxies и добавить их в selector-группы;
7. проверить:

```sh
/usr/bin/mihomo -t -d /etc/mihomo -f /tmp/config.merged-openwrt.yaml
```

После применения:

```sh
/etc/init.d/mihomo restart
```

---

# Разработка

Локальная проверка:

```sh
python3 -m py_compile unified-ui/app_factory.py
python3 -m pytest -q tests/test_unified_service_control_fallback.py tests/test_proxy_connections_cleanup.py tests/test_app_routes_smoke.py
npm run frontend:build
node scripts/verify_frontend_build.mjs
```

Сборка Keenetic release-архива:

```sh
python3 scripts/build_user_archive.py \
  --skip-frontend-build \
  --version 2.4.x-unified \
  --update-url https://github.com/sllikmll/Unified-UI/releases/download/v2.4.x-unified/unified-ui-routing.tar.gz
```

Сборка OpenWrt release-архива:

```sh
python3 scripts/build_openwrt_archive.py \
  --version 2.4.x-openwrt \
  --update-url https://github.com/sllikmll/Unified-UI/releases/download/v2.4.x-openwrt/unified-ui-openwrt.tar.gz \
  --output unified-ui-openwrt.tar.gz \
  --sha256 unified-ui-openwrt.tar.gz.sha256
```

---

# Происхождение

Проект вырос из XKeen/Xkeen UI задач, но сейчас это отдельная **Unified UI** сборка под инфраструктуру `sllikmll`: Keenetic/Entware + OpenWrt/standalone Mihomo в одной системе.
