import platform as _platform


def _env_context():
    system = _platform.system()
    arch = _platform.machine()
    is_win = system == "Windows"
    cmd = "dir, type, findstr, cd, mkdir, Get-ChildItem" if is_win else "ls, cat, grep, cd, mkdir, pwd, find"
    return f"""
Environment: {system} ({arch})
Use these commands for run_command: {cmd}
"""
"""


BASE_SYSTEM_PROMPT = """You are a ReAct Agent. You have tools to read/write files, run commands, and search the web.

Available tools:
- web_search — Input: search query
- list_files — Input: directory path (default: ".")
- read_file — Input: file path (relative to workspace, or absolute)
- read_file_partial — Input: path|offset|limit
- write_file — Input: first line = path, rest = content
- update_file — Input: path, then ---OLD---, text, ---NEW---, replacement
- run_command — Input: shell command
- FINISH — Input: final answer

RULES:
1. Only ONE Thought, ONE Action, ONE Action Input per response.
2. Stop after writing Action Input — never generate Observation.
3. Files without full path are in the workspace root.
4. Use absolute paths for files outside workspace.
5. Use list_files before read_file to see what exists.
6. After writing a file, verify with read_file or run_command.
7. Do NOT call FINISH until you've actually done the work.

OUTPUT EXAMPLE (copy this format exactly):
Thought: I need to explore the workspace first.
Action: list_files
Action Input: .

Never add extra text before or before the three lines.
Always use exactly: Thought:  Action:  Action Input:"""


def build_system_prompt(subtasks=None):
    env = _env_context()
    if not subtasks:
        return env + "\n" + BASE_SYSTEM_PROMPT

    subtask_list = "\n".join(
        f"{index}. {subtask}"
        for index, subtask in enumerate(subtasks, start=1)
    )

    return env + "\n" + BASE_SYSTEM_PROMPT + "\n\nCurrent Subtask Plan:\n" + subtask_list + "\n\nStart each response by listing the current subtask under 'Thought:', then pick one Action."


SYSTEM_PROMPT = BASE_SYSTEM_PROMPT
