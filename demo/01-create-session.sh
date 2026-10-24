#!/usr/bin/env bash
# Step 1: create the investigation session "demo-house" from the sample project.
# Usage: demo/01-create-session.sh [session-root]     (default session root: demo/.sessions)
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
demo_init "$@"

demo_header "01-create-session.sh" "Create a session" \
    "Import the sample project into a new investigation session labelled $SESSION_LABEL."

demo_step "session create"
demo_note "Reads the project file, builds the project graph and stores it in a new session folder under the session root."
demo_run create session create --project "$SAMPLE" --session-label "$SESSION_LABEL"

if [ "$LAST_RC" -ne 0 ] && [ "$(demo_error_json "e['code']" 2>/dev/null)" = "SESSION_LABEL_EXISTS" ]; then
    demo_show_error
    demo_note "The session $SESSION_LABEL is already there, so nothing was created. Use demo/cleanup.sh to start afresh."
    demo_report_error create
    exit 0
fi

demo_show 30
demo_report create \
    "session_label=d['session_label']" \
    "components=d['project_import_summary']['node_counts']['component']" \
    "group_addresses=d['project_import_summary']['node_counts']['group_address']" \
    "warnings=d['project_import_summary']['warning_total']"

demo_finish
