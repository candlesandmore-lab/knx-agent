# knx-agent

knx-agent is a KNX investigation platform built around one shared core API. The same capabilities are exposed through a Python SDK, a Typer CLI and an MCP tool server (MCPServer, from mcp 2.x, formerly FastMCP). The adapters only delegate to the SDK, which calls the application layer. Implemented capabilities: `create_session`, `describe_session` and `reimport_system_definition` (the session service, story 03) with a real ETS 6 `.knxproj` import and project graph (story 04), and the four read-only component inspection capabilities `list_components`, `describe_component`, `summarize_topology` and `trace_group_flow` (story 05, CLI group `knx-agent setup`).

## Package layout

```
src/knx_agent/
  contracts/     request/response models, response envelope, error types and codes, LogLevel
  domain/        session-state model, project graph model, component typing, graph diff, and the query logic of
                 story 05: graph_index, selectors, component_view, topology_summary, group_flow (pure)
  application/   SessionService = SessionLifecycle + ProjectRefreshGuard; QueryService (the four query
                 capabilities); importer (archive guard, ETS 6 parser, derivation, fingerprint), graph store,
                 log book writer, shared ERROR reporting
  sdk/           KnxSessionClient, the Python entry point
  cli/           Typer CLI adapter (`knx-agent session create|describe|reimport`,
                 `knx-agent setup list-components|describe-component|summarize-topology|trace-group-flow`)
  adapters/mcp/  MCP adapter (MCPServer, mcp 2.x), console script `knx-agent-mcp`
  agent_layer/   agent-facing layer (placeholder)
tests/
  conftest.py    YAML fixture loader, helpers, session test projects
  knxproj_builder.py  builder for small valid synthetic ETS 6 archives (and every error/warning variant)
  graph_factory.py    builds a project graph from a compact YAML description (domain tests need no archive)
  fixtures/      user-editable test input data (YAML)
  lifedata/      the committed sample project (see "The sample project")
```

Import direction: adapters (CLI, MCP) -> SDK -> application -> domain -> contracts (the domain may import `contracts`, which imports nothing). This is enforced by `tests/test_import_direction.py`.

## Install for development

```
uv sync
```

`uv sync` also installs agent-dev-agent, because it is a dev dependency with a path source to
`agent-dev-agent/agent-dev-agent/agent_building_agent-0.6.2-py3-none-any.whl` (see `[tool.uv.sources]` in `pyproject.toml`).
That folder and wheel must exist in the workspace root, otherwise the sync fails.
Runtime dependencies: pydantic, typer, mcp and pyyaml (pyyaml writes `session-state.yaml`). The `.knxproj` import uses only the standard library (`zipfile`, `hashlib`, `xml.etree.ElementTree`, `json`); there is no XML library dependency (lxml was not needed: the sample imports in about 1.2 s).

Dev-only dependency: `xknxproject` (GPL-2.0 per its package metadata; this repository is MIT). It is in the `dev` dependency group only, is used by `tests/test_xknxproject_crosscheck.py` as an independent cross-check, is never imported by `src/` (enforced by `tests/test_import_direction.py`) and no code of it is copied. If it is not installed the cross-check skips. License records for all dependencies are kept in `development/todos/12-dependency-license-governance.md` (todo 12 already lists xknxproject, pyyaml and lxml as to-be-recorded).

## Sessions

A session is addressed only by its user-chosen `session_label` (letters, digits, `-` and `_`, unique under the session root). There is no `session_id` and no implicit active session.

### Session root

The session root is the folder holding all work-directories. Default: `./.knx-agent/sessions` (relative to the current working directory, created on demand). It is set only by:

| Surface | Way to set it |
| --- | --- |
| CLI | `--session-root <dir>` on every `session` subcommand |
| MCP | startup argument `--session-root <dir>` of `knx-agent-mcp` |
| SDK | `KnxSessionClient(session_root=...)` |

