def call_llm(prompt : str) -> str:
    from ollama import chat
    try:
        response = chat(
            model='minimax-m2.5:cloud',
            messages=[
                {'role': 'user', 'content': prompt}
            ],
        )
        return response.message.content
    except Exception as e:
        return f"Error occurred: {e}"
