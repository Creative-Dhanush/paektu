"""Tests for the core data types, especially narrative fingerprinting."""

import pytest

from paektu.models import (
    CheckResult,
    Control,
    Evidence,
    RunSummary,
    Severity,
    Status,
    fingerprint,
)


def make_control(**overrides):
    base = dict(
        id="TEST-001",
        title="A test control",
        description="Exists only for the test suite.",
        check="posture.is_true",
    )
    base.update(overrides)
    return Control(**base)


class TestFingerprint:
    def test_is_stable_across_calls(self):
        assert fingerprint("hello world") == fingerprint("hello world")

    def test_ignores_whitespace_reflow(self):
        """Reformatting a paragraph must not register as documentation drift."""
        one_line = "The control is verified by reading the repository."
        reflowed = "The control is verified\n  by reading   the repository."
        assert fingerprint(one_line) == fingerprint(reflowed)

    def test_detects_changed_words(self):
        assert fingerprint("logs kept 90 days") != fingerprint("logs kept 30 days")

    def test_is_short_enough_to_read(self):
        assert len(fingerprint("anything")) == 16


class TestStatus:
    def test_only_pass_is_satisfied(self):
        assert Status.PASS.is_satisfied
        for other in (Status.FAIL, Status.WARN, Status.ERROR, Status.SKIP):
            assert not other.is_satisfied

    def test_fail_and_error_block_an_audit(self):
        assert Status.FAIL.blocks_audit
        assert Status.ERROR.blocks_audit

    def test_warn_and_skip_do_not_block(self):
        """A warning is information, not a finding that stops an audit."""
        assert not Status.WARN.blocks_audit
        assert not Status.SKIP.blocks_audit


class TestSeverityOrdering:
    def test_ranks_ascend(self):
        assert Severity.LOW.rank < Severity.MEDIUM.rank
        assert Severity.MEDIUM.rank < Severity.HIGH.rank
        assert Severity.HIGH.rank < Severity.CRITICAL.rank


class TestControl:
    def test_rejects_empty_id(self):
        with pytest.raises(ValueError):
            make_control(id="")

    def test_rejects_missing_check(self):
        with pytest.raises(ValueError, match="no check"):
            make_control(check="")

    def test_coerces_string_severity(self):
        assert make_control(severity="critical").severity is Severity.CRITICAL

    def test_narrative_not_stale_when_hash_matches(self):
        text = "Verified by reading the repository."
        control = make_control(narrative=text, narrative_hash=fingerprint(text))
        assert not control.narrative_is_stale

    def test_narrative_stale_when_text_changed(self):
        control = make_control(
            narrative="Retention is 90 days.", narrative_hash=fingerprint("Retention is 30 days.")
        )
        assert control.narrative_is_stale

    def test_unattested_is_distinct_from_stale(self):
        """Never reviewed and reviewed-then-changed are different problems."""
        control = make_control(narrative="Some prose.", narrative_hash="")
        assert control.narrative_is_unattested
        assert not control.narrative_is_stale

    def test_empty_narrative_is_neither(self):
        control = make_control(narrative="", narrative_hash="")
        assert not control.narrative_is_unattested
        assert not control.narrative_is_stale


class TestEvidence:
    def test_hashes_detail_when_not_supplied(self):
        evidence = Evidence(control_id="X", collector="test", detail={"a": 1})
        assert evidence.content_hash

    def test_same_detail_hashes_identically_regardless_of_key_order(self):
        first = Evidence(control_id="X", collector="t", detail={"a": 1, "b": 2})
        second = Evidence(control_id="X", collector="t", detail={"b": 2, "a": 1})
        assert first.content_hash == second.content_hash

    def test_different_detail_hashes_differently(self):
        first = Evidence(control_id="X", collector="t", detail={"a": 1})
        second = Evidence(control_id="X", collector="t", detail={"a": 2})
        assert first.content_hash != second.content_hash


class TestCheckResult:
    def test_passing_result_with_stale_prose_still_needs_attention(self):
        """The central claim of the tool: green does not mean finished."""
        result = CheckResult(
            control_id="X", status=Status.PASS, message="fine", narrative_stale=True
        )
        assert not result.status.blocks_audit
        assert result.needs_attention


def summary_with(*statuses):
    return RunSummary(
        started_at="2026-08-19T00:00:00Z",
        finished_at="2026-08-19T00:00:01Z",
        target="/tmp/x",
        results=[
            CheckResult(control_id=f"C-{i}", status=s, message="")
            for i, s in enumerate(statuses)
        ],
    )


class TestRunSummary:
    def test_score_is_share_of_passing(self):
        assert summary_with(Status.PASS, Status.PASS, Status.FAIL, Status.FAIL).score == 50.0

    def test_skips_are_excluded_from_the_score(self):
        """A control that does not apply must not drag the score down."""
        assert summary_with(Status.PASS, Status.SKIP).score == 100.0

    def test_empty_run_scores_zero_rather_than_dividing_by_zero(self):
        assert summary_with().score == 0.0

    def test_audit_ready_requires_no_failures(self):
        assert summary_with(Status.PASS, Status.PASS).audit_ready
        assert not summary_with(Status.PASS, Status.FAIL).audit_ready

    def test_audit_ready_is_false_when_only_prose_drifted(self):
        run = summary_with(Status.PASS)
        run.results[0].narrative_stale = True
        assert run.score == 100.0
        assert not run.audit_ready

    def test_serialises_totals(self):
        payload = summary_with(Status.PASS, Status.FAIL, Status.WARN).to_dict()
        assert payload["totals"]["total"] == 3
        assert payload["totals"]["pass"] == 1
        assert payload["totals"]["fail"] == 1
        assert payload["totals"]["warn"] == 1