No environment variable is read anywhere.

### Session folder layout

```
<session root>/
  <session_label>/            work-directory
    session-state.yaml        persisted session metadata (written atomically)
    project-graph.json        the project graph of the last import (written atomically)
    session-log-book.jsonl    KNX session log book (append-only JSON Lines)
```

`session-state.yaml` holds `session_label`, `created_at`, `work_directory`, `source_project_absolute_path`, `project_import` (path, mtime in ns, size, imported_at, `fingerprint`, `graph_file`, `graph_schema_version`, `project_import_summary`, and the first 200 import `warnings`), `project_refresh` (last_status, last_reimported_at, reimport_count), `active_setup`, `trace_artifacts`, `scenario_state`, `mutations`, `log_book_references` and `mutation_log_book_references`.

`create_session` validates in this order: label (`SESSION_LABEL_INVALID`), file readable (`PROJECT_FILE_UNREADABLE`), import of the archive (`PROJECT_PARSE_ERROR`, with `details.reason`), label unused (`SESSION_LABEL_EXISTS`). It builds the folder (graph, state, log book) under a temporary name and renames it, so a failed create never leaves a folder behind.

Sessions created by story 03 code (before the real import) are not migrated: their `session-state.yaml` no longer validates (`SESSION_NOT_FOUND`); create the session again.

## Project import (ETS 6)

The import reads ETS 6 `.knxproj` files only (project namespace `http://knx.org/xml/project/22`, ETS tool version 6.x) with its own parser. A project built by another ETS version fails with `PROJECT_PARSE_ERROR` (`UNSUPPORTED_NAMESPACE` / `UNSUPPORTED_TOOL_VERSION`). The ETS signature is not verified. The archive is never extracted to disk.

What is imported: the installation, areas, lines, spaces, components (devices), communication objects, group addresses and ranges, parameters, scenes and application programs, plus the memberships (communication object to group address) and the placement of components in spaces. Every node has a stable ID and a provenance (`source_part`, `source_locator`, `fact_origin`). Facts read from the project are kept apart from facts derived from them: the component typing (`SENSOR`, `ACTUATOR`, `CONTROLLER`, `IP_COUPLER_OR_INTERFACE`, `COUPLER`, `UNTYPED`, by rules CT0 to CT4 in `docs/implementation/003-proposed-capability-apis.md`) and the membership indexes exist only under `derived_facts`.

### project-graph.json and session-state.yaml

`project-graph.json` (in the work-directory) holds `graph_schema_version`, `fingerprint`, `source_facts` (`nodes`, `relations`), `derived_facts` and the complete list of `warnings`. It has sorted keys and no timestamps, so importing an unchanged project twice gives byte-identical files. `session-state.yaml` holds the metadata, the fingerprint, the `project_import_summary` (counts per node kind, relation counts, component type counts, application program counts, warning counts) and the first 200 warnings. Write order: parse first (a failure writes nothing), then `project-graph.json`, then `session-state.yaml`. `describe_session` returns `project_import` (imported_at, fingerprint, absolute `graph_file`, summary) from `session-state.yaml` only.

### Warnings

Import warnings (`code`, `message`, `location`) describe the project, not a failed operation, so they are not errors. They appear as `limitation_notes` in the response envelope (`[<code>] <message> (<location>)`, at most 50 plus one entry stating how many more exist), as counts in `project_import_summary` (`warning_total`, `warning_counts`), in full in `project-graph.json`, as one Python `logging` WARNING record per import (logger `knx_agent.application`, counts only) and as DEBUG entries in the log book (one per warning, at most 200). Codes: `OPTIONAL_PART_MISSING`, `OPTIONAL_PART_UNREADABLE`, `APPLICATION_PROGRAM_MISSING`, `PRODUCT_REFERENCE_UNRESOLVED`, `APPLICATION_PROGRAM_REFERENCE_MISMATCH`, `COMOBJECT_DEFINITION_UNRESOLVED`, `PARAMETER_DEFINITION_UNRESOLVED`, `GROUP_ADDRESS_LINK_UNRESOLVED`, `DEVICE_REFERENCE_UNRESOLVED`, `DATAPOINT_TYPE_UNKNOWN`, `INVALID_ATTRIBUTE_VALUE`, `DUPLICATE_ID`, `STRUCTURAL_ID_FALLBACK`, `UNSUPPORTED_ELEMENT`, `ADDITIONAL_INSTALLATION_IGNORED` (meanings in 003, "Warnings contract").

