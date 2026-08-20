"""Checks that evaluate the declared security posture.

Some controls cannot be proven by reading a repository: whether MFA is enforced
on the identity provider, how long logs are retained, when access was last
reviewed. Those live in `paektu.yaml`, a document the organisation maintains
deliberately.

A declaration is weaker evidence than an observation, and the tool says so.
Every result from this module records `evidence_type: declared` so a reader can
tell the difference at a glance, and controls can require a named attestation
source before they are allowed to pass.
"""

from __future__ import annotations

from typing import Any

from ..models import Evidence, Status
from . import Target, register, result


def _declared(control, key: str, value: Any, extra: dict[str, Any] | None = None) -> Evidence:
    detail: dict[str, Any] = {
        "key": key,
        "value": value,
        "evidence_type": "declared",
        "source": "paektu.yaml",
    }
    if extra:
        detail.update(extra)
    return Evidence(
        control_id=control.id,
        collector="posture.declared",
        summary=f"{key} = {value!r} (declared)",
        detail=detail,
    )


@register("posture.is_true")
def is_true(control, target: Target):
    """Require a boolean posture key to be explicitly true.

    A missing key is a FAIL rather than a SKIP. Silence is not a control.
    """
    key = control.params.get("key")
    if not key:
        return result(control, Status.ERROR, "control declares no posture key")

    value = target.posture_get(key)
    evidence = [_declared(control, key, value)]

    if value is None:
        return result(
            control,
            Status.FAIL,
            f"{key} is not declared in paektu.yaml",
            remediation=f"declare {key}: true once the control is genuinely in place",
            evidence=evidence,
        )
    if value is True:
        return result(control, Status.PASS, f"{key} is declared true", evidence=evidence)
    return result(
        control,
        Status.FAIL,
        f"{key} is declared {value!r}",
        remediation=f"implement the control, then set {key}: true",
        evidence=evidence,
    )


@register("posture.at_least")
def at_least(control, target: Target):
    """Require a numeric posture value to meet a minimum threshold."""
    key = control.params.get("key")
    minimum = control.params.get("minimum")
    if not key or minimum is None:
        return result(control, Status.ERROR, "control needs both key and minimum params")

    value = target.posture_get(key)
    evidence = [_declared(control, key, value, {"minimum": minimum})]

    if value is None:
        return result(
            control,
            Status.FAIL,
            f"{key} is not declared",
            remediation=f"declare {key} with a value of at least {minimum}",
            evidence=evidence,
        )
    if not isinstance(value, (int, float)):
        return result(
            control,
            Status.ERROR,
            f"{key} is {type(value).__name__}, expected a number",
            evidence=evidence,
        )
    if value >= minimum:
        return result(
            control, Status.PASS, f"{key} is {value} (minimum {minimum})", evidence=evidence
        )
    return result(
        control,
        Status.FAIL,
        f"{key} is {value}, below the required {minimum}",
        remediation=f"raise {key} to at least {minimum}",
        evidence=evidence,
    )


@register("posture.at_most")
def at_most(control, target: Target):
    """Require a numeric posture value to stay under a ceiling.

    Used for things where smaller is safer, such as the number of days a
    privileged session may remain valid.
    """
    key = control.params.get("key")
    maximum = control.params.get("maximum")
    if not key or maximum is None:
        return result(control, Status.ERROR, "control needs both key and maximum params")

    value = target.posture_get(key)
    evidence = [_declared(control, key, value, {"maximum": maximum})]

    if value is None:
        return result(
            control,
            Status.FAIL,
            f"{key} is not declared",
            remediation=f"declare {key} with a value no greater than {maximum}",
            evidence=evidence,
        )
    if not isinstance(value, (int, float)):
        return result(
            control,
            Status.ERROR,
            f"{key} is {type(value).__name__}, expected a number",
            evidence=evidence,
        )
    if value <= maximum:
        return result(
            control, Status.PASS, f"{key} is {value} (maximum {maximum})", evidence=evidence
        )
    return result(
        control,
        Status.FAIL,
        f"{key} is {value}, above the permitted {maximum}",
        remediation=f"reduce {key} to {maximum} or lower",
        evidence=evidence,
    )


@register("posture.one_of")
def one_of(control, target: Target):
    """Require a posture value to be drawn from an approved set."""
    key = control.params.get("key")
    allowed = control.params.get("allowed") or []
    if not key or not allowed:
        return result(control, Status.ERROR, "control needs both key and allowed params")

    value = target.posture_get(key)
    evidence = [_declared(control, key, value, {"allowed": allowed})]

    if value is None:
        return result(
            control,
            Status.FAIL,
            f"{key} is not declared",
            remediation=f"set {key} to one of: {', '.join(map(str, allowed))}",
            evidence=evidence,
        )
    if value in allowed:
        return result(control, Status.PASS, f"{key} is {value!r}", evidence=evidence)
    return result(
        control,
        Status.FAIL,
        f"{key} is {value!r}, which is not an approved value",
        remediation=f"change {key} to one of: {', '.join(map(str, allowed))}",
        evidence=evidence,
    )


@register("posture.attested")
def attested(control, target: Target):
    """Require a posture claim to name who attested it and when.

    A bare `true` is the weakest possible evidence. This check upgrades a
    declaration by demanding an owner and a date, so an auditor knows whose
    signature sits behind the claim.

    Expects a mapping shaped like:

        access_review:
          confirmed: true
          attested_by: security-lead
          attested_on: 2026-08-01
    """
    key = control.params.get("key")
    if not key:
        return result(control, Status.ERROR, "control declares no posture key")

    block = target.posture_get(key)
    if not isinstance(block, dict):
        return result(
            control,
            Status.FAIL,
            f"{key} is not declared as an attestation block",
            remediation=f"declare {key} with confirmed, attested_by and attested_on",
            evidence=[_declared(control, key, block)],
        )

    confirmed = block.get("confirmed")
    who = block.get("attested_by")
    when = block.get("attested_on")
    missing = [
        name
        for name, present in (("confirmed", confirmed is True), ("attested_by", bool(who)), ("attested_on", bool(when)))
        if not present
    ]

    evidence = [
        Evidence(
            control_id=control.id,
            collector="posture.attested",
            summary=f"{key} attested by {who or 'nobody'} on {when or 'no date'}",
            detail={
                "key": key,
                "confirmed": confirmed,
                "attested_by": who,
                "attested_on": when,
                "evidence_type": "attested",
                "source": "paektu.yaml",
            },
        )
    ]

    if missing:
        return result(
            control,
            Status.FAIL,
            f"{key} attestation incomplete, missing: {', '.join(missing)}",
            remediation="record who attested the control and on what date",
            evidence=evidence,
        )
    return result(control, Status.PASS, f"{key} attested by {who} on {when}", evidence=evidence)
