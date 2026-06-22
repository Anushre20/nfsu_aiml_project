from agent.core import run_agent
from agent.task_planner import TaskPlanner


class PlannerLLM:
    def __call__(self, prompt):
        from agent.llm import call_llm
        return call_llm(prompt)


def main():
    while True:
        query = input("\nAsk Question: ")

        if query.lower() == "exit":
            break

        planner = TaskPlanner(
            agent=None,
            llm=PlannerLLM()
        )

        subtasks = planner.decompose_task(query)

        print("\nGenerated Subtasks:")
        for i, task in enumerate(subtasks, start=1):
            print(f"{i}. {task}")

        result = run_agent(
            query,
            subtasks=subtasks
        )

        if isinstance(result, dict):
            answer = result["final_answer"]
        else:
            answer = result

        print("\nFINAL ANSWER")
        print(answer)


if __name__ == "__main__":
    main()
