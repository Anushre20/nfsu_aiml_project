from agent.llm import call_llm
from agent.parser import parse_output
from agent.log_utils import debug as _debug

class BaseAgent:
        def __init__(
            self,
            name,
            system_prompt,
            tools,
            memory,
            model=None,
        ):
            self.name = name
            self.system_prompt = system_prompt
            self.tools = tools
            self.memory = memory
            self.model = model

        def build_prompt(
            self,
            task,
            scratchpad=""
        ):
            short_context = self.memory.get_short_term_text()

            long_context = self.memory.retrieve_long_term(task)

            if long_context:

                formatted_long = "\n".join(
                    [
                        f"- {item['key']}: {item['value']}"
                        for item in long_context
                    ]
                )

            else:

                formatted_long = "No relevant long-term memory."

            prompt = (
                self.system_prompt
                + "\n\nLong-Term Memory:\n"
                + formatted_long
                + "\n\nConversation:\n"
                + short_context
                + "\n\nTask:\n"
                + task
                + "\n\n"
                + scratchpad
            )

            return prompt
        
        def think(
            self,
            task,
            scratchpad=""
        ):
            prompt = self.build_prompt(
                task,
                scratchpad,
            )

            output = call_llm(prompt, model=self.model)

            parsed = parse_output(output)

            return parsed

        def execute_tool(
            self,
            action,
            action_input,
        ):

            if action not in self.tools:

                return f"Tool '{action}' is not available for {self.name}."

            return self.tools[action](action_input)
        
        def step(
            self,
            task,
            scratchpad=""
        ):
            parsed = self.think(
                task,
                scratchpad,
            )

            _debug(f"[{self.name}] Thought: {parsed['thought']}")
            _debug(f"[{self.name}] Action: {parsed['action']}")
            _debug(f"[{self.name}] Action Input: {parsed['action_input']}")

            action = parsed["action"].lower()

            if action == "finish":
                return parsed, None

            observation = self.execute_tool(
                action,
                parsed["action_input"]
            )

            _debug(f"[{self.name}] Observation: {observation}")

            return parsed, observation
        def run(
            self,
            task,
            max_steps=20,
        ):
            scratchpad = ""
            steps = []

            for _ in range(max_steps):

                parsed, observation = self.step(
                    task,
                    scratchpad,
                )

                action = parsed["action"].lower()

                if action == "finish":

                    steps.append({

                        "thought": parsed["thought"],

                        "action": parsed["action"],

                        "action_input": parsed["action_input"],

                        "observation": None,

                    })

                    return {

                        "final_answer": parsed["action_input"],

                        "steps": steps,

                    }

                steps.append({

                    "thought": parsed["thought"],

                    "action": parsed["action"],

                    "action_input": parsed["action_input"],

                    "observation": observation,

                })

                scratchpad += (

                    f"\nThought: {parsed['thought']}"

                    f"\nAction: {parsed['action']}"

                    f"\nAction Input: {parsed['action_input']}"

                    f"\nObservation: {observation}\n"

                )
            return {

                "final_answer": "Maximum reasoning steps reached.",

                "steps": steps,

            }