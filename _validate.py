"""Final validation script."""
import sys, os, ast

passed = 0
failed = 0

def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        marker = f"  --> {detail}" if detail else ""
        print(f"  FAIL  {label}{marker}")

# --- syntax ---
files = ["agent/__init__.py","agent/core.py","agent/sub_agents.py",
         "agent/task_planner.py","agent/llm.py","agent/memory.py",
         "agent/parser.py","agent/prompts.py","agent/tools.py","app.py","main.py"]
for f in files:
    ast.parse(open(f).read())
check("all files syntax OK", True)

# --- import chain ---
from agent.tools import get_workspace, set_workspace, read_file, read_file_partial, update_file, list_files, TOOLS
check("tools import", True)

from agent.llm import call_llm
check("llm import", True)

from agent.sub_agents import SubAgent
check("sub_agents import", True)

from agent.task_planner import TaskPlanner
check("task_planner import", True)

from agent.memory import Memory
check("memory import", True)

from agent.core import run_agent, stream_agent, memory
check("core import", True)

from agent.parser import parse_output
check("parser import", True)

# --- new tools in TOOLS ---
check("list_files in TOOLS", "list_files" in TOOLS)
check("read_file_partial in TOOLS", "read_file_partial" in TOOLS)
check("update_file in TOOLS", "update_file" in TOOLS)
check("7 tools registered", len(TOOLS) == 7, f"got {len(TOOLS)}")

# --- memory reset ---
m = Memory()
m.add_short_term("user", "hello")
assert len(m.get_short_term()) == 1
m.reset_short_term()
assert len(m.get_short_term()) == 0
check("memory.reset_short_term works", True)

# --- SubAgent without agent_type ---
sa = SubAgent()
assert sa.max_steps == 6
check("SubAgent no agent_type required", True)

# --- read_file_partial ---
with open(".test_partial.txt","w") as f: f.write("a\nb\nc\nd\ne\n")
r = read_file_partial(".test_partial.txt", 1, 3)
ok = "b" in r and "c" in r and "d" in r and "a" not in r.split("}")[1]
os.remove(".test_partial.txt")
check("read_file_partial offset+limit works", ok, r[:60])

with open(".test_pipe.txt","w") as f: f.write("line0\nline1\nline2\n")
r2 = read_file_partial(".test_pipe.txt|1|2")
ok2 = "line1" in r2 and "line2" in r2 and "line0" not in r2.split("}")[1]
os.remove(".test_pipe.txt")
check("read_file_partial pipe input works", ok2, r2[:60])

# --- list_files ---
lf = list_files(".")
check("list_files returns entries", lf.startswith("[FILE]") or lf.startswith("[DIR]"), lf[:80])

# --- read_file absolute path support ---
import tempfile
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tf:
    tf.write("absolute path test")
    tf_path = tf.name
r3 = read_file(tf_path)
ok3 = r3 == "absolute path test"
os.remove(tf_path)
check("read_file absolute path works", ok3, r3[:60])

# --- update_file ---
with open(".test_upd.txt","w") as f: f.write("hello world\nfoo bar\n")
r = update_file(".test_upd.txt\n---OLD---\nhello world\n---NEW---\nhi there")
assert "Successfully" in r, r
with open(".test_upd.txt") as f: assert f.read() == "hi there\nfoo bar\n"
os.remove(".test_upd.txt")
check("update_file replaces text", True)

# --- workspace validation ---
orig = get_workspace()
set_workspace("/nonexistent/path")
check("ws becomes nonexistent", not os.path.exists(get_workspace()))
set_workspace(orig)
check("ws restored to valid", os.path.exists(get_workspace()))

# --- parser ---
p = parse_output("Thought: a\nAction: FINISH\nAction Input:")
check("parser empty action_input", p["action_input"] == "")
p2 = parse_output("garbage")
check("parser defaults to FINISH", p2["action"] == "FINISH")
p3 = parse_output("Thought: The Action: keyword is fine now\nAction: read_file\nAction Input: main.py")
check("parser handles Action: in thought", p3["thought"] == "The Action: keyword is fine now" and p3["action"] == "read_file")
p4 = parse_output("Thought: a\nAction: FINISH\nAction Input: some\nAction Input: not parsed")
check("parser takes first Action Input only", p4["action_input"] == "some")

# --- Flask API ---
from app import app
check("flask app import", True)

with app.test_client() as c:
    r = c.get("/api/workspace")
    check("GET /api/workspace returns 200", r.status_code == 200)

    r2 = c.post("/api/workspace", json={"path": "/nonexistent/xyz"})
    check("POST bad path returns 400", r2.status_code == 400)

    r3 = c.post("/api/workspace", json={"path": orig})
    check("POST good path returns 200", r3.status_code == 200)

    set_workspace("/nonexistent/path")
    r4 = c.post("/api/chat", json={"prompt": "hello"})
    check("chat blocked on bad ws", r4.status_code == 400)

    set_workspace(orig)
    r5 = c.post("/api/chat", json={"prompt": "hello"})
    check("chat allowed on good ws", r5.status_code == 200)

# --- template ---
with open("templates/index.html") as f:
    html = f.read()
for kw in ["wsLockMsg","backdrop-filter","wsError","linear-gradient"]:
    check(f"template has '{kw}'", kw in html)

print(f"\n{'='*40}")
print(f"  PASSED: {passed}  FAILED: {failed}")
print(f"{'='*40}")
sys.exit(0 if failed == 0 else 1)
