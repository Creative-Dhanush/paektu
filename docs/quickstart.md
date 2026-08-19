# Quickstart

Getting from nothing to a first report, and then to the one behaviour that makes
this tool different from a linter.

## Requirements

Python 3.10 or newer. The only runtime dependency is PyYAML.

## Install

```bash
git clone https://github.com/Creative-Dhanush/plumbline
cd plumbline
pip install -e .
```

Confirm it landed:

```bash
plumbline --version
```

If `plumbline` is not on your PATH, `python -m plumbline` works identically and
is the safer form inside CI.

## 1. Run your first check

From the repository root:

```bash
plumbline check
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

## 2. Narrow the run

```bash
plumbline check --framework SOC2         # only controls citing SOC 2
plumbline check --min-severity high      # skip the low-stakes ones
plumbline check --control SEC-001        # one control
plumbline check --tag observed           # only machine-verified controls
```

The last one is worth knowing. Controls tagged `observed` are the ones a machine
actually verified, as opposed to those resting on a declaration in
`plumbline.yaml`. When someone asks what you can genuinely prove, that is the
filter to reach for.

## 3. Record a baseline

Drift detection needs something to compare against:

```bash
plumbline check --save-evidence --label baseline
```

This writes a timestamped JSON artifact under `.plumbline/evidence/` and adds it
to a manifest. Runs are append-only: nothing here rewrites or deletes a previous
one, because a compliance tool that can quietly revise its own history is not
worth much as a source of truth.

## 4. Watch documentation drift get caught

Here is the part that matters. Open any control file in `controls/` and change a
word in a `narrative:` block. For example, in `controls/data-protection.yaml`,
change SEC-004's narrative from `ninety day floor` to `thirty day floor`.

Now re-run:

```bash
plumbline check --control SEC-004
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
plumbline attest SEC-004
```

```
attested SEC-004: 3f9a2b1c8d7e6f50 -> 7d1e4f92a6b3c8d1
```

The tool will never attest on your behalf. The fingerprint means "a person read
these words", and a tool signing that for you would make the whole mechanism
worthless.

## 5. Compare against the baseline

```bash
plumbline drift
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

## 6. Produce an audit-facing report

```bash
plumbline report --out posture.md
```

Markdown rather than PDF, because Markdown diffs. Being able to see what changed
between last quarter's report and this one is worth more than typographic polish.

The report includes evidence hashes. Re-running `check` on an unchanged target
reproduces them, which is how a reviewer confirms the artifact they were handed
is the one the tool actually produced.

## 7. Wire it into CI

```yaml
- name: Compliance posture
  run: plumbline check --strict
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

## Next

- [Writing controls](guides/writing-controls.md) to add your own
- [Documentation drift](guides/documentation-drift.md) for the reasoning behind
  the fingerprint mechanism
- [CLI reference](reference/cli.md) for every flag
