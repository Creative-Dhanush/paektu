"""Loading and validating control definitions.

Controls live as YAML so that a compliance owner who does not write Python can
still read, review and amend them in a pull request. Validation is strict and
loud: a malformed control is a defect in the audit trail, not something to
silently skip.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

from .models import Control, FrameworkRef, Severity

REQUIRED_FIELDS = ("id", "title", "description", "check")


class ControlError(ValueError):
    """Raised when a control definition cannot be trusted."""


def _parse_frameworks(raw: Any, control_id: str) -> list[FrameworkRef]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ControlError(f"{control_id}: frameworks must be a list")

    refs: list[FrameworkRef] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ControlError(f"{control_id}: each framework entry must be a mapping")
        framework = item.get("framework")
        clause = item.get("clause")
        if not framework or not clause:
            raise ControlError(f"{control_id}: framework entries need framework and clause")
        refs.append(
            FrameworkRef(
                framework=str(framework),
                clause=str(clause),
                title=str(item.get("title", "")),
            )
        )
    return refs


def control_from_dict(data: dict[str, Any], source: str = "<memory>") -> Control:
    """Build a Control from a plain mapping, validating as we go."""
    if not isinstance(data, dict):
        raise ControlError(f"{source}: expected a mapping, got {type(data).__name__}")

    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        raise ControlError(f"{source}: missing required field(s): {', '.join(missing)}")

    severity_raw = str(data.get("severity", "medium")).lower()
    try:
        severity = Severity(severity_raw)
    except ValueError as exc:
        valid = ", ".join(s.value for s in Severity)
        raise ControlError(
            f"{data['id']}: severity {severity_raw!r} is not one of: {valid}"
        ) from exc

    params = data.get("params") or {}
    if not isinstance(params, dict):
        raise ControlError(f"{data['id']}: params must be a mapping")

    tags = data.get("tags") or []
    if not isinstance(tags, list):
        raise ControlError(f"{data['id']}: tags must be a list")

    return Control(
        id=str(data["id"]),
        title=str(data["title"]),
        description=str(data["description"]).strip(),
        check=str(data["check"]),
        severity=severity,
        frameworks=_parse_frameworks(data.get("frameworks"), str(data["id"])),
        params=params,
        narrative=str(data.get("narrative", "")).strip(),
        narrative_hash=str(data.get("narrative_hash", "")),
        owner=str(data.get("owner", "unassigned")),
        tags=[str(t) for t in tags],
    )


def load_file(path: Path) -> list[Control]:
    """Load every control in a single YAML file.

    Accepts either a bare list of controls or a mapping with a `controls` key,
    because both spellings are natural and forcing one is needless friction.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ControlError(f"{path.name}: invalid YAML: {exc}") from exc
    except OSError as exc:
        raise ControlError(f"{path}: cannot read: {exc}") from exc

    if raw is None:
        return []
    if isinstance(raw, dict) and "controls" in raw:
        raw = raw["controls"]
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise ControlError(f"{path.name}: expected a list of controls")

    return [control_from_dict(item, source=path.name) for item in raw]


def load_dir(directory: Path) -> list[Control]:
    """Load all controls from a directory, rejecting duplicate ids.

    Duplicate ids are fatal. Two controls answering to the same name means a
    report can cite a passing result while a failing one exists.
    """
    if not directory.is_dir():
        raise ControlError(f"{directory} is not a directory")

    controls: list[Control] = []
    seen: dict[str, str] = {}

    for path in sorted(directory.rglob("*.y*ml")):
        for control in load_file(path):
            if control.id in seen:
                raise ControlError(
                    f"duplicate control id {control.id!r} in {path.name} "
                    f"(already defined in {seen[control.id]})"
                )
            seen[control.id] = path.name
            controls.append(control)

    return controls


def filter_controls(
    controls: Iterable[Control],
    framework: str | None = None,
    control_id: str | None = None,
    tag: str | None = None,
    min_severity: str | None = None,
) -> list[Control]:
    """Narrow a control set. Filters combine with AND."""
    selected = list(controls)

    if control_id:
        selected = [c for c in selected if c.id == control_id]
    if framework:
        selected = [c for c in selected if c.frameworks_named(framework)]
    if tag:
        selected = [c for c in selected if tag in c.tags]
    if min_severity:
        floor = Severity(min_severity.lower()).rank
        selected = [c for c in selected if c.severity.rank >= floor]

    return selected


def write_attestation(path: Path, control_id: str, new_hash: str) -> bool:
    """Update a control's narrative_hash in place, preserving file layout.

    Rewriting via the YAML serialiser would reflow comments and key order,
    which makes the diff unreviewable. Since a control file is line-oriented,
    a targeted line edit keeps the change legible in a pull request.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    target_index: int | None = None
    indent = ""

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped in (f"id: {control_id}", f"- id: {control_id}", f'id: "{control_id}"'):
            target_index = index
            leading = line[: len(line) - len(line.lstrip())]
            # For a list item (`  - id: X`) the sibling keys sit two columns
            # further right than the dash, because `- ` occupies that space.
            # Getting this wrong produces YAML that no longer parses.
            indent = leading + "  " if stripped.startswith("- ") else leading
            break

    if target_index is None:
        return False

    # Look for an existing narrative_hash inside this control block. A line at
    # or below the control indent that starts a new id ends the block.
    for index in range(target_index + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith(("- id:", "id: ")) and index != target_index:
            break
        if stripped.startswith("narrative_hash:"):
            lines[index] = f"{indent}narrative_hash: {new_hash}\n"
            path.write_text("".join(lines), encoding="utf-8")
            return True

    lines.insert(target_index + 1, f"{indent}narrative_hash: {new_hash}\n")
    path.write_text("".join(lines), encoding="utf-8")
    return True
