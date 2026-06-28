from agent.base_agent import BaseAgent
from agent.tools import web_search
from agent.memory import Memory


RESEARCHER_PROMPT = """
You are the Researcher Agent in a multi-agent ReAct system.

Your ONLY responsibility is to gather information.

You may:
- search the web
- retrieve useful knowledge from long-term memory

You must NOT:
- execute code
- modify files
- write files
- update files
- delegate work
- critique answers

Always produce factual findings.

Follow the ReAct format exactly.

Thought:
...

Action:
...

Action Input:
...

Never produce Observation yourself.
"""


class ResearcherAgent(BaseAgent):

    def __init__(self, memory: Memory):

        researcher_tools = {
            "web_search": web_search,
        }

        super().__init__(
            name="Researcher",
            system_prompt=RESEARCHER_PROMPT,
            tools=researcher_tools,
            memory=memory,
        )