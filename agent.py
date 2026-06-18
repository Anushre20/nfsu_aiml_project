from llm import call_llm
from parser import parse_output
from prompts import SYSTEM_PROMPT
from tools import TOOLS

MAX_STEPS = 8

def run_agent(question):
    scratchpad = ""
    for step in range(MAX_STEPS):
        print("STEP=", step)
        prompt = f"""

{SYSTEM_PROMPT}
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
            return parsed["action_input"]
        
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