from jarvis.brains.claude_brain import ClaudeBrain, create_provider
from jarvis.config import config
from jarvis.utils.logger import log


class Conclave:
    ROLES = {
        "critic": "You are a harsh CRITIC. Analyze the plan for flaws, edge cases, and failures. Be brutally honest.",
        "advocate": "You are an ADVOCATE. Defend and improve the plan. Address each criticism and propose a stronger solution.",
        "synthesizer": "You are a SYNTHESIZER. Merge the best of both arguments into one optimal final solution.",
    }

    def __init__(self):
        self.critic = ClaudeBrain(temperature=0.7)
        self.advocate = ClaudeBrain(temperature=0.5)
        self.synthesizer = ClaudeBrain(temperature=0.3)

    def debate(self, task: str, context: str = "") -> str:
        if not config.conclave.enabled:
            return self._direct_answer(task)

        prompt = f"""Task: {task}
Context: {context}
Analyze thoroughly and provide your best solution."""

        log.info("Conclave: Round 1 - Critic")
        critic_resp = self.critic.think(
            messages=[{"role": "user", "content": f"{prompt}\n\nAct as a CRITIC. What are the flaws, risks, and edge cases?"}],
            system=self.ROLES["critic"],
        )

        log.info("Conclave: Round 2 - Advocate")
        advocate_resp = self.advocate.think(
            messages=[{"role": "user", "content": f"Task: {task}\n\nCritic raised: {critic_resp}\n\nNow act as ADVOCATE. Address each criticism."}],
            system=self.ROLES["advocate"],
        )

        log.info("Conclave: Round 3 - Synthesizer")
        final = self.synthesizer.think(
            messages=[{"role": "user", "content": f"Task: {task}\n\nCritic:\n{critic_resp}\n\nAdvocate:\n{advocate_resp}\n\nSynthesize the best final solution."}],
            system=self.ROLES["synthesizer"],
        )

        log.info("Conclave: Final synthesis complete")
        return final

    def _direct_answer(self, task: str) -> str:
        brain = ClaudeBrain()
        return brain.think(
            messages=[{"role": "user", "content": task}],
        )
