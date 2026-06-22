import re

def parse_output(text):
    try:
        thought_match = re.search(
            r"Thought\s*:\s*(.*?)(?=Action\s*:)",
            text,
            re.DOTALL | re.IGNORECASE
        )

        action_match = re.search(
            r"Action\s*:\s*(.*?)(?=Action Input\s*:)",
            text,
            re.DOTALL | re.IGNORECASE
        )

        action_input_match = re.search(
            r"Action Input\s*:\s*(.*?)(?=\n\s*(?:Observation|Thought|Action)\s*:|\Z)",
            text,
            re.DOTALL | re.IGNORECASE
        )

        thought = (thought_match.group(1).strip() if thought_match and thought_match.group(1) else "")
        action = (action_match.group(1).strip() if action_match and action_match.group(1) else "FINISH")
        action_input = (action_input_match.group(1).strip() if action_input_match and action_input_match.group(1) else "")

        return{
            "thought": thought,
            "action": action,
            "action_input": action_input
        }

    except Exception as e:
        print("Parser Error:", e)
        return {
            "thought": "Parser failed",
            "action": "FINISH",
            "action_input": str(e)
        }
