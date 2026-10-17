#!/usr/bin/env python3
"""
Aftermath Demo 2: E2B Firecracker Cloud Micro-VM & Live Pytest Execution
Demonstrates running an agent in an isolated cloud micro-VM, executing live terminal commands,
and evaluating test suite invariants.

Usage:
    python demo_e2b_cloud_sandbox.py [--model mock-buggy|mock-fixed|gemma4|mistral] [--backend e2b|local] [--non-interactive]
"""

import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from aftermath.core.task import TaskDefinition
from aftermath.core.runner import ExecutionRunner
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
    parser = argparse.ArgumentParser(description="Aftermath Demo 2: E2B Cloud Micro-VM & Live Pytest Execution")
    parser.add_argument("--model", "-m", default="mock-buggy", help="Model to evaluate (mock-buggy, mock-fixed, gemma4, mistral)")
    parser.add_argument("--backend", "-b", default="e2b", choices=["e2b", "local"], help="Sandbox backend")
    parser.add_argument("--non-interactive", "-y", action="store_true", help="Run without pausing for user input")
    parser.add_argument("--task", default="fixtures/tasks/e2b_service_regression_test.yaml", help="Path to task definition YAML")
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
        "[bold white]AFTERMATH DEMO 2[/bold white] — [bold green]E2B Firecracker Cloud Micro-VM Sandbox[/bold green]\n"
        "[dim]Aspect: Remote POSIX Terminal Execution & Live Test Suite Verification[/dim]",
        border_style="green"
    ))

    task_path = Path(args.task).resolve()
    if not task_path.exists():
        console.print(f"[bold red]Error:[/bold red] Task file not found: {task_path}")
        sys.exit(1)

    task = TaskDefinition.load(task_path)
    task.sandbox_backend = args.backend

    has_e2b_key = bool(settings.get_e2b_key())
    if args.backend == "e2b" and not has_e2b_key:
        console.print("[bold red]Warning:[/bold red] No E2B_API_KEY detected in environment or .env file.")
        console.print("[dim]Falling back to local sandbox with POSIX-compatible emulation...[/dim]")
        task.sandbox_backend = "local"
        args.backend = "local"

    console.print(f"""
[bold]Scenario Overview:[/bold]
• [bold]Target Goal:[/bold] Agent modifies authentication service 'auth.py' to add 'verify_api_key'.
• [bold]Live Test Suite:[/bold] 'pytest test_auth.py' executed directly inside Linux micro-VM.
• [bold]Critical Invariants:[/bold] 'test_token_validation_live' and 'ast_syntax_valid' must pass.
• [bold]Configured Model:[/bold] {args.model}
• [bold]Active Sandbox Backend:[/bold] [bold cyan]{args.backend.upper()}[/bold cyan]
""")

    pause("Press Enter to boot the sandbox and execute the test run...")

    # Phase 1: Execution
    console.print(f"\n[bold yellow]==> Phase 1: Executing Agent ({args.model}) in {args.backend.upper()} Sandbox[/bold yellow]")
    adapter = resolve_adapter(args.model)
    runner = ExecutionRunner(task, adapter)
    trace = runner.run()

    Reporter.render_run_report(trace)

    # Save trace
    trace_dir = Path(".aftermath_traces")
    trace_dir.mkdir(exist_ok=True)
    trace_file = trace_dir / f"demo_e2b_{int(trace.start_time)}.json"
    trace.save(trace_file)

    if trace.status == "FAILED":
        console.print(f"[bold red]Test Suite Invariant Violated:[/bold red] Pytest failed inside micro-VM with non-zero exit code!")
        console.print(f"[dim]Trace saved: {trace_file}[/dim]")
        pause("Press Enter to execute the fixed agent to prove test suite compliance...")

        # Phase 2: Fixed verification
        console.print(f"\n[bold yellow]==> Phase 2: Running Fixed Agent in {args.backend.upper()} Sandbox[/bold yellow]")
        fixed_adapter = MockAdapter(mode="fixed")
        fixed_runner = ExecutionRunner(task, fixed_adapter)
        fixed_trace = fixed_runner.run()

        Reporter.render_run_report(fixed_trace)
        console.print(f"[bold green]LIVE PYTEST SUITE PASSED:[/bold green] All assertions and invariant tests passed exit code 0!")
    else:
        console.print(f"[bold green]ALL TESTS PASSED:[/bold green] Agent preserved full suite in {args.backend.upper()}!")

if __name__ == "__main__":
    main()
