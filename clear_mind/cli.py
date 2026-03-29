"""CLI entry point for Clear Mind."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import typer
from rich.console import Console
from rich.prompt import Prompt

from clear_mind.config import ClearMindConfig

app = typer.Typer(
    name="clear-mind",
    help="Clear Mind - An AI companion that grows with you through your Obsidian notes.",
)
console = Console()


def _load_config(
    vault: Path | None = None,
    model: str | None = None,
) -> ClearMindConfig:
    """Load configuration from .env, applying optional CLI overrides."""
    overrides = {}
    if vault is not None:
        overrides["vault_path"] = vault
    if model is not None:
        overrides["model_name"] = model
    return ClearMindConfig(**overrides)


@contextmanager
def _agent_session(
    vault: Path | None = None,
    model: str | None = None,
) -> Generator[tuple, None, None]:
    """Context manager that sets up the agent and tears down the checkpointer.

    Yields (agent, config). The checkpointer is kept open for the duration
    of the context and closed on exit.
    """
    from clear_mind.agent import create_clear_mind_agent
    from clear_mind.obsidian import ensure_agent_structure, set_vault_path

    config = _load_config(vault=vault, model=model)
    set_vault_path(config.vault_path, agent_folder=config.agent_folder)
    ensure_agent_structure()

    # Pre-load knowledge rules
    rules_path = config.agent_dir / "knowledge_rules.md"
    knowledge_rules = ""
    if rules_path.exists():
        knowledge_rules = rules_path.read_text(encoding="utf-8")

    checkpointer_ctx = config.get_checkpointer()
    with checkpointer_ctx as checkpointer:
        agent = create_clear_mind_agent(
            config, checkpointer, knowledge_rules=knowledge_rules,
        )
        yield agent, config, checkpointer


@app.command()
def reset():
    """Clear agent memory: checkpoint database and _clear_mind/ contents."""
    config = _load_config()

    # Remove checkpoint database
    db = config.checkpoint_db
    if db.exists():
        db.unlink()
        console.print(f"[green]Removed checkpoint: {db}[/]")
    else:
        console.print("[dim]No checkpoint database found.[/]")

    # Reset _clear_mind/ files to initial state
    from clear_mind.obsidian import ensure_agent_structure, set_vault_path

    set_vault_path(config.vault_path, agent_folder=config.agent_folder)
    agent_dir = config.agent_dir
    if agent_dir.exists():
        # Remove contents but keep directory structure
        for f in agent_dir.iterdir():
            if f.is_file():
                f.unlink()
            elif f.is_dir():
                import shutil
                shutil.rmtree(f)
        console.print(f"[green]Cleared agent files in {agent_dir}[/]")

    ensure_agent_structure()
    console.print("[green]Agent memory reset complete. Run [cyan]clear-mind chat[/] to start fresh.[/]")


@app.command()
def init(
    vault: Path | None = typer.Option(None, "--vault", "-v", help="Path to Obsidian vault"),
    base_url: str | None = typer.Option(None, "--base-url", help="LLM API base URL"),
    api_key: str | None = typer.Option(None, "--api-key", help="LLM API key"),
    model: str | None = typer.Option(None, "--model", "-m", help="Model name"),
):
    """Interactive setup: configure vault path, model, and initialize _clear_mind/ structure."""
    console.print("[bold cyan]Clear Mind Setup[/]\n")

    if vault is None:
        detected_vault = "." if (Path.cwd() / ".obsidian").exists() else None
        if detected_vault:
            console.print(f"[dim]Obsidian vault detected at {Path.cwd()}[/]")
        vault_input = Prompt.ask("Obsidian vault path", default=detected_vault or ".")
        vault = Path(vault_input).expanduser().resolve()
    if not vault.exists():
        console.print(f"[red]Path does not exist: {vault}[/]")
        raise typer.Exit(1)
    if not (vault / ".obsidian").exists():
        console.print(f"[yellow]Warning: {vault} does not appear to be an Obsidian vault[/]")

    if base_url is None:
        base_url = Prompt.ask("LLM base URL", default="http://localhost:1234/v1")
    if api_key is None:
        api_key = Prompt.ask("API key", default="lm-studio")
    if model is None:
        model = Prompt.ask("Model name", default="qwen3.5-9b")

    env_content = (
        f"CLEAR_MIND_VAULT_PATH={vault}\n"
        f"CLEAR_MIND_BASE_URL={base_url}\n"
        f"CLEAR_MIND_API_KEY={api_key}\n"
        f"CLEAR_MIND_MODEL_NAME={model}\n"
    )
    env_path = Path(".env")
    env_path.write_text(env_content, encoding="utf-8")
    console.print(f"\n[green]Configuration saved to {env_path.absolute()}[/]")

    from clear_mind.obsidian import ensure_agent_structure, set_vault_path

    config = _load_config(vault=vault, model=model)
    set_vault_path(config.vault_path, agent_folder=config.agent_folder)
    ensure_agent_structure()
    console.print(f"[green]Agent folder created at {vault / '_clear_mind/'}[/]")
    console.print("\n[bold]Setup complete![/] Run [cyan]clear-mind chat[/] to start.")


@app.command()
def chat(
    vault: Path | None = typer.Option(None, "--vault", "-v", help="Vault path override"),
    model: str | None = typer.Option(None, "--model", "-m", help="Model name override"),
):
    """Start an interactive chat session with your Clear Mind agent."""
    from clear_mind.agent import run_chat

    with console.status("[dim]Loading knowledge base...[/]"):
        session = _agent_session(vault=vault, model=model)
        agent, config, checkpointer = session.__enter__()

    try:
        run_chat(agent, config, checkpointer)
    finally:
        session.__exit__()


@app.command()
def heartbeat(
    vault: Path | None = typer.Option(None, "--vault", "-v", help="Vault path override"),
    model: str | None = typer.Option(None, "--model", "-m", help="Model name override"),
):
    """Run a single heartbeat cycle and exit."""
    from clear_mind.heartbeat import run_heartbeat_cycle

    with _agent_session(vault=vault, model=model) as (agent, config):
        console.print("[dim]Running heartbeat...[/]")
        run_heartbeat_cycle(agent, config)
        console.print("[green]Heartbeat complete.[/]")


@app.command()
def serve(
    vault: Path | None = typer.Option(None, "--vault", "-v", help="Vault path override"),
    model: str | None = typer.Option(None, "--model", "-m", help="Model name override"),
):
    """Start the heartbeat scheduler as a long-running process."""
    from clear_mind.heartbeat import start_scheduler

    with _agent_session(vault=vault, model=model) as (agent, config):
        start_scheduler(agent, config)


@app.command()
def doctor():
    """Diagnose configuration: check Obsidian CLI, model connection, vault structure."""
    import subprocess

    errors = []
    warnings = []

    console.print("[bold]1. Configuration[/]")
    try:
        config = ClearMindConfig()
        console.print(f"   Vault: [green]{config.vault_path}[/]")
        console.print(f"   Model: [green]{config.model_name}[/]")
        console.print(f"   Base URL: [green]{config.base_url}[/]")
    except Exception as e:
        errors.append(f"Config load failed: {e}")
        console.print(f"   [red]{e}[/]")
        raise typer.Exit(1)

    console.print("\n[bold]2. Vault[/]")
    if config.vault_path.exists():
        console.print("   Vault exists: [green]OK[/]")
        if (config.vault_path / ".obsidian").exists():
            console.print("   .obsidian/: [green]found[/]")
        else:
            warnings.append("No .obsidian/ folder -- may not be a valid vault")
            console.print("   .obsidian/: [yellow]not found[/]")
    else:
        errors.append(f"Vault path does not exist: {config.vault_path}")
        console.print(f"   [red]Vault not found: {config.vault_path}[/]")

    console.print("\n[bold]3. Agent Folder[/]")
    agent_dir = config.agent_dir
    if agent_dir.exists():
        console.print("   _clear_mind/: [green]found[/]")
        for name in ("AGENTS.md", "about_user.md", "personality.md", "entropy_log.md"):
            status = "[green]OK[/]" if (agent_dir / name).exists() else "[yellow]missing[/]"
            console.print(f"   {name}: {status}")
    else:
        warnings.append("_clear_mind/ not initialized -- run `clear-mind init`")
        console.print("   [yellow]_clear_mind/ not found[/]")

    console.print("\n[bold]4. Obsidian CLI[/]")
    try:
        result = subprocess.run(
            ["obsidian", "version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            console.print(f"   Obsidian CLI: [green]available[/] ({result.stdout.strip()})")
        else:
            errors.append("Obsidian CLI error -- agent operations will fail")
            console.print("   [red]CLI error[/]")
    except FileNotFoundError:
        errors.append("Obsidian CLI not found -- agent operations will fail")
        console.print("   [red]Not found[/]")
    except subprocess.TimeoutExpired:
        errors.append("Obsidian CLI timed out")
        console.print("   [red]Timed out[/]")

    console.print("\n[bold]5. Model Connection[/]")
    try:
        model = config.get_model()
        model.invoke("Hi")
        console.print("   Model: [green]connected[/]")
    except Exception as e:
        errors.append(f"Model connection failed: {e}")
        console.print(f"   [red]Failed: {e}[/]")

    console.print("\n[bold]--- Summary ---[/]")
    if errors:
        for e in errors:
            console.print(f"[red]ERROR: {e}[/]")
    if warnings:
        for w in warnings:
            console.print(f"[yellow]WARNING: {w}[/]")
    if not errors and not warnings:
        console.print("[green]All checks passed![/]")
    elif not errors:
        console.print("[yellow]Ready with warnings.[/]")
    else:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
