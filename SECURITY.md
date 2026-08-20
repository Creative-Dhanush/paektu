# Security policy

## Reporting a vulnerability

Report security issues privately by email to **dhanush416158@gmail.com** with
the subject line `paektu security`. Please do not open a public issue for a
vulnerability, since that discloses it to everyone before there is a fix.

Include whatever you have: affected version, what you did, what happened, and
what you expected. A rough report sent early is more useful than a polished one
sent late.

You should get an acknowledgement within **72 hours**. If you do not, assume the
mail was lost and try again rather than assuming it was ignored.

## Supported versions

Paektu is pre-1.0 and only the latest release receives fixes.

| Version | Supported |
| --- | --- |
| 0.1.x | yes |
| < 0.1 | no |

## Scope

Paektu reads files from a repository path you point it at, parses YAML, and
writes JSON and Markdown. It makes no network calls and holds no credentials.
The interesting attack surface is therefore what happens when it is pointed at
a repository it should not trust.

In scope:

- Path traversal that lets a control definition read outside the target root
- YAML parsing that executes code or constructs arbitrary objects
- A crafted repository that causes unbounded resource consumption during a scan
- Evidence artifacts that can be altered without `paektu verify` noticing

Out of scope:

- The secret scanner missing a credential. `repo.no_hardcoded_secrets` is a
  regular-expression scan of the working tree and is documented as a coarse net,
  not a replacement for a dedicated scanner. Missed detections are a known
  limitation rather than a vulnerability. Reports of new patterns worth adding
  are very welcome as ordinary issues.
- Someone editing `paektu.yaml` to make a declared control pass. That is the
  documented trust model, not a flaw. See `docs/guides/documentation-drift.md`.

## What this tool does not do

Paektu does not make you compliant, and a green run is not an audit opinion.
It checks what it says it checks, records how each fact was established, and
distinguishes an observation from somebody's declaration. Everything beyond that
is the reader's judgement.
