# Writing controls

Adding a control means writing YAML. Adding a *check* means writing one Python
function. Most of the time you only need the first.

## Anatomy of a control

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
    Retention is declared in plumbline.yaml and compared against a ninety day
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
| `narrative_hash` | no | Written by `plumbline attest`, not by hand. |

Files live in `controls/` and are grouped by theme. Grouping is cosmetic; the
loader reads every `.yaml` and `.yml` in the directory tree.

Duplicate ids are a fatal error rather than a warning. Two controls answering to
one name means a report can cite a passing result while a failing one exists.

## Choosing a check

Run `plumbline checks` for the live list. Three families ship:

### Repository checks — observed

These read files. Strongest evidence available, because a machine looked.

| Check | Params | Asks |
| --- | --- | --- |
| `repo.file_present` | `any_of` | Does one of these files exist? |
| `repo.no_hardcoded_secrets` | `allow_paths` | Any credential-shaped strings? |
| `repo.dependencies_pinned` | `manifests` | Every requirement version-constrained? |
| `repo.ci_configured` | — | Is there a pipeline definition? |
| `repo.tests_present` | `paths`, `min_files` | Does a test suite exist? |
| `repo.gitignore_excludes` | `patterns` | Are secret patterns ignored? |

### Posture checks — declared

These read `plumbline.yaml` for facts a repository cannot prove.

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

### Documentation checks — observed

| Check | Params | Asks |
| --- | --- | --- |
| `docs.narrative_current` | — | Does the prose match its attestation? |
| `docs.pages_present` | `pages`, `min_chars` | Do the docs cover a minimum surface? |
| `docs.evidence_explained` | `markers` | Does the narrative state its provenance? |

## Writing a narrative that earns its place

The narrative is what an auditor reads. Three things make it useful:

**Say whether the fact was observed or declared.** This is the single most
valuable sentence you can write. "Observed by reading .gitignore" and "declared in
plumbline.yaml" tell a reader precisely how much weight to give the pass.

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

## Adding a new check

A check is one function. It receives the control and a `Target`, and returns a
`CheckResult`.

```python
from ..models import Evidence, Status
from . import Target, register, result


@register("repo.readme_mentions_security")
def readme_mentions_security(control, target: Target):
    """One-line summary. Shown by `plumbline checks`."""
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

Put it in `plumbline/checks/repo.py`, `posture.py` or `docs.py`. The decorator
registers it; `load_builtins()` imports those three modules, so nothing else needs
to change.

### The `Target` API

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

### Rules worth following

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

## Verifying your work

```bash
plumbline checks                     # is it registered?
plumbline check --control YOUR-ID    # does it behave?
plumbline check --control YOUR-ID --format json
python -m pytest
```

The shipped test suite asserts that every control in `controls/` loads, cites at
least one framework, names a registered check, and carries a narrative. A control
that fails those is caught in CI rather than in a report.
