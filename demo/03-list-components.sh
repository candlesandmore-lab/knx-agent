#!/usr/bin/env bash
# Step 3: list components with a generic query (name, individual address, ETS id, location) and the three detail levels.
# Usage: demo/03-list-components.sh [session-root]     (needs the session from 01-create-session.sh)
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
demo_init "$@"

demo_header "03-list-components.sh" "List components" \
    "Find components with a generic query and see what each detail level adds."

demo_require_session

demo_step "Looking up example values"
demo_pick_example

demo_step "No query: all components"
demo_note "Without --query every component is listed. A broad listing is never ambiguous."
demo_run list_all setup list-components --session "$SESSION_LABEL" --detail-level SUMMARY
demo_show 30
demo_report list_all "count=d['match_count']" "ambiguous=d['ambiguous']"

demo_step "Generic query by partial name"
demo_note "Without --selector-kind the kind is recognised automatically. Text matches part of a name, ignoring upper/lower case."
demo_run by_name setup list-components --session "$SESSION_LABEL" --query "$EX_NAME_PART" --detail-level SUMMARY
demo_show 30
demo_report by_name "count=d['match_count']" "ambiguous=d['ambiguous']"

demo_step "Generic query by individual address"
demo_note "An individual address such as 1.1.5 matches exactly one component. match_kinds tells how it was recognised."
demo_run by_address setup list-components --session "$SESSION_LABEL" --query "$EX_ADDRESS" --detail-level SUMMARY
demo_show 30
demo_report by_address "count=d['match_count']" "kinds=d['matches'][0]['match_kinds']"

demo_step "Generic query by ETS id"
demo_note "The ETS id is the internal identifier of the component in the project file; it matches exactly."
demo_run by_ets_id setup list-components --session "$SESSION_LABEL" --query "$EX_ETS_ID" --detail-level SUMMARY
demo_show 30
demo_report by_ets_id "count=d['match_count']" "kinds=d['matches'][0]['match_kinds']"

demo_step "Generic query by location (instance path with a trailing slash)"
demo_note "Building/Floor/Room/ with a slash at the end lists every component placed in that location."
demo_run by_path_location setup list-components --session "$SESSION_LABEL" --query "$EX_LOCATION_QUERY" --detail-level SUMMARY
demo_show 30
demo_report by_path_location "count=d['match_count']" "ambiguous=d['ambiguous']"

demo_step "Detail level SUMMARY"
demo_note "Same location query. SUMMARY gives the identity and the derived component type only."
demo_run level_summary setup list-components --session "$SESSION_LABEL" --query "$EX_LOCATION_QUERY" --detail-level SUMMARY
demo_report level_summary "count=d['match_count']" "has_topology='topology' in d['matches'][0]"

demo_step "Detail level MEDIUM"
demo_note "MEDIUM (the default) adds the topology (area, line, location) and the component parameters."
demo_run level_medium setup list-components --session "$SESSION_LABEL" --query "$EX_LOCATION_QUERY" --detail-level MEDIUM
demo_show 45
demo_report level_medium \
    "count=d['match_count']" \
    "has_topology='topology' in d['matches'][0]" \
    "has_objects='communication_objects' in d['matches'][0]"

demo_step "Detail level FULL"
demo_note "FULL adds the communication objects with their flags and group addresses, the product and the application."
demo_run level_full setup list-components --session "$SESSION_LABEL" --query "$EX_LOCATION_QUERY" --detail-level FULL
demo_show 45
demo_report level_full "count=d['match_count']" "has_objects='communication_objects' in d['matches'][0]"

demo_finish
