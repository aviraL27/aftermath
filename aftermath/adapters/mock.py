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

        # Built-in behavior for typical config task
        step_num = len([h for h in history if h.get("role") == "assistant"])
        
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

