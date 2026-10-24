# Implementation 003: Proposed Capability APIs

## Purpose

This document proposes the first concrete capability set derived from the clarified use cases in `docs/methodology/001-use-cases-raw.md`. The goal is to define one callable core API that is projected consistently onto the Python SDK, the `typer` CLI, the `mcp` FastMCP tool surface, and the outer agent layer.

## Layer model

### Shared callable core API

- Lives below the SDK and above storage or parsing adapters.
- Owns request validation, session or mutation resolution, business logic, result assembly, provenance, and limitation notes.
- Is the primary target for pytest.
- Any new Python implementation in this layer should land with direct pytest coverage.

### SDK layer

- Exposes the callable core API as stable Python methods and data models.
- Is the canonical programmable surface.

### CLI layer

- Uses `typer`.
- Converts command-line arguments into SDK-facing requests.
- Does not own business rules.

### MCP layer

- Uses the `mcp` package with FastMCP.
- Converts MCP tool inputs into SDK-facing requests.
- Does not own business rules.

### Agent layer

- Accepts natural-language user requests.
- Resolves them into deterministic capability calls.
- Must ask for clarification instead of guessing unresolved identifiers or meanings.

## Cross-surface rules

- Every capability is defined once at the callable core API layer.
- CLI, SDK, and MCP use the same semantic request and response structures.
- Session-scoped capabilities accept `session_id` and may accept `mutation_name` when mutation scope matters.
- Every response should include limitation notes and evidence sources when the answer depends on inference.
- The solution package should be validated with pytest, with core behavior exercised through SDK-facing calls before adapter-level checks.

## Proposed capability groups

### 1. Session capabilities

#### Capability: `create_session`

- Purpose: Create a session bound to a mandatory `.knxproj` path.
- Core request:
  - `project_path`
  - `session_label` optional
- Core response:
  - `session_id`
  - `session_label`
  - `work_directory`
  - `session_state_path`
  - `source_project_absolute_path`
  - `project_refresh_status`
  - `project_import_summary`
- CLI proposal: `knx-agent session create --project <file> [--label <name>]`
- SDK proposal: `client.create_session(project_path=..., session_label=...)`
- MCP proposal: `create_session`

#### Capability: `describe_session`

- Purpose: Return the persisted metadata and current status of a session.
- Core request:
  - `session_id`
- Core response:
  - `session_id`
  - `session_label`
  - `work_directory`
  - `source_project_absolute_path`
  - `project_refresh`
  - `trace_artifacts`
  - `mutation_references`
  - `log_book_references`
  - `latest_state_summary`
- CLI proposal: `knx-agent session describe --session <id>`
- SDK proposal: `client.describe_session(session_id=...)`
- MCP proposal: `describe_session`

#### Capability: `read_session_log_book`

- Purpose: Read the overall session history used for reasoning and auditing.
- Core request:
  - `session_id`
  - `limit` optional
  - `since_entry_id` optional
- Core response:
  - `entries`
  - `truncated`
- CLI proposal: `knx-agent session log-book --session <id> [--limit <n>]`
- SDK proposal: `client.read_session_log_book(session_id=..., limit=...)`
- MCP proposal: `read_session_log_book`

### 2. Setup inspection capabilities

#### Capability: `list_components`

- Purpose: Search components by partial name, purpose, address, or broad listing.
- Core request:
  - `session_id`
  - `query` optional
  - `purpose` optional
  - `detail_level` default `MEDIUM`
  - `mutation_name` optional
- Core response:
  - `matches`
  - `match_count`
  - `detail_level`
  - `ambiguity_flag`
  - `clarification_hint` optional
- CLI proposal: `knx-agent setup list-components --session <id> [--query <text>] [--purpose <text>] [--detail-level SUMMARY|MEDIUM|FULL] [--mutation <name>]`
- SDK proposal: `client.list_components(...)`
- MCP proposal: `list_components`

#### Capability: `describe_component`

- Purpose: Return configuration and topology details for one selected component.
- Core request:
  - `session_id`
  - `component_selector`
  - `detail_level` default `MEDIUM`
  - `mutation_name` optional
