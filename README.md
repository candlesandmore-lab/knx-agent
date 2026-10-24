# knx-agent

knx-agent is a KNX investigation platform built around one shared core API. The same capabilities are exposed through a Python SDK, a Typer CLI and an MCP tool server (MCPServer, from mcp 2.x, formerly FastMCP). The adapters only delegate to the SDK, which calls the application layer. Implemented capabilities: `create_session`, `describe_session` and `reimport_system_definition` (the session service, story 03). `.knxproj` content is not parsed yet: the import only validates the file as a zip archive and records its file metadata.

## Package layout

```
src/knx_agent/
  contracts/     request/response models, response envelope, error types and codes, LogLevel
  domain/        session-state model and session_label rule (pure)
  application/   SessionService = SessionLifecycle + ProjectRefreshGuard, .knxproj guard, log book writer
  sdk/           KnxSessionClient, the Python entry point
  cli/           Typer CLI adapter (`knx-agent session create|describe|reimport`)
  adapters/mcp/  MCP adapter (MCPServer, mcp 2.x), console script `knx-agent-mcp`
  agent_layer/   agent-facing layer (placeholder)
tests/
  conftest.py    YAML fixture loader, synthetic .knxproj factory, helpers
  fixtures/      user-editable test input data (YAML)
```

Import direction: adapters (CLI, MCP) -> SDK -> application -> contracts/domain. This is enforced by `tests/test_import_direction.py`.

## Install for development

```
uv sync
```

`uv sync` also installs agent-dev-agent, because it is a dev dependency with a path source to
`agent-dev-agent/agent-dev-agent/agent_building_agent-0.6.2-py3-none-any.whl` (see `[tool.uv.sources]` in `pyproject.toml`).
That folder and wheel must exist in the workspace root, otherwise the sync fails.
Runtime dependencies: pydantic, typer, mcp and pyyaml (pyyaml writes `session-state.yaml`; to be added to the license record, todo 12).

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
    session-log-book.jsonl    KNX session log book (append-only JSON Lines)
```

`session-state.yaml` holds `session_label`, `created_at`, `work_directory`, `source_project_absolute_path`, `project_import` (path, mtime in ns, size, imported_at, project_import_summary, `fingerprint: null`), `project_refresh` (last_status, last_reimported_at, reimport_count), `active_setup`, `trace_artifacts`, `scenario_state`, `mutations`, `log_book_references` and `mutation_log_book_references`.

`create_session` validates in this order: label (`SESSION_LABEL_INVALID`), file readable (`PROJECT_FILE_UNREADABLE`), valid zip archive (`PROJECT_PARSE_ERROR`), label unused (`SESSION_LABEL_EXISTS`). It builds the folder under a temporary name and renames it, so a failed create never leaves a folder behind.

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

### Project refresh check

Every session-scoped call (`describe_session`, `reimport_system_definition`) runs through the application layer. `describe_session` first compares existence, mtime and size of the bound `.knxproj` with `project_import`: unchanged writes nothing (idempotent), changed triggers an automatic re-import. A missing or unreadable file fails with `PROJECT_FILE_UNREADABLE` and leaves `session-state.yaml` unchanged. `reimport_system_definition` forces the re-read and reports `CHANGED` or `UNCHANGED`.

Known limitation: until the fingerprint exists (todo 04), a content change that keeps mtime and size is not detected automatically; run `reimport_system_definition` manually.

### Single-writer assumption

One process works on a session at a time. Concurrent access to the same session (for example CLI and MCP writing together) is out of scope and not protected by locking.

### Logging and the KNX session log book

- `log_level` (INFO default, DEBUG, FULL) is chosen per call: CLI `--log-level`, SDK `log_level`, MCP startup argument. Lifecycle events (create, re-imports) are INFO, unchanged refresh checks are DEBUG.
- Every issue is logged as ERROR through the standard Python `logging` module (logger `knx_agent` and children). The library installs no handler; the CLI and `knx-agent-mcp` attach a stderr handler. When the session exists, the ERROR is also appended to `session-log-book.jsonl` as level `ERROR`, whatever `log_level` is configured. A failed `create_session` is logged to the Python logger only.
- Log book entries: `entry_id`, `timestamp`, `level`, `capability`, `setup`, `summary`, `details`.

## Test fixtures

Test input data lives in YAML files, not in test modules. Tests use temporary session roots and synthetic `.knxproj` zip files built in the tests.

| File | Content |
| --- | --- |
| `tests/fixtures/describe_session_cases.yaml` | `describe_session` valid and invalid labels (`valid_case`, `invalid_case` arguments) |
| `tests/fixtures/session_label_cases.yaml` | label rules for create and existing-session calls |
| `tests/fixtures/create_session_error_cases.yaml` | create failures and the fixed error order |
| `tests/fixtures/refresh_change_cases.yaml` | unchanged / mtime / size / missing / not-zip project changes |
| `tests/fixtures/log_level_cases.yaml` | expected log book levels per `log_level` and scenario, incl. ERROR |

To add a case, append an entry with a unique `id`; no Python change is needed.

## Run the tests

```
uv run pytest tests
```
