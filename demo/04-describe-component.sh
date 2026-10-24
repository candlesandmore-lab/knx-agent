#!/usr/bin/env bash
# Step 4: describe one component at the detail levels MEDIUM and FULL.
# Usage: demo/04-describe-component.sh [session-root]     (needs the session from 01-create-session.sh)
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
demo_init "$@"

demo_header "04-describe-component.sh" "Describe one component" \
    "Look at a single component in detail: identity, topology, communication objects and group addresses."

demo_require_session

demo_step "Looking up example values"
demo_pick_example

demo_step "describe-component at MEDIUM"
demo_note "One component, selected by its ETS id: identity, derived type, topology and parameters."
demo_run describe_medium setup describe-component --session "$SESSION_LABEL" --component "$EX_ETS_ID" --detail-level MEDIUM
demo_show 50
demo_report describe_medium \
    "count=d['match_count']" \
    "has_topology='topology' in d['components'][0]" \
    "has_objects='communication_objects' in d['components'][0]"

demo_step "describe-component at FULL"
demo_note "The same component with its communication objects, their flags and the linked group addresses."
demo_run describe_full setup describe-component --session "$SESSION_LABEL" --component "$EX_ETS_ID" --detail-level FULL
demo_show 60
demo_report describe_full \
    "count=d['match_count']" \
    "objects=len(d['components'][0]['communication_objects'])" \
    "group_addresses=len(d['components'][0]['group_addresses'])"
demo_note "How to read a communication object: label is its name, flags tell what it may do (transmit, write, read, ...),"
demo_note "and group_addresses lists the group addresses it is linked to."

demo_finish
