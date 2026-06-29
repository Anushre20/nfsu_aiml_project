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


class Memory:

    MAX_SHORT_TERM = 100

    def __init__(self):
        self.short_term = []

    def add_short_term(self, role, content):
        self.short_term.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        if len(self.short_term) > self.MAX_SHORT_TERM:
            self.short_term.pop(0)

    def get_short_term(self):
        return self.short_term

    def get_short_term_text(self):
        return "\n".join(
            [f"{entry['role']}: {entry['content']}" for entry in self.short_term]
        )

    def add_long_term(self, key, value, agent="System"):

        key = str(key).strip()
        value = str(value).strip()

        # ---------- Memory Normalization ----------

        # If the LLM produced only one sentence,
        # automatically infer key/value.

        if key and not value:

            sentence = key

            words = sentence.split()

            if words:

                stop_words = {
                    "remember",
                    "that",
                    "the",
                    "a",
                    "an",
                    "user",
                    "my",
                }

                for word in words:

                    cleaned = word.strip(".,:;()")

                    if cleaned.lower() not in stop_words:

                        key = cleaned

                        break

                value = sentence

        # Final validation

        key = key.strip()
        value = value.strip()

        if not key or not value:
            return False
        bad_keys = {

            "remember",

            "that",

            "this",

            "it",

            "information",

            "fact",

        }

        if key.lower() in bad_keys:
            return False
        items = _load_long_term()

        # Duplicate check
        for item in items:
            if (
                item.get("key", "").strip().lower() == key.lower()
                and
                item.get("value", "").strip().lower() == value.lower()
            ):
                return False

        items.append({
            "agent": agent,
            "key": key,
            "value": value,
            "timestamp": datetime.now().isoformat()
        })

        _save_long_term(items)

        return True

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

    def reset_short_term(self):
        self.short_term.clear()

    def reset(self):
        self.short_term.clear()
        self.clear_long_term()

    def memory_stats(self):
        return {
            "short_term_turns": len(self.short_term),
            "long_term_docs": len(_load_long_term()),
        }