- Core response:
  - `component_identity`
  - `topology`
  - `device_parameters`
  - `group_addresses`
  - `communication_objects`
  - `purpose_annotations`
  - `evidence_sources`
- CLI proposal: `knx-agent setup describe-component --session <id> --component <selector> [--detail-level ...] [--mutation <name>]`
- SDK proposal: `client.describe_component(...)`
- MCP proposal: `describe_component`

#### Capability: `summarize_topology`

- Purpose: Summarize areas, lines, rooms if derivable, and component distributions.
- Core request:
  - `session_id`
  - `detail_level` default `MEDIUM`
  - `mutation_name` optional
- Core response:
  - `topology_summary`
  - `component_counts`
  - `purpose_summary`
- CLI proposal: `knx-agent setup summarize-topology --session <id> [--detail-level ...] [--mutation <name>]`
- SDK proposal: `client.summarize_topology(...)`
- MCP proposal: `summarize_topology`

#### Capability: `trace_group_flow`

- Purpose: Show participants and propagation paths for a group address or communication object.
- Core request:
  - `session_id`
  - `group_address` optional
  - `communication_object_ref` optional
  - `mutation_name` optional
- Core response:
  - `participants`
  - `propagation_path`
  - `unresolved_links`
- CLI proposal: `knx-agent setup trace-group-flow --session <id> [--group-address <ga> | --object-ref <ref>] [--mutation <name>]`
- SDK proposal: `client.trace_group_flow(...)`
- MCP proposal: `trace_group_flow`

### 3. Environment capabilities

#### Capability: `list_environment_inputs`

- Purpose: Show sensor-oriented environment inputs that can drive the system.
- Core request:
  - `session_id`
  - `query` optional
  - `purpose` optional
  - `mutation_name` optional
- Core response:
  - `inputs`
  - `current_values`
  - `value_sources`
- CLI proposal: `knx-agent environment list-inputs --session <id> [--query <text>] [--purpose <text>] [--mutation <name>]`
- SDK proposal: `client.list_environment_inputs(...)`
- MCP proposal: `list_environment_inputs`

#### Capability: `set_environment_value`

- Purpose: Set or override an environment-model value by sensor-oriented name.
- Core request:
  - `session_id`
  - `sensor_name`
  - `value`
  - `mutation_name` optional
  - `reason` optional
- Core response:
  - `accepted_value`
  - `normalized_knx_value`
  - `updated_environment_element`
  - `log_book_entry_id`
- CLI proposal: `knx-agent environment set-value --session <id> --sensor <name> --value <value> [--mutation <name>]`
- SDK proposal: `client.set_environment_value(...)`
- MCP proposal: `set_environment_value`

### 4. Trace ingestion capabilities

#### Capability: `load_bus_trace`

- Purpose: Load a bus trace into the session.
- Core request:
  - `session_id`
  - `trace_path`
- Core response:
  - `trace_id`
  - `packet_count`
  - `decode_warnings`
  - `observed_address_summary`
  - `log_book_entry_id`
- CLI proposal: `knx-agent trace load --session <id> --path <file>`
- SDK proposal: `client.load_bus_trace(...)`
- MCP proposal: `load_bus_trace`

#### Capability: `infer_environment_from_trace`

- Purpose: Infer environment values and user actions from trace evidence.
- Core request:
  - `session_id`
  - `trace_id`
  - `time_window` optional
  - `mutation_name` optional
- Core response:
  - `inferred_environment_values`
  - `candidate_user_actions`
  - `confidence_scores`
  - `evidence_packets`
- CLI proposal: `knx-agent trace infer-environment --session <id> --trace <id> [--mutation <name>]`
- SDK proposal: `client.infer_environment_from_trace(...)`
- MCP proposal: `infer_environment_from_trace`

### 5. User-action capabilities

#### Capability: `resolve_user_action_candidates`

- Purpose: Resolve a human-facing user action description into candidate KNX-level actions.
- Core request:
  - `session_id`
  - `action_query`
  - `mutation_name` optional
- Core response:
  - `candidates`
  - `ambiguity_flag`
  - `clarification_hint` optional
