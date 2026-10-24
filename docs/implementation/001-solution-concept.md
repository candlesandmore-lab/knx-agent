# Implementation 001: Solution Concept

## Implementation spec update package

- target_documents:
  - `docs/implementation/001-solution-concept.md`
- topics_added_or_updated:
  - user outcomes
  - operating modes
  - domain model responsibilities
  - proposed capability families
  - scenario input concept
  - trace-backed environment inference
  - capability surface parity
  - investigation session model
  - mutation handling
  - agent-layer behavior
- interface_or_prompt_contracts:
  - Prompt contract for natural-language troubleshooting sessions.
  - Unified CLI, SDK, and MCP contract families for session, setup, environment, user-action, activity-question, and mutation operations.
- validation_expectations:
  - The concept must clearly separate source facts, inferred behavior, and simulated state.
  - Each MCP tool family must map to a user troubleshooting job.
  - The document must treat optional bus-trace support as a first-class evidence source without requiring traces for every session.
  - The document must require capability parity across CLI, SDK, and MCP for supported operations.
- dependencies:
  - `docs/architecture/001-knx-investigation-platform.md`

## Product concept

The first usable version of the platform is an investigation copilot for a single KNX project at a time. A user or agent first creates an investigation session anchored by an ETS project. That session receives a unique session identifier and work-directory with a `session-state.yaml` file. Within that session, the user or agent can add bus monitor traces, describe the symptom in plain language, supply additional scenario conditions, and ask the agent to explain what should happen and why it is not happening.

The `.knxproj` file is mandatory when the session is created. The session remains bound to the full absolute path of that file, and every CLI, SDK, or MCP call must refresh the imported project state if the file changed on disk.

The same capabilities should be consumable three ways:

- by the agent through MCP,
- by an operator through deterministic CLI commands, and
- by developers or automation through a Python SDK.

The implementation rule is that CLI and MCP do not own separate business logic. They call the same core API that is exposed through the SDK, which makes SDK-based pytest coverage the first validation path before human CLI use or agent MCP use.

The solution also includes an agent or skill layer that sits above these tool surfaces. That layer is responsible for resolving natural-language requests into deterministic capability calls without guessing unresolved component identity or missing context.

## Primary user jobs

1. Create or reopen an investigation session for a KNX project.
2. Understand installation structure.
2. Trace which devices and group objects participate in a behavior.
3. Ask what should happen if an input changes.
4. Compare expected versus observed behavior.
5. Inspect whether a device parameter or group assignment looks suspicious.
6. Recover likely system-environment conditions from recent telegram history when those conditions are encoded indirectly in bus traffic.
7. Run parameter-only what-if mutations in parallel and question them independently.

## Operating modes

### Configuration exploration mode

- Answers questions like “which devices listen to this group address?” or “what actuator should react to this button?”

### Session management mode

- Creates, opens, and describes investigation sessions.
- Anchors every analysis run to a session identifier and session work-directory.
- Requires a `.knxproj` path when creating a session and persists that path as an absolute reference.
- Detects source-project updates on every tool-surface call and re-reads the project automatically when needed.
- Allows CLI and SDK callers to supply an explicit session identifier for deterministic execution.

### Setup inspection mode

- Queries the KNX system setup by partial name, exact name, purpose, address, or broad listing.
- Supports detail levels with `MEDIUM` as the default.
- Returns sets when the selector is ambiguous rather than guessing.

### Expectation mode

- Answers questions like “if this push button sends `1`, which objects should change and which outputs should switch?”

### Trace interpretation mode

- Accepts live or recorded bus monitor traces when available.
- Decodes telegram sequences into observed actions, measured values, and candidate environment conditions.
- Feeds those observations into troubleshooting and simulation as evidence rather than replacing project facts.

### Scenario simulation mode

- Accepts user-provided environmental context, such as “room is 29 degrees, the sun is strong on the south facade, wind alarm is active, and the blind-up key was pressed once.”
- Produces a predicted chain of effects with confidence and provenance.

### Mutation analysis mode

- Creates named parameter-only mutations as deltas over the default KNX system setup.
- Lets later capability calls target either the default setup or a named mutation.
- Persists mutation-specific files and mutation-specific log books in the session work-directory.

### Knowledge enrichment mode

- Fetches device-family details or manuals when ETS metadata alone is insufficient.
- Normalizes those findings into simulation hints or troubleshooting notes.

## Shared domain concepts

### Source facts

- Imported directly from `.knxproj`.
- Immutable within a troubleshooting session unless the project is reloaded.

### Observed facts

- Imported from bus monitor traces.
- Timestamped and tied to decoded telegram evidence.
- May reveal control actions or measured values without proving the underlying installer intent.

### Derived facts

- Computed from source facts, such as reverse indexes, device-to-group maps, and event propagation paths.

### Enriched facts

- Added from vendor documentation or curated adapters.
- Must retain provenance and confidence.

### Scenario facts

- Represent assumed current conditions, manually injected events, and accepted trace-derived environment hints.
- Must be session-scoped and resettable.

### Environment model facts

- Represent primary environment inputs by sensor-oriented name.
- Normalize values to KNX datatypes from ETS.
- Follow `last come wins` semantics when later values target the same environment element.

