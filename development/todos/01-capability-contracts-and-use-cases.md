# Todo 01: Clean up and unify the capability API definition
Source: docs/methodology/001-use-cases-raw.md (answered), docs/implementation/001 (capability families), 002 (tool mappings), 003 (proposed APIs)
Problem: the capability set is defined three times with different names and coverage. Goal: ONE authoritative, reviewed capability catalogue (docs/implementation/003), with 001 and 002 reduced to references to it, derived from the answered use cases. Per capability: name, purpose, request, response (evidence sources, limitation notes), errors, CLI/SDK/MCP projection, and the use case it traces to.

Inconsistencies to resolve (each is a decision for the user; none is auto-picked):
1. Naming: describe_device (001) vs describe_component (003); explain_expected_reaction + list_possible_causes + compare_expected_vs_observed + simulate_outcome (001) vs single answer_activity_question (003); `label` (002, CLI) vs `session_label` (003).
2. Capabilities in 001/002 but absent in 003: load_project, find_group_address, get_environment_value, decode_telegram, summarize_recent_activity, inject_event, reset_scenario, simulate_outcome, describe_mutation, read_mutation_log_book, extract_behavior_hints, show_evidence_sources, list_possible_causes. For each: add, merge into another capability, or drop.
3. Capabilities with no home yet: purpose annotation queries (todo 14), scenario/state reset.
4. compare_expected_vs_observed and original-vs-mutated comparison: use case 5 says agent-level only. Remove from core API?
5. `mutation_name` on environment, trace and user-action capabilities, while mutations are parameter-only: is environment/KNX system state per session or per mutation?
6. create_session input: path only (003) or also "uploaded artifact handle" (002)?
7. Placeholder status: 001 says names are "not a locked public API"; decide the freeze point.

Fixed by the use cases (apply as-is): selector = display name, individual address, ETS id or instance path with partial-name matching; ambiguous query returns a set; detail levels SUMMARY/MEDIUM(default)/FULL; unresolvable user action = error; `now` = state after all ordered prior inputs, "unknown" is valid; every state-changing or answer-producing call writes the session log book (plus mutation log book when targeted).
Deliverables: updated 003 (catalogue), 001/002 trimmed to references, traceability table use case -> capability.
Depends on: none (first)
