"""Test result formatting and terminal output."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table


@dataclass
class TestResult:
    name: str
    passed: bool
    details: list[str] = field(default_factory=list)
    sub_results: list[TestResult] | None = None


def print_report(
    mode: str,
    inbox: str,
    results: list[TestResult],
    extra_footer: str | None = None,
) -> None:
    console = Console()
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    console.print()
    console.print(
        Panel(
            f"[bold]mailagent test {mode}[/bold] — {total} tests, inbox: {inbox}",
            style="cyan",
        )
    )
    console.print()

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("mark", width=2)
    table.add_column("name")

    for result in results:
        mark = "[green]✓[/]" if result.passed else "[red]✗[/]"
        table.add_row(mark, result.name)
        for line in result.details:
            table.add_row("", f"[dim]{line}[/dim]")

        if result.sub_results:
            for i, sub in enumerate(result.sub_results, 1):
                sub_mark = "[green]✓[/]" if sub.passed else "[red]✗[/]"
                detail = sub.details[0] if sub.details else ""
                table.add_row("", f"  #{i} {detail} {sub_mark}")

        table.add_row("", "")

    console.print(table)

    style = "green" if failed == 0 else "red"
    console.print(Rule(style=style))
    console.print(
        f"[bold {style}]Results: {passed} passed, {failed} failed[/]"
    )
    if extra_footer:
        console.print(f"[dim]{extra_footer}[/dim]")
    console.print(Rule(style=style))
