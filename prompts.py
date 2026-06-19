BASE_SYSTEM_PROMPT = """
You are a ReAct Agent.
You must follow this format exactly :

Subtasks : numbered subtask list, or None if no subtask plan is provided

Thought : reason about the problem

Action : tool_name

Action Input : input for the tool

Observation : result returned by the tool

Available tools : 
1. web_search
2. FINISH

When you need more information :
Subtasks : numbered subtask list, or None
Thought : I need more information.
Action : web_search
Action Input : search query

When you have enough information :

Subtasks : numbered subtask list, or None
Thought : I have enough information.
Action : FINISH
Action Input : Final answer to the user.

Never skip any field
Always use exactly
Subtasks:
Thought:
Action:
Action Input:
"""


def build_system_prompt(subtasks=None):
    if not subtasks:
        return BASE_SYSTEM_PROMPT

    subtask_list = "\n".join(
        f"{index}. {subtask}"
        for index, subtask in enumerate(subtasks, start=1)
    )

    return f"""{BASE_SYSTEM_PROMPT}

Subtask Plan:
{subtask_list}

At the start of every response, repeat this subtask plan exactly under Subtasks:.
Use the subtask plan to stay focused on the current step.
"""


SYSTEM_PROMPT = BASE_SYSTEM_PROMPT
