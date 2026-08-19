# Check reference

Every check that ships with Plumbline, what it actually proves, and what it does
not.

The last column matters most. A check's limits determine how much weight a pass
deserves, and a narrative that repeats those limits is what makes a report
trustworthy.

## Evidence types

| Type | Meaning | Strength |
| --- | --- | --- |
| `observed` | A machine read your repository | Strongest |
| `attested` | A named person confirmed it on a recorded date | Middle |
| `declared` | Somebody typed a value in a config file | Weakest |

Every result carries its type, so a reader can tell which findings rest on a
machine and which rest on somebody's word.

---

## Repository checks

Read files on disk. They verify what is **committed**, not what a hosting
provider's dashboard claims. That distinction matters during an audit: a branch
protection rule configured in a web UI and never captured in the repo leaves no
evidence trail.

### `repo.file_present`

Asserts that at least one named file exists.

```yaml
check: repo.file_present
params:
  any_of: [LICENSE, LICENSE.md, LICENSE.txt, COPYING]
```

Accepts alternatives because projects disagree about casing and placement.

**Proves:** a file with that name exists.
**Does not prove:** that its contents are correct, current, or non-empty.

### `repo.no_hardcoded_secrets`

Scans committed text files for credential-shaped strings: AWS access keys, PEM
private key blocks, Slack and GitHub tokens, and assignments to variables named
like secrets.

```yaml
check: repo.no_hardcoded_secrets
params:
  allow_paths: [tests/, docs/]
```

Skips vendored and cache directories (`node_modules`, `.venv`, `__pycache__` and
similar) and only reads text-like extensions. Reports path, line number and which
pattern matched.

**Proves:** no string matching a known credential shape is in the working tree.
**Does not prove:** that the repository is clean. It will not find a credential
committed and later removed but still present in git history, and it will not spot
a high-entropy secret matching no known pattern. It is a coarse net for the obvious
mistake, not a replacement for a dedicated scanner.

### `repo.dependencies_pinned`

Requires every dependency line to carry a version operator (`==`, `>=`, `~=`, `@`
and so on).

```yaml
check: repo.dependencies_pinned
params:
  manifests: [requirements.txt, requirements-dev.txt]
```

Ignores comments and flag lines. `SKIP`s cleanly when no manifest exists.

**Proves:** declared dependencies in the listed manifests are constrained.
**Does not prove:** that the constraints are tight, that transitive dependencies
are pinned, or that a lockfile format this check cannot parse is safe.

### `repo.ci_configured`

Looks for a pipeline definition: anything under `.github/workflows/`, or a
`.gitlab-ci.yml`, `Jenkinsfile` or `.circleci/config.yml`.

**Proves:** a pipeline definition exists in the repository.
**Does not prove:** that the pipeline passes, runs on the branches that matter, or
does anything at all. A workflow that only echoes a string satisfies this check.

### `repo.tests_present`

Counts `test_*.py` files under the configured paths.

```yaml
check: repo.tests_present
params:
  paths: [tests]
  min_files: 3
```

Below `min_files` produces a `WARN` rather than a `FAIL`, on the reasoning that a
token single test file is worse than none because it creates a false impression of
coverage.

**Proves:** test files exist.
**Does not prove:** coverage, that the tests pass, or that they assert anything
meaningful.

### `repo.gitignore_excludes`

Confirms `.gitignore` lists the patterns that most often leak credentials.

```yaml
check: repo.gitignore_excludes
params:
  patterns: [".env", "*.pem", "*.key"]
```

Matches entries literally, so `*.pem` and `**/*.pem` are different strings.

**Proves:** the patterns are listed.
**Does not prove:** that nothing matching them was already committed, or that
nobody will `git add --force` past it. Preventive companion to the detective
`repo.no_hardcoded_secrets`; both exist because neither is sufficient.

---

## Posture checks

Read `plumbline.yaml`. These cover facts a repository cannot establish: what the
identity provider enforces, how long logs are kept, when a backup was last
restored.

Every result is labelled `declared` or `attested`. A missing key is always a
`FAIL`, never a `SKIP` — silence is not a control.

### `posture.is_true`

```yaml
check: posture.is_true
params:
  key: identity.mfa_enforced
```

Requires the key to be explicitly `true`. Missing or `false` both fail.

**Proves:** somebody wrote `true`.
**Does not prove:** anything about the world.

### `posture.at_least` / `posture.at_most`

```yaml
check: posture.at_least
params:
  key: logging.retention_days
  minimum: 90
```

```yaml
check: posture.at_most
params:
  key: identity.privileged_session_hours
  maximum: 12
```

Numeric floor and ceiling. A non-numeric value is an `ERROR`, not a `FAIL`, because
that is a defect in the posture file rather than a finding about the system.

### `posture.one_of`

```yaml
check: posture.one_of
params:
  key: data.min_tls_version
  allowed: ["1.2", "1.3"]
```

Restricts a value to an approved set. Compares as declared, so `"1.2"` and `1.2`
are different values — quote version strings in YAML.

### `posture.attested`

The strongest posture check. Rejects a bare `true` and requires a named signer and
a date:

```yaml
identity:
  access_review:
    confirmed: true
    attested_by: security-lead
    attested_on: 2026-08-15
```

Fails with a specific message naming which field is missing.

**Proves:** somebody put their name and a date against the claim.
**Does not prove:** that the review or test was thorough, or that it happened.

Use this for anything where a tickbox is not good enough. An access review with
nobody's name against it is not a review.

---

## Documentation checks

The reason this tool is not a linter. Documentation is treated as a control
surface with its own evidence and failure modes.

### `docs.narrative_current`

Compares the control's narrative against the `narrative_hash` it was last attested
at. Fingerprints are computed over whitespace-normalised text, so reflowing a
paragraph is not drift while changing a word is.

Three outcomes, deliberately distinct:

| State | Status |
| --- | --- |
| No narrative | `FAIL` |
| Narrative, never attested | `WARN` |
| Fingerprint mismatch | `FAIL` |

**Proves:** the words have not changed since a person confirmed them.
**Does not prove:** that the narrative is accurate. A confidently wrong narrative,
attested, passes cleanly.

Full reasoning: [documentation drift](../guides/documentation-drift.md).

### `docs.pages_present`

```yaml
check: docs.pages_present
params:
  min_chars: 400
  pages: [docs/index.md, docs/quickstart.md, docs/troubleshooting.md]
```

Requires each page to exist and carry at least `min_chars` of content. Missing
pages `FAIL`; present-but-thin pages `WARN`.

The character floor exists because an empty `quickstart.md` satisfies a naive
existence check while helping nobody — and a stub is arguably worse than an
absence, since it stops anyone noticing the gap.

**Proves:** the files exist and are not stubs.
**Does not prove:** that the content is correct, current or comprehensible.

### `docs.evidence_explained`

Scans a narrative for words indicating provenance was addressed: *evidence*,
*verified*, *observed*, *declared*, *collected*, *attested*.

```yaml
check: docs.evidence_explained
params:
  markers: [evidence, verified, observed, declared]
```

**Proves:** almost nothing on its own. This is a keyword search and trivially
gamed.
**Value:** a narrative containing none of these words almost certainly never told
the reader whether a human or a machine established the fact. Treat it as a prompt
during review, not an assurance.

---

## Writing your own

See [writing controls](../guides/writing-controls.md). A check is one decorated
function returning a `CheckResult`; nothing else in the codebase needs to change.
