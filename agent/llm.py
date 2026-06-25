import json
import threading
import time

_llm_lock = threading.Lock()


def call_llm(prompt: str, structured: bool = False) -> str:
    from ollama import Client

    client = Client(timeout=300)

    options = {
        "num_predict": 8192,
        "temperature": 0.3,
        "num_ctx": 65536,
    }

    def _do_call():
        response = client.chat(
            model='qwen3.6',
            messages=[
                {'role': 'user', 'content': prompt}
            ],
            options=options,
        )
        output = response.message.content
        if not output or not output.strip():
            return "Error: LLM returned empty response"
        return output

    with _llm_lock:
        last_error = None
        for attempt in range(3):
            try:
                result = _do_call()
                if "Error: LLM returned empty" not in result:
                    return result
                last_error = result
            except Exception as e:
                last_error = f"Error: LLM call failed — {e}"
            if attempt < 2:
                time.sleep(2 ** attempt)
        return last_error