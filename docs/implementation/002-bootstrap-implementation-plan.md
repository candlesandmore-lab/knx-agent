# Implementation 002: Bootstrap Implementation Plan

## Implementation spec update package

- target_documents:
  - `docs/implementation/002-bootstrap-implementation-plan.md`
  - `docs/implementation/003-proposed-capability-apis.md`
- topics_added_or_updated:
  - package boundaries
  - first delivery slices
  - use-case-driven API definition policy
  - MCP contracts
  - CLI and SDK contracts
  - session lifecycle and persistence
  - agent-layer integration
  - mutation persistence
  - log-book persistence
  - validation approach
  - staged rollout
  - bus-trace ingestion
  - dependency licensing policy
- interface_or_prompt_contracts:
  - Session lifecycle contract for create, select, and describe operations.
  - Python domain-core interfaces for import, graph query, enrichment, environment updates, user-action injection, mutation updates, and simulation.
  - SDK interface that exposes the canonical callable core API for the same capability set.
  - CLI interface for deterministic command execution across supported capabilities via `typer`.
  - MCP server interface for structured request and response payloads via `mcp` FastMCP.
  - Investigation-agent prompt contract that requires evidence-backed conclusions and explicit clarification instead of guessing.
- validation_expectations:
  - First implementation slice must prove session creation, `.knxproj` anchoring, graph querying, optional bus-trace decoding, and a minimal expectation simulation path.
  - Each MCP tool response must include enough provenance to explain why the answer was produced.
  - CLI, SDK, and MCP surfaces must call the same domain-core operations and return compatible structured results.
  - CLI and MCP adapters must be thin wrappers over the same SDK-facing callable core API.
  - Public capability contracts must be derived from reviewed use cases before they are treated as stable APIs.
  - Any delivered Python code must ship with pytest-based automated tests.
  - The solution package is validated with pytest as the baseline automated test framework.
  - Session creation must create a session-unique work-directory and persist a valid `session-state.yaml` file.
  - Session creation must require a `.knxproj` input and persist its full absolute path in session state.
  - Every session-scoped CLI, SDK, and MCP call must perform a project refresh check and re-read the project when the bound file changed.
  - Capability calls that change session behavior must update the session log book and any targeted mutation log book.
  - Named parameter-only mutations must persist as deltas rather than rewritten full project copies.
  - Selected Python dependencies must pass a documented free-to-use license review.
  - Bootstrap plan must support adding vendor-specific adapters without changing the core protocol.
- dependencies:
  - `docs/architecture/001-knx-investigation-platform.md`
  - `docs/implementation/001-solution-concept.md`

## Proposed package boundaries

```text
src/knx_agent/
  domain/
    session_model/
    mutation_model/
    logbook_model/
    project_model/
    trace_model/
    expectation_engine/
    scenario_model/
  adapters/
    ets_import/
    trace_import/
    component_knowledge/
    mcp/
    filesystem_session_store/
    filesystem_mutation_store/
    filesystem_logbook_store/
  sdk/
  cli/
  agent_layer/
  application/
    session_service/
    mutation_service/
    logbook_service/
    investigation_service/
  contracts/

The intended layering is:

- `application/` and `domain/` hold the callable core API and business rules,
- `sdk/` re-exports that callable core API in a stable Python integration surface,
- `cli/` uses `typer` to bind commands onto the same SDK-facing operations,
- `adapters/mcp/` uses `mcp` FastMCP to bind MCP tools onto the same SDK-facing operations,
- `agent_layer/` packages the instructed prompts, skills, and non-guessing orchestration rules for commercial reasoning agents.
```

## Bootstrap delivery slices

### Slice 1: session lifecycle and project anchoring

- Create an investigation session from a `.knxproj` input.
- Allocate a session-unique work-directory.
- Persist canonical session metadata in `session-state.yaml`.
- Persist the full absolute path of the mandatory source `.knxproj` file.
- Persist project-import freshness metadata that can drive later refresh checks.
- Support resolving a session by explicit session identifier across CLI, SDK, and MCP.
- Re-check the bound project file on every session-scoped call and re-import automatically when it changed.
- Initialize the overall session log book.

### Slice 1a: shared core API and adapter policy

