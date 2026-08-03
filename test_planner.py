import asyncio

from app.agents.planner import PlannerAgent


async def main():
    planner = PlannerAgent()

    result = await planner.run("12 * (5 + 8)")

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())