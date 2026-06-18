from agent import run_agent

def main():

    while True:

        query = input("\nAsk Question: ")

        if query.lower() == "exit":
            break

        answer = run_agent(query)

        print("\nFINAL ANSWER")
        print(answer)

if __name__ == "__main__":
    main()