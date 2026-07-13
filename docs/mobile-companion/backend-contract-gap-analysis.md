# Xkeen-UI Mobile Companion Backend Contract Gap Analysis

Status: working analysis
Updated: 2026-07-13

## Цель

Определить, какие части текущего backend surface уже пригодны для Android companion, а где нам нужен отдельный mobile contract вместо прямого использования web-oriented API.

Важно: mobile roadmap теперь включает не только quick-control сценарии, но и постепенный перенос части сложных web-поверхностей. Первый глубокий модуль начинается с `Routing Xray`, затем идут `Routing Mihomo`, отдельные сценарии `Mihomo Generator`, partial `DevTools`, а позже и controlled `Commands`/`Files`. Значит, контракт нужно проектировать так, чтобы он не упирался только в стартовый MVP.

## Краткий вывод

Текущий backend уже дает почти все необходимые доменные возможности, а Android-клиент начал переиспользовать часть существующих read-only endpoint'ов напрямую. Но удобного мобильного контракта "из коробки" все еще нет. Главные проблемы не в отсутствии логики, а в форме доступа к ней: browser-style auth, смешанная гранулярность эндпоинтов, отсутствие versioned mobile namespace и неоднородный формат ответов для быстрых мобильных сценариев.

Рекомендуемое направление: оставить существующие web endpoints как есть и добавить тонкий adapter layer наподобие `/api/mobile/v1/*`, который агрегирует текущие сервисы в мобильные use cases.

## Практический статус на 2026-07-13

Этот gap analysis теперь опирается на уже существующий Android baseline в `android-companion/`. На стороне клиента уже есть рабочий Compose shell с фазами `Launching`, `Connections`, `Pair/Login`, `Ready`, capability-aware вкладками `Xray`, `Mihomo`, `Ports`, `Shell`, `Generator` и контекстными drawer-разделами.

Клиент больше не является чисто demo-only: уже подключены read-only запросы `GET /api/xkeen/core`, `GET /api/routing/fragments`, `GET /api/routing?file=...`, а `Routing Xray` умеет читать fragment list и содержимое документов. Но write/apply/service actions, auth/session transport, logs и terminal пока не опираются на полноценный backend contract.

Это делает backend gap очень конкретным: следующий рабочий шаг не в новых экранах, а в доведении текущего shell до реального mobile contract со следующими минимальными slices:

- `bootstrap` и session bootstrap/pairing;
- ready-workspace summary и safe service actions;
- logs history/live transport с reconnect semantics;
- `Routing Xray` document, `validate`, `preview`, `save`, `apply` flow.

## Что уже можно переиспользовать

| Область | Текущий surface | Оценка для mobile | Что делать |
| --- | --- | --- | --- |
| Auth and setup | `GET /api/auth/status`, `POST /api/auth/login`, `POST /api/auth/logout`, `POST /api/auth/setup` | Логика есть, но UX browser-oriented | Переиспользовать backend auth services, но не тащить текущую cookie+CSRF схему в UI без адаптера |
| Capabilities | `GET /api/capabilities` | Хорошая база для feature gating | Сохранить и встроить в mobile bootstrap/dashboard |
| Service control | `GET /api/xkeen/status`, `GET /api/xkeen/core`, `GET /api/cores/status`, `GET /api/cores/versions`, `GET /api/cores/updates`, `POST /api/xkeen/start`, `POST /api/xkeen/stop`, `POST /api/xkeen/core`, `POST /api/restart`, `POST /api/restart-xkeen` | Сильная база для quick actions; `GET /api/xkeen/core` уже читается Android-клиентом | Обернуть в агрегированный ready summary и action endpoints |
| Logs and streams | `GET /api/xray-logs`, `GET /api/xray-logs/status`, `GET /api/restart-log`, `POST /api/ws-token`, `/ws/xray-logs`, `/ws/xray-logs2`, `/ws/devtools-logs` | Пригодно частично, но потоковая модель заточена под web | Вынести мобильный streaming contract и единый reconnect-friendly protocol |
| Xray routing workflows | Xray routing/config endpoints и связанные backend services | Высокая ценность для первого editor-like mobile модуля; read-only fragments/content уже переиспользуются, но current shape все еще web-oriented | Вынести отдельные mobile use cases для `Routing Xray`: documents, validate, preview, save, apply, conflict detection |
| Mihomo workflows | Группы `/api/mihomo/profiles*`, `/api/mihomo/subscriptions*`, `/api/mihomo/generate*`, `/api/mihomo/backups*` | Полезная логика есть, но слишком широкая поверхность | Для V1 выделить quick profile/status actions, затем отдельными slices переносить `Routing Mihomo` и части `Mihomo Generator` |
| Backups | `GET /api/backups`, `POST /api/backup`, `POST /api/restore`, `POST /api/delete-backup` и related endpoints | Полезно, но рискованно для мобильного UX | Перенести в V1.1 или пускать в V1 только после отдельного safety gate |
| UI settings | `GET/PATCH /api/ui-settings` | Ограниченно полезно | Использовать только если реально нужен мобильный app-level toggle |
| Advanced config editors | `GET/POST /api/inbounds`, `GET/POST /api/outbounds`, другие Xray/Mihomo editor endpoints | Не подходит для прямого mobile parity, но важно для расширения | Не переносить как raw editor parity; строить отдельные mobile editor flows, начиная с `Routing Xray`, затем routing-related Mihomo сценариями |
| FS, RemoteFS, PTY, DevTools | `/api/fs/*`, `/api/remotefs/*`, `/api/fileops/*`, terminal/log devtools surfaces | Не подходит для V1 в полном виде, но часть сценариев имеет ценность | Вводить через granular mobile scopes и отдельные controlled surfaces |

