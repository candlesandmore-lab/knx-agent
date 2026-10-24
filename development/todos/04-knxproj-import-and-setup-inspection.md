# Todo 04: .knxproj import, project graph, setup inspection
Source: architecture 001 (3), implementation 002 (Slice 2), use case 1
Goal: parse `.knxproj` into normalized project graph (installation, lines, areas, devices, communication objects, group addresses, memberships, parameters, scenes, topology) with stable IDs, provenance, import warnings, device typing (purpose annotation itself is todo 14); separate source facts from derived facts. Capabilities: load_project, summarize_topology, list_components (name/purpose/address, detail levels, MEDIUM default, ambiguous selector returns a set), describe_device, find_group_address, trace_group_flow.
Blocker: needs a sanitized representative `.knxproj` sample (or structure description) from the user; ETS version coverage is an open question.
Answered: selector may be name/individual address/ETS id/instance path; partial names (e.g. "Kid") return sets; SUMMARY and MEDIUM = topology + device-level parameters; FULL adds group addresses, communication objects, purpose and anything else available.
Capability names: see todo 01 (find_group_address and load_project missing in 003).
Depends on: 02, 03
