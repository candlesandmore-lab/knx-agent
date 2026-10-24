# Implementation 003: Capability Catalogue

**Status: reviewed draft.**

This is the ONE authoritative capability catalogue. `docs/implementation/001-solution-concept.md`
and `docs/implementation/002-bootstrap-implementation-plan.md` only point here and must not define
capabilities. Terms follow `docs/methodology/02-terminology-dictionary.md`. Use cases are those in
`docs/methodology/001-use-cases-raw.md` (the inline answers are binding).

Freeze note: the catalogue is frozen only after `development/todos/13-fixtures-and-end-to-end-validation.md`
passes; all later changes require a catalogue update plus a review cycle.

Marking convention: anything labelled **(proposal)** was not decided by the use cases or by the
reviewed decisions of story 01. It is the minimal shape needed to make the entry complete and must be
confirmed during review. Error codes are proposals until the catalogue is frozen. CLI command names and flags, MCP tool names,
SDK method names and the log-level spelling were confirmed by the user. Capability names and the parameter names
`session_label`, `mutation_name`, `detail_level` and `log_level` are decided.

## Purpose and layer model

One callable core API is projected identically onto the Python SDK, the `typer` CLI, the `mcp`
`MCPServer` tool surface, and consumed by the agent layer.

- Shared Python core (the callable core API): below the SDK, above storage/parsing adapters. Owns request validation,
  session and setup resolution, business logic, result assembly, evidence sources and limitation
  notes. Primary pytest target; any Python in this layer lands with direct pytest coverage.
- SDK: the callable core API as stable Python methods and data models; canonical programmable surface.
- CLI (`typer`) and MCP (`mcp` package, `MCPServer`): thin adapters converting arguments or tool inputs into SDK
  requests; no business rules.
- Agent layer: accepts natural language, resolves it into deterministic capability calls, never
  guesses unresolved identifiers or meanings, asks the human to clarify. Out of the core catalogue:
  purpose resolution (the agent resolves purpose strings through the query capabilities; purpose
  annotation data is `development/todos/14-component-purpose-annotation.md`), and original-versus-mutated
  or expected-versus-observed comparison narratives (agent-level only, use case 5).

## Catalogue-wide conventions

### C1. Sessions and `session_label`
- Every session-scoped capability takes `session_label` (CLI `--session <session_label>`, SDK
  parameter `session_label`, MCP tool argument `session_label`). No other name is used for it.
- `create_session` takes a `.knxproj` path (no uploaded artifact handle) and a user-chosen `session_label`
  (required, confirmed). The `session_label` must be unique among all sessions under the session root
  (rule: section "Session service realisation (story 03)"). The session is bound
  to the absolute path of that file.
- Project refresh check: every session-scoped call first compares the bound file with the imported
  metadata and re-reads it when changed; `reimport_system_definition` forces the re-read explicitly.
- There is no reset capability. To restart, create a new session.

### C2. Setups, active setup, `mutation_name`
- The **default setup** is the imported `.knxproj` settings (name `default`). A **mutation** is a
  named, parameter-only delta over it (use case 5), created on top of the current system state (see C5).
- A session has one **active setup** (initially `default`). Capabilities act on the active setup.
  An optional `mutation_name` on a call overrides the target for that call only and never changes the
  active setup. `select_setup` changes the active setup.
- Calls that cannot target a mutation (for example `create_session`) do not take `mutation_name`.
  `read_session_log_book` uses `mutation_name` to choose the mutation log book (see its entry).

### C3. Selectors and ambiguity
- Component selector (`component_selector`): display name (partial-name matching), instance path
  (partial-name matching), individual address (exact), ETS id (exact). Any one of them may be given.
  Selector kind is inferred from the value; optional `selector_kind` (`ANY` default, `NAME`,
  `INSTANCE_PATH`, `INDIVIDUAL_ADDRESS`, `ETS_ID`) disambiguates **(proposal)**.
- Group address selector (`group_address_selector`): group address (exact) or group address name
  (partial) **(proposal)**.
- An ambiguous query returns the set of matches. State-changing calls with an ambiguous selector
  change nothing and return the set with `status: AMBIGUOUS` so the caller can refine **(proposal)**.
  A selector matching nothing is the error `SELECTOR_UNRESOLVED`.
- Flag-to-parameter mapping: the CLI flags `--query`, `--component` and `--sensor` all carry a
  `component_selector` (`--sensor` carries `sensor_selector`, see below); `--group-address` carries
  `group_address_selector`; `--selector-kind` carries `selector_kind`; `--mutation` carries `mutation_name`
  everywhere except `mutation create`, where `--name` carries it; `--session` carries `session_label`;
  `--log-level` is a global CLI option on state-changing and answer-producing commands. Every request
  field below has a CLI flag; none is CLI-excluded.
- `sensor_selector` is a `component_selector` for a sensor component; it supports `selector_kind?` and
  the same `AMBIGUOUS` handling.
- The core never guesses; room or function words absent from the project are not interpreted (agent layer asks).

### C4. Detail levels
`detail_level` is `SUMMARY`, `MEDIUM` (default) or `FULL`, supported on all descriptive calls.
- `SUMMARY`: component identity, topology placement, component-level parameters, purpose annotation when available.
- `MEDIUM`: `SUMMARY` plus setup context needed for most troubleshooting questions.
- `FULL`: everything the solution has, including group addresses, communication objects, enriched
  metadata and purpose annotation when available.
Which concrete fields belong to MEDIUM is deferred to `development/todos/04-knxproj-import-and-setup-inspection.md`.

### C5. Current system state per setup ("now")
- Each setup holds a persistent **current system state** ("now"), persisted after every operation so
  CLI commands can run stateful sequences. It is the state after applying all ordered prior inputs
  (environment values, user actions, trace loads), last input wins per environment element. `unknown`
  is a valid value and a valid answer.
- The environment model holds the primary inputs; the system state holds the simulated result
  (ripple-down component communication).
- A mutation is created on top of the current state (confirmed): its state is seeded from a copy of the
  DEFAULT setup's current environment model and ordered input history at creation time, even when a
  mutation is the active setup. Later changes to the default do not flow into the mutation.
  Mutations of mutations are not supported; `create_mutation` has no base parameter and never copies from another mutation.
- Within one mutation the user applies parameter overrides one by one (`set_parameter_override`
  repeated); each call re-evaluates the mutation's state from its copied history (confirmed).

### C6. Log levels and log books
- `log_level`: `INFO` (default; state-changing calls and answers), `DEBUG` (INFO plus substantial
  results), `FULL` (DEBUG plus low-level flow and debug detail). `ERROR` (added by story 03, user decision
  2026-10-24) marks any issue and is NOT a configurable `log_level` threshold: ERROR entries are always
  written, whatever `log_level` is configured (see "Session service realisation (story 03)").
- Chosen per call: CLI `--log-level`, SDK parameter `log_level`; for MCP at server startup argument
  `--log-level` (confirmed). It is not stored as a per-session setting.
- Every state-changing or answer-producing call writes the session log book, and the mutation log
  book too when a mutation is targeted, subject to the level. Each entry has `entry_id`, `timestamp`,
  `level`, `capability`, `setup`, `summary`, `details`.

### C7. Common response envelope and errors
Every response contains: `setup` (name used), `evidence_sources` (list of `KNXPROJ`, `TRACE`,
`USER_INPUT`, `VENDOR_DOCUMENTATION`, `SIMULATION_RULE`, each with a reference), `limitation_notes`
(list, possibly empty), and `log_book_entry_id` when a log entry was written. `detail_level` is echoed
on descriptive calls. Errors use a code plus message plus optional `details` **(proposal: codes)**.
Common errors: `SESSION_NOT_FOUND`, `PROJECT_FILE_UNREADABLE` (file missing or unreadable; the single code for both), `PROJECT_PARSE_ERROR`,
`MUTATION_NOT_FOUND`, `INVALID_DETAIL_LEVEL`, `INVALID_LOG_LEVEL`, `SELECTOR_UNRESOLVED`, `INVALID_REQUEST` (a required parameter is missing, parameters conflict, or a value is malformed).
Only entry-specific errors are listed per capability below. In requests, `session_label`,
`mutation_name?` and `detail_level?` are listed only where they differ from the convention. `log_level` is a CLI/SDK per-call parameter on every state-changing or answer-producing capability and a startup argument for MCP (see C6); it is not repeated in the per-capability requests and is not an MCP per-call parameter.

## Capabilities (19)

Order: sessions, setup inspection, environment, traces, user actions, questions, mutations, knowledge.
CLI/SDK/MCP names were confirmed by the user (still subject to the freeze condition). SDK shape is `client.<capability>(...)`; MCP tool name equals the capability name.

### 1. `create_session` (UC 1-5, entry point)
- Purpose: create an investigation session bound to a `.knxproj` path.
- Request: `project_path` (required, path only); `session_label` (required, user-chosen, unique among sessions under the session root; non-empty, letters, digits, `-` and `_` only so it is safe as a directory name).
- Response: `session_label` (echo), `work_directory`, `session_state_path`, `source_project_absolute_path`, `project_import_summary` (fields: section "Project import and project graph (story 04)"), `active_setup` (`default`), envelope.
- Evidence/limits: `KNXPROJ`; import warnings for unsupported or ambiguous data are returned as `limitation_notes`.
- Errors: `PROJECT_FILE_UNREADABLE` (missing or unreadable file), `PROJECT_PARSE_ERROR` (not a zip archive, encrypted, not ETS 6, hostile archive, malformed required part; reason in `details.reason`), `SESSION_LABEL_EXISTS`, `SESSION_LABEL_INVALID`; validation order is fixed (see story 03 section). Atomic: a failed create leaves no folder.
- Projection: CLI `knx-agent session create --project <file> --session-label <session_label> [--session-root <dir>] [--log-level <level>]`; SDK `client.create_session(project_path=..., session_label=...)` (client built as `KnxSessionClient(session_root=...)`); MCP `create_session`.

### 2. `reimport_system_definition` (UC 1, freshness)
- Purpose: explicitly re-read the bound `.knxproj` of an existing session.
- Request: `session_label`.
- Response: `project_refresh_status` (`CHANGED`/`UNCHANGED`), `project_import_summary`, `changes` (components and group addresses added/removed/changed; shape in section "Project import and project graph (story 04)"), `invalidated_references` (state entries or mutation deltas pointing to vanished components or group addresses), envelope.
- Evidence/limits: `KNXPROJ`. Retaining or recomputing current system state after a changed project is a **(proposal)**: state is retained, invalidated references are reported as limitation notes.
- Errors: `PROJECT_FILE_UNREADABLE`, `PROJECT_PARSE_ERROR`.
- Projection: CLI `knx-agent session reimport --session <session_label> [--session-root <dir>] [--log-level <level>]`; SDK `client.reimport_system_definition(session_label=...)`; MCP `reimport_system_definition`.

