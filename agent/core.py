import os
from agent.llm import call_llm
from agent.parser import parse_output
from agent.prompts import build_system_prompt
from agent.tools import TOOLS, _resolve_path
from agent.memory import Memory
from agent.log_utils import debug as _debug
from agent.sub_agents import run_subagent_stream, run_subagents_parallel

DEBUG = True
MAX_STEPS = 200
SCRATCHPAD_MAX_STEPS = 6
memory = Memory()


def _truncate_obs(text, max_len=300):
    if text and len(text) > max_len:
        return text[:max_len] + f"\n... [truncated {len(text) - max_len} chars]"
    return text


def _format_scratchpad(scratchpad):
    lines = scratchpad.strip().split("\n")
    obs_count = 0
    result = []
    for line in reversed(lines):
        result.insert(0, line)
        stripped = line.strip()
        if stripped.startswith("Observation:") or stripped.startswith("Tool Result:"):
            obs_count += 1
        if obs_count >= SCRATCHPAD_MAX_STEPS:
            remaining = lines[:len(lines) - len(result)]
            if remaining:
                result.insert(0, f"... [{len(remaining)} earlier steps truncated]")
            break
    return "\n".join(result)


def _agent_step(question, subtasks, scratchpad):
    short_context = memory.get_short_term_text()
    long_memory = memory.retrieve_long_term(question)

    if long_memory:
        long_context = "\n".join(
            [f"- [{it['key']}]: {_truncate_obs(it['value'], 200)}" for it in long_memory]
        )
        knowledge_block = f"Relevant Past Knowledge:\n{long_context}"
    else:
        knowledge_block = ""

    system_prompt = build_system_prompt(subtasks)
    scratchpad = _format_scratchpad(scratchpad)

    prompt = system_prompt + "\n\n" + knowledge_block + "\n\nRecent Conversation:\n" + short_context + "\n\nQuestion:\n" + question + "\n\n" + scratchpad

    llm_output = call_llm(prompt)

    if DEBUG:
        _debug("=== Prompt (first 500) ===")
        _debug(prompt[:500])
        _debug("=== LLM Output ===")
        _debug(llm_output)

    parsed = parse_output(llm_output)
    if DEBUG:
        _debug("PARSED=" + str(parsed))
    action = parsed["action"].strip().lower()

    if action == "finish":
        return action, parsed, None, None, scratchpad, None

    if action == "store_memory":
        memory.add_long_term(parsed.get("action_input", ""), parsed.get("action_input_extra", ""))
        result = "Information stored in long-term memory."
        step_entry = f"Thought: {parsed['thought']}\nAction: store_memory\nAction Input: {parsed['action_input']}\nObservation: {result}"
        return action, parsed, result, step_entry, scratchpad + "\n" + step_entry, None

    if action == "batch_delegate":
        raw = parsed.get("action_input", "")
        tasks = [t.strip() for t in raw.split("\n") if t.strip()]
        if not tasks:
            tasks = [raw]
        depth = parsed.get("depth", 1)
        try:
            depth = int(depth)
        except (ValueError, TypeError):
            depth = 1
        return action, parsed, tasks, depth, scratchpad, "batch_delegate"

    if action == "delegate":
        task = parsed.get("action_input", "")
        sub_depth = parsed.get("depth", 1)
        try:
            sub_depth = int(sub_depth)
        except (ValueError, TypeError):
            sub_depth = 1
        return action, parsed, task, sub_depth, scratchpad, "delegate"

    if action not in TOOLS:
        return action, parsed, None, None, scratchpad, None

    tool_result = TOOLS[action](parsed["action_input"])
    if DEBUG:
        _debug("TOOL RESULT=" + str(tool_result))

    step_entry = f"Thought: {parsed['thought']}\nAction: {action}\nAction Input: {parsed['action_input']}\nObservation: {_truncate_obs(str(tool_result))}"
    if DEBUG:
        _debug("--- ReAct Step ---")
        _debug(step_entry.strip())

    return action, parsed, str(tool_result), step_entry, scratchpad + "\n" + step_entry, None


