Локальный Happ decryptor
========================

Кладите сюда локальный decryptor, если нужна поддержка raw-ссылок
`happ://crypt...`. Для актуального `happ://crypt5` используйте сборку
`happ-decrypt-universal` из раздела ниже: она расшифровывает ссылку локально и
не требует внешнего HTTP-сервиса.

Имена файлов, которые панель ищет автоматически:
- happ_decryptor.py
- happ-decryptor.py
- happ_decrypt_universal.py
- happ-decrypt-universal.py
- happwner.py
- Happwner.py
- happ_decryptor
- happ-decryptor
- happ_decrypt_universal
- happ-decrypt-universal
- happwner

Контракт команды:
- XKeen передаёт входящую ссылку последним аргументом или заменяет `%LINK%`.
- Decryptor должен вывести один из вариантов:
  - прямой URL подписки
  - расшифрованный текст или тело подписки
  - JSON с полем `url`, `text`, `result`, `output`, `body` или `decrypted`

Автоопределение всегда можно переопределить переменной:
- XKEEN_HAPP_DECRYPTOR_CMD
- XKEEN_HAPP_DECRYPTOR_REMOTE_URL

Встроенный `scripts/happ_transport_helper.py` по-прежнему отвечает за HTTP(S)
landing page подписки Happ.

Опциональный remote fallback
============================

Если локальный decryptor временно несовместим с будущим форматом Happ, можно
явно включить HTTP fallback через доверенный внешний endpoint.

Вариант 1: JSON API endpoint, который принимает POST `{ "url": "happ://crypt..." }`
и возвращает JSON с `decryptedUrl`, `url` или `result`:

```sh
XKEEN_HAPP_DECRYPTOR_REMOTE_URL='https://example.com/api/decrypt'
```

Вариант 2: GET URL-шаблон с `%LINK_ENCODED%` или `%LINK%`. Панель подставит raw
Happ deep-link прямо в URL и выполнит GET-запрос. Это удобно для публичных proxy
сервисов наподобие Happy Decoder:

```sh
XKEEN_HAPP_DECRYPTOR_REMOTE_URL='https://happy-decoder.cc/p/%LINK_ENCODED%'
```

По умолчанию этот fallback выключен: включайте его только если осознанно
доверяете внешнему сервису и понимаете, что ссылка подписки уйдёт на удалённый
сервер.

Локальная сборка актуального crypt5
===================================

Репозиторий XKeen не хранит готовый Happ decryptor и ключевой материал. Для
локальных тестов можно собрать drop-in decryptor из актуального checkout
`LeeeeT/happ-decryptor` и включить его в локальный архив
`xkeen-ui-routing.tar.gz`, не коммитя launcher, assets или сгенерированный
исходник с ключевым материалом в GitHub.

Ожидаемый локальный checkout:
- `.tmp/leeeet-happ-decryptor`

Builder читает:
- `src/decrypt.js`
- `src/emu/emu_core.js`
- `public/emu/liberror-code.so`
- `public/emu/unicorn_aarch64.js`
- `public/emu/unicorn-wrapper.js`
- `public/data/keytable.json`

Команда сборки из корня репозитория:

```sh
python scripts/build_happ_decryptor_node.py
```

Выходные файлы по умолчанию:

```text
xkeen-ui/bin/happ-decrypt-universal
xkeen-ui/bin/happ-decrypt-universal.assets/
```

Для запуска нужен `node` на той машине, где работает UI. Decryptor выполняет
расшифровку локально: `happ://crypt5` не отправляется на внешний сервис.

Рекомендуемая явная команда для роутера:

```sh
XKEEN_HAPP_DECRYPTOR_CMD='/opt/bin/node /opt/etc/xkeen-ui/bin/happ-decrypt-universal %LINK%'
```

Если `node` уже есть в `PATH` процесса UI и launcher сохраняет auto-detect имя
`happ-decrypt-universal`, задавать `XKEEN_HAPP_DECRYPTOR_CMD` необязательно.
Панель найдёт его автоматически.

Чтобы передать локальный decryptor тестировщикам, пересоберите пользовательский
архив после появления launcher и assets-директории:

```sh
python scripts/build_user_archive.py --skip-frontend-build
```

Ручная установка у тестировщика
===============================

Тестировщикам нужно передавать launcher и assets-директорию рядом с ним:

```text
happ-decrypt-universal
happ-decrypt-universal.assets/
```

Сборка не привязана к старому Linux/aarch64 Go-бинарнику, но для запуска нужен
`node` на той машине, где работает UI. Assets используются локально, без
обращения к внешнему decoder-сервису.

Рекомендуемый путь на роутере:

```text
/opt/etc/xkeen-ui/bin/happ-decrypt-universal
/opt/etc/xkeen-ui/bin/happ-decrypt-universal.assets/
```

Пример загрузки с ПК:

```sh
scp happ-decrypt-universal root@192.168.1.1:/tmp/happ-decrypt-universal
scp -r happ-decrypt-universal.assets root@192.168.1.1:/tmp/happ-decrypt-universal.assets
```

Затем выполните на роутере по SSH:

```sh
mkdir -p /opt/etc/xkeen-ui/bin
mv /tmp/happ-decrypt-universal /opt/etc/xkeen-ui/bin/happ-decrypt-universal
rm -rf /opt/etc/xkeen-ui/bin/happ-decrypt-universal.assets
mv /tmp/happ-decrypt-universal.assets /opt/etc/xkeen-ui/bin/happ-decrypt-universal.assets
chmod 755 /opt/etc/xkeen-ui/bin/happ-decrypt-universal
```

Быстрая проверка на роутере:

```sh
/opt/bin/node /opt/etc/xkeen-ui/bin/happ-decrypt-universal
```

Ожидаемый вывод без аргументов:

```text
usage: happ-decrypt-universal <happ://crypt...>
```

Если launcher и assets лежат по указанному пути и сохранили auto-detect имя,
XKeen должен найти их автоматически. Для явной настройки через DevTools -> ENV
укажите:

```sh
XKEEN_HAPP_DECRYPTOR_CMD=/opt/bin/node /opt/etc/xkeen-ui/bin/happ-decrypt-universal %LINK%
```

Значение применяется к следующей попытке импорта или обновления и не требует
Restart UI.
