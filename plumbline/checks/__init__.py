"""Check registry.

A check is a plain function that receives the control being evaluated and a
`Target` describing what to inspect, and returns a `CheckResult`. Checks are
registered by name so control YAML can reference them as strings.

Adding a check means writing one function and decorating it. Nothing else in
the codebase needs to know about it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..models import CheckResult, Control, Status

CheckFn = Callable[["Control", "Target"], CheckResult]

_REGISTRY: dict[str, CheckFn] = {}


@dataclass
class Target:
    """What a check is allowed to look at.

    Checks are deliberately confined to a repository path plus a declared
    posture document. There is no network access and no cloud SDK, which keeps
    runs reproducible and means the tool can be pointed at any checkout.
    """

    root: Path
    posture: dict[str, Any] = field(default_factory=dict)

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def exists(self, *candidates: str) -> str | None:
        """Return the first candidate path that exists, else None.

        Accepts several spellings because projects disagree about casing and
        placement (LICENSE vs LICENSE.md vs docs/LICENSE).
        """
        for candidate in candidates:
            if self.path(candidate).exists():
                return candidate
        return None

    def read(self, relative: str) -> str:
        try:
            return self.path(relative).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def posture_get(self, dotted: str, default: Any = None) -> Any:
        """Look up a nested posture value by dotted path."""
        node: Any = self.posture
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def register(name: str) -> Callable[[CheckFn], CheckFn]:
    """Decorator registering a check function under a stable name."""

    def wrapper(fn: CheckFn) -> CheckFn:
        if name in _REGISTRY:
            raise ValueError(f"check {name!r} is already registered")
        _REGISTRY[name] = fn
        return fn

    return wrapper


def get(name: str) -> CheckFn | None:
    return _REGISTRY.get(name)


def names() -> list[str]:
    return sorted(_REGISTRY)


def result(
    control: Control,
    status: Status,
    message: str,
    remediation: str = "",
    evidence: list[Any] | None = None,
) -> CheckResult:
    """Build a CheckResult that inherits the control severity and narrative state."""
    return CheckResult(
        control_id=control.id,
        status=status,
        message=message,
        severity=control.severity,
        remediation=remediation,
        evidence=evidence or [],
        narrative_stale=control.narrative_is_stale,
        narrative_unattested=control.narrative_is_unattested,
    )


def load_builtins() -> None:
    """Import the shipped check modules so their decorators run."""
    from . import docs, posture, repo  # noqa: F401


__all__ = ["Target", "register", "get", "names", "result", "load_builtins", "CheckFn"]
