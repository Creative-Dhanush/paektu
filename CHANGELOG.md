# Changelog

All notable changes to Paektu are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

Because this tool checks its own repository, entries here are themselves subject
to `DOC-002`, which requires this file to exist and carry real content.

## [Unreleased]

Nothing yet.

## [0.1.0] — 2026-08-19

First release. Everything below is new, so this entry describes what the tool
does rather than what changed.

### Added

**Narrative drift detection.** Controls carry a `narrative_hash`, a fingerprint of
the prose a person last reviewed. Change the words without re-attesting and the
control is flagged even though its check still passes. Fingerprints are computed
over whitespace-normalised text, so reflowing a paragraph is not drift. Three
states are kept distinct: no narrative (`FAIL`), narrative never attested (`WARN`),
and fingerprint mismatch (`FAIL`).

**Evidence typing.** Every result records how the fact was established:
`observed` (a machine read the repository), `attested` (a named person confirmed it
on a date), or `declared` (somebody typed a value). The distinction is preserved
through checks, reports and stored artifacts.

**Twenty-one controls** across five files, mapped to SOC 2, ISO 27001, HIPAA,
PCI DSS and GDPR clauses:

- `controls/access-control.yaml` — MFA, least privilege, access review, session lifetime
- `controls/data-protection.yaml` — committed secrets, encryption at rest and in transit, log retention, gitignore hygiene
- `controls/sdlc.yaml` — CI, tests, dependency pinning, licence, disclosure route
- `controls/resilience.yaml` — backup restore testing, alerting, incident plan, vendor register
- `controls/documentation.yaml` — narrative currency, documentation surface, evidence provenance

**Fourteen checks** in three families: `repo.*` (observed), `posture.*` (declared
or attested), `docs.*` (observed).

**`posture.attested`**, which rejects a bare `true` and requires `confirmed`,
`attested_by` and `attested_on`. Used by the controls where a tickbox is not good
enough: access reviews, restore tests and incident response plans.

**Append-only evidence store** under `.paektu/evidence/`, with a manifest and
a content hash per run. `paektu verify` re-hashes every artifact and reports
tampering, missing files, and manifest disagreement.

**Drift comparison** across four categories, because each demands a different
response: regressions, improvements, narrative drift, and structural changes.
Regressions and narrative drift block; improvements and added controls do not.

**Framework crosswalk** with coverage reporting that lists gaps rather than hiding
them, and surfaces clauses cited by controls but absent from the catalogue —
usually a typo, which would otherwise masquerade as coverage.

**CLI** with eight subcommands: `check`, `report`, `drift`, `attest`,
`frameworks`, `verify`, `checks`. Exit codes separate findings (`1`) from tool
failure (`2`) so a pipeline can tell a real regression from a broken config.

**Audit-facing Markdown reports** including evidence hashes that reproduce on an
unchanged target. Markdown rather than PDF because Markdown diffs.

**110 tests** covering fingerprint stability, whitespace tolerance, every check's
pass and fail paths, control validation, drift categorisation, evidence tamper
detection, and a suite asserting that every shipped control loads, cites a
framework, names a registered check and carries a narrative.

### Known limitations

Recorded here rather than left for a user to discover.

- `repo.no_hardcoded_secrets` is a regular-expression scan of the working tree. It
  will not find a credential removed from the tree but still in git history, nor a
  high-entropy string matching no known shape.
- Declared controls cannot be verified. Writing `mfa_enforced: true` without
  enforcing MFA produces a pass, labelled `declared`.
- `docs.evidence_explained` is a keyword search and is easy to satisfy without
  meaning it.
- Framework coverage is partial by design and reports gaps openly. Coverage counts
  clauses addressed, not clauses passed.
- The evidence store is gitignored, so CI has no baseline for `drift` unless one is
  committed or cached deliberately.

[Unreleased]: https://github.com/Creative-Dhanush/paektu/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Creative-Dhanush/paektu/releases/tag/v0.1.0
