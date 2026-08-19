"""Tests for the shipped checks, run against synthetic repositories."""

import pytest

from plumbline import checks
from plumbline.checks import Target
from plumbline.models import Control, Status

checks.load_builtins()


@pytest.fixture
def repo(tmp_path):
    """An empty directory standing in for a repository."""
    return tmp_path


def control(check: str, **params) -> Control:
    return Control(
        id="T-001",
        title="test",
        description="test",
        check=check,
        params=params,
    )


def run(ctl: Control, root, posture: dict | None = None):
    fn = checks.get(ctl.check)
    assert fn is not None, f"check {ctl.check} is not registered"
    return fn(ctl, Target(root=root, posture=posture or {}))


class TestFilePresent:
    def test_passes_when_a_candidate_exists(self, repo):
        (repo / "LICENSE").write_text("Apache", encoding="utf-8")
        result = run(control("repo.file_present", any_of=["LICENSE", "LICENSE.md"]), repo)
        assert result.status is Status.PASS

    def test_accepts_any_alternative_spelling(self, repo):
        (repo / "LICENSE.md").write_text("MIT", encoding="utf-8")
        result = run(control("repo.file_present", any_of=["LICENSE", "LICENSE.md"]), repo)
        assert result.status is Status.PASS

    def test_fails_when_none_exist(self, repo):
        result = run(control("repo.file_present", any_of=["LICENSE"]), repo)
        assert result.status is Status.FAIL
        assert result.remediation

    def test_errors_when_control_declares_no_paths(self, repo):
        assert run(control("repo.file_present"), repo).status is Status.ERROR


