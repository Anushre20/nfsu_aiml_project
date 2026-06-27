import re
from typing import Any
from agent.log_utils import debug as _debug


class TaskPlanner:
    def __init__(self, agent: Any, llm: Any, enable_replanning: bool = False):
        self.agent = agent
        self.llm = llm
        self.enable_replanning = enable_replanning

    def decompose_task(self, query: str) -> list[str]:
        prompt = f"""You are an expert task planner for a ReAct AI agent.

Your job is to break the user's request into the SMALLEST NUMBER of meaningful executable subtasks.

Rules:

1. Output ONLY numbered tasks.
2. One task per line.
3. Prefer module-level subtasks instead of file-level subtasks.
4. Never create one subtask per file unless absolutely necessary.
5. Group related work together.
6. If several files belong to one logical component, create ONE subtask for that component.
7. Independent components should become separate subtasks because they may execute in parallel.
8. Dependent work should remain sequential.
9. Prefer 3–6 subtasks for large projects.
10. Prefer a single task for simple questions.

Examples:

User:
Explain this Python repository.

Good:

1. Analyze the backend architecture.
2. Analyze the frontend architecture.
3. Analyze configuration and entry points.
4. Produce the final explanation.

Bad:

1. Read app.py
2. Read core.py
3. Read llm.py
4. Read parser.py
5. Read prompts.py
6. Read tools.py

User Request:
{query}
"""

        output = self._call_llm(prompt)
        tasks = self._parse_numbered_list(output)

        if not tasks:
            return [query]

        # Prevent over-decomposition
        if len(tasks) > 6:
            tasks = tasks[:6]

        return tasks

    def execute_plan(self, query: str) -> str:
        if self.agent is None:
            raise ValueError("agent is not set — cannot execute plan")

        subtasks = self.decompose_task(query)
        completed: list[tuple[str, str]] = []
        running_context = ""
        index = 0

        while index < len(subtasks):
            subtask = subtasks[index]
            agent_prompt = f"""
Context:
{running_context}

Current Task:
{subtask}
"""

            agent_result = self.agent.run(agent_prompt)
            result = agent_result if isinstance(agent_result, str) else agent_result.get("final_answer", str(agent_result))

            if self._task_failed(result) and self.enable_replanning:
                remaining = self.replan_after_failure(
                    query=query,
                    completed=completed,
                    failed=subtask,
                )
                subtasks = subtasks[:index] + remaining
                if not remaining:
                    break
                continue

            result = result or ""
            completed.append((subtask, result))
            running_context = self._format_completed_results(completed)
            index += 1

        subtask_results = self._format_completed_results(completed)
        synthesis_prompt = f"""You are an AI assistant.

Using the completed subtask results below, provide a final coherent answer.

{subtask_results}"""

        return self._call_llm(synthesis_prompt)

    def replan_after_failure(
        self,
        query: str,
        completed: list[tuple[str, str]],
        failed: str,
    ) -> list[str]:
        completed_text = self._format_completed_results(completed)
        prompt = f"""The following plan partially failed.

Original query:
{query}

Completed tasks:
{completed_text}

Failed task:
{failed}

Generate a revised list of remaining tasks only.

Output numbered tasks only."""

        return self._parse_numbered_list(self._call_llm(prompt))

    def _call_llm(self, prompt: str) -> str:
        if callable(self.llm):
            result = str(self.llm(prompt))
            _debug("[planner] output: " + result[:500])
            return result
        if hasattr(self.llm, "call"):
            result = str(self.llm.call(prompt))
            _debug("[planner] output: " + result[:500])
            return result
        if hasattr(self.llm, "run"):
            result = str(self.llm.run(prompt))
            _debug("[planner] output: " + result[:500])
            return result
        raise TypeError("llm must be callable or expose call()/run().")

    def _parse_numbered_list(self, text: str) -> list[str]:
        return [
            match.strip()
            for match in re.findall(r"^\s*\d+[\.)]\s+(.+?)\s*$", text, re.MULTILINE)
            if match.strip()
        ]

    def _format_completed_results(self, completed: list[tuple[str, str]]) -> str:
        blocks = []
        for index, (task, result) in enumerate(completed, start=1):
            blocks.append(f"Task {index}:\n{task}\nResult:\n{result}")
        return "Previous Results:\n" + "\n\n".join(blocks) if blocks else "Previous Results:"

    def _task_failed(self, result: str | None) -> bool:
        return not result or "MAX_STEPS_REACHED" in result
