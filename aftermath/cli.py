import typer
from pathlib import Path
from typing import Optional, List
import json
import uvicorn
import sys
from rich.console import Console

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from aftermath.core.task import TaskDefinition
from aftermath.core.runner import ExecutionRunner
from aftermath.core.trace import RunTrace
from aftermath.core.reporter import Reporter
from aftermath.core.generator import RegressionTestGenerator
from aftermath.adapters.mock import MockAdapter
from aftermath.adapters.gemma import GemmaAdapter
from aftermath.adapters.mistral import MistralAdapter
from aftermath.config import settings

app = typer.Typer(
    name="aftermath",
    help="Aftermath: An open-source regression testing harness for AI agents."
)
console = Console(legacy_windows=False)

def _resolve_adapter(model_name: str, provider: Optional[str] = None):
    m = model_name.lower()
    if m.startswith("mock"):
        mode = "buggy" if "buggy" in m else "fixed"
        return MockAdapter(mode=mode)
    elif "mistral" in m:
        return MistralAdapter()
    elif "gemma" in m or "gemini" in m:
        pref = provider or ("google" if settings.get_google_key() else "ollama")
        return GemmaAdapter(primary_provider=pref)
    else:
        # Default fallback to mock
        return MockAdapter(mode="fixed")

@app.command()
def run(
    task_file: str = typer.Argument(..., help="Path to task YAML/JSON definition file"),
    model: str = typer.Option("mock-buggy", "--model", "-m", help="Model to test (gemma4, mistral, mock-buggy, mock-fixed)"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider for model (google, ollama, mistral)"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b", help="Sandbox backend: local or e2b"),
    save_trace: Optional[str] = typer.Option(None, "--save-trace", "-s", help="Path to save execution trace JSON"),
):
    """Execute an agent against a task and detect any regression or invariant violation."""
    task_p = Path(task_file).resolve()
    if not task_p.exists():
        console.print(f"[bold red]Error:[/bold red] Task file not found: {task_p}")
        raise typer.Exit(code=1)

    task = TaskDefinition.load(task_p)
    if backend:
        task.sandbox_backend = backend.lower() # type: ignore

    adapter = _resolve_adapter(model, provider)

    console.print(f"[bold cyan]Aftermath:[/bold cyan] Running task '{task.name}' with model '{adapter.name}' on [bold green]{task.sandbox_backend.upper()}[/bold green] sandbox...")
    runner = ExecutionRunner(task, adapter)
    trace = runner.run()

    # Save trace if requested or default to .aftermath_traces/
    trace_dir = Path(".aftermath_traces")
    trace_dir.mkdir(exist_ok=True)
    out_path = Path(save_trace) if save_trace else trace_dir / f"trace_{trace.task_id}_{int(trace.start_time)}.json"
    trace.save(out_path)
    console.print(f"[dim]Saved trace to: {out_path}[/dim]")

    # Render report
    Reporter.render_run_report(trace)

    if trace.status != "PASSED":
        raise typer.Exit(code=1)

