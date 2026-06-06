"""Provedores de IA gratuitos e pagos para o JARVIS."""
import json
import requests
from jarvis.utils.logger import log


class OllamaProvider:
    """Roda modelos localmente via Ollama (100% gratuito)."""

    def __init__(self, model: str = "qwen2.5-coder:7b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def chat(self, messages: list, system: str = "", temperature: float = 0.3,
             max_tokens: int = 4096) -> str:
        payload = {
            "model": self.model,
            "messages": [],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].extend(messages)

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except requests.exceptions.ConnectionError:
            return "[ERROR] Ollama not running. Start with: ollama serve"
        except Exception as e:
            return f"[ERROR] Ollama: {e}"

    def list_models(self) -> list:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except:
            return []


class GeminiProvider:
    """Usa Google Gemini API (free tier disponivel)."""

    def __init__(self, api_key: str = "", model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def chat(self, messages: list, system: str = "", temperature: float = 0.3,
             max_tokens: int = 4096) -> str:
        if not self.api_key:
            return "[ERROR] GEMINI_API_KEY not set. Get one free at https://aistudio.google.com/apikey"

        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        try:
            url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts)
            return ""
        except Exception as e:
            return f"[ERROR] Gemini: {e}"


class GroqProvider:
    """Usa Groq (free tier: 30 req/min, 14400 req/dia)."""

    def __init__(self, api_key: str = "", model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"

    def chat(self, messages: list, system: str = "", temperature: float = 0.3,
             max_tokens: int = 4096) -> str:
        if not self.api_key:
            return "[ERROR] GROQ_API_KEY not set. Get one free at https://console.groq.com/keys"

        payload = {
            "model": self.model,
            "messages": [],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].extend(messages)

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[ERROR] Groq: {e}"


class ClaudeProvider:
    """Provedor Claude (API paga, mas mais poderosa)."""

    def __init__(self, api_key: str = "", model: str = "claude-3-opus-latest"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _ensure_client(self):
        if self._client is None and self.api_key:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self.api_key)

    def chat(self, messages: list, system: str = "", temperature: float = 0.3,
             max_tokens: int = 4096) -> str:
        if not self.api_key:
            return "[ERROR] ANTHROPIC_API_KEY not set."
        self._ensure_client()
        try:
            kwargs = dict(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
            )
            if system:
                kwargs["system"] = system
            resp = self._client.messages.create(**kwargs)
            return resp.content[0].text if resp.content else ""
        except Exception as e:
            return f"[ERROR] Claude: {e}"
