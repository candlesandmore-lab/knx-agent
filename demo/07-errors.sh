#!/usr/bin/env bash
# Step 7: three calls that fail on purpose, to show how errors look. They must not stop the tour.
# Usage: demo/07-errors.sh [session-root]     (needs the session from 01-create-session.sh)
# Exit code 0 when all three calls failed with exit 1 and the documented error code, otherwise 1.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
demo_init "$@"

demo_header "07-errors.sh" "Error examples" \
    "Three failing calls: a missing session, an unknown component and an unknown group address."

demo_require_session

demo_step "Session that does not exist"
demo_note "Expected: exit code 1, nothing on stdout, error code SESSION_NOT_FOUND."
demo_run err_session_not_found session describe --session demo-no-such-session
demo_show_error
demo_report_error err_session_not_found
demo_expect_error err_session_not_found SESSION_NOT_FOUND
demo_note "code names the problem, message explains it, details.session_label is the label that was not found."

demo_step "Component that does not exist"
demo_note "Expected: exit code 1, error code SELECTOR_UNRESOLVED."
demo_run err_selector_unresolved_component setup describe-component --session "$SESSION_LABEL" --component no-such-component-xyz
demo_show_error
demo_report_error err_selector_unresolved_component
demo_expect_error err_selector_unresolved_component SELECTOR_UNRESOLVED
demo_note "details.selector is what you typed, selector_kind ANY is the automatic recognition, evaluated_kinds lists what was tried."

demo_step "Group address that does not exist"
demo_note "31/7/255 is a valid address form (the highest one) but not used in the project. Expected: SELECTOR_UNRESOLVED."
demo_run err_selector_unresolved_group_address setup trace-group-flow --session "$SESSION_LABEL" --group-address 31/7/255
demo_show_error
demo_report_error err_selector_unresolved_group_address
demo_expect_error err_selector_unresolved_group_address SELECTOR_UNRESOLVED
demo_note "details.selector_kind GROUP_ADDRESS and details.address_raw show how the address was understood."

demo_finish