def run_agent(question, subtasks=None):
    memory.add_short_term("user", question)

    steps_data = []
    scratchpad = ""
    for _ in range(MAX_STEPS):
        action, parsed, tool_result, step_entry, scratchpad, flow_type = _agent_step(
            question, subtasks, scratchpad
        )

        if action == "finish":
            answer = parsed["action_input"]
            memory.add_short_term("assistant", answer)
            steps_data.append({
                "thought": parsed["thought"],
                "action": action,
                "action_input": parsed["action_input"],
                "observation": "Final Answer Generated"
            })
            return {"steps": steps_data, "final_answer": answer}

        if action == "store_memory":
            steps_data.append({
                "thought": parsed["thought"],
                "action": action,
                "action_input": parsed["action_input"],
                "observation": "Stored in long-term memory."
            })
            continue

        if action == "batch_delegate":
            tasks = tool_result
            depth = parsed.get("depth", 1)
            all_sub_steps = []
            combined_result = ""
            for ev in run_subagents_parallel(tasks, depth=depth):
                if ev["type"] in ("sub_step",):
                    all_sub_steps.append(ev["sub_step"])
                elif ev["type"] == "sub_done":
                    combined_result += f"[Agent {ev['agent_idx']+1}]: {ev['result']}\n"
            steps_data.append({
                "thought": parsed["thought"],
                "action": action,
                "action_input": "\n".join(tasks),
                "observation": combined_result or "Delegation completed.",
                "sub_steps": all_sub_steps,
            })
            scratchpad += f"\nThought: {parsed['thought']}\nAction: batch_delegate\nAction Input: {_truncate_obs(str(tasks))}\nObservation: {_truncate_obs(combined_result)}"
            continue

        if action == "delegate":
            result = ""
            for sub_step, sub_result, is_done in run_subagent_stream(parsed["action_input"], depth=parsed.get("depth", 1)):
                if is_done:
                    result = sub_result
            steps_data.append({
                "thought": parsed["thought"],
                "action": action,
                "action_input": parsed["action_input"],
                "observation": str(result) if result else "Delegation completed.",
            })
            scratchpad += f"\nThought: {parsed['thought']}\nAction: delegate\nAction Input: {parsed['action_input']}\nObservation: {_truncate_obs(str(result))}"
            continue

        if action not in TOOLS:
            return {
                "steps": steps_data,
                "final_answer": f"Unknown tool : {action}"
            }

        steps_data.append({
            "thought": parsed["thought"],
            "action": action,
            "action_input": parsed["action_input"],
            "observation": tool_result,
        })

    return {"steps": steps_data, "final_answer": "Maximum Steps Reached."}


