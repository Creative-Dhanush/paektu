"""Tests for drift detection and the documentation-drift checks.

These cover the behaviour that distinguishes Paektu from a linter: a control
holding a PASS across two runs while its narrative silently diverges.
"""

import pytest

from paektu import checks
from paektu.checks import Target
from paektu.drift import compare
from paektu.models import CheckResult, Control, RunSummary, Status, fingerprint

checks.load_builtins()


def payload(*, finished="2026-08-01T00:00:00Z", score=0.0, results=None):
    return {
        "finished_at": finished,
        "score": score,
        "results": results or [],
    }


def entry(control_id, status, severity="high", narrative_stale=False):
    return {
        "control_id": control_id,
        "status": status,
        "severity": severity,
        "message": "",
        "narrative_stale": narrative_stale,
    }


class TestDriftComparison:
    def test_identical_runs_show_no_drift(self):
        before = payload(results=[entry("A", "pass")], score=100.0)
        after = payload(results=[entry("A", "pass")], score=100.0)
        assert not compare(before, after).has_drift

    def test_detects_a_regression(self):
        before = payload(results=[entry("A", "pass")], score=100.0)
        after = payload(results=[entry("A", "fail")], score=0.0)
        report = compare(before, after)
        assert len(report.regressions) == 1
        assert report.regressions[0].control_id == "A"
        assert report.is_blocking

    def test_detects_an_improvement_without_blocking(self):
        before = payload(results=[entry("A", "fail")], score=0.0)
        after = payload(results=[entry("A", "pass")], score=100.0)
        report = compare(before, after)
        assert len(report.improvements) == 1
        assert not report.is_blocking

    def test_reports_score_delta(self):
        report = compare(payload(score=60.0), payload(score=85.5))
        assert report.score_delta == 25.5

    def test_notices_added_and_removed_controls(self):
        before = payload(results=[entry("A", "pass"), entry("B", "pass")])
        after = payload(results=[entry("A", "pass"), entry("C", "pass")])
        report = compare(before, after)
        assert report.added == ["C"]
        assert report.removed == ["B"]

    def test_added_controls_alone_do_not_block(self):
        before = payload(results=[entry("A", "pass")])
        after = payload(results=[entry("A", "pass"), entry("B", "pass")])
        assert not compare(before, after).is_blocking

    def test_narrative_drift_blocks_even_when_status_holds(self):
        """The central case: green in both runs, prose quietly rotted."""
        before = payload(results=[entry("A", "pass", narrative_stale=False)], score=100.0)
        after = payload(results=[entry("A", "pass", narrative_stale=True)], score=100.0)
        report = compare(before, after)

        assert not report.regressions
        assert report.score_delta == 0.0
        assert report.narrative_drift == ["A"]
        assert report.is_blocking

    def test_already_stale_narrative_is_not_reported_again(self):
        before = payload(results=[entry("A", "pass", narrative_stale=True)])
        after = payload(results=[entry("A", "pass", narrative_stale=True)])
        assert compare(before, after).narrative_drift == []

    def test_regressions_are_ordered_worst_first(self):
        before = payload(
            results=[entry("LOW", "pass", "low"), entry("CRIT", "pass", "critical")]
        )
        after = payload(
            results=[entry("LOW", "fail", "low"), entry("CRIT", "fail", "critical")]
        )
        report = compare(before, after)
        assert [d.control_id for d in report.regressions] == ["CRIT", "LOW"]

    def test_accepts_a_run_summary_directly(self):
        before = payload(results=[entry("A", "pass")], score=100.0)
        current = RunSummary(
            started_at="2026-08-19T00:00:00Z",
            finished_at="2026-08-19T00:00:01Z",
            target="/tmp",
            results=[CheckResult(control_id="A", status=Status.FAIL, message="broke")],
        )
        assert compare(before, current).regressions


def narrative_control(text: str, attested_hash: str = "") -> Control:
    return Control(
        id="DOC-T",
        title="test",
        description="test",
        check="docs.narrative_current",
        narrative=text,
        narrative_hash=attested_hash,
    )


def run_doc_check(ctl, tmp_path):
    fn = checks.get(ctl.check)
    return fn(ctl, Target(root=tmp_path, posture={}))


class TestNarrativeCurrentCheck:
    def test_matching_fingerprint_passes(self, tmp_path):
        text = "Verified by reading the repository."
        result = run_doc_check(narrative_control(text, fingerprint(text)), tmp_path)
        assert result.status is Status.PASS

    def test_changed_text_fails(self, tmp_path):
        stale = fingerprint("Retention is 30 days.")
        result = run_doc_check(narrative_control("Retention is 90 days.", stale), tmp_path)
        assert result.status is Status.FAIL
        assert "changed since attestation" in result.message

    def test_never_attested_warns_rather_than_fails(self, tmp_path):
        """Written but unreviewed is a different problem from written then changed."""
        result = run_doc_check(narrative_control("Some prose.", ""), tmp_path)
        assert result.status is Status.WARN

    def test_absent_narrative_fails(self, tmp_path):
        result = run_doc_check(narrative_control("", ""), tmp_path)
        assert result.status is Status.FAIL

    def test_reflow_does_not_trigger_drift(self, tmp_path):
        original = "The control is verified by reading the repository."
        attested = fingerprint(original)
        reflowed = "The control is verified\n    by reading the repository."
        result = run_doc_check(narrative_control(reflowed, attested), tmp_path)
        assert result.status is Status.PASS


class TestPagesPresentCheck:
    def _control(self, pages, min_chars=200):
        return Control(
            id="DOC-P",
            title="t",
            description="t",
            check="docs.pages_present",
            params={"pages": pages, "min_chars": min_chars},
        )

    def test_fails_when_a_page_is_missing(self, tmp_path):
        result = run_doc_check(self._control(["docs/index.md"]), tmp_path)
        assert result.status is Status.FAIL

    def test_warns_when_a_page_is_a_stub(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("too short", encoding="utf-8")
        result = run_doc_check(self._control(["docs/index.md"], min_chars=200), tmp_path)
        assert result.status is Status.WARN

    def test_passes_with_substantive_content(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("x" * 250, encoding="utf-8")
        result = run_doc_check(self._control(["docs/index.md"], min_chars=200), tmp_path)
        assert result.status is Status.PASS


class TestEvidenceExplainedCheck:
    def _control(self, narrative):
        return Control(
            id="DOC-E",
            title="t",
            description="t",
            check="docs.evidence_explained",
            narrative=narrative,
        )

    def test_passes_when_provenance_is_stated(self, tmp_path):
        result = run_doc_check(
            self._control("This is observed by reading the repository."), tmp_path
        )
        assert result.status is Status.PASS

    def test_warns_when_provenance_is_absent(self, tmp_path):
        result = run_doc_check(self._control("MFA is on for everyone."), tmp_path)
        assert result.status is Status.WARN

    def test_skips_with_no_narrative(self, tmp_path):
        result = run_doc_check(self._control(""), tmp_path)
        assert result.status is Status.SKIP
