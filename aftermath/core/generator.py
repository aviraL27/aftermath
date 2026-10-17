from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import json
from aftermath.core.task import TaskDefinition, ExpectedOutcomes, AssertionSpec
from aftermath.core.trace import RunTrace
from aftermath.core.sandbox import Sandbox
from aftermath.core.assertions import evaluate_task, EvaluationSummary

class RegressionTestGenerator:
    """
    Generates reusable regression tests from recorded failure traces.
    Strictly validates generated tests against failing and known-correct cases.
    """
    def __init__(self, output_dir: str | Path = "aftermath/generated_tests"):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, trace: RunTrace, task_def: Optional[TaskDefinition] = None) -> Tuple[TaskDefinition, bool, str]:
        """
        Generate and validate regression test from failure trace.
        Returns: (Generated TaskDefinition, is_validated, status_message)
        """
        if trace.status != "FAILED":
            return None, False, f"Cannot generate regression test: trace status is '{trace.status}', not 'FAILED'."

        failed_invariants = [
            inv for inv in trace.invariant_results if not inv.get("passed", False)
        ]
        failed_assertions = [
            a for a in trace.assertion_results if not a.get("passed", False)
        ]

        if not failed_invariants and not failed_assertions:
            return None, False, "No explicit failure found in trace assertion/invariant results."

        # Prepare regression fixture directory
        regression_id = f"regression_{trace.task_id}_{int(trace.start_time)}"
        fixture_dir = self.output_dir / "fixtures" / regression_id
        fixture_dir.mkdir(parents=True, exist_ok=True)

        # Write initial snapshot files to fixture dir
        for rel_path, content in trace.initial_snapshot.items():
            dest = fixture_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

        # Synthesize expected outcomes
        outcomes = ExpectedOutcomes()

        if task_def:
            outcomes.assertions = list(task_def.expected_outcomes.assertions)
            outcomes.invariants = list(task_def.expected_outcomes.invariants)
        else:
            # Reconstruct from trace
            for a_data in trace.assertion_results:
                outcomes.assertions.append(AssertionSpec(**a_data["spec"]))
            for inv_data in trace.invariant_results:
                outcomes.invariants.append(AssertionSpec(**inv_data["spec"]))

        # Build regression task definition
        reg_task = TaskDefinition(
            id=regression_id,
            name=f"Regression: {trace.task_name}",
            description=f"Auto-generated regression test for failure in {trace.task_id}. Ensures invariants are preserved.",
            instruction=trace.instruction,
            workspace_fixture=str(fixture_dir),
            tools=["read_file", "write_file", "edit_file", "list_files"],
            max_steps=10,
            expected_outcomes=outcomes,
            is_regression_test=True,
            generated_from_trace=trace.task_id,
            validated=False
        )

        # --- VALIDATION STAGE ---
        # 1. Negative Validation: Test MUST fail against the recorded failing state
        with Sandbox(base_dir=None) as sb_fail:
            # Seed with failing snapshot
            for rel_path, content in trace.final_snapshot.items():
                sb_fail.write_file(rel_path, content)
            
            eval_fail: EvaluationSummary = evaluate_task(sb_fail, reg_task.expected_outcomes)
            if eval_fail.all_passed:
                return (
                    reg_task,
                    False,
                    "Validation failed: generated test unexpectedly PASSED on the failing agent snapshot."
                )

        # 2. Positive Validation: Test MUST pass on a ground-truth correct state
        # Create a reference workspace by taking initial state and applying expected assertions
        with Sandbox(fixture_path=fixture_dir) as sb_correct:
            # For JSON key invariants, verify they exist in initial state
            # and verify assertions pass when correct changes are made
            for a in reg_task.expected_outcomes.assertions:
                if a.type == "json_value_equals" and sb_correct.file_exists(a.path):
                    try:
                        data = json.loads(sb_correct.read_file(a.path))
                        # Set key path
                        parts = a.key_path.split(".")
                        curr = data
                        for p in parts[:-1]:
                            curr = curr.setdefault(p, {})
                        curr[parts[-1]] = a.expected
                        sb_correct.write_file(a.path, json.dumps(data, indent=2))
                    except Exception:
                        pass
                elif a.type == "file_exact":
                    sb_correct.write_file(a.path, str(a.expected))

            eval_correct: EvaluationSummary = evaluate_task(sb_correct, reg_task.expected_outcomes)
            if not eval_correct.all_passed:
                failures = [f.error_message for f in eval_correct.failed_assertions + eval_correct.failed_invariants]
                return (
                    reg_task,
                    False,
                    f"Validation failed: generated test FAILED on known-correct state: {failures}"
                )

        # Both validations passed!
        reg_task.validated = True
        save_path = self.output_dir / f"{regression_id}.yaml"
        reg_task.save_yaml(save_path)

        return (
            reg_task,
            True,
            f"Regression test successfully generated, validated, and saved to {save_path}"
        )

