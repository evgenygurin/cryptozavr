# Dev Workflow Contract v2 — Superpowers + FastMCP, token-economical

Активные плагины:
- `superpowers` (obra/superpowers v5.0.7)
- `fastmcp-creator` (Jamie-BitFlight/claude_skills v4.2.9)

Этот файл — **инструкция для агента в сессии**. Читается один раз при старте,
затем агент руководствуется ей. Все планы проекта — по ссылкам на git-файлы
в `docs/superpowers/plans/`, не в prompt-окне.

---

## IRON RULES (non-negotiable)

1. **Skill-first.** В начале сессии вызываешь `superpowers:using-superpowers`.
   Перед любым non-trivial действием проверяешь: подходит ли skill?
   Если шанс >1% — вызывай Skill ДО любого ответа, включая уточняющие
   вопросы.

2. **No code without approved design.** Никакой имплементации, никаких
   scaffold'ов, никакого Write/Edit по source-коду, пока
   `superpowers:brainstorming` не провёл дизайн и пользователь его явно
   не approve'ил. Silent-consent ЗАПРЕЩЁН.

3. **No implementation without plan.** Когда дизайн утверждён —
   `superpowers:writing-plans`, сохранить в `docs/superpowers/plans/`,
   дождаться user ok.

4. **TDD per production-code change.** RED → GREEN → REFACTOR внутри
   subagent'а. Код без watched failure — удалить.

5. **No completion claims without evidence.** `verification-before-completion`
   ПЕРЕД фразой "готово/работает" и перед любым commit/PR.

6. **No fix without root cause.** Баг → `systematic-debugging` 4-фазно.
   3+ неудачных фикса = архитектурная проблема, STOP + обсуждать.

7. **MCP work is docs-first.** Любое касание FastMCP → `fastmcp-creator`
   + MCP-инструменты `mcp__plugin_fastmcp-creator_fastmcp-reference__*`
   (search_docs / validate_server / scaffold_server / version_check).

8. **⭐ NEW — Token economy.** Задачи дробятся на **крупные unit'ы**
   (3-5 per sub-project, не 14 bite-sized). Один subagent = один
   autonomous unit. Review — лёгкий на unit, тяжёлый на group.
   Подробности → секция «Subagent Economy».

---

## Subagent Economy (главное отличие от v1)

### Правило размера unit'а

**Unit = логически связанный кусок с чёткой границей, который один
subagent может сделать от RED до GREEN за ОДИН dispatch.**

Хороший unit:
- 3-8 файлов, все связаны одним concern'ом
- 10-30 тестов внутри
- Subagent сам делает TDD цикл
- После завершения — коммит

Плохой unit (слишком мелкий):
- "Написать один индикатор SMA" — overhead на 3 reviewers > продукт
- "Добавить один метод" — делай это сам без subagent

Плохой unit (слишком крупный):
- "Сделай всю фазу 3" — subagent не удержит в контексте
- "8 MCP tools одним махом" — ломается review quality

### Правила review

| Уровень | Что делаем | Когда |
|---|---|---|
| **Self-review** | subagent сам после TDD | Всегда, внутри каждого unit |
| **Light review (1 reviewer)** | spec compliance + quick quality pass в одном dispatch | После каждого unit |
| **Heavy review (full code review)** | независимый subagent прочитывает весь diff, архитектура, security | Один раз на group (= один PR) |
| **User review gate** | пользователь читает spec и утверждает | После brainstorming до writing-plans |

**Не делаем двойной review на каждый unit.** Это был главный провал v1.

### Экономия контекста

1. **Subagent читает файлы сам** через ссылки на paths в git. Не передаём полный код в prompt.
2. **Subagent получает контракт, не копию кода** — границы, интерфейсы, что уже есть, что надо сделать.
3. **Один master plan на диске** (`docs/superpowers/plans/.../master-plan.md`). Все subagents ссылаются на нужную секцию, не получают full plain text.
4. **Parallel dispatches независимых unit'ов** — если unit A и unit B не зависят друг от друга, запускаем одновременно.

### Budget ориентир

При грамотном режиме: **~20 subagent dispatches на 6 оставшихся phase**
(2D + 2E + skill + 3 + 4 + 5), не 273. **~1-2 weekly quota** на всё,
не 5-8.

---

## Trigger → Skill (MUST invoke)