## Текущие backend особенности, которые особенно важны для mobile

- Защита завязана на session cookie и CSRF.
- Для `/api/*` и `/ws/*` есть distinct состояния `428 not_configured`, `401 unauthorized`, `403 csrf_failed`.
- Streaming использует web socket tokens и web-oriented scopes.
- Мобильному клиенту пришлось бы знать слишком много про внутреннюю структуру web routes, если использовать их напрямую.

## Главные разрывы

### 1. Auth and pairing gap

Мобильное приложение не должно копировать браузерный UX с cookie-сессией, CSRF и промежуточными редирект-ожиданиями. Даже если для alpha мы временно используем текущую auth-модель, V1 должен получить mobile-friendly bootstrap и понятный session lifecycle.

Что нужно:

- Явный mobile bootstrap endpoint.
- Решение по session creation: либо controlled session bootstrap поверх текущей auth logic, либо device/pairing token flow.
- Понятный ответ на вопрос, как приложение восстанавливает сессию после перезапуска и как обрабатывает истечение авторизации.

### 2. Endpoint granularity gap

Сейчас полезные данные размазаны по нескольким route groups. Для мобильного dashboard это создает лишние round trips и хрупкую клиентскую сборку состояния.

Что нужно:

- Aggregated `bootstrap` endpoint.
- Aggregated `ready workspace summary` endpoint.
- Небольшой набор action endpoints, отражающих реальные мобильные use cases.

### 3. Response consistency gap

Разные части API могут возвращать разные формы успеха, ошибки и статусных payloads. Для мобильного клиента это повышает сложность обработки edge cases.

Что нужно:

- Единый envelope для mobile contract.
- Стабильные error codes.
- Явные признаки retryable/non-retryable ошибок.

### 4. Long-running operations gap

Часть операций может занимать заметное время или порождать промежуточные состояния. На мобильном нельзя полагаться на то, что пользователь будет держать экран открытым и вручную обновлять статус.

Что нужно:

- Единая модель `operation_id`.
- Polling endpoint или event stream для статуса операции.
- Ясный terminal state: `pending`, `running`, `succeeded`, `failed`, `cancelled`.

### 5. Streaming and lifecycle gap

Логи и live updates в Android живут в другом lifecycle-контексте, чем в браузере. Нам нужен контракт, который нормально переживает background/foreground и reconnect.

Что нужно:

- Единый mobile streaming protocol для логов.
- Понятные правила reconnect и replay window.
- Разделение "live tail" и "recent history".

### 6. Editor semantics gap

Если в приложении появляется `Routing Xray`, а затем `Routing Mihomo` и части `Mihomo Generator`, нам недостаточно просто "отдать файл и принять файл обратно". Мобильному редактору нужны stateful сценарии: drafts, validation, preview, conflict detection и apply semantics.

Что нужно:

- Документированная модель `draft` и `published` состояния.
- Endpoints для `validate`, `preview`, `save`, `apply`.
- Семантические diagnostics, а не только raw syntax errors.
- Явный способ сообщать о конфликте версий или внешних изменениях файла.

### 7. Terminal and file safety gap

Терминал и файловый менеджер на телефоне полезны, но это самые рискованные поверхности с точки зрения случайных действий и злоупотребления полномочиями.

Что нужно:

- Granular scopes для terminal и files отдельно от базовой mobile session.
- Read-only режимы там, где это возможно.
- Path and action guards, auditability и понятные destructive confirms.
- Ограничение raw low-level операций до тех случаев, где они действительно оправданы.

### 8. Capability and permission granularity gap

По мере расширения mobile app нам уже недостаточно общего ответа "`feature available`". Нужны флаги и permissions по конкретным advanced modules.

Что нужно:

- Capability flags уровня `routingEditor`, `mihomoGenerator`, `devtoolsPartial`, `terminal`, `files`.
- Разделение read/write/execute permission levels.
- Возможность backend-side отключать целые advanced surfaces для конкретной инсталляции.

### 9. Safety gap

Веб-панель допускает более широкий набор действий. В mobile companion нужно заранее отделить безопасные быстрые действия от опасных low-level workflows.

Что нужно:

