"""Cerebro principal do JARVIS - suporta provedores gratis e pagos."""
from jarvis.config import config
from jarvis.brains.providers import OllamaProvider, GeminiProvider, GroqProvider, ClaudeProvider
from jarvis.utils.logger import log


PROVIDER_MAP = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "claude": ClaudeProvider,
}


def create_provider(provider: str = None):
    provider = provider or config.brain.provider
    bc = config.brain

    if provider == "ollama":
        return OllamaProvider(model=bc.ollama_model, base_url=bc.ollama_base_url)
    elif provider == "gemini":
        return GeminiProvider(api_key=config.api.gemini_api_key, model=bc.gemini_model)
    elif provider == "groq":
        return GroqProvider(api_key=config.api.groq_api_key, model=bc.groq_model)
    elif provider == "claude":
        return ClaudeProvider(api_key=config.api.anthropic_api_key, model=bc.claude_model)
    else:
        log.warn(f"Unknown provider '{provider}', falling back to ollama")
        return OllamaProvider()


class ClaudeBrain:
    """Cerebro principal - usa o provider configurado."""

    def __init__(self, model: str = None, temperature: float = None,
                 provider: str = None):
        self.provider = create_provider(provider)
        self.temperature = temperature if temperature is not None else config.brain.temperature
        self.max_tokens = config.brain.max_tokens
        self.model = model or config.brain.claude_model

    def think(self, messages: list, system: str = "", max_tokens: int = None,
              temperature: float = None) -> str:
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        log.info(f"Brain [{config.brain.provider}] thinking...")
        result = self.provider.chat(
            messages=messages,
            system=system,
            temperature=temp,
            max_tokens=tokens,
        )
        log.info(f"Brain responded ({len(result)} chars)")
        return result
