from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.storage.paths import paths


@dataclass
class Artifact:
    artifact_id: str
    name: str
    path: Path
    media_type: str
    size: int
    version: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)


class ArtifactManager:
    """
    First-class storage for generated outputs.
    """

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or (paths.root / "artifacts")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        self._artifacts: dict[str, Artifact] = {}
        self._load_index()

    def _load_index(self) -> None:
        if not self._index_path.exists():
            return
        data = json.loads(self._index_path.read_text(encoding="utf-8"))
        for item in data:
            artifact = Artifact(
                artifact_id=item["artifact_id"],
                name=item["name"],
                path=Path(item["path"]),
                media_type=item["media_type"],
                size=item["size"],
                version=item.get("version", 1),
                created_at=item.get("created_at", datetime.now(timezone.utc).isoformat()),
                metadata=item.get("metadata", {}),
            )
            self._artifacts[artifact.artifact_id] = artifact

    def _save_index(self) -> None:
        payload = [
            {
                "artifact_id": artifact.artifact_id,
                "name": artifact.name,
                "path": str(artifact.path),
                "media_type": artifact.media_type,
                "size": artifact.size,
                "version": artifact.version,
                "created_at": artifact.created_at,
                "metadata": artifact.metadata,
            }
            for artifact in self._artifacts.values()
        ]
        self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def store(
        self,
        source: str | Path | bytes,
        *,
        name: str,
        media_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        artifact_id = str(uuid4())
        versions = [
            item for item in self._artifacts.values() if item.name == name
        ]
        version = len(versions) + 1
        folder = self.root / artifact_id
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name

        if isinstance(source, bytes):
            target.write_bytes(source)
        else:
            source_path = Path(source)
            if source_path.exists():
                shutil.copy2(source_path, target)
            else:
                target.write_text(str(source), encoding="utf-8")

        artifact = Artifact(
            artifact_id=artifact_id,
            name=name,
            path=target,
            media_type=media_type,
            size=target.stat().st_size,
            version=version,
            metadata=metadata or {},
        )
        self._artifacts[artifact_id] = artifact
        self._save_index()
        return artifact

    def get(self, artifact_id: str) -> Artifact:
        if artifact_id not in self._artifacts:
            raise KeyError(f"Artifact '{artifact_id}' not found.")
        return self._artifacts[artifact_id]

    def list(self, name: str | None = None) -> list[Artifact]:
        items = list(self._artifacts.values())
        if name:
            items = [item for item in items if item.name == name]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def delete(self, artifact_id: str) -> None:
        artifact = self.get(artifact_id)
        shutil.rmtree(artifact.path.parent, ignore_errors=True)
        self._artifacts.pop(artifact_id, None)
        self._save_index()


artifact_manager = ArtifactManager()