- Define one callable core API shape that is directly consumable from the SDK.
- Keep CLI and MCP logic adapter-thin, limited to input parsing, output rendering, and protocol wiring.
- Ensure pytest can exercise capabilities through the SDK-facing API without going through CLI or MCP transports.
- Keep agent-layer prompting outside the core API while making all required deterministic steps callable.
- Require every new Python module or behavior slice to land with corresponding pytest coverage.

### Slice 1b: use-case capture and API derivation

- Capture prioritized troubleshooting use cases from the user.
- Derive concrete capability boundaries, inputs, outputs, and error cases from those use cases.
- Review proposed API contracts before treating CLI commands, SDK methods, or MCP tools as stable.

### Slice 1c: mutation and log-book persistence

- Define mutation delta files and mutation-specific log books inside the session work-directory.
- Define the overall session log book format and update triggers.
- Ensure default and named mutation scopes can be selected consistently across surfaces.

### Slice 2: project import and query backbone

- Parse a `.knxproj` into a normalized in-memory graph.
- Discover device metadata and device typing from the project.
- Support basic queries for topology, device metadata, group-address usage, and communication-object relationships.
- Support setup lookup by partial name, exact name, purpose, and address.
- Support detail levels with `MEDIUM` as the default.
- Emit import warnings for unsupported or ambiguous data.
- Define structured request and response contracts that can be reused by CLI, SDK, and MCP.

### Slice 3: bus-trace ingestion and observation decoding

- Parse supported KNX bus monitor trace exports into normalized telegram observations.
- Resolve telegram addresses and datapoint context against the imported project where possible.
- Infer candidate environmental or user-action facts from traces with explicit confidence and provenance.

### Slice 4: minimal expectation engine

- Allow explicit event injection against known inputs.
- Allow trace-derived observations to seed scenario state.
- Process ordered inputs so the latest KNX system state can answer `now` questions.
- Resolve a limited propagation model through group addresses and configured participants.
- Return expected downstream device and object reactions even when the semantic coverage is partial.

### Slice 5: verbal scenario model

- Convert user-described conditions into normalized scenario state.
- Support temperature, sun exposure, wind alarm, time-of-day, and button events first.
- Merge verbal inputs with accepted trace-derived state while keeping provenance separate.
- Apply `last come wins` updates for the same environment element.
- Keep scenario parsing separate from simulation rules.

### Slice 6: component knowledge enrichment

- Fetch component detail pages or documentation by product identifier.
- Extract structured behavior hints with explicit provenance.
- Cache normalized results for repeated use.
- Restrict implementation choices to Python packages with free-to-use licenses.

### Slice 7: investigation-facing MCP surface

- Expose the domain core through stable CLI commands, SDK entry points, and MCP tool schemas.
- Keep capability naming and payload structures aligned across surfaces.
- Include evidence sources and limitation notes in responses.
- Use `typer` for the CLI implementation.
- Use `mcp` FastMCP for the MCP implementation.
- Publish session, setup, environment, user-action, activity-question, mutation, knowledge, and log-book capability groups.

### Slice 7a: agent-layer package

- Create instructed prompts or skills that orchestrate the deterministic capability surface.
- Enforce technical, short, crisp, and non-guessing behavior.
- Require clarification when user language does not resolve onto deterministic identifiers.

### Slice 8: dependency governance and license verification

- Maintain a dependency decision record for each non-trivial Python package.
- Record license, project URL, intended usage, and replacement options for rejected packages.
- Block adoption of packages that are not free to use under the intended delivery model.

## Proposed capability mappings

The detailed proposed capability set lives in `docs/implementation/003-proposed-capability-apis.md`. The same capability set should be defined once and projected onto CLI, SDK, and MCP. Final public API names, argument shapes, and response schemas should be reviewed against evolving use cases before implementation freeze.

### Tool: `create_session`

- Inputs: mandatory `.knxproj` path or uploaded artifact handle, optional requested session label.
- Outputs: session identifier, work-directory path, `session-state.yaml` path, bound source project absolute path, project import summary.
- CLI shape: `knx-agent session create --project <file> [--label <name>]`
- SDK shape: `client.create_session(project_path=..., label=...)`
- MCP implementation note: FastMCP tool delegates directly to the same SDK-facing callable.