def stream_agent(question, subtasks=None, resume_from=None):
    memory.add_short_term("user", question)

    if resume_from:
        steps_data = list(resume_from.get("steps_data", []))
        scratchpad = resume_from.get("scratchpad", "")
        start_step = resume_from.get("step_count", 0)
    else:
        steps_data = []
        scratchpad = ""
        start_step = 0

    for step_num in range(start_step, start_step + MAX_STEPS):
        action, parsed, tool_result, step_entry, scratchpad, flow_type = _agent_step(
            question, subtasks, scratchpad
        )

        if action == "finish":
            answer = parsed["action_input"]
            memory.add_short_term("assistant", answer)
            yield {
                "type": "step",
                "step": step_num,
                "thought": parsed["thought"],
                "action": action,
                "action_input": parsed["action_input"],
                "observation": "Final Answer Generated",
            }
            yield {"type": "done", "final_answer": answer, "steps": steps_data}
            return

        if action == "store_memory":
            yield {
                "type": "step",
                "step": step_num,
                "thought": parsed["thought"],
                "action": action,
                "action_input": parsed["action_input"],
                "observation": "Stored in long-term memory.",
            }
            steps_data.append({
                "thought": parsed["thought"],
                "action": action,
                "action_input": parsed["action_input"],
                "observation": "Stored in long-term memory.",
            })
            continue

        if action == "batch_delegate":
            tasks = tool_result
            depth = parsed.get("depth", 1)
            yield {
                "type": "batch_delegation_start",
                "step": step_num,
                "thought": parsed["thought"],
                "tasks": tasks,
                "depth": depth,
                "total": len(tasks),
            }
            all_sub_steps = []
            combined_result = ""
            for ev in run_subagents_parallel(tasks, depth=depth):
                if ev["type"] == "sub_step":
                    all_sub_steps.append(ev["sub_step"])
                    yield {
                        "type": "subagent_step",
                        "step": step_num,
                        "depth": ev["depth"],
                        "agent_idx": ev["agent_idx"],
                        "total_agents": ev["total"],
                        "sub_step": ev["sub_step"],
                    }
                elif ev["type"] == "sub_done":
                    ai = ev["agent_idx"]
                    combined_result += f"[Agent {ai+1}/{ev['total']}]: {ev['result']}\n"
                    yield {
                        "type": "subagent_done",
                        "step": step_num,
                        "depth": ev["depth"],
                        "agent_idx": ai,
                        "total_agents": ev["total"],
                        "result": ev["result"],
                    }
                elif ev["type"] == "sub_error":
                    yield {
                        "type": "subagent_error",
                        "step": step_num,
                        "depth": ev["depth"],
                        "agent_idx": ev["agent_idx"],
                        "total_agents": ev["total"],
                        "error": ev["error"],
                    }
                elif ev["type"] == "sub_final":
                    pass
            yield {
                "type": "batch_delegation_end",
                "step": step_num,
                "result": combined_result or "Completed.",
            }
            steps_data.append({
                "thought": parsed["thought"],
                "action": action,
                "action_input": "\n".join(tasks),
                "observation": combined_result or "Delegation completed.",
                "sub_steps": all_sub_steps,
            })
            scratchpad += f"\nThought: {parsed['thought']}\nAction: batch_delegate\nAction Input: {_truncate_obs(str(tasks))}\nObservation: {_truncate_obs(combined_result)}"
            continue

        if action == "delegate":
            task = parsed["action_input"]
            depth = parsed.get("depth", 1)
            yield {
                "type": "delegation_start",
                "step": step_num,
                "thought": parsed["thought"],
                "task": task,
                "depth": depth,
            }
            sub_steps = []
            for sub_step, sub_result, is_done in run_subagent_stream(task, depth=depth):
                sub_step["depth"] = depth
                sub_steps.append(sub_step)
                yield {
                    "type": "subagent_step",
                    "step": step_num,
                    "depth": depth,
                    "agent_idx": 0,
                    "total_agents": 1,
                    "sub_step": sub_step,
                }
                if is_done:
                    final_result = sub_result
            yield {
                "type": "delegation_end",
                "step": step_num,
                "task": task,
                "result": str(final_result) if final_result else "Completed.",
            }
            steps_data.append({
                "thought": parsed["thought"],
                "action": action,
                "action_input": task,
                "observation": str(final_result) if final_result else "Delegation completed.",
                "sub_steps": sub_steps,
            })
            scratchpad += f"\nThought: {parsed['thought']}\nAction: delegate\nAction Input: {task}\nObservation: {_truncate_obs(str(final_result))}"
            continue

        if action not in TOOLS:
            yield {
                "type": "done",
                "final_answer": f"Unknown tool : {action}",
                "steps": steps_data,
            }
            return

        yield {
            "type": "step",
            "step": step_num,
            "thought": parsed["thought"],
            "action": action,
            "action_input": parsed["action_input"],
            "observation": tool_result,
        }

        steps_data.append({
            "thought": parsed["thought"],
            "action": action,
            "action_input": parsed["action_input"],
            "observation": tool_result,
        })

    yield {
        "type": "paused",
        "message": "Step limit reached. Continue?",
        "resume_context": {
            "scratchpad": scratchpad,
            "steps_data": steps_data,
            "step_count": start_step + MAX_STEPS,
            "question": question,
            "subtasks": subtasks,
        },
        "steps": steps_data,
    }