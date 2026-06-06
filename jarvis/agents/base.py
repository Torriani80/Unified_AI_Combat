from jarvis.brains.claude_brain import ClaudeBrain
from jarvis.memory.obsidian import ObsidianMemory
from jarvis.utils.logger import log


class BaseAgent:
    def __init__(self, name: str, role: str, system_prompt: str,
                 model: str = "claude-3-opus-latest", temperature: float = 0.3,
                 max_tokens: int = 4096):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.brain = ClaudeBrain(model=model)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory: ObsidianMemory = None

    def set_memory(self, memory: ObsidianMemory):
        self.memory = memory

    def execute(self, task: str, context: str = "") -> str:
        full_context = context
        if self.memory:
            mem = self.memory.get_conversation_context(10)
            profile = self.memory.get_profile_summary()
            full_context = f"{context}\n\nRecent memory:\n{mem}\n\nProfile:\n{profile}"

        messages = [{"role": "user", "content": f"Task: {task}\n\nContext:\n{full_context}"}]

        log.info(f"[{self.name}] executing task ({len(task)} chars)")
        response = self.brain.think(
            messages=messages,
            system=self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        if self.memory:
            self.memory.add_conversation("assistant", response, {"agent": self.name})

        return response

    def __repr__(self):
        return f"<Agent {self.name} ({self.role})>"
