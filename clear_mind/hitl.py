"""Human-in-the-loop tool approval for Clear Mind agent."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def handle_interrupt(console: Console, hitl_request: dict) -> dict:
    """Handle a HITL interrupt by presenting approval UI and collecting decisions.

    Args:
        console: Rich Console instance.
        hitl_request: The HITLRequest dict from the interrupt value.

    Returns:
        HITLResponse dict with decisions.
    """
    action_requests = hitl_request["action_requests"]
    decisions = []

    for req in action_requests:
        name = req["name"]
        args = req.get("args", {})

        # Format args for display
        args_text = "\n".join(f"  {k}: {v}" for k, v in args.items())
        if not args_text:
            args_text = "  (no arguments)"

        panel = Panel(
            Text(args_text),
            title=f"[bold yellow]{name}[/]",
            border_style="yellow",
        )
        console.print(panel)
        console.print("[dim]  approve / reject  (a/r)[/]")

        while True:
            try:
                choice = input("  > ").strip().lower()
            except EOFError:
                choice = "a"

            if choice in ("a", "approve", "y", "yes", ""):
                decisions.append({"type": "approve"})
                console.print("[dim]  Approved.[/]")
                break
            elif choice in ("r", "reject", "n", "no"):
                msg = ""
                try:
                    console.print("[dim]  Reason (optional, Enter to skip):[/]")
                    msg = input("  > ").strip()
                except EOFError:
                    pass
                decision = {"type": "reject"}
                if msg:
                    decision["message"] = msg
                decisions.append(decision)
                console.print("[dim]  Rejected.[/]")
                break
            else:
                console.print("[dim]  Press 'a' to approve or 'r' to reject.[/]")

    return {"decisions": decisions}