- Каталог разрешенных quick actions.
- Явные confirm steps для рискованных операций.
- Возможность backend-side маркировать действия как запрещенные или требующие подтверждения.

### 10. Versioning gap

Существующие web endpoints исторически развивались для UI, а не как отдельный public mobile contract. Нам нужна предсказуемая compat story.

Что нужно:

- Versioned namespace для mobile.
- Contract tests.
- Документированные compat guarantees хотя бы в пределах `v1`.

### 11. Observability gap

Если мобильный клиент не может объяснить, почему действие не выполнилось, приложение быстро теряет доверие пользователя.

Что нужно:

- Correlation id или аналог для диагностирования запросов.
- Ясные machine-readable error codes.
- Read-only diagnostics summary для последних операций.

## Рекомендуемый mobile contract

Ниже не финальная спецификация, а рекомендуемый shape для Phase 1.

### Core endpoints

- `GET /api/mobile/v1/bootstrap`
- `GET /api/mobile/v1/ready`
- `POST /api/mobile/v1/session` или `POST /api/mobile/v1/pair`
- `DELETE /api/mobile/v1/session`
- `POST /api/mobile/v1/service/actions`
- `GET /api/mobile/v1/logs/sources`
- `POST /api/mobile/v1/logs/stream-token` или альтернативный streaming bootstrap
- `GET /api/mobile/v1/xray/routing/cards`
- `GET /api/mobile/v1/xray/routing/documents/{id}`
- `POST /api/mobile/v1/xray/routing/validate`
- `POST /api/mobile/v1/xray/routing/preview`
- `PUT /api/mobile/v1/xray/routing/documents/{id}`
- `POST /api/mobile/v1/xray/routing/apply`
- `GET /api/mobile/v1/operations/{id}`

### Expansion endpoints after V1

- `GET /api/mobile/v1/mihomo/profiles`
- `POST /api/mobile/v1/mihomo/profiles/activate`
- `GET /api/mobile/v1/mihomo/routing/cards`
- `GET /api/mobile/v1/mihomo/routing/documents/{id}`
- `POST /api/mobile/v1/mihomo/routing/validate`
- `POST /api/mobile/v1/mihomo/routing/preview`
- `PUT /api/mobile/v1/mihomo/routing/documents/{id}`
- `GET /api/mobile/v1/mihomo/generator/state`
- `POST /api/mobile/v1/mihomo/generator/actions`
- `GET /api/mobile/v1/devtools/summary`
- `GET /api/mobile/v1/devtools/operations/recent`
- `POST /api/mobile/v1/terminal/sessions`
- `DELETE /api/mobile/v1/terminal/sessions/{id}`
- `GET /api/mobile/v1/files/tree`
- `POST /api/mobile/v1/files/read`
- `POST /api/mobile/v1/files/write`

### Optional V1.1 / later endpoints

- `GET /api/mobile/v1/backups`
- `POST /api/mobile/v1/backups/create`
- `POST /api/mobile/v1/backups/restore`
- `GET /api/mobile/v1/diagnostics/recent`

## Рекомендуемая форма ответа

```json
{
  "ok": true,
  "data": {},
  "meta": {
    "api_version": "mobile-v1"
  }
}
```

```json
{
  "ok": false,
  "error": {
    "code": "unauthorized",
    "message": "Authentication required",
    "retryable": false
  }
}
```

Если операция асинхронная, ответ должен либо сразу содержать terminal state, либо возвращать `operation_id` с понятным способом узнать дальнейший прогресс.

## Что не нужно делать

- Не переписывать существующий web backend под mobile целиком.
- Не дублировать доменную логику только ради нового namespace.
- Не включать terminal, files, devtools и editor flows в mobile contract без поэтапного включения, capability flags и safety-модели.
- Не полагаться на прямой вызов десятков legacy/web endpoints из Android UI.
- Не проектировать mobile API под конкретную стороннюю библиотеку редактора, терминала или файлового дерева.
- Не переносить desktop split-pane и raw file-editing semantics в Android 1:1 только потому, что они уже есть в web UI.

## Практический итог для реализации

Backend уже достаточно богат по возможностям, чтобы мобильное приложение не начиналось с нуля. Более того, Android уже переиспользует часть web API для чтения active core и Xray routing documents. Но для устойчивого клиента нам нужен именно новый слой контракта, а не просто список уже существующих маршрутов. Причем этот слой должен сразу учитывать не только auth, ready summary, service actions и logs, но и стартовый controlled сценарий `Routing Xray`, а затем будущие editor/devtools/terminal/files expansion waves. Чем раньше мы введем mobile namespace, capability granularity и contract tests, тем дешевле будет дальнейшая разработка приложения.

С учетом уже поднятого `android-companion` это означает следующее: UI baseline уже не нулевой, первые read-only integrations доказали пригодность backend surface, а главным блокером для перехода к настоящему MVP теперь стал целостный mobile contract для auth, writes и streams.
