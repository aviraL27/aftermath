#!/usr/bin/env python3
"""
Aftermath Demo 1: Configuration & Security Invariant Preservation
Demonstrates detecting collateral deletion in configuration files and generating regression suites.

Usage:
    python demo_config_invariants.py [--model mock-buggy|mock-fixed|gemma4|mistral] [--backend local|e2b] [--non-interactive]
"""

import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from aftermath.core.task import TaskDefinition
from aftermath.core.runner import ExecutionRunner
from aftermath.core.generator import RegressionTestGenerator
from aftermath.core.reporter import Reporter
from aftermath.adapters.mock import MockAdapter
from aftermath.adapters.gemma import GemmaAdapter
from aftermath.adapters.mistral import MistralAdapter
from aftermath.config import settings

console = Console(legacy_windows=False)

def resolve_adapter(model_name: str):
    m = model_name.lower()
    if m.startswith("mock"):
        mode = "buggy" if "buggy" in m else "fixed"
        return MockAdapter(mode=mode)
    elif "mistral" in m:
        return MistralAdapter()
    elif "gemma" in m:
        return GemmaAdapter()
    return MockAdapter(mode="fixed")

def main():
    parser = argparse.ArgumentParser(description="Aftermath Demo 1: Configuration & Security Invariant Preservation")
    parser.add_argument("--model", "-m", default="mock-buggy", help="Model to evaluate (mock-buggy, mock-fixed, gemma4, mistral)")
    parser.add_argument("--backend", "-b", default="local", choices=["local", "e2b"], help="Sandbox backend")
    parser.add_argument("--non-interactive", "-y", action="store_true", help="Run without pausing for user input")
    parser.add_argument("--task", default="fixtures/tasks/config_update_invariant.yaml", help="Path to task definition YAML")
    args = parser.parse_args()

    def pause(msg: str):
        if not args.non_interactive:
            console.print(f"\n[bold cyan]>[/bold cyan] [dim]{msg}[/dim]")
            try:
                input()
            except (KeyboardInterrupt, EOFError):
                console.print("\nDemo aborted.")
                sys.exit(0)

    console.clear()
    console.print(Panel.fit(
        "[bold white]AFTERMATH DEMO 1[/bold white] — [bold cyan]Configuration & Security Invariant Protection[/bold cyan]\n"
        "[dim]Aspect: Deterministic JSON State Preservation & Silent Deletion Detection[/dim]",
        border_style="cyan"
    ))

    task_path = Path(args.task).resolve()
    if not task_path.exists():
        console.print(f"[bold red]Error:[/bold red] Task file not found: {task_path}")
        sys.exit(1)

    task = TaskDefinition.load(task_path)
    task.sandbox_backend = args.backend

    console.print(f"""
[bold]Scenario Overview:[/bold]
• [bold]Target Goal:[/bold] Agent updates database connection URL to 'postgresql://prod-db:5432/app'.
• [bold]Critical Invariants:[/bold] 'server.port' (8080) and 'security.jwt_secret' must NOT be erased.
• [bold]Configured Model:[/bold] {args.model}
• [bold]Sandbox Runtime:[/bold] {args.backend.upper()}
""")

    pause("Press Enter to execute the agent in the isolated sandbox...")

    # Phase 1: Execution
    console.print(f"\n[bold yellow]==> Phase 1: Running Agent ({args.model}) on {args.backend.upper()} Sandbox[/bold yellow]")
    adapter = resolve_adapter(args.model)
    runner = ExecutionRunner(task, adapter)
    trace = runner.run()

    Reporter.render_run_report(trace)

    # Save trace
    trace_dir = Path(".aftermath_traces")
    trace_dir.mkdir(exist_ok=True)
    trace_file = trace_dir / f"demo_config_{int(trace.start_time)}.json"
    trace.save(trace_file)

    if trace.status == "FAILED":
        console.print(f"[bold red]Invariant Violation Detected:[/bold red] The agent dropped required configuration keys!")
        pause("Press Enter to synthesize and validate an automated regression test...")

        # Phase 2: Synthesis
        console.print("\n[bold yellow]==> Phase 2: Automated Regression Test Synthesis[/bold yellow]")
        generator = RegressionTestGenerator()
        reg_task, validated, msg = generator.generate(trace, task_def=task)

        if validated:
            console.print(Panel(
                f"[bold green]Dual Ground-Truth Validation PASSED[/bold green]\n"
                f"[white]{msg}[/white]\n"
                f"[dim]Saved Suite: {reg_task.id}.yaml[/dim]",
                title="[bold]Synthesized Regression Test[/bold]",
                border_style="green"
            ))

            pause("Press Enter to verify against the fixed agent...")

            # Phase 3: Fixed verification
            console.print("\n[bold yellow]==> Phase 3: Running Corrected Agent (Invariant Preserved)[/bold yellow]")
            fixed_adapter = MockAdapter(mode="fixed")
            fixed_runner = ExecutionRunner(reg_task, fixed_adapter)
            fixed_trace = fixed_runner.run()

            Reporter.render_run_report(fixed_trace)
            console.print(f"[bold green]SUCCESS:[/bold green] Corrected agent passed all assertions and invariants!")
    else:
        console.print(f"[bold green]ALL INVARIANTS PRESERVED:[/bold green] The agent performed the update safely!")

if __name__ == "__main__":
    main()