### 3. `describe_session` (UC 1-5, session inspection)
- Purpose: persisted metadata and status of a session.
- Request: `session_label`.
- Response: `session_label`, `work_directory`, `source_project_absolute_path`, `project_refresh`, `project_import` (story 04: `imported_at`, `fingerprint`, `graph_file`, `project_import_summary`), `active_setup`, `setups` (default plus mutations, each with current system state summary), `trace_artifacts`, `log_book_references`, envelope.
- Errors: common only (`SESSION_NOT_FOUND`; `PROJECT_FILE_UNREADABLE` and `PROJECT_PARSE_ERROR` from the automatic refresh check). Read-only: writes no log book entry (no `log_book_entry_id`).
- Projection: CLI `knx-agent session describe --session <session_label> [--session-root <dir>]`; SDK `client.describe_session(session_label=...)`; MCP `describe_session`.

### 4. `select_setup` (UC 5)
- Purpose: switch the active setup.
- Request: `session_label`, `mutation_name?` (omitted selects `default`).
- Response: `active_setup`, `current_system_state_summary`, envelope.
- Errors: `MUTATION_NOT_FOUND`.
- Logging: state-changing, writes session log book (and mutation log book if selected).
- Projection: CLI `knx-agent session select-setup --session <session_label> [--mutation <name>]`; SDK `client.select_setup(session_label=..., mutation_name=...)`; MCP `select_setup`.

### 5. `read_session_log_book` (UC 3, 4)
- Purpose: read the session history for reasoning and audit; replaces separate recent-activity and mutation log reads.
- Request: `session_label`, `mutation_name?` (when given reads that mutation log book, otherwise the overall session log book), `min_level?` (filter by log level; values `ERROR`, `INFO`, `DEBUG`, `FULL`, severity order ERROR highest; catalogue update by story 03, ERROR is new), `limit?`, `since_entry_id?`.
- Response: `entries`, `truncated`, envelope. Reading does not itself write the log book.
- Evidence/limits: entries below the level configured when they were written are absent; note this in `limitation_notes`.
- Errors: `MUTATION_NOT_FOUND`.
- Projection: CLI `knx-agent session log-book --session <session_label> [--mutation <name>] [--min-level ERROR|INFO|DEBUG|FULL] [--limit <n>] [--since-entry-id <id>]`; SDK `client.read_session_log_book(...)`; MCP `read_session_log_book`.

### 6. `list_components` (UC 1.1, 1.2)
- Purpose: query components by (partial) selector, or list all.
- Request: `component_selector?` (omitted = broad listing), `selector_kind?`, `detail_level?`, `mutation_name?`. No `purpose` parameter (see agent layer note).
- Response: `matches`, `match_count`, `ambiguous` (true when more than one), `detail_level`, envelope. `purpose_annotation` appears per match when available (todo 14).
- Evidence/limits: `KNXPROJ`; mutation delta values flagged when a mutation is targeted.
- Errors: none beyond common (no match returns an empty set for a listing; `SELECTOR_UNRESOLVED` is not raised here) **(proposal)**.
- Projection: CLI `knx-agent setup list-components --session <session_label> [--query <text>] [--selector-kind <kind>] [--detail-level ...] [--mutation <name>]`; SDK `client.list_components(...)`; MCP `list_components`.

### 7. `describe_component` (UC 1.3)
- Purpose: configuration and topology of components selected by name, instance path, address or ETS id.
- Request: `component_selector`, `selector_kind?`, `detail_level?`, `mutation_name?`.
- Response: `components` (set; one element when unambiguous), per component: `identity`, `topology`, `component_parameters`, plus at `FULL`: `group_addresses`, `communication_objects`, `purpose_annotation` when available; `ambiguous`, envelope.
- Evidence/limits: `KNXPROJ` (and `VENDOR_DOCUMENTATION` at FULL if enriched data is available); mutated parameter values are marked.
- Errors: `SELECTOR_UNRESOLVED`.
- Projection: CLI `knx-agent setup describe-component --session <session_label> --component <selector> [--selector-kind <kind>] [--detail-level ...] [--mutation <name>]`; SDK `client.describe_component(...)`; MCP `describe_component`.

### 8. `summarize_topology` (UC 1.2)
- Purpose: summarize areas, lines, rooms if derivable, and component distribution.
- Request: `detail_level?`, `mutation_name?`.
- Response: `topology_summary`, `component_counts`, `purpose_summary` when annotations are available, envelope.
- Evidence/limits: `KNXPROJ`; rooms only where the project encodes them.
- Errors: common only.
- Projection: CLI `knx-agent setup summarize-topology --session <session_label> [--detail-level ...] [--mutation <name>]`; SDK `client.summarize_topology(...)`; MCP `summarize_topology`.

### 9. `trace_group_flow` (UC 2.3)
- Purpose: participants and propagation path of a group address or communication object; also finds group addresses by name.
- Request: `group_address_selector?`, `communication_object_ref?` (one of the two required), `mutation_name?`, `detail_level?`.
- Response: `group_addresses` (matches, set when ambiguous), per match `participants`, `propagation_path`, `unresolved_links`, `current_value` (from current system state, may be `unknown`), envelope.
- Evidence/limits: `KNXPROJ`, `SIMULATION_RULE` for current value; unresolved links noted.
- Errors: `SELECTOR_UNRESOLVED`, `INVALID_REQUEST` (neither or both selectors given).
- Projection: CLI `knx-agent setup trace-group-flow --session <session_label> [--group-address <selector> | --object-ref <ref>] [--detail-level ...] [--mutation <name>]`; SDK `client.trace_group_flow(...)`; MCP `trace_group_flow`.

### 10. `list_environment_inputs` (UC 2.1)
- Purpose: list sensor-oriented environment inputs that drive the system, with current values.
- Request: `component_selector?` (sensor by name etc.; omitted = all inputs), `selector_kind?`, `detail_level?`, `mutation_name?`. No `purpose` parameter.
- Response: `inputs` (per input: sensor component identity, communication object, KNX datapoint type, `current_value` or `unknown`, `value_source` `USER_INPUT`/`TRACE`/`NONE`), envelope.
- Evidence/limits: `KNXPROJ` for inputs; `USER_INPUT`/`TRACE` for values. The project holds no sensor values.
- Errors: common only.
- Projection: CLI `knx-agent environment list-inputs --session <session_label> [--query <text>] [--selector-kind <kind>] [--detail-level ...] [--mutation <name>]`; SDK `client.list_environment_inputs(...)`; MCP `list_environment_inputs`.

### 11. `set_environment_value` (UC 2.2, 2.3)
- Purpose: provide a simulation value for a sensor; updates the environment model and ripples down into the current system state.
- Request: `sensor_selector` (component selector), `selector_kind?`, `communication_object?` (when the sensor has several), `value`, `mutation_name?`, `reason?`.
- Response: `status` (`APPLIED`/`AMBIGUOUS`), `accepted_value`, `normalized_knx_value` (KNX datatype from ETS), `previous_value`, `state_update_summary` (components that react and group telegrams emitted, or none), envelope.
- Evidence/limits: `USER_INPUT`, `KNXPROJ`, `SIMULATION_RULE`; partial component behavior coverage is a limitation note. Last come wins over earlier trace or user values.
- Errors: `SELECTOR_UNRESOLVED`, `VALUE_INVALID_FOR_DATAPOINT`, `NOT_AN_ENVIRONMENT_INPUT`.
- Projection: CLI `knx-agent environment set-value --session <session_label> --sensor <selector> [--selector-kind <kind>] [--communication-object <ref>] --value <value> [--reason <text>] [--mutation <name>]`; SDK `client.set_environment_value(...)`; MCP `set_environment_value`.

### 12. `load_bus_trace` (UC 2.3, 3.2; includes environment inference)
- Purpose: load a bus trace into the session, update the setup's environment and system state from it, and report what was inferred with evidence (this merges the former separate inference capability).
- Request: `trace_path`, `trace_format?` (format indicator placeholder; the format decision is `development/todos/05-bus-trace-ingestion.md`), `mutation_name?`.
- Response: `trace_id`, `packet_count`, `decode_warnings`, `observed_address_summary`, `inferred_environment_values` (value, target sensor, `confidence`, `evidence_packets`), `candidate_user_actions` (with evidence), `state_update_summary`, envelope.
- Evidence/limits: `TRACE`, `KNXPROJ`; inference quality depends on address resolution and datapoint typing; unresolvable packets are listed in `decode_warnings`.
- Errors: `TRACE_FILE_UNREADABLE`, `TRACE_FORMAT_UNSUPPORTED`.
- Projection: CLI `knx-agent trace load --session <session_label> --path <file> [--format <name>] [--mutation <name>]`; SDK `client.load_bus_trace(...)`; MCP `load_bus_trace`.

### 13. `resolve_user_action_candidates` (UC 3.1, 3.3)
- Purpose: resolve a component (and control or gesture) into candidate KNX-level actions (group address, datapoint, value); natural language is handled by the agent layer.
- Request: `component_selector`, `selector_kind?`, `control?`, `gesture?` (only gestures configured in the project, such as long press or dimming), `mutation_name?` Structured request instead of free text (confirmed), since language interpretation is agent-layer.
- Response: `candidates` (each with `action_reference`, group address, datapoint type, value, gesture), `ambiguous`, envelope.
- Evidence/limits: `KNXPROJ`; unsupported gestures are limitation notes.
- Errors: `USER_ACTION_UNRESOLVABLE` (control cannot be resolved from the project graph), `SELECTOR_UNRESOLVED`.
- Projection: CLI `knx-agent action resolve --session <session_label> --component <selector> [--selector-kind <kind>] [--control <name>] [--gesture <name>] [--mutation <name>]`; SDK `client.resolve_user_action_candidates(...)`; MCP `resolve_user_action_candidates`.

### 14. `inject_user_action` (UC 3.1, 3.2, 3.3)
- Purpose: apply a resolved user action (such as a button press) and update the current system state.
- Request: `action_reference`, `mutation_name?`.
- Response: `resolved_knx_activity`, `state_update_summary`, envelope.
- Evidence/limits: `USER_INPUT`, `KNXPROJ`, `SIMULATION_RULE`.
- Errors: `USER_ACTION_UNRESOLVABLE`, `ACTION_REFERENCE_UNKNOWN`.
- Projection: CLI `knx-agent action inject --session <session_label> --action <ref> [--mutation <name>]`; SDK `client.inject_user_action(...)`; MCP `inject_user_action`.

### 15. `answer_activity_question` (UC 4.1, 4.2, 4.3, 5.2)
- Purpose: answer `should`, `why`, `why not`, `what changed`, `what input caused this` questions about the current system state ("now"). Sole question capability.
- Request: `question` (text), `mutation_name?`.
- Response: `answer_status` (`ANSWERED`/`UNKNOWN`), `answer`, `confidence`, `unresolved_assumptions`, `needed_inputs` (inputs the user must provide when `UNKNOWN`), envelope with `evidence_sources` mandatory.
- Evidence/limits: `evidence_sources` and `unresolved_assumptions` are required content; the question-interpretation mechanism is defined in `development/todos/07-expectation-engine-and-activity-questions.md`. Referents not present in the project are not guessed.
- Errors: `QUESTION_NOT_INTERPRETABLE`.
- Projection: CLI `knx-agent activity ask --session <session_label> --question <text> [--mutation <name>]`; SDK `client.answer_activity_question(...)`; MCP `answer_activity_question`.

