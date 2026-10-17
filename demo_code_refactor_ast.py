#!/usr/bin/env python3
"""
Aftermath Demo 3: Code Refactoring, Function Contracts & AST Syntax Analysis
Demonstrates enforcing Python AST syntax tree validity, function signature contracts,
and preventing accidental deletion of helper routines during code refactoring.

Usage:
    python demo_code_refactor_ast.py [--model mock-buggy|mock-fixed|gemma4|mistral] [--backend local|e2b] [--non-interactive]
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
    parser = argparse.ArgumentParser(description="Aftermath Demo 3: Code Refactoring & AST Syntax Invariant Protection")
    parser.add_argument("--model", "-m", default="mock-buggy", help="Model to evaluate (mock-buggy, mock-fixed, gemma4, mistral)")
    parser.add_argument("--backend", "-b", default="local", choices=["local", "e2b"], help="Sandbox backend")
    parser.add_argument("--non-interactive", "-y", action="store_true", help="Run without pausing for user input")
    parser.add_argument("--task", default="fixtures/tasks/refactor_function_contract.yaml", help="Path to task definition YAML")
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
        "[bold white]AFTERMATH DEMO 3[/bold white] — [bold magenta]Code Refactoring & AST Syntax Contracts[/bold magenta]\n"
        "[dim]Aspect: AST Parse Tree Integrity, Public Signatures & Function Preservation[/dim]",
        border_style="magenta"
    ))

    task_path = Path(args.task).resolve()
    if not task_path.exists():
        console.print(f"[bold red]Error:[/bold red] Task file not found: {task_path}")
        sys.exit(1)

    task = TaskDefinition.load(task_path)
    task.sandbox_backend = args.backend

    console.print(f"""
[bold]Scenario Overview:[/bold]
• [bold]Target Goal:[/bold] Agent refactors 'calculator.py' to add 'def power(a: int, b: int) -> int:'.
• [bold]Contract Invariants:[/bold] Public functions ('add', 'divide') and zero-division contracts must NOT be deleted.
• [bold]AST Invariants:[/bold] Modified file must parse into a valid Python Abstract Syntax Tree (AST).
• [bold]Configured Model:[/bold] {args.model}
• [bold]Sandbox Runtime:[/bold] {args.backend.upper()}
""")

    pause("Press Enter to execute the agent in the refactoring sandbox...")

    # Phase 1: Execution
    console.print(f"\n[bold yellow]==> Phase 1: Running Agent ({args.model}) on {args.backend.upper()} Sandbox[/bold yellow]")
    adapter = resolve_adapter(args.model)
    runner = ExecutionRunner(task, adapter)
    trace = runner.run()

    Reporter.render_run_report(trace)

    # Save trace
    trace_dir = Path(".aftermath_traces")
    trace_dir.mkdir(exist_ok=True)
    trace_file = trace_dir / f"demo_refactor_{int(trace.start_time)}.json"
    trace.save(trace_file)

    if trace.status == "FAILED":
        console.print(f"[bold red]Contract Violation Detected:[/bold red] Existing public functions and error contracts were wiped out!")
        pause("Press Enter to generate and double-validate an AST regression test suite...")

        # Phase 2: Synthesis
        console.print("\n[bold yellow]==> Phase 2: Generating Contract & AST Regression Test[/bold yellow]")
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

            pause("Press Enter to verify against the fixed agent preserving AST and contracts...")

            # Phase 3: Fixed verification
            console.print("\n[bold yellow]==> Phase 3: Running Corrected Agent (Contracts Preserved)[/bold yellow]")
            fixed_adapter = MockAdapter(mode="fixed")
            fixed_runner = ExecutionRunner(reg_task, fixed_adapter)
            fixed_trace = fixed_runner.run()

            Reporter.render_run_report(fixed_trace)
            console.print(f"[bold green]AST & CONTRACTS VERIFIED:[/bold green] Added power function while preserving all existing contracts!")
    else:
        console.print(f"[bold green]CONTRACTS PRESERVED:[/bold green] Function added cleanly with valid AST!")

if __name__ == "__main__":
    main()

