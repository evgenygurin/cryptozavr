# LLM Study Guide — обязательные материалы для продолжения cryptozavr

**Аудитория:** любой LLM-агент (Claude Code, Codex, Gemini CLI, OpenCode, Cursor), которому передали задачу в cryptozavr в **новой сессии** без контекста.

**Инвариант:** прежде чем писать код — прочитать нужную группу материалов из раздела «Группы под типовые задачи». Нельзя отвечать «из памяти» или сочинять API. При работе с файлами в репе использовать современные инструменты из раздела «Tooling cheat sheet».

Источники:
1. **FastMCP v3** — официальные доки, примеры, v3-notes. Версия: `fastmcp==3.2.4`.
2. **GoF design patterns (Python)** — conceptual examples от Refactoring.Guru, локально лежат в `/Users/laptop/Documents/design-patterns-ru/Python/src/`.
3. **Проект spec** — `docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md` (sections 5, 11, 12, 13).
4. **Project memory** — `~/.claude/projects/-Users-laptop-dev-cryptozavr/memory/feedback_fastmcp_idiomatic.md`.

---

## 1. Индивидуальные сущности FastMCP v3

Каждая ссылка — одна страница доки (`.mdx`) или один снимок миграционной заметки. Базовый URL `https://github.com/PrefectHQ/fastmcp/blob/main/`.

### Core surface (servers)

| Тема | Файл | Когда читать |
|---|---|---|
| Tool decorator | [docs/servers/tools.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/tools.mdx) | любой новый `@mcp.tool` |
| Prompt decorator | [docs/servers/prompts.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/prompts.mdx) | любой новый `@mcp.prompt` |
| Resource decorator | [docs/servers/resources.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/resources.mdx) | любой новый `@mcp.resource` |
| Context API (`ctx.*`) | [docs/servers/context.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/context.mdx) | когда нужен `ctx.info/warning/report_progress/sample/elicit` |
| Dependency Injection | [docs/servers/dependency-injection.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/dependency-injection.mdx) | `Depends(get_xxx)`, `CurrentContext()` |
| Lifespan | [docs/servers/lifespan.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/lifespan.mdx) | dict-yield паттерн для глобальных сервисов |
| Middleware | [docs/servers/middleware.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/middleware.mdx) | кросс-каттинг (logging/retry/cache/ratelimit/timing) |
| Progress | [docs/servers/progress.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/progress.mdx) | долгие операции, multi-step tools |
| Logging (server → client) | [docs/servers/logging.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/logging.mdx) | настройка уровней, форматов |
| Elicitation | [docs/servers/elicitation.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/elicitation.mdx) | запрос у пользователя внутри тула |
| Sampling | [docs/servers/sampling.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/sampling.mdx) | обратный вызов LLM клиента внутри тула |
| Tasks (task=True) | [docs/servers/tasks.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/tasks.mdx) | фоновое выполнение, TaskMeta |
| Pagination | [docs/servers/pagination.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/pagination.mdx) | когда список tools/resources не помещается в один ответ |
| Visibility (enable/disable) | [docs/servers/visibility.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/visibility.mdx) | v3 breaking: `enabled=` deprecated |
| Composition | [docs/servers/composition.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/composition.mdx) | mount, вложенные серверы |
| Server options | [docs/servers/server.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/server.mdx) | `mask_error_details`, `name`, `version` |
| Icons | [docs/servers/icons.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/icons.mdx) | визуалка tools/resources в клиенте |
| Server testing | [docs/servers/testing.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/testing.mdx) | in-memory транспорт, `Client(mcp)` |
| Telemetry | [docs/servers/telemetry.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/telemetry.mdx) | OpenTelemetry инструментация |
| Storage backends | [docs/servers/storage-backends.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/storage-backends.mdx) | state persistence |
| Versioning | [docs/servers/versioning.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/versioning.mdx) | `meta.version` tool/resource |
| Authorization | [docs/servers/authorization.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/authorization.mdx) | capability gating |

