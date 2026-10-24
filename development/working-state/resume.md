# Working state (saved 2026-10-24)

Resume rule: read this file, then verify reality (git status, `uv run pytest` through the MCP pytest tool) before trusting it.

## Where the work stands
- Stories 01-05 are implemented (see `development/backlog/implemented/`). `main` contains stories 01-04 (fast-forwarded to 435d281 by user request, not pushed). Story 05 (todo 15, component inspection capabilities) is committed on branch `story/05-component-inspection-capabilities` (not yet on main; the user decides when main is updated).
- No active story. `development/backlog/active` and `open` are empty.
- Test suite: 1088 tests pass (1064 + 24 skips when `tests/lifedata/20261010-EFH-Armbruster.knxproj` is absent).
- Implemented capabilities (SDK `KnxSessionClient`, CLI `knx-agent ...`, MCP `knx-agent-mcp`): create_session, describe_session, reimport_system_definition, list_components, describe_component, summarize_topology, trace_group_flow.

## Remaining todos (development/todos)
- 05 bus-trace ingestion: BLOCKED on a sample ETS 6 Professional bus monitor trace file from the user (XML or CSV export; put it under tests/lifedata/).
- 06 environment/user action/scenario state, 07 expectation engine, 08 mutations and logbooks (log book filter must accept ERROR; MUTATION_NOT_FOUND placeholder exists), 09 component knowledge enrichment, 10 CLI/MCP adapters (largely delivered per capability; review what remains), 11 agent layer, 12 dependency license governance (records for lxml-not-used, xknxproject dev-only GPL-2.0, pyyaml, pydantic, typer, mcp), 13 fixtures and end-to-end validation, 14 component purpose annotation.
- Open verification items: meaning of the order of group address links (first link = sender?) unverified, real ETS 6 scene structure unverified (sample has none).

## Decisions made by the user (do not re-ask)
- ETS 6 Professional only; bus traces from the ETS 6 Professional bus monitor.
- Own parser; xknxproj/xknxproject (GPL-2.0, repository LICENSE is MIT) only as a dev-group test cross-check.
- The sample project tests/lifedata/20261010-EFH-Armbruster.knxproj is committed (contains personal data; keep names out of code, docs and fixtures, assert counts/ids/structure).
- Session root default `./.knx-agent/sessions`, only via --session-root / session_root=; no environment variables. Any issue is ERROR (Python logging + session log book, always written); import warnings are not issues. DTD/entity/encoding problems: required parts fail, optional parts skipped with a warning.
- Terms confirmed and in the dictionary: Session root, Location, Instance path, Component selector, Selector kind, Match kinds, Communication object, ETS id, Direction label.
- Query rules: instance path = location path incl. component name; ANY selector detection; leading '/' anchors, trailing '/' lists a location; three distinct detail levels; trace_group_flow = direct participants only, direction from flags only (SENDER/RECEIVER/SENDER_RECEIVER/UNDETERMINED), set with ambiguous=true on multi-match.

## Process lessons
- Tool rules: Python, pytest, YAML validation and git operations only through the MCP tools (python_execution, pytest_execution, validate_yaml, git_*); Edit/Write for files; `uv lock`/`uv add --dev` in the terminal is accepted (no MCP tool); never a plain `uv sync`. Merge to main uses `git_branch_sync` switch to main then pull with remote "." and the branch (fast-forward).
- Coded agents: `review-validation-agent` only reads `active_story` content passed INLINE (include everything: success criteria, shipped_asset_alignment with rationales, step 5-8 artifacts); it cannot read files and often repeats "nothing ran" prose. Use the structured `request` parameter for coded_agent_invoke (the raw form truncates). `story-telling-agent` ignores side notes on the first call; resume the same task id with resolved_open_questions and revision_notes, then write the story file yourself (it never persists). `qa-agent`: NEW task id each time, validation_scope as a list, plus pytest_scope and yaml_paths; `pass_fail_result` is the evidence.
- Subagent reports are not user input. Domain-visible choices (names, options, output shapes, defaults) go to the user with AskUserQuestion; internal choices are documented with options and rationale in the story.
- Commit with explicit care: stage `.` only after `git status` shows no stray files; end commit messages with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; do not push or open PRs unless asked.
