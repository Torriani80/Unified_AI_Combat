import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class APIConfig:
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", "")
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.environ.get("GEMINI_API_KEY", "")
    )
    groq_api_key: str = field(
        default_factory=lambda: os.environ.get("GROQ_API_KEY", "")
    )


@dataclass
class BrainConfig:
    provider: str = "ollama"  # ollama | gemini | groq | claude | openai
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_base_url: str = "http://localhost:11434"
    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.3-70b-versatile"
    claude_model: str = "claude-3-opus-latest"
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class VoiceConfig:
    enabled: bool = True
    stt_engine: str = "google"   # google | whisper
    tts_engine: str = "edge"     # edge | pyttsx3
    wake_word: str = "jarvis"
    language: str = "pt-BR"


@dataclass
class ConclaveConfig:
    enabled: bool = True
    num_debaters: int = 3
    rounds: int = 2


@dataclass
class MemoryConfig:
    storage_path: str = str(os.path.join(os.path.expanduser("~"), "JARVIS", "memory"))
    max_history: int = 1000
    enable_vector_search: bool = True


@dataclass
class AgentConfig:
    name: str = ""
    role: str = ""
    system_prompt: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class AppConfig:
    api: APIConfig = field(default_factory=APIConfig)
    brain: BrainConfig = field(default_factory=BrainConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    conclave: ConclaveConfig = field(default_factory=ConclaveConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    data_dir: str = str(os.path.join(os.path.expanduser("~"), "JARVIS", "projects"))
    verbose: bool = False


config = AppConfig()
