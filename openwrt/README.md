# Unified UI для OpenWrt

OpenWrt-версия Unified UI сделана **без Python/Flask**: лёгкая статическая страница под `uhttpd` + CGI backend на `ash`, который ходит в Mihomo API Nikki.

## Почему не Python

На тестовом роутере `172.16.0.21`:

```text
OpenWrt 25.12.5
arch: aarch64_cortex-a53
root overlay: 147.6M total / 116.0M used / 26.9M free
python3: not installed
package manager: apk, not opkg
```

Симуляция показывает:

```text
apk add --simulate python3 -> OK: 141.6 MiB in 250 packages
py3-flask -> no such package
```

То есть Flask-панель для этого OpenWrt — плохая идея: overlay быстро забьётся и роутер словит ненужную боль.

## Архитектура

```text
uhttpd static page      /www/unified-ui/index.html
CGI backend             /www/cgi-bin/unified-ui-api
runtime config/env      /etc/unified-ui/openwrt.env
build info              /etc/unified-ui/BUILD.json
backup dir              /etc/unified-ui/backups/
update script           /etc/unified-ui/openwrt-update.sh
uninstall script        /etc/unified-ui/openwrt-uninstall.sh
Mihomo controller       http://127.0.0.1:6060
Nikki profile           /etc/nikki/profiles/manual-mihomo.yaml
Nikki active config     /etc/nikki/run/config.yaml
```

## Что умеет сейчас

### Runtime controls

- статус Mihomo + UI version;
- просмотр selector/group/proxy дерева;
- переключение selector → proxy;
- delay/ping check по proxy;
- просмотр активных соединений;
- фильтр соединений;
- разрыв одного соединения;
- разрыв всех соединений;
- restart Nikki/Mihomo.

### Config editor

Для `manual-mihomo.yaml`:

- чтение текущего конфига;
- validate через реальный `mihomo -t`;
- save только после успешной валидации;
- backup старого файла перед записью;
- save+apply через restart Nikki;
- сохранение backup в `/etc/unified-ui/backups/`.

## Release asset

Основной OpenWrt-архив:

```text
unified-ui-openwrt.tar.gz
```

Latest:

```text
https://github.com/sllikmll/Unified-UI/releases/latest/download/unified-ui-openwrt.tar.gz
```

Checksum:

```text
https://github.com/sllikmll/Unified-UI/releases/latest/download/unified-ui-openwrt.tar.gz.sha256
```

## Установка на OpenWrt

```sh
cd /tmp
curl -fL -o unified-ui-openwrt.tar.gz \
  "https://github.com/sllikmll/Unified-UI/releases/latest/download/unified-ui-openwrt.tar.gz"
mkdir -p unified-ui-openwrt
tar -xzf unified-ui-openwrt.tar.gz -C .
cd unified-ui-openwrt
sh install.sh
```

После установки:

```text
http://<router>/unified-ui/
```

## API endpoints

```text
GET  /cgi-bin/unified-ui-api/status
GET  /cgi-bin/unified-ui-api/version
GET  /cgi-bin/unified-ui-api/configs
GET  /cgi-bin/unified-ui-api/proxies
GET  /cgi-bin/unified-ui-api/connections
GET  /cgi-bin/unified-ui-api/config-get
GET  /cgi-bin/unified-ui-api/restart
POST /cgi-bin/unified-ui-api/select                { group, groupEncoded, name }
POST /cgi-bin/unified-ui-api/delay                 { name, nameEncoded, timeout, url }
POST /cgi-bin/unified-ui-api/connection-close      { id }
POST /cgi-bin/unified-ui-api/connections-close-all {}
POST /cgi-bin/unified-ui-api/config-validate       { content }
POST /cgi-bin/unified-ui-api/config-save           { content, apply }
```

## Обновление и удаление

Обновление с release asset:

```sh
sh /etc/unified-ui/openwrt-update.sh
```

Полное удаление:

```sh
sh /etc/unified-ui/openwrt-uninstall.sh
```

## Проверено на 172.16.0.21

HTTP smoke:

```text
/unified-ui/                           HTTP 200
/cgi-bin/unified-ui-api/status         HTTP 200
/cgi-bin/unified-ui-api/version        HTTP 200
/cgi-bin/unified-ui-api/proxies        HTTP 200
/cgi-bin/unified-ui-api/connections    HTTP 200
/cgi-bin/unified-ui-api/config-get     HTTP 200
```

Runtime actions:

```text
delay DIRECT: {"delay":86}
select GLOBAL -> DIRECT: HTTP 200
close one connection: before_count=25, after_count=24
```

Config editor:

```text
config-get: path=/etc/nikki/profiles/manual-mihomo.yaml
content_len: 19231
config-validate: ok=true, exit_code=0
config-save apply=false: ok=true, backup created
config-save apply=true: ok=true, pid_changed=true
```

Browser smoke:

```text
summary: Групп: 22 · узлов/служебных proxy: 18
selectors: 22 dropdowns
ping buttons: 361
apply buttons: 22
close buttons: 25
config tab: textarea loaded, validate OK
JS errors: []
```

## Сборка локального release-архива

```sh
python3 scripts/build_openwrt_archive.py \
  --version 2.4.x-unified \
  --update-url https://github.com/sllikmll/Unified-UI/releases/download/v2.4.x-unified/unified-ui-openwrt.tar.gz
```

или

```sh
npm run archive:openwrt
```

## Что дальше можно улучшить

- diff/editor UX лучше обычного textarea;
- compare against running config `/etc/nikki/run/config.yaml`;
- selective restart/reload flow, если Nikki даст безопасный apply без полного restart;
- auth gate поверх OpenWrt UI, если панель будут открывать не только из LAN.
