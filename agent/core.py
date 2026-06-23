import concurrent.futures
from agent.llm import call_llm
from agent.parser import parse_output
from agent.prompts import build_system_prompt
from agent.tools import TOOLS
from agent.memory import Memory
from agent.sub_agents import SubAgent

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

    prompt = f"""
            {system_prompt}

            {knowledge_block}

            Recent Conversation:
            {short_context}

            Question:
            {question}

            {scratchpad}
            """

    llm_output = call_llm(prompt)

    if DEBUG:
        print("\n===================== LLM Output ====================")
        print(llm_output)

    parsed = parse_output(llm_output)
    if DEBUG:
        print("PARSED=", parsed)
    action = parsed["action"].strip().lower()

    if action == "FINISH":
        return action, parsed, None, None, scratchpad

    if action not in TOOLS:
        return action, parsed, None, None, scratchpad

    tool_result = TOOLS[action](parsed["action_input"])
    if DEBUG:
        print("TOOL RESULT=", tool_result)

    step_entry = f"""
    Thought: {parsed['thought']}
    Action: {action}
    Action Input: {parsed['action_input']}
    Observation: {tool_result}
    """
    if DEBUG:
        print("\n--- ReAct Step ---")
        print(step_entry.strip())

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

        if action == "FINISH":
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


def _run_single_sub_agent(task):
    agent = SubAgent()
    steps, result = agent.run(task)
    return task, steps, result


def _synthesize_answer(question, subtask_results):
    results_text = "\n".join(
        f"Subtask: {t}\nResult: {r}\n---" for t, r in subtask_results
    )
    prompt = f"""You are a helpful assistant. Given a user's question and the results from several subtasks, provide a clear, natural final answer.

User question:
{question}

Subtask results:
{results_text}

Final answer:"""
    return call_llm(prompt)


def stream_agent(question, subtasks=None):
    memory.reset_short_term()
    memory.add_short_term("user", question)

    all_steps = []

    if subtasks and len(subtasks) > 1:
        # --- DELEGATION MODE ---
        yield {"type": "delegation", "message": "Breaking down the task...", "subtasks": subtasks}

        yield {"type": "delegation", "message": "Running subtasks..."}

        parallel_batches = []
        current_batch = []
        for i, task in enumerate(subtasks):
            current_batch.append(task)
            if len(current_batch) >= 2 or i == len(subtasks) - 1:
                parallel_batches.append(current_batch)
                current_batch = []

        all_results = []
        for batch in parallel_batches:
            if len(batch) == 1:
                task = batch[0]
                _, steps, result = _run_single_sub_agent(task)
                for s in steps:
                    s["subtask"] = task
                    yield {"type": "step", **s}
                all_steps.extend(steps)
                all_results.append((task, result))
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
                    futures = {executor.submit(_run_single_sub_agent, task): task for task in batch}
                    for future in concurrent.futures.as_completed(futures):
                        task = futures[future]
                        _, steps, result = future.result()
                        for s in steps:
                            s["subtask"] = task
                            yield {"type": "step", **s}
                        all_steps.extend(steps)
                        all_results.append((task, result))

        final = _synthesize_answer(question, all_results)
        memory.add_short_term("assistant", final)
        memory.add_long_term(f"\nQuestion:\n{question}\n\nAnswer:\n{final}\n")

        yield {"type": "done", "final_answer": final, "steps": all_steps}
        return

    # --- STANDALONE MODE ---
    memory.add_short_term("user", question)
    steps_data = []
    scratchpad = ""
    for step_num in range(MAX_STEPS):
        action, parsed, tool_result, step_entry, scratchpad = _agent_step(
            question, subtasks, scratchpad
        )

        if action == "FINISH":
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

    yield {
        "type": "done",
        "final_answer": "Maximum Steps Reached.",
        "steps": steps_data,
    }
