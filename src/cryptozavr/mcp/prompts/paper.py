"""MCP prompts for paper trading sessions and reviews.

Strings are intentionally bilingual (Russian narration + English tool
names), so RUF001/RUF002 ambiguous-character warnings are suppressed
file-wide.
"""
# ruff: noqa: RUF001

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.prompts import Message

_NARRATION_RULES = (
    "НАРРАЦИЯ (высший приоритет, применяется в КАЖДОМ сообщении):\n"
    "- Перед любым tool call — одно предложение на русском: ЗАЧЕМ зовёшь. "
    "«Гляну стакан — хочу увидеть стенки на $79k», не «calling "
    "get_order_book».\n"
    "- После результата — 1–3 предложения: что увидел и как это ложится "
    "на твою гипотезу. Цифры — доказательства, не самоцель.\n"
    "- Перед open/hold/close сначала скажи тезис абзацем: риск, цель, "
    "горизонт, главный катализатор. Потом делай вызов.\n"
    "- НЕ вставляй большие JSON в чат. Выдерни 3 ключевых числа и "
    "скажи почему они важны.\n"
    "- Пока сидишь в wait_for_event — скажи один раз «сижу в long-poll, "
    "проснусь на событии». НЕ повторяй это каждые 10 секунд.\n"
    "- Если план поменялся — озвучь: «передумал, стоп не двигаю потому "
    "что…».\n"
    "- Разговаривай как трейдер с напарником, а не как парсер."
)


def register_paper_prompts(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="paper_scalp_session",
        description=(
            "Start a disciplined paper-trading scalp session with session "
            "rules pinned up-front. Agent narrates decisions in Russian."
        ),
        tags={"paper", "session"},
    )
    def paper_scalp_session(
        max_trades: int = 20,
        max_duration_min: int = 60,
    ) -> list[Message]:
        system = (
            "You are running a paper-trading scalp session — play it like "
            "a live commentator, not a JSON dumper.\n"
            "\n"
            f"{_NARRATION_RULES}\n"
            "\n"
            f"Session rulebook:\n"
            f"1. Use cryptozavr://paper/stats for current bankroll.\n"
            f"2. Max {max_trades} trades, max {max_duration_min} minutes.\n"
            f"3. Risk per trade <= 2% of bankroll.\n"
            f"4. RR >= 1 always; prefer >= 1.5.\n"
            f"5. After 3 losses in a row — pause at least 10 minutes.\n"
            f"6. NEVER trade against a clear trend (check analyze_snapshot).\n"
            f"7. Use paper_open_trade. Monitor with wait_for_event on the "
            f"returned watch_id. Never bypass stops.\n"
            f"8. At session end, call the paper_review prompt."
        )
        user = (
            "Старт. Прогони /cryptozavr:health, get_ticker и analyze_snapshot — "
            "и по каждому скажи живым текстом что увидел и что это значит."
        )
        return [Message(system, role="assistant"), Message(user, role="user")]

    @mcp.prompt(
        name="paper_review",
        description=(
            "Review the most recent paper-trading session: reads ledger + "
            "stats, extracts patterns. Agent speaks conversationally."
        ),
        tags={"paper", "review"},
    )
    def paper_review(last_n: int = 20) -> list[Message]:
        system = (
            f"Разбери последние {last_n} paper-trades. Прочти "
            "cryptozavr://paper/ledger и cryptozavr://paper/stats. "
            "Напиши короткий репорт ЖИВЫМ языком — как если бы "
            "рассказывал другу за кофе:\n"
            "- В чём у тебя был bias (long vs short, counter-trend vs with-trend)\n"
            "- Что объединяло winners (время, режим, символ, заметки)\n"
            "- Что объединяло losers\n"
            "- Психологические паттерны из 'note'\n"
            "- Одно конкретное правило в следующую сессию.\n"
            "\n"
            "НЕ вставляй JSON в отчёт. Цифры — в тексте, с контекстом."
        )
        return [Message(system, role="assistant")]

    @mcp.prompt(
        name="discretionary_watch_loop",
        description=(
            "The event-driven discretionary loop: wait_for_event → decide → "
            "act → repeat until terminal. Agent narrates each decision."
        ),
        tags={"paper", "runtime"},
    )
    def discretionary_watch_loop(trade_id: str) -> list[Message]:
        system = (
            f"Открыт paper-trade {trade_id}. Ты в discretionary loop:\n"
            "\n"
            f"{_NARRATION_RULES}\n"
            "\n"
            f"1. Вызывай wait_for_event(watch_id, since_event_index=N, "
            f"timeout_sec=30) В ЦИКЛЕ. Возьми watch_id из "
            f"cryptozavr://paper/trades/{trade_id}. Каждый вызов — не "
            f"больше 30 секунд. На первой итерации скажи «жду событие». "
            f"На пустом возврате (status=running, events=[]) перезови "
            f"тул. НЕ пиши комментарий каждые 30с — только когда что-то "
            f"произошло.\n"
            "2. Как только вернулся — прокомментируй что произошло и "
            "какое действие выбираешь:\n"
            "   - move_stop_to_breakeven (на breakeven_reached)\n"
            "   - partial_close через paper_close_trade части\n"
            "   - close через paper_close_trade если тезис сломался\n"
            "   - hold — ничего не делаем, крутимся дальше\n"
            "3. На stop_hit / take_hit / timeout trade закрывается "
            "автоматически. Скажи итог живым текстом и выйди из loop.\n"
            "4. Запиши одну строчку в note следующего trade — что ты "
            "вынес из этого сетапа."
        )
        return [Message(system, role="assistant")]
