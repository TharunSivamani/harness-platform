import asyncio

from app.agents.planner import PlannerAgent
from app.tools.loader import load_plugins


async def main():
    load_plugins()
    planner = PlannerAgent()

    cases = [
        "calculate 12 * (5 + 8)",
        "list files in .",
        "run python sum([10, 20, 30])",
        "run echo forge-ok",
    ]

    for prompt in cases:
        result = await planner.run(prompt)
        print(f"\n=== {prompt} ===")
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
