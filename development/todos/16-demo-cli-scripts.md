# Todo 16: Demo CLI scripts and guide for the sample project
Source: user request 2026-10-24 (no earlier todo; raised after story 05, before todo 05).
Goal: give the end user a hands-on way to see what the current implementation can do, using the committed ETS 6 Professional sample `tests/lifedata/20261010-EFH-Armbruster.knxproj`.
Scope (user wording, points a-d):
- (a) Demo CLI scripts in a new top-level folder `./demo` that work with `tests/lifedata/20261010-EFH-Armbruster.knxproj`.
- (b) Show what is possible at the current implementation level: from creation of a session to ALL available CLI calls (session create / describe / reimport; setup list-components / describe-component / summarize-topology / trace-group-flow), one or two examples for each action (e.g. selector kinds, detail levels, instance path with trailing '/', group address by address and by name, an error case such as an unknown selector or a missing session).
- (c) The examples live in `./demo`.
- (d) `./demo/README.md` guides the end user easily through the possible CLI calls (what to run, in which order, what you will see, how to clean up).
- The scripts are SPECIFIC to the data of the sample project and only need to work in this development workspace (the sample is not shipped with the agent); they must not hard-code personal data beyond what the sample file name already contains where avoidable (take names from the CLI output, e.g. by listing first).
- Standing rule for upcoming todos: every upcoming todo that adds actions or features (05 bus traces, 06, 07, 08, 09, 10, 11, 14 and any later one) must, once implemented, add examples for them to `./demo` (scripts and README) and keep the existing examples working. Add this requirement to the todo files of the upcoming todos.
Constraints: scripts call the real CLI (`knx-agent ...`), use an own session root inside `./demo` that is git-ignored and cleaned up by a script, need no environment variables, and are covered by a pytest that runs them against the sample (skips when the sample is absent) so they cannot rot.
Depends on: 02, 03, 04, 15 (the CLI commands listed above)
