import pytest
from pathlib import Path
from aftermath.core.task import TaskDefinition
from aftermath.core.runner import ExecutionRunner
from aftermath.adapters.mock import MockAdapter

def test_runner_catches_buggy_agent_failure():
    task_path = Path("fixtures/tasks/config_update_invariant.yaml")
    task = TaskDefinition.load(task_path)

    # Buggy agent deletes invariants
    adapter = MockAdapter(mode="buggy")
    runner = ExecutionRunner(task, adapter)
    trace = runner.run()

    assert trace.status == "FAILED"
    assert len(trace.steps) == 3
    # Check that invariant violation was recorded
    failed_invs = [inv for inv in trace.invariant_results if not inv["passed"]]
    assert len(failed_invs) >= 1
    assert "server.port" in str(failed_invs)

def test_runner_passes_with_fixed_agent():
    task_path = Path("fixtures/tasks/config_update_invariant.yaml")
    task = TaskDefinition.load(task_path)

    # Fixed agent edits only database.url, preserving invariants
    adapter = MockAdapter(mode="fixed")
    runner = ExecutionRunner(task, adapter)
    trace = runner.run()

    assert trace.status == "PASSED"
    failed_invs = [inv for inv in trace.invariant_results if not inv["passed"]]
    assert len(failed_invs) == 0

