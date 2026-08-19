"""Report rendering.

Two audiences, two formats. A human reviewing a pull request wants a table in
their terminal; an auditor wants a document with dates, evidence hashes and
framework citations they can file.

Markdown is the archive format rather than PDF because it diffs. Being able to
see what changed between last quarter's report and this one is worth more than
typographic polish.
"""

from __future__ import annotations

import json
from typing import Iterable

from .drift import DriftReport
from .frameworks import Coverage, canonical
from .models import Control, RunSummary, Status

GLYPH = {
    Status.PASS: "PASS",
    Status.FAIL: "FAIL",
    Status.WARN: "WARN",
    Status.ERROR: "ERR ",
    Status.SKIP: "SKIP",
}


def _truncate(text: str, width: int) -> str:
    """Collapse whitespace and clip to width.

    Uses an ASCII ellipsis rather than the typographic one, because Windows
    consoles still default to cp1252 and a single stray character turns the
    whole table into mojibake.
    """
    text = " ".join(text.split())
    return text if len(text) <= width else text[: max(width - 3, 1)] + "..."


def console_table(summary: RunSummary, width: int = 96) -> str:
    """Render a run as a fixed-width table for a terminal."""
    lines: list[str] = []
    id_width = max((len(r.control_id) for r in summary.results), default=10)
    id_width = min(max(id_width, 10), 28)
    message_width = max(width - id_width - 18, 20)

    lines.append(f"{'STATUS':<7}{'CONTROL':<{id_width + 2}}{'SEV':<10}MESSAGE")
    lines.append("-" * width)

    order = {Status.FAIL: 0, Status.ERROR: 1, Status.WARN: 2, Status.SKIP: 3, Status.PASS: 4}
    for result in sorted(summary.results, key=lambda r: (order[r.status], r.control_id)):
        flag = " (doc)" if result.narrative_stale else ""
        lines.append(
            f"{GLYPH[result.status]:<7}"
            f"{result.control_id:<{id_width + 2}}"
            f"{result.severity.value:<10}"
            f"{_truncate(result.message + flag, message_width)}"
        )

    lines.append("-" * width)
    totals = summary.to_dict()["totals"]
    lines.append(
        f"{summary.total} controls   "
        f"pass {totals['pass']}   fail {totals['fail']}   warn {totals['warn']}   "
        f"error {totals['error']}   skip {totals['skip']}"
    )
    lines.append(f"posture score {summary.score}%")

    if summary.stale_narratives:
        ids = ", ".join(r.control_id for r in summary.stale_narratives)
        lines.append(f"documentation drift on {len(summary.stale_narratives)} control(s): {ids}")

    if summary.unattested_narratives:
        ids = ", ".join(r.control_id for r in summary.unattested_narratives)
        lines.append(
            f"never attested on {len(summary.unattested_narratives)} control(s): {ids}"
        )

    lines.append("audit ready: " + ("yes" if summary.audit_ready else "no"))
    return "\n".join(lines)


