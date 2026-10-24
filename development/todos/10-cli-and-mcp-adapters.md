# Todo 10: SDK, CLI (typer) and MCP (`MCPServer`) tool surfaces
Source: architecture 001 (2, 2a), implementation 002 (Slice 7)
Goal: expose every delivered capability on SDK, `typer` CLI (e.g. `knx-agent session create --project <file>`) and `mcp` `MCPServer` as thin adapters over the same core API; capability parity, no surface drift; MCP responses carry provenance and limitation notes; session id explicit or active-session. Incremental: adapters per capability group as todos 03-09 land.
Open: MCP hosting mode, local CLI + VS Code vs. remote service.
Note: the use cases define "user" as human (CLI), program (SDK) or agent (MCP); MCP is the agent-facing surface.
Depends on: 02 (then incremental with 03-09)
