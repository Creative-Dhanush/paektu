"""Tests for control loading, the evaluation engine, and the evidence store."""

import json

import pytest

from paektu import engine, registry
from paektu.evidence import EvidenceStore
from paektu.frameworks import canonical, coverage, crosswalk
from paektu.models import Control, Status

VALID = """
controls:
  - id: A-001
    title: A control
    description: Does a thing.
    check: posture.is_true
    severity: high
    params:
      key: a.b
    frameworks:
      - framework: SOC2
        clause: CC6.1
        title: Logical access
    narrative: Declared in the posture file.
"""


class TestControlLoading:
    def test_loads_a_valid_file(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(VALID, encoding="utf-8")
        controls = registry.load_file(path)
        assert len(controls) == 1
        assert controls[0].id == "A-001"
        assert controls[0].frameworks[0].framework == "SOC2"

    def test_rejects_a_missing_required_field(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text("controls:\n  - id: X\n    title: t\n", encoding="utf-8")
        with pytest.raises(registry.ControlError, match="missing required"):
            registry.load_file(path)

    def test_rejects_an_unknown_severity(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(
            "controls:\n  - id: X\n    title: t\n    description: d\n"
            "    check: posture.is_true\n    severity: catastrophic\n",
            encoding="utf-8",
        )
        with pytest.raises(registry.ControlError, match="severity"):
            registry.load_file(path)

    def test_rejects_invalid_yaml(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text("controls:\n  - id: [unclosed\n", encoding="utf-8")
        with pytest.raises(registry.ControlError, match="invalid YAML"):
            registry.load_file(path)

    def test_rejects_a_framework_entry_without_a_clause(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(
            "controls:\n  - id: X\n    title: t\n    description: d\n"
            "    check: posture.is_true\n    frameworks:\n      - framework: SOC2\n",
            encoding="utf-8",
        )
        with pytest.raises(registry.ControlError, match="clause"):
            registry.load_file(path)

    def test_rejects_duplicate_ids_across_files(self, tmp_path):
        """Two controls with one id means a report can cite the wrong result."""
        (tmp_path / "one.yaml").write_text(VALID, encoding="utf-8")
        (tmp_path / "two.yaml").write_text(VALID, encoding="utf-8")
        with pytest.raises(registry.ControlError, match="duplicate control id"):
            registry.load_dir(tmp_path)

    def test_accepts_a_bare_list_without_the_controls_key(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(
            "- id: A-001\n  title: t\n  description: d\n  check: posture.is_true\n",
            encoding="utf-8",
        )
        assert len(registry.load_file(path)) == 1

    def test_empty_file_yields_nothing(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text("", encoding="utf-8")
        assert registry.load_file(path) == []


class TestFiltering:
    def _controls(self):
        return [
            Control(id="A", title="a", description="d", check="posture.is_true",
                    severity="low", tags=["x"]),
            Control(id="B", title="b", description="d", check="posture.is_true",
                    severity="critical", tags=["y"]),
        ]

    def test_filters_by_id(self):
        got = registry.filter_controls(self._controls(), control_id="A")
        assert [c.id for c in got] == ["A"]

    def test_filters_by_tag(self):
        got = registry.filter_controls(self._controls(), tag="y")
        assert [c.id for c in got] == ["B"]

    def test_filters_by_minimum_severity(self):
        got = registry.filter_controls(self._controls(), min_severity="high")
        assert [c.id for c in got] == ["B"]


class TestAttestationWriting:
    def test_inserts_a_hash_when_absent(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(VALID, encoding="utf-8")
        assert registry.write_attestation(path, "A-001", "deadbeefdeadbeef")
        assert "narrative_hash: deadbeefdeadbeef" in path.read_text(encoding="utf-8")

    def test_updates_an_existing_hash_in_place(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(VALID + "    narrative_hash: oldhash\n", encoding="utf-8")
        assert registry.write_attestation(path, "A-001", "newhash0newhash0")
        body = path.read_text(encoding="utf-8")
        assert "newhash0newhash0" in body
        assert "oldhash" not in body

    def test_returns_false_for_an_unknown_control(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(VALID, encoding="utf-8")
        assert not registry.write_attestation(path, "NOPE-999", "x")

    def test_written_file_still_parses_as_yaml(self, tmp_path):
        """Regression: the inserted key must align with its siblings.

        A list item `  - id: X` puts sibling keys two columns right of the dash.
        Inserting at the dash's own indent produced YAML that would not load,
        which silently broke every shipped control file.
        """
        import yaml

        path = tmp_path / "c.yaml"
        path.write_text(VALID, encoding="utf-8")
        assert registry.write_attestation(path, "A-001", "abc123abc123abc1")

        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert loaded["controls"][0]["narrative_hash"] == "abc123abc123abc1"
        assert loaded["controls"][0]["title"] == "A control"

    def test_round_trips_through_the_loader(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(VALID, encoding="utf-8")
        registry.write_attestation(path, "A-001", "abc123abc123abc1")

        control = registry.load_file(path)[0]
        assert control.narrative_hash == "abc123abc123abc1"
        assert control.title == "A control"


class TestEngine:
    def test_unknown_check_becomes_an_error_result(self, tmp_path):
        control = Control(id="X", title="t", description="d", check="does.not.exist")
        summary = engine.run([control], tmp_path, posture={})
        assert summary.results[0].status is Status.ERROR
        assert "unknown check" in summary.results[0].message

    def test_a_raising_check_does_not_abort_the_run(self, tmp_path):
        """One broken plugin must not cost the whole pass."""
        from paektu import checks

        @checks.register("test.explodes")
        def explodes(control, target):
            raise RuntimeError("boom")

        controls = [
            Control(id="BAD", title="t", description="d", check="test.explodes"),
            Control(id="GOOD", title="t", description="d", check="posture.is_true",
                    params={"key": "a"}),
        ]
        summary = engine.run(controls, tmp_path, posture={"a": True})

        by_id = {r.control_id: r for r in summary.results}
        assert by_id["BAD"].status is Status.ERROR
        assert "RuntimeError" in by_id["BAD"].message
        assert by_id["GOOD"].status is Status.PASS

    def test_missing_posture_file_is_tolerated(self, tmp_path):
        assert engine.load_posture(tmp_path) == {}

    def test_reads_a_posture_file(self, tmp_path):
        (tmp_path / "paektu.yaml").write_text(
            "posture:\n  a:\n    b: true\n", encoding="utf-8"
        )
        assert engine.load_posture(tmp_path) == {"a": {"b": True}}

    def test_rejects_a_non_directory_target(self, tmp_path):
        target = tmp_path / "afile"
        target.write_text("x", encoding="utf-8")
        with pytest.raises(engine.EngineError):
            engine.run([], target)


class TestEvidenceStore:
    def _summary(self, tmp_path):
        control = Control(id="A", title="t", description="d", check="posture.is_true",
                          params={"key": "k"})
        return engine.run([control], tmp_path, posture={"k": True})

    def test_saves_and_reloads_a_run(self, tmp_path):
        store = EvidenceStore(tmp_path)
        stored = store.save(self._summary(tmp_path))
        assert stored.path.exists()
        assert store.latest() is not None

    def test_history_accumulates(self, tmp_path):
        store = EvidenceStore(tmp_path)
        store.save(self._summary(tmp_path), label="one")
        store.save(self._summary(tmp_path), label="two")
        assert len(store.history()) == 2

    def test_verify_passes_on_untouched_evidence(self, tmp_path):
        store = EvidenceStore(tmp_path)
        store.save(self._summary(tmp_path))
        assert store.verify() == []

    def test_verify_detects_an_edited_artifact(self, tmp_path):
        """An evidence trail that can be silently rewritten is worthless."""
        store = EvidenceStore(tmp_path)
        stored = store.save(self._summary(tmp_path))

        payload = json.loads(stored.path.read_text(encoding="utf-8"))
        assert payload["score"] == 100.0, "fixture assumption: the single control passes"
        payload["score"] = 42.0  # a value it demonstrably did not have
        stored.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        problems = store.verify()
        assert problems
        assert "changed after recording" in problems[0][1]

    def test_empty_store_has_no_latest(self, tmp_path):
        assert EvidenceStore(tmp_path).latest() is None

    def test_saves_a_run_whose_evidence_contains_a_date(self, tmp_path):
        """Regression: YAML turns `attested_on: 2026-08-15` into a date object.

        Every real posture file has one, so a serialisation path without a
        fallback encoder crashed on the first attested control.
        """
        import datetime

        control = Control(
            id="ATT", title="t", description="d", check="posture.attested",
            params={"key": "review"},
        )
        posture = {
            "review": {
                "confirmed": True,
                "attested_by": "security-lead",
                "attested_on": datetime.date(2026, 8, 15),
            }
        }
        summary = engine.run([control], tmp_path, posture=posture)
        assert summary.results[0].status is Status.PASS

        store = EvidenceStore(tmp_path)
        stored = store.save(summary, label="dated")
        assert stored.path.exists()

        # The written artifact must still hash consistently, or verify() is a lie.
        assert store.verify() == []


class TestFrameworks:
    def test_canonicalises_common_spellings(self):
        assert canonical("soc 2") == "SOC2"
        assert canonical("iso27001") == "ISO27001"
        assert canonical("PCI DSS") == "PCIDSS"

    def test_coverage_counts_mapped_clauses(self):
        controls = [
            Control(id="A", title="t", description="d", check="posture.is_true",
                    frameworks=[registry.FrameworkRef("SOC2", "CC6.1")])
        ]
        cov = coverage(controls, "SOC2")
        assert "CC6.1" in cov.mapped
        assert cov.percent > 0

    def test_uncatalogued_clause_is_surfaced_not_hidden(self):
        """A typo in a control file must not masquerade as coverage."""
        controls = [
            Control(id="A", title="t", description="d", check="posture.is_true",
                    frameworks=[registry.FrameworkRef("SOC2", "CC9.9")])
        ]
        cov = coverage(controls, "SOC2")
        assert "CC9.9" in cov.unknown
        assert "CC9.9" not in cov.mapped

    def test_crosswalk_indexes_every_framework(self):
        controls = [
            Control(id="A", title="t", description="d", check="posture.is_true",
                    frameworks=[
                        registry.FrameworkRef("SOC2", "CC6.1"),
                        registry.FrameworkRef("ISO27001", "A.5.17"),
                    ])
        ]
        table = crosswalk(controls)
        assert table["SOC2"]["CC6.1"] == ["A"]
        assert table["ISO27001"]["A.5.17"] == ["A"]


class TestShippedControlSet:
    """The controls that ship with the tool must themselves be valid."""

    def test_repo_controls_load_without_error(self):
        from pathlib import Path

        controls_dir = Path(__file__).resolve().parent.parent / "controls"
        controls = registry.load_dir(controls_dir)
        assert len(controls) >= 20

    def test_every_shipped_control_cites_at_least_one_framework(self):
        from pathlib import Path

        controls_dir = Path(__file__).resolve().parent.parent / "controls"
        for control in registry.load_dir(controls_dir):
            assert control.frameworks, f"{control.id} cites no framework"

    def test_every_shipped_control_names_a_registered_check(self):
        from pathlib import Path

        from paektu import checks

        checks.load_builtins()
        controls_dir = Path(__file__).resolve().parent.parent / "controls"
        for control in registry.load_dir(controls_dir):
            assert checks.get(control.check), f"{control.id} names unknown check {control.check}"

    def test_every_shipped_control_has_a_narrative(self):
        from pathlib import Path

        controls_dir = Path(__file__).resolve().parent.parent / "controls"
        for control in registry.load_dir(controls_dir):
            assert control.narrative.strip(), f"{control.id} has no narrative"
