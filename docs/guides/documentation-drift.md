# Documentation drift

The reasoning behind the one mechanism that makes Plumbline different from a
compliance linter.

## The failure this addresses

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

## How it works

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
    Retention is declared in plumbline.yaml and compared against a ninety day
    floor, chosen because PCI DSS requires three months of immediately available
    logs.
  narrative_hash: 3f9a2b1c8d7e6f50
```

On every run the narrative is re-hashed and compared. Mismatch means somebody
changed the words since the last review, and the control is flagged regardless of
whether its check passed.

### Whitespace does not count

Fingerprints are computed over whitespace-normalised text, so this is not drift:

```
Retention is declared in plumbline.yaml
    and compared against a ninety day floor.
```

while this is:

```
Retention is declared in plumbline.yaml and compared against a thirty day floor.
```

Reformatting is not a documentation change. Changing a number is. A drift
detector that fires when someone rewraps a paragraph gets muted within a week,
and a muted detector is worse than none.

### Three outcomes, kept separate

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

## Attestation is a human act

Resolving drift is one command:

```bash
plumbline attest SEC-004
```

```
attested SEC-004: 3f9a2b1c8d7e6f50 -> 7d1e4f92a6b3c8d1
```

The tool will never do this on its own. Not as a safety limitation but because
the fingerprint's entire meaning is *"a person read these words and stands behind
them"*. A tool that could attest for you would be recording a fact about itself,
not about anyone's judgement, and the mechanism would be theatre.

For the same reason `plumbline attest` writes a targeted line edit into the YAML
rather than re-serialising the file. Round-tripping through a YAML dumper would
reflow comments and reorder keys, producing a diff nobody can review — and an
unreviewable diff in the middle of an attestation workflow defeats the purpose.

To attest everything currently stale or unreviewed:

```bash
plumbline attest all
```

Use that sparingly. Attesting twenty narratives in one command is a fair signal
that nobody read them.

## Drift is not a score regression

This is the subtle part, and it drove the design of `plumbline drift`.

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

## Honest limits

Worth stating, because a drift detector that oversells itself is the kind of tool
people learn to ignore.

- **It cannot tell whether a narrative is accurate.** It only knows whether a
  person confirmed it since it last changed. A confidently wrong narrative,
  attested, passes cleanly.
- **It cannot detect drift in prose it does not hold.** If your real
  documentation lives in a wiki and the control narrative is a summary, the
  fingerprint tracks the summary. The wiki can rot untouched.
- **Attestation is only as good as the review.** `plumbline attest all` after
  skimming is indistinguishable, to the tool, from a careful reading.
- **`docs.evidence_explained` is a keyword search.** It looks for words like
  *observed*, *declared* and *verified*. Easy to satisfy without meaning it. Its
  value is as a prompt during review, not as an assurance.

What it does buy you is that the failure mode changes shape. Instead of prose
rotting invisibly for nine months, a diff to a narrative surfaces in the next CI
run and lands in front of whoever owns the control.
