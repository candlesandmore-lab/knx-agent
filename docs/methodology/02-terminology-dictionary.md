<!-- Copyright (c) 2026 agent-building-agent contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Source: https://TBD (training course) -->

# Terminology Dictionary

This file is the single source of truth for the canonical-term rule and the current set of
verified canonical terms. `story-telling-agent` and `review-validation-agent` read it at
runtime, and every other instructed agent consults it per its own terminology-dictionary
consultation instructions before making a terminology or naming decision.

## Canonical-Term Rule

- Terminology consistency: use one canonical term for each concept inside a story or review.
  Do not introduce synonyms or alias terms for the same thing. When a todo or story draft uses
  a different term for an existing concept, map it to the canonical term and record the
  mapping.
- Alias terms: the same concept referred to by more than one term inside a story, or across a
  todo and a story, must be flagged and resolved to one canonical term rather than left to
  coexist.
- Ambiguity handling: when a todo, story draft, or reviewed content contains holes,
  ambiguities, or contradictions, do not auto-select among the possible interpretations.
  Record each as an entry in `story.open_questions` with at least `question` and `options`,
  and ask the user to choose. Only after the user decides may the story proceed.

## Canonical Terms

| Term | Canonical form | Notes |
| --- | --- | --- |
| Tool surface | Tool surface | Refers to a CLI, SDK, or MCP API exposure of a capability. |
| Capability | Capability | A user-meaningful operation provided by the shared Python core and projected consistently across tool surfaces. |
| Shared Python core | Shared Python core | The canonical implementation layer that owns domain behavior, request handling, result models, and business rules for all surfaces. |
| Contract | Contract | The structured request and response model for a capability, independent of whether it is invoked by CLI, SDK, or MCP. |
| Project graph | Project graph | The normalized in-memory representation of a `.knxproj` installation, including topology, components, group addresses, communication objects, parameters, and provenance. |
| KNX system setup | KNX system setup | The imported default configuration derived from the bound `.knxproj` file, including components, parameters, topology, group addresses, and communication objects. |
| Component typing | Component typing | The classification of components and component roles derived from `.knxproj` contents and optionally refined by enrichment logic. |
| Location | Location | A space of the ETS location tree of a project (Building, Floor, Room, Corridor, DistributionBoard, ...) in which components are placed. Components that are not placed have no location. |
| Instance path | Instance path (`instance_path`) | The full path of a component in the ETS location tree including the component name, segments separated by `/`, for example `Haus/EG/Wohnzimmer/Taster 1`. Usable as a component selector (partial, case-insensitive segments) and returned as the output field `instance_path`; does not exist for components that are not placed in a location. |
| Component selector | Component selector (`component_selector`) | The value that selects components by display name, instance path, individual address or ETS id (docs/implementation/003 convention C3). The optional `selector_kind` disambiguates it. |
| Selector kind | Selector kind (`selector_kind`) | The kind of a component selector value: `ANY` (default, auto-detect), `NAME`, `INSTANCE_PATH`, `INDIVIDUAL_ADDRESS` or `ETS_ID`. An explicit kind that does not fit the value is `INVALID_REQUEST`. |
| Match kinds | Match kinds (`match_kinds`) | The sorted, duplicate-free set of selector kinds through which a component matched a component selector under `ANY`. |
| Communication object | Communication object | A single group-communication endpoint of a component, with direction flags and datapoint type, linked to group addresses; addressed in `communication_object_ref` as `<component id>/co/<ref id>`. |
| ETS id | ETS id | The `Id` attribute ETS assigns to an element of the project XML. For a component it is the component node id (for example `P-051B-0_DI-6`); for a communication object it is the composite node id `<component id>/co/<ref id>`. |
| Direction label | Direction label | The role of a communication object for a group address in `trace_group_flow`: `SENDER`, `RECEIVER`, `SENDER_RECEIVER` or `UNDETERMINED`, derived only from the ETS communication object flags (transmit, write, update; the read flag adds the role `ANSWERS_READ`), never from the order of group address links. |
| Trace observation | Trace observation | A timestamped decoded fact extracted from a KNX bus monitor trace, linked to packet evidence and address interpretation. |
| Observed fact | Observed fact | A fact derived from recorded or live KNX telegram activity rather than directly from the ETS project. |
| Source fact | Source fact | A fact imported directly from the `.knxproj` without interpretation beyond parsing and normalization. |
| Derived fact | Derived fact | A fact computed from source facts or observed facts, such as reverse indexes, inferred participant lists, or event propagation paths. |
| Enriched fact | Enriched fact | A fact added from external component knowledge, vendor documentation, curated rules, or later adapter logic, with explicit provenance. |
| Scenario state | Scenario state | The session-scoped ordered inputs (environment values, user actions, trace loads) of a setup that produce its current system state, kept separate from source facts. It is not resettable; restart by creating a new session. |
| Environment model | Environment model | The session-scoped model of primary environmental inputs, such as sensor-oriented lux or temperature values, that can drive KNX component behavior. |
| KNX system state | KNX system state | The simulated or observed current state of the KNX installation after processing ordered inputs, trace observations, and resulting component communication. |
| Environment condition | Environment condition | A normalized representation of contextual state relevant to KNX behavior, such as room temperature, sun exposure, wind alarm, occupancy, or time-of-day. |
| Injected event | Injected event | A user-supplied or tool-generated stimulus introduced into the simulation, such as a button press, sensor update, or scheduled trigger. |
| Expected reaction | Expected reaction | The predicted downstream behavior of components, group objects, or environment-dependent logic for a given project graph and scenario state. |
| Evidence source | Evidence source | The origin of a conclusion or result element, such as `.knxproj` structure, trace evidence, vendor documentation, or simulation rules. |
| Provenance | Provenance | The metadata that explains where a fact came from, how it was inferred, and which artifacts or packets support it. |
| Confidence | Confidence | An explicit measure of how strongly the system stands behind an inferred or enriched statement, especially for trace-derived environment conditions. |
| Investigation session | Investigation session | The bounded working context for analyzing one project, optional trace inputs, scenario state, and generated hypotheses. |
| session_label | `session_label` | The identifier chosen by the user at `create_session` (required, unique within the workspace) and used to address an investigation session on every CLI, SDK, and MCP tool surface. Replaces `session identifier`, `session_id`, `session_handle`, `session_token`, and `label`. |
| Work-directory | Work-directory | The session-unique filesystem directory that stores persistent artifacts for an investigation session, including `session-state.yaml` and future session-scoped files. |
| Session root | Session root | The folder that holds one work-directory per investigation session (`<session root>/<session_label>`). Defaults to `./.knx-agent/sessions` and is set only through the `--session-root` option (CLI, MCP server startup) or the `session_root=` parameter (SDK); never through an environment variable. Replaces `sessions directory`, `session base folder`, and `work-directory root`. |
| Session state | Session state | The persisted metadata for an investigation session, stored in `session-state.yaml`, including the source `.knxproj` input and other session-scoped facts, references, and settings. |
| KNX session log book | KNX session log book | The ordered session history of significant actions, inputs, assumptions, answers, refresh events, and mutations that the outer agent layer can use for reasoning and explanation. |
| Source project path | Source project path | The full absolute filesystem path of the `.knxproj` file that is mandatory at session creation time and remains bound to the session for later refresh checks. |
| Project refresh check | Project refresh check | The per-call detection step that compares the bound `.knxproj` file on disk with the session's imported project metadata and triggers re-reading when the file has changed. |
| Diagnostic hypothesis | Diagnostic hypothesis | A falsifiable explanation for observed misbehavior that the agent can test by querying configuration, trace evidence, or simulation outcomes. |
| Deterministic run | Deterministic run | A repeatable execution of a capability through CLI, SDK, or MCP that produces the same structured result for the same inputs and configuration. |
| Session-scoped capability | Session-scoped capability | A capability that requires a `session_label` to resolve which project graph, trace observations, and scenario state should be used. |
| Mutation | Mutation | A named parameter-only overlay on top of the default KNX system setup within a session. |
| Mutation delta | Mutation delta | The persisted set of changed parameter values that differentiates a mutation from the default KNX system setup. |
| Agent layer | Agent layer | The instructed agent or skill package that turns natural-language user requests into explicit capability calls against the SDK, CLI, or MCP tool surfaces. |
| Capability parity | Capability parity | The requirement that supported capabilities behave consistently across CLI, SDK, and MCP, using the same contracts and domain-core logic. |
| Surface drift | Surface drift | An unwanted difference in behavior, naming, payload shape, or semantics between tool surfaces for the same capability. |
| License decision | License decision | The recorded assessment that a Python dependency's license is acceptable or unacceptable for use in this solution. |
| Free-to-use license | Free-to-use license | A software license that permits the intended development, local use, internal use, and redistribution model of this project without paid-use restrictions. |
| mutation_name | `mutation_name` | The parameter naming a mutation: the user-defined name given at creation. On capability calls it optionally overrides the target setup for that call only; it never changes the active setup. |
| Mutation log book | Mutation log book | The per-mutation history of actions on that mutation; those actions are also written to the KNX session log book, subject to log level. |
| Default setup | Default setup | The unmutated KNX system setup imported from the `.knxproj`; its setup name is `default`. |
| Active setup | Active setup | The setup (default setup or a mutation) that capability calls act on unless `mutation_name` overrides it for one call; changed only by `select_setup`. |
| Current system state | Current system state ("now") | The persistent KNX system state of a setup after all ordered prior inputs, persisted after every operation; `unknown` is a valid value. |
| Component | Component | The canonical term for a KNX device-like entity in the KNX system setup, in capability names, parameters, and docs. Replaces `device`, `object`, and `element`. |
| Selector | Selector | How a component or group address is identified in a request: display name (partial match), instance path (partial match), individual address (exact), ETS id (exact). An ambiguous query returns a set. |
| Detail level | Detail level | `SUMMARY`, `MEDIUM` (default), or `FULL`; controls how much a descriptive capability returns. |
| Log level | Log level | `INFO` (default), `DEBUG`, or `FULL`; governs what is written to the log books; chosen per CLI/SDK call or at MCP server startup, not stored per session. |
| Capability catalogue | Capability catalogue | `docs/implementation/003-proposed-capability-apis.md`, the single authoritative list of capabilities. Status `reviewed draft` until the story in `development/todos/13-fixtures-and-end-to-end-validation.md` passes; changes after that need a catalogue update plus a review cycle. |
| create_session | `create_session` | Capability: creates an investigation session from a `.knxproj` path and a user-chosen unique `session_label` (no uploaded artifact handle). |
| reimport_system_definition | `reimport_system_definition` | Capability: re-reads the bound `.knxproj` for an existing session. Replaces `refresh`, `refresh_session`, `load_project`. |
| select_setup | `select_setup` | Capability: switches the active setup to the default (no name) or an existing mutation and reports its current system state summary. |
| describe_session | `describe_session` | Capability: persisted metadata and status of a session, including setups and their state summaries. |
| list_components | `list_components` | Capability: queries or lists components by selector at a detail level. |
| describe_component | `describe_component` | Capability: configuration and topology of selected components. Replaces `describe_device`. |
| summarize_topology | `summarize_topology` | Capability: summarizes areas, lines, rooms if derivable, and component distribution. |
| trace_group_flow | `trace_group_flow` | Capability: participants and propagation path of a group address or communication object. Also covers group address lookup. |
| list_environment_inputs | `list_environment_inputs` | Capability: lists environment inputs with current values. Also covers reading a value. |
| set_environment_value | `set_environment_value` | Capability: sets an environment-model value for a sensor and updates the current system state. |
| load_bus_trace | `load_bus_trace` | Capability: loads a bus trace, updates environment and system state, and returns inferred values with evidence. Absorbs `infer_environment_from_trace` and `decode_telegram`. |
| resolve_user_action_candidates | `resolve_user_action_candidates` | Capability: resolves a component and control into candidate KNX-level actions. |
| inject_user_action | `inject_user_action` | Capability: applies a resolved user action and updates the current system state. |
| answer_activity_question | `answer_activity_question` | The single capability answering should, why, why not, what changed, and what input caused this questions about now. Replaces `explain_expected_reaction`, `list_possible_causes`, `compare_expected_vs_observed`, and `simulate_outcome`. |
| read_session_log_book | `read_session_log_book` | Capability: reads the session log book, or a mutation log book when `mutation_name` is given. Replaces `summarize_recent_activity` and `read_mutation_log_book`. |
| create_mutation | `create_mutation` | Capability: creates a named parameter-only mutation seeded from a copy of the default setup's current environment model and input history; mutations of mutations are not supported. |
| set_parameter_override | `set_parameter_override` | Capability: sets a component parameter in a mutation. |
| list_mutations | `list_mutations` | Capability: lists mutations with details. Replaces `describe_mutation`. |
| fetch_component_details | `fetch_component_details` | Capability: fetches vendor or catalogue information including behavior hints. Replaces `extract_behavior_hints`. |
| KnxSessionClient | `KnxSessionClient` | The SDK entry-point class in `knx_agent.sdk`; exposes catalogue capabilities as methods (`client.<capability>(...)`) and delegates to the shared Python core. Not `KnxClient`. |
| Reviewed draft | Reviewed draft | Document status of a catalogue or specification that passed review but is not yet frozen; it becomes frozen only when its stated freeze condition is met (for the capability catalogue: todo 13 end-to-end validation passes). Changes after freezing need a catalogue update plus a review cycle. |
| Limitation note | Limitation note | An explicit statement in a result or document that describes unsupported behavior, ambiguity, missing evidence, or partial coverage. |

