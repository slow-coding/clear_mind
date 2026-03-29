"""Agent assembly using LangGraph."""

import re
import uuid

from clear_mind.obsidian import (
    append_agent_note,
    append_note,
    get_backlinks,
    get_note_info,
    get_outline,
    get_property,
    get_tags,
    list_folders,
    list_notes,
    read_note,
    search_notes,
    search_notes_context,
    set_property,
    write_agent_note,
    write_note,
)
from clear_mind.prompts import SYSTEM_PROMPT

# Tools for normal chat (hard boundary: _clear_mind/ only)
_AGENT_TOOLS = [
    # Read-only (full vault)
    read_note,
    search_notes,
    search_notes_context,
    list_notes,
    list_folders,
    get_backlinks,
    get_outline,
    get_tags,
    get_note_info,
    get_property,
    # Write (agent folder only)
    write_agent_note,
    append_agent_note,
    set_property,
]

# Tools for /card and /refactor (full vault write access, no agent-folder restriction)
_FULL_TOOLS = [
    # Read-only (full vault)
    read_note,
    search_notes,
    search_notes_context,
    list_notes,
    list_folders,
    get_backlinks,
    get_outline,
    get_tags,
    get_note_info,
    get_property,
    # Write (full vault)
    write_note,
    append_note,
]


def create_clear_mind_agent(config, checkpointer, *,
                            full_write: bool = False,
                            knowledge_rules: str = ""):
    """Assemble the Clear Mind agent.

    Accepts a checkpointer instance (already opened via context manager).
    When full_write is True, agent can write anywhere in the vault.
    knowledge_rules is pre-loaded content of _clear_mind/knowledge_rules.md.
    """
    from datetime import datetime

    from langgraph.prebuilt import create_react_agent

    model = config.get_model()

    tools = _FULL_TOOLS if full_write else _AGENT_TOOLS

    current_date = datetime.now().strftime("%Y-%m-%d")
    system_prompt = SYSTEM_PROMPT.format(current_date=current_date, knowledge_rules=knowledge_rules)

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
        checkpointer=checkpointer,
    )
    return agent


def _stream_agent(agent, console, config, input_data):
    """Stream agent output token by token."""
    from rich.live import Live
    from rich.markdown import Markdown

    response_text = ""
    tool_counts: dict[str, int] = {}

    with Live("\n", console=console, refresh_per_second=15, vertical_overflow="visible") as live:
        for chunk in agent.stream(
            input_data,
            config=config,
            stream_mode="messages",
        ):
            message, _metadata = chunk
            content = getattr(message, "content", None)
            msg_type = getattr(message, "type", None)

            if msg_type in ("ai", "AIMessageChunk"):
                if content and isinstance(content, str):
                    response_text += content
                else:
                    tool_calls = getattr(message, "tool_calls", None)
                    if tool_calls:
                        for tc in tool_calls:
                            name = tc.get("name", "")
                            if name:
                                tool_counts[name] = tool_counts.get(name, 0) + 1

                # Build display: tool summary + response
                parts = []
                if tool_counts:
                    calls = ", ".join(
                        f"{name} ×{n}" if n > 1 else name
                        for name, n in tool_counts.items()
                    )
                    parts.append(f"*⚙ {calls}*")
                if response_text:
                    parts.append(response_text)
                live.update(Markdown("\n\n".join(parts)))
            elif msg_type == "tool":
                pass

    # Fallback: if streaming produced nothing, use invoke
    if not response_text:
        with console.status("[dim]Thinking...[/]"):
            result = agent.invoke(input_data, config=config)
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "content") and getattr(msg, "type", None) == "ai":
                console.print(Markdown(msg.content))
                break


def _handle_card(user_text: str, agent, console, config) -> None:
    """Handle /card command: write user content as a note card, verbatim."""
    _stream_agent(
        agent, console, config,
        {"messages": [{"role": "user", "content": (
            "Create a note card. STRICT RULES:\n"
            "1. Write the user's content to a suitable path in the vault (e.g. cards/ folder).\n"
            "2. File name must be in the SAME LANGUAGE as the user's content (e.g. Chinese content → Chinese file name).\n"
            "3. The content must be EXACTLY what the user wrote. Do NOT add, expand, rewrite, or continue.\n"
            "4. ONLY fix: obvious typos, broken grammar that obscures meaning, punctuation.\n"
            "4. Do NOT add headers, summaries, bullet points, commentary, or anything the user didn't write.\n"
            "5. If the user wrote one sentence, the card contains one sentence. No more.\n"
            "6. After writing, just confirm the file path. No explanation.\n\n"
            f"User content:\n---\n{user_text}\n---"
        )}]},
    )


def _handle_memo(user_text: str, agent, console, config) -> None:
    """Handle /memo command: record a rule to knowledge_rules.md."""
    _stream_agent(
        agent, console, config,
        {"messages": [{"role": "user", "content": (
            f"Record this as a rule in `_clear_mind/knowledge_rules.md` "
            f"using `append_agent_note`. Format it concisely. "
            f"Do not add commentary, just record the rule:\n\n"
            f"---\n{user_text}\n---"
        )}]},
    )


def _handle_refactor(user_text: str, agent, console, config) -> None:
    """Handle /refactor command: reorganize notes per user's instructions."""
    _stream_agent(
        agent, console, config,
        {"messages": [{"role": "user", "content": (
            f"Reorganize/refactor notes according to these instructions. "
            f"You have full write access to the vault. "
            f"Read the relevant notes first, then make the changes.\n\n"
            f"---\n{user_text}\n---"
        )}]},
    )


