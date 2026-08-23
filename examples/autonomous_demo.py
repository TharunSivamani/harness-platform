import asyncio

from app.agents.runner import agent_runner


async def main():
    run = await agent_runner.start(
        goal="calculate 12 * (5 + 8)",
        auto_approve=True,
        max_steps=4,
    )
    print("started", run.run_id)

    for _ in range(40):
        current = agent_runner.get(run.run_id)
        print("status", current.status, "steps", len(current.steps))
        if current.status in {"completed", "failed"}:
            print(agent_runner.serialize(current))
            break
        await asyncio.sleep(0.25)


if __name__ == "__main__":
    asyncio.run(main())
