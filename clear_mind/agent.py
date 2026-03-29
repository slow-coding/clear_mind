"""Agent assembly using DeepAgents SDK."""

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


def create_clear_mind_agent(config, checkpointer):
    """Assemble the Clear Mind agent.

    Accepts a checkpointer instance (already opened via context manager).
    """
    from deepagents import create_deep_agent

    model = config.get_model()
    agent = create_deep_agent(
        model=model,
        tools=_get_all_tools(),
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    return agent


def run_chat(agent, thread_id: str = "default") -> None:
    """Run an interactive chat loop in the terminal."""
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.prompt import Prompt

    console = Console()
    console.print("[bold cyan]Clear Mind[/] - Your AI companion")
    console.print("Type [dim]exit[/] or [dim]quit[/] to end the session.\n")

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/]")
            break

        if user_input.lower().strip() in ("exit", "quit", "q"):
            console.print("[dim]Goodbye.[/]")
            break

        if not user_input.strip():
            continue

        with console.status("[dim]Thinking...[/]"):
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config={"configurable": {"thread_id": thread_id}},
            )

        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "content") and getattr(msg, "type", None) == "ai":
                console.print(Markdown(msg.content))
                break

        console.print()
