"""MCP prompts for paper trading sessions and reviews."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.prompts import Message


def register_paper_prompts(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="paper_scalp_session",
        description=(
            "Start a disciplined paper-trading scalp session with session rules pinned up-front."
        ),
        tags={"paper", "session"},
    )
    def paper_scalp_session(
        max_trades: int = 20,
        max_duration_min: int = 60,
    ) -> list[Message]:
        system = (
            f"You are running a paper-trading scalp session with a strict rulebook:\n"
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
        user = "Begin. Call /cryptozavr:health, get_ticker, analyze_snapshot first."
        return [Message(system, role="assistant"), Message(user, role="user")]

    @mcp.prompt(
        name="paper_review",
        description=(
            "Review the most recent paper-trading session: reads ledger + stats, extracts patterns."
        ),
        tags={"paper", "review"},
    )
    def paper_review(last_n: int = 20) -> list[Message]:
        system = (
            f"Review my last {last_n} paper trades. Read cryptozavr://paper/ledger "
            f"and cryptozavr://paper/stats. Produce a short report:\n"
            f"- Bias: where were you biased (long vs short win rates, counter-trend "
            f"vs with-trend).\n"
            f"- Winning conditions: what made winners win (time of day, regime, "
            f"symbol, note content).\n"
            f"- Losing conditions: what made losers lose.\n"
            f"- Psychological notes: patterns in the 'note' field if present.\n"
            f"- One concrete rule to add to the next session."
        )
        return [Message(system, role="assistant")]

    @mcp.prompt(
        name="discretionary_watch_loop",
        description=(
            "The event-driven discretionary loop: wait_for_event → decide → "
            "act → repeat until terminal."
        ),
        tags={"paper", "runtime"},
    )
    def discretionary_watch_loop(trade_id: str) -> list[Message]:
        system = (
            f"You have an open paper trade {trade_id}. Enter the discretionary loop:\n"
            f"1. Call wait_for_event on the trade's watch_id (from paper_trades/{trade_id}).\n"
            f"2. On each event choose exactly one action:\n"
            f"   - 'move_stop_to_breakeven' (when breakeven_reached fires)\n"
            f"   - 'partial_close' via paper_close_trade of a fraction if you build one\n"
            f"   - 'close' via paper_close_trade if thesis is broken\n"
            f"   - 'hold' — no-op, keep looping.\n"
            f"3. On stop_hit / take_hit / timeout the trade auto-closes. Stop looping.\n"
            f"4. Log decisions in the note via paper_set_note (future tool) or via a "
            f"post-close note on the next open."
        )
        return [Message(system, role="assistant")]
