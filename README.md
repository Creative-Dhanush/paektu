<div align="center">

# Paektu

**Security controls as code — with the one thing every compliance platform forgets.**

Your automated checks pass. Your dashboard is green. And the document your auditor
actually reads has been quietly wrong for nine months.

[![CI](https://github.com/Creative-Dhanush/paektu/actions/workflows/ci.yml/badge.svg)](https://github.com/Creative-Dhanush/paektu/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Controls](https://img.shields.io/badge/controls-21-informational)](controls/)
[![Tests](https://img.shields.io/badge/tests-112%20passing-brightgreen)](tests/)
[![Self-audited](https://img.shields.io/badge/self--audited-100%25-success)](#it-audits-itself)

[Quickstart](docs/quickstart.md) · [Why this matters](#why-this-exists) · [The market](#the-market) ·
[CLI reference](docs/reference/cli.md) · [Checks](docs/reference/checks.md) · [Contributing](CONTRIBUTING.md)

</div>

---

Paektu is the highest peak on the Korean peninsula: the fixed landmark you take
your bearings from when everything else on the horizon has moved. That is the job
here. State what your controls require, check them mechanically, and keep the
written record honest about **how each fact was established**.

```bash
pip install -e . && paektu check
```

```
STATUS CONTROL     SEV       MESSAGE
------------------------------------------------------------------------------
PASS   SEC-004     high      logging.retention_days is 180 (minimum 90) (doc)
------------------------------------------------------------------------------
21 controls   pass 21   fail 0   warn 0   error 0   skip 0
posture score 100.0%
documentation drift on 1 control(s): SEC-004
audit ready: no
```

Every control passes. The score is 100%. And it is **not audit ready**, because one
narrative no longer describes the system it claims to describe.

That single line is the product.

---

## Table of contents

| Section | What it answers |
| --- | --- |
| [Why this exists](#why-this-exists) | The failure mode nobody instruments |
| [Why now](#why-now) | What changed in 2025–2026 to make this urgent |
| [What it costs to not have this](#what-it-costs-to-not-have-this) | Real money, with sources |
| [The market](#the-market) | Size, growth, and where this sits |
| [Where you actually use it](#where-you-actually-use-it) | Six concrete deployments |
| [How it works](#how-it-works) | Commands, controls, architecture |
| [Evidence typing](#evidence-typing-the-second-idea) | Why a green tick is not evidence |
| [Compared to what exists](#compared-to-what-exists) | Vanta, Drata, OpenSCAP, Cloud Custodian |
| [What it does not do](#what-it-does-not-do) | Honest limits |
| [All links](#all-links) | Everything referenced |

---

## Why this exists

A compliance programme has **three** artifacts per control, not two:

| # | Artifact | Who consumes it | Is it automated today? |
| --- | --- | --- | --- |
| 1 | **The control** — what is required | Engineers, tooling | Yes |
| 2 | **The evidence** — what a machine observed | Auditors, tooling | Yes |
| 3 | **The narrative** — prose explaining what it does and why it is adequate | **The auditor, the regulator, the enterprise buyer, and now AI agents** | **No. Nothing watches it.** |

Every compliance platform on the market automates 1 and 2. Number 3 — the part a
human being actually reads and makes a judgement on — is a text box someone filled
in once.

### The failure, concretely

> **January.** An engineer writes: *"Audit logs are retained for 90 days in line with
> PCI DSS 10.5."* True at the time.
>
> **April.** The platform team raises retention to 180 days. The automated check
> still passes — 180 is more than the 90-day floor. Nobody edits the paragraph.
>
> **October.** An auditor reads a document asserting 90 days, for a system that keeps
> 180. **The check was green the entire time.**

That is the benign direction. The dangerous one is the reverse: retention drops to
30 days, the narrative still claims 90, and now your documentation is actively
misleading a regulator while the failure sits unread in a backlog.

Neither case is detected by any tool that only watches controls and evidence.

### What Paektu does about it

Each control records a **fingerprint of the narrative a person last reviewed**.
Change the words without re-attesting, and the control is flagged — even though its
check still passes.

```
FAIL   DOC-001   high   narrative changed since attestation (a1b2c3d4 -> e5f6a7b8)
```

Fingerprints are computed over whitespace-normalised text, so **reflowing a
paragraph is not drift while changing a number is**. A detector that fires when
someone rewraps a line gets muted within a week, and a muted detector is worse than
none.

Resolving it is deliberately a **human act**:

```bash
paektu attest SEC-004
```

The tool will never attest on its own. Not as a safety limitation — because the
fingerprint's entire meaning is *"a person read these words and stands behind
them."* A tool that could sign that for you would be recording a fact about itself.

---

## Why now

Three things changed, and they compound.

| Shift | What it means for documentation |
| --- | --- |
| **Continuous audit replaced annual audit** | Evidence is sampled year-round, so a stale narrative is exposed continuously rather than once, after a quarter of cleanup time |
| **AI agents became consumers of your docs** | RAG systems and agents ground answers in your written policies. A stale narrative is no longer a document somebody might misread — it is a **training and retrieval input that confidently propagates the error** |
| **Enforcement stopped being theoretical** | ~**€7.1 billion** in cumulative GDPR fines as of January 2026, with over 60% of that landing since January 2023 ([DLA Piper](https://www.dlapiper.com/), [CMS Enforcement Tracker](https://cms.law/en/int/publication/GDPR-Enforcement-Tracker-Report/numbers-and-figures)) |

The second row is the one most teams have not priced in. When a human read a stale
policy, one person was misinformed. When an agent retrieves it, the error is served
at scale, with confidence, to everyone who asks — and the citation makes it look
verified.

---

## What it costs to not have this

Every figure below is sourced and linked. Where something is an estimate rather
than a measured finding, it says so.

### Breach economics

| Metric | Value | Source |
| --- | --- | --- |
| Global average cost of a data breach | **$4.99M** (record, up 12% YoY) | [IBM Cost of a Data Breach 2026](https://www.ibm.com/reports/data-breach) |
| United States average | **$11.5M** | IBM, 2026 |
| Added cost when AI-driven attack involved | **+~$1M** | IBM, 2026 |
| Growth in AI-driven attacks | **+56%** | IBM, 2026 |
| Study base | 602 organisations, 16 countries, 17 industries | Ponemon Institute for IBM |

### Regulatory exposure

| Regime | Maximum penalty | Reality check |
| --- | --- | --- |
| **GDPR** | €20M or **4% of global annual turnover**, whichever is higher | ~**€7.1B** cumulative since 2018; ~**€1.2B** in the last 12 months alone |
| **HIPAA** | Tiered civil penalties, escalating by culpability, with annual caps per violation category | Documentation of safeguards is explicitly required under §164.316 |
| **PCI DSS** | Contractual fines levied monthly by acquiring banks until remediation | Requirement 12 is *entirely* about documented policy |
| **SOC 2** | No fine — but a qualified opinion or delayed report | Blocks enterprise deals directly |

Ireland's DPC alone accounts for **€4.04B**, roughly **57%** of all GDPR fine value
([CMS Enforcement Tracker Report 2025/2026](https://cms.law/en/int/publication/GDPR-Enforcement-Tracker-Report/numbers-and-figures)).

### The cost of compliance itself

| Item | Cost | Source |
| --- | --- | --- |
| SOC 2 first-year total, small startup | **~$25,000** | [Workstreet](https://www.workstreet.com/blog/soc-2-audit-cost) |
| SOC 2 first-year total, large enterprise | **$200,000+** | Workstreet |
| SOC 2 Type 2 audit fee alone | **$12,000 – $100,000+** | [Drata](https://drata.com/learn/soc-2/cost) |
| Saving from compliance automation | **30–50%** of total cost | Industry reporting, see [Vanta](https://www.vanta.com/products/soc-2) |
| Reduction in audit completion time | **~50%** | Vanta |

### The cost nobody puts on a line item

This is where documentation drift specifically bites, and it is the part no
platform currently addresses:

| Hidden cost | Mechanism |
| --- | --- |
| **Audit findings from stale documentation** | An auditor who catches one wrong narrative starts testing the rest of your documentation instead of trusting it. Sampling widens. Fieldwork hours climb. |
| **Deal cycle friction** | Enterprise security reviews run to 200+ questions. Answers inconsistent with your own published policy trigger follow-up rounds and legal review. |
| **Re-audit and remediation** | A qualified opinion means remediation plus a second engagement, at full price. |
| **Loss of auditor trust — the compounding one** | Trust is cheap to lose and expensive to rebuild. Once your documents are treated as unreliable, every subsequent audit costs more, permanently. |
| **Agent-propagated misinformation** | Covered above. New in 2026, and nothing on the market instruments it. |

> **The asymmetry that makes this worth automating:** detecting narrative drift costs
> one CI job. Not detecting it costs a widened audit scope, and possibly a finding
> against a control that was *working correctly the entire time*.

---

## The market

Compliance tooling is a large, fast-growing, well-funded category — and this
specific gap is unaddressed inside it.

| Segment | 2026 size | Forecast | Source |
| --- | --- | --- | --- |
| GRC **software** (narrow) | **$23.32B** | $39.01B by 2031 | [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/governance-risk-and-compliance-software-market) |
| GRC **platforms** (broad) | **$56.73B** | — | [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/governance-risk-and-compliance-platforms-market) |
| **Enterprise** GRC | **$82.9B** | **$203.7B** by 2033 | [Grand View Research](https://www.grandviewresearch.com/industry-analysis/enterprise-governance-risk-compliance-egrc-market) |
| Overall GRC market | ~**$94.83B** | — | [Business Research Insights](https://www.businessresearchinsights.com/market-reports/governance-risk-management-and-compliance-grc-market-102540) |

Cloud captured **62.9%** of GRC software spend in 2025, and the stated growth
drivers are *"regulatory divergence, growing cyber-attack surfaces, and board-level
demand for continuous controls monitoring."*

**Continuous controls monitoring is exactly the wedge.** If controls are monitored
continuously but their documentation is reviewed annually, the gap between them
widens for eleven months of every year. That gap is what this tool measures.

### Who buys tools in this space

| Segment | Trigger to buy | Why documentation drift hurts them specifically |
| --- | --- | --- |
| **Seed/Series A SaaS** | First enterprise prospect demands SOC 2 | Writing narratives for the first time with nobody to keep them current |
| **Scaling SaaS (50–500)** | Multi-framework: SOC 2 + ISO 27001 + GDPR | One system change now invalidates narratives across three frameworks at once |
| **Fintech / lending** | RBI, MAS, OCC, PCI DSS obligations | Regulator-facing documents; being wrong in writing is the actual violation |
| **Healthtech** | HIPAA §164.316 requires documented safeguards | Documentation *is* the control, not a description of it |
| **Any company with an AI agent over internal docs** | RAG grounded on policy | Stale narrative becomes confidently-served misinformation |
| **Open-source / self-hosting** | Cannot or will not send posture data to a SaaS vendor | No incumbent serves this; the market is entirely SaaS |

That last row is worth dwelling on. Every major player — Vanta, Drata, Secureframe,
Sprinto — is closed-source SaaS that requires you to grant read access to your
cloud accounts. For a defence contractor, a regulated bank, an air-gapped
environment, or a team that simply will not hand posture data to a third party,
**there is currently no answer.** Paektu makes no network calls and holds no
credentials, by design.

---

## Where you actually use it

Six concrete deployments, in rough order of immediate practicality.

### 1. A CI gate that fails the build on documentation drift

The primary use. One job, on every pull request.

```yaml
- name: Compliance posture
  run: paektu check --strict
```

Change a control's implementation without updating its narrative, and the pull
request goes red before it merges. This is the difference between prose rotting
invisibly for nine months and a diff landing in front of whoever owns the control,
the same afternoon.

### 2. Continuous evidence for a live audit

```bash
paektu check --save-evidence --label 2026-Q3
paektu report --out posture-q3.md
paektu verify        # re-hash everything, prove nothing was edited after the fact
```

An append-only store with a content hash per run. Auditors do not want a
dashboard; they want artifacts with dates on them that reproduce.

### 3. Answering enterprise security questionnaires without a week of archaeology

```bash
paektu frameworks SOC2
```

```
SOC2: 11/12 catalogued clauses addressed (91.7%)
  CC6.1   Logical access security software and infrastructure
          controls: AC-001, AC-004, SEC-001, SEC-005
```

Clause to control to evidence, in one command. And critically, it **reports gaps
rather than hiding them** — so you learn what you cannot answer before a prospect
does.

### 4. Pre-audit gap analysis

```bash
paektu check --min-severity high --format json | jq '.results[] | select(.status=="fail")'
```

Find what would become a finding, ranked by severity, before somebody bills you
hourly to find it.

### 5. Proving you did not regress

```bash
paektu drift
```

```
score 100.0% -> 100.0% (+0.0)

DOCUMENTATION DRIFT (1)
  SEC-004 narrative changed since attestation

blocking: yes
```

**Read those numbers again.** The score did not move. A documentation regression is
invisible to a posture score, which is precisely why it needs its own category and
its own blocking behaviour.

### 6. Making your policy corpus safe for an AI agent to read

If an agent grounds answers in your compliance documentation, every narrative is a
retrieval source. `paektu check --strict` gates whether that corpus is currently
trustworthy. This is a 2026 problem with no incumbent solution.

---

## How it works

### Commands

| Command | Purpose |
| --- | --- |
| `paektu check` | Evaluate controls. `--strict` also fails on warnings and drift |
| `paektu report` | Audit-facing Markdown or JSON, with reproducible evidence hashes |
| `paektu drift` | Compare against a stored baseline across four categories |
| `paektu attest ID` | Record that a human reviewed a narrative |
| `paektu frameworks` | Clause coverage, crosswalk, and gaps |
| `paektu verify` | Re-hash stored evidence and detect tampering |
| `paektu checks` | List available check implementations |

Filters compose with AND: `--framework`, `--control`, `--tag`, `--min-severity`.

### Exit codes — built for pipelines, not people

| Code | Meaning |
| --- | --- |
| `0` | Satisfied |
| `1` | A control failed, or drift was detected |
| `2` | The tool could not run — bad config, missing controls, unreadable YAML |

The split between `1` and `2` is deliberate and most tools get it wrong. A pipeline
must distinguish *"your posture regressed"* from *"the compliance tool is broken."*
Collapse them and a typo in a control file looks like a real finding, which is how
teams learn to ignore the signal.

### The 21 shipped controls

| File | Controls | Covers |
| --- | --- | --- |
| [`access-control.yaml`](controls/access-control.yaml) | AC-001…004 | MFA, least privilege, access review, privileged session lifetime |
| [`data-protection.yaml`](controls/data-protection.yaml) | SEC-001…005 | Committed secrets, encryption at rest and in transit, log retention, gitignore hygiene |
| [`sdlc.yaml`](controls/sdlc.yaml) | SDLC-001…005 | CI, tests, dependency pinning, licence, disclosure route |
| [`resilience.yaml`](controls/resilience.yaml) | RES-001…004 | Backup restore testing, alerting, incident plan, vendor register |
| [`documentation.yaml`](controls/documentation.yaml) | DOC-001…003 | Narrative currency, documentation surface, evidence provenance |

Mapped to **SOC 2, ISO 27001, HIPAA, PCI DSS and GDPR** clauses. Controls are YAML
so a compliance owner who does not write Python can review them in a pull request:

```yaml
- id: SEC-004
  title: Audit logs are retained long enough to investigate an incident
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
    Retention is declared in paektu.yaml and compared against a ninety day floor,
    chosen because PCI DSS requires three months of immediately available logs.
    This control checks the declared figure and cannot confirm that logs are
    actually present for that whole window.
  narrative_hash: eb3deb21654b61fc
```

### Architecture

```
paektu/
├── models.py       Control, Evidence, CheckResult, RunSummary, fingerprinting
├── registry.py     YAML loading, strict validation, attestation writing
├── engine.py       Evaluation. A raising check becomes ERROR, never aborts the run
├── checks/
│   ├── repo.py     observed  — reads your repository
│   ├── posture.py  declared  — reads paektu.yaml
│   └── docs.py     observed  — narrative currency and documentation surface
├── evidence.py     Append-only store, content hashes, tamper detection
├── drift.py        Four-category comparison against a baseline
├── frameworks.py   Clause catalogue and crosswalk
├── report.py       Console tables and audit Markdown
└── cli.py          Eight subcommands, three exit codes
```

**One runtime dependency: PyYAML.** No network calls, no cloud SDKs, no credentials.
That constraint is why runs are reproducible and why the tool can be pointed at any
checkout — and it is the honest reason declared controls exist at all.

Adding a check is one decorated function. See
[writing controls](docs/guides/writing-controls.md).

---

## Evidence typing — the second idea

The most important design decision after drift detection: **not all evidence is
equal, and the tool refuses to pretend otherwise.**

| Type | Meaning | Strength | Example |
| --- | --- | --- | --- |
| `observed` | A machine read your repository | **Strongest** | No AWS keys in tracked files |
| `attested` | A named person confirmed it on a recorded date | Middle | Access review performed |
| `declared` | Somebody typed `true` in a config file | **Weakest** | MFA is enforced |

Every result carries its type through checks, reports and stored artifacts, so a
reader can tell which findings rest on a machine and which rest on somebody's word.

The higher-risk controls use `posture.attested`, which **rejects a bare `true`**:

```yaml
# fails — a tickbox is not an attestation
access_review: true

# passes
access_review:
  confirmed: true
  attested_by: security-lead
  attested_on: 2026-08-15
```

An access review with nobody's name against it is not a review.

### It audits itself

The CI pipeline runs `paektu check --strict` against this repository. If the tool
cannot hold itself to its own controls, it has no business being pointed at anyone
else's code.

| Metric | Value |
| --- | --- |
| Controls passing | **21 / 21** |
| Posture score | **100.0%** |
| Audit ready | **yes** |
| Tests | **112 passing**, Python 3.10 – 3.13 |
| Package code | 2,582 lines |
| Documentation | 1,775 lines |

---

## Compared to what exists

| | Paektu | Vanta / Drata / Secureframe | OpenSCAP | Cloud Custodian |
| --- | --- | --- | --- | --- |
| Controls as reviewable code | **Yes** (YAML) | Partial, in-platform | Yes (XCCDF) | Yes (policy) |
| **Documentation drift detection** | **Yes** | **No** | No | No |
| **Evidence strength typing** | **Yes** | No | No | No |
| Attestation requires a named signer | **Yes** | Varies | No | No |
| Framework crosswalk with gaps shown | Yes | Yes | Partial | No |
| Tamper-evident evidence store | Yes | Yes (hosted) | No | No |
| Self-hostable / air-gappable | **Yes** | No | Yes | Yes |
| Needs cloud credentials | **No** | Yes | No | Yes |
| Live cloud config scanning | No | **Yes** | Partial | **Yes** |
| Auditor network, hosted portal | No | **Yes** | No | No |
| Open source | **Apache-2.0** | No | Yes | Yes |
| Price | Free | $10k–$50k+/yr | Free | Free |

**Read this table honestly.** The commercial platforms do substantially more than
Paektu: live cloud scanning, auditor relationships, hosted trust portals, vendor
risk workflows. This is not a replacement for Vanta.

What it is: the **only** tool in the comparison that instruments the third artifact
— and it runs with no credentials, no network, and no vendor. Those two columns are
the entire argument.

---

## What it does not do

Stated plainly, because compliance tooling has a reputation for implying more than
it delivers. Every one of these is also documented in the relevant control's own
narrative.

| Limitation | Detail |
| --- | --- |
| **It does not make you compliant** | It checks what it says it checks. A green run is not an audit opinion. |
| **It cannot verify a declaration** | Write `mfa_enforced: true` without enforcing MFA and it reports a pass. It labels that pass `declared` — that is the point of the labelling — but it cannot go and look. |
| **The secret scanner is a coarse net** | Regex over the working tree. Will not find a credential removed from the tree but still in git history, nor a high-entropy string matching no known shape. |
| **It cannot tell if a narrative is *accurate*** | Only whether a person confirmed it since it last changed. A confidently wrong narrative, attested, passes cleanly. |
| **`docs.evidence_explained` is a keyword search** | Easy to satisfy without meaning it. Value is as a review prompt, not an assurance. |
| **Framework coverage is partial** | Counts clauses *addressed*, not clauses *passed*, and lists gaps rather than hiding them. |
| **No live cloud scanning** | By design. That is what `posture.yaml` and the `declared` label exist to be honest about. |
| **The evidence store is gitignored** | So CI has no `drift` baseline unless you commit or cache one deliberately. |

---

## Getting started

```bash
git clone https://github.com/Creative-Dhanush/paektu
cd paektu
pip install -e ".[dev]"

paektu check                          # evaluate everything
paektu check --framework SOC2         # one framework
paektu check --save-evidence          # record a baseline
bash examples/demo.sh                 # watch drift get caught, end to end
python -m pytest                      # 112 tests
```

The demo script is the fastest way to understand the product. It records a
baseline, changes one word of documentation, shows the check still passing while
the control is flagged, and restores the file when it exits.

---

## All links

### This project

| Resource | Link |
| --- | --- |
| Repository | https://github.com/Creative-Dhanush/paektu |
| CI pipeline | [Actions](https://github.com/Creative-Dhanush/paektu/actions) |
| Issues | [Issues](https://github.com/Creative-Dhanush/paektu/issues) |
| Documentation home | [`docs/index.md`](docs/index.md) |
| Quickstart | [`docs/quickstart.md`](docs/quickstart.md) |
| Documentation drift, in depth | [`docs/guides/documentation-drift.md`](docs/guides/documentation-drift.md) |
| Writing controls | [`docs/guides/writing-controls.md`](docs/guides/writing-controls.md) |
| CLI reference | [`docs/reference/cli.md`](docs/reference/cli.md) |
| Check reference | [`docs/reference/checks.md`](docs/reference/checks.md) |
| Troubleshooting | [`docs/troubleshooting.md`](docs/troubleshooting.md) |
| Changelog | [`CHANGELOG.md`](CHANGELOG.md) |
| Security policy | [`SECURITY.md`](SECURITY.md) |
| Contributing | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Licence | [`LICENSE`](LICENSE) — Apache-2.0 |

### Frameworks referenced

| Framework | Authority |
| --- | --- |
| SOC 2 | [AICPA Trust Services Criteria](https://www.aicpa-cima.com/resources/landing/system-and-organization-controls-soc-suite-of-services) |
| ISO/IEC 27001:2022 | [ISO](https://www.iso.org/standard/27001) |
| HIPAA Security Rule | [HHS](https://www.hhs.gov/hipaa/for-professionals/security/index.html) |
| PCI DSS v4.0 | [PCI Security Standards Council](https://www.pcisecuritystandards.org/) |
| GDPR | [EUR-Lex 2016/679](https://eur-lex.europa.eu/eli/reg/2016/679/oj) |

### Market and cost sources

| Claim | Source |
| --- | --- |
| $4.99M average breach cost, $11.5M US | [IBM Cost of a Data Breach 2026](https://www.ibm.com/reports/data-breach) |
| €7.1B cumulative GDPR fines | [CMS GDPR Enforcement Tracker 2025/2026](https://cms.law/en/int/publication/GDPR-Enforcement-Tracker-Report/numbers-and-figures) |
| GRC software $23.32B → $39.01B | [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/governance-risk-and-compliance-software-market) |
| Enterprise GRC $82.9B → $203.7B | [Grand View Research](https://www.grandviewresearch.com/industry-analysis/enterprise-governance-risk-compliance-egrc-market) |
| SOC 2 audit cost ranges | [Drata](https://drata.com/learn/soc-2/cost) · [Workstreet](https://www.workstreet.com/blog/soc-2-audit-cost) |

### Prior art and related tools

| Tool | Relationship |
| --- | --- |
| [OpenSCAP](https://www.open-scap.org/) | Host configuration scanning; no documentation layer |
| [Cloud Custodian](https://cloudcustodian.io/) | Cloud policy enforcement; no narrative concept |
| [OSCAL](https://pages.nist.gov/OSCAL/) | NIST control interchange format; a planned export target |
| [Open Policy Agent](https://www.openpolicyagent.org/) | Policy as code for authorisation, adjacent problem |
| [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) | Changelog convention used here |

---

<div align="center">

**Built by [Dhanush N](https://github.com/Creative-Dhanush)** · Apache-2.0

*Your checks passing is not the same as your documentation being true.*

</div>
