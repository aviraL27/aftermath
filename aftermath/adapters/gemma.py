import json
import re
import httpx
from typing import Any, Dict, List, Optional
from aftermath.adapters.base import BaseModelAdapter, AgentAction
from aftermath.config import settings

class GemmaAdapter(BaseModelAdapter):
    """
    Adapter for Gemma 4.
    Uses the faster provider (Google API) as primary, with local Ollama as automatic fallback.
    """
    def __init__(
        self,
        primary_provider: str = "google",
        google_model: str = "models/gemma-4-26b-a4b-it",
        ollama_model: str = "gemma4:12b",
        ollama_base_url: Optional[str] = None,
        google_api_key: Optional[str] = None,
    ):
        self.name = "gemma4"
        self.provider = primary_provider
        self.primary_provider = primary_provider
        self.fallback_provider = "ollama" if primary_provider == "google" else "google"
        
        self.google_model = google_model
        self.ollama_model = ollama_model or settings.ollama_gemma_model
        self.ollama_base_url = (ollama_base_url or settings.ollama_base_url).rstrip("/")
        self.google_api_key = google_api_key or settings.get_google_key()

    def _build_system_prompt(self, instruction: str, tools: List[Dict[str, Any]], files: List[str]) -> str:
        tool_names = [t["name"] for t in tools]
        return (
            "You are an AI developer agent operating in an isolated workspace.\n"
            f"Available workspace files: {files}\n"
            f"Available tools: {tool_names}\n\n"
            f"Task: {instruction}\n\n"
            "RULES:\n"
            "1. Output MUST be a single raw JSON object. No intro, no outro, no markdown formatting.\n"
            "2. Structure:\n"
            "{\n"
            '  "thought": "brief reasoning",\n'
            '  "tool": "read_file" | "write_file" | "edit_file" | "list_files" | null,\n'
            '  "args": {"path": "...", ...},\n'
            '  "finish": false,\n'
            '  "message": "summary if finish is true"\n'
            "}\n\n"
            "Example to read a file:\n"
            '{"thought": "Reading config", "tool": "read_file", "args": {"path": "config/app.json"}, "finish": false}\n\n'
            "Example when finished:\n"
            '{"thought": "Task complete", "tool": null, "args": {}, "finish": true, "message": "Updated URL successfully."}'
        )

    def _parse_action(self, text: str) -> AgentAction:
        clean = text.strip()
        # Find json block ```json ... ```
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
            # Fallback heuristic: did the model say to read a file?
            read_m = re.search(r"(?:read|inspect)\s+[`'\"]?([a-zA-Z0-9_\-\./]+)[`'\"]?", text, re.IGNORECASE)
            if read_m:
                return AgentAction(
                    thought=f"Extracted read request from prose: {text[:100]}",
                    tool_name="read_file",
                    tool_args={"path": read_m.group(1)},
                    finish=False
                )
            return AgentAction(
                thought=f"Raw response: {text[:200]}",
                finish=True,
                final_message=text
            )


    def _call_google_api(self, prompt: str) -> str:
        if not self.google_api_key:
            raise ValueError("No Google API key provided for Gemma 4")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/{self.google_model}:generateContent?key={self.google_api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}
        }
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_ollama(self, prompt: str) -> str:
        url = f"{self.ollama_base_url}/api/chat"
        payload = {
            "model": self.ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.2}
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]

    def step(
        self,
        instruction: str,
        history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        workspace_files: List[str]
    ) -> AgentAction:
        system = self._build_system_prompt(instruction, available_tools, workspace_files)
        
        # Build conversation text
        convo_lines = [system, "\nExecution History:"]
        for h in history:
            role = h.get("role", "assistant")
            content = h.get("content", "")
            convo_lines.append(f"[{role.upper()}]: {content}")
            
        convo_lines.append("\nWhat is your next action? Respond strictly in the specified JSON format.")
        full_prompt = "\n".join(convo_lines)

        # Attempt primary provider first (Google API = 2.4s vs Ollama = 7.5s)
        try:
            if self.primary_provider == "google":
                raw = self._call_google_api(full_prompt)
                self.provider = "google"
            else:
                raw = self._call_ollama(full_prompt)
                self.provider = "ollama"
        except Exception as e:
            # Fallback to secondary provider
            try:
                if self.fallback_provider == "ollama":
                    raw = self._call_ollama(full_prompt)
                    self.provider = "ollama (fallback)"
                else:
                    raw = self._call_google_api(full_prompt)
                    self.provider = "google (fallback)"
            except Exception as e2:
                return AgentAction(
                    thought=f"Primary ({self.primary_provider}) failed: {e}. Fallback ({self.fallback_provider}) failed: {e2}",
                    finish=True,
                    final_message=f"Model execution error: {e2}"
                )

        return self._parse_action(raw)

