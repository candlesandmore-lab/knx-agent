# Todo 08: Named parameter-only mutations and log books
Source: use case 5, architecture 001 (7), implementation 002 (Slice 1c)
Goal: named mutations stored as deltas (never full project copies) in the session work-directory; optional mutation name on every capability call (default = knxproj setup); session log book plus mutation-specific log books (mutation actions mirrored in session book); Capabilities: create_mutation, list_mutations, set_parameter_override, describe_mutation, read_session_log_book, read_mutation_log_book.
Answered: parameters only (no groups/topology/names); multiple parallel named mutations per session; deltas persisted in mutation-specific files in the work dir and documented in session-state.yaml; each mutation has its own log book AND actions also go to the session log book; default = unmutated .knxproj setup when no name is given. Comparison is agent-level, not part of this todo.
Open: whether environment/state is per mutation (todo 01).
Depends on: 03, 04
Follow-up from story 03 (catalogue update): log level ERROR was added (always written, severity above INFO); read_session_log_book min_level / --min-level must accept ERROR, INFO, DEBUG, FULL. See docs/implementation/003-proposed-capability-apis.md.