- CLI proposal: `knx-agent action resolve --session <id> --query <text> [--mutation <name>]`
- SDK proposal: `client.resolve_user_action_candidates(...)`
- MCP proposal: `resolve_user_action_candidates`

#### Capability: `inject_user_action`

- Purpose: Apply a resolved user action and update KNX system state.
- Core request:
  - `session_id`
  - `action_reference`
  - `gesture` optional
  - `mutation_name` optional
- Core response:
  - `resolved_knx_activity`
  - `state_update_summary`
  - `log_book_entry_id`
- CLI proposal: `knx-agent action inject --session <id> --action <ref> [--gesture <name>] [--mutation <name>]`
- SDK proposal: `client.inject_user_action(...)`
- MCP proposal: `inject_user_action`

### 6. Activity-question capabilities

#### Capability: `answer_activity_question`

- Purpose: Answer `should`, `why`, `why not`, `what changed`, or `what input caused this` questions about the latest KNX system state.
- Core request:
  - `session_id`
  - `question`
  - `mutation_name` optional
- Core response:
  - `answer`
  - `confidence`
  - `evidence_sources`
  - `unresolved_assumptions`
  - `needed_inputs`
  - `log_book_entry_id`
- CLI proposal: `knx-agent activity ask --session <id> --question <text> [--mutation <name>]`
- SDK proposal: `client.answer_activity_question(...)`
- MCP proposal: `answer_activity_question`

### 7. Mutation capabilities

#### Capability: `create_mutation`

- Purpose: Create a named parameter-only overlay on the default setup.
- Core request:
  - `session_id`
  - `mutation_name`
  - `description` optional
- Core response:
  - `mutation_name`
  - `mutation_delta_path`
  - `mutation_log_book_path`
- CLI proposal: `knx-agent mutation create --session <id> --name <name> [--description <text>]`
- SDK proposal: `client.create_mutation(...)`
- MCP proposal: `create_mutation`

#### Capability: `set_parameter_override`

- Purpose: Apply a parameter override to a named mutation.
- Core request:
  - `session_id`
  - `mutation_name`
  - `component_selector`
  - `parameter_name`
  - `value`
- Core response:
  - `updated_delta`
  - `affected_component`
  - `log_book_entry_id`
- CLI proposal: `knx-agent mutation set-parameter --session <id> --mutation <name> --component <selector> --parameter <name> --value <value>`
- SDK proposal: `client.set_parameter_override(...)`
- MCP proposal: `set_parameter_override`

#### Capability: `list_mutations`

- Purpose: List named mutations in a session.
- Core request:
  - `session_id`
- Core response:
  - `mutations`
- CLI proposal: `knx-agent mutation list --session <id>`
- SDK proposal: `client.list_mutations(...)`
- MCP proposal: `list_mutations`

### 8. Knowledge capabilities

#### Capability: `fetch_component_details`

- Purpose: Fetch vendor or catalog information to enrich component purpose or behavior.
- Core request:
  - `session_id`
  - `component_selector` optional
  - `manufacturer` optional
  - `product_code` optional
- Core response:
  - `normalized_component_metadata`
  - `purpose_annotations`
  - `behavior_hints`
  - `evidence_sources`
- CLI proposal: `knx-agent knowledge fetch-component-details --session <id> [--component <selector>] [--manufacturer <name>] [--product-code <code>]`
- SDK proposal: `client.fetch_component_details(...)`
- MCP proposal: `fetch_component_details`

## Agent-layer contract notes

- The agent layer should translate short human phrases such as `Kid room blind` into deterministic component queries and ask for clarification when multiple candidates remain.
- The agent layer should use capability responses rather than fabricate names or state.
- Comparison narratives between default and mutated setups belong primarily to the agent layer, built on top of deterministic capability results.

## Output-profile proposal

- `SUMMARY`: topology placement, device-level parameters, basic identity, and purpose annotation when available.
- `MEDIUM`: `SUMMARY` plus additional setup context needed for most troubleshooting questions.
- `FULL`: everything currently available, including group addresses, communication objects, and enriched metadata.# Implementation 003: Proposed Capability APIs

