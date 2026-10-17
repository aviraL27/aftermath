from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class AgentAction(BaseModel):
    thought: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    finish: bool = False
    final_message: Optional[str] = None

class BaseModelAdapter(ABC):
    """Abstract interface for model adapters."""
    name: str
    provider: str

    @abstractmethod
    def step(
        self,
        instruction: str,
        history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        workspace_files: List[str]
    ) -> AgentAction:
        """Given conversation history and available tools, produce next action."""
        pass

