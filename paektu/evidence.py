"""Evidence store.

An auditor does not want a dashboard, they want artifacts with dates on them.
This module writes each run to a timestamped JSON file and maintains a manifest
so the history is walkable without a database.

Runs are append-only by design. Nothing here mutates or deletes a previous run,
because a compliance tool that can quietly rewrite its own history is worth
very little as a source of truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import RunSummary, fingerprint, utcnow

DEFAULT_STORE = ".paektu/evidence"
MANIFEST_NAME = "manifest.json"


@dataclass
class StoredRun:
    """A run as recorded on disk."""

    path: Path
    recorded_at: str
    score: float
    audit_ready: bool
    run_hash: str

    @property
    def filename(self) -> str:
        return self.path.name


class EvidenceStore:
    """Append-only collection of run artifacts on the filesystem."""

    def __init__(self, root: Path, subdir: str = DEFAULT_STORE) -> None:
        self.dir = Path(root) / subdir
        self.manifest_path = self.dir / MANIFEST_NAME

    def ensure(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)

    def _read_manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data.get("runs", []) if isinstance(data, dict) else []

    def _write_manifest(self, runs: list[dict[str, Any]]) -> None:
        payload = {
            "updated_at": utcnow(),
            "count": len(runs),
            "runs": runs,
        }
        self.manifest_path.write_text(
            json.dumps(payload, indent=2, sort_keys=False, default=str) + "\n",
            encoding="utf-8",
        )

    def save(self, summary: RunSummary, label: str = "") -> StoredRun:
        """Persist a run and add it to the manifest.

        The filename carries the timestamp so a directory listing is already
        sorted chronologically. The run hash covers the full serialised payload,
        which lets a reviewer prove a stored artifact has not been edited after
        the fact.
        """
        self.ensure()

        body = summary.to_dict()
        if label:
            body["label"] = label
        serialised = json.dumps(body, indent=2, sort_keys=True, default=str)
        run_hash = fingerprint(serialised)

        stamp = summary.finished_at.replace(":", "").replace("-", "")
        suffix = f"-{label}" if label else ""
        path = self.dir / f"run-{stamp}{suffix}.json"

        body["run_hash"] = run_hash
        path.write_text(
            json.dumps(body, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )

        runs = self._read_manifest()
        runs.append(
            {
                "file": path.name,
                "recorded_at": summary.finished_at,
                "score": summary.score,
                "audit_ready": summary.audit_ready,
                "run_hash": run_hash,
                "label": label,
            }
        )
        self._write_manifest(runs)

        return StoredRun(
            path=path,
            recorded_at=summary.finished_at,
            score=summary.score,
            audit_ready=summary.audit_ready,
            run_hash=run_hash,
        )

    def history(self) -> list[StoredRun]:
        """Every recorded run, oldest first."""
        stored: list[StoredRun] = []
        for entry in self._read_manifest():
            stored.append(
                StoredRun(
                    path=self.dir / entry.get("file", ""),
                    recorded_at=entry.get("recorded_at", ""),
                    score=float(entry.get("score", 0.0)),
                    audit_ready=bool(entry.get("audit_ready", False)),
                    run_hash=entry.get("run_hash", ""),
                )
            )
        return stored

    def latest(self) -> dict[str, Any] | None:
        """Load the most recent run payload, or None if the store is empty."""
        runs = self.history()
        if not runs:
            return None
        return self.load(runs[-1].path)

    @staticmethod
    def load(path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def verify(self) -> list[tuple[str, str]]:
        """Re-hash every stored run and report any that no longer match.

        Returns a list of (filename, reason) for each artifact that failed
        verification. An empty list means the history is intact.
        """
        problems: list[tuple[str, str]] = []
        for entry in self._read_manifest():
            name = entry.get("file", "")
            path = self.dir / name
            payload = self.load(path)
            if payload is None:
                problems.append((name, "missing or unreadable"))
                continue
            recorded = payload.pop("run_hash", None)
            recomputed = fingerprint(json.dumps(payload, indent=2, sort_keys=True, default=str))
            if recorded != entry.get("run_hash"):
                problems.append((name, "manifest hash disagrees with file"))
            elif recomputed != recorded:
                problems.append((name, "contents changed after recording"))
        return problems
