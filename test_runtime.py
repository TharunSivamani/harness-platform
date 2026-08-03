import asyncio

from app.runtime.sandbox import sandbox_manager
from app.runtime.workspace import workspace_manager
from app.runtime.artifacts import artifact_manager
from app.runtime.events import event_bus
from app.runtime.state import TaskState, state_machine
from app.kernel.kernel import ExecutionKernel


async def main():
    await event_bus.publish("TaskStarted", {"demo": True})

    workspace = workspace_manager.create()
    print("workspace:", workspace.workspace_id, workspace.path)

    artifact = artifact_manager.store(
        b"hello artifact",
        name="hello.txt",
        media_type="text/plain",
        metadata={"workspace_id": workspace.workspace_id},
    )
    print("artifact:", artifact.artifact_id)

    sandbox = await sandbox_manager.execute("echo sandbox-ok", workdir=workspace.path)
    print("sandbox:", sandbox.success, sandbox.stdout.strip())

    task = state_machine.create("demo")
    state_machine.transition(task.task_id, TaskState.PLANNING)
    state_machine.transition(task.task_id, TaskState.RUNNING)

    kernel = ExecutionKernel()
    result = await kernel.execute("calculator", expression="2+2")
    print("kernel:", result.model_dump())

    state_machine.transition(task.task_id, TaskState.COMPLETED, output=result.output)
    print("events:", [event.type for event in event_bus.history()])


if __name__ == "__main__":
    asyncio.run(main())
