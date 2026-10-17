#!/usr/bin/env python3
"""
Aftermath Master Interactive Demo Suite
Unified launcher for all three Aftermath demo scenarios.

Usage:
    python demo.py [--demo 1|2|3|all] [--model mock-buggy|mock-fixed|gemma4|mistral] [--backend local|e2b] [--non-interactive]
"""

import sys
import argparse
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console(legacy_windows=False)

DEMOS = {
    "1": {
        "title": "Configuration & Security Invariant Protection",
        "script": "demo_config_invariants.py",
        "aspect": "JSON State Preservation & Silent Key Deletion Detection",
        "default_backend": "local"
    },
    "2": {
        "title": "E2B Firecracker Cloud Micro-VM & Live Pytest Execution",
        "script": "demo_e2b_cloud_sandbox.py",
        "aspect": "Hardware-Isolated Micro-VMs & Live Test Suite Invariants",
        "default_backend": "e2b"
    },
    "3": {
        "title": "Code Refactoring, Function Contracts & AST Syntax Analysis",
        "script": "demo_code_refactor_ast.py",
        "aspect": "AST Parse Tree Integrity, Public Signatures & Error Contracts",
        "default_backend": "local"
    }
}

def run_script(script_name: str, model: str, backend: str, non_interactive: bool):
    cmd = [sys.executable, script_name, "--model", model, "--backend", backend]
    if non_interactive:
        cmd.append("--non-interactive")
    subprocess.run(cmd)

def main():
    parser = argparse.ArgumentParser(description="Aftermath Master Interactive Demo Launcher")
    parser.add_argument("--demo", "-d", choices=["1", "2", "3", "all"], help="Specific demo number to run")
    parser.add_argument("--model", "-m", default="mock-buggy", help="Model to evaluate (mock-buggy, mock-fixed, gemma4, mistral)")
    parser.add_argument("--backend", "-b", choices=["local", "e2b"], help="Override default sandbox backend")
    parser.add_argument("--non-interactive", "-y", action="store_true", help="Run without pausing for input")
    args = parser.parse_args()

    console.clear()
    console.print(Panel.fit(
        "[bold white]AFTERMATH DEMO SUITE[/bold white]\n"
        "[italic dim]An Open-Source Regression Testing Harness for AI Agents[/italic dim]",
        border_style="cyan"
    ))

    choice = args.demo
    if not choice:
        console.print("[bold]Select an interactive demo to run:[/bold]\n")
        for key, info in DEMOS.items():
            console.print(f"  [bold cyan][{key}][/bold cyan] [bold]{info['title']}[/bold]")
            console.print(f"      [dim]Aspect: {info['aspect']}[/dim]")
        console.print(f"  [bold cyan][all][/bold cyan] [bold]Run all 3 demos sequentially[/bold]")
        console.print(f"  [bold cyan][q][/bold cyan]   [dim]Quit[/dim]\n")

        try:
            choice = Prompt.ask("Choose a demo", choices=["1", "2", "3", "all", "q"], default="1")
        except (KeyboardInterrupt, EOFError):
            console.print("\nExiting.")
            sys.exit(0)

    if choice == "q":
        console.print("Goodbye!")
        sys.exit(0)

    demos_to_run = ["1", "2", "3"] if choice == "all" else [choice]

    for d in demos_to_run:
        demo_info = DEMOS[d]
        backend = args.backend or demo_info["default_backend"]
        run_script(demo_info["script"], args.model, backend, args.non_interactive)

    console.print(Panel(
        "[bold green]DEMO SUITE FINISHED[/bold green]\n\n"
        "Three distinct reliability dimensions demonstrated:\n"
        "  • Config State & Security Invariants\n"
        "  • Remote Linux Micro-VM Execution (E2B) & Live Pytest Verification\n"
        "  • Source Code AST Syntax & Function Contract Preservation\n\n"
        "Web Dashboard Live: [cyan]https://aftermath-1494.onrender.com[/cyan] (or [cyan]http://localhost:8000[/cyan])",
        title="[bold]Summary[/bold]",
        border_style="green"
    ))

if __name__ == "__main__":
    main()
