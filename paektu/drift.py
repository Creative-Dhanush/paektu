"""Drift detection between two runs.

Compliance rots quietly. A control that passed in March and fails in August is
the interesting event, and it is invisible if you only ever look at the current
run in isolation.

Drift is reported in four categories, kept separate because they demand
different responses:

- regressions      a control that passed and now fails, fix the system
- improvements     a control that failed and now passes, update the narrative
- narrative drift  the prose moved away from its attestation, re-review it
- structural       controls added or removed since the baseline, review scope
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import RunSummary, Status


@dataclass
class ControlDelta:
    """One control that changed between two runs."""

    control_id: str
    before: str
    after: str
    severity: str
    message: str = ""

    @property
    def is_regression(self) -> bool:
        return self.before == Status.PASS.value and self.after != Status.PASS.value

    @property
    def is_improvement(self) -> bool:
        return self.before != Status.PASS.value and self.after == Status.PASS.value


@dataclass
class DriftReport:
    """The full comparison between a baseline run and a current run."""

    baseline_at: str
    current_at: str
    regressions: list[ControlDelta] = field(default_factory=list)
    improvements: list[ControlDelta] = field(default_factory=list)
    other_changes: list[ControlDelta] = field(default_factory=list)
    narrative_drift: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    score_before: float = 0.0
    score_after: float = 0.0

    @property
    def score_delta(self) -> float:
        return round(self.score_after - self.score_before, 1)

    @property
    def has_drift(self) -> bool:
        return bool(
            self.regressions
            or self.improvements
            or self.other_changes
            or self.narrative_drift
            or self.added
            or self.removed
        )

    @property
    def is_blocking(self) -> bool:
        """Whether this drift should fail a pipeline.

        Regressions block. Narrative drift blocks too, because documentation
        that no longer describes the system is a defect an auditor will find.
        Improvements and added controls never block.
        """
        return bool(self.regressions or self.narrative_drift)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_at": self.baseline_at,
            "current_at": self.current_at,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "score_delta": self.score_delta,
            "blocking": self.is_blocking,
            "regressions": [vars(d) for d in self.regressions],
            "improvements": [vars(d) for d in self.improvements],
            "other_changes": [vars(d) for d in self.other_changes],
            "narrative_drift": self.narrative_drift,
            "added_controls": self.added,
            "removed_controls": self.removed,
        }


def _index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["control_id"]: r for r in payload.get("results", [])}


def compare(baseline: dict[str, Any], current: RunSummary | dict[str, Any]) -> DriftReport:
    """Compare a stored baseline payload against a current run.

    Accepts either a RunSummary or an already-serialised payload for the current
    side, so this works both in-process and against two files on disk.
    """
    current_payload = current.to_dict() if isinstance(current, RunSummary) else current

    before = _index(baseline)
    after = _index(current_payload)

    report = DriftReport(
        baseline_at=baseline.get("finished_at", "unknown"),
        current_at=current_payload.get("finished_at", "unknown"),
        score_before=float(baseline.get("score", 0.0)),
        score_after=float(current_payload.get("score", 0.0)),
    )

    report.added = sorted(set(after) - set(before))
    report.removed = sorted(set(before) - set(after))

    for control_id in sorted(set(before) & set(after)):
        old, new = before[control_id], after[control_id]

        if old.get("status") != new.get("status"):
            delta = ControlDelta(
                control_id=control_id,
                before=old.get("status", "unknown"),
                after=new.get("status", "unknown"),
                severity=new.get("severity", "medium"),
                message=new.get("message", ""),
            )
            if delta.is_regression:
                report.regressions.append(delta)
            elif delta.is_improvement:
                report.improvements.append(delta)
            else:
                report.other_changes.append(delta)

        # Narrative drift is tracked independently of status. A control can hold
        # a PASS across both runs while its documentation silently diverges.
        if new.get("narrative_stale") and not old.get("narrative_stale"):
            report.narrative_drift.append(control_id)

    # Sort regressions worst-first so a truncated console view shows what matters.
    rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    report.regressions.sort(key=lambda d: rank.get(d.severity, 0), reverse=True)

    return report