### Transforms

| Тема | Файл |
|---|---|
| Overview | [docs/servers/transforms/transforms.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/transforms.mdx) |
| Namespace prefix | [docs/servers/transforms/namespace.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/namespace.mdx) |
| Namespacing | [docs/servers/transforms/namespacing.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/namespacing.mdx) |
| Tool Transformation (rename/reshape) | [docs/servers/transforms/tool-transformation.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/tool-transformation.mdx) |
| Tool Search | [docs/servers/transforms/tool-search.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/tool-search.mdx) |
| Code Mode | [docs/servers/transforms/code-mode.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/code-mode.mdx) |
| Prompts as Tools | [docs/servers/transforms/prompts-as-tools.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/prompts-as-tools.mdx) |
| Resources as Tools | [docs/servers/transforms/resources-as-tools.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/resources-as-tools.mdx) |

### Providers

| Тема | Файл |
|---|---|
| Overview | [docs/servers/providers/overview.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/providers/overview.mdx) |
| Local (default) | [docs/servers/providers/local.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/providers/local.mdx) |
| Custom | [docs/servers/providers/custom.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/providers/custom.mdx) |
| Proxy | [docs/servers/providers/proxy.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/providers/proxy.mdx) |
| Filesystem | [docs/servers/providers/filesystem.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/providers/filesystem.mdx) |
| Skills | [docs/servers/providers/skills.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/providers/skills.mdx) |

### v3-notes (breaking changes v2 → v3)

| Заметка | Файл | Ключевое |
|---|---|---|
| Get methods consolidation | [v3-notes/get-methods-consolidation.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/get-methods-consolidation.md) | `get_tools()` → `list_tools()`, dict → list |
| Prompt internal types | [v3-notes/prompt-internal-types.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/prompt-internal-types.md) | новые internal types |
| Provider architecture | [v3-notes/provider-architecture.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/provider-architecture.md) | `FastMCPProvider`, `TransformingProvider` |
| Provider test pattern | [v3-notes/provider-test-pattern.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/provider-test-pattern.md) | `await mcp.call_tool(...)` вместо `Client(mcp)` |
| Resource internal types | [v3-notes/resource-internal-types.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/resource-internal-types.md) | v3 изменения в resource internals |
| Task meta parameter | [v3-notes/task-meta-parameter.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/task-meta-parameter.md) | `task_meta: TaskMeta` для background |
| Visibility | [v3-notes/visibility.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/visibility.md) | `mcp.enable/disable(keys/tags)` вместо `enabled=` |
| v3 features | [docs/development/v3-notes/v3-features.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/development/v3-notes/v3-features.mdx) | обзорный список |

### Upgrading

- [docs/getting-started/upgrading/from-fastmcp-2.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/getting-started/upgrading/from-fastmcp-2.mdx)
- [docs/getting-started/upgrading/from-low-level-sdk.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/getting-started/upgrading/from-low-level-sdk.mdx)
- [docs/getting-started/upgrading/from-mcp-sdk.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/getting-started/upgrading/from-mcp-sdk.mdx)

### Clients (для тестирования)

| Тема | Файл |
|---|---|
| Client basics | [docs/clients/client.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/client.mdx) |
| Transports (incl. in-memory) | [docs/clients/transports.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/transports.mdx) |
| Tools from client | [docs/clients/tools.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/tools.mdx) |
| Resources | [docs/clients/resources.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/resources.mdx) |
| Prompts | [docs/clients/prompts.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/prompts.mdx) |
| Progress handler | [docs/clients/progress.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/progress.mdx) |
| Sampling handler | [docs/clients/sampling.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/sampling.mdx) |
| Elicitation handler | [docs/clients/elicitation.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/elicitation.mdx) |
| Tasks client | [docs/clients/tasks.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/tasks.mdx) |
| Notifications | [docs/clients/notifications.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/notifications.mdx) |