| Ситуация | Skill |
|---|---|
| Начало сессии | `superpowers:using-superpowers` |
| "Давай добавим / построим X" | `superpowers:brainstorming` |
| Дизайн утверждён, пора планировать | `superpowers:writing-plans` |
| План утверждён, изоляция нужна | `superpowers:using-git-worktrees` |
| План готов, несколько unit'ов, текущая сессия | `superpowers:subagent-driven-development` |
| 2+ независимых unit'ов одновременно | `superpowers:dispatching-parallel-agents` |
| Пишу production-код внутри subagent | `superpowers:test-driven-development` |
| Пишу / ревью / дебажу Python-тесты | `fastmcp-creator:fastmcp-python-tests` |
| Баг / failing test | `superpowers:systematic-debugging` |
| Перед "готово" / коммит / PR | `superpowers:verification-before-completion` |
| Группа закончена, нужен heavy review | `superpowers:requesting-code-review` |
| Получил review feedback | `superpowers:receiving-code-review` |
| Всё зелёное, merge/PR/cleanup | `superpowers:finishing-a-development-branch` |
| Создаю/правлю skill | `superpowers:writing-skills` |
| FastMCP сервер: build/extend/debug | `fastmcp-creator:fastmcp-creator` |
| Внешний MCP сервер — понять tools | `fastmcp-creator:fastmcp-client-cli` |
| Вопрос по FastMCP v3 API | `...fastmcp-reference__search_docs` ДО ответа |
| Старт нового FastMCP проекта | `...fastmcp-reference__scaffold_server` |
| Изменения FastMCP закончены | `...fastmcp-reference__validate_server` |

---

## Канонический pipeline

```bash
Идея
    ↓ brainstorming ← ASK → APPROVE → spec в docs/superpowers/specs/
Дизайн approved
    ↓ writing-plans ← decompose на UNITS → plan → user ok
Master plan на диске
    ↓ using-git-worktrees (если нужно)
    ↓ subagent-driven-development
    ↓   per unit:
    ↓     dispatch subagent → TDD внутри → self-review → commit
    ↓     light review (1 dispatch) → feedback → fix (если надо)
    ↓     mark checkbox в master-plan.md
Все unit'ы группы done
    ↓ requesting-code-review (heavy, 1 dispatch на group)
    ↓ receiving-code-review
Merge-ready
    ↓ finishing-a-development-branch ← user решает merge/PR/keep/discard
Merge
```

---

## MCP Work Contract (FastMCP-specific)

Порядок обязателен:
1. ПЕРЕД кодом → `fastmcp-creator:fastmcp-creator` + Trigger Matrix
2. API-вопрос → `search_docs` первый
3. Новый сервер → `scaffold_server` даёт скелет
4. Изменения готовы → `validate_server` перед claim "работает"
5. Интеграция со сторонним MCP → `fastmcp-client-cli` (fastmcp list / call)
6. v3 синтаксис: `@mcp.tool` без скобок, `task=True`, `require_scopes`,
   `arbitrary_types_allowed=True` для dataclass-полей.

---

## Красные флаги → STOP

- "Простой вопрос, не нужен skill" → вызывай
- "Быстро посмотрю код" → skill говорит КАК смотреть
- "Я помню этот API" → skills evolve, читай свежий
- "Just try changing X" → `systematic-debugging` нарушение
- "Готово" без `verification-before-completion` → STOP
- FastMCP-код без `search_docs` → STOP
- Пользователь молчит → НЕ silent-consent
- **NEW: Дробишь задачу меньше unit'а** → объединяй, не диспетч под каждый метод
- **NEW: Запускаешь 2-3 reviewers на один unit** → хватит одного light

---

## Если застрял

- 3+ фикса не сработали → brainstorming, архитектурный вопрос
- Plan слишком большой для одного PR → декомпозируй через brainstorming
- Review непонятен → задай вопрос ДО имплементации
- FastMCP ведёт себя странно → `search_docs` + Version Gating (3.0 vs 3.1)
- **Unit получился слишком большой** (>10 файлов / subagent теряется) →
  раздели на 2 unit'а, **не выполняй сам**

---

## Запрещено

- Merge в main без явной команды пользователя
- Self-LOCK spec/plan по silent consent
- Декомпозиция одной фазы на подфазы без brainstorming с user
- Amend published commits без запроса
- Skip TDD / verification
- FastMCP code на training data без `search_docs`
- v2-синтаксис (`@mcp.tool()` со скобками, `TaskConfig`, `require_auth`)
- **NEW: Диспетч subagent под одну функцию / один файл** — overhead > value
- **NEW: Два reviewer'а на один unit** — достаточно одного light

---

## Язык

Русский в коммуникации. Технические идентификаторы (skill names, API,
код) — оригинал.