### KNX system state facts

- Represent the latest resulting state after ordered inputs, trace observations, and simulated ripple-down communication.
- Are the basis for answering `should`, `why`, `why not`, and `what changed` style questions about `now`.

### Session facts

- Include the bound source `.knxproj` absolute path, session identifier, work-directory path, project-import fingerprint, trace artifact references, and active scenario metadata.
- Persist in `session-state.yaml` and evolve as the session gains more artifacts.

### Mutation facts

- Include mutation name, mutation delta file references, mutation-specific log book reference, and active parameter overrides.
- Are session-scoped and optional on capability calls.

## Proposed capability families

These tool families define capability areas only. The concrete APIs, command shapes, SDK call signatures, and MCP tool contracts should be finalized from user-provided use cases rather than from this bootstrap document alone. Each resulting capability must then be surfaced consistently as CLI commands, SDK entry points, and MCP tools.

### Session capabilities

- `create_session`
- `describe_session`
- `load_project`

### Setup inspection capabilities

- `summarize_topology`
- `list_components`
- `find_group_address`
- `describe_device`
- `trace_group_flow`

### Trace ingestion capabilities

- `load_bus_trace`
- `decode_telegram`
- `infer_environment_from_trace`
- `summarize_recent_activity`

### Environment capabilities

- `list_environment_inputs`
- `set_environment_value`
- `get_environment_value`

### User-action capabilities

- `inject_user_action`
- `resolve_user_action_candidates`

### Activity-question capabilities

- `explain_expected_reaction`
- `list_possible_causes`
- `compare_expected_vs_observed`

### Mutation capabilities

- `create_mutation`
- `list_mutations`
- `set_parameter_override`
- `describe_mutation`

### Scenario capabilities

- `set_environment_state`
- `inject_event`
- `simulate_outcome`
- `reset_scenario`

### Knowledge capabilities

- `fetch_component_details`
- `extract_behavior_hints`
- `show_evidence_sources`

### Log-book capabilities

- `read_session_log_book`
- `read_mutation_log_book`

These names are placeholders for planning discussion, not a locked public API.

## Dependency policy

- Python packages used by the solution must have a free-to-use license compatible with development, distribution, and commercial or internal operational use.
- License review is part of dependency selection, not a later packaging task.
- If a desired package is license-ambiguous or usage-restricted, the design should prefer an alternative package or an in-house adapter.
- The CLI tool surface should use the `typer` package.
- The MCP tool surface should use the `mcp` package with FastMCP.

## Agent interaction model

The conversational agent should prefer a loop of:

1. restate the symptom as a falsifiable hypothesis,
2. resolve or create the relevant investigation session,
3. inspect the KNX system setup, environment model, and named mutation context,
4. inspect bus-trace evidence when available,
5. resolve or clarify any ambiguous names instead of guessing,
6. simulate the expected chain,
7. compare that chain with the user’s reported observation and trace evidence,
8. present the most likely explanations and the next discriminating checks.

## Conceptual data flow

1. User or agent creates or opens an investigation session with a `.knxproj` input.
2. Session service creates the session work-directory and persists `session-state.yaml`.
3. Import service builds the normalized KNX project graph from the bound absolute project path, including device typing discovered from the project.
4. On every later tool-surface call, session service checks whether the bound project file changed and refreshes imported project state before continuing when needed.
5. Trace service decodes telegram evidence into observed facts when traces are available.
6. Agent asks the tool surfaces for relevant setup data, observed activity, environment inputs, and expected behavior within the selected session.
7. User or agent sets additional scenario conditions or mutation-scoped parameter overrides.
8. Simulation engine produces expected transitions and the latest KNX system state.
9. Log-book state is updated.
10. Agent reports explanation, uncertainty, and recommended next checks.

## Assumptions for the bootstrap phase

- One project is active at a time.
- One investigation session is anchored by one starting `.knxproj` file.
- That starting `.knxproj` file is mandatory and stored as a full absolute path in session state.
- The first domain core is Python because parsing, rule engines, and MCP server tooling are straightforward there.
- The initial simulation engine will be declarative and rule-based rather than a full continuous-time model.
- Device categories are discovered from the `.knxproj` and then enriched incrementally.
- Some device types will only have partial support in the first release.
- The shared Python core is the single implementation authority behind CLI, SDK, and MCP surfaces.
- The SDK-facing core API is the primary test target for pytest; CLI and MCP are verified mainly as adapters over that API.
- Session persistence starts with a session-unique work-directory and a YAML session-state file.
- Project refresh checks happen on every CLI, SDK, and MCP capability call.
- Parameter-only mutations are the first supported what-if mechanism.
- The outer agent layer must ask clarifying questions instead of guessing unresolved names, rooms, or actions.

## Information we still need from you

1. Sample `.knxproj` files or a sanitized structural description.
2. Sample KNX bus monitor traces if you want trace-driven environment inference to be exercised early.
3. Preferred hosting mode for the MCP server.
4. Which bus-monitor trace formats or export styles you expect to use first.
5. Priority troubleshooting use cases that should drive the first concrete API definitions.