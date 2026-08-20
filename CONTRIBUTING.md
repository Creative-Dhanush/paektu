# Contributing

## Setup

```bash
git clone https://github.com/Creative-Dhanush/paektu
cd paektu
pip install -e ".[dev]"
python -m pytest
```

Python 3.10 or newer. PyYAML is the only runtime dependency, and it should stay
that way — a tool that runs in someone's CI to check their compliance posture has
no business dragging in a large dependency tree.

## Before opening a pull request

```bash
python -m pytest              # all tests pass
paektu check --strict      # the repo satisfies its own controls
```

Both run in CI. The second one matters: if this tool cannot hold itself to its own
controls, it has no business being pointed at anyone else's code.

If you changed a control narrative, attest it:

```bash
paektu attest CONTROL-ID
```

Otherwise `DOC-001` will flag the drift and `--strict` will fail the build. That is
the feature working, not a nuisance.

## Adding a check

See [`docs/guides/writing-controls.md`](docs/guides/writing-controls.md) for the
full walkthrough. Briefly: a check is one decorated function in
`paektu/checks/repo.py`, `posture.py` or `docs.py`, returning a `CheckResult`.

A new check needs three things alongside it:

1. **Tests for both the pass and the fail path.** Use `tmp_path` to build a
   synthetic repository rather than asserting against this one.
2. **A row in `docs/reference/checks.md`** including what it does *not* prove.
   That column is the most useful part of the document.
3. **A one-line docstring**, because `paektu checks` prints it.

## Adding a control

Controls are YAML in `controls/`. Every one needs a `narrative`, and the shipped
test suite enforces that along with citing at least one framework and naming a
registered check.

Write the narrative for an auditor, not for a developer. Say whether the fact is
observed or declared, state the limits of the check, and explain where any numbers
came from. A narrative admitting that a regex scanner misses git history is worth
more than one implying comprehensive coverage.

## Conventions

**Status codes carry meaning.** `SKIP` is "not applicable", `FAIL` is "not
satisfied", `WARN` is "present but inadequate", `ERROR` is "the tool could not
evaluate this". Conflating skip and fail makes the posture score meaningless.

**Return, do not raise.** The engine converts exceptions into `ERROR` results so
one broken check cannot cost a whole run, but a returned status carries a better
message than a caught traceback.

**Every failure gets a `remediation`.** A finding with no next action becomes a
permanent backlog item.

**Attach evidence with a `detail` payload.** It gets hashed and the hash lands in
the audit report. Evidence a reviewer cannot reproduce is decoration.

**No network calls.** Checks read a repository path and a posture document. That
constraint is why runs are reproducible and why the tool needs no credentials, and
it is the reason declared controls exist at all.

**Serialise with `default=str`.** YAML turns `attested_on: 2026-08-15` into a
`date`, and every real posture file has one. A `json.dumps` without a fallback
encoder crashes on the first attested control. There is a regression test for this
because it has already happened once.

## Docs are part of the change

`DOC-002` requires a fixed set of pages to exist and carry real content, so a
change that outdates a documented behaviour fails CI until the page is updated.
That is deliberate. This project is about documentation keeping pace with the
product, and shipping a version that does not do so itself would be an odd look.

## Reporting bugs

Open an issue with the command, the output, and your Python version. For anything
security-sensitive read [SECURITY.md](SECURITY.md) and report privately instead.
