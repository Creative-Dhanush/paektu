# CLI reference

Every command, flag and exit code.

## Exit codes

Shared by all commands, and part of the contract:

| Code | Meaning |
| --- | --- |
| `0` | Everything the command asked about is satisfied |
| `1` | A control failed, or drift was detected |
| `2` | The tool could not run: bad config, missing controls, unreadable YAML |

The split between `1` and `2` is deliberate. A pipeline needs to distinguish "your
compliance posture regressed" from "the compliance tool is broken". Collapsing
both into `1` makes a typo in a control file look like a real finding, and teams
learn to ignore the signal.

## Common flags

Accepted by `check`, `report` and `drift`:

| Flag | Default | Purpose |
| --- | --- | --- |
| `--path PATH` | `.` | Repository root to evaluate |
| `--controls DIR` | `controls` | Directory of control definitions |
| `--framework NAME` | all | Only controls citing this framework |
| `--control ID` | all | Only this control |
| `--tag TAG` | all | Only controls carrying this tag |
| `--min-severity LEVEL` | all | Ignore controls below `low`/`medium`/`high`/`critical` |

Filters combine with AND. If nothing matches, the command exits `2` rather than
reporting a vacuous pass — an empty run that looks like success is worse than an
error.

---

## `plumbline check`

Evaluate controls and print the results.

```bash
plumbline check
plumbline check --framework SOC2 --min-severity high
plumbline check --control SEC-001 --format json
plumbline check --save-evidence --label pre-release
```

| Flag | Default | Purpose |
| --- | --- | --- |
| `--format {table,json}` | `table` | Output shape |
| `--strict` | off | Also exit `1` on warnings and documentation drift |
| `--save-evidence` | off | Record this run in the evidence store |
| `--label TEXT` | none | Label attached to a saved run |

Failures sort to the top. A `(doc)` marker after a message means that control's
narrative has drifted, even where the check itself passed.

**On `--strict`.** Without it, only `FAIL` and `ERROR` block. With it, warnings and
narrative drift block too. Recommended in CI on your default branch; without it a
documentation regression will merge silently.

### Reading the summary

```
21 controls   pass 19   fail 1   warn 1   error 0   skip 0
posture score 90.5%
audit ready: no
```

`posture score` is the share of evaluated controls that passed. Skipped controls
are excluded rather than counted as failures, because a control that does not
apply should not drag the number down.

`audit ready` is stricter than the score: it requires no failures **and** no
narrative drift. A run can score 100% and still not be audit ready, which is the
whole point of tracking prose separately.

---

## `plumbline report`

Produce an audit-facing document.

```bash
plumbline report --out posture.md
plumbline report --format json --out posture.json
plumbline report --frameworks SOC2,ISO27001
```

| Flag | Default | Purpose |
| --- | --- | --- |
| `--format {md,json}` | `md` | Output shape |
| `--out FILE` | stdout | Write here instead of printing |
| `--frameworks LIST` | all known | Comma-separated frameworks for coverage |

The Markdown report contains: totals, findings needing remediation ordered by
severity, a documentation drift section, every control with owner and framework
citations, framework coverage with gaps listed, and an evidence table with content
hashes.

Markdown rather than PDF because Markdown diffs. Seeing what changed between last
quarter's report and this one is worth more than typographic polish. Always exits
`0`; use `check` for a pass/fail signal.

---

## `plumbline drift`

Compare current state against a recorded baseline.

```bash
plumbline drift
plumbline drift --baseline .plumbline/evidence/run-20260819T091402Z-baseline.json
plumbline drift --format json
```

| Flag | Default | Purpose |
| --- | --- | --- |
| `--baseline FILE` | most recent stored run | What to compare against |
| `--format {table,json}` | `table` | Output shape |

Reports four categories:

| Category | Blocks? | Meaning |
| --- | --- | --- |
| Regressions | yes | Passed before, fails now |
| Documentation drift | yes | Prose moved away from its attestation |
| Improvements | no | Failed before, passes now |
| Structural | no | Controls added or removed |

Exits `1` if anything blocking is found. With no stored runs it exits `2` and tells
you to record one first.

Note that documentation drift can be reported with a score delta of `+0.0`. A
control still passing while its narrative rots does not move the score, which is
precisely why drift is tracked as its own category.

---

## `plumbline attest`

Record that you have read a narrative and stand behind it.

```bash
plumbline attest SEC-004
plumbline attest all
```

| Argument | Default | Purpose |
| --- | --- | --- |
| `control_id` | `all` | Control to attest, or `all` for every stale one |
| `--controls DIR` | `controls` | Directory of control definitions |

Writes the current narrative fingerprint into the control's YAML as a targeted
line edit, preserving comments and key order so the diff stays reviewable.

`attest all` covers every narrative currently stale or never attested. Use it
sparingly: attesting twenty narratives in one command is a fair signal that nobody
read them.

Controls with no narrative are skipped with a message rather than silently
ignored.

---

## `plumbline frameworks`

Inspect clause coverage and the crosswalk.

```bash
plumbline frameworks --list
plumbline frameworks SOC2
plumbline frameworks ISO27001 --format json
plumbline frameworks
```

| Argument | Purpose |
| --- | --- |
| `name` | Framework to inspect. Omit for the full crosswalk. |
| `--list` | List catalogued frameworks and clause counts |
| `--format {table,json}` | Output shape |

Names are fuzzy: `soc2`, `SOC 2` and `soc-2` all resolve.

Output separates three things:

- **mapped** — catalogued clauses your controls cite
- **gaps** — catalogued clauses nothing cites
- **uncatalogued clauses cited** — clauses your controls reference that the
  catalogue does not know, which usually means a typo

That last category exists so a mapping error cannot masquerade as coverage.

Coverage counts clauses *addressed*, not clauses *passed*. It is a map of what
this control set talks about, and it is not a compliance claim.

---

## `plumbline verify`

Re-hash stored evidence and detect tampering.

```bash
plumbline verify
plumbline verify --path /some/repo
```

Walks the evidence manifest, recomputes each artifact's hash, and reports any that
no longer match. Exits `1` if any artifact fails.

Catches three problems: a manifest hash disagreeing with its file, file contents
changed after recording, and a manifest entry whose file has gone missing.

---

## `plumbline checks`

List every registered check with its one-line summary. No flags. Useful when
writing a control and you need the exact check name.

---

## CI example

```yaml
name: compliance

on: [push, pull_request]

jobs:
  posture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e .
      - name: Verify evidence integrity
        run: plumbline verify
      - name: Check posture
        run: plumbline check --strict
      - name: Publish report
        if: always()
        run: plumbline report --out posture.md
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: posture-report
          path: posture.md
```

`if: always()` on the report step matters. The run you most want a report from is
the one that just failed.
