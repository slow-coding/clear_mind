"""Obsidian vault integration via CLI commands."""

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_vault_path: Path | None = None
_agent_folder: str = "_clear_mind"


def set_vault_path(path: Path, agent_folder: str = "_clear_mind") -> None:
    global _vault_path, _agent_folder
    _vault_path = path
    _agent_folder = agent_folder


def _get_vault() -> Path:
    if _vault_path is None:
        raise RuntimeError("Vault path not configured. Call set_vault_path() first.")
    return _vault_path


def _validate_agent_path(note_path: str) -> Path:
    """Only allow writes inside the agent folder (_clear_mind/)."""
    vault = _get_vault()
    resolved = (vault / note_path).resolve()
    agent_dir = (vault / _agent_folder).resolve()
    if not str(resolved).startswith(str(agent_dir)):
        raise PermissionError(
            f"Cannot write outside {_agent_folder}/. Rejected: {note_path}"
        )
    if not str(resolved).startswith(str(vault.resolve())):
        raise ValueError("Path traversal detected. Rejected.")
    return resolved


def _run_cli(*args: str) -> str:
    """Execute an Obsidian CLI command."""
    result = subprocess.run(
        ["obsidian", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Read-only tools (accessible across entire vault)
# ---------------------------------------------------------------------------


@tool
def read_note(path: str) -> str:
    """Read the contents of a note in the Obsidian vault.

    Args:
        path: Note path relative to vault root, e.g. "folder/note.md"
    """
    return _run_cli("read", f"path={path}")


@tool
def search_notes(query: str) -> str:
    """Search the Obsidian vault for notes matching a text query.

    Uses Obsidian's built-in search index for fast, accurate results.

    Args:
        query: Search text
    """
    return _run_cli("search", f"query={query}")


@tool
def search_notes_context(query: str, limit: int = 10) -> str:
    """Search vault with surrounding context lines (grep-style).

    Args:
        query: Search text
        limit: Max number of files to return
    """
    return _run_cli("search:context", f"query={query}", f"limit={limit}")


@tool
def list_notes(folder: str = "") -> str:
    """List files in a vault folder.

    Args:
        folder: Folder path relative to vault root. Empty for root.
    """
    args = ["files"]
    if folder:
        args.append(f"folder={folder}")
    return _run_cli(*args)


@tool
def list_folders(folder: str = "") -> str:
    """List subfolders in a vault folder.

    Args:
        folder: Folder path relative to vault root. Empty for root.
    """
    args = ["folders"]
    if folder:
        args.append(f"folder={folder}")
    return _run_cli(*args)


@tool
def get_backlinks(path: str) -> str:
    """Get backlinks (incoming links) to a note.

    Args:
        path: Note path relative to vault root
    """
    return _run_cli("backlinks", f"path={path}", "format=json")


@tool
def get_outline(path: str) -> str:
    """Get the heading outline of a note.

    Args:
        path: Note path relative to vault root
    """
    return _run_cli("outline", f"path={path}")


@tool
def get_tags() -> str:
    """List all tags in the vault with their occurrence counts."""
    return _run_cli("tags", "counts")


@tool
def get_tasks(path: str = "") -> str:
    """List tasks from a note or the entire vault.

    Args:
        path: Optional note path. If empty, lists all vault tasks.
    """
    args = ["tasks", "todo"]
    if path:
        args.append(f"path={path}")
    return _run_cli(*args)


@tool
def get_note_info(path: str) -> str:
    """Get metadata about a note (size, created time, modified time).

    Args:
        path: Note path relative to vault root
    """
    return _run_cli("file", f"path={path}")


@tool
def get_property(path: str, name: str) -> str:
    """Read a specific frontmatter property from a note.

    Args:
        path: Note path relative to vault root
        name: Property name to read
    """
    return _run_cli("property:read", f"path={path}", f"name={name}")


# ---------------------------------------------------------------------------
# Write tools (restricted to agent folder _clear_mind/)
# ---------------------------------------------------------------------------


@tool
def write_agent_note(path: str, content: str) -> str:
    """Create or overwrite a note in the agent's folder (_clear_mind/).

    The path MUST be inside _clear_mind/. Writing outside is forbidden.

    Args:
        path: Note path relative to vault root, must start with _clear_mind/
        content: Full note content in Markdown
    """
    _validate_agent_path(path)
    return _run_cli("create", f"path={path}", f"content={content}", "overwrite")


@tool
def append_agent_note(path: str, content: str) -> str:
    """Append content to a note in the agent's folder (_clear_mind/).

    Args:
        path: Note path relative to vault root, must start with _clear_mind/
        content: Content to append
    """
    _validate_agent_path(path)
    return _run_cli("append", f"path={path}", f"content={content}")


@tool
def set_property(path: str, name: str, value: str) -> str:
    """Set a frontmatter property on a note in the agent's folder (_clear_mind/).

    Args:
        path: Note path relative to vault root, must start with _clear_mind/
        name: Property name
        value: Property value
    """
    _validate_agent_path(path)
    return _run_cli("property:set", f"path={path}", f"name={name}", f"value={value}")


# ---------------------------------------------------------------------------
# Vault change scanning (pure Python, no LLM tokens consumed)
# ---------------------------------------------------------------------------


@dataclass
class FileChange:
    path: str
    modified_at: datetime
    size: int


def scan_vault_changes(since: datetime) -> list[FileChange]:
    """Scan vault for markdown files modified since a given timestamp.

    Skips the agent's own folder and hidden directories.
    """
    vault = _get_vault()
    agent_dir = (vault / _agent_folder).resolve()
    changes: list[FileChange] = []

    for root, dirs, filenames in os.walk(vault):
        # Prune hidden directories and agent folder so os.walk won't descend
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and (Path(root) / d).resolve() != agent_dir
        ]

        for fname in filenames:
            if not fname.endswith(".md"):
                continue

            md_file = Path(root) / fname
            stat = md_file.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime).astimezone()
            if mtime > since:
                changes.append(
                    FileChange(
                        path=str(md_file.relative_to(vault)),
                        modified_at=mtime,
                        size=stat.st_size,
                    )
                )

    return changes


