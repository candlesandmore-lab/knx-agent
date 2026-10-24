# Todo 02: Python package skeleton and shared core API
Source: docs/implementation/002 (package boundaries, Slice 1a)
Goal: uv-managed `src/knx_agent` layout (domain/application/adapters/sdk/cli/agent_layer/contracts), pytest scaffolding, one callable core API (SDK-facing) that CLI and MCP will only wrap, structured result models carrying provenance and limitation notes.
Rules: every Python slice ships with pytest; SDK-first testing.
Depends on: 01 (contract shape)