### Replaced aliases

Do not use the replaced term; use the replacement. These terms may appear only in this table, in the
replaced-names table of the capability catalogue, and in historical todos and stories.

| Replaced term | Replacement | Notes |
| --- | --- | --- |
| device, object, element, `describe_device`, device typing | component, `describe_component`, component typing | |
| `session identifier`, `session_id`, `session_handle`, `session_token`, `label` | `session_label` | |
| `refresh`, `refresh_session`, `load_project`, `project load` | `reimport_system_definition` | |
| `explain_expected_reaction`, `list_possible_causes`, `simulate_outcome` | `answer_activity_question` | |
| `compare_expected_vs_observed`, original-versus-mutated comparison | agent layer (no core capability) | |
| `summarize_recent_activity`, `read_mutation_log_book` | `read_session_log_book` | |
| `infer_environment_from_trace`, `decode_telegram` | `load_bus_trace` | merged |
| `inject_event`, `set_environment_state` | `inject_user_action`, `set_environment_value` | |
| `find_group_address` | `trace_group_flow` | |
| `get_environment_value` | `list_environment_inputs` | |
| `describe_mutation` | `list_mutations` | |
| `extract_behavior_hints` | `fetch_component_details` | |
| `show_evidence_sources` | none | dropped; evidence is embedded in every response |
| `reset_state`, `reset_scenario` | none | dropped; create a new session |
| uploaded artifact handle (for `create_session`) | none | dropped; path only |
| `purpose` request parameter | none | dropped from core; the agent layer resolves purposes via query capabilities |

