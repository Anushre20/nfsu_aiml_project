import re

def parse_output(text):
    try:
        # If the LLM returned an error, propagate it
        if text.startswith("Error:"):
            return {
                "thought": "",
                "action": "FINISH",
                "action_input": text
            }

        thought_match = re.search(
            r"Thought\s*:\s*(.*?)(?=\n\s*Action\s*:)",
            text,
            re.DOTALL | re.IGNORECASE
        )

        action_match = re.search(
            r"(?:^|\n)\s*Action\s*:\s*(.*?)(?=\n\s*Action Input\s*:)",
            text,
            re.DOTALL | re.IGNORECASE
        )

        action_input_match = re.search(
            r"Action Input\s*:\s*(.*?)(?=\n\s*(?:Observation|Thought|Action\b(?!\s*Input)|Action Input|Subtasks)\s*:|\Z)",
            text,
            re.DOTALL | re.IGNORECASE
        )

        thought = (thought_match.group(1).strip() if thought_match and thought_match.group(1) else "")
        action = (action_match.group(1).strip() if action_match and action_match.group(1) else "FINISH")
        action_input = (action_input_match.group(1).strip() if action_input_match and action_input_match.group(1) else "")

        # If parser found nothing meaningful, show the raw LLM output
        if action == "FINISH" and not action_input and not thought:
            return {
                "thought": "LLM output was not in ReAct format",
                "action": "FINISH",
                "action_input": "Raw LLM response: " + text[:500]
            }

        return{
            "thought": thought,
            "action": action,
            "action_input": action_input
        }

    except Exception as e:
        return {
            "thought": "Parser error",
            "action": "FINISH",
            "action_input": f"Parser exception: {e}"
        }
