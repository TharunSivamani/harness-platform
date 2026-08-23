from __future__ import annotations

from dataclasses import dataclass, field

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {
        "filesystem.read",
        "search",
        "browser.navigate",
        "read_file",
    },
    "member": {
        "filesystem.read",
        "filesystem.write",
        "python.execute",
        "terminal.execute",
        "search",
        "browser.navigate",
        "browser.screenshot",
        "calculator.execute",
        "read_file",
        "write_file",
        "patch",
    },
    "developer": {
        "filesystem.read",
        "filesystem.write",
        "python.execute",
        "terminal.execute",
        "search",
        "browser.navigate",
        "browser.screenshot",
        "calculator.execute",
        "read_file",
        "write_file",
        "patch",
    },
    "owner": {"*"},
    "admin": {"*"},
}


@dataclass
class PermissionDecision:
    allowed: bool
    missing: list[str] = field(default_factory=list)
    role: str = "viewer"


class PermissionEngine:
    """
    Role-based permission checks for tool execution.
    """

    def __init__(self, role_map: dict[str, set[str]] | None = None):
        self.role_map = role_map or ROLE_PERMISSIONS

    def check(self, role: str, required: list[str]) -> PermissionDecision:
        granted = self.role_map.get(role, set())
        if "*" in granted:
            return PermissionDecision(allowed=True, role=role)

        missing = [perm for perm in required if perm not in granted]
        return PermissionDecision(allowed=not missing, missing=missing, role=role)

    def require(self, role: str, required: list[str]) -> None:
        decision = self.check(role, required)
        if not decision.allowed:
            raise PermissionError(
                f"Role '{role}' missing permissions: {', '.join(decision.missing)}"
            )


permission_engine = PermissionEngine()
