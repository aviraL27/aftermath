import pytest
from aftermath.core.sandbox import Sandbox
from aftermath.core.task import AssertionSpec, ExpectedOutcomes
from aftermath.core.assertions import evaluate_task, evaluate_single_assertion

def test_json_invariants_and_assertions(tmp_path):
    with Sandbox(base_dir=tmp_path) as sb:
        sb.write_file("config.json", '''{
            "database": {"url": "postgresql://prod-db:5432/app"},
            "server": {"port": 8080},
            "security": {"jwt_secret": "secret123"}
        }''')

        # Passing assertion
        res = evaluate_single_assertion(sb, AssertionSpec(
            type="json_value_equals",
            path="config.json",
            key_path="database.url",
            expected="postgresql://prod-db:5432/app"
        ))
        assert res.passed is True

        # Passing invariant
        res_inv = evaluate_single_assertion(sb, AssertionSpec(
            type="json_key_preserved",
            path="config.json",
            key_path="server.port",
            expected=8080
        ), is_invariant=True)
        assert res_inv.passed is True

        # Failing invariant (e.g. if key was deleted)
        sb.write_file("config.json", '{"database": {"url": "postgresql://prod-db:5432/app"}}')
        res_fail = evaluate_single_assertion(sb, AssertionSpec(
            type="json_key_preserved",
            path="config.json",
            key_path="server.port",
            expected=8080
        ), is_invariant=True)
        assert res_fail.passed is False
        assert "missing" in res_fail.error_message

def test_ast_syntax_assertion(tmp_path):
    with Sandbox(base_dir=tmp_path) as sb:
        sb.write_file("valid.py", "def test():\n    return 42\n")
        res = evaluate_single_assertion(sb, AssertionSpec(
            type="ast_syntax_valid",
            path="valid.py"
        ))
        assert res.passed is True

        sb.write_file("broken.py", "def test() return 42\n")
        res_broken = evaluate_single_assertion(sb, AssertionSpec(
            type="ast_syntax_valid",
            path="broken.py"
        ))
        assert res_broken.passed is False
        assert "SyntaxError" in res_broken.error_message

