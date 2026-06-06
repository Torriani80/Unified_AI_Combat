import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class ObsidianMemory:
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.history_file = self.storage_path / "history.json"
        self.profile_file = self.storage_path / "profile.json"
        self._history = self._load(self.history_file, [])
        self._profile = self._load(self.profile_file, {})

    def _load(self, path, default):
        if path.exists():
            try:
                return json.load(open(path, encoding="utf-8"))
            except:
                pass
        return default

    def _save(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def remember(self, key: str, value, namespace: str = "general"):
        ns = self._profile.setdefault(namespace, {})
        ns[key] = {
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }
        self._save(self.profile_file, self._profile)

    def recall(self, key: str, namespace: str = "general") -> Optional[dict]:
        ns = self._profile.get(namespace, {})
        entry = ns.get(key)
        return entry["value"] if entry else None

    def add_conversation(self, role: str, content: str, metadata: dict = None):
        self._history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        })
        max_h = 1000
        if len(self._history) > max_h:
            self._history = self._history[-max_h:]
        self._save(self.history_file, self._history)

    def get_recent(self, n: int = 20) -> list:
        return self._history[-n:]

    def get_conversation_context(self, n: int = 30) -> str:
        recent = self.get_recent(n)
        lines = []
        for msg in recent:
            role_icon = "🧑" if msg["role"] == "user" else "🤖"
            lines.append(f"{role_icon} {msg['content'][:200]}")
        return "\n".join(lines)

    def get_profile_summary(self) -> str:
        lines = []
        for ns, data in self._profile.items():
            lines.append(f"[{ns}]")
            for key, entry in data.items():
                val = entry["value"]
                lines.append(f"  {key}: {val}")
        return "\n".join(lines) if lines else "No profile data yet."

    def search(self, query: str) -> list:
        query = query.lower()
        results = []
        for msg in self._history:
            if query in msg["content"].lower():
                results.append(msg)
        return results[-10:]