# ---------------------------------------------------------------------------
# Agent folder initialization
# ---------------------------------------------------------------------------

INITIAL_AGENTS_MD = """\
# Clear Mind Agent

You are Clear Mind, a thoughtful AI companion who helps maintain clarity and order
in the user's knowledge system. You observe, understand, and grow alongside the user.

## Core Values
- Respect the user's notes -- they are sacred
- Grow understanding incrementally
- Suggest, don't impose
- Reduce entropy wherever possible
"""

INITIAL_ABOUT_USER = """\
# About the User

*This file grows as the agent learns more about the user through their notes and conversations.*
"""

INITIAL_PERSONALITY = """\
# Personality Growth

*This file records how the agent's personality evolves to better serve the user.*
"""

INITIAL_ENTROPY_LOG = """\
# Entropy Reduction Log

*Suggestions and actions that help maintain clarity and order in the vault.*
"""

INITIAL_KNOWLEDGE_RULES = """\
# Knowledge Base Rules

*Rules learned by the agent about how this user organizes and uses their knowledge base. \
The agent will gradually fill this document as patterns are discovered.*
"""


def ensure_agent_structure() -> None:
    """Create the _clear_mind/ folder structure if it doesn't exist."""
    agent_dir = _get_vault() / _agent_folder
    reflections = agent_dir / "reflections"
    reflections.mkdir(parents=True, exist_ok=True)

    files = {
        "AGENTS.md": INITIAL_AGENTS_MD,
        "about_user.md": INITIAL_ABOUT_USER,
        "personality.md": INITIAL_PERSONALITY,
        "entropy_log.md": INITIAL_ENTROPY_LOG,
        "knowledge_rules.md": INITIAL_KNOWLEDGE_RULES,
    }
    for name, content in files.items():
        path = agent_dir / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
