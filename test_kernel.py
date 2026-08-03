import asyncio

from app.kernel.kernel import ExecutionKernel


async def main():
    kernel = ExecutionKernel()

    result = await kernel.execute(
        "calculator",
        expression="10 * (5 + 2)"
    )

    print(result)


asyncio.run(main())