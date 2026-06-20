# import os
# from urllib import response
# from dotenv import load_dotenv
from ollama import chat

# load_dotenv()

# HF_API_KEY = os.getenv("HF_API_KEY")
# if not HF_API_KEY:
#    raise ValueError("HF_API_KEY is not set in the environment variables.")


#MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

def call_llm(prompt : str) -> str:
    """
    sends a prompt to hugging face inference API
    and returns the generated response.
    """
    try:
        # response = client.chat_completion(
        #     model=MODEL_NAME,
        #     messages=[{"role": "user", "content": prompt}],
        #     max_tokens=300,
        #     temperature=0.2,
        # )
        
        response = chat(
        model='minimax-m2.5:cloud',
        messages=[
            {'role': 'user', 'content': prompt}
            ],
        )
        return response.message.content
        #return response.choices[0].message.content
    
    except Exception as e:
        return f"Error occurred: {e}"
        
