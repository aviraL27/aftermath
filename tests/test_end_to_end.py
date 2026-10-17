import pytest
from pathlib import Path
from aftermath.core.task import TaskDefinition
from aftermath.core.runner import ExecutionRunner
from aftermath.core.generator import RegressionTestGenerator
from aftermath.core.reporter import Reporter
from aftermath.adapters.mock import MockAdapter

def test_full_regression_lifecycle_milestone(tmp_path):
    """
    End-to-End Milestone:
    Demonstrates one agent failure being detected, reproduced from a saved fixture,
    converted into a regression test, and caught again during a later run.
    """
    # 1. Load original task with invariants
    task = TaskDefinition.load("fixtures/tasks/config_update_invariant.yaml")
    assert len(task.expected_outcomes.invariants) == 3

    # 2. Buggy agent executes and violates invariants
    runner_buggy = ExecutionRunner(task, MockAdapter(mode="buggy"))
    trace_buggy = runner_buggy.run()
    assert trace_buggy.status == "FAILED"

    # Save trace
    trace_path = tmp_path / "failure_trace.json"
    trace_buggy.save(trace_path)
    assert trace_path.exists()

    # 3. Generate regression test from the failure trace
    generator = RegressionTestGenerator(output_dir=tmp_path / "generated")
    reg_task, validated, message = generator.generate(trace_buggy, task_def=task)
    assert validated is True
    assert reg_task.validated is True

    # 4. Rerun against buggy agent (e.g. before fixing the agent) -> Regression test catches the bug!
    runner_recheck = ExecutionRunner(reg_task, MockAdapter(mode="buggy"))
    trace_recheck = runner_recheck.run()
    assert trace_recheck.status == "FAILED"

    # 5. Rerun against fixed agent (after fixing prompt/model) -> Regression test passes!
    runner_fixed = ExecutionRunner(reg_task, MockAdapter(mode="fixed"))
    trace_fixed = runner_fixed.run()
    assert trace_fixed.status == "PASSED"

    # 6. Verify reporter does not crash on either trace
    Reporter.render_run_report(trace_buggy)
    Reporter.render_comparison_report([trace_buggy, trace_fixed])

