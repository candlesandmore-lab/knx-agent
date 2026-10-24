# Todo 12: Dependency license governance
Source: implementation 002 (Slice 8), architecture 001 (licensing hygiene)
Goal: decision record per non-trivial Python dependency (license, URL, usage, alternatives); automated pytest check blocking non-free-to-use licenses; applies to typer, mcp, parser/trace libraries.
Open: any license families to exclude beyond generally-free ones.
Depends on: starts with 02, continuous

Additional information (user, 2026-10-24): repository LICENSE is MIT. `xknxproject` is GPL-2.0 (upstream sidebar; no permissive reading found) and is therefore only allowed as a development-time cross-check in tests (dev dependency group, never a runtime dependency, no code copied). Pyyaml (runtime since story 03), pydantic, typer, mcp, hatchling and any XML parser (lxml) need license records.
