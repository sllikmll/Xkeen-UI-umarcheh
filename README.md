# Unified UI

**Unified UI** — единая панель управления Mihomo, маршрутизацией, selector-группами, подключениями и service-rules для роутеров, серверов и desktop-устройств.

Это отдельная Unified UI сборка под инфраструктуру `sllikmll`: одна панель вместо набора разрозненных dashboard’ов и временных обёрток.

## Быстрые ссылки

| Что | Ссылка |
|---|---|
| Репозиторий | https://github.com/sllikmll/Unified-UI |
| **Актуальный Native desktop релиз** | **[`v2.6.7-native`](https://github.com/sllikmll/Unified-UI/releases/tag/v2.6.7-native)** |
| Windows installer | [Unified-UI-Native-Setup-2.6.7-x64.exe](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-Setup-2.6.7-x64.exe) |
| Windows standalone EXE | [Unified-UI-Native-2.6.7-x64.exe](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-x64.exe) |
| Windows portable ZIP | [Unified-UI-Native-2.6.7-windows-x64-portable.zip](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-windows-x64-portable.zip) |
| macOS Apple Silicon | [Unified-UI-Native-2.6.7-mac-arm64.zip](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-mac-arm64.zip) |
| Linux portable | [Unified-UI-Native-2.6.7-linux-x64-portable.tar.gz](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-linux-x64-portable.tar.gz) |
| Linux `.deb` | [Unified-UI-Native-2.6.7-linux-x64.deb](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-linux-x64.deb) |
| Linux `.rpm` | [Unified-UI-Native-2.6.7-linux-x64.rpm](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-linux-x64.rpm) |
| SHA256 / manifest | [SHA256SUMS](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/SHA256SUMS), [native-release-manifest.json](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/native-release-manifest.json) |
| Legacy desktop/docker релиз | https://github.com/sllikmll/Unified-UI/releases/tag/v2.5.2 |
| Docker image | `ghcr.io/sllikmll/unified-ui:latest` |
| Версия Mihomo в desktop/native/docker сборках | `v1.19.29` |

---

## Скачать

### Рекомендуемый desktop-вариант: Native app

Если нужно именно **полноценное приложение, а не web-панель внутри окна**, скачивай native-сборку:

| Платформа | Файл | Статус |
|---|---|---|
| macOS Apple Silicon | [Unified-UI-Native-2.6.7-mac-arm64.zip](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-mac-arm64.zip) | Есть |
| Windows x64 installer / setup wizard | [Unified-UI-Native-Setup-2.6.7-x64.exe](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-Setup-2.6.7-x64.exe) | Есть |
| Windows x64 portable | [Unified-UI-Native-2.6.7-windows-x64-portable.zip](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-windows-x64-portable.zip) | Есть |
| Windows x64 standalone EXE | [Unified-UI-Native-2.6.7-x64.exe](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-x64.exe) | Есть |
| Linux x64 portable | [Unified-UI-Native-2.6.7-linux-x64-portable.tar.gz](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-linux-x64-portable.tar.gz) | Есть |
| Linux Debian/Ubuntu | [Unified-UI-Native-2.6.7-linux-x64.deb](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-linux-x64.deb) | Есть |
| Linux RPM | [Unified-UI-Native-2.6.7-linux-x64.rpm](https://github.com/sllikmll/Unified-UI/releases/download/v2.6.7-native/Unified-UI-Native-2.6.7-linux-x64.rpm) | Есть |

Native app:

- рисует интерфейс настоящими Qt Widgets;
- **не использует QWebEngine/WebView** и не открывает web-панель внутри окна;
- **не запускает Flask UI server**;
- напрямую управляет Mihomo через `external-controller API`;
- умеет импортировать HTTP-подписки/статические прокси, добавлять узлы в selector-группы и показывать per-node ping статусы: серый — не проверялся, зелёный — online, красный — offline.


### Download portal / установочная витрина

Для desktop/native релизов в репозитории есть самодостаточная страница:

```text
docs/native-download-portal.html
```

Локально открыть:

```sh
npm run native:manifest
npm run native:portal:open
# затем http://127.0.0.1:8765/native-download-portal.html
```

Перед полноценным релизом строгая проверка артефактов:

```sh
npm run native:manifest:strict
```

Она проверяет наличие Mac/Windows/Linux пакетов, пересчитывает `SHA256SUMS` и пишет `dist-artifacts/native-release-manifest.json` для портала и release notes.

### Legacy desktop / Docker

Старые desktop-сборки Electron/Qt-webview и Docker доступны в релизах:

```text
https://github.com/sllikmll/Unified-UI/releases/latest
```

---

## Где работает

| Платформа | UI | Runtime | Назначение |
|---|---:|---|---|
| **Keenetic / Entware** | `http://<router-ip>:8088/` | Python/Flask + standalone Mihomo | Полная роутерная панель с backend, registry, installer/self-update |
| **OpenWrt** | `http://<router-ip>/unified-ui/` | Static full-panel + CGI API + standalone Mihomo | Версия без Python stack на маленьком overlay |
| **MikroTik / RouterOS container** | `http://<router-ip>:8088/` | RouterOS container: Unified UI + Mihomo | Full-панель внутри RouterOS container |
| **Docker / Compose** | `http://localhost:8088/` | Container: Flask Unified UI + Mihomo | Серверы, NAS, homelab, desktop Docker |
| **Desktop Native** | Нативное Qt Widgets приложение | PySide6 + Mihomo controller API, без WebView/Flask UI | Локальный proxy/full-system TUN routing, импорт подписок, selector-группы |
| **Legacy Desktop Qt/WebView** | Нативное окно-оболочка | PySide6/QtWebEngine + Flask backend + Mihomo | Старый режим совместимости |

---

## Возможности

| Раздел | Что делает |
|---|---|
| **Маршрутизация** | Runtime-переключение selector-групп Mihomo, режим плиток/списков, ping одного или всех узлов |
| **Mihomo** | Редактирование активного `config.yaml`, обновление подписок, YAML-инструменты |
| **Соединения** | Активные Mihomo connections, фильтры, детали, принудительный разрыв соединений |
| **DAT GeoIP / GeoSite** | Обновление, просмотр и редактирование локальных GeoIP/GeoSite/rule-provider данных |
| **Маршруты DNS** | Keenetic-style DNS/domain/IP/service lists с привязкой к интерфейсам роутера |
| **WireGuard / Amnezia / Hysteria2 / VLESS / Trojan / Mieru / NaiveProxy** | Импорт подключений ссылкой или файлом, добавление в selector-группы |
| **Mihomo Генератор** | Встроенный генератор конфига без iframe и отдельной страницы |
| **Файлы / Команды / Настройки** | File manager, runtime команды, обновления, env/status |

---

# Установка

## 1. Docker / Docker Compose

Готовый образ:

```text
ghcr.io/sllikmll/unified-ui:latest
```

Быстрый запуск proxy-mode:

```sh
docker run -d \
  --name unified-ui \
  --restart unless-stopped \
  -p 8088:8088 \
  -p 9090:9090 \
  -p 7890:7890 \
  -e UNIFIED_UI_AUTH_USER=admin \
  -e UNIFIED_UI_AUTH_PASSWORD=admin \
  -v unified-ui-state:/data/unified-ui \
  -v unified-ui-mihomo:/etc/mihomo \
  ghcr.io/sllikmll/unified-ui:latest
```

После запуска:

```text
UI:          http://localhost:8088/
Mihomo API:  http://localhost:9090/
Mixed proxy: 127.0.0.1:7890
DNS:         127.0.0.1:1053 optional
```

Compose:

```sh
curl -fL -o docker-compose.yml \
  https://raw.githubusercontent.com/sllikmll/Unified-UI/main/docker-compose.yml

docker compose up -d
```

### Docker TUN / полная системная маршрутизация

По умолчанию Docker стартует безопасно: **без TUN**, только UI + mixed proxy.

Для TUN-режима:

```sh
docker compose --profile tun up -d unified-ui-tun
```

TUN profile включает:

```yaml
network_mode: host
cap_add:
  - NET_ADMIN
devices:
  - /dev/net/tun:/dev/net/tun
environment:
  MIHOMO_ENABLE_TUN: "true"
```

Если `/etc/mihomo/config.yaml` уже существует, TUN-блок добавляется idempotent-миграцией с backup:

```text
config.yaml.pre-tun.bak
```

> `UNIFIED_UI_AUTH_PASSWORD` и `MIHOMO_SUB_URL` нужны только на первом запуске. После создания `/data/unified-ui/auth.json` и `/etc/mihomo/config.yaml` их лучше убрать из env/compose.

---

## 2. MikroTik / RouterOS container

MikroTik-версия — это отдельный ARM64 container для RouterOS `container` package. Проверенный сценарий — RB5009/RouterOS container runtime.

Что внутри контейнера:

- Flask Unified UI из `unified-ui/`;
- bundled `mihomo-linux-arm64`;
- Unified UI на `:8088`;
- Mihomo controller на `:9090`;
- mixed proxy на `:1080`;
- DNS listener на `:1053`;
- persistent state в RouterOS `root-dir`, обычно `/usb1/docker/unified-ui-mikrotik`.

### Сборка образа

RouterOS плохо переваривает обычный buildx/OCI archive и может падать с:

```text
download/extract error: no config found in manifest
```

Поэтому нужен classic `docker-archive` через `skopeo`:

```sh
# From repo root
sh -n mikrotik/entrypoint.sh
npm run frontend:build

# Если собираешь не на arm64-хосте
docker run --privileged --rm tonistiigi/binfmt --install arm64

docker build --platform linux/arm64 \
  -f mikrotik/Dockerfile \
  -t unified-ui-mikrotik:routeros .

skopeo copy \
  docker-daemon:unified-ui-mikrotik:routeros \
  docker-archive:unified-ui-mikrotik-docker-archive.tar:unified-ui-mikrotik:routeros

gzip -1 -f unified-ui-mikrotik-docker-archive.tar
```

На выходе нужен файл:

```text
unified-ui-mikrotik-docker-archive.tar.gz
```

Готовый архив из релиза `v2.6.4-native`:

```text
https://github.com/sllikmll/Unified-UI/releases/download/v2.6.4-native/unified-ui-mikrotik-docker-archive-2.6.4.tar.gz
```

Его нужно загрузить на MikroTik в Files, например в корень или на USB-диск.

### Установка на RouterOS

В репозитории есть готовый шаблон:

```text
mikrotik/routeros-install-template.rsc
```

Перед импортом замени placeholders локально:

```routeros
:local SUB_URL "<MIHOMO_SUBSCRIPTION_URL>"
:local AUTH_USER "<UI_USER>"
:local AUTH_PASSWORD "<UI_PASSWORD>"
:local SECRET_KEY "<UI_SECRET_KEY>"
```

Шаблон делает backup RouterOS перед заменой контейнера:

```routeros
/system backup save name=pre-unified-ui-mikrotik
/export file=pre-unified-ui-mikrotik
```

И создаёт runtime layout:

| Объект | Значение |
|---|---|
| container comment | `unified-ui-mikrotik` |
| container root-dir | `/usb1/docker/unified-ui-mikrotik` |
| veth | `MIHOMO` |
| container IP | `192.168.254.3/24` |
| RouterOS gateway IP | `192.168.254.1/24` |
| UI dstnat | `<router-ip>:8088 -> 192.168.254.3:8088` |
| Mihomo API dstnat | `<router-ip>:9090 -> 192.168.254.3:9090` |
| mixed proxy inside container | `1080` |
| DNS inside container | `1053` |

Пример ключевых RouterOS-команд из шаблона:

```routeros
/interface/veth add name=MIHOMO address=192.168.254.3/24 gateway=192.168.254.1 comment="unified-ui-mikrotik"
/ip/address add address=192.168.254.1/24 interface=MIHOMO comment="unified-ui-mikrotik"
/ip/firewall/nat add chain=srcnat action=masquerade src-address=192.168.254.0/24 comment="unified-ui-mikrotik"
/ip/firewall/nat add chain=dstnat action=dst-nat protocol=tcp dst-port=8088 to-addresses=192.168.254.3 to-ports=8088 comment="unified-ui-mikrotik-ui"
/ip/firewall/nat add chain=dstnat action=dst-nat protocol=tcp dst-port=9090 to-addresses=192.168.254.3 to-ports=9090 comment="unified-ui-mikrotik-api"
/container/add file=unified-ui-mikrotik-docker-archive.tar.gz interface=MIHOMO root-dir=/usb1/docker/unified-ui-mikrotik envlist=UNIFIED_UI_MIKROTIK hostname=unified-ui-mikrotik logging=yes start-on-boot=yes dns=1.1.1.1,8.8.8.8,9.9.9.9 comment="unified-ui-mikrotik"
/container/start [find where comment="unified-ui-mikrotik"]
```

После запуска:

```text
Unified UI: http://<mikrotik-ip>:8088/
Mihomo API: http://<mikrotik-ip>:9090/
```

### Важно про секреты

RouterOS пишет env values в logs при старте контейнера. Поэтому `UNIFIED_UI_AUTH_PASSWORD`, `UNIFIED_UI_SECRET_KEY` и `MIHOMO_SUB_URL` нужны только для первого запуска. После успешного первого старта контейнер сохраняет auth/config в persistent `root-dir`, и sensitive env лучше удалить:

```routeros
:foreach e in=[/container/envs find where list="UNIFIED_UI_MIKROTIK" and key="UNIFIED_UI_AUTH_PASSWORD"] do={ /container/envs/remove $e }
:foreach e in=[/container/envs find where list="UNIFIED_UI_MIKROTIK" and key="UNIFIED_UI_SECRET_KEY"] do={ /container/envs/remove $e }
:foreach e in=[/container/envs find where list="UNIFIED_UI_MIKROTIK" and key="MIHOMO_SUB_URL"] do={ /container/envs/remove $e }
```

### Проверка

```routeros
/container/print detail where comment="unified-ui-mikrotik"
/log/print where message~"unified-mikrotik|unified-ui-mikrotik|mihomo"
/ip/firewall/nat/print where comment~"unified-ui-mikrotik"
```

Снаружи:

```sh
curl -I http://<mikrotik-ip>:8088/
curl http://<mikrotik-ip>:9090/version
```

Подробнее: `mikrotik/README.md` и `mikrotik/routeros-install-template.rsc`.

## 3. Desktop Native `2.6.7`

Актуальная native-сборка — это не WebView и не Flask-панель в окне. Приложение напрямую управляет локальным Mihomo через controller API.

Артефакты релиза `v2.6.7-native`:

| ОС | Файл |
|---|---|
| macOS Apple Silicon | `Unified-UI-Native-2.6.7-mac-arm64.zip` |
| Windows x64 installer / setup wizard | `Unified-UI-Native-Setup-2.6.7-x64.exe` |
| Windows x64 portable | `Unified-UI-Native-2.6.7-windows-x64-portable.zip` |
| Windows x64 standalone EXE | `Unified-UI-Native-2.6.7-x64.exe` |
| Linux portable | `Unified-UI-Native-2.6.7-linux-x64-portable.tar.gz` |
| Linux Debian/Ubuntu | `Unified-UI-Native-2.6.7-linux-x64.deb` |
| Linux RPM | `Unified-UI-Native-2.6.7-linux-x64.rpm` |

Что важно в `2.6.7`:

- для Windows рекомендуемый вариант — `Unified-UI-Native-Setup-2.6.7-x64.exe`: NSIS-мастер установки, установка в `Program Files`, ярлыки Start Menu/Desktop и uninstall через “Приложения и компоненты”;
- компактные selector-плитки ближе к web-панели;
- proxy nodes из подписки доступны в selector-группах, а не теряются после импорта;
- per-node ping: отдельное обновление на узле, зелёный online, красный offline, серый not checked;
- runtime-sanitization для импортированных router/OpenWrt/Keenetic Mihomo configs;
- Windows/Linux/macOS артефакты плюс SHA256SUMS.

---

## 4. Legacy Desktop Electron

Артефакты старого релиза `v2.5.1`:

| ОС | Файл |
|---|---|
| macOS Apple Silicon | `Unified-UI-2.5.1-arm64.dmg` |
| Windows x64 | `Unified-UI-Setup-2.5.2-x64.exe` |
| Linux Debian/Ubuntu | `Unified-UI-2.5.1-amd64.deb` |
| Linux RPM distros | `Unified-UI-2.5.1-x86_64.rpm` |
| Linux portable | `Unified-UI-2.5.1-x86_64.AppImage` |

Локальные порты Electron-сборки:

```text
Unified UI:  http://127.0.0.1:18088/
Mihomo API:  http://127.0.0.1:19090/
Mixed proxy: 127.0.0.1:17890
DNS:         127.0.0.1:15353
```

На первом запуске приложение:

1. создаёт runtime-папку в профиле пользователя;
2. скачивает подходящий Mihomo binary, если его нет;
3. создаёт Python venv;
4. ставит зависимости из `unified-ui/requirements.txt`;
5. запускает локальный Flask backend и Mihomo.

### Electron TUN mode

Включение из меню:

```text
Routing → Full-system TUN routing
```

Или через env:

```sh
UNIFIED_UI_ENABLE_TUN=1 "Unified UI.app/Contents/MacOS/Unified UI"
```

В TUN-режиме Unified UI добавляет в Mihomo:

```yaml
tun:
  enable: true
  stack: system
  auto-route: true
  auto-detect-interface: true
  strict-route: false
  dns-hijack:
    - any:53
```

На macOS Mihomo запрашивает administrator prompt через `osascript`, потому что `utun/routes` без повышенных прав не поднять. На Linux нужны root/capabilities. На Windows — запуск с правами администратора для Wintun/system routes.

Обычный режим без TUN безопасный: только локальный proxy, без перехвата всего трафика системы.

### Windows: восстановление удаления старой сборки

Если удаление из “Панели управления” показывает `NSIS Error: Installer integrity check has failed`, значит установленный `Uninstall Unified UI.exe` повреждён или был частично записан/заблокирован Defender'ом. Это не лечится из уже сломанного uninstall-файла.

Рабочий путь:

1. скачай свежий `Unified-UI-Setup-2.5.2-x64.exe`;
2. установи его **поверх** текущей установки в ту же папку;
3. после этого удаляй через “Приложения и компоненты” ещё раз.

Версия `2.5.2` также исправляет `EPERM/Permission denied` при скачивании `mihomo-windows-amd64-v1.19.29.zip`: загрузка теперь идёт во временный `.part`/unique файл, cleanup не валит Electron main process.

---

## 5. Legacy Desktop Qt/WebView

Qt-сборка — отдельная нативная оболочка:

```text
Unified UI Qt
```

Артефакт:

```text
Unified-UI-Qt-2.5.1-arm64.dmg
```

Что внутри:

- PySide6;
- QtWebEngine;
- нативное окно;
- верхняя панель в стиле Unified UI;
- кнопки `Обновить`, `Runtime`, `TUN ON/OFF`;
- тот же Flask backend;
- тот же Mihomo runtime;
- тот же веб-интерфейс внутри окна.

Порты Qt-сборки:

```text
Unified UI:  http://127.0.0.1:18188/
Mihomo API:  http://127.0.0.1:19190/
Mixed proxy: 127.0.0.1:17990
DNS:         127.0.0.1:15354
```

Проверка из исходников:

```sh
python3 -m pip install -r desktop/qt/requirements-qt.txt
python3 desktop/qt/unified_ui_qt.py --smoke
python3 desktop/qt/unified_ui_qt.py
```

Сборка macOS `.app/.dmg`:

```sh
pyinstaller --noconfirm \
  --distpath dist/qt \
  --workpath build/qt \
  desktop/qt/unified-ui-qt.spec

hdiutil create -volname 'Unified UI Qt' \
  -srcfolder 'dist/qt/Unified UI Qt.app' \
  -ov -format UDZO \
  'dist/qt/Unified-UI-Qt-2.5.1-arm64.dmg'
```

---

## 6. Keenetic / Entware

### Требования

- установлен Entware;
- есть shell-доступ к роутеру;
- свободен порт `8088` или доступен запасной порт;
- желательно уже иметь рабочий Mihomo config.

### Установка

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

### Что ставит Keenetic installer

- Python/Flask/gevent панель;
- bundled wheelhouse для Python-зависимостей;
- standalone Mihomo core;
- layout `/opt/etc/mihomo`;
- symlink `config.yaml -> profiles/default.yaml`;
- `/opt/etc/mihomo/restart-mihomo.sh`;
- optional `xk-geodat`;
- optional proxy-client artifacts;
- init-сервис `/opt/etc/init.d/S99unified-ui001`.

### Обновление Keenetic

Через UI:

```text
Настройки → Проверить обновления → Установить
```

Или вручную:

```sh
/opt/etc/unified-ui/scripts/update_unified_ui.sh
```

---

## 7. OpenWrt / standalone Mihomo

OpenWrt-сборка — full-panel snapshot той же Unified UI, но без Flask/Python на роутере.

### Требования

- OpenWrt с `apk` или совместимым shell;
- `uhttpd` с `/www` и `/cgi-bin`;
- установленный Mihomo binary;
- активный config `/etc/mihomo/config.yaml`;
- controller `127.0.0.1:9090`;
- mixed proxy обычно `7890`.

### Установка

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

OpenWrt-версия ставит:

- `/www/unified-ui/` — static full-panel UI;
- `/www/cgi-bin/unified-ui-api` — CGI API bridge;
- `/etc/unified-ui/openwrt.env`;
- `/etc/unified-ui/BUILD.json`;
- `/etc/unified-ui/openwrt-update.sh`;
- backups в `/etc/unified-ui/backups/`.

Она **не ставит Python/Flask**, не тянет Nikki и не использует LuCI/Nikki UI.

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

## MikroTik / RouterOS

| Объект | Назначение |
|---|---|
| `/usb1/docker/unified-ui-mikrotik` | Container `root-dir` / persistent state |
| `MIHOMO` | RouterOS veth для контейнера |
| `192.168.254.3` | IP контейнера |
| `192.168.254.1` | Gateway IP на RouterOS стороне veth |
| `UNIFIED_UI_MIKROTIK` | RouterOS container envlist первого запуска |
| `mikrotik/routeros-install-template.rsc` | Шаблон установки |
| `unified-ui-mikrotik-docker-archive.tar.gz` | Classic docker-archive для `/container/add file=...` |

## Desktop runtime

| Shell | Runtime path |
|---|---|
| Electron macOS | `~/Library/Application Support/unified-ui/runtime` |
| Qt macOS | `~/Library/Application Support/Unified UI Qt/runtime` |
| Docker | `/data/unified-ui` + `/etc/mihomo` volumes |

---

# Разработка

Базовые проверки:

```sh
python3 -m py_compile unified-ui/app_factory.py
npm run frontend:build
node scripts/verify_frontend_build.mjs
```

Desktop Electron:

```sh
npx electron-builder --mac dmg --arm64
npx electron-builder --win nsis --x64
npx electron-builder --linux deb rpm AppImage --x64
```

Desktop Qt:

```sh
python3 -m pip install -r desktop/qt/requirements-qt.txt
python3 desktop/qt/unified_ui_qt.py --smoke
pyinstaller --noconfirm --distpath dist/qt --workpath build/qt desktop/qt/unified-ui-qt.spec
```

Docker:

```sh
docker build -t ghcr.io/sllikmll/unified-ui:latest .
docker run --rm -p 8088:8088 -p 9090:9090 ghcr.io/sllikmll/unified-ui:latest
```

MikroTik / RouterOS container:

```sh
sh -n mikrotik/entrypoint.sh
npm run frontend:build

docker run --privileged --rm tonistiigi/binfmt --install arm64

docker build --platform linux/arm64 \
  -f mikrotik/Dockerfile \
  -t unified-ui-mikrotik:routeros .

skopeo copy \
  docker-daemon:unified-ui-mikrotik:routeros \
  docker-archive:unified-ui-mikrotik-docker-archive.tar:unified-ui-mikrotik:routeros

gzip -1 -f unified-ui-mikrotik-docker-archive.tar
```

---

# Проверено в `v2.5.1`

| Проверка | Результат |
|---|---|
| Electron packaged macOS app | UI стартует, Mihomo `v1.19.29`, ports `18088/19090` listen |
| Qt packaged macOS app | `--smoke` зелёный, UI `200`, Mihomo `v1.19.29` |
| Docker normal mode | container `healthy`, UI `/login`, Mihomo API отвечает |
| Docker TUN config | `tun`, `auto-route`, `dns-hijack` добавляются в config |
| DMG validation | Electron DMG и Qt DMG checksum valid |
| GHCR | `2.5.1` и `latest` manifest доступны |

---

# Происхождение

Сейчас это отдельный **Unified UI** проект: одна панель для Keenetic, OpenWrt, MikroTik, Docker и desktop-устройств.
