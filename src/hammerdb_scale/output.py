"""Terminal output helpers using Rich."""

from rich.console import Console
from rich.panel import Panel

console = Console()


def print_success(msg: str) -> None:
    console.print(f"  [green]+[/green] {msg}")


def print_error(msg: str) -> None:
    console.print(f"  [red]x[/red] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"  [yellow]![/yellow] {msg}")


def print_info(msg: str) -> None:
    console.print(f"  [blue]>[/blue] {msg}")


def print_banner(name: str, benchmark: str, target_count: int, detail: str) -> None:
    text = f"{name} | {benchmark} | {target_count} targets | {detail}"
    console.print(Panel(text, title="HammerDB-Scale 2.0.0"))