@app.command()
def compare(
    task_file: str = typer.Argument(..., help="Path to task YAML/JSON file"),
    models: str = typer.Option("gemma4,mistral", "--models", "-m", help="Comma-separated list of models to compare"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b", help="Sandbox backend: local or e2b"),
):
    """Run the same task across multiple models and compare traces and invariants."""
    task_p = Path(task_file).resolve()
    if not task_p.exists():
        console.print(f"[bold red]Error:[/bold red] Task file not found: {task_p}")
        raise typer.Exit(code=1)

    task = TaskDefinition.load(task_p)
    if backend:
        task.sandbox_backend = backend.lower() # type: ignore

    model_list = [m.strip() for m in models.split(",") if m.strip()]

    traces = []
    for m in model_list:
        adapter = _resolve_adapter(m)
        console.print(f"[cyan]Running test against:[/cyan] [bold]{adapter.name}[/bold] ({adapter.provider}) on {task.sandbox_backend.upper()}...")
        runner = ExecutionRunner(task, adapter)
        trace = runner.run()
        traces.append(trace)

    Reporter.render_comparison_report(traces)

@app.command()
def reproduce(
    trace_file: str = typer.Argument(..., help="Path to saved RunTrace JSON"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override model for reproduction run"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b", help="Sandbox backend override: local or e2b"),
):
    """Reproduce a failure from a saved run trace."""
    tp = Path(trace_file).resolve()
    if not tp.exists():
        console.print(f"[bold red]Error:[/bold red] Trace file not found: {tp}")
        raise typer.Exit(code=1)

    trace = RunTrace.load(tp)
    console.print(f"[bold yellow]Reproducing run:[/bold yellow] Task '{trace.task_name}' (Original status: {trace.status})")

    # Use original model or override
    target_model = model or trace.model_name
    adapter = _resolve_adapter(target_model, trace.provider)

    from aftermath.core.task import ExpectedOutcomes, AssertionSpec
    outcomes = ExpectedOutcomes(
        assertions=[AssertionSpec(**a["spec"]) for a in trace.assertion_results],
        invariants=[AssertionSpec(**inv["spec"]) for inv in trace.invariant_results]
    )

    # Reconstruct fixture workspace from snapshot
    repro_dir = Path(".aftermath_repro") / f"repro_{trace.task_id}_{int(trace.start_time)}"
    repro_dir.mkdir(parents=True, exist_ok=True)
    for rel_path, content in trace.initial_snapshot.items():
        dest = repro_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    chosen_backend = (backend or "local").lower()

    # Reconstruct task definition
    task = TaskDefinition(
        id=f"repro_{trace.task_id}",
        name=f"Reproduction of {trace.task_name}",
        instruction=trace.instruction,
        workspace_fixture=str(repro_dir),
        sandbox_backend=chosen_backend, # type: ignore
        expected_outcomes=outcomes
    )

    runner = ExecutionRunner(task, adapter)
    repro_trace = runner.run()
    Reporter.render_run_report(repro_trace)

    if repro_trace.status == trace.status:
        console.print(f"[bold green]Reproduction Verified:[/bold green] Re-execution faithfully reproduced original '{trace.status}' state.")
    else:
        console.print(f"[bold yellow]Divergence Observed:[/bold yellow] Original status was '{trace.status}', re-execution produced '{repro_trace.status}'.")

    if repro_trace.status != "PASSED":
        raise typer.Exit(code=1)

@app.command()
def generate_test(
    trace_file: str = typer.Argument(..., help="Path to failure trace JSON"),
    output_dir: str = typer.Option("aftermath/generated_tests", "--output-dir", "-o", help="Directory to save generated tests"),
):
    """Generate and validate a permanent regression test from a failure trace."""
    tp = Path(trace_file).resolve()
    if not tp.exists():
        console.print(f"[bold red]Error:[/bold red] Trace file not found: {tp}")
        raise typer.Exit(code=1)

    trace = RunTrace.load(tp)
    generator = RegressionTestGenerator(output_dir=output_dir)
    reg_task, validated, message = generator.generate(trace)

    if validated:
        console.print(f"[bold green]SUCCESS:[/bold green] {message}")
        console.print(f"[dim]Generated test ID: {reg_task.id}[/dim]")
    else:
        console.print(f"[bold red]VALIDATION FAILED:[/bold red] {message}")
        raise typer.Exit(code=1)

@app.command()
def ui(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="UI server host"),
    port: int = typer.Option(8000, "--port", "-p", help="UI server port"),
):
    """Launch the interactive Aftermath Web Dashboard (taste & impeccable style)."""
    console.print(f"[bold cyan]Launching Aftermath Dashboard on http://{host}:{port}...[/bold cyan]")
    uvicorn.run("aftermath.ui.server:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    app()

