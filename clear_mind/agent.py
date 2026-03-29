"""Agent assembly using DeepAgents SDK."""

import uuid

from clear_mind.obsidian import (
    append_agent_note,
    get_backlinks,
    get_note_info,
    get_outline,
    get_property,
    get_tags,
    get_tasks,
    list_folders,
    list_notes,
    read_note,
    search_notes,
    search_notes_context,
    set_property,
    write_agent_note,
)
from clear_mind.prompts import SYSTEM_PROMPT


def _get_all_tools():
    """Return all tools available to the agent."""
    return [
        # Read-only (full vault)
        read_note,
        search_notes,
        search_notes_context,
        list_notes,
        list_folders,
        get_backlinks,
        get_outline,
        get_tags,
        get_tasks,
        get_note_info,
        get_property,
        # Write (agent folder only)
        write_agent_note,
        append_agent_note,
        set_property,
    ]


# Write tools that require human approval
_WRITE_TOOLS = {"write_agent_note", "append_agent_note", "set_property"}


def create_clear_mind_agent(config, checkpointer, *, enable_hitl: bool = True):
    """Assemble the Clear Mind agent.

    Accepts a checkpointer instance (already opened via context manager).
    When enable_hitl is True, write tools require human approval.
    """
    from deepagents import create_deep_agent

    model = config.get_model()

    interrupt_on = None
    if enable_hitl:
        interrupt_on = {name: True for name in _WRITE_TOOLS}

    agent = create_deep_agent(
        model=model,
        tools=_get_all_tools(),
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        interrupt_on=interrupt_on,
    )
    return agent


def _stream_agent(agent, console, config, input_data):
    """Stream agent output, handling HITL interrupts.

    Returns accumulated response text.
    """
    from langgraph.types import Command
    from rich.live import Live
    from rich.markdown import Markdown

    from clear_mind.hitl import handle_interrupt

    response_text = ""

    with Live(console=console, refresh_per_second=8, vertical_overflow="visible") as live:
        for chunk in agent.stream(
            input_data,
            config=config,
            stream_mode=["messages", "updates"],
        ):
            mode, data = chunk

            if mode == "messages":
                token, _metadata = data
                if isinstance(token, str):
                    response_text += token
                    live.update(Markdown(response_text))
                elif hasattr(token, "content") and getattr(token, "type", None) == "ai":
                    # AIMessage chunk
                    if token.content and isinstance(token.content, str):
                        response_text += token.content
                        live.update(Markdown(response_text))

            elif mode == "updates":
                # Check for HITL interrupts
                if isinstance(data, dict) and "__interrupt__" in data:
                    for interrupt_obj in data["__interrupt__"]:
                        live.stop()
                        hitl_response = handle_interrupt(
                            console, interrupt_obj.value
                        )
                        console.print()
                        live.start()
                        # Resume with the approval decision
                        resumed_text = _stream_agent(
                            agent, console, config,
                            Command(resume=hitl_response),
                        )
                        response_text += resumed_text

    return response_text


def run_chat(agent, thread_id: str = "default") -> None:
    """Run an interactive chat loop in the terminal."""
    from importlib.metadata import version as pkg_version

    from rich.console import Console

    from clear_mind.input_handler import get_user_input

    console = Console()
    config = {"configurable": {"thread_id": thread_id}}

    ver = pkg_version("clear-mind")
    console.print(f"[bold cyan]Clear Mind[/] v{ver}")
    console.print("[dim]Enter to send, Ctrl+O for newline, ESC to cancel, /clear to reset session.[/]")
    console.print("[dim]Type exit or quit to end the session.[/]\n")

    # Agent greets first
    _stream_agent(
        agent, console, config,
        {"messages": [{"role": "user", "content": "请简单打个招呼，不需要读任何文件。"}]},
    )
    console.print()

    while True:
        user_input = get_user_input(console)

        if user_input is None:
            console.print("[dim]Goodbye.[/]")
            break

        stripped = user_input.lower().strip()

        if stripped in ("exit", "quit", "q"):
            console.print("[dim]Goodbye.[/]")
            break

        if stripped == "/clear":
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            console.print("[dim]Session cleared.[/]\n")
            continue

        if not user_input.strip():
            continue

        _stream_agent(
            agent, console, config,
            {"messages": [{"role": "user", "content": user_input}]},
        )
        console.print()