### 16. `create_mutation` (UC 5.1, 5.3)
- Purpose: create a named parameter-only mutation (delta) on top of the current state.
- Request: `mutation_name` (unique), `description?`.
- Response: `mutation_name`, `mutation_delta_path`, `mutation_log_book_path`, `seeded_state_summary`, envelope. Does not change the active setup.
- Evidence/limits (confirmed): always seeded from the default setup's current environment model and ordered input history at creation time, even if a mutation is the active setup; there is no base parameter and mutations of mutations are not supported. Later default changes do not flow in.
- Errors: `MUTATION_BASE_NOT_SUPPORTED` (reserved for adapter-level rejection of an unrecognised base or from-mutation argument; the core request has no base parameter), `MUTATION_ALREADY_EXISTS`, `MUTATION_NAME_INVALID` (including `default`).
- Projection: CLI `knx-agent mutation create --session <session_label> --name <name> [--description <text>]`; SDK `client.create_mutation(...)`; MCP `create_mutation`.

### 17. `set_parameter_override` (UC 5.1)
- Purpose: set a component parameter in a mutation (parameters only; no group, topology or name changes).
- Request: `component_selector`, `selector_kind?`, `parameter_name`, `value`, `mutation_name?` (omitted targets the active setup; if the resulting target is `default` the call fails with `DEFAULT_SETUP_IMMUTABLE`).
- Response: `status` (`APPLIED`/`AMBIGUOUS`), `updated_delta`, `affected_component`, `state_update_summary`, envelope.
- Evidence/limits (confirmed): may be called repeatedly on the same mutation; each call re-evaluates the mutation's state.
- Errors: `DEFAULT_SETUP_IMMUTABLE`, `MUTATION_NOT_FOUND`, `SELECTOR_UNRESOLVED`, `PARAMETER_UNKNOWN`, `VALUE_INVALID_FOR_PARAMETER`.
- Projection: CLI `knx-agent mutation set-parameter --session <session_label> [--mutation <name>] --component <selector> [--selector-kind <kind>] --parameter <name> --value <value>`; SDK `client.set_parameter_override(...)`; MCP `set_parameter_override`.

### 18. `list_mutations` (UC 5.3)
- Purpose: list mutations of a session, including their deltas (details by `detail_level`).
- Request: `detail_level?`.
- Response: `mutations` (name, description, creation time, `active` flag, delta at MEDIUM/FULL, log book reference, state summary), envelope.
- Errors: common only.
- Projection: CLI `knx-agent mutation list --session <session_label> [--detail-level ...]`; SDK `client.list_mutations(...)`; MCP `list_mutations`.

### 19. `fetch_component_details` (UC 1.3; also component behavior hints)
- Purpose: fetch vendor or catalogue information to enrich a component, including behavior hints.
- Request: `component_selector?`, `manufacturer?`, `product_code?` (one source of identity required), `mutation_name` not applicable. Not setup-scoped, so the envelope `setup` field is omitted.
- Response: `normalized_component_metadata`, `purpose_annotation` when available, `behavior_hints`, envelope with `VENDOR_DOCUMENTATION` references.
- Evidence/limits: vendor sources can be inconsistent; results carry provenance and may be cached (todo 09).
- Errors: `SELECTOR_UNRESOLVED`, `ENRICHMENT_SOURCE_UNAVAILABLE`, `INVALID_REQUEST`.
- Projection: CLI `knx-agent knowledge fetch-component-details --session <session_label> [--component <selector>] [--manufacturer <name>] [--product-code <code>]`; SDK `client.fetch_component_details(...)`; MCP `fetch_component_details`.

## Session service realisation (story 03)

Realises capabilities 1-3 and the C1/C6 rules on disk. Decisions of 2026-10-24; error codes remain
proposals until the catalogue freeze.

### Session root and work-directory
- The session root is the folder holding all work-directories. Default `./.knx-agent/sessions`
  (relative to the current working directory, created on demand).
- It is set ONLY by CLI option `--session-root <dir>` (on every `session` subcommand), the MCP server
  startup argument `--session-root <dir>`, and the SDK parameter `session_root=` on `KnxSessionClient`.
  No environment variable is read. The MCP server is started with the new console script `knx-agent-mcp`
  (user decision 2026-10-24), e.g. `knx-agent-mcp --session-root <dir> --log-level DEBUG`.
- Work-directory of a session: `<session root>/<session_label>`, containing `session-state.yaml` and
  `session-log-book.jsonl`. `describe_session` and `create_session` return it as an absolute path.
- `session_label`: non-empty, letters, digits, `-` and `_` only. On session-scoped calls other than
  `create_session`, a blank or non-string label is `INVALID_REQUEST` (story 02 behaviour kept), a label
  with other characters can never exist and yields `SESSION_NOT_FOUND`; a missing folder is `SESSION_NOT_FOUND`.
- There is no `session_id` and no implicit active session; "active" refers to the active setup only.

### Error order of create_session
1. `SESSION_LABEL_INVALID`  2. `PROJECT_FILE_UNREADABLE`  3. `PROJECT_PARSE_ERROR`  4. `SESSION_LABEL_EXISTS`.
For existing sessions: label check, `SESSION_NOT_FOUND`, then the refresh check (`PROJECT_FILE_UNREADABLE`, `PROJECT_PARSE_ERROR`).
The `.knxproj` guard only verifies that the file is readable and a valid zip archive; content is not
parsed (todo 04). Superseded by story 04: the guard step becomes the full import; same order, and
`PROJECT_PARSE_ERROR` now also covers the reasons listed in "Project import and project graph (story 04)".

### Atomicity
- `create_session` builds the work-directory in a temporary sibling folder (`<session root>/.<session_label>.creating-<token>`;
  labels cannot start with `.`), then renames it into place; any failure removes the temporary folder, so a
  failed create never blocks the label. A rename that loses a race maps to `SESSION_LABEL_EXISTS`.
- `session-state.yaml` is always written to a temporary file in the same folder and then renamed over the
  old file; a failed re-import leaves the previous state intact. Single-writer assumption: one process
  per session at a time (documented in README.md).

