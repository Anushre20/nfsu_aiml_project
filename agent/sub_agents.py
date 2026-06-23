"""Generalized sub-agent for task delegation."""

import platform as _platform

from agent.llm import call_llm
from agent.parser import parse_output
from agent.tools import TOOLS
from agent.log_utils import debug as _debug


def _env_context():
    system = _platform.system()
    arch = _platform.machine()
    is_win = system == "Windows"
    cmd = "dir, type, findstr, cd, mkdir, Get-ChildItem" if is_win else "ls, cat, grep, cd, mkdir, pwd, find"
    return f"Environment: {system} ({arch})\nCommands: {cmd}"


SUB_AGENT_PROMPT_TEMPLATE = """You are an AI assistant with access to the user's local machine.

{env}

Tools:
- list_files — Input: directory path (default: ".")
- read_file — Input: path (relative to workspace, or absolute)
- read_file_partial — Input: path|offset|limit
- write_file — Input: first line = path, rest = content
- update_file — Input: path, then ---OLD---, text, ---NEW---, replacement
- run_command — Input: shell command
- web_search — Input: search query
- FINISH — Input: final result

Rules:
1. ONLY ONE Thought, Action, Action Input per response.
2. Stop after Action Input — never add Observation.
3. Files without full path are in the workspace root.
4. Use absolute paths for files outside workspace.
5. Do NOT call FINISH until you've verified your work.

Example:
Thought: I should list the workspace files first.
Action: run_command
Action Input: dir

Always use exactly: Thought:  Action:  Action Input:"""


def get_sub_agent_prompt(task):
    env = _env_context()
    prompt = SUB_AGENT_PROMPT_TEMPLATE.format(env=env)
    return prompt + "\n\nYour task:\n" + task + "\n\nStart with one Thought and one Action."


class SubAgent:
    def __init__(self, max_steps=6):
        self.max_steps = max_steps

    def run(self, task):
        steps = []
        for step_data, result, is_done in self.run_stream(task):
            steps.append(step_data)
            if is_done:
                return steps, result
        return steps, "Maximum steps reached in sub-agent."

    def run_stream(self, task):
        """Generator that yields (step_data, result_or_None, is_done) for each step."""
        scratchpad = ""
        system_prompt = get_sub_agent_prompt(task)

        for step_num in range(self.max_steps):
            prompt = f"""
{system_prompt}

{scratchpad}
"""

            output = call_llm(prompt)
            _debug("[subagent] LLM output: " + output[:500])
            parsed = parse_output(output)
            _debug("[subagent] parsed: " + str(parsed))
            action = parsed["action"]
            action_input = parsed["action_input"]

            if action == "FINISH":
                step_data = {
                    "thought": parsed["thought"],
                    "action": action,
                    "action_input": action_input,
                    "observation": "Task completed by sub-agent",
                }
                yield step_data, action_input, True
                return

            if action not in TOOLS:
                step_data = {
                    "thought": parsed["thought"],
                    "action": action,
                    "action_input": action_input,
                    "observation": f"Unknown tool: {action}",
                }
                yield step_data, f"Error: Unknown tool {action}", True
                return

            tool_result = TOOLS[action](action_input)

            step_data = {
                "thought": parsed["thought"],
                "action": action,
                "action_input": action_input,
                "observation": str(tool_result),
            }
            yield step_data, None, False

            scratchpad += f"""
    Thought: {parsed['thought']}
    Action: {action}
    Action Input: {action_input}
    Observation: {tool_result}
"""

        # Max steps reached — yield the last step data as final
        last_data = {
            "observation": "Maximum steps reached in sub-agent.",
            "thought": "",
            "action": "FINISH",
            "action_input": "Maximum steps reached in sub-agent.",
        }
        yield last_data, "Maximum steps reached in sub-agent.", True
