# Implementation 002: Bootstrap Implementation Plan

This document used to hold tool mappings, delivery slices and a validation strategy. Capability and
tool definitions now live only in `docs/implementation/003-proposed-capability-apis.md` (single
authoritative catalogue, status reviewed draft); delivery is planned through `development/todos/`
(todos 02 to 14) and story task plans under `development/backlog/`.

This document defines no capabilities. Valid non-capability content (session persistence contract,
layering, dependency policy, validation expectations) was migrated to the appendix of
`docs/implementation/003-proposed-capability-apis.md`; delivery slices, milestones, test-asset lists
and open bootstrap questions were discarded explicitly there because todos 02 to 14 supersede them.

## Slice 1 realisation note (story 03)

Slice 1 (session foundation) is realised by story 03: `SessionLifecycle` and `ProjectRefreshGuard` as
separate application-layer collaborators composed by a session service, `session-state.yaml` via
PyYAML (runtime dependency) with atomic writes, and the KNX session log book as JSON Lines. Session
root, field list, log point table and error order are specified only in
`docs/implementation/003-proposed-capability-apis.md` (section "Session service realisation (story 03)");
this note defines nothing. Task plan: `development/backlog/active/03-session-service-and-project-refresh-task-plan.yaml`.

## Slice 2 realisation note (story 04)

Slice 2 (`.knxproj` import) is realised by story 04: an own ETS 6 parser (stdlib `ElementTree` streaming;
lxml only if the first benchmark task breaches the 30 s rule), a project graph with source facts and derived
facts persisted as `project-graph.json` in the work-directory, a hostile-archive guard, a SHA-256 fingerprint in
the project refresh check, and the real import behind `create_session`, `reimport_system_definition` and
`describe_session` on SDK, CLI and MCP. Everything is specified only in
`docs/implementation/003-proposed-capability-apis.md` (section "Project import and project graph (story 04)");
this note defines nothing. The query capabilities are todo 15. Task plan:
`development/backlog/active/04-knxproj-import-and-project-graph-task-plan.yaml`.

## Slice 3 realisation note (story 05)

Slice 3 (component inspection) is realised by story 05: a `QueryService` in the application layer over the
persisted project graph, pure domain modules for selectors, component views, topology summary and group flow, and
the capabilities `list_components`, `describe_component`, `summarize_topology` and `trace_group_flow` on SDK, CLI
(`knx-agent setup ...`) and MCP. Everything is specified only in
`docs/implementation/003-proposed-capability-apis.md` (section "Component inspection (story 05)"); this note
defines nothing. Task plan: `development/backlog/active/05-component-inspection-capabilities-task-plan.yaml`.

Related: `docs/implementation/001-solution-concept.md`, `docs/architecture/001-knx-investigation-platform.md`.