Failures are errors (`ERROR` in the Python logger and the log book): `PROJECT_PARSE_ERROR` with `details.reason` (for example `NOT_A_ZIP`, `ENCRYPTED`, `PROJECT_FOLDER_NOT_FOUND`, `REQUIRED_PART_MALFORMED`, `UNSUPPORTED_TOOL_VERSION`, the archive limit reasons and `XML_DTD_FORBIDDEN` / `XML_ENTITY_FORBIDDEN` / `XML_ENCODING_UNSUPPORTED` in a required part) and `PROJECT_FILE_UNREADABLE` (also `details.reason: CHANGED_DURING_IMPORT` when the file changed while it was imported). Only `project.xml` and `0.xml` are required; a broken optional part (catalog, `Hardware.xml`, application program, `knx_master.xml`) is skipped with `OPTIONAL_PART_UNREADABLE` and never partially used.

### Limits of the hostile-archive guard

At most 5000 entries, 256 MiB per entry, 1 GiB uncompressed in total, a compression ratio of at most 200 per entry, no duplicate entry names, no encrypted entries. XML parts containing a DTD (`<!DOCTYPE`), an entity declaration (`<!ENTITY`) or a non-UTF-8 encoding are rejected before any parser sees them (no entity expansion).

### Fingerprint and refresh check

The fingerprint is the SHA-256 of the `.knxproj` file bytes (lowercase hex, `project_import.fingerprint`). The project refresh check runs before every session-scoped call and compares, in this order: existence (`PROJECT_FILE_UNREADABLE` if missing, state unchanged), mtime, size, fingerprint. A difference (or a stored fingerprint of `null`, or a missing `project-graph.json`) means `CHANGED`: the project is re-imported automatically. Only when mtime and size equal the stored values is the file hashed on every check (about 4 ms for the 7.5 MB sample); equal everything writes nothing, so the check is idempotent and `session-state.yaml` stays byte-identical. This closes the story 03 limitation: a content change that keeps mtime and size is detected.

`reimport_system_definition` always re-parses and rewrites the graph; it returns `project_refresh_status` `CHANGED` (mtime, size, fingerprint or graph file differed) or `UNCHANGED`, `changes` (components and group addresses added, removed or changed, compared by stable ID) and `invalidated_references` (entries in `scenario_state` or `mutations` that name a component or group address which no longer exists; they are retained, never deleted, and each also appears as a limitation note). A failed import leaves state and graph unchanged.

### The sample project

`tests/lifedata/20261010-EFH-Armbruster.knxproj` is a real ETS 6 project and is committed to the repository as is (user decision; it contains personal data of the project owner, which the tests, fixtures and this README do not copy). Sample-based tests (`tests/test_sample_project.py`, `tests/test_xknxproject_crosscheck.py`) skip with a clear message when the file is absent. Golden counts are in `tests/fixtures/sample_project_counts.yaml` (user-editable; a mismatch is investigated, not re-baselined). Measured on the sample (macOS, Python 3.12): create_session end to end (fingerprint through persisted graph) about 1.2 s, peak RSS about 83 MiB, `project-graph.json` 3.2 MB. The sample yields 26 warnings, all from one component whose module-instance references are not modelled.

### Commands

