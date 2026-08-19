"""Command line interface.

Exit codes are part of the contract, because the main consumer of this tool is
a CI pipeline rather than a person:

    0  everything the command asked about is satisfied
    1  a control failed, or drift was detected
    2  the tool could not run (bad config, missing controls, unreadable YAML)

That split matters. A pipeline needs to distinguish "your compliance posture
regressed" from "the compliance tool is broken", and collapsing both into 1
means a misconfigured run looks like a real finding.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__, checks, engine, frameworks, registry, report
from .evidence import EvidenceStore
from .drift import compare
from .models import Status, fingerprint

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

DEFAULT_CONTROLS_DIR = "controls"


def _terminal_width(default: int = 96) -> int:
    try:
        return max(shutil.get_terminal_size().columns, 60)
    except OSError:
        return default


def _load(args) -> tuple[list, Path]:
    """Load and filter controls, or exit 2 with a clear message."""
    controls_dir = Path(args.controls).resolve()
    try:
        every = registry.load_dir(controls_dir)
    except registry.ControlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)

    if not every:
        print(f"error: no controls found in {controls_dir}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)

    selected = registry.filter_controls(
        every,
        framework=getattr(args, "framework", None),
        control_id=getattr(args, "control", None),
        tag=getattr(args, "tag", None),
        min_severity=getattr(args, "min_severity", None),
    )

    if not selected:
        print("error: no controls matched the given filters", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)

    return selected, controls_dir


def cmd_check(args) -> int:
    controls, _ = _load(args)
    root = Path(args.path).resolve()

    try:
        summary = engine.run(controls, root)
    except engine.EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.format == "json":
        print(report.as_json(summary))
    else:
        print(report.console_table(summary, width=_terminal_width()))

    if args.save_evidence:
        store = EvidenceStore(root)
        stored = store.save(summary, label=args.label or "")
        print(f"\nevidence written to {stored.path} (hash {stored.run_hash})")

    if args.strict:
        return EXIT_FINDINGS if not summary.audit_ready else EXIT_OK
    blocking = any(r.status.blocks_audit for r in summary.results)
    return EXIT_FINDINGS if blocking else EXIT_OK


def cmd_report(args) -> int:
    controls, _ = _load(args)
    root = Path(args.path).resolve()

    try:
        summary = engine.run(controls, root)
    except engine.EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.format == "json":
        body = report.as_json(summary)
    else:
        names = args.frameworks.split(",") if args.frameworks else frameworks.known_frameworks()
        coverages = [frameworks.coverage(controls, name.strip()) for name in names if name.strip()]
        body = report.markdown_report(summary, controls, coverages)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body + "\n", encoding="utf-8")
        print(f"report written to {out_path}")
    else:
        print(body)

    return EXIT_OK


def cmd_drift(args) -> int:
    controls, _ = _load(args)
    root = Path(args.path).resolve()
    store = EvidenceStore(root)

    if args.baseline:
        baseline = EvidenceStore.load(Path(args.baseline))
        if baseline is None:
            print(f"error: cannot read baseline {args.baseline}", file=sys.stderr)
            return EXIT_ERROR
    else:
        baseline = store.latest()
        if baseline is None:
            print(
                "error: no stored runs to compare against.\n"
                "       record one first with: plumbline check --save-evidence",
                file=sys.stderr,
            )
            return EXIT_ERROR

    try:
        summary = engine.run(controls, root)
    except engine.EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    result = compare(baseline, summary)

    if args.format == "json":
        print(report.as_json(result))
    else:
        print(report.drift_console(result))

    return EXIT_FINDINGS if result.is_blocking else EXIT_OK


def cmd_attest(args) -> int:
    """Record the current narrative fingerprint for one or all controls.

    This is the deliberate human act in the workflow. The tool will not attest
    on its own, because the whole point of the fingerprint is that a person
    read the words and stood behind them.
    """
    controls_dir = Path(args.controls).resolve()
    try:
        every = registry.load_dir(controls_dir)
    except registry.ControlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.control_id and args.control_id != "all":
        targets = [c for c in every if c.id == args.control_id]
        if not targets:
            print(f"error: no control with id {args.control_id!r}", file=sys.stderr)
            return EXIT_ERROR
    else:
        targets = [c for c in every if c.narrative_is_stale or c.narrative_is_unattested]
        if not targets:
            print("nothing to attest: every narrative already matches its fingerprint")
            return EXIT_OK

    updated = 0
    for control in targets:
        if not control.narrative.strip():
            print(f"skip {control.id}: no narrative to attest")
            continue

        new_hash = fingerprint(control.narrative)
        if new_hash == control.narrative_hash:
            print(f"skip {control.id}: already attested at {new_hash}")
            continue

        wrote = False
        for path in sorted(controls_dir.rglob("*.y*ml")):
            if registry.write_attestation(path, control.id, new_hash):
                wrote = True
                break

        if wrote:
            old = control.narrative_hash or "unattested"
            print(f"attested {control.id}: {old} -> {new_hash}")
            updated += 1
        else:
            print(f"error: could not locate {control.id} in any control file", file=sys.stderr)

    print(f"\n{updated} control(s) attested")
    return EXIT_OK


def cmd_frameworks(args) -> int:
    controls_dir = Path(args.controls).resolve()
    try:
        every = registry.load_dir(controls_dir)
    except registry.ControlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.list:
        print("frameworks in the catalogue:")
        for name in frameworks.known_frameworks():
            clauses = len(frameworks.CATALOGUE[name])
            print(f"  {name:<12} {clauses} catalogued clauses")
        return EXIT_OK

    if args.name:
        cov = frameworks.coverage(every, args.name)
        if args.format == "json":
            print(
                report.as_json(
                    {
                        "framework": cov.framework,
                        "percent": cov.percent,
                        "mapped": cov.mapped,
                        "unmapped": cov.unmapped,
                        "unknown": cov.unknown,
                    }
                )
            )
        else:
            print(report.coverage_console(cov))
        return EXIT_OK

    table = frameworks.crosswalk(every)
    if args.format == "json":
        print(report.as_json(table))
    else:
        for name, clauses in table.items():
            print(f"{name}")
            for clause, ids in clauses.items():
                print(f"  {clause:<18} {', '.join(ids)}")
            print()
    return EXIT_OK


def cmd_verify(args) -> int:
    """Re-hash the stored evidence history and report tampering."""
    root = Path(args.path).resolve()
    store = EvidenceStore(root)
    history = store.history()

    if not history:
        print("no stored runs to verify")
        return EXIT_OK

    problems = store.verify()
    print(f"verified {len(history)} stored run(s)")

    if not problems:
        print("all evidence artifacts match their recorded hashes")
        return EXIT_OK

    for name, reason in problems:
        print(f"  FAIL {name}: {reason}")
    return EXIT_FINDINGS


def cmd_checks(args) -> int:
    """List every registered check, for people writing new controls."""
    checks.load_builtins()
    print("registered checks:")
    for name in checks.names():
        fn = checks.get(name)
        doc = (fn.__doc__ or "").strip().split("\n")[0] if fn else ""
        print(f"  {name:<28} {doc}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plumbline",
        description=(
            "Security controls as code. Runs checks, collects evidence, and flags "
            "documentation that has drifted away from the system it describes."
        ),
    )
    parser.add_argument("--version", action="version", version=f"plumbline {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p, with_filters: bool = True) -> None:
        p.add_argument("--path", default=".", help="repository root to evaluate (default: .)")
        p.add_argument(
            "--controls",
            default=DEFAULT_CONTROLS_DIR,
            help=f"directory of control definitions (default: {DEFAULT_CONTROLS_DIR})",
        )
        if with_filters:
            p.add_argument("--framework", help="only controls citing this framework")
            p.add_argument("--control", help="only this control id")
            p.add_argument("--tag", help="only controls carrying this tag")
            p.add_argument(
                "--min-severity",
                dest="min_severity",
                choices=["low", "medium", "high", "critical"],
                help="ignore controls below this severity",
            )

    p_check = sub.add_parser("check", help="evaluate controls against a target")
    add_common(p_check)
    p_check.add_argument("--format", choices=["table", "json"], default="table")
    p_check.add_argument(
        "--strict",
        action="store_true",
        help="also exit non-zero on warnings and documentation drift",
    )
    p_check.add_argument(
        "--save-evidence",
        dest="save_evidence",
        action="store_true",
        help="record this run in the evidence store",
    )
    p_check.add_argument("--label", help="label to attach to a saved run")
    p_check.set_defaults(func=cmd_check)

    p_report = sub.add_parser("report", help="produce an audit-facing report")
    add_common(p_report)
    p_report.add_argument("--format", choices=["md", "json"], default="md")
    p_report.add_argument("--out", help="write to this file instead of stdout")
    p_report.add_argument(
        "--frameworks",
        help="comma-separated frameworks to include in coverage (default: all known)",
    )
    p_report.set_defaults(func=cmd_report)

    p_drift = sub.add_parser("drift", help="compare the current state against a baseline run")
    add_common(p_drift)
    p_drift.add_argument("--baseline", help="path to a stored run (default: most recent)")
    p_drift.add_argument("--format", choices=["table", "json"], default="table")
    p_drift.set_defaults(func=cmd_drift)

    p_attest = sub.add_parser(
        "attest", help="record that a narrative has been reviewed and is accurate"
    )
    p_attest.add_argument(
        "control_id", nargs="?", default="all", help="control id, or 'all' for every stale one"
    )
    p_attest.add_argument("--controls", default=DEFAULT_CONTROLS_DIR)
    p_attest.set_defaults(func=cmd_attest)

    p_fw = sub.add_parser("frameworks", help="show framework coverage and crosswalk")
    p_fw.add_argument("name", nargs="?", help="framework to inspect")
    p_fw.add_argument("--controls", default=DEFAULT_CONTROLS_DIR)
    p_fw.add_argument("--list", action="store_true", help="list catalogued frameworks")
    p_fw.add_argument("--format", choices=["table", "json"], default="table")
    p_fw.set_defaults(func=cmd_frameworks)

    p_verify = sub.add_parser("verify", help="re-hash stored evidence and detect tampering")
    p_verify.add_argument("--path", default=".")
    p_verify.set_defaults(func=cmd_verify)

    p_checks = sub.add_parser("checks", help="list available check implementations")
    p_checks.set_defaults(func=cmd_checks)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SystemExit as exc:
        return int(exc.code or 0)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
