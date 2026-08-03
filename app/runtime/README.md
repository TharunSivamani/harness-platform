# `app/runtime/`

Priority-0 runtime services that turn ForgeAI into an execution platform.

## Files

| File | Purpose |
|------|---------|
| `sandbox.py` | `SandboxManager` — local/Docker ephemeral command execution |
| `workspace.py` | `WorkspaceManager` — per-session isolated folders + quotas |
| `artifacts.py` | `ArtifactManager` — versioned output storage |
| `events.py` | `EventBus` — publish/subscribe + history |
| `state.py` | `StateMachine` — NEW→…→COMPLETED/FAILED transitions |
| `workflow.py` | `WorkflowEngine` — dependency graph + parallel ready nodes |
| `queue.py` | `TaskQueue` — async worker pool queue |
| `permissions.py` | `PermissionEngine` — role → permission checks |
| `scheduler.py` | `ResourceScheduler` — CPU/memory/GPU leases |
| `recorder.py` | `ExecutionRecorder` — JSONL execution traces + replay inputs |

## Examples

```python
from app.runtime.workspace import workspace_manager
from app.runtime.artifacts import artifact_manager
from app.runtime.sandbox import sandbox_manager

ws = workspace_manager.create()
result = await sandbox_manager.execute("echo hi", workdir=ws.path)
artifact = artifact_manager.store(b"report", name="report.txt", media_type="text/plain")
```

```python
from app.runtime.state import state_machine, TaskState

task = state_machine.create("do work")
state_machine.transition(task.task_id, TaskState.PLANNING)
state_machine.transition(task.task_id, TaskState.RUNNING)
state_machine.transition(task.task_id, TaskState.COMPLETED, output={"ok": True})
```

```python
from app.runtime.workflow import WorkflowEngine, WorkflowNode

engine = WorkflowEngine()
wf = engine.create()

async def step_a(context, outputs):
    return 1

engine.add_node(wf, WorkflowNode("a", "a", step_a))
print(await engine.run(wf))
```
