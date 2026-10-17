import pytest
from pathlib import Path
from aftermath.core.task import TaskDefinition
from aftermath.core.runner import ExecutionRunner
from aftermath.core.generator import RegressionTestGenerator
from aftermath.adapters.mock import MockAdapter

def test_regression_test_generation_and_validation(tmp_path):
    task_path = Path("fixtures/tasks/config_update_invariant.yaml")
    task = TaskDefinition.load(task_path)

    # 1. Run buggy agent to produce failure trace
    runner = ExecutionRunner(task, MockAdapter(mode="buggy"))
    trace = runner.run()
    assert trace.status == "FAILED"

    # 2. Generate regression test
    generator = RegressionTestGenerator(output_dir=tmp_path)
    reg_task, validated, message = generator.generate(trace, task_def=task)

    assert validated is True
    assert reg_task.is_regression_test is True
    assert reg_task.validated is True
    assert (tmp_path / f"{reg_task.id}.yaml").exists()

    # 3. Rerun generated regression test with buggy agent -> MUST FAIL
    runner_reg_buggy = ExecutionRunner(reg_task, MockAdapter(mode="buggy"))
    trace_reg_buggy = runner_reg_buggy.run()
    assert trace_reg_buggy.status == "FAILED"

    # 4. Rerun generated regression test with fixed agent -> MUST PASS
    runner_reg_fixed = ExecutionRunner(reg_task, MockAdapter(mode="fixed"))
    trace_reg_fixed = runner_reg_fixed.run()
    assert trace_reg_fixed.status == "PASSED"