### Term preferences

- Reuse the exact canonical term names in new architecture and implementation docs, CLI help, SDK docstrings, MCP tool descriptions, tests, review notes and agent prompts.
- If a new term becomes foundational across several documents or tool surfaces, add it to the table above instead of redefining it locally.
- Prefer `tool surface` over `interface` when discussing CLI, SDK, and MCP exposure together.
- Prefer `capability` over `feature` when referring to a concrete operation with a request and response contract.
- Prefer `project graph` over `model` when referring specifically to imported KNX installation structure.
- Prefer `trace observation` or `observed fact` over `trace data` when the content has already been decoded.
- Prefer `evidence source` and `provenance` when explaining why a result was produced.
- Prefer `investigation session` or `session` over `workspace` when referring to the user-visible unit of analysis.
- Prefer `KNX system setup` for imported defaults, `environment model` for primary inputs, and `KNX system state` for resulting simulated or observed state.

### Candidate terms (not yet defined)

Likely to matter later; add a row to the table when one is introduced:

- datapoint typing
- telegram decoding
- actor versus sensor role
- state alignment
- observation window
- scenario merge policy
- rule coverage
- unsupported inference
- session activation
- session persistence

## Maintenance Rule

Add a new row to the Canonical Terms table whenever a review round finds a term used
inconsistently across stories, docs, or agent prose, or whenever a genuinely new, reusable
concept is being introduced into the workflow. Indicative signals that a new concept warrants a
row -- the term is likely to recur across multiple future stories, it names a new agent role or
mechanism, or it is already used consistently by more than one doc/agent -- guide this judgment;
there is no hard mechanical threshold to satisfy. Either way, confirm the resolved canonical form
with the user before recording it.
