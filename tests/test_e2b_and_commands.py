import pytest
from aftermath.core.sandbox import Sandbox
from aftermath.core.task import AssertionSpec, ExpectedOutcomes
from aftermath.core.assertions import evaluate_single_assertion, evaluate_task

def test_local_sandbox_command_execution():
    with Sandbox() as sb:
        sb.write_file("hello.txt", "world")
        res = sb.run_command("python -c \"print('Hello from command')\"")
        assert res["exit_code"] == 0
        assert "Hello from command" in res["stdout"]

def test_command_exit_code_and_stdout_assertions():
    with Sandbox() as sb:
        spec_exit = AssertionSpec(
            type="command_exit_code",
            command="python -c \"import sys; sys.exit(0)\"",
            expected=0
        )
        res_exit = evaluate_single_assertion(sb, spec_exit)
        assert res_exit.passed is True

        spec_stdout = AssertionSpec(
            type="command_stdout_contains",
            command="python -c \"print('E2B_AFTERMATH_TEST_123')\"",
            expected="AFTERMATH_TEST"
        )
        res_stdout = evaluate_single_assertion(sb, spec_stdout)
        assert res_stdout.passed is True

def test_sandbox_ignores_pycache_and_pyc():
    with Sandbox() as sb:
        sb.write_file("main.py", "print('ok')")
        sb.write_file("__pycache__/main.cpython-311.pyc", "binary_data")
        files = sb.list_files(".")
        assert "main.py" in files
        assert not any("__pycache__" in f for f in files)
        assert not any(f.endswith(".pyc") for f in files)

def test_command_failure_handled_gracefully():
    with Sandbox() as sb:
        res = sb.run_command("python -c \"import sys; sys.exit(42)\"")
        assert res["exit_code"] == 42
        spec_fail = AssertionSpec(
            type="command_exit_code",
            command="python -c \"import sys; sys.exit(42)\"",
            expected=0
        )
        eval_res = evaluate_single_assertion(sb, spec_fail)
        assert eval_res.passed is False
        assert "42" in eval_res.error_message
