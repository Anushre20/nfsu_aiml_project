from ddgs import DDGS
import subprocess
import tempfile

from ddgs import DDGS

def web_search(query):    
    snippets = []

    try:
        with DDGS() as ddgs:
             results = ddgs.text(query, max_results=3)
             for result in results:
                  snippets.append(result.get("body", ""))
        return "\n".join(snippets)
    except Exception as e:
        return f"Search Error: {e}"
                

# def python_executor(code):

#     try:
#         with tempfile.NamedTemporaryFile(
#             mode="w", suffix=".py", delete=False) as temp_file:
#                 temp_file.write(code)
#                 temp_file_path = temp_file.name

#         result = subprocess.run(
#             ["python", temp_file_path],
#             capture_output=True, text=True,
#             timeout=10
#         )
#         return result.stdout if result.returncode == 0 else result.stderr

#     except Exception as e:
        return f"Execution Error: {e}"
    
TOOLS = {
     "web_search": web_search,
    # "python_executor": python_executor
}
