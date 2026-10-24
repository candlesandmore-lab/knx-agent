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
  (required, confirmed). The `session_label` must be unique among all sessions under the session work-directory root
  (defined in `development/todos/03-session-service-and-project-refresh.md`). The session is bound
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
  results), `FULL` (DEBUG plus low-level flow and debug detail).
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
- Request: `project_path` (required, path only); `session_label` (required, user-chosen, unique among sessions under the session work-directory root; non-empty, letters, digits, `-` and `_` only so it is safe as a directory name).
- Response: `session_label` (echo), `work_directory`, `session_state_path`, `source_project_absolute_path`, `project_import_summary`, `active_setup` (`default`), envelope.
- Evidence/limits: `KNXPROJ`; import warnings for unsupported or ambiguous data.
- Errors: `PROJECT_FILE_UNREADABLE` (missing or unreadable file), `PROJECT_PARSE_ERROR`, `SESSION_LABEL_EXISTS`, `SESSION_LABEL_INVALID`.
- Projection: CLI `knx-agent session create --project <file> --session-label <session_label>`; SDK `client.create_session(project_path=..., session_label=...)`; MCP `create_session`.

### 2. `reimport_system_definition` (UC 1, freshness)
- Purpose: explicitly re-read the bound `.knxproj` of an existing session.
- Request: `session_label`.
- Response: `project_refresh_status` (`CHANGED`/`UNCHANGED`), `project_import_summary`, `changes` (components added/removed/changed), `invalidated_references` (state entries or mutation deltas pointing to vanished components), envelope.
- Evidence/limits: `KNXPROJ`. Retaining or recomputing current system state after a changed project is a **(proposal)**: state is retained, invalidated references are reported as limitation notes.
- Errors: `PROJECT_FILE_UNREADABLE`, `PROJECT_PARSE_ERROR`.
- Projection: CLI `knx-agent session reimport --session <session_label>`; SDK `client.reimport_system_definition(session_label=...)`; MCP `reimport_system_definition`.

### 3. `describe_session` (UC 1-5, session inspection)
- Purpose: persisted metadata and status of a session.
- Request: `session_label`.
- Response: `session_label`, `work_directory`, `source_project_absolute_path`, `project_refresh`, `active_setup`, `setups` (default plus mutations, each with current system state summary), `trace_artifacts`, `log_book_references`, envelope.
- Errors: common only.
- Projection: CLI `knx-agent session describe --session <session_label>`; SDK `client.describe_session(session_label=...)`; MCP `describe_session`.

### 4. `select_setup` (UC 5)
- Purpose: switch the active setup.
- Request: `session_label`, `mutation_name?` (omitted selects `default`).
- Response: `active_setup`, `current_system_state_summary`, envelope.
- Errors: `MUTATION_NOT_FOUND`.
- Logging: state-changing, writes session log book (and mutation log book if selected).
- Projection: CLI `knx-agent session select-setup --session <session_label> [--mutation <name>]`; SDK `client.select_setup(session_label=..., mutation_name=...)`; MCP `select_setup`.

### 5. `read_session_log_book` (UC 3, 4)
- Purpose: read the session history for reasoning and audit; replaces separate recent-activity and mutation log reads.
- Request: `session_label`, `mutation_name?` (when given reads that mutation log book, otherwise the overall session log book), `min_level?` (filter by log level), `limit?`, `since_entry_id?`.
- Response: `entries`, `truncated`, envelope. Reading does not itself write the log book.
- Evidence/limits: entries below the level configured when they were written are absent; note this in `limitation_notes`.
- Errors: `MUTATION_NOT_FOUND`.
- Projection: CLI `knx-agent session log-book --session <session_label> [--mutation <name>] [--min-level INFO|DEBUG|FULL] [--limit <n>] [--since-entry-id <id>]`; SDK `client.read_session_log_book(...)`; MCP `read_session_log_book`.

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

- Session persistence: one work-directory per session; `session-state.yaml` created at session
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
