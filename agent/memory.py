class Memory:

    MAX_DOCS = 50

    def __init__(self, max_turns=6):
        self.max_turns = max_turns
        self.short_term = []
        self.long_term_docs = []

    def add_short_term(self, role, content):
        self.short_term.append((role, content))
        if len(self.short_term) > self.max_turns:
            self.short_term.pop(0)

    def get_short_term(self):
        return self.short_term

    def add_long_term(self, text):
        self.long_term_docs.append(text)
        if len(self.long_term_docs) > self.MAX_DOCS:
            self.long_term_docs.pop(0)

    def retrieve_long_term(self, query, k=3):
        if not self.long_term_docs:
            return None
        return self.long_term_docs[-k:]

    def reset_short_term(self):
        self.short_term.clear()

    def reset(self):
        self.short_term.clear()
        self.long_term_docs.clear()

    def memory_stats(self):
        return {
            "short_term_turns": len(self.short_term),
            "long_term_docs": len(self.long_term_docs),
            "max_docs": self.MAX_DOCS,
            "max_turns": self.max_turns,
        }
