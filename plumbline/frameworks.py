"""Framework crosswalk and coverage reporting.

One control usually satisfies clauses in several frameworks at once: requiring
MFA helps with SOC 2 CC6.1, ISO 27001 A.5.17 and PCI DSS 8.4 simultaneously.
Doing that mapping by hand in a spreadsheet is how organisations end up
answering the same question four times with three different answers.

The catalogue below records the clauses this tool knows how to talk about. It is
intentionally partial. Claiming to cover a whole framework is the kind of
overreach that gets a compliance tool distrusted, so unmapped clauses are
reported as gaps rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Control

# Clause titles for the subset of each framework this tool addresses. Sourced
# from the public clause listings; wording is paraphrased, not quoted.
CATALOGUE: dict[str, dict[str, str]] = {
    "SOC2": {
        "CC6.1": "Logical access security software and infrastructure",
        "CC6.2": "Registration and authorisation of new users",
        "CC6.3": "Role-based access and least privilege",
        "CC6.6": "Protection against external threats",
        "CC6.7": "Restriction of data transmission and movement",
        "CC6.8": "Prevention and detection of unauthorised software",
        "CC7.1": "Detection of configuration changes and vulnerabilities",
        "CC7.2": "Monitoring for anomalies and security events",
        "CC7.3": "Evaluation of security events for incident response",
        "CC7.4": "Response to identified security incidents",
        "CC8.1": "Change management for infrastructure and software",
        "A1.2": "Environmental protections, backup and recovery",
    },
    "ISO27001": {
        "A.5.15": "Access control",
        "A.5.17": "Authentication information",
        "A.5.23": "Information security for cloud services",
        "A.5.30": "ICT readiness for business continuity",
        "A.8.8": "Management of technical vulnerabilities",
        "A.8.9": "Configuration management",
        "A.8.12": "Data leakage prevention",
        "A.8.15": "Logging",
        "A.8.16": "Monitoring activities",
        "A.8.24": "Use of cryptography",
        "A.8.25": "Secure development lifecycle",
        "A.8.28": "Secure coding",
        "A.8.32": "Change management",
    },
    "HIPAA": {
        "164.308(a)(1)": "Security management process and risk analysis",
        "164.308(a)(4)": "Information access management",
        "164.308(a)(5)": "Security awareness and training",
        "164.308(a)(7)": "Contingency plan",
        "164.312(a)(1)": "Access control",
        "164.312(b)": "Audit controls",
        "164.312(e)(1)": "Transmission security",
    },
    "PCIDSS": {
        "2.2": "Secure configuration standards",
        "3.5": "Protection of stored account data",
        "4.2": "Strong cryptography during transmission",
        "6.2": "Secure software development",
        "6.3": "Identification and management of vulnerabilities",
        "8.3": "Strong authentication for users",
        "8.4": "Multi-factor authentication",
        "10.2": "Audit logs for all system components",
        "10.5": "Audit log retention",
        "12.10": "Incident response readiness",
    },
    "GDPR": {
        "Art.5": "Principles for processing personal data",
        "Art.25": "Data protection by design and by default",
        "Art.30": "Records of processing activities",
        "Art.32": "Security of processing",
        "Art.33": "Notification of a personal data breach",
        "Art.35": "Data protection impact assessment",
    },
}

ALIASES = {
    "soc2": "SOC2",
    "soc 2": "SOC2",
    "soc2type2": "SOC2",
    "iso": "ISO27001",
    "iso27001": "ISO27001",
    "iso 27001": "ISO27001",
    "hipaa": "HIPAA",
    "pci": "PCIDSS",
    "pcidss": "PCIDSS",
    "pci dss": "PCIDSS",
    "gdpr": "GDPR",
}


def canonical(name: str) -> str:
    """Resolve a user-supplied framework name to its catalogue key."""
    key = name.strip().lower().replace("-", "").replace("_", "")
    if key in ALIASES:
        return ALIASES[key]
    for candidate in CATALOGUE:
        if candidate.lower() == key:
            return candidate
    return name.strip().upper()


def known_frameworks() -> list[str]:
    return sorted(CATALOGUE)


@dataclass
class Coverage:
    """How much of one framework the current control set speaks to."""

    framework: str
    mapped: dict[str, list[str]]
    unmapped: list[str]
    unknown: dict[str, list[str]]

    @property
    def total_clauses(self) -> int:
        return len(self.mapped) + len(self.unmapped)

    @property
    def percent(self) -> float:
        if not self.total_clauses:
            return 0.0
        return round(100.0 * len(self.mapped) / self.total_clauses, 1)

    def clause_title(self, clause: str) -> str:
        return CATALOGUE.get(self.framework, {}).get(clause, "")


def coverage(controls: Iterable[Control], framework: str) -> Coverage:
    """Work out which clauses of a framework the controls actually cover.

    Clauses cited by a control but absent from the catalogue are surfaced under
    `unknown` rather than dropped. That usually means a typo in a control file,
    and silently ignoring it would let a mapping error masquerade as coverage.
    """
    name = canonical(framework)
    catalogue = CATALOGUE.get(name, {})

    mapped: dict[str, list[str]] = {}
    unknown: dict[str, list[str]] = {}

    for control in controls:
        for ref in control.frameworks_named(name):
            bucket = mapped if ref.clause in catalogue else unknown
            bucket.setdefault(ref.clause, []).append(control.id)

    unmapped = sorted(set(catalogue) - set(mapped))

    return Coverage(
        framework=name,
        mapped={k: sorted(v) for k, v in sorted(mapped.items())},
        unmapped=unmapped,
        unknown={k: sorted(v) for k, v in sorted(unknown.items())},
    )


def crosswalk(controls: Iterable[Control]) -> dict[str, dict[str, list[str]]]:
    """Build a framework -> clause -> control-ids index across all frameworks."""
    table: dict[str, dict[str, list[str]]] = {}
    for control in controls:
        for ref in control.frameworks:
            name = canonical(ref.framework)
            table.setdefault(name, {}).setdefault(ref.clause, []).append(control.id)
    return {
        framework: {clause: sorted(ids) for clause, ids in sorted(clauses.items())}
        for framework, clauses in sorted(table.items())
    }
