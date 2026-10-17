import json
import re
import ast
from typing import Any, List, Optional
from pydantic import BaseModel
from aftermath.core.sandbox import Sandbox
from aftermath.core.task import AssertionSpec

class AssertionResult(BaseModel):
    spec: AssertionSpec
    passed: bool
    actual_value: Optional[Any] = None
    expected_value: Optional[Any] = None
    error_message: Optional[str] = None
    is_invariant: bool = False

class EvaluationSummary(BaseModel):
    all_passed: bool
    assertion_results: List[AssertionResult]
    invariant_results: List[AssertionResult]
    failed_assertions: List[AssertionResult]
    failed_invariants: List[AssertionResult]

def _get_nested_key(data: Any, key_path: str) -> Any:
    """Resolve dotted path like 'database.url' in nested dicts."""
    parts = key_path.split(".")
    curr = data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        elif isinstance(curr, list) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(curr):
                curr = curr[idx]
            else:
                raise KeyError(f"Index out of range: {part}")
        else:
            raise KeyError(f"Key not found: {part} in path {key_path}")
    return curr

def evaluate_single_assertion(sandbox: Sandbox, spec: AssertionSpec, is_invariant: bool = False) -> AssertionResult:
    """Evaluate one assertion or invariant against the sandbox."""
    try:
        if spec.type == "file_exists":
            exists = sandbox.file_exists(spec.path)
            return AssertionResult(
                spec=spec,
                passed=exists,
                actual_value="exists" if exists else "missing",
                expected_value="exists",
                error_message=None if exists else f"Expected file '{spec.path}' to exist, but it was not found.",
                is_invariant=is_invariant
            )

        elif spec.type == "file_not_exists":
            exists = sandbox.file_exists(spec.path)
            return AssertionResult(
                spec=spec,
                passed=not exists,
                actual_value="missing" if not exists else "exists",
                expected_value="missing",
                error_message=None if not exists else f"Expected file '{spec.path}' to not exist, but it does.",
                is_invariant=is_invariant
            )

        if not sandbox.file_exists(spec.path):
            return AssertionResult(
                spec=spec,
                passed=False,
                actual_value="missing",
                expected_value="exists",
                error_message=f"Target file '{spec.path}' does not exist.",
                is_invariant=is_invariant
            )

        content = sandbox.read_file(spec.path)

        if spec.type == "file_contains":
            contains = spec.expected in content if spec.expected else False
            return AssertionResult(
                spec=spec,
                passed=contains,
                actual_value=f"Substring {'found' if contains else 'not found'}",
                expected_value=f"Contains: {spec.expected}",
                error_message=None if contains else f"File '{spec.path}' did not contain expected content: '{spec.expected}'",
                is_invariant=is_invariant
            )

        elif spec.type == "file_not_contains":
            contains = spec.expected in content if spec.expected else False
            return AssertionResult(
                spec=spec,
                passed=not contains,
                actual_value=f"Substring {'found' if contains else 'not found'}",
                expected_value=f"Does not contain: {spec.expected}",
                error_message=None if not contains else f"File '{spec.path}' contains forbidden content: '{spec.expected}'",
                is_invariant=is_invariant
            )

        elif spec.type == "file_exact":
            match = (content.strip() == str(spec.expected).strip())
            return AssertionResult(
                spec=spec,
                passed=match,
                actual_value=content[:100],
                expected_value=str(spec.expected)[:100],
                error_message=None if match else f"File '{spec.path}' exact content mismatch.",
                is_invariant=is_invariant
            )

        elif spec.type in ["json_value_equals", "json_key_preserved"]:
            try:
                parsed = json.loads(content)
            except Exception as e:
                return AssertionResult(
                    spec=spec,
                    passed=False,
                    actual_value="invalid_json",
                    expected_value="valid_json",
                    error_message=f"File '{spec.path}' is not valid JSON: {e}",
                    is_invariant=is_invariant
                )
            
            if not spec.key_path:
                return AssertionResult(
                    spec=spec,
                    passed=False,
                    error_message="key_path required for JSON assertions",
                    is_invariant=is_invariant
                )
                
            try:
                val = _get_nested_key(parsed, spec.key_path)
                match = (val == spec.expected)
                err = None if match else f"Key '{spec.key_path}' has value '{val}' (expected '{spec.expected}')"
                return AssertionResult(
                    spec=spec,
                    passed=match,
                    actual_value=val,
                    expected_value=spec.expected,
                    error_message=err,
                    is_invariant=is_invariant
                )
            except KeyError as e:
                return AssertionResult(
                    spec=spec,
                    passed=False,
                    actual_value="key_missing",
                    expected_value=spec.expected,
                    error_message=f"Key '{spec.key_path}' missing in JSON file '{spec.path}'",
                    is_invariant=is_invariant
                )

        elif spec.type == "ast_syntax_valid":
            try:
                ast.parse(content)
                return AssertionResult(
                    spec=spec,
                    passed=True,
                    actual_value="valid_ast",
                    expected_value="valid_ast",
                    is_invariant=is_invariant
                )
            except SyntaxError as e:
                return AssertionResult(
                    spec=spec,
                    passed=False,
                    actual_value=f"SyntaxError: {e}",
                    expected_value="valid_ast",
                    error_message=f"Python file '{spec.path}' has SyntaxError at line {e.lineno}: {e.msg}",
                    is_invariant=is_invariant
                )

        elif spec.type == "regex_match":
            pattern = spec.pattern or str(spec.expected)
            match = bool(re.search(pattern, content))
            return AssertionResult(
                spec=spec,
                passed=match,
                actual_value="matched" if match else "no_match",
                expected_value=f"Matches /{pattern}/",
                error_message=None if match else f"File '{spec.path}' did not match regex /{pattern}/",
                is_invariant=is_invariant
            )

        return AssertionResult(
            spec=spec,
            passed=False,
            error_message=f"Unknown assertion type: {spec.type}",
            is_invariant=is_invariant
        )

    except Exception as e:
        return AssertionResult(
            spec=spec,
            passed=False,
            error_message=f"Evaluation failed with exception: {e}",
            is_invariant=is_invariant
        )

def evaluate_task(sandbox: Sandbox, expected_outcomes) -> EvaluationSummary:
    """Evaluate all assertions and invariants for a task."""
    assertion_results = [
        evaluate_single_assertion(sandbox, a, is_invariant=False)
        for a in expected_outcomes.assertions
    ]
    invariant_results = [
        evaluate_single_assertion(sandbox, inv, is_invariant=True)
        for inv in expected_outcomes.invariants
    ]

    failed_assertions = [r for r in assertion_results if not r.passed]
    failed_invariants = [r for r in invariant_results if not r.passed]
    all_passed = len(failed_assertions) == 0 and len(failed_invariants) == 0

    return EvaluationSummary(
        all_passed=all_passed,
        assertion_results=assertion_results,
        invariant_results=invariant_results,
        failed_assertions=failed_assertions,
        failed_invariants=failed_invariants
    )

