from agent.llm import call_llm
from agent.parser import parse_output
from agent.prompts import build_system_prompt
from agent.tools import TOOLS
from agent.memory import Memory
from agent.log_utils import debug as _debug

DEBUG = True
MAX_STEPS = 8
memory = Memory()


def _agent_step(question, subtasks, scratchpad):
    short_memory = memory.get_short_term()
    long_memory = memory.retrieve_long_term(question)

    short_context = "\n".join(
        [f"{role}: {content}" for role, content in short_memory]
    )

    if long_memory:
        long_context = "\n".join(long_memory)
        knowledge_block = f"Relevant Past Knowledge:\n{long_context}"
    else:
        knowledge_block = ""

    system_prompt = build_system_prompt(subtasks)

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
        return action, parsed, None, None, scratchpad

    if action not in TOOLS:
        return action, parsed, None, None, scratchpad

    tool_result = TOOLS[action](parsed["action_input"])
    if DEBUG:
        _debug("TOOL RESULT=" + str(tool_result))

    step_entry = f"""
    Thought: {parsed['thought']}
    Action: {action}
    Action Input: {parsed['action_input']}
    Observation: {tool_result}
    """
    if DEBUG:
        _debug("--- ReAct Step ---")
        _debug(step_entry.strip())

    return action, parsed, str(tool_result), step_entry, scratchpad + step_entry


def run_agent(question, subtasks=None):
    memory.reset_short_term()
    memory.add_short_term("user", question)

    steps_data = []
    scratchpad = ""
    for _ in range(MAX_STEPS):
        action, parsed, tool_result, step_entry, scratchpad = _agent_step(
            question, subtasks, scratchpad
        )

        if action == "finish":
            answer = parsed["action_input"]
            memory.add_short_term("assistant", answer)
            memory.add_long_term(
                f"\nQuestion:\n{question}\n\nAnswer:\n{answer}\n"
            )
            steps_data.append({
                "thought": parsed["thought"],
                "action": action,
                "action_input": parsed["action_input"],
                "observation": "Final Answer Generated"
            })
            return {"steps": steps_data, "final_answer": answer}

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
    memory.reset_short_term()
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
        action, parsed, tool_result, step_entry, scratchpad = _agent_step(
            question, subtasks, scratchpad
        )

        if action == "finish":
            answer = parsed["action_input"]
            memory.add_short_term("assistant", answer)
            memory.add_long_term(
                f"\nQuestion:\n{question}\n\nAnswer:\n{answer}\n"
            )
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

    # Step limit reached — yield paused event with resume context
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
