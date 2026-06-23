def call_llm(prompt : str) -> str:
    from ollama import chat
    try:
        response = chat(
            model='gemma4',
            messages=[
                {'role': 'user', 'content': prompt}
            ],
            options={"num_predict": 1024},
        )
        output = response.message.content
        if not output or not output.strip():
            return "Error: LLM returned empty response"
        return output
    except Exception as e:
        return f"Error: LLM call failed — {e}"
