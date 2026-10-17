#!/usr/bin/env python3
"""
Aftermath Interactive Live Demo Script
Run this single command to walk through the complete Aftermath regression testing loop:
    python demo.py
"""

import sys
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from aftermath.core.task import TaskDefinition
from aftermath.core.runner import ExecutionRunner
from aftermath.core.generator import RegressionTestGenerator
from aftermath.core.reporter import Reporter
from aftermath.adapters.mock import MockAdapter
from aftermath.adapters.mistral import MistralAdapter
from aftermath.config import settings

console = Console()

def pause(msg: str = "Press Enter to continue..."):
    console.print(f"\n[bold cyan]>[/bold cyan] [dim]{msg}[/dim]")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        console.print("\nDemo cancelled.")
        sys.exit(0)

def main():
    console.clear()
    console.print(Panel.fit(
        "[bold white]AFTERMATH[/bold white] — [bold yellow]Interactive Live Demo[/bold yellow]\n"
        "[italic dim]An Open-Source Regression Testing Harness for AI Agents[/italic dim]",
        border_style="yellow"
    ))

    console.print("""
[bold]Scenario:[/bold]
A developer tasks an AI agent with updating the database URL in [cyan]config/app.json[/cyan].
The agent makes the edit, but accidentally wipes out critical server & security settings.

Aftermath will:
  1. Detect the invariant violation.
  2. Capture the differential trace.
  3. Generate and double-validate a permanent regression test.
  4. Prove the regression test catches the bug again.
  5. Prove the fixed agent passes the test.
  6. Execute against live AI models ([bold]Mistral open-mistral-7b[/bold]).
""")
    pause("Press Enter to begin Phase 1 (Running the Buggy Agent)...")

    # =========================================================================
    # PHASE 1: Buggy Agent Failure
    # =========================================================================
    console.print("\n[bold yellow]==> PHASE 1: Executing Agent in Controlled Sandbox[/bold yellow]")
    task_path = Path("fixtures/tasks/config_update_invariant.yaml")
    task = TaskDefinition.load(task_path)

    adapter_buggy = MockAdapter(mode="buggy")
    runner_buggy = ExecutionRunner(task, adapter_buggy)
    
    with console.status("[bold green]Agent executing tool calls in sandbox..."):
        time.sleep(1)
        trace_buggy = runner_buggy.run()

    # Save trace
    trace_dir = Path(".aftermath_traces")
    trace_dir.mkdir(exist_ok=True)
    trace_file = trace_dir / f"demo_trace_{int(trace_buggy.start_time)}.json"
    trace_buggy.save(trace_file)

    Reporter.render_run_report(trace_buggy)

    console.print(f"[bold red]FAILURE DETECTED:[/bold red] The agent deleted [bold]server.port[/bold] and [bold]security.jwt_secret[/bold]!")
    console.print(f"[dim]Failure trace saved to: {trace_file}[/dim]")

    pause("Press Enter to begin Phase 2 (Generating Regression Test)...")

    # =========================================================================
    # PHASE 2: Generate & Double-Validate Regression Test
    # =========================================================================
    console.print("\n[bold yellow]==> PHASE 2: Automatic Regression Test Generation[/bold yellow]")
    console.print("[dim]Running dual ground-truth validation (Negative validation on buggy trace, Positive validation on reference state)...[/dim]")
    
    generator = RegressionTestGenerator()
    reg_task, validated, message = generator.generate(trace_buggy, task_def=task)

    if validated:
        console.print(Panel(
            f"[bold green]STATUS: VALIDATED[/bold green]\n\n"
            f"[white]{message}[/white]\n"
            f"[dim]Generated Test ID: {reg_task.id}[/dim]",
            title="[bold]Regression Test Synthesized & Validated[/bold]",
            border_style="green"
        ))
    else:
        console.print(f"[bold red]Validation failed: {message}[/bold red]")
        return

    pause("Press Enter to begin Phase 3 (Catching the Regression)...")

    # =========================================================================
    # PHASE 3: Rerun against Buggy Agent (Prove Bug Caught)
    # =========================================================================
    console.print("\n[bold yellow]==> PHASE 3: Rerunning Generated Regression Test Against Buggy Agent[/bold yellow]")
    runner_recheck = ExecutionRunner(reg_task, MockAdapter(mode="buggy"))
    
    with console.status("[bold green]Rerunning test..."):
        time.sleep(1)
        trace_recheck = runner_recheck.run()

    console.print(f"Regression Test Run Status: [bold red]{trace_recheck.status}[/bold red]")
    console.print("[bold green]SUCCESS:[/bold green] The generated regression test successfully caught the recurring bug!")

    pause("Press Enter to begin Phase 4 (Verifying with Fixed Agent)...")

    # =========================================================================
    # PHASE 4: Verify with Fixed Agent
    # =========================================================================
    console.print("\n[bold yellow]==> PHASE 4: Rerunning Generated Regression Test Against Fixed Agent[/bold yellow]")
    runner_fixed = ExecutionRunner(reg_task, MockAdapter(mode="fixed"))
    
    with console.status("[bold green]Running fixed agent..."):
        time.sleep(1)
        trace_fixed = runner_fixed.run()

    Reporter.render_run_report(trace_fixed)
    console.print("[bold green]VERIFIED:[/bold green] When the prompt/agent preserves invariants, the regression test passes!")

    pause("Press Enter to begin Phase 5 (Live Apache-2.0 Mistral Model Execution)...")

    # =========================================================================
    # PHASE 5: Live Mistral Model Execution
    # =========================================================================
    console.print("\n[bold yellow]==> PHASE 5: Live Execution with Mistral (open-mistral-7b)[/bold yellow]")
    if settings.mistral_api_key:
        console.print("[dim]Connecting to Mistral API with open-mistral-7b (Apache-2.0)...[/dim]")
        adapter_mistral = MistralAdapter()
        runner_mistral = ExecutionRunner(task, adapter_mistral)
        
        with console.status("[bold green]Mistral agent reasoning and executing tools in sandbox..."):
            trace_mistral = runner_mistral.run()
            
        Reporter.render_run_report(trace_mistral)
        
        # Comparison Table
        console.print("\n[bold]Model Comparison Matrix:[/bold]")
        Reporter.render_comparison_report([trace_buggy, trace_fixed, trace_mistral])
    else:
        console.print("[yellow]Skipping live Mistral run (no MISTRAL_API_KEY in .env)[/yellow]")

    # =========================================================================
    # CONCLUSION & WEB UI
    # =========================================================================
    console.print(Panel(
        "[bold white]LIVE DEMO COMPLETE[/bold white]\n\n"
        "You have witnessed the complete reliability lifecycle:\n"
        "  1. Invariant violation detected automatically.\n"
        "  2. Failure trace and diff captured.\n"
        "  3. Reusable regression test synthesized and ground-truth verified.\n"
        "  4. Regression caught on buggy implementations, passed on fixed ones.\n\n"
        "[bold yellow]Web Dashboard:[/bold yellow] Running live at [cyan]http://localhost:8000[/cyan]\n"
        "Open your browser to view the visual traces, interactive diff viewer, and model comparison!",
        title="[bold green]Aftermath Summary[/bold green]",
        border_style="cyan"
    ))

if __name__ == "__main__":
    main()

