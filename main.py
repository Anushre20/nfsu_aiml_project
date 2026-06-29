import sys
import shutil

from agent.core import run_agent, stream_agent, memory as agent_memory
from agent.task_planner import TaskPlanner


class PlannerLLM:
    def __call__(self, prompt):
        from agent.llm import call_llm
        return call_llm(prompt)


TERM_WIDTH = shutil.get_terminal_size().columns


def sep(char="="):
    print(char * min(TERM_WIDTH, 72))


def print_step(step_data):
    t = step_data.get("thought", "")
    a = step_data.get("action", "")
    ai = step_data.get("action_input", "")
    o = step_data.get("observation", "")
    if t:
        print(f"  Thought:  {t[:200]}")
    if a:
        print(f"  Action:   {a}")
    if ai:
        ai_str = ai[:300] if ai else ""
        print(f"  Input:    {ai_str}")
    if o:
        o_str = o[:400] if o else ""
        print(f"  Observe:  {o_str}")
    print()


def show_memory():
    sep()
    print("SHORT-TERM MEMORY")
    st = agent_memory.get_short_term()
    for entry in st[-5:]:
        print(f"  [{entry['role']}] {entry['content'][:200]}")
    print()
    print("OBSERVATIONS")
    obs = agent_memory._observations
    for o in obs[-5:]:
        print(f"  [{o['action']}] {o['summary'][:200]}")
    print()
    print("LONG-TERM MEMORY")
    lt = agent_memory.get_all_long_term()
    if lt:
        for doc in lt[-5:]:
            print(f"  [{doc['key']}]: {doc['value'][:200]}")
    else:
        print("  (empty)")
    print()


def run_interactive():
    print("\n  ReAct Agent CLI Backdoor")
    print(f"  Model: minimax-m2.5:cloud  |  Critic: qwen3.6")
    sep()
    print("  Commands:  /exit  /memory  /clear  /stream  /quiet")
    print("  Prefix with /stream to watch step-by-step.")
    sep()

    planner = TaskPlanner(agent=None, llm=PlannerLLM())
    stream_mode = False

    while True:
        try:
            raw = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        if raw.lower() == "/exit":
            break
        if raw.lower() == "/memory":
            show_memory()
            continue
        if raw.lower() == "/clear":
            agent_memory.reset_short_term()
            agent_memory.clear_long_term()
            print("  Session and long-term memory cleared.")
            continue
        if raw.lower() == "/stream":
            stream_mode = True
            print("  Stream mode ON")
            continue
        if raw.lower() == "/quiet":
            stream_mode = False
            print("  Stream mode OFF")
            continue

        if raw.startswith("/stream "):
            query = raw[8:]
            use_stream = True
        else:
            query = raw
            use_stream = stream_mode

        sep("-")
        print(f"  Q: {query}")

        if use_stream:
            subtasks = None
            try:
                subtasks = planner.decompose_task(query)
                print(f"  Plan: {len(subtasks)} subtask(s)")
                for i, t in enumerate(subtasks, 1):
                    print(f"    {i}. {t}")
            except Exception as e:
                print(f"  Planner error: {e}")

            step_count = 0
            for event in stream_agent(query, subtasks=subtasks):
                et = event.get("type", "")
                if et == "step":
                    step_count += 1
                    print(f"\n  --- Step {step_count} ---")
                    print_step(event)
                elif et == "batch_delegation_start":
                    n = event.get("total", 0)
                    print(f"\n  --- batch_delegate: {n} parallel agents ---")
                elif et == "subagent_step":
                    ss = event.get("sub_step", {})
                    idx = event.get("agent_idx", 0)
                    print(f"  [Agent {idx+1}] {ss.get('action', '')}: {ss.get('thought', '')[:120]}")
                elif et == "subagent_done":
                    idx = event.get("agent_idx", 0)
                    tot = event.get("total_agents", 0)
                    print(f"  [Agent {idx+1}/{tot}] Done")
                elif et == "batch_delegation_end":
                    print(f"  --- all parallel agents done ---")
                elif et == "interrupt":
                    print(f"\n  !! INTERRUPT: {event.get('reason', '')}")
                elif et == "paused":
                    print(f"\n  !! Step limit reached")
                elif et == "done":
                    sep()
                    print(f"  FINAL ANSWER:")
                    print(f"  {event.get('final_answer', '')}")
            print()
        else:
            try:
                subtasks = planner.decompose_task(query)
                print(f"  Plan: {len(subtasks)} subtask(s)")
                for i, t in enumerate(subtasks, 1):
                    print(f"    {i}. {t}")
            except Exception:
                subtasks = None

            result = run_agent(query, subtasks=subtasks)
            answer = result["final_answer"] if isinstance(result, dict) else str(result)
            steps = result.get("steps", []) if isinstance(result, dict) else []
            if steps:
                print(f"  Steps: {len(steps)}")
                for s in steps:
                    print_step(s)
            sep()
            print(f"  FINAL ANSWER:")
            print(f"  {answer[:2000]}")
            print()

    print("Bye.")


if __name__ == "__main__":
    run_interactive()
