#!/usr/bin/env bash
# Step 5: summarize the topology (areas, lines, locations) at the three detail levels.
# Usage: demo/05-summarize-topology.sh [session-root]     (needs the session from 01-create-session.sh)
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
demo_init "$@"

demo_header "05-summarize-topology.sh" "Summarize the topology" \
    "See how the project is organised: areas, lines, locations and how the components are distributed."

demo_require_session

demo_step "summarize-topology at SUMMARY"
demo_note "Counts of areas, lines and locations, locations by type, and the component counts."
demo_run topology_summary setup summarize-topology --session "$SESSION_LABEL" --detail-level SUMMARY
demo_show 50
demo_report topology_summary \
    "areas=d['topology_summary']['counts']['areas']" \
    "lines=d['topology_summary']['counts']['lines']" \
    "locations=d['topology_summary']['counts']['locations']" \
    "total=d['component_counts']['total']" \
    "placed=d['component_counts']['placed']"

demo_step "summarize-topology at MEDIUM"
demo_note "Adds the areas with their lines and a location list with the number of components per location."
demo_run topology_medium setup summarize-topology --session "$SESSION_LABEL" --detail-level MEDIUM
demo_show 50
demo_report topology_medium \
    "total=d['component_counts']['total']" \
    "area_entries=len(d['topology_summary']['areas'])" \
    "location_entries=len(d['topology_summary']['locations'])"

demo_step "summarize-topology at FULL"
demo_note "Adds the component names and individual addresses under every line and location."
demo_run topology_full setup summarize-topology --session "$SESSION_LABEL" --detail-level FULL
demo_show 50
demo_report topology_full \
    "total=d['component_counts']['total']" \
    "location_entries=len(d['topology_summary']['locations'])"

demo_finish
