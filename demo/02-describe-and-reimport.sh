#!/usr/bin/env bash
# Step 2: look at the session and re-read the project file.
# Usage: demo/02-describe-and-reimport.sh [session-root]     (needs the session from 01-create-session.sh)
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
demo_init "$@"

demo_header "02-describe-and-reimport.sh" "Describe a session and re-import the project" \
    "Show what a session knows about its project, then re-read the project file."

demo_require_session

demo_step "session describe"
demo_note "Shows the session: its project file, the import summary and the refresh status."
demo_run describe session describe --session "$SESSION_LABEL"
demo_show 40
demo_report describe \
    "last_status=d['project_refresh']['last_status']" \
    "reimport_count=d['project_refresh']['reimport_count']" \
    "components=d['project_import']['project_import_summary']['node_counts']['component']"

demo_step "session describe with more log detail"
demo_note "Same answer. With --log-level DEBUG the log lines on stderr show more of what happens inside."
demo_run describe_debug session describe --session "$SESSION_LABEL" --log-level DEBUG
demo_show 8
demo_report describe_debug "session_label=d['session_label']"

demo_step "session reimport"
demo_note "Re-reads the project file. Nothing has changed, so the status is UNCHANGED and there are no changes."
demo_run reimport session reimport --session "$SESSION_LABEL"
demo_show 30
demo_report reimport \
    "status=d['project_refresh_status']" \
    "changes=len(d['changes'])" \
    "invalidated=len(d['invalidated_references'])"

demo_finish
