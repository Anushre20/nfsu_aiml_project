#!/usr/bin/env python3
"""
CLI script to evaluate a trajectory using the judge model API.
Invoked by opencode or the orchestrator after a build completes.

Usage:
    python scripts/judge_eval.py --trajectory <path> [--api-url <url>] [--output <path>]

Returns:
    JSON object with scores, evaluation, and pass/fail to stdout.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests not installed. pip install requests"}), file=sys.stderr)
    sys.exit(1)


def load_trajectory(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_workspace_files(workspace_dir, max_files=30):
    """Collect file tree and contents from a workspace directory."""
    result = {}
    workspace = Path(workspace_dir)
    if not workspace.exists():
        return {"error": "Workspace directory does not exist"}

    for path in sorted(workspace.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            rel = str(path.relative_to(workspace))
            try:
                size = path.stat().st_size
                if size > 50000:
                    result[rel] = f"[{size} bytes - truncated]"
                else:
                    result[rel] = path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                result[rel] = f"[read error: {e}]"

        if len(result) >= max_files:
            break

    return result


def build_judge_prompt(trajectory, workspace_files):
    """Build the evaluation prompt for the judge model."""
    task = trajectory.get("task_description", trajectory.get("task", "Unknown task"))
    build_output = trajectory.get("build_output", trajectory.get("test_output", ""))

    steps = trajectory.get("steps", [])
    trajectory_text = []
    for i, step in enumerate(steps):
        thought = step.get("thought", step.get("Thought", ""))
        action = step.get("action", step.get("Action", ""))
        action_input = step.get("action_input", step.get("Action Input", ""))
        obs = step.get("observation", step.get("Observation", ""))
        trajectory_text.append(f"Step {i+1}:")
        if thought:
            trajectory_text.append(f"  Thought: {thought}")
        trajectory_text.append(f"  Action: {action}")
        trajectory_text.append(f"  Action Input: {action_input}")
        if obs:
            trajectory_text.append(f"  Observation: {obs[:300]}")
    trajectory_str = "\n".join(trajectory_text)

    files_str = json.dumps(workspace_files, indent=2)[:3000]

    prompt = f"""You are a strict technical evaluator for a coding AI assistant. Evaluate the following trajectory where an AI agent attempted to complete a software development task.

Evaluate on these criteria (1-10 scale each):
1. **Correctness** — Does the solution actually work? Are there bugs?
2. **Completeness** — Were all requirements met?
3. **Code Quality** — Is the code clean, well-structured, idiomatic?
4. **Efficiency** — Is the approach efficient and appropriate?
5. **Process** — Did the agent explore properly before writing code? Did it verify its work?

Task:
{task}

Trajectory:
{trajectory_str}

Workspace files after completion:
{files_str}

Build/test output:
{build_output}

Return ONLY a valid JSON object with no other text:
{{{{
  "scores": {{{{
    "correctness": <int 1-10>,
    "completeness": <int 1-10>,
    "code_quality": <int 1-10>,
    "efficiency": <int 1-10>,
    "process": <int 1-10>
  }}}},
  "overall": <float 1.0-10.0>,
  "passed": <true/false>,
  "summary": "<2-3 sentence evaluation>",
  "critical_issues": ["<issue1>", "<issue2>"],
  "suggestions": ["<suggestion1>", "<suggestion2>"]
}}}}
"""
    return prompt


def call_judge_api(prompt, api_url, model="deepseek-r1-distill-70b", max_retries=3):
    """Call the judge model API with retry logic."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=180)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # Extract JSON from response (handles markdown wrapping)
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                if content.startswith("json"):
                    content = content[4:].strip()
                return json.loads(content)
            else:
                print(f"  API returned {resp.status_code}, retrying...", file=sys.stderr)
                time.sleep(2 ** attempt)
        except Exception as e:
            print(f"  API call failed: {e}, retrying...", file=sys.stderr)
            time.sleep(2 ** attempt)

    return {
        "error": f"Judge API failed after {max_retries} retries",
        "scores": {"correctness": 0, "completeness": 0, "code_quality": 0, "efficiency": 0, "process": 0},
        "overall": 0.0,
        "passed": False,
        "summary": "Evaluation failed - API unreachable",
        "critical_issues": ["Judge API unavailable"],
        "suggestions": []
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate a trajectory using the judge model")
    parser.add_argument("--trajectory", "-t", required=True, help="Path to trajectory JSON file")
    parser.add_argument("--api-url", "-u", default="http://127.0.0.1:8081/v1/chat/completions",
                        help="Judge API URL (OpenAI-compatible)")
    parser.add_argument("--model", "-m", default="deepseek-r1-distill-70b",
                        help="Model name for the API")
    parser.add_argument("--output", "-o", help="Output file for evaluation JSON (optional)")
    parser.add_argument("--workspace", "-w", help="Workspace directory to collect files from")
    args = parser.parse_args()

    if not os.path.exists(args.trajectory):
        print(json.dumps({"error": f"Trajectory file not found: {args.trajectory}"}))
        sys.exit(1)

    trajectory = load_trajectory(args.trajectory)

    workspace_files = {}
    ws_dir = args.workspace or trajectory.get("workspace_dir", "")
    if ws_dir and os.path.exists(ws_dir):
        workspace_files = collect_workspace_files(ws_dir)

    prompt = build_judge_prompt(trajectory, workspace_files)

    result = call_judge_api(prompt, args.api_url, args.model)

    result["trajectory_file"] = args.trajectory
    result["trajectory_id"] = trajectory.get("id", trajectory.get("task_id", "unknown"))
    result["task"] = trajectory.get("task_description", trajectory.get("task", ""))

    output = json.dumps(result, indent=2)
    print(output)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)


if __name__ == "__main__":
    main()
