import json
import re
import httpx
from typing import Any, Dict, List, Optional
from aftermath.adapters.base import BaseModelAdapter, AgentAction
from aftermath.config import settings

class MistralAdapter(BaseModelAdapter):
    """
    Adapter for Apache-2.0 licensed Mistral models (open-mistral-7b).
    """
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: str = "https://api.mistral.ai/v1"
    ):
        self.name = "mistral"
        self.provider = "mistral"
        self.model = model or settings.mistral_model or "open-mistral-7b"
        self.api_key = api_key or settings.mistral_api_key
        self.base_url = base_url.rstrip("/")

    def _build_system_prompt(self, instruction: str, tools: List[Dict[str, Any]], files: List[str]) -> str:
        tool_desc = json.dumps(tools, indent=2)
        return (
            "You are an AI developer agent operating in a strictly controlled sandboxed workspace.\n"
            f"Current files in workspace: {files}\n\n"
            f"Goal / Instruction: {instruction}\n\n"
            "You must perform actions using available tools until the goal is achieved.\n"
            "Respond ONLY with a JSON object in this format:\n"
            "{\n"
            '  "thought": "Your internal reasoning",\n'
            '  "tool": "name_of_tool_or_null",\n'
            '  "args": {"arg_name": "arg_value"},\n'
            '  "finish": false,\n'
            '  "message": "Final summary message if finish is true"\n'
            "}\n\n"
            f"Available tools:\n{tool_desc}\n"
            "If the task is complete, set finish: true and tool: null."
        )

    def _parse_action(self, text: str) -> AgentAction:
        clean = text.strip()
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL)
        if m:
            clean = m.group(1)
        else:
            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end != -1 and end > start:
                clean = clean[start:end+1]

        try:
            data = json.loads(clean)
            return AgentAction(
                thought=data.get("thought"),
                tool_name=data.get("tool"),
                tool_args=data.get("args") or {},
                finish=bool(data.get("finish", False)),
                final_message=data.get("message")
            )
        except Exception:
            return AgentAction(
                thought=f"Raw response: {text[:200]}",
                finish=True,
                final_message=text
            )

    def step(
        self,
        instruction: str,
        history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        workspace_files: List[str]
    ) -> AgentAction:
        if not self.api_key:
            return AgentAction(
                thought="No Mistral API key configured",
                finish=True,
                final_message="Error: Missing MISTRAL_API_KEY in environment or .env"
            )

        system = self._build_system_prompt(instruction, available_tools, workspace_files)
        
        messages = [{"role": "system", "content": system}]
        for h in history:
            messages.append({"role": h.get("role", "assistant"), "content": h.get("content", "")})
        messages.append({
            "role": "user",
            "content": "What is your next action? Respond strictly in JSON format."
        })

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"]
                return self._parse_action(raw_text)
        except Exception as e:
            return AgentAction(
                thought=f"Mistral API call error: {e}",
                finish=True,
                final_message=f"Mistral API error: {e}"
            )

