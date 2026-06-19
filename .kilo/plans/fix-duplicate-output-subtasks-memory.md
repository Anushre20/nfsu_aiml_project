# Issues & Fixes Plan

## Issue 1 — Duplicate Output (`agent.py` + `main.py`)

### Symptoms
- Final answer is printed twice: raw LLM output is printed inside `agent.py`, then the parsed answer is printed again in `main.py`.
- Step-level noise (`STEP=`, `PARSED=`, `TOOL RESULT=`, full LLM dump) is dumped on every ReAct iteration.

### Root Cause
- `agent.py:52-53` unconditionally prints the raw LLM response for every step.
- When the agent finishes (_action == FINISH_) the partial output has already been shown, then `main.py:14-15` prints the same `answer` again.

### Fix
1. Remove the raw LLM print (`agent.py:52-53`) and all step-level debug prints.
2. Keep structured logging behind a `DEBUG` flag so they are opt-in.
3. Ensure `run_agent` returns only the final answer; all intermediate state stays internal.

---

## Issue 2 — Subtask Planning Does Not Work (`agent.py` + `task_planner.py` + `prompts.py`)

### Symptoms
- `TaskPlanner.decompose_task()` returns a list but the ReAct agent ignores it.
- Prompts never show the subtask plan to the model.

### Root Cause
- `prompts.py:60` hard-codes `SYSTEM_PROMPT = BASE_SYSTEM_PROMPT`, so `build_system_prompt()` (which injects subtasks) is **never called**.
- `agent.py:36` passes `SYSTEM_PROMPT` unchanged to the LLM; no subtask context is ever injected.
- `task_planner.py:30-71` calls `self.agent.run(...)` directly as a raw prompt, bypassing the ReAct format entirely, so multi-step tool use never happens.

### Fix
1. Wire subtask injection end-to-end:
   - Call `build_system_prompt(subtasks)` before the first step in `run_agent`.
   - Include the subtask list in every step's prompt so the model can track progress.
2. Fix `TaskPlanner`:
   - Use `build_system_prompt(subtasks)` for every agent call in `execute_plan()`.
   - Pass the running context plus current subtask into the ReAct agent rather than a bare prompt string.
3. Add a completion marker per subtask so `parse_output` can detect step completion, and previse `replan_after_failure()` to preserve partially completed work.

---

## Issue 3 — Memory Implementation (`memory.py`)

### Symptoms
- Long-term memory grows unbounded; no eviction or summarization.
- Retriever silently declines (`return []`) but the calling code joins an empty list into the prompt anyway, producing a useless "Relevant Past Knowledge:" block.

### Root Cause
- `documents` and the FAISS index are never pruned.
- `retrieve_long_term()` returns `[]` when empty instead of a sentinel, making it impossible for the caller to skip the section.
- Fixed dimension `384` is Magic Number; no fallback if the embedder changes.
- No batching or cache for embeddings; every call re-encodes independently.

### Fix
1. Add bounded memory:
   - MAX_LONG_TERM with FIFO eviction (drop oldest when full).
   - Summarize old entries before eviction to preserve coarse signal.
2. Defensive retrieval:
   - Return `None` (not `[]`) on empty store so the caller can omit the section entirely.
   - Return only the top-k non-empty results, deduped.
3. Embedding hygiene:
   - Compute dimension from embedder output shape instead of hard-coding.
   - Batch-encode on `add_long_term` if multiple docs arrive.
4. Optional: expose `reset()` and `memory_stats()` for debugging.
