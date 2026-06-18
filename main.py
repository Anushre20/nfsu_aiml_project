from agent import run_agent

def main():

    query = input("Ask Question:")

    answer = run_agent(query)

    print("\n FINAL ANSWER")
    print(answer)

if __name__ == "__main__":
    main()