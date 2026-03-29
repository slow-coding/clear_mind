"""Heartbeat mechanism for periodic vault monitoring."""

import signal
import time
from datetime import datetime, timedelta

import schedule

from clear_mind.config import ClearMindConfig
from clear_mind.obsidian import scan_vault_changes
from clear_mind.prompts import HEARTBEAT_PROMPT


def _get_last_heartbeat_time(config: ClearMindConfig) -> datetime:
    """Read the timestamp of the last successful heartbeat."""
    ts_file = config.agent_dir / ".last_heartbeat"
    if ts_file.exists():
        return datetime.fromisoformat(ts_file.read_text().strip())
    # Default: 24 hours ago for first run
    return datetime.now().astimezone() - timedelta(hours=24)


def _save_heartbeat_time(config: ClearMindConfig, ts: datetime) -> None:
    """Persist the heartbeat timestamp."""
    ts_file = config.agent_dir / ".last_heartbeat"
    ts_file.write_text(ts.isoformat(), encoding="utf-8")


def run_heartbeat_cycle(agent, config: ClearMindConfig) -> None:
    """Execute a single heartbeat cycle.

    1. Scan for changes since last heartbeat (no LLM tokens)
    2. If no changes, exit early
    3. Feed change summary to agent for reflection
    """
    last_time = _get_last_heartbeat_time(config)
    now = datetime.now().astimezone()

    changes = scan_vault_changes(last_time)
    if not changes:
        return

    # Build a lightweight summary (paths + timestamps only, no full content)
    change_lines = [
        f"- {c.path} (modified {c.modified_at.strftime('%H:%M')}, {c.size} bytes)"
        for c in changes
    ]
    change_summary = "\n".join(change_lines)

    prompt = HEARTBEAT_PROMPT.format(
        change_summary=change_summary,
        date=now.strftime("%Y-%m-%d"),
    )

    agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"configurable": {"thread_id": "heartbeat"}},
    )

    _save_heartbeat_time(config, now)


def parse_simple_cron(cron: str) -> str:
    """Parse a simplified cron expression to a schedule time.

    Only supports daily patterns like "0 9 * * *" -> "09:00".
    """
    parts = cron.split()
    if len(parts) >= 2:
        hour, minute = parts[1], parts[0]
        return f"{hour.zfill(2)}:{minute.zfill(2)}"
    return "09:00"


def start_scheduler(agent, config: ClearMindConfig) -> None:
    """Start the heartbeat scheduler as a long-running process."""
    time_str = parse_simple_cron(config.heartbeat_cron)
    schedule.every().day.at(time_str).do(
        run_heartbeat_cycle, agent=agent, config=config
    )

    running = True

    def _handle_signal(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    from rich.console import Console

    console = Console()
    console.print(
        f"[bold cyan]Clear Mind[/] heartbeat running at {time_str} daily. "
        "Press Ctrl+C to stop."
    )

    while running:
        schedule.run_pending()
        time.sleep(60)

    console.print("[dim]Heartbeat stopped.[/]")
