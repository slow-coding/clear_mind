from pathlib import Path
from typing import Any

from langchain.chat_models import init_chat_model
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClearMindConfig(BaseSettings):
    """Configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_prefix="CLEAR_MIND_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Vault
    vault_path: Path
    agent_folder: str = "_clear_mind"

    # LLM
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"
    model_name: str = "qwen3.5-9b"

    # Heartbeat
    heartbeat_cron: str = "0 9 * * *"
    heartbeat_enabled: bool = True

    # State
    checkpointer_path: str = "~/_clear_mind_state/checkpoints.db"

    @property
    def agent_dir(self) -> Path:
        return self.vault_path / self.agent_folder

    def get_model(self):
        """Create an LLM instance configured for OpenAI-compatible APIs."""
        return init_chat_model(
            model=self.model_name,
            model_provider="openai",
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=300,
            max_retries=2,
        )

    def get_checkpointer(self) -> Any:
        """Create a SQLite-backed checkpointer for state persistence.

        Returns a context manager that yields a SqliteSaver.
        """
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = Path(self.checkpointer_path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return SqliteSaver.from_conn_string(str(db_path))
