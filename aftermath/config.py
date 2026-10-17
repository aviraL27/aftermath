from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

# Load .env if present
load_dotenv()

class Settings(BaseModel):
    google_api_key: str = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    ollama_base_url: str = Field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_gemma_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_GEMMA_MODEL", "gemma4:12b"))
    mistral_api_key: str = Field(default_factory=lambda: os.getenv("MISTRAL_API_KEY", ""))
    mistral_model: str = Field(default_factory=lambda: os.getenv("MISTRAL_MODEL", "open-mistral-7b"))
    ui_host: str = Field(default_factory=lambda: os.getenv("AFTERMATH_HOST", "127.0.0.1"))
    ui_port: int = Field(default_factory=lambda: int(os.getenv("AFTERMATH_PORT", "8000")))

    # Priority setting for Gemma 4: 'auto', 'api', 'ollama'
    gemma_preferred_provider: str = Field(default="auto")

    def get_google_key(self) -> str:
        return self.google_api_key or self.gemini_api_key

settings = Settings()

