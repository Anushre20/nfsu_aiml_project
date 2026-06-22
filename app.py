import json
import os
import sys

from flask import Flask, render_template, request, Response, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.core import stream_agent, run_agent
from agent.task_planner import TaskPlanner
from agent.llm import call_llm
from agent.tools import get_workspace, set_workspace


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


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
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
        subtasks = None
        try:
            subtasks = planner.decompose_task(prompt)
            yield f"data: {json.dumps({'type': 'subtasks', 'subtasks': subtasks})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'subtasks', 'subtasks': [], 'error': str(e)})}\n\n"

        for event in stream_agent(prompt, subtasks=subtasks):
            yield f"data: {json.dumps(event)}\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


if __name__ == "__main__":
    app.run(debug=True, threaded=True, port=5000)
