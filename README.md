# Plumbline

Security controls as code, with evidence collection and documentation drift
detection.

A plumb line is the reference you hold something against to check whether it is
true. That is the job here: define what your controls actually require, check
them mechanically, and keep the written record honest about how each fact was
established.

## The problem this addresses

Most compliance tooling models two things: the control, and the evidence. It
leaves out the third thing an auditor actually reads, which is the **narrative**
— the prose explaining what a control does and why it is adequate.

Narratives rot. The system changes, the check keeps passing, and the paragraph
describing it slowly stops being true. Nothing in the pipeline notices, because
nothing is watching the prose. The tool reports green while the document a human
will rely on has quietly become fiction.

Plumbline treats the narrative as a control surface. Each control records the
fingerprint of the narrative text a person last reviewed. Change the words
without re-attesting and the control is flagged, even though the underlying check
still passes.

```
FAIL   DOC-001   high   narrative changed since attestation (a1b2c3d4 -> e5f6a7b8)
```

## What it checks

Twenty-one controls ship in `controls/`, mapped to SOC 2, ISO 27001, HIPAA,
PCI DSS and GDPR clauses. They split into two honest categories.

**Observed** controls read your repository and report what is actually there:
committed secrets, unpinned dependencies, a missing licence, absent CI, a
`.gitignore` that does not exclude `.env`, documentation pages that do not exist.

**Declared** controls read `plumbline.yaml`, where you record the facts a
repository cannot prove — whether MFA is enforced, how long logs are retained,
when a backup was last restored.

The distinction is preserved everywhere. Every result carries an
`evidence_type` of `observed`, `declared` or `attested`, so a reader can tell at
a glance which findings rest on a machine and which rest on somebody's word.
Higher-risk controls use the `posture.attested` check, which refuses a bare
`true` and demands a name and a date.

## Install

```bash
git clone https://github.com/Creative-Dhanush/plumbline
cd plumbline
pip install -e .
```

Python 3.10 or newer. The only runtime dependency is PyYAML.

## Use

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

Other commands:

```bash
plumbline check --framework SOC2        # only controls citing SOC 2
plumbline check --min-severity high     # ignore the low-stakes ones
plumbline check --save-evidence         # record this run for later comparison
plumbline drift                         # compare now against the last recorded run
plumbline report --out posture.md       # audit-facing Markdown with evidence hashes
plumbline frameworks SOC2               # clause coverage and gaps
plumbline attest DOC-001                # confirm you have read a narrative
plumbline verify                        # re-hash stored evidence, detect tampering
plumbline checks                        # list available check implementations
```

Full command reference: [`docs/reference/cli.md`](docs/reference/cli.md).

## Exit codes

Designed for a pipeline, not a person:

| Code | Meaning |
| --- | --- |
| 0 | everything the command asked about is satisfied |
| 1 | a control failed, or drift was detected |
| 2 | the tool could not run: bad config, missing controls, unreadable YAML |

The split between 1 and 2 matters. A pipeline needs to distinguish "your posture
regressed" from "the compliance tool is broken", and collapsing both into 1 makes
a misconfigured run look like a real finding.

## Writing a control

Controls are YAML so that whoever owns compliance can read and amend them in a
pull request without writing Python:

```yaml
- id: SEC-004
  title: Audit logs are retained long enough to investigate an incident
  description: Security-relevant logs are kept for at least ninety days.
  check: posture.at_least
  severity: high
  owner: platform-team
  params:
    key: logging.retention_days
    minimum: 90
  frameworks:
    - framework: PCIDSS
      clause: "10.5"
      title: Audit log retention
  narrative: >
    Retention is declared in plumbline.yaml and compared against a ninety day
    floor, chosen because PCI DSS requires three months of immediately available
    logs. This control checks the declared figure and cannot confirm that logs
    are actually present for that whole window.
  narrative_hash: 3f9a2b1c8d7e6f50
```

A check is one decorated function. See
[`docs/guides/writing-controls.md`](docs/guides/writing-controls.md).

## What this does not do

Worth being direct about, since compliance tooling has a reputation for implying
more than it delivers.

- **It does not make you compliant.** It checks what it says it checks. A green
  run is not an audit opinion.
- **It cannot verify a declaration.** If you write `mfa_enforced: true` without
  enforcing MFA, the tool will report a pass. It will label that pass `declared`,
  which is the whole point, but it cannot go and look.
- **The secret scanner is a coarse net.** Regular expressions over the working
  tree. It will not find a credential removed from the tree but still in git
  history, and it will not spot a high-entropy string that matches no known
  shape.
- **Framework coverage is partial and says so.** `plumbline frameworks SOC2`
  reports which catalogued clauses the control set speaks to, and lists the gaps
  rather than hiding them. Coverage counts clauses addressed, not clauses passed.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