### Testing

- [docs/development/tests.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/development/tests.mdx) — in-memory testing, AsyncMock
- [docs/patterns/testing.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/patterns/testing.mdx) — паттерны для unit vs integration
- [examples/testing_demo/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/testing_demo) — рабочий пример с тестами

### llms.txt / llms-full.txt (карта-индекс)

- https://gofastmcp.com/llms.txt — карта документации (100 строк), читать как TOC
- https://gofastmcp.com/llms-full.txt — полный конкатенированный дамп всех `.mdx` (большой)

### Рабочие примеры (топ-15 для cryptozavr-подобных задач)

| Цель | Пример |
|---|---|
| Minimal server | [examples/simple_echo.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/simple_echo.py) |
| Complex input schemas (Pydantic) | [examples/complex_inputs.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/complex_inputs.py) |
| Custom serializer decorator | [examples/custom_tool_serializer_decorator.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/custom_tool_serializer_decorator.py) |
| Tags + metadata | [examples/tags_example.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/tags_example.py) |
| ToolResult full control | [examples/tool_result_echo.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/tool_result_echo.py) |
| Elicitation | [examples/elicitation.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/elicitation.py) |
| Task + elicitation | [examples/task_elicitation.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/task_elicitation.py) |
| Tracing / middleware | [examples/run_with_tracing.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/run_with_tracing.py) |
| Mount multiple servers | [examples/mount_example.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/mount_example.py) |
| Proxy pattern | [examples/in_memory_proxy_example.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/in_memory_proxy_example.py) |
| Persistent state (set_state/get_state) | [examples/persistent_state/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/persistent_state) |
| Tasks (background) | [examples/tasks/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/tasks) |
| Sampling variations | [examples/sampling/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/sampling) |
| Custom provider (SQLite) | [examples/providers/sqlite/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/providers/sqlite) |
| Code mode transform | [examples/code_mode/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/code_mode) |
| Memory server | [examples/memory.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/memory.py) |
| Prompts as tools | [examples/prompts_as_tools/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/prompts_as_tools) |
| Resources as tools | [examples/resources_as_tools/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/resources_as_tools) |

---

## 2. Индивидуальные сущности — GoF паттерны (Refactoring.Guru)

Локальные файлы (conceptual examples), базовый путь `/Users/laptop/Documents/design-patterns-ru/Python/src/`.

### Creational

- **AbstractFactory** — `AbstractFactory/Conceptual/main.py`
- **Builder** — `Builder/Conceptual/main.py`
- **FactoryMethod** — `FactoryMethod/Conceptual/main.py`
- **Prototype** — `Prototype/Conceptual/main.py`
- **Singleton** — `Singleton/Conceptual/{ThreadSafe,NonThreadSafe}/main.py`

### Structural

- **Adapter** — `Adapter/Conceptual/{object,class}/main.py`
- **Bridge** — `Bridge/Conceptual/main.py`
- **Composite** — `Composite/Conceptual/main.py`
- **Decorator** — `Decorator/Conceptual/main.py`
- **Facade** — `Facade/Conceptual/main.py`
- **Flyweight** — `Flyweight/Conceptual/main.py`
- **Proxy** — `Proxy/Conceptual/main.py`

### Behavioral

- **ChainOfResponsibility** — `ChainOfResponsibility/Conceptual/main.py`
- **Command** — `Command/Conceptual/main.py`
- **Iterator** — `Iterator/Conceptual/main.py`
- **Mediator** — `Mediator/Conceptual/main.py`
- **Memento** — `Memento/Conceptual/main.py`
- **Observer** — `Observer/Conceptual/main.py`
- **State** — `State/Conceptual/main.py`
- **Strategy** — `Strategy/Conceptual/main.py`
- **TemplateMethod** — `TemplateMethod/Conceptual/main.py`
- **Visitor** — `Visitor/Conceptual/main.py`

Книги (полный справочник):