## Purpose

This document proposes the first concrete capability set derived from the clarified use cases in `docs/methodology/001-use-cases-raw.md`. The goal is to define one callable core API that is projected consistently onto the Python SDK, the `typer` CLI, the `mcp` FastMCP tool surface, and the outer agent layer.

## Layer model

### Shared callable core API

- Lives below the SDK and above storage or parsing adapters.
- Owns request validation, session or mutation resolution, business logic, result assembly, provenance, and limitation notes.
- Is the primary target for pytest.
- Any new Python implementation in this layer should land with direct pytest coverage.

### SDK layer

- Exposes the callable core API as stable Python methods and data models.
- Is the canonical programmable surface.

### CLI layer

- Uses `typer`.
- Converts command-line arguments into SDK-facing requests.
- Does not own business rules.

### MCP layer

- Uses the `mcp` package with FastMCP.
- Converts MCP tool inputs into SDK-facing requests.
- Does not own business rules.

### Agent layer

- Accepts natural-language user requests.
- Resolves them into deterministic capability calls.
- Must ask for clarification instead of guessing unresolved identifiers or meanings.

## Cross-surface rules

- Every capability is defined once at the callable core API layer.
- CLI, SDK, and MCP use the same semantic request and response structures.
- Session-scoped capabilities accept `session_id` and may accept `mutation_name` when mutation scope matters.
- Every response should include limitation notes and evidence sources when the answer depends on inference.
- The solution package should be validated with pytest, with core behavior exercised through SDK-facing calls before adapter-level checks.

## Proposed capability groups

### 1. Session capabilities

#### Capability: `create_session`

- Purpose: Create a session bound to a mandatory `.knxproj` path.
- Core request:
  - `project_path`
  - `session_label` optional
- Core response:
  - `session_id`
  - `session_label`
  - `work_directory`
  - `session_state_path`
  - `source_project_absolute_path`
  - `project_refresh_status`
  - `project_import_summary`
- CLI proposal: `knx-agent session create --project <file> [--label <name>]`
- SDK proposal: `client.create_session(project_path=..., session_label=...)`
- MCP proposal: `create_session`

#### Capability: `describe_session`

- Purpose: Return the persisted metadata and current status of a session.
- Core request:
  - `session_id`
- Core response:
  - `session_id`
  - `session_label`
  - `work_directory`
  - `source_project_absolute_path`
  - `project_refresh`
  - `trace_artifacts`
  - `mutation_references`
  - `log_book_references`
  - `latest_state_summary`
- CLI proposal: `knx-agent session describe --session <id>`
- SDK proposal: `client.describe_session(session_id=...)`
- MCP proposal: `describe_session`

#### Capability: `read_session_log_book`

- Purpose: Read the overall session history used for reasoning and auditing.
- Core request:
  - `session_id`
  - `limit` optional
  - `since_entry_id` optional
- Core response:
  - `entries`
  - `truncated`
- CLI proposal: `knx-agent session log-book --session <id> [--limit <n>]`
- SDK proposal: `client.read_session_log_book(session_id=..., limit=...)`
- MCP proposal: `read_session_log_book`

### 2. Setup inspection capabilities

#### Capability: `list_components`

- Purpose: Search components by partial name, purpose, address, or broad listing.
- Core request:
  - `session_id`
  - `query` optional
  - `purpose` optional
  - `detail_level` default `MEDIUM`
  - `mutation_name` optional
- Core response:
  - `matches`
  - `match_count`
  - `detail_level`
  - `ambiguity_flag`
  - `clarification_hint` optional
- CLI proposal: `knx-agent setup list-components --session <id> [--query <text>] [--purpose <text>] [--detail-level SUMMARY|MEDIUM|FULL] [--mutation <name>]`
- SDK proposal: `client.list_components(...)`
- MCP proposal: `list_components`

#### Capability: `describe_component`

- Purpose: Return configuration and topology details for one selected component.
- Core request:
  - `session_id`
  - `component_selector`
  - `detail_level` default `MEDIUM`
  - `mutation_name` optional
