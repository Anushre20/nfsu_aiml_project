import json
import os
import sys
from datetime import datetime

from flask import Flask, render_template, request, Response, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.core import stream_agent, run_agent, memory as agent_memory
from agent.task_planner import TaskPlanner
from agent.llm import call_llm
from agent.tools import get_workspace, set_workspace


_HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent")
_HISTORY_FILE = os.path.join(_HISTORY_DIR, "chat_history.json")


def _load_history():
    if not os.path.exists(_HISTORY_FILE):
        return {"sessions": []}
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sessions": []}


def _save_history(data):
    os.makedirs(_HISTORY_DIR, exist_ok=True)
    with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class PlannerLLM:
    def __call__(self, prompt):
        return call_llm(prompt)


planner = TaskPlanner(agent=None, llm=PlannerLLM())

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", workspace=get_workspace())


@app.route("/api/workspace", methods=["GET"])
def api_get_workspace():
    return jsonify({"path": get_workspace()})


@app.route("/api/workspace", methods=["POST"])
def api_set_workspace():
    data = request.get_json()
    new_path = data.get("path", "").strip()
    if not new_path:
        return jsonify({"error": "Path is required"}), 400
    result = set_workspace(new_path)
    if result.startswith("Error"):
        return jsonify({"error": result}), 400
    return jsonify({"path": result})


@app.route("/api/memory", methods=["GET"])
def api_get_memory():
    return jsonify({
        "short_term": agent_memory.get_short_term(),
        "long_term": agent_memory.get_all_long_term(),
        "stats": agent_memory.memory_stats(),
    })


@app.route("/api/clear_session", methods=["POST"])
def api_clear_session():
    short_term = agent_memory.get_short_term()
    long_term = agent_memory.get_all_long_term()

    session_summary = ""
    if short_term:
        session_text = "\n".join(
            [f"{e['role']}: {e['content'][:200]}" for e in short_term]
        )
        session_summary = f"Session History:\n{session_text}"

    long_term_text = ""
    if long_term:
        lt_text = "\n".join(
            [f"- [{it['key']}]: {it['value'][:200]}" for it in long_term]
        )
        long_term_text = f"Current Long-Term Memory:\n{lt_text}"

    if session_summary or long_term_text:
        extraction_prompt = f"""Review the session below and extract any useful information about the user's coding habits, preferences, common mistakes, or recurring patterns. Output only the facts worth storing long-term, each on a new line with a key:value format.

{session_summary}

{long_term_text}

Extracted facts to store in long-term memory:
"""
        try:
            facts = call_llm(extraction_prompt)
            if facts and not facts.startswith("Error:"):
                for line in facts.strip().split("\n"):
                    line = line.strip()
                    if ":" in line and len(line) > 3:
                        key, value = line.split(":", 1)
                        agent_memory.add_long_term(key.strip(), value.strip())
        except Exception:
            pass

    agent_memory.reset_short_term()
    return jsonify({"status": "cleared"})


@app.route("/api/memory/long_term", methods=["DELETE"])
def api_clear_long_term():
    agent_memory.clear_long_term()
    return jsonify({"status": "long_term_cleared"})


@app.route("/api/history", methods=["GET"])
def api_get_history():
    data = _load_history()
    sessions = data.get("sessions", [])
    return jsonify({"sessions": sessions})


@app.route("/api/history", methods=["POST"])
def api_save_history():
    body = request.get_json()
    messages = body.get("messages", [])
    session_id = body.get("session_id", "")
    data = _load_history()
    sessions = data.get("sessions", [])

    if session_id:
        for s in sessions:
            if s.get("id") == session_id:
                s["timestamp"] = datetime.now().isoformat()
                s["messages"] = messages
                _save_history(data)
                return jsonify({"status": "updated", "session_id": session_id})
        session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
    else:
        session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")

    session = {
        "id": session_id,
        "timestamp": datetime.now().isoformat(),
        "messages": messages,
    }
    sessions.append(session)
    if len(sessions) > 50:
        sessions = sessions[-50:]
    data["sessions"] = sessions
    _save_history(data)
    return jsonify({"status": "saved", "session_id": session_id})


@app.route("/api/history/clear", methods=["POST"])
def api_clear_history():
    _save_history({"sessions": []})
    return jsonify({"status": "cleared"})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    prompt = data.get("prompt", "").strip()
    resume_from = data.get("resume_from")

    if not resume_from and not prompt:
        return Response(
            json.dumps({"error": "Prompt is required"}), status=400, content_type="application/json"
        )

    ws_path = get_workspace()
    if not os.path.exists(ws_path):
        return Response(
            json.dumps({"error": "Workspace path does not exist. Set a valid directory first."}),
            status=400, content_type="application/json",
        )

    def generate():
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"

        try:
            if resume_from:
                subtasks = resume_from.get("subtasks")
                q = resume_from.get("question", prompt)
                for event in stream_agent(q, subtasks=subtasks, resume_from=resume_from):
                    yield f"data: {json.dumps(event)}\n\n"
            else:
                subtasks = None
                subtask_error = None
                try:
                    subtasks = planner.decompose_task(prompt)
                    yield f"data: {json.dumps({'type': 'subtasks', 'subtasks': subtasks})}\n\n"
                except Exception as e:
                    subtask_error = str(e)
                    yield f"data: {json.dumps({'type': 'subtasks', 'subtasks': [], 'error': subtask_error})}\n\n"

                for event in stream_agent(prompt, subtasks=subtasks):
                    yield f"data: {json.dumps(event)}\n\n"
        except GeneratorExit:
            pass
        except Exception as e:
            yield f"data: {json.dumps({'type': 'done', 'final_answer': f'Server error: {e}', 'steps': []})}\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


if __name__ == "__main__":
    app.run(debug=True, threaded=True, port=5000)