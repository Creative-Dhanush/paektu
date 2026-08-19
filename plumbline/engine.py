"""Evaluation engine.

Runs a set of controls against a target and collects the results. Deliberately
boring: no concurrency, no caching, no clever ordering. A compliance run that
takes three seconds is fast enough, and determinism is worth more than speed
when the output is going to an auditor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from . import checks
from .checks import Target
from .models import CheckResult, Control, RunSummary, Status, utcnow

DEFAULT_POSTURE_FILE = "plumbline.yaml"


class EngineError(RuntimeError):
    pass


def load_posture(root: Path, filename: str = DEFAULT_POSTURE_FILE) -> dict:
    """Read the declared posture document, tolerating its absence.

    A missing posture file is not an error. Repository checks still run, and
    every posture control will fail loudly with a message explaining why, which
    is more useful than refusing to start.
    """
    path = root / filename
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise EngineError(f"{filename}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise EngineError(f"{filename}: expected a mapping at the top level")
    return data.get("posture", data)


def evaluate_one(control: Control, target: Target) -> CheckResult:
    """Evaluate a single control, converting any exception into an ERROR result.

    A check that raises must not abort the run. The failure is recorded against
    the control it belongs to so the report shows exactly which control could
    not be evaluated, rather than losing the whole pass to one bad plugin.
    """
    fn = checks.get(control.check)
    if fn is None:
        available = ", ".join(checks.names())
        return CheckResult(
            control_id=control.id,
            status=Status.ERROR,
            message=f"unknown check {control.check!r}",
            severity=control.severity,
            remediation=f"use one of: {available}",
            narrative_stale=control.narrative_is_stale,
            narrative_unattested=control.narrative_is_unattested,
        )

    try:
        return fn(control, target)
    except Exception as exc:  # noqa: BLE001 - a broken check must not kill the run
        return CheckResult(
            control_id=control.id,
            status=Status.ERROR,
            message=f"check {control.check} raised {type(exc).__name__}: {exc}",
            severity=control.severity,
            remediation="fix the check implementation or the control params",
            narrative_stale=control.narrative_is_stale,
            narrative_unattested=control.narrative_is_unattested,
        )


def run(controls: Iterable[Control], root: Path, posture: dict | None = None) -> RunSummary:
    """Evaluate every control against the given repository root."""
    checks.load_builtins()

    root = root.resolve()
    if not root.is_dir():
        raise EngineError(f"{root} is not a directory")

    target = Target(root=root, posture=posture if posture is not None else load_posture(root))

    started = utcnow()
    results = [evaluate_one(control, target) for control in controls]
    finished = utcnow()

    return RunSummary(
        started_at=started,
        finished_at=finished,
        target=str(root),
        results=results,
    )
