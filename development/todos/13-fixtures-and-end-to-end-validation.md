# Todo 13: Fixtures, parity tests, end-to-end walkthroughs
Source: implementation 002 (validation strategy), task plan completion conditions
Goal: sanitized `.knxproj` and trace fixtures, graph/decoding snapshots, session-state and mutation/log-book fixtures, golden CLI/SDK/MCP outputs, use-case-to-contract traceability test, provenance regression tests; manual walkthroughs (project-only fault, project+trace fault, session resume, on-disk project edit triggers re-import).
Depends on: 03-11 (fixtures needed earlier by 04/05)

Additional information (user, 2026-10-24): real data is ETS 6 Professional. First real project sample: `tests/lifedata/20261010-EFH-Armbruster.knxproj` (committed by user decision; contains personal data). Bus traces are ETS 6 Professional bus monitor exports (sample still to be supplied under `tests/lifedata/`). Tests that need real data run against tests/lifedata and skip with a clear message when a file is absent; small synthetic `.knxproj` fixtures remain for fast tests.

Note: the demo rule of todo 16 does not apply to this todo unless it adds user-facing actions (then add examples to ./demo).
