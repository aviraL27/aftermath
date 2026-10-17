from typing import Any, List, Optional, Literal, Dict
from pydantic import BaseModel, Field
from pathlib import Path
import yaml
import json

class AssertionSpec(BaseModel):
    """Specification of an expected outcome or invariant to check."""
    type: Literal[
        "file_exists",
        "file_not_exists",
        "file_contains",
        "file_not_contains",
        "file_exact",
        "json_value_equals",
        "json_key_preserved",
        "ast_syntax_valid",
        "regex_match",
        "command_exit_code",
        "command_stdout_contains",
        "command_stdout_not_contains"
    ]
    path: str = ""
    key_path: Optional[str] = None
    expected: Optional[Any] = None
    pattern: Optional[str] = None
    command: Optional[str] = None
    timeout: Optional[int] = 30
    description: Optional[str] = None

class ExpectedOutcomes(BaseModel):
    """Assertions for intended changes and invariants for preserved state."""
    assertions: List[AssertionSpec] = Field(default_factory=list)
    invariants: List[AssertionSpec] = Field(default_factory=list)

class ModelConfig(BaseModel):
    """Model selection and parameters."""
    model: str = "gemma4"
    provider: Optional[str] = None  # e.g., 'google', 'ollama', 'mistral', 'mock'
    temperature: float = 0.2
    max_tokens: int = 2048

class TaskDefinition(BaseModel):
    """Full definition of a test task in Aftermath."""
    id: str
    name: str
    description: str = ""
    instruction: str
    workspace_fixture: str  # Path relative to task file or root
    sandbox_backend: Literal["local", "e2b"] = "local"
    e2b_template: Optional[str] = None
    tools: List[str] = Field(default_factory=lambda: ["read_file", "write_file", "edit_file", "list_files", "run_command"])
    max_steps: int = 10
    model_config_override: Optional[ModelConfig] = None
    expected_outcomes: ExpectedOutcomes = Field(default_factory=ExpectedOutcomes)

    # Metadata for regression tests
    is_regression_test: bool = False
    generated_from_trace: Optional[str] = None
    validated: bool = False

    @classmethod
    def load(cls, file_path: str | Path) -> "TaskDefinition":
        """Load task definition from YAML or JSON file."""
        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Task definition file not found: {p}")
        
        content = p.read_text(encoding="utf-8")
        if p.suffix.lower() in [".yaml", ".yml"]:
            data = yaml.safe_load(content)
        elif p.suffix.lower() in [".json"]:
            data = json.loads(content)
        else:
            raise ValueError(f"Unsupported file format: {p.suffix}. Use .yaml or .json.")
        
        # Resolve relative fixture path based on task file directory
        if "workspace_fixture" in data:
            fixture_p = Path(data["workspace_fixture"])
            if not fixture_p.is_absolute():
                candidate = (p.parent / fixture_p).resolve()
                if candidate.exists():
                    data["workspace_fixture"] = str(candidate)
        
        return cls(**data)

    def save_yaml(self, file_path: str | Path) -> None:
        """Save task definition as clean YAML."""
        p = Path(file_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(exclude_none=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, indent=2)

