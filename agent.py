from llm import call_llm
from parser import parse_output
from prompts import SYSTEM_PROMPT
from tools import TOOLS
from memory import Memory

MAX_STEPS = 8
memory = Memory()

def run_agent(question):
    memory.add_short_term(
        "user",
        question
    )

    scratchpad = ""
    for step in range(MAX_STEPS):
        print("STEP=", step)
        short_memory = memory.get_short_term()

        long_memory = memory.retrieve_long_term(
            question
        )

        short_context = "\n".join(
            [
                f"{role}: {content}"
                for role, content in short_memory
            ]
        )

        long_context = "\n".join(
            long_memory
        )

        prompt = f"""
        {SYSTEM_PROMPT}

        Relevant Past Knowledge:
        {long_context}

        Recent Conversation:
        {short_context}

        Question:
        {question}

        {scratchpad}
        """

        llm_output = call_llm(prompt)
        print("\n===================== LLM Output ====================")
        print(llm_output)

        parsed = parse_output(llm_output)
        print("PARSED=", parsed)
        action = parsed["action"]

        if action == "FINISH":

            answer = parsed["action_input"]

            memory.add_short_term(
                "assistant",
                answer
            )

            summary = f"""
Question:
{question}

Answer:
{answer}
"""

            memory.add_long_term(
                summary
            )

            return answer
        
        if action not in TOOLS:
            return f"Unknown tool : {action}"
        
        tool_result = TOOLS[action](
            parsed["action_input"]
        )
        print("TOOL RESULT=", tool_result)

        scratchpad += f"""
        Thought: {parsed['thought']}
        Action: {action}
        Action Input: {parsed['action_input']}
        Observation: {tool_result}
        """
    return "Maximum Steps Reached."