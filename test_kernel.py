import asyncio

from app.kernel.kernel import ExecutionKernel
from app.tools.loader import load_plugins


async def main():
    load_plugins()
    kernel = ExecutionKernel()

    calc = await kernel.execute(
        "calculator",
        expression="5 * (12 + 8)",
    )
    print("calculator:", calc.model_dump_json(indent=2))

    py = await kernel.execute(
        "python",
        code="sum([1, 2, 3, 4])",
    )
    print("python:", py.model_dump_json(indent=2))

    fs_write = await kernel.execute(
        "filesystem",
        action="write",
        path="hello.txt",
        content="hello forge",
    )
    print("filesystem write:", fs_write.model_dump_json(indent=2))

    fs_read = await kernel.execute(
        "filesystem",
        action="read",
        path="hello.txt",
    )
    print("filesystem read:", fs_read.model_dump_json(indent=2))

    term = await kernel.execute(
        "terminal",
        command="echo forge-ok",
    )
    print("terminal:", term.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