```
knx-agent session create --project <file.knxproj> --session-label <label> [--session-root <dir>] [--log-level INFO|DEBUG|FULL]
knx-agent session describe --session <label> [--session-root <dir>] [--log-level INFO|DEBUG|FULL]
knx-agent session reimport --session <label> [--session-root <dir>] [--log-level INFO|DEBUG|FULL]
knx-agent-mcp [--session-root <dir>] [--log-level INFO|DEBUG|FULL]
```

The CLI prints the response as JSON on stdout; an error is printed as `ErrorInfo` JSON (the last line on stderr) with exit code 1. SDK:

```python
client = KnxSessionClient(session_root="sessions", log_level="INFO")
client.create_session(project_path="house.knxproj", session_label="house-1")
client.describe_session(session_label="house-1")
client.reimport_system_definition(session_label="house-1")
```

The MCP tools `create_session`, `describe_session` and `reimport_system_definition` use the startup arguments; the MCP server never writes to stdout except the protocol (logging goes to stderr).

### Single-writer assumption

One process works on a session at a time. Concurrent access to the same session (for example CLI and MCP writing together) is out of scope and not protected by locking.

### Logging and the KNX session log book

- `log_level` (INFO default, DEBUG, FULL) is chosen per call: CLI `--log-level`, SDK `log_level`, MCP startup argument. Lifecycle events (create, re-imports) are INFO; unchanged refresh checks, "Import started" and each import warning are DEBUG.
- Every failure is logged as ERROR through the standard Python `logging` module (logger `knx_agent` and children). The library installs no handler; the CLI and `knx-agent-mcp` attach a stderr handler. When the session exists, the ERROR is also appended to `session-log-book.jsonl` as level `ERROR`, whatever `log_level` is configured. A failed `create_session` is logged to the Python logger only.
- Log book entries: `entry_id`, `timestamp`, `level`, `capability`, `setup`, `summary`, `details`.

## Component inspection (story 05)

Four read-only capabilities answer questions about the imported project graph. Every call first runs the project refresh check (a changed project is re-imported before the query), then validates the request, loads `project-graph.json`, indexes it and answers; nothing is cached between calls. Terms: a *location* is a space of the ETS location tree (Building, Floor, Room, ...); the *instance path* of a component is its location path plus its own name, joined by `/` (for example `House/Ground floor/Living room/Wall switch`); a component that is not placed in a location has no instance path.

### Commands

```
knx-agent setup list-components --session house-1 [--query <selector>] [--selector-kind K] [--detail-level L] [--mutation M]
knx-agent setup describe-component --session house-1 --component <selector> [--selector-kind K] [--detail-level L] [--mutation M]
knx-agent setup summarize-topology --session house-1 [--detail-level L] [--mutation M]
knx-agent setup trace-group-flow --session house-1 (--group-address <address or name> | --object-ref <ref>) [--detail-level L] [--mutation M]
```

All four also take `--session-root <dir>` and `--log-level INFO|DEBUG|FULL`. All values are plain strings validated by the core (a bad `--detail-level` is the catalogue error `INVALID_DETAIL_LEVEL`, not a usage error). Examples with generic names:

```
knx-agent setup list-components --session house-1 --query 1.1.5
knx-agent setup list-components --session house-1 --query "Ground floor/Living room/" --detail-level SUMMARY
knx-agent setup list-components --session house-1 --query "switch" --selector-kind NAME
knx-agent setup describe-component --session house-1 --component P-0001-0_DI-6 --detail-level FULL
knx-agent setup summarize-topology --session house-1 --detail-level MEDIUM
knx-agent setup trace-group-flow --session house-1 --group-address 5/0/12
knx-agent setup trace-group-flow --session house-1 --object-ref "P-0001-0_DI-6/co/O-0_R-1"
```

