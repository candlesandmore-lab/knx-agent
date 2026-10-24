# knx-agent

knx-agent is a KNX investigation platform built around one shared core API. The same capabilities are exposed through a Python SDK, a Typer CLI and an MCP tool server (MCPServer, from mcp 2.x, formerly FastMCP). The adapters only delegate to the SDK, which calls the application layer. Implemented capabilities: `create_session`, `describe_session` and `reimport_system_definition` (the session service, story 03) with a real ETS 6 `.knxproj` import and project graph (story 04). The query capabilities on the graph (`summarize_topology`, `list_components`, ...) follow in todo 15.

## Package layout

```
src/knx_agent/
  contracts/     request/response models, response envelope, error types and codes, LogLevel
  domain/        session-state model, project graph model, component typing, graph diff (pure)
  application/   SessionService = SessionLifecycle + ProjectRefreshGuard; importer (archive guard, ETS 6 parser,
                 derivation, fingerprint), graph store, log book writer
  sdk/           KnxSessionClient, the Python entry point
  cli/           Typer CLI adapter (`knx-agent session create|describe|reimport`)
  adapters/mcp/  MCP adapter (MCPServer, mcp 2.x), console script `knx-agent-mcp`
  agent_layer/   agent-facing layer (placeholder)
tests/
  conftest.py    YAML fixture loader, helpers, session test projects
  knxproj_builder.py  builder for small valid synthetic ETS 6 archives (and every error/warning variant)
  fixtures/      user-editable test input data (YAML)
  lifedata/      the committed sample project (see "The sample project")
```

Import direction: adapters (CLI, MCP) -> SDK -> application -> contracts/domain. This is enforced by `tests/test_import_direction.py`.

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

To add a case, append an entry with a unique `id`; no Python change is needed.

### Sample-based tests and skipping

`tests/test_sample_project.py` and `tests/test_xknxproject_crosscheck.py` skip (with the reason in the report) when `tests/lifedata/20261010-EFH-Armbruster.knxproj` is absent; the cross-check also skips when `xknxproject` is not installed (`uv sync` installs it from the dev group). In CI, run with `-rs` to see the skip reasons. The cross-check compares our graph with xknxproject: individual addresses and group addresses are equal; xknxproject lists only communication objects that have a group address link (677 on the sample, ours: 692), so the test compares per component on our objects that have a membership.

## Run the tests

```
uv run pytest tests
```
