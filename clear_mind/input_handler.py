"""Multi-line input handler with ESC cancellation support."""

from rich.console import Console


def get_user_input(console: Console) -> str | None:
    """Get user input with multi-line and ESC-cancel support.

    - Enter: send
    - Shift+Enter or Ctrl+O: newline
    - ESC or Ctrl+C: cancel current input (stay in conversation)
    - Ctrl+D: exit conversation

    Returns:
        The user's input string, or None if the user wants to exit.
    """
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings

    kb = KeyBindings()

    # Enter sends (default in single-line mode)
    # Shift+Enter inserts newline -- only works on terminals with modifyOtherKeys
    # Ctrl+O is the portable fallback for newline
    @kb.add("c-o")
    def _insert_newline(event):
        event.current_buffer.insert_text("\n")

    # Try to bind shift+enter for terminals that support it
    @kb.add("escape", "enter")
    def _shift_enter_fallback(event):
        event.current_buffer.insert_text("\n")

    # ESC cancels input by resetting buffer and accepting empty
    @kb.add("escape")
    def _cancel_input(event):
        event.current_buffer.reset()
        event.current_buffer.set_document(
            type("Doc", (), {"text": "", "cursor_position": 0})()
        )
        event.app.exit(result="")

    try:
        result = pt_prompt(
            HTML("<ansigreen><b>You</b></ansigreen>> "),
            key_bindings=kb,
            multiline=False,
        )
    except KeyboardInterrupt:
        # Ctrl+C exits conversation
        return None
    except EOFError:
        # Ctrl+D exits
        return None

    if result is None:
        return ""

    return result