SDK: `client.list_components(session_label, component_selector=None, selector_kind=None, detail_level=None, mutation_name=None, log_level=None)`, `describe_component(...)` (same parameters), `summarize_topology(session_label, detail_level=None, mutation_name=None, log_level=None)` and `trace_group_flow(session_label, group_address_selector=None, communication_object_ref=None, detail_level=None, mutation_name=None, log_level=None)`; strings or the enums `SelectorKind` / `DetailLevel` are accepted, case-insensitively. MCP tools of the same names take `session_label`, `component_selector`, `selector_kind`, `group_address_selector`, `communication_object_ref`, `detail_level` and `mutation_name` as strings; the log level is the server startup argument. An MCP error is a `ValueError` whose first line is `CODE: message` and whose second line is the `ErrorInfo` JSON (including `details.reason`), identical to the CLI error JSON.

### Component selectors

`selector_kind` is `ANY` (default, auto-detect), `NAME`, `INSTANCE_PATH`, `INDIVIDUAL_ADDRESS` or `ETS_ID`. The value is stripped; an empty value is `INVALID_REQUEST` (`details.reason` `SELECTOR_BLANK`).

| Kind | Looks like | Matches |
| --- | --- | --- |
| `NAME` | any text | partial, case-insensitive substring of the component name (components without a name never match) |
| `INSTANCE_PATH` | segments separated by `/` | partial, case-insensitive, per segment, over consecutive path segments (below) |
| `INDIVIDUAL_ADDRESS` | `1.1.5` (area 0-15, line 0-15, device 0-255; leading zeros are accepted) | exact |
| `ETS_ID` | `P-0001-0_DI-6` | exact, case-sensitive |

Under `ANY` the name is always evaluated; an individual address or ETS id is evaluated when the value has that syntax; an instance path is evaluated only when the value contains `/`. The result is the union, each component once, and every match carries `match_kinds` (sorted, no duplicates): a component named `1.1.5` that also has that individual address matches with `["INDIVIDUAL_ADDRESS", "NAME"]`, and a value such as `1.1.300` (out of range) is only a name query. An explicit kind evaluates only that kind; a value that does not fit it (for example `INDIVIDUAL_ADDRESS` with `1.1`) is `INVALID_REQUEST` with `details.reason` `SELECTOR_KIND_MISMATCH`. An unknown kind is `SELECTOR_KIND_UNKNOWN`, a kind without a selector in `list_components` is `SELECTOR_KIND_WITHOUT_SELECTOR`.

Instance path queries: the query is split at `/`; its segments must match consecutive path segments (each as a case-insensitive substring), so `Ground floor/Living room/Wall` matches and `House/Living room` does not (a floor lies between). A leading `/` anchors the first segment at the root (`/House/Ground/`); a trailing `/` makes it a location query that must match inside the location part (`Ground floor/Living room/` lists every component placed there, including in nested child locations). Segment texts: the node name; an empty space name uses the space id, an empty component name uses its individual address. Names containing `/` stay one segment.

Results: `list_components` returns `matches`, `match_count` and `ambiguous` (a selector was given and more than one component matches; a broad listing is never ambiguous); no match is an empty set, not an error. `describe_component` returns the same set as `components`; nothing matching is `SELECTOR_UNRESOLVED` (`details.selector`, `selector_kind`, `evaluated_kinds`).

### Detail levels

`detail_level` is `SUMMARY`, `MEDIUM` (default) or `FULL`; the three levels are distinct, and fields of a higher level are absent (not `null`) at a lower one.

| Block | SUMMARY | MEDIUM | FULL |
| --- | --- | --- | --- |
| `identity` (name, individual address, ETS id, `instance_path`, `other_instance_paths`) | yes | yes | yes |
| `derived` (`fact_kind` `DERIVED`, `component_type`) | yes | yes | plus `typing_rule_id`, `typing_basis` |
| `match_kinds` | with a selector | with a selector | with a selector |
| `topology` (area, line, location path), `component_parameters` (raw ETS strings) | no | yes | yes (+ `parameter_type_id`) |
| `group_addresses`, `communication_objects` (flags, datapoint types, linked group addresses), `product`, `application`, `engineering_metadata` | no | no | yes |