### session-state.yaml field list
`session_label`; `created_at` (UTC ISO 8601); `work_directory` (absolute); `source_project_absolute_path`;
`project_import`: `path`, `mtime` (integer nanoseconds), `size` (bytes), `imported_at`,
`project_import_summary` (file name, archive entry count, `limitation_note`: ".knxproj content import is
not implemented yet"), `fingerprint` (always `null` until todo 04); `project_refresh`: `last_status`
(`CHANGED`/`UNCHANGED`), `last_reimported_at`, `reimport_count` (incremented by every re-import, automatic or
explicit `reimport_system_definition` even when the result is `UNCHANGED`; never by an unchanged automatic
check, so that check is idempotent); `active_setup` (`default`); `trace_artifacts: []`;
`scenario_state: []`; `mutations: []`; `log_book_references` (list, here `session-log-book.jsonl`);
`mutation_log_book_references` (empty mapping).
Story 04 replaces the `project_import` content (summary, fingerprint, graph reference, warnings): see
"Project import and project graph (story 04)".

### Project refresh check
Run by the application layer before every public session-scoped operation (CLI and MCP get it through
the SDK). It compares existence, `mtime` and `size` with `project_import`. Equal: no write, operation
proceeds. Different: automatic re-import (validate archive, update `project_import` and `project_refresh`
atomically), then the operation proceeds. Missing or unreadable: `PROJECT_FILE_UNREADABLE`, state unchanged.
`reimport_system_definition` forces the re-read and reports `CHANGED` (metadata differed) or `UNCHANGED`;
it always rewrites `project_import.imported_at`. `changes` and `invalidated_references` are empty until
todo 04. Known limitation: a content change that keeps `mtime` and `size` is not detected by the automatic
check (manual `reimport_system_definition`; fingerprint in todo 04).
Superseded by story 04: the check also compares the SHA-256 fingerprint, closing this limitation; `changes`
and `invalidated_references` are real; `project_import_summary` and `fingerprint` have the story 04 shape
(see the next section). Sessions created by story 03 code are not migrated (recreate them).

### KNX session log book format
Append-only JSON Lines file `session-log-book.jsonl` in the work-directory, one JSON object per line with
`entry_id` (integer, starts at 1, increments by 1), `timestamp` (UTC ISO 8601), `level` (`ERROR`/`INFO`/`DEBUG`/`FULL`),
`capability`, `setup`, `summary`, `details` (object). `ERROR` entries are always written, whatever
`log_level` is configured. Other entries are written only if their level is at or below the call's
`log_level` (INFO < DEBUG < FULL; `log_level` itself accepts only INFO, DEBUG, FULL). Severity order for
filtering is ERROR (highest), INFO, DEBUG, FULL. The file is created at session creation. Reading is
`read_session_log_book` (todo 08).

Catalogue update: adding `ERROR` changes the level list INFO/DEBUG/FULL used by C6 and by the
`read_session_log_book` `min_level`/`--min-level` filter; todo 08 must implement the four-value filter
(follow-up `development/todos/08-mutations-and-logbooks.md`).

### Error logging (user decision 2026-10-24: "any issue should be logged as ERROR, use the python logging framework")
- Any issue is an ERROR: failed refresh check, missing or unreadable project file, failed re-import, and
  every raised catalogue error (`KnxAgentError`).
- Each ERROR goes to the Python standard `logging` module (logger `knx_agent` and child loggers such as
  `knx_agent.application`; no custom logging code beyond configuring a handler in the CLI and MCP entry
  points) AND, when a session exists (work-directory present), to the KNX session log book as level ERROR.
  Errors before a session exists (for example a failed `create_session`, `SESSION_NOT_FOUND`) are logged to
  the Python logger only.
- ERROR is written regardless of `log_level`.

### Log point table (story 03)
| Log point | Capability | Level | Summary / details |
| --- | --- | --- | --- |
| Session created | `create_session` | INFO | label, project path, work-directory |
| Explicit re-import done | `reimport_system_definition` | INFO | status CHANGED/UNCHANGED, old and new mtime/size |
| Refresh check, unchanged | any session-scoped call | DEBUG | compared mtime/size |
| Refresh check, changed, automatic re-import done | any session-scoped call | INFO | old and new mtime/size |
| Any failure (refresh check failed, file missing/unreadable/not a zip, failed re-import, any raised catalogue error) | the calling capability | ERROR | error code, message (state unchanged); always written |
| `describe_session` success | `describe_session` | none | read-only, no entry |

With the default `INFO` the log book holds lifecycle events and all errors; unchanged refresh checks appear
only at `DEBUG`. `capability` of a refresh-check entry is the calling capability. A failed `create_session`
writes no log book entry (no folder survives) but still logs the ERROR to the Python logger. Entries describing an operation are written after the state write; the
response envelope carries `log_book_entry_id` (integer) of the entry written for that call, if any; for `describe_session` it is set
only when its refresh check wrote an entry. Implementation notes (story 03): `create_session` writes its INFO
entry into the temporary folder just before the atomic rename (it stays the first entry and keeps create fully
atomic); `describe_session` also accepts `--log-level` / `log_level` (default `INFO`) so the DEBUG entry of an
unchanged refresh check can be recorded; an explicit `reimport_system_definition` runs the forced re-read
instead of the automatic check (no second refresh entry); a session folder with a missing or corrupt
`session-state.yaml` is `SESSION_NOT_FOUND` with the reason in `details`; any non-catalogue exception is also
logged at ERROR and re-raised unchanged; the CLI prints the Python-logging ERROR line to stderr followed by the
`ErrorInfo` JSON as the last line; `describe_session` returns `setups` as `[{name: default,
current_system_state_summary: unknown}]` until todo 06.

## Project import and project graph (story 04)

Realises capabilities 1-3 with a real `.knxproj` import. Decisions of 2026-10-24 (user: ETS 6 Professional
only, own parser; architect: the decisions marked "architect" below). No capability, CLI command or MCP
tool is added. Error codes remain proposals until the catalogue freeze. The query capabilities
(`summarize_topology`, `list_components`, `describe_component`, `trace_group_flow`) are todo 15 and read the
persisted project graph defined here.

### Decisions (options and rationale)

| Decision | Options | Chosen | Rationale |
| --- | --- | --- | --- |
| Internal structure (arch) | arch-a layered importer + graph model + derivation; arch-b flat tables | arch-a (user/story, 2026-10-24) | Source/derived separation and topology traversal. |
| XML library (impl-a vs impl-b) | lxml iterparse; stdlib `xml.etree.ElementTree` iterparse | impl-b (stdlib) by default, binding switch rule below (architect) | Planning measurement (below) is 1 to 2 orders of magnitude inside the 30 s target; no new native dependency. lxml could not be installed during planning, so the first implementation task re-measures with the real workload and applies the rule. |
| Stable IDs (impl-c) | ETS `Id` with structural fallback | impl-c (story) | See "Stable ID rules". |
| Persistence (impl-d) | YAML; JSON | JSON, file `project-graph.json`, atomic write (architect) | Large and machine-read; PyYAML dumping of ~10k nodes is slow and a JSON file is still inspectable. `session-state.yaml` stays YAML-first for session metadata. |
| Fingerprint timing | hash only on mtime/size change; hash on every check | hash on every refresh check after the cheap comparisons agree (architect) | The point of the fingerprint is to catch changes that keep mtime and size, so it cannot be gated by them. SHA-256 of 7.5 MB takes about 10 to 30 ms. |
| Import warnings and the ERROR rule | warnings are issues (ERROR); warnings are not issues | warnings are NOT issues (architect) | The story 03 rule "any issue is ERROR" covers failures of an operation (raised catalogue errors). A warning describes the project, not a failed operation. Details: "Log points". |
| DTD, entity or unsupported encoding in an XML part | fail the import for every part; fail for required parts and skip optional parts with a warning | required parts (`project.xml`, `0.xml`): `PROJECT_PARSE_ERROR`; optional parts: skip the part with warning `OPTIONAL_PART_UNREADABLE` (user decision, 2026-10-24) | The importer needs the required parts to build any graph; an optional part only enriches it. A rejected optional part is never parsed and no partial result of it is used (the guard rejects before the parser sees the document). |

### impl-a vs impl-b: benchmark rule (binding)

Planning measurement (architect, 2026-10-24, Python 3.12, macOS, stdlib `ElementTree.iterparse`, parse-only
pass without graph building, no lxml): `tests/lifedata/20261010-EFH-Armbruster.knxproj`, 0.xml, knx_master.xml
and all 13 application program XMLs (50 MB largest, 0.69 s): total 1.06 s, peak RSS 27 MiB. This is not the
final number because graph building, derivation, hashing and persistence are not included.

Binding rule: the FIRST implementation task (T1 of the task plan) is a benchmark. It measures the
ElementTree streaming read of the referenced application programs and the required parts of the sample
and records the result in this section ("Measured results" below). The default is impl-b. Switch to impl-a (lxml) only if
the measured end-to-end import of the sample (cold interpreter, archive open to graph persisted) exceeds
30 s. The task plan re-checks the rule once more on the finished import (T12 QA run); a breach at that point
adds a follow-up task to switch to lxml (record the license in README.md and todo 12; BSD-3-Clause), it does
not block the story if the 120 s test bound still holds. No lxml dependency is added while impl-b stands.

Measured results (T1 filled; T12 fills the end-to-end lines): preliminary parse-only 1.06 s / 27 MiB (above).

T1 benchmark (`scripts/benchmark_knxproj_parse.py`, 2026-10-24, macOS, Python 3.12, stdlib `ElementTree.iterparse`,
3 cold child processes, no archive extraction): total wall time 0.951 / 0.921 / 0.940 s, median 0.94 s; peak RSS
32.5 / 31.6 / 32.0 MiB. Per-file times of the median run: SHA-256 of the 7.5 MB file 0.004 s, `project.xml` 0.001 s,
`0.xml` 0.014 s, `knx_master.xml` 0.026 s, three `Hardware.xml` under 0.002 s together, the 12 referenced application
programs 0.000 to 0.097 s each plus the 50 MB program `M-0083_A-008A-22-33A1.xml` 0.574 s (the benchmark keeps only
referenced definitions and clears translation and dynamic subtrees). The workload is 28 components, 12 referenced
programs read, 695 group addresses, 692 communication object references, 3132 parameter references.
Decision: impl-b (stdlib ElementTree) stands; the measured parse is about 30 times inside the 30 s target, so lxml
is not needed and was not installed or measured. Re-check of the rule on the finished import: T12/T14.
Parser check (T6, same machine, own parser building the full source facts of the sample plus derivation, in one
process): 1.02 s parse, derivation under 0.01 s, peak RSS 65 MiB (including interpreter, pydantic and package
imports).
T12 end-to-end measurement (`scripts/measure_sample_import.py`, `create_session` on the sample through the SDK in a
cold process: fingerprint, archive guard, parser, derivation, summary, `project-graph.json` and `session-state.yaml`
written, log book; 3 runs through the MCP python_execution tool): 1.185 / 1.182 / 1.180 s, median 1.18 s (target
30 s, test bound 120 s); peak RSS 83.4 / 86.0 / 83.1 MiB (measured once, documented, not asserted; includes the
interpreter, pydantic and the package imports); `project-graph.json` 3,202,162 bytes (3.2 MB), indented with
1 space; the 20 MB switch to compact JSON is not needed (`JSON_INDENT` stays 1). The pytest run measured 1.23 s for
`import_project` alone and 1.14 s for `create_session`. The impl-a/impl-b rule is re-checked on the finished import:
1.18 s is far below 30 s, impl-b (stdlib ElementTree) stands, no lxml dependency. Hash cost of the refresh check
(SHA-256 of the 7.5 MB file): 0.004 s (T1 per-file time).

### Archive and XML limits (hostile archive defence)

Applied by `application/knxproj_archive.py` before any entry is read, and while reading. Never extract files
to disk (all reads via `zipfile.ZipFile.open` into memory or an incremental parser).

| Limit | Value | Reason code in `details.reason` |
| --- | --- | --- |
| Entries in archive | at most 5000 | `ARCHIVE_TOO_MANY_ENTRIES` |
| Uncompressed size of ONE entry | at most 256 MiB (268435456 bytes) | `ARCHIVE_ENTRY_TOO_LARGE` |
| Sum of uncompressed sizes | at most 1 GiB (1073741824 bytes) | `ARCHIVE_TOTAL_TOO_LARGE` |
| Compression ratio of ONE entry = uncompressed size / compressed size | at most 200 (an entry with uncompressed size greater than 0 and compressed size 0 breaches it) | `ARCHIVE_COMPRESSION_RATIO` |
| Duplicate entry names | rejected | `ARCHIVE_DUPLICATE_ENTRY` |
| Encrypted entries (general-purpose flag bit 0) | rejected, nothing is read | `ENCRYPTED` |

- "Exceeds" means strictly greater than the limit. Header checks (from the central directory) run for all
  entries first; `zipfile` never yields more bytes than the declared uncompressed size, so the declared size is
  a hard read cap. Limits are an `ArchiveLimits` value with these defaults; tests lower them instead of
  building gigabyte archives, plus one test asserts the default constants.
- Entry names are never used as file system paths (no extraction), so path traversal names are harmless; they
  are looked up by exact string only.
- XML rules for every parsed document (project.xml, 0.xml, knx_master.xml, Catalog/Hardware XML, application
  programs): no DTD, no entity declaration, no external entity, no network access, no `huge_tree`. With stdlib
  ElementTree the importer feeds the parser through a guard that scans the byte stream (chunk-overlap safe) for
  `<!DOCTYPE` and `<!ENTITY` and rejects the document with `XML_DTD_FORBIDDEN` or `XML_ENTITY_FORBIDDEN`;
  documents that are not UTF-8 (a UTF-16 byte-order mark or an encoding declaration other than UTF-8) are rejected
  with `XML_ENCODING_UNSUPPORTED` because the ASCII scan would not see them (ETS writes UTF-8 with BOM). The
  expat entity-amplification protection of Python 3.12 is defence in depth, not the control. If impl-a (lxml)
  applies: `XMLParser(resolve_entities=False, no_network=True, huge_tree=False, load_dtd=False)` plus the same
  rejection. Consequence of a rejection (user decision 2026-10-24): in a REQUIRED part (`project.xml`, `0.xml`) it is
  `PROJECT_PARSE_ERROR` with `details.reason` `XML_DTD_FORBIDDEN`, `XML_ENTITY_FORBIDDEN` or `XML_ENCODING_UNSUPPORTED`;
  in an OPTIONAL part (catalog, `Hardware.xml`, application program XMLs, `knx_master.xml`; UserFiles, AddinData
  and BinaryData are never opened) the part is skipped, the import continues, and the warning
  `OPTIONAL_PART_UNREADABLE` is added with the same reason in the message (`reason: XML_DTD_FORBIDDEN` etc.). The
  guard decides before parsing, so the part is never parsed and none of its content is used; facts depending on it
  stay unresolved and are reported by the other warning codes (for example the affected components' objects get
  `COMOBJECT_DEFINITION_UNRESOLVED`).
- Required parts (failure = `PROJECT_PARSE_ERROR`): the project folder's `project.xml` and `0.xml`. The project
  folder is the one top-level folder matching `P-<hex digits>` that contains `project.xml`
  (`PROJECT_FOLDER_NOT_FOUND` when none or more than one). Missing part: `REQUIRED_PART_MISSING`; not
  well-formed: `REQUIRED_PART_MALFORMED`.
- Normative part lists. REQUIRED parts, exactly two: `<project folder>/project.xml` and `<project folder>/0.xml`.
  OPTIONAL parts, everything else that the import may read: `<M>/Hardware.xml`, `<M>/Catalog.xml`, application
  program XMLs `<M>/<application program id>.xml`, `knx_master.xml`; the entries under `UserFiles`, `AddinData`,
  `BinaryData`, `Baggages`, the signature/certificate/`.validation` entries and all other entries are optional
  and never opened. Failure classes: a required part failure (missing, malformed, DTD/entity/encoding) is
  `PROJECT_PARSE_ERROR`. For an optional part, `OPTIONAL_PART_MISSING` = absent from the archive;
  `OPTIONAL_PART_UNREADABLE` = present but rejected or malformed; its message AND the warning's structured
  reason text carry the underlying reason: `XML_DTD_FORBIDDEN`, `XML_ENTITY_FORBIDDEN`,
  `XML_ENCODING_UNSUPPORTED`, `XML_MALFORMED` or `ENTRY_READ_ERROR` (the message form is
  `Optional part skipped (reason: <REASON>)`). ARCHIVE-LEVEL guard failures (too many entries, entry or total
  size, compression ratio, duplicate entry names, encrypted entry, not a zip archive) stay `PROJECT_PARSE_ERROR`
  even when they concern only an optional part (they are checked on the whole archive before any part is read).
- Optional parts (failure = warning, the import continues): manufacturer catalog folders `M-<hex>/`
  (`Catalog.xml`, `Hardware.xml`, application program XMLs), `knx_master.xml`, `UserFiles`, `AddinData`,
  `BinaryData`, `*.signature`, `*.certificate`, `.validation`. Only `Hardware.xml`, the application program XMLs
  of components that exist, and `knx_master.xml` are read; the other optional parts are never opened. Facts that
  depend on an unreadable optional part (communication object and parameter definitions, datapoint type
  verification) are reported as limitation notes via the warnings below. The ETS signature and certificate are
  NOT verified (documented limitation).
- `PROJECT_PARSE_ERROR` `details`: `reason` (one of: `NOT_A_ZIP`, `ENCRYPTED`, `ARCHIVE_TOO_MANY_ENTRIES`,
  `ARCHIVE_ENTRY_TOO_LARGE`, `ARCHIVE_TOTAL_TOO_LARGE`, `ARCHIVE_COMPRESSION_RATIO`, `ARCHIVE_DUPLICATE_ENTRY`,
  `PROJECT_FOLDER_NOT_FOUND`, `REQUIRED_PART_MISSING`, `REQUIRED_PART_MALFORMED`, `NOT_ETS_PROJECT`,
  `UNSUPPORTED_NAMESPACE`, `UNSUPPORTED_TOOL_VERSION`, `XML_DTD_FORBIDDEN`, `XML_ENTITY_FORBIDDEN`,
  `XML_ENCODING_UNSUPPORTED`), `path` (the `.knxproj`), and where relevant `entry` (zip entry), `limit`, `actual`,
  `namespace`, `tool_version`. The message names the reason in words. `NOT_ETS_PROJECT`: root element is not `KNX`
  or the project element/`Id` is missing. Support check: root namespace must equal
  `http://knx.org/xml/project/22` (else `UNSUPPORTED_NAMESPACE`) and the root `ToolVersion` major (digits before
  the first `.`) must be 6 (else `UNSUPPORTED_TOOL_VERSION`; a missing or unparsable `ToolVersion` is also
  `UNSUPPORTED_TOOL_VERSION`). A failure of any kind leaves the previous state and graph untouched.
- Only `0.xml` (installation id `<project id>-0`) is imported. Other `<n>.xml` installation files in the
  project folder are ignored with warning `ADDITIONAL_INSTALLATION_IGNORED`.

### Project graph model

Module placement: pure model in `domain/project_graph.py` (Pydantic v2 models, no I/O); parser in
`application/knxproj_parser.py`; derivation in `domain/derivation.py`. The graph has two separate parts and one
list of warnings:

1. `source_facts`: nodes and relations imported without interpretation beyond parsing and normalization.
2. `derived_facts`: facts computed from source facts (component typing, reverse indexes). Recomputable; nothing
   in `source_facts` depends on them, and no derived value is ever written into a source node.
3. `warnings`: import warnings (contract below).

Common node fields (source facts): `id` (stable ID), `kind`, `id_origin` (`ETS_ID`, `ETS_COMPOSITE`,
`STRUCTURAL_FALLBACK`), and provenance: `source_part` (zip entry name), `source_locator` (the XML element
tag with its ETS `Id`/`RefId` or, without one, its structural path, for example
`DeviceInstance[@Id=P-051B-0_DI-6]`), and `fact_origin` (`PROJECT` for the project folder, `CATALOG` for
manufacturer catalog and application program facts, `MASTER` for `knx_master.xml`).

Node kinds and fields (names are the persisted JSON field names; `null` when the attribute is absent):

| Kind | Source of the node | Fields beyond the common fields |
| --- | --- | --- |
| `installation` | `0.xml` Installation, project.xml ProjectInformation | `project_id`, `project_name`, `group_address_style` (`ThreeLevel`, `TwoLevel` or `Free`), `default_line_id`, `last_modified`, `completion_status`, `ets_tool_version`, `created_by`, `schema_namespace` |
| `area` | Topology/Area | `installation_id`, `address` (int), `name` |
| `line` | Area/Line | `area_id`, `address` (int), `name`, `description`, `medium_type_refs` (from its Segments, for example `MT-5`) |
| `space` | Locations//Space | `parent_id` (null for the top space), `space_type` (`Building`, `Floor`, `Room`, `Corridor`, `DistributionBoard`, other values kept verbatim), `name`, `usage_ref` (for example `SU-7`) |
| `component` | Line/Segment/DeviceInstance | `line_id`, `segment_id`, `medium_type_ref`, `address` (int, device number), `individual_address` ("area.line.device"), `name`, `description`, `comment`, `product_ref_id`, `hardware2program_ref_id`, `application_program_id` (resolved through the catalog, else `null`), `manufacturer_id` (from the product reference, for example `M-0083`), `product_text`, `order_number` (catalog, optional), `has_ip_config` (boolean), `serial_number`, `last_modified`, `last_download`, `load_state` (the five `...Loaded` booleans as an object) |
| `communication_object` | DeviceInstance/ComObjectInstanceRefs/ComObjectInstanceRef | `component_id`, `ref_id` (for example `O-23_R-113`), `object_number`, `function_text`, `text`, `object_size`, `read_flag`, `write_flag`, `communication_flag`, `transmit_flag`, `update_flag`, `read_on_init_flag` (each `Enabled`, `Disabled` or `null`), `datapoint_types` (list of ETS datapoint ids such as `DPST-1-1`, as written; empty if none), `channel_id`, `description` (instance description), `instance_text` (instance `Text`), `definition_resolved` (boolean) |
| `group_address` | GroupAddresses//GroupAddress | `address_raw` (int 0-65535), `address` (text formatted per `group_address_style`, for example `5/0/12`), `name`, `description`, `datapoint_type` (as written, or `null`), `range_id` (nearest GroupRange or `null`) |
| `group_range` | GroupRanges//GroupRange | `parent_id`, `range_start`, `range_end`, `name`, `description` |
| `parameter` | DeviceInstance/ParameterInstanceRefs/ParameterInstanceRef | `component_id`, `ref_id`, `parameter_id` (resolved definition id or `null`), `name`, `text`, `parameter_type_id`, `value` (raw string exactly as in the project), `definition_resolved` (boolean) |
| `scene` | reserved, see below | `name`, `scene_number`, `members` |
| `application_program` | catalog Hardware.xml and application program XML (CATALOG) | `manufacturer_id`, `application_number`, `application_version`, `mask_version`, `name` (if present), `source_loaded` (boolean: the XML was found and read) |

Relations (source facts, listed under `source_facts.relations`):

| Relation | Fields | Source |
| --- | --- | --- |
| `membership` | `communication_object_id`, `group_address_id`, `order` (0-based position in `Links`; the semantics of position 0 (sending address) are NOT asserted here; todo 15 must verify them before `trace_group_flow` relies on them) | `Links` attribute (space-separated `GA-<n>`, resolved to `<project id>-0_GA-<n>`) |
| `placed_in` | `space_id`, `component_id` | `Space/DeviceInstanceRef` |

Containment is carried by the parent fields above (`area.installation_id`, `line.area_id`, `component.line_id`,
`space.parent_id`, `communication_object.component_id`, `parameter.component_id`, `group_address.range_id`,
`group_range.parent_id`). Segments are not a node kind; the segment id and medium type are fields of line and
component. Channels (`Node` elements), `ModuleInstance`, `Argument`, `Security`, `BinaryData`, `IPConfig`
details, `AdditionalAddresses`, `ProjectTrace` (ETS change history) and `UserFiles` are intentionally not
modelled (no warning); `channel_id` is kept on communication objects.

Scenes: the sample contains no scene elements, so the real ETS 6 scene structure is not verified. The node
kind `scene` is part of the model; the parser creates scene nodes only from elements named `Scene` it can map
(`Name`, `Number`, and member references) and otherwise emits `UNSUPPORTED_ELEMENT` once per distinct element
name containing "Scene" (case-insensitive). The sample count for `scene` is 0. A synthetic fixture covers the
mapped form; real-world scene coverage is a limitation noted for todo 15.

Referenced application program (ONE normative definition). An application program is "referenced" if and only
if at least one component resolves to it by the following path, checked on the real sample
(`DeviceInstance/@Hardware2ProgramRefId` = `M-0083_H-88-1_HP-0056-11-A826`):

1. Normative path (P1): `DeviceInstance/@Hardware2ProgramRefId` -> the manufacturer folder `<M>` is the part of
   that value before the first `_` (`M-0083`) -> entry `<M>/Hardware.xml` -> the `Hardware2Program` element whose
   `Id` equals that value -> its `ApplicationProgramRef/@RefId` (`M-0083_A-0056-11-A826`) = the application
   program id -> the application program XML is the entry `<M>/<application program id>.xml`.
2. `DeviceInstance/@ProductRefId` is NOT a path to the application program (one product/hardware can offer
   several programs). It only supplies `product_text` and `order_number` through `Hardware.xml`
   `Product`; an unresolvable product gives `PRODUCT_REFERENCE_UNRESOLVED`.
3. Fallback (P2), used only when `<M>/Hardware.xml` is absent or unreadable, or has no matching
   `Hardware2Program`: derive the id textually, `<M>_H-...-<x>_HP-<rest>` -> `<M>_A-<rest>` (for the sample value
   `M-0083_A-0056-11-A826`); the derived id counts as resolved only if the entry `<M>/<id>.xml` exists. P2 is
   always accompanied by the warning that explains why P1 was not usable (`OPTIONAL_PART_MISSING`,
   `OPTIONAL_PART_UNREADABLE` or `PRODUCT_REFERENCE_UNRESOLVED`).
4. Disagreement: when P1 and P2 are both computable and give different ids, P1 wins and the warning
   `APPLICATION_PROGRAM_REFERENCE_MISMATCH` is added. When the `ParameterInstanceRef/@RefId` values of a
   component name an application program id (the part before `_P-` or `_UP-`) different from the resolved
   program, the resolved program (P1, else P2) still wins, those parameters stay unresolved
   (`PARAMETER_DEFINITION_UNRESOLVED`) and one `APPLICATION_PROGRAM_REFERENCE_MISMATCH` is added per component.
5. A component for which neither path yields an existing entry gets `application_program_id` as resolved by
   P1/P2 if known (else `null`) and `APPLICATION_PROGRAM_MISSING`.
6. Only referenced programs are opened. The sample: 28 components reference 12 distinct application programs;
   the archive holds 13 application program XMLs; `M-0083/M-0083_A-003B-24-3717.xml` is not referenced and is
   NEVER opened or read.

Resolution of definitions (CATALOG facts): `communication_object.ref_id` `O-n_R-m` resolves
to the `ComObjectRef` with id `<application program id>_O-n_R-m` and its `ComObject`
(`<application program id>_O-n`); attributes of the reference override those of the object. `parameter.ref_id`
is the `ParameterRef` id; its `RefId` is the `Parameter` (also inside `Union`). Only application programs
referenced by components are opened, each streamed with incremental parsing; only definitions whose ids are
referenced by the component instances are kept (the parameter definition id is the `ref_id` up to the last
`_R-`), and large subtrees (translations, dynamic sections) are cleared as soon as they end, so memory stays
bounded by the project, not by the 50 MB file. Unreferenced programs in the archive are never read.

### Stable ID rules

1. Element has an ETS `Id` attribute (`Area`, `Line`, `Segment`, `DeviceInstance`, `GroupAddress`, `GroupRange`,
   `Space`): `id` = that value, `id_origin` `ETS_ID`. Example `P-051B-0_DI-6`.
2. The installation has no `Id`: `id` = `<project folder id>-<installation file stem>`, for example `P-051B-0`
   (`ETS_COMPOSITE`).
3. Elements identified only by a reference inside a component get a composite ID (`ETS_COMPOSITE`):
   communication object `<component id>/co/<RefId>`, parameter `<component id>/pa/<RefId>`. Membership has no
   node ID; a relation is identified by the pair of IDs plus `order`. Application program `<ApplicationProgramRef RefId>`
   (for example `M-0083_A-0056-11-A826`).
4. An element that should have an `Id` but lacks it (or an element kind that has none, such as a scene) gets the
   structural fallback (`STRUCTURAL_FALLBACK`): `s:` + parent id + `/` + kind + `[` + key + `]`, key = the
   `Address` value if present, else the `Name`, else the 0-based position among same-kind siblings. A warning
   `STRUCTURAL_ID_FALLBACK` is emitted for each such element. Fallback IDs change when the structure changes;
   ETS and composite IDs do not.
5. Collision: when two nodes would get the same `id`, the later one gets the suffix `~2`, `~3`, ... and the
   warning `DUPLICATE_ID` is emitted (location = first colliding element).
6. Determinism: the same file always yields the same IDs, nodes sorted by (`kind`, `id`), relations by their
   key; the persisted graph is byte-identical across re-imports of the same file (it contains no timestamps).

### Derivation: component typing (derived facts)

Module `domain/derivation.py` (pure). Input: source facts. Output, stored under `derived_facts`:

- `component_typing`: object keyed by component id; value `{component_type, rule_id, basis}`.
- `membership_index`: `group_address_to_communication_objects` (group address id -> sorted communication object
  ids) and `component_to_group_addresses` (component id -> sorted group address ids). Reverse indexes only.
- `derived_counts`: `component_type_counts`.

Component typing is never a source fact and is recomputed on every import. Values of `component_type`:
`IP_COUPLER_OR_INTERFACE`, `COUPLER`, `SENSOR`, `ACTUATOR`, `CONTROLLER`, `UNTYPED`. Rules are evaluated strictly in
the order CT0, CT1, CT2, CT3, CT4; the first rule whose condition holds decides and later rules are not
evaluated (so an override beats everything; an IP component with device number 0 is `IP_COUPLER_OR_INTERFACE`, not
`COUPLER`); `rule_id` names the deciding rule and `basis` lists the inputs used. The override table of CT0 lives
only as a parameter of the derivation function (`overrides`), is EMPTY by default, is never read from a file,
the environment or the project, and is never persisted; only tests inject entries, so a real import always starts
at CT1:

| Rule id | Condition | Type |
| --- | --- | --- |
| `CT0_OVERRIDE` | an entry of the curated override table matches the component's `product_ref_id`, `hardware2program_ref_id` or `application_program_id` (exact); the table is a function parameter, EMPTY by default, so data-driven tests inject entries; this is the extension point for product or application based typing | entry's type |
| `CT1_IP` | `has_ip_config` is true, or the component's segment medium type is `MT-5` (IP) | `IP_COUPLER_OR_INTERFACE` |
| `CT2_COUPLER` | `address` (device number) is 0 | `COUPLER` |
| `CT3_NO_OBJECTS` | no communication object with `definition_resolved` true | `UNTYPED` |
| `CT4_DIRECTION` | let R = objects with `write_flag` Enabled and T = objects with `transmit_flag` Enabled (an object may count in both). R>0 and T=0: `ACTUATOR`; T>0 and R=0: `SENSOR`; R=0 and T=0: `UNTYPED`; both >0: if R >= 2*T then `ACTUATOR`, else if T >= 2*R then `SENSOR`, otherwise `CONTROLLER` (mixed direction). Direction of the comparison: write flag (receive, R) is compared against transmit flag (T); the exact boundary favours the stated side (R = 2T is `ACTUATOR`, T = 2R is `SENSOR`); a tie R = T > 0 is `CONTROLLER`; R = 1, T = 1 is `CONTROLLER`; R = 3, T = 2 is `CONTROLLER`. Only objects with `definition_resolved` true and a flag value `Enabled` count; objects with unresolved flags (`null`) count in neither R nor T. The two conditions R >= 2T and T >= 2R cannot both hold when R, T > 0 | per rule |

Rule coverage by fixture (`tests/fixtures/typing_rule_cases.yaml`, T4/T7): CT0 matches by each of the three
keys and beats CT1; CT1 by `has_ip_config` and by medium `MT-5`; CT1 beats CT2; CT2 (device number 0) beats CT3;
CT3 with zero objects and with objects whose definitions are unresolved; CT4 for R>0/T=0, T>0/R=0, R=T=0 with
resolved objects (`UNTYPED`, rule id `CT4_DIRECTION`), R = 2T, R = 2T - 1 (`CONTROLLER`), T = 2R, T = 2R - 1
(`CONTROLLER`), the tie R = T (`CONTROLLER`), and an object with both flags Enabled counting in both R and T.

`basis` always holds: `product_ref_id`, `application_program_id`, `receive_object_count` (R), `transmit_object_count` (T),
`object_count`, `datapoint_main_types` (sorted unique main numbers parsed from the objects' `datapoint_types`, for
example `["1", "5", "9"]`; subtype tokens are parsed from the ids `DPT-<n>` / `DPST-<n>-<m>`; the objects' datapoint types
are checked against `knx_master.xml` when readable). Typing is coarse by design: purpose annotation is todo 14.
The rule set may only be extended by a spec change (new rule ids), never by changing the meaning of an existing id.

### Warnings contract

Model `ImportWarning` (contracts): `code` (string), `message` (string, one sentence, no personal data beyond element ids and names present in the project),
`location` (string): the zip entry (`M-0083/Hardware.xml`), or `<zip entry>#<ETS id or locator>`
(`P-051B/0.xml#P-051B-0_DI-6`). The full ordered list is persisted in `project-graph.json`; `session-state.yaml`
keeps the first 200 plus the counts. Codes:

| Code | Meaning |
| --- | --- |
| `OPTIONAL_PART_MISSING` | an optional part that the import needs is ABSENT from the archive (`knx_master.xml`, a manufacturer `Hardware.xml`); nothing was read |
| `OPTIONAL_PART_UNREADABLE` | an optional part is skipped: not well-formed, unreadable, or rejected by the XML guard (DTD, entity declaration or non-UTF-8 encoding). The message names the reason (`reason: XML_DTD_FORBIDDEN`, `XML_ENTITY_FORBIDDEN`, `XML_ENCODING_UNSUPPORTED`, or a malformed/read-error cause); a rejected part is never parsed or partially used |
| `APPLICATION_PROGRAM_MISSING` | a component's application program XML is not in the archive or not found through the catalog; its objects and parameters stay unresolved |
| `PRODUCT_REFERENCE_UNRESOLVED` | the product or hardware-to-program reference of a component is not found in the catalog |
| `APPLICATION_PROGRAM_REFERENCE_MISMATCH` | resolution paths P1 and P2 disagree, or a component's parameter references name another application program than the resolved one (P1 wins; see "Referenced application program") |
| `COMOBJECT_DEFINITION_UNRESOLVED` | a communication object reference has no definition in the application program (`definition_resolved` false) |
| `PARAMETER_DEFINITION_UNRESOLVED` | same for a parameter reference |
| `GROUP_ADDRESS_LINK_UNRESOLVED` | a `Links` entry names a group address that does not exist; no membership is created |
| `DEVICE_REFERENCE_UNRESOLVED` | a `Space/DeviceInstanceRef` names a component that does not exist; no `placed_in` relation |
| `DATAPOINT_TYPE_UNKNOWN` | a datapoint type id is not found in `knx_master.xml` (only when the master was read) |
| `INVALID_ATTRIBUTE_VALUE` | a required attribute (for example `Address`) is missing or not numeric; the element is skipped |
| `DUPLICATE_ID` | stable ID collision (rule 5) |
| `STRUCTURAL_ID_FALLBACK` | a node got a structural fallback ID (rule 4) |
| `UNSUPPORTED_ELEMENT` | scene-like content that cannot be mapped (see Scenes) |
| `ADDITIONAL_INSTALLATION_IGNORED` | a second installation file `<n>.xml` exists |

### Persistence: `project-graph.json` and its relation to `session-state.yaml`

- File `project-graph.json` in the work-directory, UTF-8 JSON, keys sorted, written atomically (temporary file in
  the same folder, then `os.replace`). Top-level keys: `graph_schema_version` (1), `fingerprint`, `source_facts`
  (`nodes`, `relations`), `derived_facts`, `warnings`. It contains no wall-clock times, so an unchanged project
  re-imports to byte-identical content. Size of the sample graph is measured and recorded at T12; if it exceeds
  20 MB switch to compact JSON (no indentation).
- `session-state.yaml` `project_import` after story 04 (replaces the story 03 shape): `path`, `mtime`
  (integer ns), `size`, `imported_at`, `fingerprint` (64 lowercase hex digits), `graph_file`
  (`project-graph.json`, relative), `graph_schema_version`, `project_import_summary`, `warnings` (first 200
  import warnings). `project_refresh` is unchanged.
- Write order on import and re-import: parse completely first (a failure writes nothing), then write
  `project-graph.json`, then `session-state.yaml`. A crash between the two leaves a stale fingerprint in the
  state, so the next refresh check re-imports (self-healing). `create_session` builds both inside the temporary
  sibling folder (atomic create, story 03). A missing or corrupt `project-graph.json` of an existing session is
  repaired by the next refresh check or explicit re-import (the check treats a missing graph file as CHANGED).
- Single-writer assumption (story 03) applies. The graph file is read only by `reimport_system_definition` (to
  compute `changes` against the old graph), by the automatic re-import for the same purpose (counts in the log),
  and by the later query capabilities; `describe_session` and an unchanged refresh check do not read it.

### Fingerprint and refresh check

Terms used in this section and in the task plan (use exactly these; the terminology dictionary is unchanged):

- **Fingerprint**: the SHA-256 of the `.knxproj` file bytes, lowercase hex, stored as `project_import.fingerprint`.
- **Project refresh check**: the per-call step that compares the bound `.knxproj` file with the stored import
  metadata (existence, mtime, size, fingerprint) and re-imports it automatically when anything differs.
- **CHANGED**: the value of `project_refresh.last_status` and of `project_refresh_status` meaning that mtime, size,
  fingerprint or the graph file differed from the stored state, so the project was re-imported with new metadata.
- **UNCHANGED**: the value meaning that all of these were equal; for an explicit `reimport_system_definition` the
  file was nevertheless re-read and the graph rewritten, for the automatic check nothing is written.

- Fingerprint = SHA-256 of the `.knxproj` file bytes, lowercase hex, computed over the whole file in 1 MiB chunks.
- Refresh check order, run before every session-scoped call: (1) existence and readability
  (`PROJECT_FILE_UNREADABLE`, state unchanged); (2) `mtime` differs; (3) `size` differs; (4) fingerprint differs.
  Steps 2 and 3 are the cheap short-circuit: a difference means CHANGED without hashing first (the hash is then
  computed as part of the re-import). Only when mtime and size equal the stored values is the file hashed and the
  result compared (step 4). So the hash is computed on every check that does not already find a change; for the
  7.5 MB sample that is about 10 to 30 ms (measured at T12 and recorded in README.md).
- Any difference (including `fingerprint` stored as `null`, which is the case for sessions of story 03, or a
  missing graph file) means CHANGED: automatic re-import, atomic state and graph update, `reimport_count`
  incremented, exactly as in story 03. Equal on all four: no write (idempotent; the state file stays byte-identical).
- `reimport_system_definition` always re-parses: status CHANGED when any of mtime, size or fingerprint differs from
  the stored values (or the graph file is missing), else UNCHANGED; `imported_at` is always rewritten; the graph is
  rewritten and compared with the old one in both cases.
- The file is stat-ed before hashing and again after the import; if mtime or size changed in between, the import
  is aborted with `PROJECT_FILE_UNREADABLE` (`details.reason` `CHANGED_DURING_IMPORT`), nothing is written.

### `project_import_summary`

Persisted in `session-state.yaml`, returned unchanged by `create_session`, `reimport_system_definition` and (inside
`project_import`) `describe_session`. Fields (the story 03 field `limitation_note` is removed; limitation notes
are in the envelope):

- `file_name`, `archive_entry_count`
- `ets_tool_version` (for example `6.1.5686.0`), `schema_namespace`, `created_by` (`ETS6`), `project_id`, `project_name`, `group_address_style`
- `node_counts`: object with one integer per node kind (all kinds listed, 0 when absent): `installation`, `area`, `line`, `space`, `component`, `communication_object`, `group_address`, `group_range`, `parameter`, `scene`, `application_program`
- `relation_counts`: `membership`, `placed_in`
- `component_type_counts`: derived (object, type -> integer; types with 0 omitted)
- `application_programs`: `referenced` (distinct programs components use), `read` (found and read), `unreadable`
- `warning_total`, `warning_counts` (object, code -> integer)
- `graph_file`, `graph_schema_version`

Golden counts for the sample (initial values for `tests/fixtures/sample_project_counts.yaml`, measured at planning
by element counts in the XML; the user may edit the fixture): `installation` 1, `area` 2, `line` 3, `space` 21,
`component` 28, `communication_object` 692, `group_address` 695, `group_range` 60, `parameter` 3132, `scene` 0,
`application_program` 12 (13 application program XMLs are in the archive; one is unreferenced and not read),
`membership` 677, `ets_tool_version` 6.1.5686.0, namespace `http://knx.org/xml/project/22`, `archive_entry_count`
82, project id `P-051B`. The importer must reproduce these numbers; a mismatch is investigated, not silently
re-baselined.

Envelope `limitation_notes` of `create_session`, `reimport_system_definition` and `describe_session`: one entry per
import warning, formatted `[<code>] <message> (<location>)`, at most 50 entries; when more exist a last entry states
`<n> more import warnings not listed; see project_import_summary.warning_counts and project-graph.json`. When the
import produced no warnings the list is empty (the story 03 placeholder note is gone). Standing limitation:
the ETS signature is not verified (documented in README.md, not repeated in every response).

### Reimport: `changes` and `invalidated_references`

`changes` (list of objects, sorted by `entity`, then `id`; empty when nothing changed or at first import):
`{entity: "component" | "group_address", change: "added" | "removed" | "changed", id, label, details}`.
- `label`: component `name` with `individual_address`, or group address `address` with `name`.
- `details` for `added`/`removed`: `{}`. For `changed`: `{changed_fields: [..], old: {..}, new: {..}}` with the
  source fields that differ. Component fields compared: the component fields in the node table except
  provenance, plus `parameters` (count of parameter nodes whose `value` or presence differs, listed as
  `parameter_ref_ids` changed), and `group_addresses` (the sorted ids of the component's linked group addresses,
  from the memberships). Group address fields compared: `address_raw`, `name`, `description`, `datapoint_type`.
- Comparison is by stable ID; a node whose ID changed (structural fallback) appears as removed plus added.
- No other entity is reported in `changes`; communication objects and parameters appear only as changes of their component.

`invalidated_references` (list of objects; empty when nothing is invalidated): scan `session-state.yaml`
`scenario_state` and `mutations` entries (their schemas are defined by todos 06 and 08). An entry that is an
object with `component_id`, `component_ids` (list) or `group_address_id` naming an ID that existed in the old graph and is
absent from the new graph yields
`{reference_kind: "scenario_state" | "mutation_delta", owner, component_id | group_address_id, reason: "COMPONENT_REMOVED" | "GROUP_ADDRESS_REMOVED"}`.
`owner` is the mutation `name` for mutations, else the zero-based list index as text. Entries without these keys are
ignored. State is retained, never deleted (catalogue 2 proposal); each invalidated reference also appears as a
limitation note. Tests inject synthetic entries into `session-state.yaml`.

### What `describe_session` returns

Everything of story 03 plus `project_import`: `{imported_at, fingerprint, graph_file (absolute path), project_import_summary}`.
It reads only `session-state.yaml` (the summary and the first 200 warnings are persisted there). The envelope
`limitation_notes` are the import warnings as above. Its automatic refresh check may re-import.

### Log points (additions to the story 03 table)

| Log point | Capability | Level | Summary / details |
| --- | --- | --- | --- |
| Import finished (create) | `create_session` | INFO (the existing "Session created" entry) | details gain: fingerprint, `node_counts`, `warning_total`, import duration in seconds |
| Re-import finished (explicit or automatic) | `reimport_system_definition` or the calling capability | INFO (existing entries) | details gain: fingerprint old/new, `warning_total`, counts of `changes` by entity and change, count of `invalidated_references`, duration |
| Import started | the calling capability | DEBUG | project path, size |
| Each import warning | the calling capability | DEBUG (one entry each, at most 200, then one DEBUG entry stating how many were omitted) | code, message, location |
| Import failed (`PROJECT_PARSE_ERROR`, `PROJECT_FILE_UNREADABLE`) | the calling capability | ERROR | as story 03; always written; reason in details |

Import warnings are not issues in the sense of the story 03 ERROR rule (see decisions): they do not produce ERROR
entries. Python logging: one `logging.WARNING` record on logger `knx_agent.application` per import that has warnings
(counts only, no per-warning records at WARNING; per-warning records at DEBUG). No custom logging code.

### Dependencies

Runtime: no new dependency while impl-b stands (stdlib `zipfile`, `hashlib`, `xml.etree.ElementTree`, `json`).
Dev group: `xknxproject` (GPL-2.0, dev-time cross-check only, never imported by `src/`; if it cannot be installed
the cross-check test skips and the golden counts are the fallback). Licenses are recorded in
`development/todos/12-dependency-license-governance.md`; if lxml is adopted by the benchmark rule it is added as
a runtime dependency (BSD-3-Clause) with a README.md note.

### Module placement (layering, story 04)

`domain`: `project_graph.py` (models, ID helpers), `derivation.py` (component typing, indexes), `graph_diff.py`
(changes, invalidated references; pure). `application`: `knxproj_archive.py` (limits, hostile-archive guard,
safe XML reading), `knxproj_parser.py` (ETS 6 elements to graph), `project_importer.py` (fingerprint, archive,
parser, derivation -> `ImportResult`), `graph_store.py` (JSON read/write, atomic), and changes to
`knxproj_guard.py` (keeps `stat_project`), `project_refresh_guard.py`, `session_lifecycle.py`, `session_service.py`.
`contracts`: extended `ProjectImportSummary`, new `ImportWarning`, `ProjectChange`, `InvalidatedReference`,
`ProjectImportInfo`; `DescribeSessionResponse.project_import`. Adapters (SDK, CLI, MCP) need no new command; they
return the extended models unchanged. Import-direction test stays green.

### Implementation notes (T1 to T8, interpretations recorded by the implementation)

- Parameter reference prefix (P4): the application program id named by a `ParameterInstanceRef/@RefId` is the part
  before `_P-`, `_UP-` or `_MD-`. `_MD-` is needed because module-instance references of the sample
  (`M-0083_A-013C-32-51EA_MD-2_M-1_MI-1_P-1_R-1`) would otherwise count as another program. Module-instance
  references (ids with `_MD-..._MI-...`) are not resolved against module definitions: their objects and parameters
  stay `definition_resolved` false with the unresolved warnings (sample: 12 objects and 14 parameters of one component).
- Unresolved warnings are emitted per object or parameter when the program was read or was rejected/unreadable; for a
  missing program (`APPLICATION_PROGRAM_MISSING`, once per component) no per-object warnings follow.
- `DATAPOINT_TYPE_UNKNOWN` is emitted once per distinct unknown id (location: first node using it).
- `INVALID_ATTRIBUTE_VALUE`: `Address` of Area, Line, DeviceInstance and GroupAddress (group address also 0 to 65535)
  must be numeric, else the element and its subtree are skipped; `RangeStart`/`RangeEnd` of a GroupRange must be
  numeric, else only the range node is skipped and its children attach to the enclosing range.
- Scene detection: the element `Scene` (case-sensitive) maps to a scene node, its descendants are not reported; the
  plural container `Scenes` is not reported either; any other element name containing "scene" gives one
  `UNSUPPORTED_ELEMENT` per distinct name. A scene without `Id` gets a structural fallback ID and a
  `STRUCTURAL_ID_FALLBACK` warning.
- Typing basis: `object_count` counts all communication objects of the component; R and T count only objects with
  `definition_resolved` true. CT0 entries are `TypeOverride(match, value, component_type)` (first match in table order).
- Change details for a changed component: `details.old.parameters` and `details.new.parameters` map the changed
  parameter `ref_id`s to their old/new raw value (`null` = absent).
- Required-part check: `0.xml` without an `Installation` element is `REQUIRED_PART_MALFORMED`.
- Optional parts are scanned in full before parsing (a second decompression pass), so a rejected optional part never
  reaches a parser and nothing from it is used; archive-level guard failures are checked on the whole central
  directory first.
- Story 03 transition (done in T10): `limitation_note`, `LIMITATION_NOTE` and `inspect_project`/`ProjectFileInfo` are
  removed; `DescribeSessionResponse.project_import` is required. The content fields of `ProjectImportSummary` keep
  their defaults (they are harmless and keep small hand-built summaries in tests short).

### Implementation notes (T9 to T13, interpretations recorded by the implementation)

- Modules: `application/project_importer.py` (`import_project`, `ImportResult`, `file_fingerprint`, `build_summary`),
  `application/import_support.py` (persisted `project_import` shape, log points, limitation notes). The importer
  stats the file, hashes it (1 MiB chunks), opens the archive guard, parses, derives and stats again; it writes
  nothing. `overrides` (CT0) is a parameter of `import_project` only.
- Log points: "Import started" (DEBUG) is written before the import for re-imports. For `create_session` the log book
  exists only after the import, so the DEBUG entries "Import started", the per-warning entries and the INFO entry
  "Session created" are written into the new log book in that order just before the atomic rename (their timestamps
  are those of writing). Per-warning DEBUG entries and the single Python WARNING record (logger `knx_agent.application`)
  are written after the graph and state write; the INFO entry comes last and its id is the envelope
  `log_book_entry_id`. INFO details of re-imports: `status`, old/new mtime, size and fingerprint, `warning_total`,
  `changes` (counts keyed `<entity>_<change>`, for example `component_added`), `invalidated_references` (count),
  `duration_s`. ERROR entries gain `details.reason` when the error has one.
- Refresh check: a stored fingerprint of `null` or a missing `project-graph.json` is CHANGED before any hashing
  (nothing to compare); a present but corrupt graph file is not detected by the automatic check (it would need a
  read of the graph) and is repaired by the next explicit `reimport_system_definition` (the old graph then counts as
  missing, so `changes` is empty).
- A failure between the graph write and the state write leaves the new graph with the old state; the stale fingerprint
  makes the next refresh check re-import (self-healing, as specified).
- Archive reading: every referenced application program XML is opened twice (once by the XML guard scan, once by the
  parser); the sample test asserts exactly 12 distinct program entries opened, 2 openings each, and that
  `M-0083/M-0083_A-003B-24-3717.xml` is never opened.
- `limitation_notes` of `describe_session` come from the 200 warnings persisted in `session-state.yaml`; the
  "n more" entry uses `project_import_summary.warning_total - 50`.
- xknxproject cross-check (T12): individual addresses (28) and group addresses (695, including `raw_address`) are
  equal. xknxproject reports 677 communication objects against our 692 because it lists only objects that have at
  least one group address link; per component, the number of our objects with a membership equals its
  `communication_object_ids` for all 28 components (the three components with the difference are those that own
  unlinked objects). The test asserts this and that the gap equals the number of unlinked objects.
- T11: no code change was needed in SDK, CLI or MCP (they return the extended models unchanged); tests were added or
  updated in `tests/test_adapters.py`, `tests/test_sdk.py` and `tests/test_contracts.py`.

## Traceability: use case to capability

Use case numbers follow `docs/methodology/001-use-cases-raw.md`; sub-rows are its success criteria.

| Use case | Satisfied by |
| --- | --- |
| 1.1 Query components by name (purpose via agent layer) | `list_components`, `describe_component` |
| 1.2 Broad query with SUMMARY/MEDIUM/FULL | `list_components`, `summarize_topology` |
| 1.3 Configuration of one component by name | `describe_component`, `fetch_component_details` |
| 1 (criterion) Settings, configuration and parameters come from the `.knxproj` | `describe_component` (evidence source `KNXPROJ`) |
| 2.1 Query sensor inputs by name, or broadly | `list_environment_inputs` |
| 2.2 Provide a value for simulation (environment model) | `set_environment_value` |
| 2.3 Simulated impact on KNX system state; trace as input | `set_environment_value`, `load_bus_trace`, `trace_group_flow` |
| 3.1 Provide user input (button press) | `resolve_user_action_candidates`, `inject_user_action` |
| 3.2 Session log book for debugging and reasoning | `read_session_log_book` (and logging by all state-changing calls) |
| 3.3 Unresolvable input is an error | `resolve_user_action_candidates`, `inject_user_action` |
| 4.1 Questions about activities ("now") | `answer_activity_question` |
| 4.2 Evidence sources, unresolved assumptions, log book update | `answer_activity_question`, `read_session_log_book` |
| 4.3 Missing input leads to a request; what-if variants | `answer_activity_question` (`needed_inputs`), `create_mutation` |
| 5.1 Mutate parameters on top of the `.knxproj` | `create_mutation`, `set_parameter_override` |
| 5.2 Run use cases 1-4 on mutated and original setup | all setup-scoped capabilities via `mutation_name` / `select_setup` |
| 5.3 Named, persistent deltas; mutation log books | `create_mutation`, `list_mutations`, `read_session_log_book(mutation_name)` |
| Session foundation for all use cases | `create_session`, `describe_session`, `reimport_system_definition`, `select_setup` |
| Agent-layer-only items: purpose resolution, natural-language mapping, comparison | not in core; agent layer (todos 11, 14) |

Note: "query by name or purpose" is satisfied for purpose by the agent layer filtering the returned `purpose_annotation` (data from `development/todos/14-component-purpose-annotation.md`); the core has no purpose parameter.

Every one of the 19 capabilities appears in at least one row.

## Replaced and dropped names

| Former name | Disposition |
| --- | --- |
| `describe_device`, device, object, element, device typing | `describe_component`, component, component typing; use "component" |
| `explain_expected_reaction`, `list_possible_causes`, `compare_expected_vs_observed`, `simulate_outcome` | `answer_activity_question` (comparison is agent-level only) |
| `label`, `session_id`, `session_handle`, `session_token`, session identifier | `session_label` |
| `refresh`, `refresh_session`, `load_project`, `project load` | `reimport_system_definition` |
| `summarize_recent_activity`, `read_mutation_log_book` | `read_session_log_book` with `mutation_name` |
| `infer_environment_from_trace`, `decode_telegram` | merged into `load_bus_trace` |
| `inject_event`, `set_environment_state` | `inject_user_action` / `set_environment_value` |
| `find_group_address` | `trace_group_flow` |
| `get_environment_value` | `list_environment_inputs` |
| `describe_mutation` | `list_mutations` |
| `extract_behavior_hints` | `fetch_component_details` |
| `show_evidence_sources` | dropped; evidence is embedded in every response |
| `reset_state`, `reset_scenario` | dropped; create a new session |
| uploaded artifact handle (create_session) | dropped; path only |
| `purpose` request parameter | dropped from core; agent layer resolves purposes |

## Agent-layer contract notes

- The agent layer translates phrases such as "Kid room blind" into deterministic queries (partial name
  `Kid`), asks when several candidates remain, and never fabricates names or state.
- It uses short, crisp technical wording and builds comparisons between default and mutated setups on
  top of capability results.

## Appendix: non-capability design notes migrated from 001 and 002

Content of `docs/implementation/001-solution-concept.md` and `002-bootstrap-implementation-plan.md` that
is still valid and not captured by the architecture or the dictionary:

- Session persistence: one work-directory per session (`<session root>/<session_label>`, see "Session service realisation (story 03)"); `session-state.yaml` created at session
  creation with at least `session_label`, `created_at`, `work_directory`, `source_project_absolute_path`,
  `project_import`, `project_refresh`, `active_setup`, `trace_artifacts`, `mutations`, per-setup
  `current_system_state` reference and log-book references; artifacts are referenced from the state
  file, not found by directory scanning; mutations persist as deltas in mutation files.
- Layering: `domain/` and `application/` hold the callable core API, `sdk/` re-exports it, `cli/`
  (`typer`) and `adapters/mcp/` (`MCPServer`) bind to SDK operations, `agent_layer/` packages prompts and
  skills; every new Python module lands with pytest coverage; SDK-first tests precede adapter tests.
  Concrete package skeleton: `development/todos/02-package-skeleton-and-core-api.md`.
  Firm package-layout note (story 02, decided):
  - One uv-managed project (single `pyproject.toml`, `src` layout), importable package `knx_agent` under `src/knx_agent/`.
    Layer boundaries are enforced by an import-direction test, not by the build.
  - Sub-packages (each a plain Python package):
    - `domain`: pure domain concepts and rules; no I/O, no framework imports.
    - `application`: the callable core API (capability functions: request validation, resolution, result assembly); depends on `domain` and `contracts`.
    - `adapters`: outward-facing bindings and (later) storage/parsing adapters; `adapters/mcp` holds the `MCPServer` tool adapter. Adapters call the SDK only.
    - `sdk`: the canonical programmable surface (`client.<capability>(...)`); re-exports and wraps `application`.
    - `cli`: the `typer` app (entry point `knx-agent`); calls the SDK only.
    - `agent_layer`: placeholder for prompts and skills (todo 11); no runtime code yet.
    - `contracts`: Pydantic v2 request/response/envelope/error models; shared by all layers, imports nothing from `knx_agent`.
  - Import direction rule: `cli` and `adapters` (incl. `adapters/mcp`) -> `sdk` -> `application` -> `domain`; `contracts`
    is importable by every layer and imports no other `knx_agent` sub-package; no inner layer imports an outer layer;
    `cli` and `adapters` never import `application` or `domain` directly; `agent_layer` may import `sdk` and `contracts` only.
  - Envelope models (Pydantic v2, `knx_agent.contracts`) implement C7 without adding fields:
    - `EvidenceSource`: `kind` (enum `KNXPROJ`, `TRACE`, `USER_INPUT`, `VENDOR_DOCUMENTATION`, `SIMULATION_RULE`) and `reference` (string).
    - `ResponseEnvelope`: `setup` (string; optional because `fetch_component_details` omits it), `evidence_sources` (list of `EvidenceSource`, possibly empty),
      `limitation_notes` (list of strings, possibly empty, never null), `log_book_entry_id` (optional), `detail_level` (optional, enum `SUMMARY`, `MEDIUM`, `FULL`; set only on descriptive calls).
      Capability response models embed or inherit the envelope.
    - `ErrorInfo`: `code` (string; codes remain proposals per C7), `message` (string), `details` (optional). Core failures are raised as one SDK exception carrying `ErrorInfo`; adapters map it to their surface unchanged.
  - Skeleton callable (story 02): `describe_session(session_label)` (catalogue capability 3) with a clearly marked placeholder body that returns the envelope and a limitation note
    stating that the session service is not implemented yet (todo 03). No other capability is wired by the skeleton; wiring all capabilities is todo 10.
  - Testing strategy: pytest from the repository root; SDK-first (core API and SDK tests call the SDK directly, without CLI or MCP), then adapter delegation tests
    (core/SDK callable mocked; inputs and outputs pass through unchanged and no domain logic exists in the adapter), model validation tests (envelope and error shape,
    evidence kinds), one import test per sub-package, and an import-direction test that parses module imports (AST) and fails on any inward-rule violation.
- Dependencies: `typer` for CLI, `mcp` (`MCPServer`; called FastMCP in mcp 1.x, renamed in mcp 2.x, pinned `mcp>=2,<3`) for MCP; every dependency needs a recorded free-to-use
  license review (`development/todos/12-dependency-license-governance.md`).
- Validation expectations carried forward: SDK, CLI and MCP return compatible structured results;
  every response includes evidence sources and limitation notes; session resume from the work-directory;
  edited `.knxproj` detected on the next call.

Discarded explicitly (superseded or tracked elsewhere): 001 primary user jobs, operating modes and
conceptual data flow (superseded by the use cases and this catalogue); 001 "Information we still need"
and 002 "Bootstrap decisions needing input" (tracked as todos 05, 09, 10, 12); 002 delivery slices and
near-term milestones (superseded by `development/todos/02` to `14`); 002 test-asset and manual-check
lists (owned by `development/todos/13-fixtures-and-end-to-end-validation.md`); 001 shared domain
concepts (live in `docs/architecture/001-knx-investigation-platform.md` and the dictionary);
001 scenario capabilities and "resettable" scenario facts (dropped, see replaced names).
