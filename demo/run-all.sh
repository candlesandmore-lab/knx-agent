#!/usr/bin/env bash
# Run the whole demo tour: clean the session root, then scripts 01 to 07 in order.
# Usage: demo/run-all.sh [session-root]     (default session root: demo/.sessions)
# A failing script does not stop the tour. Exit code 0 only when all seven scripts exited 0.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
demo_init "$@"

ROOT_ARGUMENT="${1:-}"

echo "knx-agent demo tour. Session root: $SESSION_ROOT"

# Fresh tour: remove the session root of an earlier run. A root that does not exist yet needs no cleaning.
if [ -z "$ROOT_ARGUMENT" ]; then
    bash demo/cleanup.sh
    CLEAN_RC=$?
elif [ -e "$ROOT_ARGUMENT" ] || [ -L "$ROOT_ARGUMENT" ]; then
    bash demo/cleanup.sh "$ROOT_ARGUMENT"
    CLEAN_RC=$?
else
    CLEAN_RC=0
fi
if [ "$CLEAN_RC" -ne 0 ]; then
    echo "run-all.sh: the session root could not be cleaned (see the message above); the tour was not started." >&2
    exit 2
fi

SCRIPTS="01-create-session.sh 02-describe-and-reimport.sh 03-list-components.sh 04-describe-component.sh 05-summarize-topology.sh 06-trace-group-flow.sh 07-errors.sh"
SUMMARY=""
PASSED=0
TOTAL=0
for script in $SCRIPTS; do
    TOTAL=$((TOTAL + 1))
    bash "demo/$script" ${ROOT_ARGUMENT:+"$ROOT_ARGUMENT"}
    rc=$?
    if [ "$rc" -eq 0 ]; then
        PASSED=$((PASSED + 1))
    fi
    SUMMARY="$SUMMARY
$script  exit code $rc"
done

echo
echo "================================================================================"
echo "Summary"
echo "================================================================================"
echo "script / exit code$SUMMARY"
echo
echo "Tour complete: $PASSED of $TOTAL scripts passed"
echo "Clean up with demo/cleanup.sh"
if [ "$PASSED" -eq "$TOTAL" ]; then
    exit 0
fi
exit 1
