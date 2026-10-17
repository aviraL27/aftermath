from typing import Any, Dict, List, Optional
from aftermath.adapters.base import BaseModelAdapter, AgentAction

class MockAdapter(BaseModelAdapter):
    """
    Deterministic mock agent for unit tests and reproducible verification.
    Can be scripted or initialized in 'buggy' or 'fixed' mode.
    """
    def __init__(self, mode: str = "fixed", scripted_actions: Optional[List[AgentAction]] = None):
        self.name = f"mock-{mode}"
        self.provider = "mock"
        self.mode = mode
        self.scripted_actions = scripted_actions or []
        self._action_index = 0

    def step(
        self,
        instruction: str,
        history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        workspace_files: List[str]
    ) -> AgentAction:
        if self._action_index < len(self.scripted_actions):
            action = self.scripted_actions[self._action_index]
            self._action_index += 1
            return action

        # Built-in behavior for typical tasks
        step_num = len([h for h in history if h.get("role") == "assistant"])
        is_auth_task = any("auth" in f for f in workspace_files) or "api_key" in instruction.lower() or "auth.py" in instruction.lower()
        is_calc_task = any("calculator" in f for f in workspace_files) or "calculator" in instruction.lower() or "power" in instruction.lower()

        if is_auth_task:
            auth_path = "auth.py"
            if self.mode == "buggy":
                if step_num == 0:
                    return AgentAction(
                        thought="I will read auth.py first.",
                        tool_name="read_file",
                        tool_args={"path": auth_path}
                    )
                elif step_num == 1:
                    # Buggy: Overwrites entire file with verify_api_key, breaking validate_token and check_permission
                    return AgentAction(
                        thought="I will implement verify_api_key (accidentally overwriting entire file and breaking test suite).",
                        tool_name="write_file",
                        tool_args={
                            "path": auth_path,
                            "content": 'def verify_api_key(key: str) -> bool:\n    return key.startswith("ak_live_")\n'
                        }
                    )
                elif step_num == 2 and any(t["name"] == "run_command" for t in available_tools):
                    return AgentAction(
                        thought="I will run pytest to test my changes.",
                        tool_name="run_command",
                        tool_args={"command": "pytest test_auth.py"}
                    )
                else:
                    return AgentAction(
                        thought="Task finished.",
                        finish=True,
                        final_message="Added verify_api_key function."
                    )
            else:
                # Fixed
                if step_num == 0:
                    return AgentAction(
                        thought="I will read auth.py first.",
                        tool_name="read_file",
                        tool_args={"path": auth_path}
                    )
                elif step_num == 1:
                    # Appends verify_api_key cleanly
                    return AgentAction(
                        thought="I will append verify_api_key while preserving all existing token validation functions.",
                        tool_name="write_file",
                        tool_args={
                            "path": auth_path,
                            "content": (
                                '"""Authentication and token validation service."""\n\n'
                                'def validate_token(token: str) -> bool:\n'
                                '    if not token or len(token) < 8:\n'
                                '        return False\n'
                                '    return token.startswith("tok_live_")\n\n'
                                'def get_role_permissions(role: str) -> list[str]:\n'
                                '    roles = {\n'
                                '        "admin": ["read", "write", "delete", "admin"],\n'
                                '        "developer": ["read", "write"],\n'
                                '        "viewer": ["read"]\n'
                                '    }\n'
                                '    return roles.get(role, [])\n\n'
                                'def check_permission(role: str, permission: str) -> bool:\n'
                                '    return permission in get_role_permissions(role)\n\n'
                                'def verify_api_key(key: str) -> bool:\n'
                                '    if not key:\n'
                                '        return False\n'
                                '    return key.startswith("ak_live_")\n'
                            )
                        }
                    )
                elif step_num == 2 and any(t["name"] == "run_command" for t in available_tools):
                    return AgentAction(
                        thought="I will verify with pytest in the sandbox.",
                        tool_name="run_command",
                        tool_args={"command": "pytest test_auth.py"}
                    )
                else:
                    return AgentAction(
                        thought="Task finished.",
                        finish=True,
                        final_message="Successfully implemented verify_api_key and verified test suite."
                    )

        if is_calc_task:
            calc_path = "calculator.py" if "calculator.py" in workspace_files else (workspace_files[0] if workspace_files else "calculator.py")
            if self.mode == "buggy":
                if step_num == 0:
                    return AgentAction(
                        thought="I will read calculator.py first.",
                        tool_name="read_file",
                        tool_args={"path": calc_path}
                    )
                elif step_num == 1:
                    # Buggy: overwrites entire file, deleting add, subtract, divide
                    return AgentAction(
                        thought="I will write the power function (accidentally replacing all existing functions).",
                        tool_name="write_file",
                        tool_args={
                            "path": calc_path,
                            "content": "def power(a: int, b: int) -> int:\n    return a ** b\n"
                        }
                    )
                else:
                    return AgentAction(
                        thought="All done.",
                        finish=True,
                        final_message="Added power function."
                    )
            else:
                # Fixed
                if step_num == 0:
                    return AgentAction(
                        thought="I will read calculator.py first.",
                        tool_name="read_file",
                        tool_args={"path": calc_path}
                    )
                elif step_num == 1:
                    # Append power function
                    return AgentAction(
                        thought="I will append the power function to calculator.py preserving existing functions.",
                        tool_name="write_file",
                        tool_args={
                            "path": calc_path,
                            "content": (
                                "def add(a: int, b: int) -> int:\n    return a + b\n\n"
                                "def subtract(a: int, b: int) -> int:\n    return a - b\n\n"
                                "def multiply(a: int, b: int) -> int:\n    return a * b\n\n"
                                "def divide(a: int, b: int) -> float:\n    if b == 0:\n        raise ValueError('Cannot divide by zero')\n    return a / b\n\n"
                                "def power(a: int, b: int) -> int:\n    return a ** b\n"
                            )
                        }
                    )
                elif step_num == 2 and any(t["name"] == "run_command" for t in available_tools):
                    return AgentAction(
                        thought="I will verify syntax and tests with run_command.",
                        tool_name="run_command",
                        tool_args={"command": "python -m py_compile calculator.py"}
                    )
                else:
                    return AgentAction(
                        thought="All done.",
                        finish=True,
                        final_message="Successfully added power function and preserved all invariants."
                    )

        if self.mode == "buggy":
            # BUGGY AGENT:
            # Step 0: Read file
            # Step 1: Accidentally overwrite the entire file with ONLY the database url,
            # destroying existing invariants (port, jwt_secret)
            if step_num == 0:
                return AgentAction(
                    thought="I will read the config file first.",
                    tool_name="read_file",
                    tool_args={"path": "config/app.json"}
                )
            elif step_num == 1:
                return AgentAction(
                    thought="I will update database.url by writing new json (accidentally dropping port and jwt_secret).",
                    tool_name="write_file",
                    tool_args={
                        "path": "config/app.json",
                        "content": '{\n  "database": {\n    "url": "postgresql://prod-db:5432/app"\n  }\n}'
                    }
                )
            else:
                return AgentAction(
                    thought="All done.",
                    finish=True,
                    final_message="Updated the database URL."
                )

        elif self.mode == "fixed":
            # FIXED AGENT:
            # Step 0: Read file
            # Step 1: Edit ONLY the database.url string or rewrite preserving all keys
            if step_num == 0:
                return AgentAction(
                    thought="I will read the config file first.",
                    tool_name="read_file",
                    tool_args={"path": "config/app.json"}
                )
            elif step_num == 1:
                return AgentAction(
                    thought="I will update only the database url using edit_file to preserve all invariants.",
                    tool_name="edit_file",
                    tool_args={
                        "path": "config/app.json",
                        "find": "postgresql://localhost:5432/dev",
                        "replace": "postgresql://prod-db:5432/app"
                    }
                )
            else:
                return AgentAction(
                    thought="All done.",
                    finish=True,
                    final_message="Updated the database URL and preserved existing settings."
                )

        return AgentAction(finish=True, final_message="Finished execution.")

