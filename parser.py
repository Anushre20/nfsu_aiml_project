import re

def parse_output(text):
    try:
        thought_match = re.search(
            r"Thought:\s*(.*?)(?=Action:)",
            text,
            re.DOTALL
        )

        action_match = re.search(
            r"Action:\s*(.*?)(?=Action Input:)",
            text,
            re.DOTALL
        )

        action_input_match = re.search(
            r"Action Input:\s*(.*?)(?=Observation:|$)",
            text,
            re.DOTALL
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