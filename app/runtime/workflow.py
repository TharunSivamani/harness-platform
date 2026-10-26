from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class WorkflowNode:
    node_id: str
    name: str
    handler: Callable[..., Awaitable[Any]]
    depends_on: list[str] = field(default_factory=list)
    retries: int = 0


@dataclass
class WorkflowResult:
    workflow_id: str
    success: bool
    outputs: dict[str, Any]
    errors: dict[str, str]


class WorkflowEngine:
    """
    Dependency-aware task graph executor with limited parallelism.
    """

    def __init__(self):
        self._workflows: dict[str, list[WorkflowNode]] = {}

    def create(self, nodes: list[WorkflowNode] | None = None) -> str:
        workflow_id = str(uuid4())
        self._workflows[workflow_id] = nodes or []
        return workflow_id

    def add_node(self, workflow_id: str, node: WorkflowNode) -> None:
        self._workflows.setdefault(workflow_id, []).append(node)

    async def run(self, workflow_id: str, context: dict[str, Any] | None = None) -> WorkflowResult:
        nodes = {node.node_id: node for node in self._workflows.get(workflow_id, [])}
        if not nodes:
            return WorkflowResult(workflow_id=workflow_id, success=True, outputs={}, errors={})

        context = context or {}
        completed: set[str] = set()
        outputs: dict[str, Any] = {}
        errors: dict[str, str] = {}

        while len(completed) < len(nodes):
            ready = [
                node
                for node_id, node in nodes.items()
                if node_id not in completed
                and node_id not in errors
                and all(dep in completed for dep in node.depends_on)
            ]
            if not ready:
                for node_id in nodes:
                    if node_id not in completed and node_id not in errors:
                        errors[node_id] = "Unresolved dependency cycle or blocked node."
                break

            async def _run_node(node: WorkflowNode):
                attempt = 0
                while True:
                    try:
                        result = await node.handler(context=context, outputs=outputs)
                        outputs[node.node_id] = result
                        completed.add(node.node_id)
                        return
                    except Exception as exc:  # noqa: BLE001
                        if attempt >= node.retries:
                            errors[node.node_id] = str(exc)
                            return
                        attempt += 1
                        await asyncio.sleep(0.1)

            await asyncio.gather(*[_run_node(node) for node in ready])

        return WorkflowResult(
            workflow_id=workflow_id,
            success=not errors,
            outputs=outputs,
            errors=errors,
        )


workflow_engine = WorkflowEngine()
