#!/usr/bin/env bash
#
# End-to-end walkthrough of the behaviour that distinguishes Plumbline from a
# linter: a control that keeps passing while its documentation silently rots.
#
# Run from the repository root:
#
#     bash examples/demo.sh
#
# It edits controls/data-protection.yaml and restores it at the end, so it is
# safe to run on a clean checkout. It does leave an evidence artifact behind in
# .plumbline/, which is gitignored.

set -euo pipefail

CONTROL_FILE="controls/data-protection.yaml"
ORIGINAL="floor. Ninety days is chosen because PCI DSS requires three months of"
MODIFIED="floor. Thirty days is chosen because PCI DSS requires one month of"

restore() {
  if grep -qF "$MODIFIED" "$CONTROL_FILE" 2>/dev/null; then
    # Portable in-place edit: BSD sed on macOS requires an argument to -i.
    perl -pi -e "s/\Q$MODIFIED\E/$ORIGINAL/" "$CONTROL_FILE"
    echo
    echo "(restored $CONTROL_FILE)"
  fi
}
trap restore EXIT

rule() { printf '\n%s\n%s\n' "$1" "$(printf '=%.0s' $(seq 1 ${#1}))"; }

rule "1. Baseline: every control passes"
python -m plumbline check --save-evidence --label demo-baseline | tail -6

rule "2. Change one word of documentation"
echo "Editing SEC-004's narrative: 'ninety day floor' becomes 'thirty day floor'."
echo "The system is untouched. Log retention is still 180 days."
perl -pi -e "s/\Q$ORIGINAL\E/$MODIFIED/" "$CONTROL_FILE"

rule "3. The check still passes, but the control is flagged"
python -m plumbline check --control SEC-004

rule "4. Drift, with the score unchanged"
echo "This is the point. A documentation regression does not move the posture"
echo "score, so anything watching only the score would never see it."
echo
python -m plumbline drift || true

rule "5. Resolving it is a human act"
echo "A person reads the new wording, decides whether they stand behind it, then:"
echo
echo "    plumbline attest SEC-004"
echo
echo "The tool will never attest on its own. The fingerprint means 'a person read"
echo "these words', and a tool signing that for you would make it meaningless."