- Core response:
  - `component_identity`
  - `topology`
  - `device_parameters`
  - `group_addresses`
  - `communication_objects`
  - `purpose_annotations`
  - `evidence_sources`
- CLI proposal: `knx-agent setup describe-component --session <id> --component <selector> [--detail-level ...] [--mutation <name>]`
- SDK proposal: `client.describe_component(...)`
- MCP proposal: `describe_component`

#### Capability: `summarize_topology`

- Purpose: Summarize areas, lines, rooms if derivable, and component distributions.
- Core request:
  - `session_id`
  - `detail_level` default `MEDIUM`
  - `mutation_name` optional
- Core response:
  - `topology_summary`
  - `component_counts`
  - `purpose_summary`
- CLI proposal: `knx-agent setup summarize-topology --session <id> [--detail-level ...] [--mutation <name>]`
- SDK proposal: `client.summarize_topology(...)`
- MCP proposal: `summarize_topology`

#### Capability: `trace_group_flow`

- Purpose: Show participants and propagation paths for a group address or communication object.
- Core request:
  - `session_id`
  - `group_address` optional
  - `communication_object_ref` optional
  - `mutation_name` optional
- Core response:
  - `participants`
  - `propagation_path`
  - `unresolved_links`
- CLI proposal: `knx-agent setup trace-group-flow --session <id> [--group-address <ga> | --object-ref <ref>] [--mutation <name>]`
- SDK proposal: `client.trace_group_flow(...)`
- MCP proposal: `trace_group_flow`

### 3. Environment capabilities

#### Capability: `list_environment_inputs`

- Purpose: Show sensor-oriented environment inputs that can drive the system.
- Core request:
  - `session_id`
  - `query` optional
  - `purpose` optional
  - `mutation_name` optional
- Core response:
  - `inputs`
  - `current_values`
  - `value_sources`
- CLI proposal: `knx-agent environment list-inputs --session <id> [--query <text>] [--purpose <text>] [--mutation <name>]`
- SDK proposal: `client.list_environment_inputs(...)`
- MCP proposal: `list_environment_inputs`

#### Capability: `set_environment_value`

- Purpose: Set or override an environment-model value by sensor-oriented name.
- Core request:
  - `session_id`
  - `sensor_name`
  - `value`
  - `mutation_name` optional
  - `reason` optional
- Core response:
  - `accepted_value`
  - `normalized_knx_value`
  - `updated_environment_element`
  - `log_book_entry_id`
- CLI proposal: `knx-agent environment set-value --session <id> --sensor <name> --value <value> [--mutation <name>]`
- SDK proposal: `client.set_environment_value(...)`
- MCP proposal: `set_environment_value`

### 4. Trace ingestion capabilities

#### Capability: `load_bus_trace`

- Purpose: Load a bus trace into the session.
- Core request:
  - `session_id`
  - `trace_path`
- Core response:
  - `trace_id`
  - `packet_count`
  - `decode_warnings`
  - `observed_address_summary`
  - `log_book_entry_id`
- CLI proposal: `knx-agent trace load --session <id> --path <file>`
- SDK proposal: `client.load_bus_trace(...)`
- MCP proposal: `load_bus_trace`

#### Capability: `infer_environment_from_trace`

- Purpose: Infer environment values and user actions from trace evidence.
- Core request:
  - `session_id`
  - `trace_id`
  - `time_window` optional
  - `mutation_name` optional
- Core response:
  - `inferred_environment_values`
  - `candidate_user_actions`
  - `confidence_scores`
  - `evidence_packets`
- CLI proposal: `knx-agent trace infer-environment --session <id> --trace <id> [--mutation <name>]`
- SDK proposal: `client.infer_environment_from_trace(...)`
- MCP proposal: `infer_environment_from_trace`

### 5. User-action capabilities

#### Capability: `resolve_user_action_candidates`

- Purpose: Resolve a human-facing user action description into candidate KNX-level actions.
- Core request:
  - `session_id`
  - `action_query`
  - `mutation_name` optional
- Core response:
  - `candidates`
  - `ambiguity_flag`
  - `clarification_hint` optional
