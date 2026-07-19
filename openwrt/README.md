# Unified UI для OpenWrt

Этот каталог — OpenWrt-native адаптер Unified UI без Python/Flask.

## Почему не Python

На тестовом роутере `172.16.0.21`:

```text
OpenWrt 25.12.5
arch: aarch64_cortex-a53
root overlay: 147.6M total / 116.0M used / 26.9M free
python3: not installed
package manager: apk, not opkg
Mihomo is managed by Nikki: /usr/bin/mihomo -d /etc/nikki/run
controller: http://127.0.0.1:6060
```

`apk add --simulate python3` показывает полный Python stack примерно до `141.6 MiB in 250 packages`, а Flask-пакета (`py3-flask`) в feeds нет. Для роутера с 27M свободного overlay это плохой путь.

## Текущий подход

Лёгкий режим:

```text
uhttpd static page /www/unified-ui/index.html
CGI backend       /www/cgi-bin/unified-ui-api
Mihomo API        http://127.0.0.1:6060
Secret            uci get nikki.mixin.api_secret
Config            /etc/nikki/run/config.yaml
Restart           /etc/init.d/nikki restart
```

## Установка прототипа

```sh
cat openwrt/install-openwrt-prototype.sh | ssh root@172.16.0.21 'sh'
```

После установки:

```text
http://172.16.0.21/unified-ui/
```

API endpoints:

```text
/cgi-bin/unified-ui-api/status
/cgi-bin/unified-ui-api/version
/cgi-bin/unified-ui-api/configs
/cgi-bin/unified-ui-api/proxies
/cgi-bin/unified-ui-api/connections
/cgi-bin/unified-ui-api/restart
```

## Проверено на 172.16.0.21

```text
/unified-ui/                       HTTP 200
/cgi-bin/unified-ui-api/status     HTTP 200
/cgi-bin/unified-ui-api/version    HTTP 200
/cgi-bin/unified-ui-api/proxies    HTTP 200
/cgi-bin/unified-ui-api/connections HTTP 200
```

Playwright smoke:

```text
status: PID 5633 / v1.19.27
summary: Групп: 22 · узлов/служебных proxy: 18
groupHeaders: 22
connections: 25
errors: []
```

## Следующие этапы

1. Перенести UI-компоненты из Flask-панели в общий frontend package, чтобы OpenWrt и Keenetic использовали одну визуальную базу.
2. Реализовать write endpoints:
   - selector switch через `PUT /proxies/<group>`;
   - delay check через `/group/<name>/delay` или `/proxies/<name>/delay`;
   - close connection через `DELETE /connections/<id>`;
   - close all через `DELETE /connections`.
3. Реализовать config editor для `/etc/nikki/profiles/manual-mihomo.yaml` и safe apply через Nikki.
4. Добавить auth-интеграцию через LuCI/rpcd session либо встроенный shared-secret gate.
5. Собрать нормальный release asset `unified-ui-openwrt.tar.gz`.
