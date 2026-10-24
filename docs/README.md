# KNX Agent Documentation

This repository starts with solution-definition documents before code implementation.

## Reading order

1. [Terminology dictionary](./methodology/02-terminology-dictionary.md) defines the shared terminology used across architecture, implementation, and agent workflows.
2. [Architecture 001](./architecture/001-knx-investigation-platform.md) defines the target solution shape, core boundaries, and external dependencies.
3. [Methodology 001](./methodology/001-use-cases-raw.md) captures the raw user use cases and clarifications that drive the proposed API surface.
4. [Implementation 001](./implementation/001-solution-concept.md) is a short reference stub: a brief solution preamble pointing to Implementation 003.
5. [Implementation 002](./implementation/002-bootstrap-implementation-plan.md) is a short reference stub pointing to Implementation 003; delivery is planned through `development/todos/`.
6. [Implementation 003](./implementation/003-proposed-capability-apis.md) is the single authoritative capability catalogue (19 capabilities, conventions, use-case traceability); status: reviewed draft.

## Current status

The current document set is intentionally assumption-heavy. It is a bootstrap package meant to be refined as project-specific KNX requirements, available runtime environments, and representative `.knxproj` samples become available.