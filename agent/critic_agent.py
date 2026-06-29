from agent.base_agent import BaseAgent
from agent.tools import run_command
from agent.memory import Memory
from agent.llm import CRITIC_MODEL


CRITIC_PROMPT = """
You are the Critic Agent in a multi-agent ReAct system.

Your job is NOT to gather information.

Your responsibilities are:

- verify factual consistency
- check completeness
- identify mistakes
- verify Python examples when needed
- suggest corrections
- return PASS if everything is correct

You MUST NOT:
- search the web
- modify files
- write files
- delegate work

Always follow the ReAct format.

Thought:
...

Action:
...

Action Input:
...

Never generate Observation yourself.

If the answer is already correct,
finish with:

PASS
"""


class CriticAgent(BaseAgent):

    def __init__(self, memory: Memory):

        critic_tools = {
            "run_command": run_command,
        }

        super().__init__(
            name="Critic",
            system_prompt=CRITIC_PROMPT,
            tools=critic_tools,
            memory=memory,
            model=CRITIC_MODEL,
        )