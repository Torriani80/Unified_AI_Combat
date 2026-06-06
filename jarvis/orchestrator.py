import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from jarvis.config import config
from jarvis.brains.claude_brain import ClaudeBrain
from jarvis.brains.conclave import Conclave
from jarvis.memory.obsidian import ObsidianMemory
from jarvis.agents.base import BaseAgent
from jarvis.agents.registry import create_agent, SYSTEM_PROMPTS
from jarvis.tools.file_creator import FileCreator
from jarvis.tools.screen_controller import ScreenController
from jarvis.tools.data_analyzer import DataAnalyzer
from jarvis.voice.speaker import VoiceSpeaker
from jarvis.utils.logger import log


class JarvisOrchestrator:
    def __init__(self):
        os.makedirs(config.memory.storage_path, exist_ok=True)
        os.makedirs(config.data_dir, exist_ok=True)

        self.memory = ObsidianMemory(config.memory.storage_path)
        self.brain = ClaudeBrain()
        self.conclave = Conclave()
        self.file_creator = FileCreator(config.data_dir)
        self.screen = ScreenController()
        self.data_analyzer = DataAnalyzer()
        self.speaker = VoiceSpeaker(engine=config.voice.tts_engine)

        self.agents: dict[str, BaseAgent] = {}
        self._init_agents()
        self.executor = ThreadPoolExecutor(max_workers=5)
        log.info("JARVIS Orchestrator initialized")

    def _init_agents(self):
        for key in SYSTEM_PROMPTS:
            name = key.replace("_", " ").title()
            agent = create_agent(key)
            agent.set_memory(self.memory)
            self.agents[key] = agent
        log.info(f"Loaded {len(self.agents)} agents")

    def think(self, task: str, use_conclave: bool = True) -> str:
        self.memory.add_conversation("user", task)

        profile = self.memory.get_profile_summary()
        recent = self.memory.get_conversation_context(10)
        context = f"User Profile:\n{profile}\n\nRecent Context:\n{recent}"

        if use_conclave and config.conclave.enabled:
            log.info("Routing through Conclave")
            result = self.conclave.debate(task, context)
        else:
            log.info("Direct brain")
            result = self.brain.think(
                messages=[{"role": "user", "content": f"Task: {task}\n\nContext:\n{context}"}],
                system="You are JARVIS, an AI assistant that helps users create, build, and automate.",
                temperature=0.3,
            )

        self.memory.add_conversation("assistant", result)
        return result

    def delegate(self, task: str, agent_keys: list[str] = None) -> dict[str, str]:
        if agent_keys is None:
            agent_keys = self._route_task(task)

        results = {}
        log.info(f"Delegating to {len(agent_keys)} agents: {agent_keys}")

        with ThreadPoolExecutor(max_workers=len(agent_keys)) as pool:
            fut = {}
            for key in agent_keys:
                agent = self.agents.get(key)
                if agent:
                    fut[pool.submit(agent.execute, task)] = key

            for f in as_completed(fut):
                key = fut[f]
                try:
                    results[key] = f.result()
                except Exception as e:
                    results[key] = f"[ERROR] {e}"

        return results

    def _route_task(self, task: str) -> list[str]:
        task_lower = task.lower()
        routes = ["analyst"]

        if any(w in task_lower for w in ["code", "program", "app", "script", "software", "sistema"]):
            routes = ["architect", "developer", "qa_tester"]
        elif any(w in task_lower for w in ["site", "web", "html", "landing", "dashboard"]):
            routes = ["ux_designer", "developer"]
        elif any(w in task_lower for w in ["planilha", "excel", "dados", "data", "csv"]):
            routes = ["data_engineer", "analyst"]
        elif any(w in task_lower for w in ["deploy", "docker", "server", "cloud"]):
            routes = ["devops"]
        elif any(w in task_lower for w in ["bug", "erro", "error", "crash", "fail"]):
            routes = ["rootcause", "qa_tester", "developer"]
        elif any(w in task_lower for w in ["relatório", "report", "pdf", "proposta"]):
            routes = ["analyst", "ux_designer"]
        elif any(w in task_lower for w in ["estratégia", "estrategia", "plano", "planejamento", "project"]):
            routes = ["project_manager", "product_owner", "analyst"]

        return routes

    def create_project(self, description: str) -> str:
        log.info(f"Creating project from: {description}")
        result = self.think(f"Create a complete project plan for: {description}")
        return result

    def execute_voice_command(self, command: str) -> str:
        cmd = command.lower().strip()

        if cmd.startswith("cria") or cmd.startswith("crie") or cmd.startswith("make") or cmd.startswith("create"):
            return self.create_project(command)

        if "abre" in cmd or "open" in cmd:
            import re
            urls = re.findall(r'https?://\S+', command)
            if urls:
                self.screen.open_website(urls[0])
                return f"Opening {urls[0]}"
            sites = {"youtube": "https://youtube.com", "google": "https://google.com",
                     "gmail": "https://mail.google.com", "github": "https://github.com"}
            for name, url in sites.items():
                if name in cmd:
                    self.screen.open_website(url)
                    return f"Opening {name}"
            return "Website not recognized"

        if "digita" in cmd or "type" in cmd:
            text = command.split("digita", 1)[-1].split("type", 1)[-1].strip()
            self.screen.type_text(text)
            return f"Typing: {text}"

        if "clique" in cmd or "click" in cmd:
            self.screen.click(500, 500)
            return "Clicked at center"

        if any(w in cmd for w in ["analisa", "analyze", "analise"]):
            import re
            files = re.findall(r'[\w\\/:.-]+\.\w+', command)
            if files:
                return self.data_analyzer.analyze_csv(files[0])
            return "No file found to analyze"

        return self.think(command)

    def speak(self, text: str):
        self.speaker.say(text)

    def get_agent_list(self) -> list:
        return list(self.agents.keys())

    def get_agent(self, key: str) -> BaseAgent:
        return self.agents.get(key)
