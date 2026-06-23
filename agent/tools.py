import json
import os
import subprocess as _subprocess
from pathlib import Path

from ddgs import DDGS

_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


def get_workspace():
    return str(_WORKSPACE_ROOT)


def set_workspace(path):
    global _WORKSPACE_ROOT
    new_path = Path(path).resolve()
    _WORKSPACE_ROOT = new_path
    if not new_path.exists():
        return f"Error: Path does not exist: {path}"
    return get_workspace()


def web_search(query):
    snippets = []
    try:
        with DDGS() as ddgs:
             results = ddgs.text(query, max_results=3)
             for result in results:
                  snippets.append(result.get("body", ""))
        return "\n".join(snippets)
    except Exception as e:
        return f"Search Error: {e}"


def read_file(path):
    try:
        full_path = (_WORKSPACE_ROOT / path).resolve()

        print("\nDEBUG READ")
        print("WORKSPACE =", _WORKSPACE_ROOT)
        print("REQUESTED =", path)
        print("FULL PATH =", full_path)
        if not str(full_path).startswith(str(_WORKSPACE_ROOT)):
            return "Error: Path is outside the workspace."
        if not full_path.exists():
            return f"Error: File not found: {path}"
        if not full_path.is_file():
            return f"Error: Not a file: {path}"
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Read Error: {e}"


def read_file_partial(path, offset=0, limit=None):
    try:
        full_path = (_WORKSPACE_ROOT / path).resolve()
        if not str(full_path).startswith(str(_WORKSPACE_ROOT)):
            return "Error: Path is outside the workspace."
        if not full_path.exists():
            return f"Error: File not found: {path}"
        if not full_path.is_file():
            return f"Error: Not a file: {path}"
        lines = full_path.read_text(encoding="utf-8").splitlines(keepends=True)
        total = len(lines)
        if offset < 0:
            offset = 0
        if limit is None:
            limit = total - offset
        selected = lines[offset:offset + limit]
        result = "".join(selected)
        meta = f"{{lines {offset + 1}-{offset + len(selected)} of {total}}}"
        return f"{meta}\n{result}"
    except Exception as e:
        return f"ReadPartial Error: {e}"


def write_file(raw_input):
    path = None
    content = None

    try:
        parsed = json.loads(raw_input)
        path = parsed.get("path")
        content = parsed.get("content")
    except (json.JSONDecodeError, KeyError, TypeError):
        path = None

    if path is None or content is None:
        lines = raw_input.splitlines()
        if lines:
            path = lines[0].strip()
            content = "\n".join(lines[1:])

    if not path or content is None:
        return "Error: write_file requires first line as file path, remaining lines as content."

    try:
        full_path = (_WORKSPACE_ROOT / path).resolve()
        if not str(full_path).startswith(str(_WORKSPACE_ROOT)):
            return "Error: Path is outside the workspace."
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Write Error: {e}"


def update_file(raw_input):
    lines = raw_input.splitlines()
    if not lines:
        return "Error: update_file requires path, old_string, new_string"
    path = lines[0].strip()
    rest = "\n".join(lines[1:])

    sep_old = "---OLD---\n"
    sep_new = "\n---NEW---\n"
    idx_old = rest.find(sep_old)
    if idx_old < 0:
        return "Error: update_file format: <path>\\n---OLD---\\n<old text>\\n---NEW---\\n<new text>"
    after_old = rest[idx_old + len(sep_old):]
    idx_new = after_old.find(sep_new)
    if idx_new < 0:
        return "Error: update_file format: <path>\\n---OLD---\\n<old text>\\n---NEW---\\n<new text>"

    old_string = after_old[:idx_new]
    new_string = after_old[idx_new + len(sep_new):]

    try:
        full_path = (_WORKSPACE_ROOT / path).resolve()
        if not str(full_path).startswith(str(_WORKSPACE_ROOT)):
            return "Error: Path is outside the workspace."
        if not full_path.exists():
            return f"Error: File not found: {path}"
        content = full_path.read_text(encoding="utf-8")
        if old_string not in content:
            return f"Error: old_string not found in {path}"
        count = content.count(old_string)
        if count > 1:
            return f"Error: Found {count} matches for old_string in {path}. Provide more context to identify the correct match."
        new_content = content.replace(old_string, new_string, 1)
        full_path.write_text(new_content, encoding="utf-8")
        return f"Successfully updated {path} ({len(new_content)} bytes written)"
    except Exception as e:
        return f"Update Error: {e}"


def run_command(command):
    try:
        result = _subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=_WORKSPACE_ROOT,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr
        return output or f"Command completed with exit code {result.returncode}"
    except _subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Command Error: {e}"

def list_files(path="."):
    try:
        full_path = (_WORKSPACE_ROOT / path).resolve()

        if not str(full_path).startswith(str(_WORKSPACE_ROOT)):
            return "Error: Path is outside workspace."

        if not full_path.exists():
            return f"Error: Path not found: {path}"

        items = []

        for item in sorted(full_path.iterdir()):
            if item.is_dir():
                items.append(f"[DIR] {item.name}")
            else:
                items.append(f"[FILE] {item.name}")

        return "\n".join(items)

    except Exception as e:
        return f"List Error: {e}"

TOOLS = {
     "web_search": web_search,
     "list_files": list_files,
     "read_file": read_file,
     "read_file_partial": read_file_partial,
     "write_file": write_file,
     "update_file": update_file,
     "run_command": run_command,
}
