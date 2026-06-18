from langchain_ollama import ChatOllama

llm = ChatOllama(model="minimax-m2.5:cloud")

result = llm.invoke("What is AI?")
print(result.content)