- CLI proposal: `knx-agent action resolve --session <id> --query <text> [--mutation <name>]`
- SDK proposal: `client.resolve_user_action_candidates(...)`
- MCP proposal: `resolve_user_action_candidates`

#### Capability: `inject_user_action`

- Purpose: Apply a resolved user action and update KNX system state.
- Core request:
  - `session_id`
  - `action_reference`
  - `gesture` optional
  - `mutation_name` optional
- Core response:
  - `resolved_knx_activity`
  - `state_update_summary`
  - `log_book_entry_id`
- CLI proposal: `knx-agent action inject --session <id> --action <ref> [--gesture <name>] [--mutation <name>]`
- SDK proposal: `client.inject_user_action(...)`
- MCP proposal: `inject_user_action`

### 6. Activity-question capabilities

#### Capability: `answer_activity_question`

- Purpose: Answer `should`, `why`, `why not`, `what changed`, or `what input caused this` questions about the latest KNX system state.
- Core request:
  - `session_id`
  - `question`
  - `mutation_name` optional
- Core response:
  - `answer`
  - `confidence`
  - `evidence_sources`
  - `unresolved_assumptions`
  - `needed_inputs`
  - `log_book_entry_id`
- CLI proposal: `knx-agent activity ask --session <id> --question <text> [--mutation <name>]`
- SDK proposal: `client.answer_activity_question(...)`
- MCP proposal: `answer_activity_question`

### 7. Mutation capabilities

#### Capability: `create_mutation`

- Purpose: Create a named parameter-only overlay on the default setup.
- Core request:
  - `session_id`
  - `mutation_name`
  - `description` optional
- Core response:
  - `mutation_name`
  - `mutation_delta_path`
  - `mutation_log_book_path`
- CLI proposal: `knx-agent mutation create --session <id> --name <name> [--description <text>]`
- SDK proposal: `client.create_mutation(...)`
- MCP proposal: `create_mutation`

#### Capability: `set_parameter_override`

- Purpose: Apply a parameter override to a named mutation.
- Core request:
  - `session_id`
  - `mutation_name`
  - `component_selector`
  - `parameter_name`
  - `value`
- Core response:
  - `updated_delta`
  - `affected_component`
  - `log_book_entry_id`
- CLI proposal: `knx-agent mutation set-parameter --session <id> --mutation <name> --component <selector> --parameter <name> --value <value>`
- SDK proposal: `client.set_parameter_override(...)`
- MCP proposal: `set_parameter_override`

#### Capability: `list_mutations`

- Purpose: List named mutations in a session.
- Core request:
  - `session_id`
- Core response:
  - `mutations`
- CLI proposal: `knx-agent mutation list --session <id>`
- SDK proposal: `client.list_mutations(...)`
- MCP proposal: `list_mutations`

### 8. Knowledge capabilities

#### Capability: `fetch_component_details`

- Purpose: Fetch vendor or catalog information to enrich component purpose or behavior.
- Core request:
  - `session_id`
  - `component_selector` optional
  - `manufacturer` optional
  - `product_code` optional
- Core response:
  - `normalized_component_metadata`
  - `purpose_annotations`
  - `behavior_hints`
  - `evidence_sources`
- CLI proposal: `knx-agent knowledge fetch-component-details --session <id> [--component <selector>] [--manufacturer <name>] [--product-code <code>]`
- SDK proposal: `client.fetch_component_details(...)`
- MCP proposal: `fetch_component_details`

## Agent-layer contract notes

- The agent layer should translate short human phrases such as `Kid room blind` into deterministic component queries and ask for clarification when multiple candidates remain.
- The agent layer should use capability responses rather than fabricate names or state.
- Comparison narratives between default and mutated setups belong primarily to the agent layer, built on top of deterministic capability results.

## Output-profile proposal

- `SUMMARY`: topology placement, device-level parameters, basic identity, and purpose annotation when available.
- `MEDIUM`: `SUMMARY` plus additional setup context needed for most troubleshooting questions.
- `FULL`: everything currently available, including group addresses, communication objects, and enriched metadata.