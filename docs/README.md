# KNX Agent Documentation

This repository starts with solution-definition documents before code implementation.

## Reading order

1. [Terminology dictionary](./methodology/02-terminology-dictionary.md) defines the shared terminology used across architecture, implementation, and agent workflows.
2. [Architecture 001](./architecture/001-knx-investigation-platform.md) defines the target solution shape, core boundaries, and external dependencies.
3. [Methodology 001](./methodology/001-use-cases-raw.md) captures the raw user use cases and clarifications that drive the proposed API surface.
4. [Implementation 001](./implementation/001-solution-concept.md) translates the architecture into product capabilities, user workflows, and data responsibilities.
5. [Implementation 002](./implementation/002-bootstrap-implementation-plan.md) defines the first implementation slices, interfaces, and validation expectations.
6. [Implementation 003](./implementation/003-proposed-capability-apis.md) proposes use-case-driven SDK, CLI, MCP, and agent-layer capability contracts.
7. [Bootstrap Task Plan](../development/backlog/active/knx-agent-bootstrap-task-plan.yaml) breaks the first delivery into executable phases.

## Current status

The current document set is intentionally assumption-heavy. It is a bootstrap package meant to be refined as project-specific KNX requirements, available runtime environments, and representative `.knxproj` samples become available.