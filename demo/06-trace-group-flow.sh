#!/usr/bin/env bash
# Step 6: trace which components take part in a group address (by address, by partial name, by communication object).
# Usage: demo/06-trace-group-flow.sh [session-root]     (needs the session from 01-create-session.sh)
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
demo_init "$@"

demo_header "06-trace-group-flow.sh" "Trace a group address" \
    "See which components send to or receive from a group address, with a direction label for each."

demo_require_session

demo_step "Looking up example values"
demo_pick_example

demo_step "trace-group-flow by group address"
demo_note "One group address given as written in ETS. Each participant has a direction: SENDER, RECEIVER, SENDER_RECEIVER or UNDETERMINED."
demo_run flow_by_address setup trace-group-flow --session "$SESSION_LABEL" --group-address "$EX_GROUP_ADDRESS"
demo_show 60
demo_report flow_by_address \
    "count=d['match_count']" \
    "ambiguous=d['ambiguous']" \
    "participants=len(d['group_addresses'][0]['participants'])" \
    "value=d['group_addresses'][0]['current_value']"
demo_note "current_value is always unknown: the agent does not know live bus values."

demo_step "trace-group-flow by partial group address name"
demo_note "Text that is not an address is matched against group address names. Several may match: the answer is a set (ambiguous=True)."
demo_run flow_by_name setup trace-group-flow --session "$SESSION_LABEL" --group-address "$EX_NAME_WORD" --detail-level SUMMARY
demo_show 30
demo_report flow_by_name "count=d['match_count']" "ambiguous=d['ambiguous']"

demo_step "trace-group-flow starting from a communication object"
demo_note "--object-ref names one communication object; the answer covers every group address it is linked to."
demo_run flow_by_object setup trace-group-flow --session "$SESSION_LABEL" --object-ref "$EX_OBJECT_REF"
demo_show 40
demo_report flow_by_object \
    "count=d['match_count']" \
    "participants=len(d['group_addresses'][0]['participants'])"

demo_finish