Source facts and derived facts are kept apart: the component type lives only in `derived`. `summarize_topology` returns SUMMARY: counts of areas, lines and locations plus `locations_by_type`; MEDIUM adds areas with their lines and component counts, a depth-first location list (`path`, `depth`, direct and total counts) and the unplaced / unassigned counts; FULL adds the component names and individual addresses under every line and location. `component_counts` (total, placed, unplaced, by component type) is in every level. A project without locations gives a limitation note instead of location entries.

### Group address flow and direction labels

`trace_group_flow` takes exactly one of `group_address_selector` and `communication_object_ref` (both: `SELECTOR_CONFLICT`; none: `SELECTOR_MISSING`). A group address selector that is a valid address form is matched exactly: the 3-level form `a/b/c` (a 0-31, b 0-7, c 0-255) always, plus the form of the project's address style (TwoLevel `a/b`, Free a plain number); anything else is a partial, case-insensitive group address name (unnamed addresses never match). A name may match several group addresses: the result is a set (`ambiguous` true), ordered by address. `communication_object_ref` is the object id `<component id>/co/<ref id>` shown in `communication_objects[].ets_id`; the result has one entry per linked group address (an object without links gives an empty set and a note). Unknown address, name or object: `SELECTOR_UNRESOLVED`.

Each entry lists the direct participants (the communication objects linked to the address and their components) with a direction label derived only from the ETS communication object flags: `SENDER` (transmit), `RECEIVER` (write or update), `SENDER_RECEIVER` (transmit and write/update) or `UNDETERMINED` (no such flag, a read-only object, or flags unknown because the definition is unresolved); `roles` list `TRANSMITS`, `ACCEPTS_WRITE`, `ACCEPTS_UPDATE` and `ANSWERS_READ`. Limits: the order of group address links is not used as a sender rule; there is no line or area routing; `current_value` is always `unknown`; `unresolved_links` come from the import warnings.

### Read-only behaviour and errors

The four capabilities write no log book entry of their own, at any `log_level`; only the refresh check writes (DEBUG when unchanged, INFO when it re-imported, with the calling capability name). The envelope `log_book_entry_id` is that refresh entry or `null`. Every failure is an ERROR entry (always written) plus a Python logging record. Order: log level, session, refresh check, request validation, graph load, query. `mutation_name` omitted, empty or `default` targets the default setup; any other value is `MUTATION_NOT_FOUND` until mutations exist. A stored `project-graph.json` that cannot be read is `PROJECT_PARSE_ERROR` with `details.reason` `GRAPH_FILE_INVALID` (repair it with `reimport_system_definition`).

### Limitations

No paging or result limit (a `FULL` listing of a whole project is large: narrow the selector or lower the level); component type is a coarse derived fact; parameter values are raw ETS strings; direction is flag based only; no routing and no simulated values (`current_value` is `unknown`); no purpose annotation (todo 14); a rejected request can still re-import a changed project (the refresh check comes first). Measured on the sample (28 components, 692 communication objects): every query call takes 0.02 to 0.04 s at every detail level; a `FULL` listing of all components is 1.25 MB of JSON.

## Demo

Hands-on tour of every CLI action on the sample project: [demo/README.md](demo/README.md); run `demo/run-all.sh`. The demo scripts live in `demo/`, use their own git-ignored session root `demo/.sessions` and are guarded by `tests/test_demo_scripts.py`.

## Test fixtures

Test input data lives in YAML files, not in test modules. Tests use temporary session roots and small valid synthetic ETS 6 archives made by `tests/knxproj_builder.py` (a Python/YAML description plus named mutations for every error and warning case; only `zipfile` is used). The sample project is the real-world check.

