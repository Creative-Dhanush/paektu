# Paektu — Complete Documentation

Security controls as code, with documentation drift detection.

Version 0.1.0 · Apache-2.0 · <https://github.com/Creative-Dhanush/paektu>

This file is a single-document build of everything under `docs/`, generated for
offline reading and distribution. The canonical sources are the individual pages
it is assembled from; when they disagree, the individual pages win.

## Contents

1. [Overview](#overview)
2. [Quickstart](#quickstart)
3. [Guide: Documentation drift](#guide-documentation-drift)
4. [Guide: Writing controls](#guide-writing-controls)
5. [Reference: CLI](#reference-cli)
6. [Reference: Checks](#reference-checks)
7. [Troubleshooting](#troubleshooting)


---

# Overview

*Source: [`docs/index.md`](https://github.com/Creative-Dhanush/paektu/blob/main/docs/index.md)*

## Paektu

Security controls as code, with evidence collection and documentation drift
detection.

Paektu is the highest peak on the Korean peninsula: the fixed landmark you take
your bearings from when everything else on the horizon has moved. That is the job
here. State what your controls require, check them mechanically, and keep the
written record honest about how each fact was established.

### Why this exists

Compliance tooling generally models two things: the **control** and the
**evidence**. It leaves out the third thing an auditor actually reads, which is
the **narrative** — the prose explaining what a control does and why it is
adequate.

Narratives rot. The system changes, the automated check keeps passing, and the
paragraph describing it slowly stops being true. Nothing notices, because nothing
is watching the prose. The dashboard is green while the document a human relies
on has quietly become fiction.

Paektu treats the narrative as a control surface with its own evidence and its
own failure modes. Each control records the fingerprint of the narrative text a
person last reviewed. Change the words without re-attesting and the control is
flagged, even though the underlying check still passes:

```
FAIL   DOC-001   high   narrative changed since attestation (a1b2c3d4 -> e5f6a7b8)
```

That single behaviour is the reason the tool exists. Everything else is
scaffolding to make it useful.

### The trust model

The most important idea in Paektu is that not all evidence is equal, and the
tool refuses to pretend otherwise. Every result is labelled with how the fact was
established:

| Type | Meaning | Strength |
| --- | --- | --- |
| `observed` | A machine read your repository and saw this | Strongest |
| `attested` | A named person confirmed it on a recorded date | Middle |
| `declared` | Somebody typed `true` in a config file | Weakest |

**Observed** controls read files: committed secrets, unpinned dependencies, a
missing licence, absent CI, documentation pages that do not exist.

**Declared** controls read `paektu.yaml`, which holds the facts a repository
cannot prove — whether MFA is enforced at the identity provider, how long logs
are retained.

**Attested** controls demand more than a boolean. The higher-risk ones use the
`posture.attested` check, which rejects a bare `true` and requires a name and a
date:

```yaml
access_review:
  confirmed: true
  attested_by: security-lead
  attested_on: 2026-08-15
```

An access review with nobody's name against it is not a review. This is how the
tool stops its most important controls from passing on a tickbox.

### Where to go next

| If you want to | Read |
| --- | --- |
| Run it for the first time | [Quickstart](quickstart.md) |
| Understand every command | [CLI reference](reference/cli.md) |
| Write your own control | [Writing controls](guides/writing-controls.md) |
| Understand narrative drift | [Documentation drift](guides/documentation-drift.md) |
| See what checks exist | [Check reference](reference/checks.md) |
| Fix something that broke | [Troubleshooting](troubleshooting.md) |

### What it does not do

Stated plainly, because compliance tooling has a reputation for implying more
than it delivers.

- **It does not make you compliant.** It checks what it says it checks. A green
  run is not an audit opinion and this document is not one either.
- **It cannot verify a declaration.** Write `mfa_enforced: true` without
  enforcing MFA and the tool reports a pass. It will label that pass `declared`,
  which is the entire point of the labelling, but it cannot go and look.
- **The secret scanner is a coarse net.** Regular expressions over the working
  tree. It will not find a credential removed from the tree but still in git
  history, and it will not spot a high-entropy string matching no known shape.
- **Framework coverage is partial.** Coverage counts clauses the control set
  speaks to, not clauses passed, and gaps are listed rather than hidden.


---

# Quickstart

*Source: [`docs/quickstart.md`](https://github.com/Creative-Dhanush/paektu/blob/main/docs/quickstart.md)*

## Quickstart

Getting from nothing to a first report, and then to the one behaviour that makes
this tool different from a linter.

### Requirements

Python 3.10 or newer. The only runtime dependency is PyYAML.

### Install

```bash
git clone https://github.com/Creative-Dhanush/paektu
cd paektu
pip install -e .
```

Confirm it landed:

```bash
paektu --version
```

If `paektu` is not on your PATH, `python -m paektu` works identically and
is the safer form inside CI.

### 1. Run your first check

From the repository root:

```bash
paektu check
```

```
STATUS CONTROL     SEV       MESSAGE
--------------------------------------------------------------------------
FAIL   SDLC-001    high      no CI pipeline definition found
WARN   DOC-001     high      narrative exists but has never been attested
PASS   AC-001      critical  identity.mfa_enforced is declared true
PASS   SEC-004     high      logging.retention_days is 180 (minimum 90)
--------------------------------------------------------------------------
21 controls   pass 19   fail 1   warn 1   error 0   skip 0
posture score 90.5%
audit ready: no
```

Failures sort to the top, because that is what you came to see.

Note that `audit ready` can be `no` while the score is high. The score counts
controls that passed; audit readiness additionally requires that no narrative has
drifted. A control can be technically satisfied and still not be presentable.

### 2. Narrow the run

```bash
paektu check --framework SOC2         # only controls citing SOC 2
paektu check --min-severity high      # skip the low-stakes ones
paektu check --control SEC-001        # one control
paektu check --tag observed           # only machine-verified controls
```

The last one is worth knowing. Controls tagged `observed` are the ones a machine
actually verified, as opposed to those resting on a declaration in
`paektu.yaml`. When someone asks what you can genuinely prove, that is the
filter to reach for.

### 3. Record a baseline

Drift detection needs something to compare against:

```bash
paektu check --save-evidence --label baseline
```

This writes a timestamped JSON artifact under `.paektu/evidence/` and adds it
to a manifest. Runs are append-only: nothing here rewrites or deletes a previous
one, because a compliance tool that can quietly revise its own history is not
worth much as a source of truth.

### 4. Watch documentation drift get caught

Here is the part that matters. Open any control file in `controls/` and change a
word in a `narrative:` block. For example, in `controls/data-protection.yaml`,
change SEC-004's narrative from `ninety day floor` to `thirty day floor`.

Now re-run:

```bash
paektu check --control SEC-004
```

```
FAIL   SEC-004   high   narrative changed since attestation (3f9a2b1c -> 7d1e4f92)
```

The underlying check still passes. Log retention is still 180 days. But the prose
describing it no longer matches what a human reviewed and signed off on, so the
control is flagged.

Reflowing text does not trigger this. Fingerprints are computed over
whitespace-normalised text, so rewrapping a paragraph is not drift. Changing a
number is.

To resolve it, read the new wording, decide whether you stand behind it, and
attest:

```bash
paektu attest SEC-004
```

```
attested SEC-004: 3f9a2b1c8d7e6f50 -> 7d1e4f92a6b3c8d1
```

The tool will never attest on your behalf. The fingerprint means "a person read
these words", and a tool signing that for you would make the whole mechanism
worthless.

### 5. Compare against the baseline

```bash
paektu drift
```

```
baseline 2026-08-19T09:14:02Z  ->  current 2026-08-19T11:40:55Z
score 90.5% -> 90.5% (+0.0)

DOCUMENTATION DRIFT (1)
  SEC-004 narrative changed since attestation

blocking: yes
```

Note the score did not move. A pure documentation regression is invisible to a
posture score, which is exactly why it needs its own category.

### 6. Produce an audit-facing report

```bash
paektu report --out posture.md
```

Markdown rather than PDF, because Markdown diffs. Being able to see what changed
between last quarter's report and this one is worth more than typographic polish.

The report includes evidence hashes. Re-running `check` on an unchanged target
reproduces them, which is how a reviewer confirms the artifact they were handed
is the one the tool actually produced.

### 7. Wire it into CI

```yaml
- name: Compliance posture
  run: paektu check --strict
```

Exit codes are the contract:

| Code | Meaning |
| --- | --- |
| 0 | satisfied |
| 1 | a control failed, or drift was detected |
| 2 | the tool could not run |

`--strict` also fails the build on warnings and documentation drift. Without it,
only hard failures block.

The distinction between 1 and 2 is deliberate. A pipeline needs to tell "your
posture regressed" apart from "the compliance tool is broken", and collapsing
both into 1 makes a typo in a control file look like a real finding.

### Next

- [Writing controls](guides/writing-controls.md) to add your own
- [Documentation drift](guides/documentation-drift.md) for the reasoning behind
  the fingerprint mechanism
- [CLI reference](reference/cli.md) for every flag


---

# Guide: Documentation drift

*Source: [`docs/guides/documentation-drift.md`](https://github.com/Creative-Dhanush/paektu/blob/main/docs/guides/documentation-drift.md)*

## Documentation drift

The reasoning behind the one mechanism that makes Paektu different from a
compliance linter.

### The failure this addresses

A compliance programme has three artifacts per control:

1. **The control definition** — what is required
2. **The evidence** — what a machine observed
3. **The narrative** — the prose a human wrote explaining it

Automation covers the first two well. Nothing watches the third.

So this happens. In January someone writes: *"Audit logs are retained for 90 days
in line with PCI DSS 10.5."* True at the time. In April the platform team raises
retention to 180 days and updates the config. The automated check still passes,
because 180 is more than the 90-day floor. Nobody edits the narrative.

In October an auditor reads a paragraph asserting 90 days for a system that keeps
180. The check was green the whole time. The tooling reported success while the
document a human relied on became wrong.

That is the benign direction. The dangerous one is the reverse: retention drops to
30 days, the narrative still claims 90, and the check fails — but the narrative
is now actively misleading anyone reading it while the failure sits in a backlog.

### How it works

Each control carries a `narrative_hash`, a fingerprint of the narrative text a
person last reviewed:

```yaml
- id: SEC-004
  title: Audit logs are retained long enough to investigate an incident
  check: posture.at_least
  params:
    key: logging.retention_days
    minimum: 90
  narrative: >
    Retention is declared in paektu.yaml and compared against a ninety day
    floor, chosen because PCI DSS requires three months of immediately available
    logs.
  narrative_hash: 3f9a2b1c8d7e6f50
```

On every run the narrative is re-hashed and compared. Mismatch means somebody
changed the words since the last review, and the control is flagged regardless of
whether its check passed.

#### Whitespace does not count

Fingerprints are computed over whitespace-normalised text, so this is not drift:

```
Retention is declared in paektu.yaml
    and compared against a ninety day floor.
```

while this is:

```
Retention is declared in paektu.yaml and compared against a thirty day floor.
```

Reformatting is not a documentation change. Changing a number is. A drift
detector that fires when someone rewraps a paragraph gets muted within a week,
and a muted detector is worse than none.

#### Three outcomes, kept separate

The `docs.narrative_current` check distinguishes three states rather than
collapsing them:

| State | Status | Meaning |
| --- | --- | --- |
| No narrative at all | `FAIL` | Never written |
| Narrative, no fingerprint | `WARN` | Written, never reviewed |
| Fingerprint mismatch | `FAIL` | Reviewed, then changed |

The middle case is a warning rather than a failure because a narrative awaiting
first review is a normal state during authoring. The third is a failure because
prose that drifted after sign-off is a defect, and it is the one an auditor will
find.

### Attestation is a human act

Resolving drift is one command:

```bash
paektu attest SEC-004
```

```
attested SEC-004: 3f9a2b1c8d7e6f50 -> 7d1e4f92a6b3c8d1
```

The tool will never do this on its own. Not as a safety limitation but because
the fingerprint's entire meaning is *"a person read these words and stands behind
them"*. A tool that could attest for you would be recording a fact about itself,
not about anyone's judgement, and the mechanism would be theatre.

For the same reason `paektu attest` writes a targeted line edit into the YAML
rather than re-serialising the file. Round-tripping through a YAML dumper would
reflow comments and reorder keys, producing a diff nobody can review — and an
unreviewable diff in the middle of an attestation workflow defeats the purpose.

To attest everything currently stale or unreviewed:

```bash
paektu attest all
```

Use that sparingly. Attesting twenty narratives in one command is a fair signal
that nobody read them.

### Drift is not a score regression

This is the subtle part, and it drove the design of `paektu drift`.

A documentation regression does not move the posture score. The control still
passes. If you only track the score you will never see it:

```
baseline 2026-08-19T09:14:02Z  ->  current 2026-08-19T11:40:55Z
score 90.5% -> 90.5% (+0.0)

DOCUMENTATION DRIFT (1)
  SEC-004 narrative changed since attestation

blocking: yes
```

Score unchanged. Still blocking. Narrative drift is reported as its own category
alongside regressions, improvements and structural changes, because each demands
a different response:

| Category | What it means | What to do |
| --- | --- | --- |
| Regression | Passed before, fails now | Fix the system |
| Improvement | Failed before, passes now | Update the narrative to match |
| Narrative drift | Prose moved away from its attestation | Re-review the words |
| Structural | Controls added or removed | Review the scope change |

Improvements deserve a note. When a control starts passing, its narrative is
usually now wrong in the other direction — it describes a gap that no longer
exists. That is why improvements are surfaced rather than silently celebrated.

Regressions and narrative drift block a pipeline. Improvements and added controls
never do.

### Honest limits

Worth stating, because a drift detector that oversells itself is the kind of tool
people learn to ignore.

- **It cannot tell whether a narrative is accurate.** It only knows whether a
  person confirmed it since it last changed. A confidently wrong narrative,
  attested, passes cleanly.
- **It cannot detect drift in prose it does not hold.** If your real
  documentation lives in a wiki and the control narrative is a summary, the
  fingerprint tracks the summary. The wiki can rot untouched.
- **Attestation is only as good as the review.** `paektu attest all` after
  skimming is indistinguishable, to the tool, from a careful reading.
- **`docs.evidence_explained` is a keyword search.** It looks for words like
  *observed*, *declared* and *verified*. Easy to satisfy without meaning it. Its
  value is as a prompt during review, not as an assurance.

What it does buy you is that the failure mode changes shape. Instead of prose
rotting invisibly for nine months, a diff to a narrative surfaces in the next CI
run and lands in front of whoever owns the control.


---

# Guide: Writing controls

*Source: [`docs/guides/writing-controls.md`](https://github.com/Creative-Dhanush/paektu/blob/main/docs/guides/writing-controls.md)*

## Writing controls

Adding a control means writing YAML. Adding a *check* means writing one Python
function. Most of the time you only need the first.

### Anatomy of a control

```yaml
- id: SEC-004
  title: Audit logs are retained long enough to investigate an incident
  description: >
    Security-relevant logs are kept for at least ninety days so that an incident
    discovered late can still be reconstructed.
  check: posture.at_least
  severity: high
  owner: platform-team
  tags: [logging, data]
  params:
    key: logging.retention_days
    minimum: 90
  frameworks:
    - framework: PCIDSS
      clause: "10.5"
      title: Audit log retention
  narrative: >
    Retention is declared in paektu.yaml and compared against a ninety day
    floor. Ninety days is chosen because PCI DSS requires three months of
    immediately available logs. This control checks the declared figure and
    cannot confirm logs are actually present for that whole window.
  narrative_hash: 3f9a2b1c8d7e6f50
```

| Field | Required | Purpose |
| --- | --- | --- |
| `id` | yes | Stable identifier. Must be unique across every file. |
| `title` | yes | One line, readable by a non-engineer. |
| `description` | yes | What the control requires. |
| `check` | yes | Name of a registered check. |
| `severity` | no | `low`, `medium`, `high`, `critical`. Defaults to `medium`. |
| `owner` | no | Who answers for it. Appears in reports. |
| `tags` | no | Free-form. Filter with `--tag`. |
| `params` | no | Passed to the check. Shape depends on the check. |
| `frameworks` | no | Clause citations. Drives coverage reporting. |
| `narrative` | no | Prose for the auditor. Fingerprinted. |
| `narrative_hash` | no | Written by `paektu attest`, not by hand. |

Files live in `controls/` and are grouped by theme. Grouping is cosmetic; the
loader reads every `.yaml` and `.yml` in the directory tree.

Duplicate ids are a fatal error rather than a warning. Two controls answering to
one name means a report can cite a passing result while a failing one exists.

### Choosing a check

Run `paektu checks` for the live list. Three families ship:

#### Repository checks — observed

These read files. Strongest evidence available, because a machine looked.

| Check | Params | Asks |
| --- | --- | --- |
| `repo.file_present` | `any_of` | Does one of these files exist? |
| `repo.no_hardcoded_secrets` | `allow_paths` | Any credential-shaped strings? |
| `repo.dependencies_pinned` | `manifests` | Every requirement version-constrained? |
| `repo.ci_configured` | — | Is there a pipeline definition? |
| `repo.tests_present` | `paths`, `min_files` | Does a test suite exist? |
| `repo.gitignore_excludes` | `patterns` | Are secret patterns ignored? |

#### Posture checks — declared

These read `paektu.yaml` for facts a repository cannot prove.

| Check | Params | Asks |
| --- | --- | --- |
| `posture.is_true` | `key` | Is this explicitly true? |
| `posture.at_least` | `key`, `minimum` | Does it meet a floor? |
| `posture.at_most` | `key`, `maximum` | Does it stay under a ceiling? |
| `posture.one_of` | `key`, `allowed` | Is it in an approved set? |
| `posture.attested` | `key` | Named signer and date recorded? |

A missing key is a `FAIL`, never a `SKIP`. Silence is not a control.

Use `posture.attested` for anything where a tickbox is not good enough. Access
reviews, restore tests and incident plans all use it, because each is a claim that
means nothing without somebody's name against it.

#### Documentation checks — observed

| Check | Params | Asks |
| --- | --- | --- |
| `docs.narrative_current` | — | Does the prose match its attestation? |
| `docs.pages_present` | `pages`, `min_chars` | Do the docs cover a minimum surface? |
| `docs.evidence_explained` | `markers` | Does the narrative state its provenance? |

### Writing a narrative that earns its place

The narrative is what an auditor reads. Three things make it useful:

**Say whether the fact was observed or declared.** This is the single most
valuable sentence you can write. "Observed by reading .gitignore" and "declared in
paektu.yaml" tell a reader precisely how much weight to give the pass.

**State the limits.** Every check has them. A narrative admitting that a
regex-based secret scanner misses git history is more trustworthy than one
implying comprehensive coverage — and a reader who finds an unstated limit
themselves stops believing the rest of the document.

**Explain the numbers.** Ninety days and twelve hours are policy choices, not
natural constants. Say where they came from, and say when no framework prescribes
them.

The `docs.evidence_explained` check nudges toward the first of these by looking
for words like *observed*, *declared* and *verified*. It is a keyword search and
easy to game; treat it as a prompt during review, not a guarantee.

### Adding a new check

A check is one function. It receives the control and a `Target`, and returns a
`CheckResult`.

```python
from ..models import Evidence, Status
from . import Target, register, result


@register("repo.readme_mentions_security")
def readme_mentions_security(control, target: Target):
    """One-line summary. Shown by `paektu checks`."""
    body = target.read("README.md")
    if not body:
        return result(control, Status.SKIP, "no README.md to inspect")

    needle = control.params.get("phrase", "security")
    if needle.lower() in body.lower():
        return result(
            control,
            Status.PASS,
            f"README mentions {needle!r}",
            evidence=[
                Evidence(
                    control_id=control.id,
                    collector="repo.readme_mentions_security",
                    summary=f"found {needle!r}",
                    detail={"phrase": needle, "chars": len(body)},
                )
            ],
        )

    return result(
        control,
        Status.FAIL,
        f"README never mentions {needle!r}",
        remediation="add a security section pointing at SECURITY.md",
    )
```

Put it in `paektu/checks/repo.py`, `posture.py` or `docs.py`. The decorator
registers it; `load_builtins()` imports those three modules, so nothing else needs
to change.

#### The `Target` API

```python
target.root                       # Path to the repository root
target.path("docs", "index.md")   # Build a path beneath root
target.exists("LICENSE", "LICENSE.md")  # First candidate that exists, or None
target.read("README.md")          # Text, or "" if unreadable
target.posture_get("a.b.c", default=None)  # Nested posture lookup
```

Checks are confined to a repository path and a posture document. No network, no
cloud SDKs. That keeps runs reproducible and means the tool can be pointed at any
checkout without credentials — which is also why declared controls exist at all.

#### Rules worth following

**Return, do not raise.** The engine catches exceptions and converts them to
`ERROR` results so one broken check cannot cost the whole run, but a returned
status carries a better message than a caught traceback.

**Use `SKIP` for "not applicable", `FAIL` for "not satisfied".** A missing
dependency manifest is a skip. A manifest full of unpinned packages is a failure.
Conflating them makes the score meaningless.

**Use `WARN` when present-but-inadequate.** One test file in a repository is a
warning, not a pass and not a failure. Warnings do not block unless `--strict`.

**Attach evidence with a `detail` payload.** The payload is hashed, and that hash
lands in the audit report. Evidence a reviewer cannot reproduce is decoration.

**Populate `remediation` on every failure.** A finding without a next action just
becomes a permanent backlog item.

### Verifying your work

```bash
paektu checks                     # is it registered?
paektu check --control YOUR-ID    # does it behave?
paektu check --control YOUR-ID --format json
python -m pytest
```

The shipped test suite asserts that every control in `controls/` loads, cites at
least one framework, names a registered check, and carries a narrative. A control
that fails those is caught in CI rather than in a report.


---

# Reference: CLI

*Source: [`docs/reference/cli.md`](https://github.com/Creative-Dhanush/paektu/blob/main/docs/reference/cli.md)*

## CLI reference

Every command, flag and exit code.

### Exit codes

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

### Common flags

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

### `paektu check`

Evaluate controls and print the results.

```bash
paektu check
paektu check --framework SOC2 --min-severity high
paektu check --control SEC-001 --format json
paektu check --save-evidence --label pre-release
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

#### Reading the summary

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

### `paektu report`

Produce an audit-facing document.

```bash
paektu report --out posture.md
paektu report --format json --out posture.json
paektu report --frameworks SOC2,ISO27001
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

### `paektu drift`

Compare current state against a recorded baseline.

```bash
paektu drift
paektu drift --baseline .paektu/evidence/run-20260819T091402Z-baseline.json
paektu drift --format json
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

### `paektu attest`

Record that you have read a narrative and stand behind it.

```bash
paektu attest SEC-004
paektu attest all
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

### `paektu frameworks`

Inspect clause coverage and the crosswalk.

```bash
paektu frameworks --list
paektu frameworks SOC2
paektu frameworks ISO27001 --format json
paektu frameworks
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

### `paektu verify`

Re-hash stored evidence and detect tampering.

```bash
paektu verify
paektu verify --path /some/repo
```

Walks the evidence manifest, recomputes each artifact's hash, and reports any that
no longer match. Exits `1` if any artifact fails.

Catches three problems: a manifest hash disagreeing with its file, file contents
changed after recording, and a manifest entry whose file has gone missing.

---

### `paektu checks`

List every registered check with its one-line summary. No flags. Useful when
writing a control and you need the exact check name.

---

### CI example

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
        run: paektu verify
      - name: Check posture
        run: paektu check --strict
      - name: Publish report
        if: always()
        run: paektu report --out posture.md
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: posture-report
          path: posture.md
```

`if: always()` on the report step matters. The run you most want a report from is
the one that just failed.


---

# Reference: Checks

*Source: [`docs/reference/checks.md`](https://github.com/Creative-Dhanush/paektu/blob/main/docs/reference/checks.md)*

## Check reference

Every check that ships with Paektu, what it actually proves, and what it does
not.

The last column matters most. A check's limits determine how much weight a pass
deserves, and a narrative that repeats those limits is what makes a report
trustworthy.

### Evidence types

| Type | Meaning | Strength |
| --- | --- | --- |
| `observed` | A machine read your repository | Strongest |
| `attested` | A named person confirmed it on a recorded date | Middle |
| `declared` | Somebody typed a value in a config file | Weakest |

Every result carries its type, so a reader can tell which findings rest on a
machine and which rest on somebody's word.

---

### Repository checks

Read files on disk. They verify what is **committed**, not what a hosting
provider's dashboard claims. That distinction matters during an audit: a branch
protection rule configured in a web UI and never captured in the repo leaves no
evidence trail.

#### `repo.file_present`

Asserts that at least one named file exists.

```yaml
check: repo.file_present
params:
  any_of: [LICENSE, LICENSE.md, LICENSE.txt, COPYING]
```

Accepts alternatives because projects disagree about casing and placement.

**Proves:** a file with that name exists.
**Does not prove:** that its contents are correct, current, or non-empty.

#### `repo.no_hardcoded_secrets`

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

#### `repo.dependencies_pinned`

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

#### `repo.ci_configured`

Looks for a pipeline definition: anything under `.github/workflows/`, or a
`.gitlab-ci.yml`, `Jenkinsfile` or `.circleci/config.yml`.

**Proves:** a pipeline definition exists in the repository.
**Does not prove:** that the pipeline passes, runs on the branches that matter, or
does anything at all. A workflow that only echoes a string satisfies this check.

#### `repo.tests_present`

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

#### `repo.gitignore_excludes`

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

### Posture checks

Read `paektu.yaml`. These cover facts a repository cannot establish: what the
identity provider enforces, how long logs are kept, when a backup was last
restored.

Every result is labelled `declared` or `attested`. A missing key is always a
`FAIL`, never a `SKIP` — silence is not a control.

#### `posture.is_true`

```yaml
check: posture.is_true
params:
  key: identity.mfa_enforced
```

Requires the key to be explicitly `true`. Missing or `false` both fail.

**Proves:** somebody wrote `true`.
**Does not prove:** anything about the world.

#### `posture.at_least` / `posture.at_most`

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

#### `posture.one_of`

```yaml
check: posture.one_of
params:
  key: data.min_tls_version
  allowed: ["1.2", "1.3"]
```

Restricts a value to an approved set. Compares as declared, so `"1.2"` and `1.2`
are different values — quote version strings in YAML.

#### `posture.attested`

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

### Documentation checks

The reason this tool is not a linter. Documentation is treated as a control
surface with its own evidence and failure modes.

#### `docs.narrative_current`

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

#### `docs.pages_present`

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

#### `docs.evidence_explained`

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

### Writing your own

See [writing controls](../guides/writing-controls.md). A check is one decorated
function returning a `CheckResult`; nothing else in the codebase needs to change.


---

# Troubleshooting

*Source: [`docs/troubleshooting.md`](https://github.com/Creative-Dhanush/paektu/blob/main/docs/troubleshooting.md)*

## Troubleshooting

Things that go wrong, why, and what to do.

### `paektu: command not found`

The console script was not installed or is not on your PATH.

```bash
pip install -e .
python -m paektu check
```

`python -m paektu` is equivalent and does not depend on PATH. Prefer it inside
CI, where PATH after a `pip install` is not always what you expect.

### `error: no controls found in .../controls`

You are not in the repository root, or `--controls` points somewhere empty.

```bash
paektu check --controls /path/to/controls
```

Exits `2` rather than `0`, because a run with nothing to check is a broken
invocation, not a clean bill of health.

### `error: no controls matched the given filters`

Your filters combine with AND and eliminated everything. Common cause is a
framework name that does not appear in any control:

```bash
paektu frameworks --list          # what exists
paektu frameworks                 # the full crosswalk
```

Also exits `2`. A vacuous pass would be worse than an error.

### `error: controls/x.yaml: invalid YAML`

Usually indentation, or an unquoted value YAML reads as something else. The
classic:

```yaml
clause: 10.5      # parsed as the float 10.5
clause: "10.5"    # correct
```

Quote every clause identifier. `8.4`, `1.2` and `10.5` are all strings that look
like numbers.

### `error: duplicate control id 'SEC-001'`

Two controls share an id, usually after copying a block between files. This is
fatal by design: two controls answering to one name means a report can cite a
passing result while a failing one exists.

### `ERROR unknown check 'posture.is_ture'`

A typo in the `check:` field, or a check that was never registered.

```bash
paektu checks
```

If you wrote a new check and it does not appear, it is not being imported. Checks
must live in `paektu/checks/repo.py`, `posture.py` or `docs.py` — those are the
three modules `load_builtins()` imports.

### A control fails with "not declared in paektu.yaml"

The posture key is missing. Note the nesting: `identity.mfa_enforced` means

```yaml
posture:
  identity:
    mfa_enforced: true
```

A missing key is a `FAIL`, not a `SKIP`, and that is intentional. Silence is not a
control.

### `posture.attested` fails even though I set the value to true

That check rejects a bare `true` on purpose. It wants a name and a date:

```yaml
# fails
access_review: true

# passes
access_review:
  confirmed: true
  attested_by: security-lead
  attested_on: 2026-08-15
```

The message names the missing field. Access reviews, restore tests and incident
plans all use this check, because each is a claim that means nothing without
somebody's name against it.

### `posture.one_of` fails on a value that looks correct

Almost always YAML type coercion:

```yaml
min_tls_version: 1.2      # the float 1.2, will not match "1.2"
min_tls_version: "1.2"    # correct
```

Run `--format json` and look at the evidence `detail.value` to see what the tool
actually received.

### A narrative keeps failing after I fixed the text

Editing the narrative changes its fingerprint. Fixing the words is not the same as
attesting them:

```bash
paektu attest SEC-004
```

The tool will never attest on your behalf. The fingerprint means "a person read
these words", so a tool signing it for you would make the mechanism meaningless.

### Reflowing a paragraph flagged as drift

It should not. Fingerprints are computed over whitespace-normalised text, so
rewrapping is invisible. If you saw drift, a word changed too — try
`git diff` on the control file and read carefully. Punctuation counts.

### `paektu drift` says there are no stored runs

Drift needs a baseline:

```bash
paektu check --save-evidence --label baseline
```

Artifacts land in `.paektu/evidence/`, which is gitignored because it is
generated output. That has a consequence worth knowing: **CI has no baseline
unless you provide one.** Either commit a baseline artifact deliberately, or cache
the directory between runs, or accept that `drift` is a local command and rely on
`check --strict` in CI.

### `paektu verify` reports "contents changed after recording"

An evidence artifact was edited after it was written. If that was you, the run is
no longer trustworthy — delete it and record a fresh one. If it was not you, that
is what the command is for.

The three failures it reports:

| Message | Meaning |
| --- | --- |
| `manifest hash disagrees with file` | The manifest entry was altered |
| `contents changed after recording` | The artifact was edited |
| `missing or unreadable` | The file is gone |

### Score is high but "audit ready: no"

Working as intended. The score counts controls that passed. Audit readiness
additionally requires that no narrative has drifted.

```
21 controls   pass 21   fail 0   warn 0   error 0   skip 0
posture score 100.0%
documentation drift on 1 control(s): SEC-004
audit ready: no
```

Every control passes and the posture is still not presentable, because one
narrative no longer describes the system. That gap is the reason the tool exists.

### `check` passes locally but fails in CI

Two usual causes.

**`--strict`.** If CI uses it and you did not, warnings and narrative drift block
there but not locally. Run `paektu check --strict` before pushing.

**Untracked files.** Observed checks read the working tree, so a `LICENSE` you
created but never committed passes locally and fails in CI. Run `git status` before
trusting a local pass.

### `drift` reports documentation drift with a score delta of +0.0

Correct, and the central case the tool was built for. A control still passing while
its narrative rots does not move the score. That is precisely why drift is a
separate category and why it blocks independently of the score.

### Still stuck

Open an issue at
<https://github.com/Creative-Dhanush/paektu/issues> with the command you ran,
the output, and your Python version. For anything security-sensitive, read
[SECURITY.md](../SECURITY.md) first and report privately instead.

