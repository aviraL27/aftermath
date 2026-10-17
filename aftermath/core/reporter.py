from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from aftermath.core.trace import RunTrace

console = Console(legacy_windows=False)

class Reporter:
    """Produces clean CLI reports, comparisons, and exports."""

    @staticmethod
    def render_run_report(trace: RunTrace) -> None:
        console.print()
        status_color = "green" if trace.status == "PASSED" else "red"
        
        # Header Panel
        header = Text()
        header.append(f"Task: {trace.task_name} ", style="bold white")
        header.append(f"[{trace.status}]", style=f"bold {status_color}")
        header.append(f"\nModel: {trace.model_name} ({trace.provider}) | Duration: {trace.duration_seconds:.2f}s", style="dim")
        header.append(f"\nInstruction: {trace.instruction}", style="italic white")
        
        console.print(Panel(header, title="[bold]Aftermath Test Run Summary[/bold]", border_style=status_color))

        # Steps Table
        if trace.steps:
            table = Table(title="Execution Trace", show_header=True, header_style="bold cyan")
            table.add_column("Step", width=6, justify="center")
            table.add_column("Thought", style="italic")
            table.add_column("Tool", style="bold yellow")
            table.add_column("Arguments", style="dim")
            table.add_column("Output Preview")

            for s in trace.steps:
                tool_display = s.tool_name or "[dim]None[/dim]"
                args_display = str(s.tool_args) if s.tool_args else ""
                out_display = (s.tool_output or "")[:60].replace("\n", " ")
                thought_display = (s.agent_thought or "")[:50]
                table.add_row(str(s.step_number), thought_display, tool_display, args_display, out_display)
            console.print(table)

        # Assertions & Invariants Table
        eval_table = Table(title="Evaluation & Invariants", show_header=True, header_style="bold magenta")
        eval_table.add_column("Type", width=12)
        eval_table.add_column("Path / Key", width=26)
        eval_table.add_column("Status", width=10, justify="center")
        eval_table.add_column("Expected", style="dim")
        eval_table.add_column("Actual / Details")

        for a in trace.assertion_results:
            spec = a.get("spec", {})
            passed = a.get("passed", False)
            st_text = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            loc = spec.get("key_path") or spec.get("path") or ""
            eval_table.add_row(
                "Assertion",
                loc,
                st_text,
                str(a.get("expected_value")),
                str(a.get("actual_value")) if passed else f"[red]{a.get('error_message')}[/red]"
            )

        for inv in trace.invariant_results:
            spec = inv.get("spec", {})
            passed = inv.get("passed", False)
            st_text = "[green]PASS[/green]" if passed else "[bold red]VIOLATED[/bold red]"
            loc = spec.get("key_path") or spec.get("path") or ""
            eval_table.add_row(
                "[yellow]Invariant[/yellow]",
                loc,
                st_text,
                str(inv.get("expected_value")),
                str(inv.get("actual_value")) if passed else f"[red]{inv.get('error_message')}[/red]"
            )

        console.print(eval_table)

        # Workspace Diff
        if trace.workspace_diff:
            console.print(Panel(
                Syntax(trace.workspace_diff, "diff", theme="monokai", line_numbers=True),
                title="[bold]Workspace Changes (Unified Diff)[/bold]",
                border_style="yellow"
            ))
        console.print()

    @staticmethod
    def render_comparison_report(traces: List[RunTrace]) -> None:
        console.print()
        table = Table(title="Model Comparison Matrix", show_header=True, header_style="bold white on blue")
        table.add_column("Model", style="bold")
        table.add_column("Provider")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Steps", justify="center")
        table.add_column("Failed Invariants")
        table.add_column("Workspace Diff Lines", justify="right")

        for t in traces:
            status_style = "[green]PASSED[/green]" if t.status == "PASSED" else "[bold red]FAILED[/bold red]"
            failed_invs = [
                inv.get("spec", {}).get("key_path") or inv.get("spec", {}).get("path")
                for inv in t.invariant_results if not inv.get("passed", False)
            ]
            inv_str = ", ".join(filter(None, failed_invs)) or "[green]None[/green]"
            diff_lines = len(t.workspace_diff.splitlines()) if t.workspace_diff else 0

            table.add_row(
                t.model_name,
                t.provider,
                status_style,
                f"{t.duration_seconds:.2f}s",
                str(len(t.steps)),
                inv_str,
                str(diff_lines)
            )

        console.print(table)
        console.print()

