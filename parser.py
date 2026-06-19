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
            r"Action Input\s*:\s*(.*)",
            text,
            re.DOTALL | re.IGNORECASE
        )

        return{
            "thought": thought_match.group(1).strip(),
            "action": action_match.group(1).strip(),
            "action_input": action_input_match.group(1).strip()
        }
    
    except Exception as e:
        print("Parser Error:", e)
        return {
            "thought": "Parser failed",
            "action": "FINISH",
            "action_input": str(e)
        }