def markdown_report(
    summary: RunSummary,
    controls: Iterable[Control],
    coverages: Iterable[Coverage] = (),
) -> str:
    """Render an audit-facing Markdown report."""
    by_id = {c.id: c for c in controls}
    totals = summary.to_dict()["totals"]

    out: list[str] = []
    out.append("# Compliance posture report")
    out.append("")
    out.append(f"- Target: `{summary.target}`")
    out.append(f"- Run started: {summary.started_at}")
    out.append(f"- Run finished: {summary.finished_at}")
    out.append(f"- Posture score: **{summary.score}%**")
    out.append(f"- Audit ready: **{'yes' if summary.audit_ready else 'no'}**")
    out.append("")

    out.append("## Totals")
    out.append("")
    out.append("| Outcome | Count |")
    out.append("| --- | --- |")
    for key in ("total", "pass", "fail", "warn", "error", "skip", "stale_narratives", "unattested_narratives"):
        out.append(f"| {key.replace('_', ' ')} | {totals[key]} |")
    out.append("")

    blocking = [r for r in summary.results if r.status.blocks_audit]
    if blocking:
        out.append("## Findings requiring remediation")
        out.append("")
        for result in sorted(blocking, key=lambda r: -r.severity.rank):
            control = by_id.get(result.control_id)
            title = control.title if control else result.control_id
            out.append(f"### {result.control_id} — {title}")
            out.append("")
            out.append(f"- Status: **{result.status.value}**")
            out.append(f"- Severity: {result.severity.value}")
            out.append(f"- Observed: {result.message}")
            if result.remediation:
                out.append(f"- Remediation: {result.remediation}")
            if control and control.frameworks:
                cites = ", ".join(str(f) for f in control.frameworks)
                out.append(f"- Frameworks: {cites}")
            if control and control.owner != "unassigned":
                out.append(f"- Owner: {control.owner}")
            out.append("")

    stale = summary.stale_narratives
    if stale:
        out.append("## Documentation drift")
        out.append("")
        out.append(
            "These controls are technically satisfied, but the written narrative has "
            "changed since it was last reviewed. The check result can be trusted; the "
            "prose cannot."
        )
        out.append("")
        for result in stale:
            control = by_id.get(result.control_id)
            out.append(f"- `{result.control_id}` — {control.title if control else 'unknown'}")
        out.append("")

    out.append("## All controls")
    out.append("")
    out.append("| Control | Status | Severity | Owner | Frameworks |")
    out.append("| --- | --- | --- | --- | --- |")
    for result in sorted(summary.results, key=lambda r: r.control_id):
        control = by_id.get(result.control_id)
        cites = ", ".join(str(f) for f in control.frameworks) if control else ""
        owner = control.owner if control else ""
        out.append(
            f"| `{result.control_id}` | {result.status.value} | {result.severity.value} "
            f"| {owner} | {cites} |"
        )
    out.append("")

    coverages = list(coverages)
    if coverages:
        out.append("## Framework coverage")
        out.append("")
        out.append(
            "Coverage counts clauses this control set speaks to, not clauses passed. "
            "A high number here is not a claim of compliance."
        )
        out.append("")
        for cov in coverages:
            out.append(f"### {cov.framework}")
            out.append("")
            out.append(
                f"{len(cov.mapped)} of {cov.total_clauses} catalogued clauses addressed "
                f"({cov.percent}%)."
            )
            out.append("")
            if cov.mapped:
                out.append("| Clause | Title | Controls |")
                out.append("| --- | --- | --- |")
                for clause, ids in cov.mapped.items():
                    out.append(
                        f"| {clause} | {cov.clause_title(clause)} | "
                        f"{', '.join(f'`{i}`' for i in ids)} |"
                    )
                out.append("")
            if cov.unmapped:
                out.append(f"Gaps: {', '.join(cov.unmapped)}")
                out.append("")
            if cov.unknown:
                out.append(
                    "Clauses cited by controls but absent from the catalogue "
                    "(likely typos): " + ", ".join(cov.unknown)
                )
                out.append("")

    out.append("## Evidence")
    out.append("")
    out.append("| Control | Collector | Collected at | Hash | Summary |")
    out.append("| --- | --- | --- | --- | --- |")
    for result in sorted(summary.results, key=lambda r: r.control_id):
        for item in result.evidence:
            out.append(
                f"| `{item.control_id}` | {item.collector} | {item.collected_at} "
                f"| `{item.content_hash}` | {_truncate(item.summary, 60)} |"
            )
    out.append("")
    out.append(
        "Every hash above is a SHA-256 prefix over the collected detail payload. "
        "Re-running `plumbline check` on an unchanged target reproduces them."
    )
    out.append("")

    return "\n".join(out)


def drift_console(report: DriftReport) -> str:
    """Render a drift comparison for a terminal."""
    lines: list[str] = []
    lines.append(f"baseline {report.baseline_at}  ->  current {report.current_at}")
    lines.append(
        f"score {report.score_before}% -> {report.score_after}% "
        f"({report.score_delta:+.1f})"
    )
    lines.append("")

    if not report.has_drift:
        lines.append("no drift: every control holds the same status as the baseline")
        return "\n".join(lines)

    if report.regressions:
        lines.append(f"REGRESSIONS ({len(report.regressions)})")
        for delta in report.regressions:
            lines.append(
                f"  {delta.control_id} [{delta.severity}] "
                f"{delta.before} -> {delta.after}: {_truncate(delta.message, 60)}"
            )
        lines.append("")

    if report.narrative_drift:
        lines.append(f"DOCUMENTATION DRIFT ({len(report.narrative_drift)})")
        for control_id in report.narrative_drift:
            lines.append(f"  {control_id} narrative changed since attestation")
        lines.append("")

    if report.improvements:
        lines.append(f"IMPROVEMENTS ({len(report.improvements)})")
        for delta in report.improvements:
            lines.append(f"  {delta.control_id} {delta.before} -> {delta.after}")
        lines.append("")

    if report.other_changes:
        lines.append(f"OTHER CHANGES ({len(report.other_changes)})")
        for delta in report.other_changes:
            lines.append(f"  {delta.control_id} {delta.before} -> {delta.after}")
        lines.append("")

    if report.added:
        lines.append(f"ADDED CONTROLS: {', '.join(report.added)}")
    if report.removed:
        lines.append(f"REMOVED CONTROLS: {', '.join(report.removed)}")

    lines.append("")
    lines.append("blocking: " + ("yes" if report.is_blocking else "no"))
    return "\n".join(lines)


def as_json(payload: object) -> str:
    """Serialise any report object for machine consumption."""
    if hasattr(payload, "to_dict"):
        payload = payload.to_dict()
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


def coverage_console(cov: Coverage) -> str:
    """Render framework coverage for a terminal."""
    lines = [
        f"{cov.framework}: {len(cov.mapped)}/{cov.total_clauses} catalogued clauses "
        f"addressed ({cov.percent}%)",
        "",
    ]
    for clause, ids in cov.mapped.items():
        lines.append(f"  {clause:<16} {cov.clause_title(clause)}")
        lines.append(f"  {'':<16} controls: {', '.join(ids)}")
    if cov.unmapped:
        lines.append("")
        lines.append(f"  gaps ({len(cov.unmapped)}): {', '.join(cov.unmapped)}")
    if cov.unknown:
        lines.append("")
        lines.append(f"  uncatalogued clauses cited: {', '.join(cov.unknown)}")
    return "\n".join(lines)


__all__ = [
    "console_table",
    "markdown_report",
    "drift_console",
    "coverage_console",
    "as_json",
    "canonical",
]