- `/Users/laptop/Documents/design-patterns-ru/Погружение в Рефакторинг (Александр Швец).pdf`
- `/Users/laptop/Documents/design-patterns-ru/design-patterns-en.epub`

---

## 3. Группы под типовые задачи

Читать все ссылки из группы **до** написания кода.

### Г1. Добавить новый MCP tool (самая частая задача)

1. [docs/servers/tools.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/tools.mdx)
2. [docs/servers/context.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/context.mdx)
3. [docs/servers/dependency-injection.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/dependency-injection.mdx)
4. [docs/servers/visibility.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/visibility.mdx) (v3 breaking)
5. `~/.claude/projects/-Users-laptop-dev-cryptozavr/memory/feedback_fastmcp_idiomatic.md`
6. В репе: `src/cryptozavr/mcp/tools/ticker.py` (reference реализация)

### Г2. Добавить новый resource (каталог / read-only lookup)

1. [docs/servers/resources.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/resources.mdx)
2. [docs/servers/context.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/context.mdx)
3. [v3-notes/resource-internal-types.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/resource-internal-types.md)
4. В репе: `src/cryptozavr/mcp/resources/catalogs.py`

### Г3. Добавить prompt (cross-client portability)

1. [docs/servers/prompts.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/prompts.mdx)
2. [docs/servers/transforms/prompts-as-tools.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/prompts-as-tools.mdx)
3. [v3-notes/prompt-internal-types.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/prompt-internal-types.md)
4. В репе: `src/cryptozavr/mcp/prompts/research.py`

### Г4. Long-running / streaming / composite tool

1. [docs/servers/tools.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/tools.mdx) (`timeout=`, `meta=`)
2. [docs/servers/progress.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/progress.mdx)
3. [docs/servers/context.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/context.mdx) (`ctx.report_progress`)
4. [docs/clients/progress.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/progress.mdx) (как тестировать progress handler)
5. В репе: `src/cryptozavr/mcp/tools/analytics.py` (`analyze_snapshot`), `src/cryptozavr/mcp/tools/history.py`

### Г5. Background task (task=True)

1. [docs/servers/tasks.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/tasks.mdx)
2. [v3-notes/task-meta-parameter.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/task-meta-parameter.md)
3. [docs/clients/tasks.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/tasks.mdx)
4. [examples/tasks/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/tasks)

### Г6. Тесты для tools/resources/prompts

1. [docs/development/tests.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/development/tests.mdx)
2. [docs/servers/testing.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/testing.mdx)
3. [v3-notes/provider-test-pattern.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/provider-test-pattern.md) (`await mcp.call_tool` вместо Client)
4. [docs/clients/transports.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/transports.mdx) (in-memory)
5. [examples/testing_demo/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/testing_demo)
6. В репе: `tests/unit/mcp/test_get_ticker_tool.py`, `tests/unit/mcp/test_analytics_tools.py`

### Г7. Error handling

1. [docs/servers/tools.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/tools.mdx) (ToolError section)
2. [docs/servers/resources.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/resources.mdx) (ResourceError)
3. [docs/servers/server.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/server.mdx) (`mask_error_details`)
4. В репе: `src/cryptozavr/mcp/errors.py::domain_to_tool_error`

### Г8. Custom provider / storage backend

