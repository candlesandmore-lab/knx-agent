# Implementation order of the todos (agreed 2026-10-24)

Work through the todos in this order, each through the normal flow (todo -> story -> review -> plan -> implementation -> QA -> final alignment). Update this file when a todo is done or the order changes.

## Done
| Todo | Result |
| --- | --- |
| 01 capability contracts | story 1, catalogue in docs/implementation/003 |
| 02 package skeleton and core API | story 2 |
| 03 session service and project refresh | story 3 |
| 04 .knxproj import and project graph | story 4 (query part moved to todo 15) |
| 15 component inspection capabilities | story 5 (list_components, describe_component, summarize_topology, trace_group_flow) |
| 16 demo CLI scripts | story 6 (`./demo`, run `demo/run-all.sh`) |

## Next, in this order
| Step | Todo | Why here | Needs from the user |
| --- | --- | --- | --- |
| 1 | 17 Module-instance support in the import | Small, no blockers. Makes the component data complete (sample component P-051B-0_DI-37: 12 communication objects and 14 parameters unresolved, 26 warnings). Typing, direction labels, simulation and purposes build on it. | nothing |
| 2 | 12 Dependency license governance | Small; add the pytest license check early while dependencies are few (xknxproject GPL-2.0 must stay dev-only; pyyaml, pydantic, typer, mcp, hatchling need records). | which license families to exclude beyond generally-free ones (open question in the todo) |
| 3 | 06 Environment, user actions, scenario state | Makes the data "live" (set a sensor value, inject a button press). Needs only the project import, so it can start before any trace exists. | nothing known; check the open question 'per mutation or per session' (decided by catalogue C5: mutation seeded from the default's history) |
| 3b | 05 Bus-trace ingestion | Slot in as soon as the sample exists; feeds the scenario state (last-come-wins). Notes: development/todos/05.1-monitor-trace-info.md. | a sample ETS 6 Professional bus monitor export (XML preferred, CSV possible) under `tests/lifedata/` |
| 4 | 08 Mutations and log books | Builds on scenario state (a mutation is created from the current inputs). Also adds select_setup, read_session_log_book and the ERROR level to the log book filter; replaces the MUTATION_NOT_FOUND placeholder of the query capabilities. | nothing known |
| 5 | 07 Expectation engine and activity questions | Core "should this happen / why not" reasoning; needs 04, 05, 06 and should be mutation-aware, so it follows 08. | nothing known |
| 6 | 09 Component knowledge enrichment and 14 Purpose annotation | Both are blocked on user decisions; purposes mainly help the reasoning. | 09: sanctioned documentation sources and the first device family (scraping legality open). 14: source of the purpose rules (curated table or vendor data) |
| 7 | 10 CLI and MCP adapter parity | Mostly delivered capability by capability; do a final parity pass. | MCP hosting mode (local CLI + VS Code vs. remote service) |
| 8 | 11 Agent layer | The only place natural language is handled; needs the stable contracts from 06-08 and 10. | target agent hosts (GHCP, Claude or similar) |
| 9 | 13 Fixtures and end-to-end validation | Continuous; the final walkthroughs only make sense once 07 and 08 exist. | optional: more sanitized samples |

## Rules that apply to every step
- Demo rule (todo 16): once a todo adds actions or features, add examples to `./demo` (scripts and README) and keep the existing demo scripts and `tests/test_demo_scripts.py` working.
- Domain-visible choices (names, options, output shapes, defaults) are put to the user with a question; internal choices are documented with options and rationale in the story.
- Real data: ETS 6 Professional only; sample `tests/lifedata/20261010-EFH-Armbruster.knxproj` (committed; keep personal names out of code, docs and fixtures; assert counts, ids and structure).

## State when this file was written (2026-10-24)
- `main` holds stories 1-5 (fast-forwarded, not pushed). Story 6 (demo) is committed on branch `story/06-demo-cli-scripts` and not merged yet. Todo 17 and this file are new and uncommitted, as is the user's note `05.1-monitor-trace-info.md`.
- 1119 tests pass (1087 + 32 skips when the sample is absent).
- Start tomorrow with: merge story 6 into main if the user agrees, commit todos 00, 05.1 and 17, then take todo 17 as the next story (branch from main). See also `development/working-state/resume.md`.
