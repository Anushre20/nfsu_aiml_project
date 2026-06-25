import platform as _platform
from queue import Queue
from threading import Thread

from agent.llm import call_llm
from agent.parser import parse_output
from agent.tools import TOOLS
from agent.log_utils import debug as _debug


_MAX_DEPTH = 3


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
- list_files_recursive — Input: directory path. Recursively lists all files.
- read_file — Input: path (relative to workspace, or absolute)
- read_file_partial — Input: path|offset|limit
- write_file — Input: first line = path, rest = content
- update_file — Input: path, then ---OLD---, text, ---NEW---, replacement
- run_command — Input: shell command
- web_search — Input: search query
- delegate — Input: task description for a sub-agent
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


def get_sub_agent_prompt(task, depth=1):
    env = _env_context()
    return SUB_AGENT_PROMPT_TEMPLATE.format(env=env) + "\n\nYour task:\n" + task + "\n\nStart with one Thought and one Action."


_SUBAGENT_MAX_STEPS = 200


def run_subagent(task, depth=1, max_steps=_SUBAGENT_MAX_STEPS):
    steps = []
    for step_data, result, is_done in run_subagent_stream(task, depth, max_steps):
        steps.append(step_data)
        if is_done:
            return result
    return "Maximum steps reached in sub-agent."


def run_subagent_stream(task, depth=1, max_steps=_SUBAGENT_MAX_STEPS):
    scratchpad = ""
    system_prompt = get_sub_agent_prompt(task, depth)

    for step_num in range(max_steps):
        prompt = system_prompt + "\n\n" + scratchpad

        output = call_llm(prompt)
        _debug(f"[subagent depth={depth}] LLM output: " + output[:500])
        parsed = parse_output(output)
        _debug(f"[subagent depth={depth}] parsed: " + str(parsed))
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

        if action == "delegate":
            if depth >= _MAX_DEPTH:
                result = f"Cannot delegate further: max depth {_MAX_DEPTH} reached."
            else:
                result = run_subagent(action_input, depth=depth + 1, max_steps=max_steps)
            step_data = {
                "thought": parsed["thought"],
                "action": action,
                "action_input": action_input,
                "observation": str(result),
            }
            yield step_data, None, False
            scratchpad += f"\nThought: {parsed['thought']}\nAction: {action}\nAction Input: {action_input}\nObservation: {result}"
            continue

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

        scratchpad += f"\nThought: {parsed['thought']}\nAction: {action}\nAction Input: {action_input}\nObservation: {tool_result}"

    last_data = {
        "observation": "Maximum steps reached in sub-agent.",
        "thought": "",
        "action": "FINISH",
        "action_input": "Maximum steps reached in sub-agent.",
    }
    yield last_data, "Maximum steps reached in sub-agent.", True


def _run_single_subagent(task, depth, agent_idx, total, queue, max_steps=_SUBAGENT_MAX_STEPS):
    try:
        for sub_step, sub_result, is_done in run_subagent_stream(task, depth=depth, max_steps=max_steps):
            queue.put({
                "type": "sub_step",
                "agent_idx": agent_idx,
                "total": total,
                "depth": depth,
                "sub_step": sub_step,
            })
            if is_done:
                queue.put({
                    "type": "sub_done",
                    "agent_idx": agent_idx,
                    "total": total,
                    "depth": depth,
                    "result": str(sub_result) if sub_result else "Completed.",
                })
                return
    except Exception as e:
        _debug(f"[subagent parallel depth={depth} agent={agent_idx}] error: {e}")
        queue.put({
            "type": "sub_error",
            "agent_idx": agent_idx,
            "total": total,
            "depth": depth,
            "error": str(e),
        })


def run_subagents_parallel(tasks, depth=1, max_steps=_SUBAGENT_MAX_STEPS):
    """Run multiple sub-agent tasks in parallel with isolated scratchpads.
    Yields dicts with agent_idx, total, depth, and event data for each step.
    """
    if not tasks:
        return

    queue = Queue()
    threads = []

    for i, task in enumerate(tasks):
        t = Thread(target=_run_single_subagent, args=(task, depth, i, len(tasks), queue, max_steps))
        t.start()
        threads.append(t)

    completed = 0
    total = len(tasks)
    results = [None] * total

    while completed < total:
        event = queue.get()
        yield event
        if event["type"] in ("sub_done", "sub_error"):
            agent_idx = event["agent_idx"]
            if event["type"] == "sub_done":
                results[agent_idx] = event["result"]
            else:
                results[agent_idx] = f"Error: {event['error']}"
            completed += 1

    for t in threads:
        t.join()

    for i, task in enumerate(tasks):
        yield {
            "type": "sub_final",
            "agent_idx": i,
            "total": total,
            "depth": depth,
            "task": task,
            "result": results[i] if results[i] else "Completed.",
        }