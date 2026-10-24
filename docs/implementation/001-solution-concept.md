# Implementation 001: Solution Concept

The first usable version is an investigation copilot for one KNX project at a time. A user (a human
on the CLI, a program on the SDK, or an agent on MCP) creates a session from a `.knxproj` path, adds
optional bus traces, environment values and user actions, asks questions about the resulting system
state, and can run parameter-only what-if mutations. An agent/skill layer sits above the tool surfaces
and turns natural language into deterministic capability calls without guessing.

This document no longer defines capabilities, capability families, domain concepts or data flow.

- Capability definitions, conventions and use-case traceability: `docs/implementation/003-proposed-capability-apis.md` (the single authoritative catalogue, status reviewed draft).
- Architecture and domain concepts: `docs/architecture/001-knx-investigation-platform.md`.
- Terminology: `docs/methodology/02-terminology-dictionary.md`.
- Use cases: `docs/methodology/001-use-cases-raw.md`.

Remaining valid non-capability content from the earlier version was migrated to the appendix of
`docs/implementation/003-proposed-capability-apis.md`; the rest was discarded there explicitly.
