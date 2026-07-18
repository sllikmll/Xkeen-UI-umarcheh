# Xkeen UI Unified

**Xkeen UI Unified** — форк панели `umarcheh001/Xkeen-UI`, собранный под сценарий “одна панель для Keenetic + Entware + Mihomo”.

Главная идея простая: не держать отдельно Python-панель на `8088` и Zashboard/Mihomo UI на `9090/ui`. Всё основное управление Mihomo собрано в одной панели:

- редактирование активного `config.yaml`;
- runtime-селекторы Mihomo;
- плиточный и компактный списочный режим выбора серверов;
- обновление ping по одному узлу или сразу по всем;
- редактор ручного списка `manual-proxy.yaml`;
- установка standalone Mihomo core вместе с UI.

> Панель рассчитана на локальную сеть. Не публикуйте её напрямую в интернет без отдельной авторизации/прокси-защиты. Интернету нельзя давать руль от роутера — он и так плохо себя ведёт.

---

## Скриншоты

### Роутинг Mihomo

![Роутинг Mihomo](docs/screenshots/xkeen-routing-mihomo.png)

### Селекторы плитками

![Селекторы Mihomo — плитки](docs/screenshots/xkeen-selectors-tiles.png)

### Селекторы списком

![Селекторы Mihomo — списком](docs/screenshots/xkeen-selectors-list.png)

---

## Репозитории

