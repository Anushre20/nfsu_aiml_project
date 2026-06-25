# ReAct Agent

A ReAct (Reasoning + Acting) AI agent that reads, writes, and executes code on your local machine via cloud-hosted LLMs.

## Architecture

```
User → Flask SSE Server → Agent Loop (core.py) → LLM (ollama cloud)
                          ↓
                    Tools (tools.py)
                    ├── read_file / read_file_partial
                    ├── write_file / update_file
                    ├── list_files
                    ├── run_command
                    └── web_search
```

## Agent Loop (ReAct)

1. **Thought** — LLM reasons about the next step
2. **Action** — LLM picks a tool name
3. **Action Input** — tool arguments
4. **Observation** — system runs the tool, appends result
5. Repeat until `FINISH`

All steps stream to the web UI in real time via SSE.

## Memory System

**Short-term memory**: sliding-window list of `(role, content)` tuples. Default `max_turns=6`. On each turn the new entry is appended; when the window fills, the oldest entry is dropped (FIFO).

**Long-term memory**: sliding-window list of text strings. Default `MAX_DOCS=50`. Works the same way — append until full, then evict oldest. `retrieve_long_term(query, k=3)` returns the last `k` documents by insertion order only; no semantic/vector search is performed.

The original design used `sentence-transformers` + `faiss` for cosine-similarity retrieval, but both were removed to keep dependencies minimal (~3 packages: `ollama`, `ddgs`, `flask`).

## Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read a file from disk |
| `read_file_partial` | Read a portion of a file (offset+limit) |
| `write_file` | Create/overwrite a file |
| `update_file` | Find-and-replace edit on a file |
| `list_files` | List workspace contents |
| `run_command` | Execute shell commands |
| `web_search` | Search the web via DuckDuckGo |
| `FINISH` | Produce final answer |

## Setup

```bash
pip install -r requirements.txt
python app.py
```

The agent connects to a cloud ollama model at `http://localhost:11434` (model: `minimax-m2.5:cloud`).

## Validation

```bash
python _validate.py
```

35 tests covering tools, parser, memory, subagents, Flask endpoints, and template rendering.
