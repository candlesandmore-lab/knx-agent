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
| Project graph | Project graph | The normalized in-memory representation of a `.knxproj` installation, including topology, devices, group addresses, communication objects, parameters, and provenance. |
| KNX system setup | KNX system setup | The imported default configuration derived from the bound `.knxproj` file, including devices, parameters, topology, group addresses, and communication objects. |
| Device typing | Device typing | The classification of devices and device roles derived from `.knxproj` contents and optionally refined by enrichment logic. |
| Trace observation | Trace observation | A timestamped decoded fact extracted from a KNX bus monitor trace, linked to packet evidence and address interpretation. |
| Observed fact | Observed fact | A fact derived from recorded or live KNX telegram activity rather than directly from the ETS project. |
| Source fact | Source fact | A fact imported directly from the `.knxproj` without interpretation beyond parsing and normalization. |
| Derived fact | Derived fact | A fact computed from source facts or observed facts, such as reverse indexes, inferred participant lists, or event propagation paths. |
| Enriched fact | Enriched fact | A fact added from external component knowledge, vendor documentation, curated rules, or later adapter logic, with explicit provenance. |
| Scenario state | Scenario state | The session-scoped state used for simulation, containing verbal assumptions, injected events, and accepted trace-derived context while remaining separate from source facts. |
| Environment model | Environment model | The session-scoped model of primary environmental inputs, such as sensor-oriented lux or temperature values, that can drive KNX component behavior. |
| KNX system state | KNX system state | The simulated or observed current state of the KNX installation after processing ordered inputs, trace observations, and resulting component communication. |
| Environment condition | Environment condition | A normalized representation of contextual state relevant to KNX behavior, such as room temperature, sun exposure, wind alarm, occupancy, or time-of-day. |
| Injected event | Injected event | A user-supplied or tool-generated stimulus introduced into the simulation, such as a button press, sensor update, or scheduled trigger. |
| Expected reaction | Expected reaction | The predicted downstream behavior of devices, group objects, or environment-dependent logic for a given project graph and scenario state. |
| Evidence source | Evidence source | The origin of a conclusion or result element, such as `.knxproj` structure, trace evidence, vendor documentation, or simulation rules. |
| Provenance | Provenance | The metadata that explains where a fact came from, how it was inferred, and which artifacts or packets support it. |
| Confidence | Confidence | An explicit measure of how strongly the system stands behind an inferred or enriched statement, especially for trace-derived environment conditions. |
| Investigation session | Investigation session | The bounded working context for analyzing one project, optional trace inputs, scenario state, and generated hypotheses. |
| Session identifier | Session identifier | The unique stable identifier used to address an investigation session across CLI, SDK, and MCP tool surfaces. |
| Work-directory | Work-directory | The session-unique filesystem directory that stores persistent artifacts for an investigation session, including `session-state.yaml` and future session-scoped files. |
| Session state | Session state | The persisted metadata for an investigation session, stored in `session-state.yaml`, including the source `.knxproj` input and other session-scoped facts, references, and settings. |
| KNX session log book | KNX session log book | The ordered session history of significant actions, inputs, assumptions, answers, refresh events, and mutations that the outer agent layer can use for reasoning and explanation. |
| Source project path | Source project path | The full absolute filesystem path of the `.knxproj` file that is mandatory at session creation time and remains bound to the session for later refresh checks. |
| Project refresh check | Project refresh check | The per-call detection step that compares the bound `.knxproj` file on disk with the session's imported project metadata and triggers re-reading when the file has changed. |
| Diagnostic hypothesis | Diagnostic hypothesis | A falsifiable explanation for observed misbehavior that the agent can test by querying configuration, trace evidence, or simulation outcomes. |
| Deterministic run | Deterministic run | A repeatable execution of a capability through CLI, SDK, or MCP that produces the same structured result for the same inputs and configuration. |
| Session-scoped capability | Session-scoped capability | A capability that requires a session identifier or active session context to resolve which project graph, trace observations, and scenario state should be used. |
| Mutation | Mutation | A named parameter-only overlay on top of the default KNX system setup within a session. |
| Mutation delta | Mutation delta | The persisted set of changed parameter values that differentiates a mutation from the default KNX system setup. |
| Agent layer | Agent layer | The instructed agent or skill package that turns natural-language user requests into explicit capability calls against the SDK, CLI, or MCP tool surfaces. |
| Capability parity | Capability parity | The requirement that supported capabilities behave consistently across CLI, SDK, and MCP, using the same contracts and domain-core logic. |
| Surface drift | Surface drift | An unwanted difference in behavior, naming, payload shape, or semantics between tool surfaces for the same capability. |
| License decision | License decision | The recorded assessment that a Python dependency's license is acceptable or unacceptable for use in this solution. |
| Free-to-use license | Free-to-use license | A software license that permits the intended development, local use, internal use, and redistribution model of this project without paid-use restrictions. |
| Limitation note | Limitation note | An explicit statement in a result or document that describes unsupported behavior, ambiguity, missing evidence, or partial coverage. |

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