class TestSecretScanner:
    def test_clean_repo_passes(self, repo):
        (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
        assert run(control("repo.no_hardcoded_secrets"), repo).status is Status.PASS

    def test_detects_an_aws_key(self, repo):
        (repo / "config.py").write_text(
            'KEY = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8"
        )
        result = run(control("repo.no_hardcoded_secrets"), repo)
        assert result.status is Status.FAIL
        assert "aws_access_key" in str(result.evidence[0].detail)

    def test_detects_a_private_key_block(self, repo):
        (repo / "id.pem.py").write_text(
            "-----BEGIN RSA PRIVATE KEY-----\nabc\n", encoding="utf-8"
        )
        assert run(control("repo.no_hardcoded_secrets"), repo).status is Status.FAIL

    def test_honours_the_allow_list(self, repo):
        """Fixtures under tests/ legitimately contain example credentials."""
        nested = repo / "tests"
        nested.mkdir()
        (nested / "fixture.py").write_text('K = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")
        result = run(control("repo.no_hardcoded_secrets", allow_paths=["tests/"]), repo)
        assert result.status is Status.PASS

    def test_ignores_vendored_directories(self, repo):
        vendored = repo / "node_modules"
        vendored.mkdir()
        (vendored / "leak.js").write_text('k="AKIAIOSFODNN7EXAMPLE"', encoding="utf-8")
        assert run(control("repo.no_hardcoded_secrets"), repo).status is Status.PASS

    def test_reports_the_line_number(self, repo):
        (repo / "c.py").write_text(
            'a = 1\nb = 2\nKEY = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8"
        )
        result = run(control("repo.no_hardcoded_secrets"), repo)
        assert result.evidence[0].detail["hits"][0]["line"] == 3


class TestDependencyPinning:
    def test_passes_when_everything_is_pinned(self, repo):
        (repo / "requirements.txt").write_text("PyYAML==6.0.1\nrequests>=2.31\n", encoding="utf-8")
        assert run(control("repo.dependencies_pinned"), repo).status is Status.PASS

    def test_fails_on_a_bare_package_name(self, repo):
        (repo / "requirements.txt").write_text("PyYAML==6.0.1\nrequests\n", encoding="utf-8")
        result = run(control("repo.dependencies_pinned"), repo)
        assert result.status is Status.FAIL
        assert "requests" in str(result.evidence[0].detail["unpinned"])

    def test_ignores_comments_and_flags(self, repo):
        (repo / "requirements.txt").write_text(
            "# a comment\n-r other.txt\nPyYAML==6.0.1\n", encoding="utf-8"
        )
        assert run(control("repo.dependencies_pinned"), repo).status is Status.PASS

    def test_skips_when_no_manifest_exists(self, repo):
        """No manifest is not the same as an unpinned manifest."""
        assert run(control("repo.dependencies_pinned"), repo).status is Status.SKIP


class TestGitignore:
    def test_passes_when_all_patterns_present(self, repo):
        (repo / ".gitignore").write_text(".env\n*.pem\n", encoding="utf-8")
        result = run(control("repo.gitignore_excludes", patterns=[".env", "*.pem"]), repo)
        assert result.status is Status.PASS

    def test_fails_on_a_missing_pattern(self, repo):
        (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
        result = run(control("repo.gitignore_excludes", patterns=[".env", "*.pem"]), repo)
        assert result.status is Status.FAIL

    def test_fails_when_the_file_is_absent(self, repo):
        assert run(control("repo.gitignore_excludes", patterns=[".env"]), repo).status is Status.FAIL


class TestTestsPresent:
    def test_warns_when_the_suite_is_thin(self, repo):
        suite = repo / "tests"
        suite.mkdir()
        (suite / "test_one.py").write_text("", encoding="utf-8")
        result = run(control("repo.tests_present", paths=["tests"], min_files=3), repo)
        assert result.status is Status.WARN

    def test_passes_at_the_threshold(self, repo):
        suite = repo / "tests"
        suite.mkdir()
        for name in ("a", "b", "c"):
            (suite / f"test_{name}.py").write_text("", encoding="utf-8")
        result = run(control("repo.tests_present", paths=["tests"], min_files=3), repo)
        assert result.status is Status.PASS

    def test_fails_with_no_tests_at_all(self, repo):
        assert run(control("repo.tests_present", paths=["tests"]), repo).status is Status.FAIL


class TestPostureChecks:
    def test_is_true_passes_on_true(self, repo):
        result = run(control("posture.is_true", key="a.b"), repo, {"a": {"b": True}})
        assert result.status is Status.PASS

    def test_missing_key_fails_rather_than_skips(self, repo):
        """Silence is not a control."""
        result = run(control("posture.is_true", key="a.b"), repo, {})
        assert result.status is Status.FAIL
        assert "not declared" in result.message

    def test_false_fails(self, repo):
        result = run(control("posture.is_true", key="a.b"), repo, {"a": {"b": False}})
        assert result.status is Status.FAIL

    def test_results_are_labelled_as_declared(self, repo):
        result = run(control("posture.is_true", key="a.b"), repo, {"a": {"b": True}})
        assert result.evidence[0].detail["evidence_type"] == "declared"

    def test_at_least_respects_the_floor(self, repo):
        ctl = control("posture.at_least", key="r.days", minimum=90)
        assert run(ctl, repo, {"r": {"days": 180}}).status is Status.PASS
        assert run(ctl, repo, {"r": {"days": 90}}).status is Status.PASS
        assert run(ctl, repo, {"r": {"days": 30}}).status is Status.FAIL

    def test_at_least_errors_on_non_numeric(self, repo):
        ctl = control("posture.at_least", key="r.days", minimum=90)
        assert run(ctl, repo, {"r": {"days": "lots"}}).status is Status.ERROR

    def test_at_most_respects_the_ceiling(self, repo):
        ctl = control("posture.at_most", key="s.hours", maximum=12)
        assert run(ctl, repo, {"s": {"hours": 8}}).status is Status.PASS
        assert run(ctl, repo, {"s": {"hours": 24}}).status is Status.FAIL

    def test_one_of_enforces_the_allowed_set(self, repo):
        ctl = control("posture.one_of", key="t.v", allowed=["1.2", "1.3"])
        assert run(ctl, repo, {"t": {"v": "1.3"}}).status is Status.PASS
        assert run(ctl, repo, {"t": {"v": "1.1"}}).status is Status.FAIL


class TestAttestation:
    def test_complete_attestation_passes(self, repo):
        posture = {
            "x": {"confirmed": True, "attested_by": "lead", "attested_on": "2026-08-01"}
        }
        result = run(control("posture.attested", key="x"), repo, posture)
        assert result.status is Status.PASS

    def test_bare_true_is_rejected(self, repo):
        """The whole point: a tickbox is not an attestation."""
        result = run(control("posture.attested", key="x"), repo, {"x": True})
        assert result.status is Status.FAIL

    def test_missing_signer_fails(self, repo):
        posture = {"x": {"confirmed": True, "attested_on": "2026-08-01"}}
        result = run(control("posture.attested", key="x"), repo, posture)
        assert result.status is Status.FAIL
        assert "attested_by" in result.message

    def test_missing_date_fails(self, repo):
        posture = {"x": {"confirmed": True, "attested_by": "lead"}}
        result = run(control("posture.attested", key="x"), repo, posture)
        assert result.status is Status.FAIL
        assert "attested_on" in result.message
