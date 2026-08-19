# Plumbline

Security controls as code, with evidence collection and documentation drift
detection.

A plumb line is the reference you hold something against to check whether it is
true. That is the job here: state what your controls require, check them
mechanically, and keep the written record honest about how each fact was
established.

## Why this exists

Compliance tooling generally models two things: the **control** and the
**evidence**. It leaves out the third thing an auditor actually reads, which is
the **narrative** — the prose explaining what a control does and why it is
adequate.

Narratives rot. The system changes, the automated check keeps passing, and the
paragraph describing it slowly stops being true. Nothing notices, because nothing
is watching the prose. The dashboard is green while the document a human relies
on has quietly become fiction.

Plumbline treats the narrative as a control surface with its own evidence and its
own failure modes. Each control records the fingerprint of the narrative text a
person last reviewed. Change the words without re-attesting and the control is
flagged, even though the underlying check still passes:

```
FAIL   DOC-001   high   narrative changed since attestation (a1b2c3d4 -> e5f6a7b8)
```

That single behaviour is the reason the tool exists. Everything else is
scaffolding to make it useful.

## The trust model

The most important idea in Plumbline is that not all evidence is equal, and the
tool refuses to pretend otherwise. Every result is labelled with how the fact was
established:

| Type | Meaning | Strength |
| --- | --- | --- |
| `observed` | A machine read your repository and saw this | Strongest |
| `attested` | A named person confirmed it on a recorded date | Middle |
| `declared` | Somebody typed `true` in a config file | Weakest |

**Observed** controls read files: committed secrets, unpinned dependencies, a
missing licence, absent CI, documentation pages that do not exist.

**Declared** controls read `plumbline.yaml`, which holds the facts a repository
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

## Where to go next

| If you want to | Read |
| --- | --- |
| Run it for the first time | [Quickstart](quickstart.md) |
| Understand every command | [CLI reference](reference/cli.md) |
| Write your own control | [Writing controls](guides/writing-controls.md) |
| Understand narrative drift | [Documentation drift](guides/documentation-drift.md) |
| See what checks exist | [Check reference](reference/checks.md) |
| Fix something that broke | [Troubleshooting](troubleshooting.md) |

## What it does not do

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
