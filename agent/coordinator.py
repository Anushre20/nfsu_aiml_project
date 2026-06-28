from agent.researcher_agent import ResearcherAgent
from agent.critic_agent import CriticAgent
from agent.memory import Memory


class Coordinator:

    MAX_ROUNDS = 3

    def __init__(self):

        self.memory = Memory()

        self.researcher = ResearcherAgent(self.memory)

        self.critic = CriticAgent(self.memory)

    def run(self, task):
        researcher_task = task

        researcher_scratchpad = ""

        critic_scratchpad = ""

        findings = ""

        critique = ""

        for round_no in range(self.MAX_ROUNDS):
            findings = self.researcher.run(
                researcher_task
        )
            critic_task = f"""

Researcher Findings:

{findings}

Evaluate the findings.

Return PASS if everything is correct.

Otherwise provide corrections.

"""



            critique = self.critic.run(
                critic_task
            )

            if "PASS" in critique.upper():

                return findings
            researcher_task = f"""

Improve your previous findings.

Critique:

{critique}

Previous Findings:

{findings}

"""

        return findings