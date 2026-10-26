import asyncio

from app.agents.orchestrator import MultiAgentOrchestrator


async def main():
    orch = MultiAgentOrchestrator()
    result = await orch.run("calculate 2 + 2")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
