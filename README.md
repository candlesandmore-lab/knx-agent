# knx-agent

knx-agent is a KNX investigation platform built around one shared core API. The same capabilities are exposed through a Python SDK, a Typer CLI and an MCP tool server (MCPServer, from mcp 2.x, formerly FastMCP). The adapters only delegate to the SDK, which calls the application layer. At this stage only the `describe_session` capability exists, with a placeholder body.

## Package layout

```
src/knx_agent/
  contracts/     request/response models, response envelope, error types
  domain/        domain concepts (placeholder)
  application/   core capabilities (describe_session)
  sdk/           KnxSessionClient, the Python entry point
  cli/           Typer CLI adapter (`knx-agent session describe --session <label>`)
  adapters/mcp/  MCP adapter (MCPServer, mcp 2.x), tool name `describe_session`
  agent_layer/   agent-facing layer (placeholder)
tests/
  conftest.py    YAML fixture loader and parametrization hook
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

## Test fixtures

Test input data lives in YAML files, not in test modules.

| File | Content |
| --- | --- |
| `tests/fixtures/describe_session_cases.yaml` | `describe_session` cases |

Format of `describe_session_cases.yaml`:

- `valid`: list of cases with `id`, `session_label`, `expected_setup`, `expected_active_setup`, `expected_evidence_sources` (list) and `expected_limitation_note_contains` (substring that must appear in a limitation note).
- `invalid`: list of cases with `id`, `session_label` (empty or whitespace) and `expected_error_code` (`INVALID_REQUEST`).

To add a case, append an entry with a unique `id`; no Python change is needed. `tests/conftest.py` loads the file
(`load_fixture`) and parametrizes any test that requests the `valid_case` or `invalid_case` argument. The SDK tests and the CLI and MCP delegation tests use these fixtures.

## Environment variables

None are required.

## Run the tests

```
uv run pytest tests
```