| File | Content |
| --- | --- |
| `tests/fixtures/describe_session_cases.yaml` | `describe_session` valid and invalid labels (`valid_case`, `invalid_case` arguments) |
| `tests/fixtures/session_label_cases.yaml` | label rules for create and existing-session calls |
| `tests/fixtures/create_session_error_cases.yaml` | create failures, the fixed error order and `PROJECT_PARSE_ERROR` reasons |
| `tests/fixtures/refresh_change_cases.yaml` | unchanged / mtime / size / content-with-same-mtime-and-size / missing / not-zip project changes |
| `tests/fixtures/log_level_cases.yaml` | expected log book levels per `log_level` and scenario, incl. ERROR |
| `tests/fixtures/import_error_cases.yaml` | archive description to `PROJECT_PARSE_ERROR` `details.reason` |
| `tests/fixtures/import_warning_cases.yaml` | archive description to the exact set of warning codes |
| `tests/fixtures/typing_rule_cases.yaml` | component typing rules CT0 to CT4 incl. boundaries |
| `tests/fixtures/application_program_resolution_cases.yaml` | which application program is referenced, read or never opened |
| `tests/fixtures/reimport_change_cases.yaml` | `changes` and `invalidated_references` of a re-import |
| `tests/fixtures/stable_id_cases.yaml` | stable ID rules |
| `tests/fixtures/zip_limit_cases.yaml` | lowered archive limits per case |
| `tests/fixtures/sample_project_counts.yaml` | golden counts of the sample project |
| `tests/fixtures/query_request_cases.yaml` | `detail_level` and `selector_kind` parsing |
| `tests/fixtures/selector_cases.yaml`, `selector_overlap_cases.yaml` | component selectors on described graphs; the `ANY` overlap rules |
| `tests/fixtures/group_address_selector_cases.yaml` | group address forms per address style, object refs |
| `tests/fixtures/graph_index_cases.yaml` | component order, paths, memberships, warnings by object |
| `tests/fixtures/component_detail_level_cases.yaml`, `describe_component_cases.yaml` | the three detail levels, limitation notes, list/describe results |
| `tests/fixtures/topology_summary_cases.yaml` | topology summary per level |
| `tests/fixtures/group_flow_cases.yaml` | flow entries, direction, link-order independence |
| `tests/fixtures/query_error_cases.yaml`, `query_log_cases.yaml` | query failures and read-only logging |
| `tests/fixtures/surface_cases.yaml` | SDK / CLI / MCP parity, option and argument names |
| `tests/fixtures/sample_query_expectations.yaml` | golden structure of the sample for the query capabilities |
| `tests/fixtures/demo_script_expectations.yaml` | expected exit codes, error codes and key output fields of the demo scripts |

To add a case, append an entry with a unique `id`; no Python change is needed. Domain cases describe a graph in YAML (areas, lines, location tree, components, communication objects with flags and links, group addresses, parameters, warnings) that `tests/graph_factory.py` turns into a project graph, so they need no archive; service, SDK, CLI and MCP tests use archives from `tests/knxproj_builder.py`.

### Sample-based tests and skipping

`tests/test_sample_project.py`, `tests/test_sample_queries.py` (golden structure of the four query capabilities: counts, ids and structure only, names are taken at run time), `tests/test_demo_scripts.py` (runs every `demo/` script against the sample; its static checks of the demo folder run without the sample) and `tests/test_xknxproject_crosscheck.py` skip (with the reason in the report) when `tests/lifedata/20261010-EFH-Armbruster.knxproj` is absent; the cross-check also skips when `xknxproject` is not installed (`uv sync` installs it from the dev group). In CI, run with `-rs` to see the skip reasons. The cross-check compares our graph with xknxproject: individual addresses and group addresses are equal; xknxproject lists only communication objects that have a group address link (677 on the sample, ours: 692), so the test compares per component on our objects that have a membership.

## Run the tests

```
uv run pytest tests
```
