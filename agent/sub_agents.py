"""Generalized sub-agent for task delegation."""

from agent.llm import call_llm
from agent.parser import parse_output
from agent.tools import TOOLS

SUB_AGENT_PROMPT = """
You are an AI assistant with access to the user's local machine.

You can:
- Read, write, and update files in the workspace
- Execute shell commands
- Search the web

Always follow this format:
Thought: your reasoning
Action: tool_name
Action Input: input for the tool

Stop after Action Input. Do not generate an Observation — it will be added by the system.

Available tools:
- read_file  — read a file from the workspace. Input: relative file path
- read_file_partial — read a file with line offset and limit. Input: <path>|<offset>|<limit>
- write_file — write content to a file. Input: first line = path, rest = content
- update_file — replace specific text in a file. Input: first line = path, then ---OLD---\\n<old>\\n---NEW---\\n<new>
- run_command — execute a shell command. Input: command string
- web_search — search the web. Input: search query
- FINISH — submit final answer. Input: final result

Finish with FINISH when the task is complete.
"""


def get_sub_agent_prompt(task):
    return f"""{SUB_AGENT_PROMPT}

Your task:
{task}

Remember: Generate ONLY ONE Thought and ONE Action per response.
Stop after Action Input. Do not generate Observation.
"""


class SubAgent:
    def __init__(self, max_steps=6):
        self.max_steps = max_steps

    def run(self, task):
        steps = []
        scratchpad = ""
        system_prompt = get_sub_agent_prompt(task)

        for _ in range(self.max_steps):
            prompt = f"""
{system_prompt}

{scratchpad}
"""

            output = call_llm(prompt)
            parsed = parse_output(output)
            action = parsed["action"]
            action_input = parsed["action_input"]

            if action == "FINISH":
                steps.append({
                    "thought": parsed["thought"],
                    "action": action,
                    "action_input": action_input,
                    "observation": "Task completed by sub-agent",
                })
                return steps, action_input

            if action not in TOOLS:
                steps.append({
                    "thought": parsed["thought"],
                    "action": action,
                    "action_input": action_input,
                    "observation": f"Unknown tool: {action}",
                })
                return steps, f"Error: Unknown tool {action}"

            tool_result = TOOLS[action](action_input)

            steps.append({
                "thought": parsed["thought"],
                "action": action,
                "action_input": action_input,
                "observation": str(tool_result),
            })

            scratchpad += f"""
    Thought: {parsed['thought']}
    Action: {action}
    Action Input: {action_input}
    Observation: {tool_result}
"""

        return steps, "Maximum steps reached in sub-agent."
