# Troubleshooting

Things that go wrong, why, and what to do.

## `paektu: command not found`

The console script was not installed or is not on your PATH.

```bash
pip install -e .
python -m paektu check
```

`python -m paektu` is equivalent and does not depend on PATH. Prefer it inside
CI, where PATH after a `pip install` is not always what you expect.

## `error: no controls found in .../controls`

You are not in the repository root, or `--controls` points somewhere empty.

```bash
paektu check --controls /path/to/controls
```

Exits `2` rather than `0`, because a run with nothing to check is a broken
invocation, not a clean bill of health.

## `error: no controls matched the given filters`

Your filters combine with AND and eliminated everything. Common cause is a
framework name that does not appear in any control:

```bash
paektu frameworks --list          # what exists
paektu frameworks                 # the full crosswalk
```

Also exits `2`. A vacuous pass would be worse than an error.

## `error: controls/x.yaml: invalid YAML`

Usually indentation, or an unquoted value YAML reads as something else. The
classic:

```yaml
clause: 10.5      # parsed as the float 10.5
clause: "10.5"    # correct
```

Quote every clause identifier. `8.4`, `1.2` and `10.5` are all strings that look
like numbers.

## `error: duplicate control id 'SEC-001'`

Two controls share an id, usually after copying a block between files. This is
fatal by design: two controls answering to one name means a report can cite a
passing result while a failing one exists.

## `ERROR unknown check 'posture.is_ture'`

A typo in the `check:` field, or a check that was never registered.

```bash
paektu checks
```

If you wrote a new check and it does not appear, it is not being imported. Checks
must live in `paektu/checks/repo.py`, `posture.py` or `docs.py` — those are the
three modules `load_builtins()` imports.

## A control fails with "not declared in paektu.yaml"

The posture key is missing. Note the nesting: `identity.mfa_enforced` means

```yaml
posture:
  identity:
    mfa_enforced: true
```

A missing key is a `FAIL`, not a `SKIP`, and that is intentional. Silence is not a
control.

## `posture.attested` fails even though I set the value to true

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

## `posture.one_of` fails on a value that looks correct

Almost always YAML type coercion:

```yaml
min_tls_version: 1.2      # the float 1.2, will not match "1.2"
min_tls_version: "1.2"    # correct
```

Run `--format json` and look at the evidence `detail.value` to see what the tool
actually received.

## A narrative keeps failing after I fixed the text

Editing the narrative changes its fingerprint. Fixing the words is not the same as
attesting them:

```bash
paektu attest SEC-004
```

The tool will never attest on your behalf. The fingerprint means "a person read
these words", so a tool signing it for you would make the mechanism meaningless.

## Reflowing a paragraph flagged as drift

It should not. Fingerprints are computed over whitespace-normalised text, so
rewrapping is invisible. If you saw drift, a word changed too — try
`git diff` on the control file and read carefully. Punctuation counts.

## `paektu drift` says there are no stored runs

Drift needs a baseline:

```bash
paektu check --save-evidence --label baseline
```

Artifacts land in `.paektu/evidence/`, which is gitignored because it is
generated output. That has a consequence worth knowing: **CI has no baseline
unless you provide one.** Either commit a baseline artifact deliberately, or cache
the directory between runs, or accept that `drift` is a local command and rely on
`check --strict` in CI.

## `paektu verify` reports "contents changed after recording"

An evidence artifact was edited after it was written. If that was you, the run is
no longer trustworthy — delete it and record a fresh one. If it was not you, that
is what the command is for.

The three failures it reports:

| Message | Meaning |
| --- | --- |
| `manifest hash disagrees with file` | The manifest entry was altered |
| `contents changed after recording` | The artifact was edited |
| `missing or unreadable` | The file is gone |

## Score is high but "audit ready: no"

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

## `check` passes locally but fails in CI

Two usual causes.

**`--strict`.** If CI uses it and you did not, warnings and narrative drift block
there but not locally. Run `paektu check --strict` before pushing.

**Untracked files.** Observed checks read the working tree, so a `LICENSE` you
created but never committed passes locally and fails in CI. Run `git status` before
trusting a local pass.

## `drift` reports documentation drift with a score delta of +0.0

Correct, and the central case the tool was built for. A control still passing while
its narrative rots does not move the score. That is precisely why drift is a
separate category and why it blocks independently of the score.

## Still stuck

Open an issue at
<https://github.com/Creative-Dhanush/paektu/issues> with the command you ran,
the output, and your Python version. For anything security-sensitive, read
[SECURITY.md](../SECURITY.md) first and report privately instead.
