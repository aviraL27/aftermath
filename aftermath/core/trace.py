from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from pathlib import Path
import json
import time

class StepTrace(BaseModel):
    step_number: int
    agent_thought: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
    duration_seconds: float = 0.0

class RunTrace(BaseModel):
    task_id: str
    task_name: str
    instruction: str
    model_name: str
    provider: str
    start_time: float
    end_time: float
    duration_seconds: float
    status: str  # 'PASSED', 'FAILED', 'ERROR'
    steps: List[StepTrace] = Field(default_factory=list)
    initial_snapshot: Dict[str, str] = Field(default_factory=dict)
    final_snapshot: Dict[str, str] = Field(default_factory=dict)
    workspace_diff: str = ""
    assertion_results: List[Dict[str, Any]] = Field(default_factory=list)
    invariant_results: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None

    def save(self, file_path: str | Path) -> None:
        p = Path(file_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, file_path: str | Path) -> "RunTrace":
        p = Path(file_path).resolve()
        content = p.read_text(encoding="utf-8")
        return cls(**json.loads(content))

