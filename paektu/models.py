"""Core data types for Paektu.

Three things must stay in agreement for a control to be trustworthy:

1. the definition (what the control requires),
2. the evidence (what a machine observed), and
3. the narrative (what a human wrote down about it).

Most compliance tooling models the first two and lets the third rot. The
models here treat the narrative as a first-class artifact with its own
fingerprint, so drift between code and prose becomes detectable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Status(str, Enum):
    """Outcome of evaluating a single control."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    ERROR = "error"
    SKIP = "skip"

    @property
    def is_satisfied(self) -> bool:
        return self is Status.PASS

    @property
    def blocks_audit(self) -> bool:
        """FAIL and ERROR both mean an auditor cannot rely on the control."""
        return self in (Status.FAIL, Status.ERROR)


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


def utcnow() -> str:
    """Timestamp in RFC 3339, always UTC, always suffixed Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprint(text: str) -> str:
    """Stable short hash used for narrative drift detection.

    Whitespace is normalised first so that reflowing a paragraph does not
    register as a substantive documentation change. Reformatting is not
    drift; changed words are.
    """
    normalised = " ".join(text.split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class FrameworkRef:
    """A single citation into an external compliance framework."""

    framework: str
    clause: str
    title: str = ""

    def __str__(self) -> str:
        return f"{self.framework} {self.clause}"


@dataclass
class Control:
    """A requirement that can be mechanically evaluated."""

    id: str
    title: str
    description: str
    check: str
    severity: Severity = Severity.MEDIUM
    frameworks: list[FrameworkRef] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    narrative: str = ""
    narrative_hash: str = ""
    owner: str = "unassigned"
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("control id must not be empty")
        if not self.check:
            raise ValueError(f"control {self.id} declares no check")
        if isinstance(self.severity, str):
            self.severity = Severity(self.severity)

    @property
    def narrative_is_stale(self) -> bool:
        """True when the recorded hash no longer matches the narrative text.

        An empty narrative_hash means the control was never attested, which is
        reported separately from a hash that has actively diverged.
        """
        if not self.narrative_hash:
            return False
        return fingerprint(self.narrative) != self.narrative_hash

    @property
    def narrative_is_unattested(self) -> bool:
        return bool(self.narrative) and not self.narrative_hash

    def frameworks_named(self, name: str) -> list[FrameworkRef]:
        target = name.strip().lower()
        return [f for f in self.frameworks if f.framework.lower() == target]


@dataclass
class Evidence:
    """A machine-collected observation backing a control result.

    content_hash lets an auditor confirm that the artifact handed to them is
    the one the tool actually saw, without the tool having to embed the whole
    payload in the report.
    """

    control_id: str
    collector: str
    collected_at: str = field(default_factory=utcnow)
    summary: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            payload = json.dumps(self.detail, sort_keys=True, default=str)
            self.content_hash = fingerprint(payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckResult:
    """The outcome of evaluating one control against one target."""

    control_id: str
    status: Status
    message: str
    severity: Severity = Severity.MEDIUM
    evidence: list[Evidence] = field(default_factory=list)
    remediation: str = ""
    checked_at: str = field(default_factory=utcnow)
    narrative_stale: bool = False
    narrative_unattested: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            self.status = Status(self.status)
        if isinstance(self.severity, str):
            self.severity = Severity(self.severity)

    @property
    def needs_attention(self) -> bool:
        """A passing control with stale prose still needs a human."""
        return self.status.blocks_audit or self.narrative_stale

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "status": self.status.value,
            "severity": self.severity.value,
            "message": self.message,
            "remediation": self.remediation,
            "checked_at": self.checked_at,
            "narrative_stale": self.narrative_stale,
            "narrative_unattested": self.narrative_unattested,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class RunSummary:
    """Aggregate view of one full evaluation pass."""

    started_at: str
    finished_at: str
    target: str
    results: list[CheckResult] = field(default_factory=list)

    def by_status(self, status: Status) -> list[CheckResult]:
        return [r for r in self.results if r.status is status]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passing(self) -> int:
        return len(self.by_status(Status.PASS))

    @property
    def stale_narratives(self) -> list[CheckResult]:
        return [r for r in self.results if r.narrative_stale]

    @property
    def unattested_narratives(self) -> list[CheckResult]:
        """Controls whose prose exists but has never been reviewed.

        Distinct from stale: nobody has confirmed these words yet, as opposed to
        confirming them and then changing them. Surfaced separately because every
        control carries this state, not only the one using the
        docs.narrative_current check.
        """
        return [r for r in self.results if r.narrative_unattested]

    @property
    def score(self) -> float:
        """Share of evaluated controls that passed, ignoring skips.

        Skipped controls are excluded rather than counted as failures: a
        control that does not apply should not drag the posture score down.
        """
        considered = [r for r in self.results if r.status is not Status.SKIP]
        if not considered:
            return 0.0
        satisfied = sum(1 for r in considered if r.status.is_satisfied)
        return round(100.0 * satisfied / len(considered), 1)

    @property
    def audit_ready(self) -> bool:
        """No blocking failures and no prose that has drifted from reality."""
        return not any(r.needs_attention for r in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "target": self.target,
            "score": self.score,
            "audit_ready": self.audit_ready,
            "totals": {
                "total": self.total,
                "pass": self.passing,
                "fail": len(self.by_status(Status.FAIL)),
                "warn": len(self.by_status(Status.WARN)),
                "error": len(self.by_status(Status.ERROR)),
                "skip": len(self.by_status(Status.SKIP)),
                "stale_narratives": len(self.stale_narratives),
                "unattested_narratives": len(self.unattested_narratives),
            },
            "results": [r.to_dict() for r in self.results],
        }
