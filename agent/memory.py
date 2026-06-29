import json
import os
from datetime import datetime


_LONG_TERM_FILE = None


def _ensure_long_term_file():
    global _LONG_TERM_FILE
    if _LONG_TERM_FILE is None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent")
        _LONG_TERM_FILE = os.path.join(log_dir, "long_term_memory.json")
    return _LONG_TERM_FILE


def _load_long_term():
    path = _ensure_long_term_file()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_long_term(items):
    path = _ensure_long_term_file()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
    except Exception:
        pass


_HISTORY_FILE = None


def _ensure_history_file():
    global _HISTORY_FILE
    if _HISTORY_FILE is None:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent")
        _HISTORY_FILE = os.path.join(d, "chat_history.json")
    return _HISTORY_FILE


class Memory:

    MAX_SHORT_TERM = 500
    MAX_OBSERVATIONS = 10

    def __init__(self, load_history=True):
        self.short_term = []
        self._observations = []
        self._history_loaded = not load_history
        self._skip_history = not load_history

    def _load_from_history(self):
        if self._skip_history:
            return
        path = _ensure_history_file()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions = data.get("sessions", [])
            if not sessions:
                return
            last = sessions[-1]
            for msg in last.get("messages", []):
                role = msg.get("role", "")
                text = msg.get("text", "")
                if role and text:
                    self.short_term.append({"role": role, "content": text[:500], "timestamp": datetime.now().isoformat()})
        except Exception:
            pass

    def add_short_term(self, role, content):
        if not self._history_loaded:
            self._load_from_history()
            self._history_loaded = True
        self.short_term.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        if len(self.short_term) > self.MAX_SHORT_TERM:
            self.short_term.pop(0)

    def get_short_term(self):
        if not self._history_loaded:
            self._load_from_history()
            self._history_loaded = True
        return self.short_term

    def get_short_term_text(self):
        if not self._history_loaded:
            self._load_from_history()
            self._history_loaded = True
        entries = self.short_term[-10:]
        return "\n".join(
            [f"{entry['role']}: {entry['content']}" for entry in entries]
        )

    def add_long_term(self, key, value, agent="System"):
        if not key or not key.strip():
            return
        items = _load_long_term()
        for it in items:
            if it["key"].strip().lower() == key.strip().lower():
                it["value"] = value
                it["timestamp"] = datetime.now().isoformat()
                it["agent"] = agent
                _save_long_term(items)
                return
        items.append({
            "agent": agent,
            "key": key.strip(),
            "value": value,
            "timestamp": datetime.now().isoformat()
        })
        _save_long_term(items)

    def retrieve_long_term(self, query=None, k=10):
        items = _load_long_term()
        if not items:
            return None
        if query:
            query_lower = query.lower()
            relevant = [it for it in items if query_lower in it["key"].lower() or query_lower in it["value"].lower()]
            if relevant:
                return relevant[-k:]
        return items[-k:]

    def get_all_long_term(self):
        return _load_long_term()

    def clear_long_term(self):
        _save_long_term([])

    def add_observation(self, action, summary):
        self._observations.append({
            "action": action,
            "summary": summary[:500],
            "timestamp": datetime.now().isoformat()
        })
        if len(self._observations) > self.MAX_OBSERVATIONS:
            self._observations.pop(0)

    def get_observations_text(self, k=5):
        recent = self._observations[-k:]
        if not recent:
            return ""
        lines = []
        for obs in recent:
            lines.append(f"[{obs['action']}]: {obs['summary']}")
        return "\n".join(lines)

    def _pre_question_short_term(self, before_idx):
        return self.short_term[:before_idx]

    def reset_short_term(self):
        self.short_term.clear()
        self._observations.clear()
        self._history_loaded = self._skip_history

    def reset(self):
        self.short_term.clear()
        self._observations.clear()
        self.clear_long_term()

    def memory_stats(self):
        return {
            "short_term_turns": len(self.short_term),
            "observations": len(self._observations),
            "long_term_docs": len(_load_long_term()),
        }