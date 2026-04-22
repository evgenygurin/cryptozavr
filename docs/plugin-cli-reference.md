# Claude Code Plugin CLI — полный справочник

Собрано на Claude Code **v2.1.114** (2026-04-22). Источники: официальная документация ([code.claude.com/docs](https://code.claude.com/docs/en/plugins-reference.md), [plugin-marketplaces.md](https://code.claude.com/docs/en/plugin-marketplaces.md), [discover-plugins.md](https://code.claude.com/docs/en/discover-plugins.md), [troubleshooting.md](https://code.claude.com/docs/en/troubleshooting.md)) + проверено напрямую через `claude plugin --help` и успешную установку `cryptozavr` локально.

## Содержание

- [Текущее состояние cryptozavr](#текущее-состояние-cryptozavr)
- [Subcommands `claude plugin`](#subcommands-claude-plugin)
- [Subcommands `claude plugin marketplace`](#subcommands-claude-plugin-marketplace)
- [Флаги `claude` CLI](#флаги-claude-cli-относящиеся-к-плагинам)
- [Env vars](#env-vars-для-enterprise--автоматизации)
- [Файлы на диске](#файлы-на-диске)
- [Формат settings.json](#формат-settingsjson)
- [Slash-команды `/plugin` (внутри сессии)](#slash-команды-plugin-внутри-сессии)
- [Типичные workflows для cryptozavr](#типичные-workflows-для-cryptozavr)
- [Debug + troubleshooting](#debug--troubleshooting)
- [Публикация в официальный маркетплейс](#публикация-в-официальный-маркетплейс)
- [Caveats](#caveats)

---

## Текущее состояние cryptozavr

После `claude plugin install cryptozavr@cryptozavr-marketplace`:

```text
cryptozavr@cryptozavr-marketplace
  Version: 0.3.0
  Scope:   user
  Status:  ✔ enabled
  Source:  directory /Users/laptop/dev/cryptozavr
```

В `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "cryptozavr@cryptozavr-marketplace": true
  },
  "extraKnownMarketplaces": {
    "cryptozavr-marketplace": {
      "source": { "source": "directory", "path": "/Users/laptop/dev/cryptozavr" }
    }
  }
}
```

## Subcommands `claude plugin`

| Команда | Что делает |
|---------|-----------|
| `claude plugin list` | Список установленных плагинов |
| `claude plugin list --json` | То же в JSON |
| `claude plugin install <name>@<marketplace>` | Установить плагин |
| `claude plugin install <name>@<marketplace> --scope user\|project\|local` | Задать scope (default: user) |
| `claude plugin uninstall <name>` | Удалить плагин |
| `claude plugin uninstall <name> --keep-data` | Удалить плагин, сохранить кэш |
| `claude plugin enable <name>` | Включить отключённый |
| `claude plugin disable <name>` | Отключить (без удаления) |
| `claude plugin update <name>` | Обновить (нужен restart Claude Code) |
| `claude plugin validate <path>` | Проверить manifest (plugin.json + marketplace.json) |

**Примеры для cryptozavr:**

```bash
claude plugin list
claude plugin install cryptozavr@cryptozavr-marketplace
claude plugin install cryptozavr@cryptozavr-marketplace --scope project
claude plugin disable cryptozavr@cryptozavr-marketplace
claude plugin enable cryptozavr@cryptozavr-marketplace
claude plugin uninstall cryptozavr@cryptozavr-marketplace
claude plugin validate /Users/laptop/dev/cryptozavr
```

## Subcommands `claude plugin marketplace`

| Команда | Что делает |
|---------|-----------|
| `claude plugin marketplace add <source>` | Добавить маркетплейс. Source: `owner/repo`, git URL, локальный путь, URL to `marketplace.json` |
| `claude plugin marketplace add <owner>/<repo>@<tag>` | Зафиксировать на теге/ветке |
| `claude plugin marketplace add <source> --sparse .claude-plugin plugins` | Sparse-checkout подкаталогов (для монорепо) |
| `claude plugin marketplace list` | Список маркетплейсов |
| `claude plugin marketplace list --json` | То же в JSON |
| `claude plugin marketplace update [name]` | Обновить один маркетплейс или все |
| `claude plugin marketplace remove <name>` | Убрать (удалит установленные плагины!) |

**Примеры:**

```bash
# Локальный путь (текущая установка cryptozavr)
claude plugin marketplace add /Users/laptop/dev/cryptozavr

# GitHub shortcut (после того как пуснули на GitHub)
claude plugin marketplace add evgenygurin/cryptozavr

# GitHub + тег
claude plugin marketplace add evgenygurin/cryptozavr@v0.3.0

# Git URL + тег
claude plugin marketplace add https://github.com/evgenygurin/cryptozavr.git#v0.3.0

# Удалить
claude plugin marketplace remove cryptozavr-marketplace
```

## Флаги `claude` CLI относящиеся к плагинам

| Флаг | Описание |
|------|----------|
| `--plugin-dir <path>` | Загрузить плагин из директории только для текущей сессии. Repeatable: `--plugin-dir A --plugin-dir B` |
| `--debug [filter]` | Debug мод с опциональным фильтром (`--debug plugins,hooks,mcp` или `--debug "!1p,!file"`) |
| `--debug-file <path>` | Запись debug логов в файл (неявно включает `--debug`) |
| `--bare` | Минимальный mode: пропускает hooks, LSP, plugin sync, auto-memory, keychain, CLAUDE.md auto-discovery. Устанавливает `CLAUDE_CODE_SIMPLE=1` |
| `--disable-slash-commands` | Отключить все skills (slash-commands всё ещё работают через `/skill-name`) |
| `-p, --print` | Non-interactive режим (для пайпов) |
| `--mcp-config <configs...>` | Загрузить MCP серверы из JSON файлов/строк (обходит плагин) |

**Примеры:**

```bash
# Тестировать плагин без установки (session-only)
claude --plugin-dir /Users/laptop/dev/cryptozavr

# Плюс debug для отладки
claude --plugin-dir /Users/laptop/dev/cryptozavr --debug

# Пишем debug в файл
claude --plugin-dir /Users/laptop/dev/cryptozavr --debug-file /tmp/plugin-debug.log

# Только плагины + MCP
claude --debug "plugins,mcp" 2>&1 | tee /tmp/claude-debug.log

# Минимальный mode (skip plugin sync) — полезно для чистого dev окружения
claude --bare
```

## Env vars (для enterprise / автоматизации)

```bash
# Директория кэша плагинов (default: ~/.claude/plugins/cache)
export CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-cache

# Pre-populated seed директория (для Docker контейнеров)
export CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-seed

# Таймаут git clone для маркетплейсов в миллисекундах (default: 60000)
export CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS=300000

# Оставить маркетплейс при ошибке update (для offline окружений)
export CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE=1

# Токены для приватных маркетплейсов (auto-updates)
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
export GH_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
export GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
export BITBUCKET_TOKEN=xxxxxxxxxxxxxxxxxxxx
```

## Файлы на диске

```text
~/.claude/
├── settings.json                              # enabledPlugins + extraKnownMarketplaces (user scope)
├── plugins/
│   ├── cache/                                 # Распакованные плагины: {marketplace}/{plugin}/{version}/
│   │   └── cryptozavr-marketplace/
│   │       └── cryptozavr/
│   │           └── 0.3.0/
│   │               ├── .claude-plugin/plugin.json
│   │               ├── skills/
│   │               ├── commands/
│   │               └── …
│   ├── marketplaces/                          # Клонированные marketplace репо
│   │   └── cryptozavr-marketplace/
│   │       └── .claude-plugin/marketplace.json
│   ├── known_marketplaces.json                # Сводка всех маркетплейсов
│   ├── installed_plugins.json                 # Сводка установленных плагинов
│   └── blocklist.json                         # Отключённые плагины

<project>/.claude/settings.json                # Project scope
<project>/.claude/settings.local.json          # Local scope (gitignored)
```

## Формат `settings.json`

### `enabledPlugins`

```json
{
  "enabledPlugins": {
    "cryptozavr@cryptozavr-marketplace": true,
    "superpowers@superpowers-marketplace": true,
    "context7@claude-plugins-official": true,
    "some-disabled-plugin": false
  }
}
```

- Ключ: `<plugin-name>@<marketplace-name>` или просто `<plugin-name>`
- Значение: `true` = enabled, `false` = disabled (но установлен)

### `extraKnownMarketplaces`

```json
{
  "extraKnownMarketplaces": {
    "cryptozavr-marketplace": {
      "source": {
        "source": "directory",
        "path": "/Users/laptop/dev/cryptozavr"
      },
      "autoUpdate": false
    },
    "superpowers-marketplace": {
      "source": {
        "source": "github",
        "repo": "obra/superpowers-marketplace"
      },
      "autoUpdate": true
    }
  }
}
```

**Поля `source`:**

- `"source": "directory"` + `"path": "<path>"` — локальная директория
- `"source": "github"` + `"repo": "<owner>/<repo>"` — GitHub shortcut
- `"source": "git"` + `"url": "<git-url>"` + `"ref"` (optional) — произвольный Git
- `"source": "url"` + `"url": "<url>"` — прямой URL к `marketplace.json`

## Slash-команды `/plugin` (внутри сессии)

Всё то же самое что и через CLI, но без `claude` prefix:

```sql
/plugin                                              # Интерактивный UI (4 tabs: Discover/Installed/Marketplaces/Errors)
/plugin list                                         # List installed
/plugin info <name>                                  # Info about a plugin
/plugin install <name>@<marketplace>                 # Install
/plugin uninstall <name>                             # Uninstall
/plugin enable <name>                                # Enable
/plugin disable <name>                               # Disable
/plugin update <name>                                # Update
/plugin validate <path>                              # Validate manifest

/plugin marketplace add <source>                     # Add marketplace
/plugin marketplace list                             # List
/plugin marketplace remove <name>                    # Remove
/plugin marketplace update [name]                    # Update

/reload-plugins                                      # Reload all plugins without restart
```

## Типичные workflows для cryptozavr

### 1. Локальная установка (текущая)

```bash
cd /Users/laptop/dev/cryptozavr
claude plugin validate .
claude plugin marketplace add /Users/laptop/dev/cryptozavr
claude plugin install cryptozavr@cryptozavr-marketplace
```

### 2. Переход на GitHub source

```bash
# Удалить локальный marketplace
claude plugin marketplace remove cryptozavr-marketplace

# Добавить GitHub
claude plugin marketplace add evgenygurin/cryptozavr

# Переустановить
claude plugin install cryptozavr@cryptozavr-marketplace
```

### 3. Обновление после push нового тега

```bash
# Локально: bump version в .claude-plugin/plugin.json
# git tag v0.1.1 && git push origin main v0.1.1

claude plugin marketplace update cryptozavr-marketplace
claude plugin update cryptozavr@cryptozavr-marketplace
# Перезапустить Claude Code для применения
```

### 4. Session-only тестирование (без установки)

```bash
# Изменения в /Users/laptop/dev/cryptozavr применяются сразу при перезапуске claude
claude --plugin-dir /Users/laptop/dev/cryptozavr --debug
```

### 5. Полная очистка

```bash
claude plugin uninstall cryptozavr@cryptozavr-marketplace
claude plugin marketplace remove cryptozavr-marketplace
# Физически удалить кэш (опционально)
rm -rf ~/.claude/plugins/cache/cryptozavr-marketplace
rm -rf ~/.claude/plugins/marketplaces/cryptozavr-marketplace
```

### 6. Установка для другого пользователя

На другой машине:

```bash
# Через GitHub (рекомендуемый способ для публичного плагина)
claude plugin marketplace add evgenygurin/cryptozavr
claude plugin install cryptozavr@cryptozavr-marketplace

# Или через pinned тег (для воспроизводимости)
claude plugin marketplace add evgenygurin/cryptozavr@v0.3.0
claude plugin install cryptozavr@cryptozavr-marketplace
```

## Debug + troubleshooting

### Диагностика системы

```bash
claude doctor
# Показывает:
# - Installation type + version
# - Invalid settings files (malformed JSON)
# - MCP server configuration errors
# - Plugin and agent loading errors
# - Context usage warnings
```

### Debug логи плагинов

```bash
# Фильтр: только плагины + hooks + MCP
claude --debug "plugins,hooks,mcp"

# В файл
claude --debug-file /tmp/claude-debug.log

# Лови ошибки во время загрузки
claude --debug 2>&1 | grep -i "plugin\|error"
```

### Валидация до установки

```bash
claude plugin validate /Users/laptop/dev/cryptozavr
# Проверяет:
# ✓ .claude-plugin/plugin.json + marketplace.json синтаксис
# ✓ commands/*.md, agents/*.md, skills/**/SKILL.md frontmatter
# ✓ hooks/hooks.json
# ✓ .mcp.json (если есть)
# ✓ Нет `..` в source paths
# ✓ Нет дубликатов имён
```

### Ошибки плагинов в интерактивной сессии

В сессии: `/plugin` → вкладка **Errors**. Показывает все ошибки загрузки плагинов с путями + трассировкой.

## Публикация в официальный маркетплейс

```text
https://claude.ai/settings/plugins/submit
```

Требования:
- Публичный GitHub репо с `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`
- Семантическое версионирование (`version` в plugin.json обновляется при каждом теге)
- Тесты + документация
- MIT/Apache/BSD license (или совместимая open-source)
- `keywords` для поиска

**Не обязательно** — можно делиться плагином ссылкой на GitHub, и пользователи сами добавляют через `/plugin marketplace add evgenygurin/cryptozavr`.

## Caveats

1. **Нет `$schema` поля.** Claude Code 2.1.114 CLI validator отвергает любые `$schema` поля в `plugin.json` и `marketplace.json` с ошибкой `Unrecognized key: "$schema"`. Хотя это стандарт JSON Schema tooling — здесь не применяется.

2. **Version bump нужен вручную.** `git tag v0.1.1` не обновляет `version` в `plugin.json` автоматически. Процесс: bump version → commit → tag → push. Иначе `claude plugin update` не увидит изменений.

3. **`update` требует restart.** После `claude plugin update` нужно перезапустить Claude Code для применения изменений к MCP серверу и slash-commands.

4. **Marketplace remove = uninstall all plugins from it.** Удаление маркетплейса автоматически удаляет все установленные из него плагины. Осторожно с `--scope user` (затронет все проекты).

5. **`--plugin-dir` для dev не перенимает кэшируемое состояние.** Каждый запуск `claude --plugin-dir <path>` загружает плагин свежий; изменения применяются сразу без `update`.

6. **Session-scope vs install-scope.** `--plugin-dir` = только эта сессия, без записи в `settings.json`. `plugin install` = persistent в `settings.json`.

7. **Cursor не поддерживает SessionStart hooks.** При использовании cryptozavr в Cursor банер не появится — запусти `/cryptozavr:health` вручную.

8. **Bash hook требует bash на хосте.** Windows + WSL работает; Windows native без WSL — нет (используй git-bash или переписать hook на sh-совместимый).

## Полезные ссылки

- [Плагины overview](https://code.claude.com/docs/en/plugins.md)
- [Plugin reference (все поля manifest)](https://code.claude.com/docs/en/plugins-reference.md)
- [Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces.md)
- [Discover plugins](https://code.claude.com/docs/en/discover-plugins.md)
- [Troubleshooting](https://code.claude.com/docs/en/troubleshooting.md)
- [Submit to official marketplace](https://claude.ai/settings/plugins/submit)
- [Superpowers — reference implementation](https://github.com/obra/superpowers)
- [Superpowers marketplace](https://github.com/obra/superpowers-marketplace)