| Что | Репозиторий |
|---|---|
| Unified UI | [`sllikmll/Xkeen-UI-umarcheh`](https://github.com/sllikmll/Xkeen-UI-umarcheh) |
| Mihomo fork | [`sllikmll/mihomo`](https://github.com/sllikmll/mihomo) |
| UI upstream | [`umarcheh001/Xkeen-UI`](https://github.com/umarcheh001/Xkeen-UI) |
| Старый XKeen UI источник фич | [`zxc-rv/XKeen-UI`](https://github.com/zxc-rv/XKeen-UI) |
| Mihomo upstream | [`MetaCubeX/mihomo`](https://github.com/MetaCubeX/mihomo) |

Почему репозиторий называется `Xkeen-UI-umarcheh`, а не просто `Xkeen-UI`: в аккаунте уже есть форк `sllikmll/XKeen-UI` от `zxc-rv/XKeen-UI`, а GitHub не различает имена репозиториев только по регистру букв. Да, регистр есть, но свободы нет. Классика.

---

## Что умеет именно этот форк

### Unified installer

`install.sh` ставит не только Python-панель, но и standalone `mihomo`:

- проверяет/ставит `python3`;
- ставит `Flask`;
- по возможности ставит `gevent/gevent-websocket`;
- ставит `lftp` для файлового менеджера;
- ставит или проверяет `/opt/sbin/mihomo`;
- создаёт стандартный layout `/opt/etc/mihomo`;
- создаёт symlink `config.yaml -> profiles/default.yaml`;
- создаёт `/opt/etc/mihomo/restart-mihomo.sh`;
- прописывает команды validate/restart в env панели;
- регистрирует init-сервис `/opt/etc/init.d/S99xkeen-ui-umarcheh001`.

### Mihomo selectors внутри панели `8088`

Добавлена вкладка **Селекторы** прямо в Xkeen UI:

- runtime-переключение selector-групп через Mihomo API;
- режим **Плитки** — по умолчанию;
- режим **Списки** — компактные строки `selector + dropdown`;
- выбор сервера в подписке прямо из dropdown;
- ping рядом с узлом;
- клик по ping обновляет задержку конкретного узла;
- кнопка **Обновить все пинги**;
- поддержка provider-нод из `/providers/proxies`, а не только top-level `/proxies`.

Это важно: подписочные узлы вроде `VLESS-amst` могут быть видны внутри selector-группы, но не существовать как отдельный ключ `/proxies/VLESS-amst`. Поэтому прямой запрос `/proxies/<name>/delay` может вернуть `404`. Форк умеет мапить такие узлы через provider healthcheck.

### Ручной список в UI

Вкладка **Селекторы** также содержит редактор:

```text
/opt/etc/mihomo/rules/manual-proxy.yaml
```

Файл сохраняется через backend панели с backup. Больше не нужно лезть в SSH ради пары доменов.

---

## Быстрая установка

На Keenetic с Entware:

```sh
cd /opt
curl -fL -o xkeen-ui-routing.tar.gz \
  "https://github.com/sllikmll/Xkeen-UI-umarcheh/releases/latest/download/xkeen-ui-routing.tar.gz"
tar -xzf xkeen-ui-routing.tar.gz
cd xkeen-ui
sh install.sh
```

После установки панель обычно доступна на:

```text
http://<IP_роутера>:8088/
```

Если `8088` занят, installer попробует:

```text
8091, затем 8100–8199
```

---

## Release asset

Основной установочный архив:

```text
xkeen-ui-routing.tar.gz
```

Latest:

```text
https://github.com/sllikmll/Xkeen-UI-umarcheh/releases/latest/download/xkeen-ui-routing.tar.gz
```

Checksum:

```text
https://github.com/sllikmll/Xkeen-UI-umarcheh/releases/latest/download/xkeen-ui-routing.tar.gz.sha256
```

---

## Управление установкой Mihomo

По умолчанию Mihomo ставится вместе с UI. Отключить:

```sh
XKEEN_INSTALL_MIHOMO=0 sh install.sh
```

Принудительно переустановить бинарник:

```sh
XKEEN_INSTALL_MIHOMO_FORCE=1 sh install.sh
```

Взять конкретный repo/tag:

```sh
XKEEN_MIHOMO_REPO=sllikmll/mihomo \
XKEEN_MIHOMO_TAG=v1.19.29 \
sh install.sh
```

Взять конкретный asset URL:

```sh
XKEEN_MIHOMO_ASSET_URL=https://example.com/mihomo-linux-arm64.gz sh install.sh
```

### Откуда берётся Mihomo

Installer сначала пробует релизы форка:

```text
sllikmll/mihomo
```

Если там нет release assets, автоматически использует upstream:

```text
MetaCubeX/mihomo
```

Это сделано специально, потому что GitHub forks не наследуют upstream release assets.

---

## Пути на роутере

| Назначение | Путь |
|---|---|
| UI | `/opt/etc/xkeen-ui` |
| UI init script | `/opt/etc/init.d/S99xkeen-ui-umarcheh001` |
| UI env/state | `/opt/etc/xkeen-ui/devtools.env` |
| Mihomo binary | `/opt/sbin/mihomo` |
| Mihomo root | `/opt/etc/mihomo` |
| Active profile | `/opt/etc/mihomo/profiles/default.yaml` |
| Active config symlink | `/opt/etc/mihomo/config.yaml` |
| Mihomo restart script | `/opt/etc/mihomo/restart-mihomo.sh` |
| Manual proxy list | `/opt/etc/mihomo/rules/manual-proxy.yaml` |
| UI logs | `/opt/var/log/xkeen-ui/` |
| Mihomo logs | `/opt/var/log/mihomo/` |

Ожидаемый symlink:

```sh
/opt/etc/mihomo/config.yaml -> profiles/default.yaml
```

---

## Управление сервисами

Панель:

```sh
/opt/etc/init.d/S99xkeen-ui-umarcheh001 start
/opt/etc/init.d/S99xkeen-ui-umarcheh001 stop
/opt/etc/init.d/S99xkeen-ui-umarcheh001 restart
/opt/etc/init.d/S99xkeen-ui-umarcheh001 status
```

Mihomo:

```sh
/opt/etc/mihomo/restart-mihomo.sh
```

Проверка Mihomo API:

```sh
wget -qO- http://127.0.0.1:9090/version
```

Проверка конфига:

```sh
/opt/sbin/mihomo -t -d /opt/etc/mihomo -f /opt/etc/mihomo/config.yaml
```

---

## Основные API панели для Mihomo

| Endpoint | Что делает |
|---|---|
| `GET /api/mihomo/clash/status` | Проверяет Mihomo `/version` |
| `GET /api/mihomo/clash/proxies` | Возвращает selectors + provider nodes |
| `PUT /api/mihomo/clash/proxies/<selector>` | Переключает selector runtime |
| `POST /api/mihomo/clash/proxies/<proxy>/delay` | Обновляет ping одного узла |
| `POST /api/mihomo/clash/proxies/delay-all` | Обновляет ping всех видимых узлов |
| `GET /api/mihomo/manual-proxy` | Читает ручной список |
| `POST /api/mihomo/manual-proxy` | Сохраняет ручной список с backup |

---

## Обновление

Если панель уже установлена:

```sh
cd /opt
curl -fL -o xkeen-ui-routing.tar.gz \
  "https://github.com/sllikmll/Xkeen-UI-umarcheh/releases/latest/download/xkeen-ui-routing.tar.gz"
tar -xzf xkeen-ui-routing.tar.gz
cd xkeen-ui
sh install.sh
```

Installer сохраняет существующий порт панели и не перетирает пользовательский Mihomo profile, если он уже есть.

---

## Сброс логина/пароля

```sh
/opt/etc/init.d/S99xkeen-ui-umarcheh001 stop
rm -f /opt/etc/xkeen-ui/auth.json
/opt/etc/init.d/S99xkeen-ui-umarcheh001 start
```

После этого панель снова предложит первичную настройку доступа.

---

## Удаление

Быстро удалить панель:

```sh
sh /opt/etc/xkeen-ui/uninstall.sh
```

Дополнительная ручная очистка, если нужно снести хвосты:

```sh
rm -rf /opt/var/log/xkeen-ui
rm -f /opt/var/log/xkeen-ui.log
rm -f /opt/var/run/xkeen-ui.pid
rm -f /opt/bin/sysmon
rm -f /opt/bin/entware-backup
```

Если Mihomo больше не нужен:

```sh
rm -f /opt/sbin/mihomo
rm -rf /opt/etc/mihomo
rm -rf /opt/var/log/mihomo
rm -f /opt/var/run/mihomo.pid
```

Осторожно: удаление `/opt/etc/mihomo` снесёт ваши профили, rule-providers и ручные списки. Без backup это будет не “очистка”, а маленький бытовой апокалипсис.

---

## Разработка

Сборка frontend:

```sh
npm run frontend:build
```

Сборка пользовательского архива:

```sh
npm run archive:user
```

Быстрая проверка installer-контрактов:

```sh
pytest tests/test_unified_mihomo_install_contract.py tests/test_install_script_pip_fallbacks.py -q
```

---

## Статус проекта

Этот форк — практичная сборка под рабочий Keenetic/Entware setup:

- свежая Python-панель от `umarcheh001/Xkeen-UI`;
- идеи runtime-селекторов и ручного списка из `zxc-rv/XKeen-UI`;
- standalone Mihomo без legacy `xkeen` CLI;
- одна панель на `8088` вместо двух отдельных UI.

Фокус проекта — реальная эксплуатация на роутере, а не красивая демка, которая умирает при первом `restart`.
