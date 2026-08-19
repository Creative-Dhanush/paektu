"""Checks that hold documentation to the same standard as code.

This is the part of Plumbline that does not exist in most compliance tooling.
A control can be technically satisfied while the prose describing it is a year
out of date, and an auditor reading that prose is being misled by a system that
reports itself green.

So the narrative is versioned. Each control records the fingerprint of the
narrative text that was last reviewed. Change the words without re-attesting
and the control is flagged, even though the underlying check still passes.
"""

from __future__ import annotations

from ..models import Evidence, Status, fingerprint
from . import Target, register, result


@register("docs.narrative_current")
def narrative_current(control, target: Target):
    """Verify this control's narrative matches its attested fingerprint.

    Three distinct outcomes, deliberately not collapsed into one:

    - no narrative at all           -> FAIL, nothing was ever written
    - narrative but no fingerprint  -> WARN, written but never reviewed
    - fingerprint mismatch          -> FAIL, prose changed after review
    """
    if not control.narrative.strip():
        return result(
            control,
            Status.FAIL,
            "control has no narrative",
            remediation=f"write a narrative for {control.id}, then run: plumbline attest {control.id}",
        )

    current = fingerprint(control.narrative)
    evidence = [
        Evidence(
            control_id=control.id,
            collector="docs.narrative_current",
            summary=f"narrative fingerprint {current}",
            detail={
                "current_fingerprint": current,
                "attested_fingerprint": control.narrative_hash or None,
                "narrative_chars": len(control.narrative),
            },
        )
    ]

    if not control.narrative_hash:
        return result(
            control,
            Status.WARN,
            "narrative exists but has never been attested",
            remediation=f"review the text and run: plumbline attest {control.id}",
            evidence=evidence,
        )

    if current != control.narrative_hash:
        return result(
            control,
            Status.FAIL,
            f"narrative changed since attestation ({control.narrative_hash} -> {current})",
            remediation=f"re-review the narrative and run: plumbline attest {control.id}",
            evidence=evidence,
        )

    return result(control, Status.PASS, "narrative matches its attestation", evidence=evidence)


@register("docs.pages_present")
def pages_present(control, target: Target):
    """Require the documentation set to cover a minimum surface.

    A quickstart that does not exist cannot be followed, and a troubleshooting
    page is the one readers reach for when something has already gone wrong.
    """
    required = control.params.get("pages") or []
    if not required:
        return result(control, Status.ERROR, "control declares no required pages")

    missing = [page for page in required if not target.path(page).exists()]
    thin: list[str] = []
    min_chars = int(control.params.get("min_chars", 200))

    for page in required:
        if page in missing:
            continue
        if len(target.read(page).strip()) < min_chars:
            thin.append(page)

    evidence = [
        Evidence(
            control_id=control.id,
            collector="docs.pages_present",
            summary=f"{len(missing)} missing, {len(thin)} below {min_chars} chars",
            detail={"required": required, "missing": missing, "thin": thin},
        )
    ]

    if missing:
        return result(
            control,
            Status.FAIL,
            f"missing documentation: {', '.join(missing)}",
            remediation="write the missing pages",
            evidence=evidence,
        )
    if thin:
        return result(
            control,
            Status.WARN,
            f"present but thin: {', '.join(thin)}",
            remediation=f"expand these pages past {min_chars} characters of real guidance",
            evidence=evidence,
        )
    return result(
        control, Status.PASS, f"all {len(required)} required pages present", evidence=evidence
    )


@register("docs.evidence_explained")
def evidence_explained(control, target: Target):
    """Require a narrative to say where its evidence comes from.

    A narrative that describes the control but never says how it is verified
    leaves the reader unable to reproduce the finding. The check looks for any
    of a set of phrases that indicate provenance was addressed.
    """
    if not control.narrative.strip():
        return result(control, Status.SKIP, "no narrative to inspect")

    markers = control.params.get("markers") or [
        "evidence",
        "verified",
        "observed",
        "declared",
        "collected",
        "attested",
    ]
    lowered = control.narrative.lower()
    hits = [marker for marker in markers if marker in lowered]

    evidence = [
        Evidence(
            control_id=control.id,
            collector="docs.evidence_explained",
            summary=f"{len(hits)} provenance marker(s)",
            detail={"markers_found": hits, "markers_checked": markers},
        )
    ]

    if hits:
        return result(
            control,
            Status.PASS,
            f"narrative explains provenance ({', '.join(hits)})",
            evidence=evidence,
        )
    return result(
        control,
        Status.WARN,
        "narrative never says how the control is verified",
        remediation="state what evidence backs this control and how a reader can reproduce it",
        evidence=evidence,
    )
