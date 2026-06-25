import re


def parse_output(text):
    try:
        if text.startswith("Error:"):
            return {
                "thought": "",
                "action": "FINISH",
                "action_input": text,
                "action_input_extra": "",
                "depth": 1,
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

        action_lower = action.lower()

        extra = ""
        depth = 1

        if action_lower == "store_memory":
            if "|" in action_input:
                parts = action_input.split("|", 1)
                action_input = parts[0].strip()
                extra = parts[1].strip()

        if action_lower == "delegate":
            depth_match = re.search(r"depth\s*[=:]\s*(\d+)", action_input, re.IGNORECASE)
            if depth_match:
                depth = int(depth_match.group(1))

        if action == "FINISH" and not action_input and not thought:
            return {
                "thought": "LLM output was not in ReAct format",
                "action": "FINISH",
                "action_input": "Raw LLM response: " + text[:500],
                "action_input_extra": "",
                "depth": 1,
            }

        return {
            "thought": thought,
            "action": action,
            "action_input": action_input,
            "action_input_extra": extra,
            "depth": depth,
        }

    except Exception as e:
        return {
            "thought": "Parser error",
            "action": "FINISH",
            "action_input": f"Parser exception: {e}",
            "action_input_extra": "",
            "depth": 1,
        }