### Tool: `describe_session`

- Inputs: session identifier.
- Outputs: session identifier, work-directory path, bound source project absolute path, linked trace references, scenario summary, creation metadata, last project refresh metadata.
- CLI shape: `knx-agent session describe --session <id>`
- SDK shape: `client.describe_session(session_id=...)`
- MCP implementation note: FastMCP tool delegates directly to the same SDK-facing callable.

### Tool: `load_project`

- Inputs: session identifier.
- Outputs: project ID, import summary, warning list, topology counts, discovered device-type summary, refresh status.
- CLI shape: `knx-agent project load --session <id>`
- SDK shape: `client.load_project(session_id=...)`
- MCP implementation note: FastMCP tool delegates directly to the same SDK-facing callable.

## Session persistence contract

- Each session owns exactly one work-directory.
- `session-state.yaml` is created during session creation before later artifacts are written.
- Session creation fails if no `.knxproj` input is provided.
- Initial required fields in `session-state.yaml` should include `session_id`, `label`, `created_at`, `work_directory`, `source_project_absolute_path`, `project_import`, `project_refresh`, `trace_artifacts`, and `scenario_state`.
- `project_refresh` should track enough metadata to detect on-disk project updates before every session-scoped call.
- Future session artifacts should be referenced from `session-state.yaml` rather than discovered by directory scanning alone.
- Mutation references and log-book references should also live in `session-state.yaml`.

## Validation strategy

### Test assets

- Small sanitized `.knxproj` fixtures.
- Small sanitized KNX bus-trace fixtures.
- Expected normalized graph snapshots.
- Expected telegram-decoding and environment-inference snapshots.
- Example `session-state.yaml` fixtures and work-directory snapshots.
- Example mutation delta files and session or mutation log-book fixtures.
- Golden CLI output fixtures and SDK response fixtures for the same scenarios.
- Scenario and outcome examples for common device categories.

### Required automated checks

- Pytest package validation as the default automated validation entry point.
- Use-case-to-contract traceability checks.
- Session lifecycle tests.
- Project refresh-detection tests.
- Import parser tests.
- Trace import and decoding tests.
- Expectation-engine rule tests.
- SDK-first capability tests that exercise the callable core API directly with pytest.
- Pytest coverage for every delivered Python code path in the solution package.
- Mutation delta persistence tests.
- Session log-book update tests.
- CLI contract tests.
- SDK contract tests.
- MCP contract tests.
- Agent-layer prompt compliance checks where practical.
- Dependency license policy checks.
- Regression tests for provenance fields in tool responses.

### Manual checks

- Walk through at least one realistic fault report end-to-end.
- Walk through at least one realistic fault report that uses both project data and a trace excerpt.
- Verify that a session can be resumed from its work-directory and persisted state.
- Verify that editing the bound `.knxproj` file on disk is detected and causes automatic re-import on the next CLI, SDK, or MCP call.
- Verify the agent can distinguish fact, inference, and unknowns.
- Verify CLI and MCP behavior matches SDK-tested behavior for the same inputs.
- Verify the agent layer asks for clarification rather than guessing unresolved names.

## Suggested near-term milestones

1. Establish Python package skeleton and parser spike.
2. Capture prioritized troubleshooting use cases.
3. Define the investigation-session and session-state schemas.
4. Define project refresh metadata and re-import behavior for bound `.knxproj` files.
5. Define mutation delta and log-book persistence schemas.
6. Define the normalized KNX graph and trace observation schemas.
7. Derive shared capability contracts from the use cases and expose the first read-only operations through the SDK-facing core API, then through CLI and MCP adapters.
8. Add the initial scenario engine for discrete events and environment inputs.
9. Introduce vendor enrichment for device types discovered in a representative project.
10. Add dependency license checks to the delivery workflow.
11. Establish the package-level pytest validation workflow and required test scaffolding.

## Bootstrap decisions needing user input

1. Which KNX bus-monitor trace formats or exports should be supported first?
2. Do you already have sanctioned documentation sources for the target devices?
3. Are there any license families you want excluded even if they are generally considered free to use?
4. Should the first packaging focus on local CLI and VS Code agent usage, or also a remote multi-user service?
5. Which user troubleshooting use cases should define the first stable APIs?