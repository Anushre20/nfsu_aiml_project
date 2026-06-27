import json
import os
import subprocess as _subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from ddgs import DDGS

_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# ---------------- FILE CACHE ----------------

_FILE_CACHE = {}

def clear_file_cache():
    _FILE_CACHE.clear()

# --------------------------------------------


def get_workspace():
    return str(_WORKSPACE_ROOT)


def set_workspace(path):
    global _WORKSPACE_ROOT
    new_path = Path(path).resolve()
    _WORKSPACE_ROOT = new_path
    clear_file_cache()
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


def _resolve_path(path):
    p = Path(path)
    if p.is_absolute():
        return p.resolve(), True
    full = (_WORKSPACE_ROOT / path).resolve()
    if not str(full).startswith(str(_WORKSPACE_ROOT)):
        return full, False
    return full, True


def read_file(path):
    try:
        full_path, allowed = _resolve_path(path)
        cache_key = str(full_path.resolve())

        if cache_key in _FILE_CACHE:
            return _FILE_CACHE[cache_key]
        if not allowed:
            return "Error: Path is outside the workspace."
        if not full_path.exists():
            return f"Error: File not found: {path}"
        if not full_path.is_file():
            return f"Error: Not a file: {path}"
        content = full_path.read_text(encoding="utf-8")
        _FILE_CACHE[cache_key] = content
        return content
    except Exception as e:
        return f"Read Error: {e}"

def batch_read_files(raw_input):
    """
    Input:
        one file path per line

    Output:
        concatenated contents
    """

    paths = [
        p.strip()
        for p in raw_input.splitlines()
        if p.strip()
    ]

    if not paths:
        return "Error: No file paths provided."

    def _read(path):
        return path, read_file(path)

    with ThreadPoolExecutor(
            max_workers=min(4, len(paths))
    ) as executor:

        results = list(
            executor.map(_read, paths)
        )

    outputs = []

    for path, result in results:

        outputs.append(
            f"\n{'='*25}\n"
            f"{path}\n"
            f"{'='*25}\n"
            f"{result}"
        )

    return "\n".join(outputs)

def read_file_partial(path, offset=0, limit=None):
    try:
        if limit is None and isinstance(path, str) and "|" in path:
            parts = path.split("|", 2)
            path = parts[0].strip()
            offset = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0
            limit = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else None
        full_path, allowed = _resolve_path(path)
        cache_key = str(full_path.resolve())
        if not allowed:
            return "Error: Path is outside the workspace."
        if not full_path.exists():
            return f"Error: File not found: {path}"
        if not full_path.is_file():
            return f"Error: Not a file: {path}"
        if cache_key not in _FILE_CACHE:
            _FILE_CACHE[cache_key] = full_path.read_text(
                encoding="utf-8"
            )

        lines = _FILE_CACHE[cache_key].splitlines(keepends=True)
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
        full_path, allowed = _resolve_path(path)
        if not allowed:
            return "Error: Path is outside the workspace."
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        _FILE_CACHE[str(full_path.resolve())] = content
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
        full_path, allowed = _resolve_path(path)
        if not allowed:
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
        _FILE_CACHE[str(full_path.resolve())] = new_content
        return f"Successfully updated {path} ({len(new_content)} bytes written)"
    except Exception as e:
        return f"Update Error: {e}"


def list_files(path="."):
    try:
        full_path, allowed = _resolve_path(path)
        if not allowed:
            return "Error: Path is outside the workspace."
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


def list_files_recursive(path="."):
    try:
        full_path, allowed = _resolve_path(path)
        if not allowed:
            return "Error: Path is outside the workspace."
        if not full_path.exists():
            return f"Error: Path not found: {path}"
        items = []
        for root, dirs, files in os.walk(str(full_path)):
            rel = os.path.relpath(root, str(_WORKSPACE_ROOT))
            if rel == ".":
                rel = ""
            for d in sorted(dirs):
                items.append(f"[DIR] {os.path.join(rel, d)}")
            for f in sorted(files):
                items.append(f"[FILE] {os.path.join(rel, f)}")
        return "\n".join(items)
    except Exception as e:
        return f"ListRecursive Error: {e}"


def run_command(command):
    try:
        result = _subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_WORKSPACE_ROOT),
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

TOOLS = {
     "web_search": web_search,
     "list_files": list_files,
     "list_files_recursive": list_files_recursive,
     "read_file": read_file,
     "batch_read_files": batch_read_files,
     "read_file_partial": read_file_partial,
     "write_file": write_file,
     "update_file": update_file,
     "run_command": run_command,
}