# Pattern: /command followed by space and content
_CMD_PATTERN = re.compile(r"^/(card|memo|refactor|search|deep)\s+(.*)", re.DOTALL)


def _handle_search(query: str, console) -> None:
    """Handle /search: fast Obsidian CLI search, no LLM."""
    from clear_mind.obsidian import _run_cli
    from rich.panel import Panel
    from rich.text import Text

    try:
        results = _run_cli("search", f"query={query}")
    except Exception as e:
        console.print(f"[red]Search failed: {e}[/]")
        return

    if not results:
        console.print(f"[dim]No results for: {query}[/]")
        return

    console.print(Panel(Text(results), title=f"Search: {query}", border_style="cyan"))


def _handle_deep(user_text: str, agent, console, config) -> None:
    """Handle /deep: deep, thorough response rooted in full understanding of the user."""
    _stream_agent(
        agent, console, config,
        {"messages": [{"role": "user", "content": (
            "The user is asking you to think deeply about something, fully from THEIR perspective.\n\n"
            "Before answering, you MUST:\n"
            "1. Read `_clear_mind/about_user.md` — what you know about this person\n"
            "2. Read `_clear_mind/knowledge_rules.md` — rules about their note system\n"
            "3. Search the vault for notes related to the user's question — read the relevant ones thoroughly\n"
            "4. Consider their values, habits, goals, and concerns shown in their notes\n\n"
            "Then respond:\n"
            "- Stand fully in THEIR shoes, not as an outside advisor\n"
            "- Draw concrete connections to what you've read in their vault\n"
            "- Be thorough and deep — this is not a quick answer\n"
            "- Speak their language (match the language of their notes)\n"
            "- Be honest. If you don't have enough context, say so.\n\n"
            f"User's question/topic:\n---\n{user_text}\n---"
        )}]},
    )


def _print_help(console, ver: str) -> None:
    """Print the command help table."""
    from rich.box import ROUNDED
    from rich.table import Table

    console.print(f"[bold cyan]Clear Mind[/] v{ver}\n")
    table = Table(show_header=False, box=ROUNDED, border_style="dim", padding=(0, 2))
    table.add_row("[bold]/card[/] <text>", "Write a note card (verbatim)")
    table.add_row("[bold]/memo[/] <rule>", "Record a knowledge rule")
    table.add_row("[bold]/search[/] <query>", "Search vault (instant)")
    table.add_row("[bold]/deep[/] <topic>", "Deep think from your POV")
    table.add_row("[bold]/refactor[/] <instr>", "Reorganize notes")
    table.add_row("[bold]/clear[/]", "Clear screen & reset session")
    table.add_row("[bold]exit[/]", "Quit")
    console.print(table)
    console.print()


def run_chat(agent, config_obj, checkpointer, thread_id: str | None = None) -> None:
    """Run an interactive chat loop in the terminal."""
    from importlib.metadata import version as pkg_version

    from rich.console import Console

    from clear_mind.input_handler import get_user_input

    console = Console()
    if thread_id is None:
        thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    ver = pkg_version("clear-mind")
    _print_help(console, ver)

    while True:
        user_input = get_user_input(console)

        if user_input is None:
            console.print("[dim]Goodbye.[/]")
            break

        stripped = user_input.strip()

        if stripped.lower() in ("exit", "quit", "q"):
            console.print("[dim]Goodbye.[/]")
            break

        if stripped.lower() == "/clear":
            import os
            os.system("clear")
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            _print_help(console, ver)
            continue

        if not stripped:
            continue

        # Check for slash commands
        cmd_match = _CMD_PATTERN.match(stripped)
        if cmd_match:
            cmd, content = cmd_match.groups()
            content = content.strip()

            if not content:
                console.print(f"[dim]Usage: /{cmd} <content>[/]\n")
                continue

            if cmd == "card":
                card_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                model = config_obj.get_model()
                from langgraph.prebuilt import create_react_agent
                card_agent = create_react_agent(
                    model=model,
                    tools=_FULL_TOOLS,
                    prompt="You are Clear Mind. You have FULL write access to the entire Obsidian vault. Use `write_note` to create notes anywhere.",
                    checkpointer=checkpointer,
                )
                _handle_card(content, card_agent, console, card_config)

            elif cmd == "memo":
                _handle_memo(content, agent, console, config)

            elif cmd == "search":
                _handle_search(content, console)

            elif cmd == "deep":
                _handle_deep(content, agent, console, config)

            elif cmd == "refactor":
                refactor_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                model = config_obj.get_model()
                from langgraph.prebuilt import create_react_agent
                refactor_agent = create_react_agent(
                    model=model,
                    tools=_FULL_TOOLS,
                    prompt="You are Clear Mind. You have FULL write access to the entire Obsidian vault. Use `write_note`, `append_note`, `read_note`, `search_notes` etc. as needed. Read before writing.",
                    checkpointer=checkpointer,
                )
                _handle_refactor(content, refactor_agent, console, refactor_config)

            console.print()
            continue

        # Normal chat
        _stream_agent(
            agent, console, config,
            {"messages": [{"role": "user", "content": user_input}]},
        )
        console.print()
