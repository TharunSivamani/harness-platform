import asyncio

from app.kernel.kernel import ExecutionKernel


async def main():
    kernel = ExecutionKernel()

    result = await kernel.execute(
        "calculator",
        expression="5 * (12 + 8)"
    )

    print(result.model_dump_json(indent=2))


asyncio.run(main())