1. [docs/servers/providers/overview.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/providers/overview.mdx)
2. [docs/servers/providers/custom.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/providers/custom.mdx)
3. [v3-notes/provider-architecture.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/provider-architecture.md)
4. [v3-notes/provider-test-pattern.md](https://github.com/PrefectHQ/fastmcp/blob/main/v3-notes/provider-test-pattern.md)
5. [examples/providers/sqlite/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/providers/sqlite)

### Г9. Middleware (cross-cutting на уровне MCP)

1. [docs/servers/middleware.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/middleware.mdx)
2. [docs/servers/telemetry.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/telemetry.mdx)
3. [docs/servers/logging.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/logging.mdx)
4. [examples/run_with_tracing.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/run_with_tracing.py)

### Г10. Композиция серверов / namespacing

1. [docs/servers/composition.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/composition.mdx)
2. [docs/servers/transforms/namespace.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/namespace.mdx)
3. [docs/servers/transforms/namespacing.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/transforms/namespacing.mdx)
4. [examples/mount_example.py](https://github.com/PrefectHQ/fastmcp/blob/main/examples/mount_example.py)

### Г11. Trade / LLM-inside-tool

1. [docs/servers/sampling.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/sampling.mdx)
2. [docs/servers/elicitation.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/servers/elicitation.mdx)
3. [docs/clients/sampling.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/clients/sampling.mdx)
4. [examples/sampling/](https://github.com/PrefectHQ/fastmcp/tree/main/examples/sampling)

### Г12. Миграция с v2 → v3 или с mcp-sdk

1. [docs/getting-started/upgrading/from-fastmcp-2.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/getting-started/upgrading/from-fastmcp-2.mdx)
2. [docs/getting-started/upgrading/from-low-level-sdk.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/getting-started/upgrading/from-low-level-sdk.mdx)
3. Все файлы [v3-notes/](https://github.com/PrefectHQ/fastmcp/tree/main/v3-notes)
4. [docs/development/v3-notes/v3-features.mdx](https://github.com/PrefectHQ/fastmcp/blob/main/docs/development/v3-notes/v3-features.mdx)

### Г13. Архитектура cryptozavr (паттерны в коде)

| Слой | Паттерн | Файл паттерна | Реализация в репе |
|---|---|---|---|
| L2 infra | Decorator | `Decorator/Conceptual/main.py` | `src/cryptozavr/infrastructure/providers/decorators/*.py` |
| L2 infra | Chain of Responsibility | `ChainOfResponsibility/Conceptual/main.py` | `src/cryptozavr/infrastructure/providers/chain/` |
| L2 infra | State | `State/Conceptual/main.py` | `src/cryptozavr/infrastructure/providers/state/venue_state.py` |
| L2 infra | Adapter | `Adapter/Conceptual/object/main.py` | CCXT adapter в `providers/` |
| L2 infra | Bridge | `Bridge/Conceptual/main.py` | `MarketDataProvider` interface vs CCXT/CoinGecko |
| L2 infra | Facade | `Facade/Conceptual/main.py` | `SupabaseGateway` |
| L3 domain | Flyweight | `Flyweight/Conceptual/main.py` | `SymbolRegistry` |
| L4 app | Strategy | `Strategy/Conceptual/main.py` | `AnalysisStrategy` семейство |
| L4 app | Template Method | `TemplateMethod/Conceptual/main.py` | `BaseProvider.fetch_*` скелет |
| L4 app | Factory Method | `FactoryMethod/Conceptual/main.py` | `ProviderFactory` |
| L4 app | Iterator | `Iterator/Conceptual/main.py` | `OHLCVPaginator` |
| L4 app | Mediator | `Mediator/Conceptual/main.py` | `MarketDataService` |
| L5 mcp | Facade | `Facade/Conceptual/main.py` | `build_envelope` (SessionExplainer) |

### Г14. Новые паттерны для phase 2+ (ещё не в коде)

| Паттерн | Когда появится | Файл паттерна |
|---|---|---|
| Builder | phase 2 (StrategySpec) | `Builder/Conceptual/main.py` |
| Visitor | phase 2 (backtest analytics) | `Visitor/Conceptual/main.py` |
| Memento | phase 4 (decision replay) | `Memento/Conceptual/main.py` |
| Observer | phase 1.5 (Realtime cache invalidation) | `Observer/Conceptual/main.py` |
| Command | phase 3 (TradeIntent queue) | `Command/Conceptual/main.py` |
| Prototype | phase 2 (StrategySpec presets) | `Prototype/Conceptual/main.py` |
| Composite | phase 2 (nested strategies) | `Composite/Conceptual/main.py` |

---

## 4. Промпт-шаблоны

### Шаблон A — «я получил задачу Y в новой сессии»

```text
Ты работаешь в cryptozavr (см. CLAUDE.md). До того, как написать хоть одну строку кода, выполни:

1. Определи тип задачи из списка в docs/llm-study-guide.md §3 (Г1..Г14).
2. Прочитай ВСЕ ссылки из подходящей группы — это обязательное чтение, не «если успею».
3. Если задача — про GoF паттерн, прочитай его conceptual example из §2.
4. Проверь feedback_fastmcp_idiomatic.md в memory.
5. Посмотри 1-2 reference-файла в репе (ticker.py, analytics.py — как уже сделано).

Только после этого — план → код → тесты → коммит.

Задача: <описание задачи>
```

### Шаблон B — «Ralph loop для многошаговой работы»

```text
Read docs/llm-study-guide.md and identify which group (Г1..Г14) applies to this task.
Read every referenced file in that group before writing code. Do NOT guess FastMCP APIs.

Hard rules:
- Conform to ~/.claude/projects/-Users-laptop-dev-cryptozavr/memory/feedback_fastmcp_idiomatic.md
- Every tool/resource/prompt must follow the idiomatic v3 patterns (Depends, direct Pydantic DTO return, ctx logging, ToolError, mask_error_details).
- Tests use `await mcp.call_tool(...)` (v3 provider-test-pattern) or in-memory `Client(mcp)` for integration checks.
- Imports added ONLY together with usage (CLAUDE.md §Editing workflow).
- Conventional commits, atomic, via /tmp/commit-msg.txt + git commit -F.

Task: <описание задачи>

Output <promise>...</promise> only when:
1. uv run pytest tests/unit tests/contract -m "not integration" -q — all green
2. uv run ruff check . && uv run ruff format --check . && uv run mypy src — clean
3. CHANGELOG updated, tag pushed to origin.
```

### Шаблон C — «рефакторинг по GoF»

```text
Задача связана с GoF паттерном <имя>. До написания кода:

1. Прочитай /Users/laptop/Documents/design-patterns-ru/Python/src/<Имя>/Conceptual/main.py + Output.txt.
2. Прочитай соответствующую главу в "Погружение в Рефакторинг (Александр Швец).pdf".
3. Из docs/llm-study-guide.md §3 Г13/Г14 возьми текущее или будущее место паттерна в cryptozavr.
4. Найди ближайшие аналоги в репе через `rg "class .*Decorator|Strategy|State" src/cryptozavr/` и т.п.

Реализуй следуя структуре conceptual, но адаптируй нейминг под cryptozavr.
```

---

## 5. Tooling cheat sheet

Современные замены стандартным утилитам. Использовать их по умолчанию.

### fd (вместо `find`)

```bash
fd -t f '\.py$' src/cryptozavr           # все .py файлы
fd -t f '_test\.py$' tests/              # тесты
fd -e mdx docs/servers                   # .mdx в servers/
fd -HI '__init__.py'                     # включая hidden + ignored
```

### rg (ripgrep, вместо `grep -r`)

```bash
rg -n 'class \w+Strategy' src/            # имена + номера строк
rg -l 'Depends\(' src/cryptozavr/mcp      # только имена файлов
rg -t py '@mcp\.tool' -A 2                # .py файлы + 2 строки контекста
rg -U 'class \w+:\n\s+""".*strategy'      # multiline
rg --stats 'ToolError' src tests          # + общая статистика
```

### ast-grep (структурный поиск по AST)

```bash
# Найти все @mcp.tool декораторы
ast-grep --pattern '@mcp.tool($$$)' --lang py src/

# Найти все Depends(...) в сигнатурах
ast-grep --pattern 'Depends($X)' --lang py src/

# Найти все `raise ToolError(...)`
ast-grep --pattern 'raise ToolError($$$)' --lang py src/

# Отрефакторить: model_dump(mode="json") → прямой DTO (dry-run)
ast-grep --pattern '$DTO.from_domain($$$).model_dump(mode="json")' --lang py src/
```

### fzf (интерактивный выбор)

```bash
# Выбрать файл и открыть
fd -t f -e py | fzf --preview 'bat --color=always {}'

# Выбрать коммит для cherry-pick
git log --oneline | fzf | awk '{print $1}' | xargs git cherry-pick

# Выбрать ветку
git branch -a | fzf | xargs git checkout
```

### jq (JSON)

```bash
# FastMCP repo tree
gh api 'repos/PrefectHQ/fastmcp/git/trees/main?recursive=1' \
  | jq -r '.tree[] | select(.path | test("^docs/servers/.*\\.mdx$")) | .path'

# plugin.json fields
jq -r '.name, .version' .claude-plugin/plugin.json

# pytest JSON output: падающие тесты
uv run pytest --json-report --json-report-file=/tmp/pyt.json \
  && jq -r '.tests[] | select(.outcome=="failed") | .nodeid' /tmp/pyt.json
```

### yq (YAML/TOML — в режиме -p toml)

```bash
# Читать pyproject.toml
yq -p toml '.project.dependencies' pyproject.toml

# Извлечь secrets из .env.example (формат KEY=VAL → YAML)
yq eval '.' .env.example

# Обновить зависимость
yq -iP 'toml' '.project.dependencies += ["httpx>=0.28"]' pyproject.toml
```

### gh (GitHub CLI)

```bash
# Содержимое файла в репо
gh api 'repos/PrefectHQ/fastmcp/contents/docs/servers/tools.mdx' \
  | jq -r '.content' | base64 -d

# Дерево файлов в ветке
gh api 'repos/PrefectHQ/fastmcp/git/trees/main?recursive=1' \
  | jq -r '.tree[] | select(.type=="blob") | .path'

# Последние релизы
gh release list --repo PrefectHQ/fastmcp --limit 5
```

---

## 6. Правила, которые нельзя нарушать

Эти правила — **жёсткие**, из ранее накопленного опыта:

1. **Imports only with usage** (CLAUDE.md §Editing workflow). Добавил импорт — сразу добавь код, который его использует, одним Edit/Write. Иначе ruff-format его снесёт.
2. **No HEREDOC for commits** (~/.claude/rules/git.md). Сообщение в `/tmp/commit-msg.txt`, потом `git commit -F /tmp/commit-msg.txt`.
3. **No `git add .`** — только явные файлы.
4. **Direct DTO return** из tool'ов (не `.model_dump(mode="json")`).
5. **`Depends(get_xxx_service)`** module-level, не inline (ruff B008).
6. **`await ctx.info/warning/error/report_progress`** — все асинхронные.
7. **`ToolError`** через `domain_to_tool_error`, обычные исключения маскируются `mask_error_details=True`.
8. **Tests** предпочитают `await mcp.call_tool("name", {...})` (v3 pattern) над `Client(mcp)` wrapper.
9. **Conventional commits**, атомарные, никаких mixed-concern коммитов.
10. **Никогда не pushить в main без approval** — feature branch + PR.

---

## 7. Быстрый self-check перед PR

```bash
uv run pytest tests/unit tests/contract -m "not integration" -q    # green
uv run ruff check .                                                 # no errors
uv run ruff format --check .                                        # no changes
uv run mypy src                                                     # no errors
git log --oneline origin/main..HEAD                                 # атомарные коммиты
fd -t f '\.py$' src tests | xargs rg -l 'TODO|FIXME'                # не оставил TODO
rg -n 'model_dump\(mode="json"\)' src/cryptozavr/mcp/tools          # пусто (anti-pattern)
rg -n 'cast\(Any, ctx\.' src/                                       # пусто (anti-pattern)
```

Если хоть один чек красный — PR не готов.
