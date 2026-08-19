"""Checks that inspect the repository itself.

These read files on disk. They never call out to a hosting provider, so they
verify what is committed rather than what a dashboard claims. That distinction
matters during an audit: a branch protection rule configured in a web UI and
never captured in the repo leaves no evidence trail.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import Evidence, Status
from . import Target, register, result

SECRET_PATTERNS: list[tuple[str, str]] = [
    ("aws_access_key", r"AKIA[0-9A-Z]{16}"),
    ("private_key_block", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("generic_api_key", r"(?i)(?:api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{24,}['\"]"),
    ("slack_token", r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    ("gh_token", r"gh[pousr]_[A-Za-z0-9]{36,}"),
]

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".tox", ".ruff_cache",
}

TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".env", ".sh", ".ps1", ".md", ".txt", ".tf", ".rb", ".go",
}


def _walk_text_files(root: Path, limit: int = 2000):
    """Yield text-ish files under root, skipping vendored and cache dirs."""
    count = 0
    for path in root.rglob("*"):
        if count >= limit:
            return
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        count += 1
        yield path


@register("repo.file_present")
def file_present(control, target: Target):
    """Assert that at least one of the named files exists.

    Used for LICENSE, SECURITY.md, CODE_OF_CONDUCT and similar. The candidate
    list comes from control params so one check serves many controls.
    """
    candidates = control.params.get("any_of") or []
    if not candidates:
        return result(control, Status.ERROR, "control declares no any_of paths")

    found = target.exists(*candidates)
    if found:
        evidence = Evidence(
            control_id=control.id,
            collector="repo.file_present",
            summary=f"found {found}",
            detail={"path": found, "candidates": candidates},
        )
        return result(control, Status.PASS, f"{found} is present", evidence=[evidence])

    return result(
        control,
        Status.FAIL,
        "none of the expected files exist",
        remediation=f"add one of: {', '.join(candidates)}",
        evidence=[
            Evidence(
                control_id=control.id,
                collector="repo.file_present",
                summary="no candidate matched",
                detail={"candidates": candidates},
            )
        ],
    )


@register("repo.no_hardcoded_secrets")
def no_hardcoded_secrets(control, target: Target):
    """Scan committed text files for credential-shaped strings.

    This is a coarse net on purpose. It exists to catch the obvious mistake,
    not to replace a dedicated secret scanner, and the narrative for the
    control should say so plainly.
    """
    allowlist = set(control.params.get("allow_paths") or [])
    hits: list[dict[str, object]] = []

    for path in _walk_text_files(target.root):
        rel = path.relative_to(target.root).as_posix()
        if any(rel.startswith(prefix) for prefix in allowlist):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for label, pattern in SECRET_PATTERNS:
            match = re.search(pattern, text)
            if match:
                line = text[: match.start()].count("\n") + 1
                hits.append({"path": rel, "line": line, "pattern": label})

    if not hits:
        return result(
            control,
            Status.PASS,
            "no credential-shaped strings found in tracked text files",
            evidence=[
                Evidence(
                    control_id=control.id,
                    collector="repo.no_hardcoded_secrets",
                    summary="clean scan",
                    detail={"patterns_checked": [p[0] for p in SECRET_PATTERNS]},
                )
            ],
        )

    listed = ", ".join(f"{h['path']}:{h['line']} ({h['pattern']})" for h in hits[:5])
    return result(
        control,
        Status.FAIL,
        f"{len(hits)} possible secret(s): {listed}",
        remediation="rotate the credential, purge it from history, and move it to a secret manager",
        evidence=[
            Evidence(
                control_id=control.id,
                collector="repo.no_hardcoded_secrets",
                summary=f"{len(hits)} candidate secrets",
                detail={"hits": hits},
            )
        ],
    )


@register("repo.dependencies_pinned")
def dependencies_pinned(control, target: Target):
    """Require dependency declarations to carry version constraints.

    An unpinned dependency means the artifact an auditor reviewed is not
    necessarily the artifact that ships next week.
    """
    manifests = control.params.get("manifests") or ["requirements.txt"]
    checked: list[str] = []
    unpinned: list[str] = []

    for manifest in manifests:
        if not target.path(manifest).exists():
            continue
        checked.append(manifest)
        for raw in target.read(manifest).splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", "-", "[")):
                continue
            if not re.search(r"(==|>=|<=|~=|>|<|@)", line):
                unpinned.append(f"{manifest}: {line}")

    if not checked:
        return result(
            control,
            Status.SKIP,
            f"no dependency manifest found among {', '.join(manifests)}",
        )

    evidence = Evidence(
        control_id=control.id,
        collector="repo.dependencies_pinned",
        summary=f"{len(unpinned)} unpinned across {len(checked)} manifest(s)",
        detail={"manifests": checked, "unpinned": unpinned},
    )

    if unpinned:
        return result(
            control,
            Status.FAIL,
            f"{len(unpinned)} dependency line(s) carry no version constraint",
            remediation="pin every dependency to an exact or bounded version",
            evidence=[evidence],
        )
    return result(
        control,
        Status.PASS,
        f"all dependencies pinned across {', '.join(checked)}",
        evidence=[evidence],
    )


@register("repo.ci_configured")
def ci_configured(control, target: Target):
    """Require an automated pipeline definition to exist in the repo."""
    workflow_dir = target.path(".github", "workflows")
    workflows = (
        sorted(p.name for p in workflow_dir.glob("*.y*ml")) if workflow_dir.is_dir() else []
    )
    others = [c for c in (".gitlab-ci.yml", "Jenkinsfile", ".circleci/config.yml")
              if target.path(c).exists()]

    if workflows or others:
        return result(
            control,
            Status.PASS,
            f"pipeline defined ({', '.join(workflows + others)})",
            evidence=[
                Evidence(
                    control_id=control.id,
                    collector="repo.ci_configured",
                    summary="pipeline present",
                    detail={"workflows": workflows, "other": others},
                )
            ],
        )
    return result(
        control,
        Status.FAIL,
        "no CI pipeline definition found",
        remediation="add a pipeline that runs tests and checks on every push",
    )


@register("repo.tests_present")
def tests_present(control, target: Target):
    """Require a test suite, and warn when it is suspiciously thin."""
    minimum = int(control.params.get("min_files", 1))
    roots = control.params.get("paths") or ["tests", "test"]

    found: list[str] = []
    for candidate in roots:
        directory = target.path(candidate)
        if directory.is_dir():
            found.extend(
                p.relative_to(target.root).as_posix() for p in directory.rglob("test_*.py")
            )

    evidence = Evidence(
        control_id=control.id,
        collector="repo.tests_present",
        summary=f"{len(found)} test file(s)",
        detail={"files": sorted(found)},
    )

    if not found:
        return result(
            control,
            Status.FAIL,
            "no test files found",
            remediation=f"add tests under {roots[0]}/",
            evidence=[evidence],
        )
    if len(found) < minimum:
        return result(
            control,
            Status.WARN,
            f"only {len(found)} test file(s), expected at least {minimum}",
            remediation="broaden test coverage",
            evidence=[evidence],
        )
    return result(control, Status.PASS, f"{len(found)} test file(s) present", evidence=[evidence])


@register("repo.gitignore_excludes")
def gitignore_excludes(control, target: Target):
    """Check that .gitignore excludes patterns that must never be committed."""
    required = control.params.get("patterns") or [".env"]
    if not target.path(".gitignore").exists():
        return result(
            control,
            Status.FAIL,
            "no .gitignore present",
            remediation="add a .gitignore excluding secrets and build artifacts",
        )

    body = target.read(".gitignore")
    entries = {line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#")}
    missing = [pattern for pattern in required if pattern not in entries]

    evidence = Evidence(
        control_id=control.id,
        collector="repo.gitignore_excludes",
        summary=f"{len(missing)} required pattern(s) missing",
        detail={"required": required, "missing": missing},
    )

    if missing:
        return result(
            control,
            Status.FAIL,
            f".gitignore is missing: {', '.join(missing)}",
            remediation="add the missing patterns to .gitignore",
            evidence=[evidence],
        )
    return result(control, Status.PASS, "all required patterns ignored", evidence=[evidence])
