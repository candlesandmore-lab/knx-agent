# knx-agent demo

## 1. What this demo is

A guided tour of everything the knx-agent command line can do today. It runs on the real ETS 6 sample project `tests/lifedata/20261010-EFH-Armbruster.knxproj` (a real house: 28 components, 695 group addresses). You start by creating an investigation session from the project file and then try every available action: describe and re-import a session, list and describe components, summarize the topology, trace a group address, and see three typical errors.

Each step is a small script in this folder. The scripts only call the real `knx-agent` command; they print every command before it runs, so you can copy it and try your own variations. The scripts are written for the sample project and for this development workspace. Only the command line is shown here (see section 8 for the other ways to use knx-agent).

## 2. Prerequisites

- macOS or Linux with `bash`.
- `uv` installed, and `uv sync` done once in the repository (see the main [README](../README.md)).
- The sample file present at `tests/lifedata/20261010-EFH-Armbruster.knxproj`.
- Nothing else. The demo needs no environment variables and does not change any.

## 3. Quick start

```
demo/run-all.sh
```

This removes any earlier demo session, then runs the scripts 01 to 07 in order and ends with a summary such as `Tour complete: 7 of 7 scripts passed`. The whole tour takes about ten seconds.

- The demo keeps its sessions in `demo/.sessions`. This folder is the *session root*, the folder that holds all sessions. Git ignores it.
- Every script accepts an optional first argument: another session root. A relative path is taken from the repository root, an absolute path is used as it is. Example: `demo/run-all.sh /tmp/my-demo-sessions`.
- You can start the scripts from any folder; they always switch to the repository root first.
- Run a single script when you want to look at one topic, for example `demo/03-list-components.sh`. Scripts 02 to 07 need the session made by script 01 and tell you so if it is missing.

## 4. How to read the output

For every call you see:

1. The command, shown as you could type it: `$ knx-agent setup list-components --session demo-house ... --session-root <folder>`. (The scripts run it as `uv run knx-agent ...`.)
2. The answer as formatted JSON. Long answers are shortened after a number of lines; the line "top-level values further down" then repeats the short values such as `match_count`.
3. A `RESULT` line: `RESULT <call> exit=<code> name=value ...`. It is a compact summary of the call that people and the automated test can read the same way.

How to tell success from failure:

- Success: exit code 0, the answer as JSON on stdout. Messages that appear in addition (lines starting with `WARNING` or `INFO`) are log output on stderr. The warnings say that the sample project has some parts the importer could not fully resolve; this is information, not a failure.
- Failure: exit code 1, nothing on stdout. On stderr you see one `ERROR` log line and then the error as JSON with three fields: `code` (a fixed name such as `SESSION_NOT_FOUND`), `message` (a sentence) and `details` (facts about the problem).

## 5. The tour in order

### 01-create-session.sh : create the session

| Command | Purpose | What to expect |
| --- | --- | --- |
| `knx-agent session create --project tests/lifedata/20261010-EFH-Armbruster.knxproj --session-label demo-house` | Import the project into a new investigation session called `demo-house`. | A JSON answer with `session_label`, the session folder (`work_directory`) and a `project_import_summary` that counts what was found: components, communication objects, group addresses, warnings. `RESULT create ... components=28 group_addresses=695 warnings=26`. |

Run it twice and the second time it reports that the session already exists (`SESSION_LABEL_EXISTS`) and stops with success; use `demo/cleanup.sh` to start afresh.

### 02-describe-and-reimport.sh : look at the session, re-read the project

| Command | Purpose | What to expect |
| --- | --- | --- |
| `knx-agent session describe --session demo-house` | Show what the session knows. | `project_refresh.last_status` UNCHANGED, `reimport_count` 0 and the import summary again. |
| `knx-agent session describe --session demo-house --log-level DEBUG` | The same answer with more log lines on stderr. | The same JSON. `--log-level` (INFO, DEBUG or FULL) only changes how much is logged. |
| `knx-agent session reimport --session demo-house` | Read the project file again and compare. | `project_refresh_status` UNCHANGED, `changes` empty, `invalidated_references` empty, because the file did not change. |

### 03-list-components.sh : find components

The script first reads the full list once and picks example values from the project (a name, an address, an id, a location). Then it calls `list-components` several ways. A *component* is a device of the project. An *instance path* is the location of a component plus its own name, separated by `/`, for example `Building/Floor/Room/Device`. A *selector* is the text you give to find components. If you leave out `--selector-kind`, the default is `ANY`: the program recognises the kind of text itself. We call that a generic query.

| Command | Purpose | What to expect |
| --- | --- | --- |
| `knx-agent setup list-components --session demo-house --detail-level SUMMARY` | No query: all components. | `match_count` 28, `ambiguous` False (a full listing is never ambiguous). |
| `... --query <part of a name> --detail-level SUMMARY` | Query by partial name; upper and lower case do not matter. The script takes the first run of at least four letters or digits from the picked component's name (so it matches several components). | Several matches, `ambiguous` True, each with `match_kinds` NAME. |
| `... --query <individual address, e.g. 1.1.5> --detail-level SUMMARY` | Query by individual address. | Exactly one match, `match_kinds` INDIVIDUAL_ADDRESS. |
| `... --query <ETS id> --detail-level SUMMARY` | Query by ETS id, the identifier inside the project file. | Exactly one match, `match_kinds` ETS_ID. |
| `... --query "<Building>/<Floor>/<Room>/" --detail-level SUMMARY` | Query by location: an instance path with a slash at the end. | Every component placed in that location, including nested locations. |
| the location query with `--detail-level SUMMARY` | Detail level SUMMARY. | Identity (name, address, ETS id, instance path) and the derived component type only. |
| the location query with `--detail-level MEDIUM` | Detail level MEDIUM (the default). | Adds `topology` (area, line, location path) and `component_parameters`. |
| the location query with `--detail-level FULL` | Detail level FULL. | Adds `communication_objects` (with flags and group addresses), `group_addresses`, `product`, `application`. |

The detail level only adds fields; fields of a higher level are missing, not empty, at a lower level.

### 04-describe-component.sh : one component in detail

| Command | Purpose | What to expect |
| --- | --- | --- |
| `knx-agent setup describe-component --session demo-house --component <ETS id> --detail-level MEDIUM` | Describe one component. | `components` with one entry: identity, derived type, topology, parameters. |
| `knx-agent setup describe-component --session demo-house --component <ETS id> --detail-level FULL` | The same component with everything. | The list `communication_objects`. Each object has a `label`, `flags` (read, write, transmit, update, ...) and the `group_addresses` it is linked to. |

`describe-component` takes the same kinds of selector as `list-components`. When nothing matches it is an error (see script 07), not an empty list.

### 05-summarize-topology.sh : the shape of the installation

| Command | Purpose | What to expect |
| --- | --- | --- |
| `knx-agent setup summarize-topology --session demo-house --detail-level SUMMARY` | Overview. | `topology_summary.counts` (areas 2, lines 3, locations 21), `locations_by_type` and `component_counts` (total, placed, unplaced, by component type). |
| `... --detail-level MEDIUM` | Adds structure. | The areas with their lines, and the list of locations with the number of components in each. |
| `... --detail-level FULL` | Adds the members. | The component names and individual addresses under every line and location. |

### 06-trace-group-flow.sh : who talks on a group address

A *group address* is the address that devices send to and listen on (for example `0/1/5`). A *communication object* is one data point of a component. Both are linked in the project.

| Command | Purpose | What to expect |
| --- | --- | --- |
| `knx-agent setup trace-group-flow --session demo-house --group-address <address>` | Trace one group address. | One entry in `group_addresses`; its `participants` list the components and objects linked to it, each with a `direction`. |
| `knx-agent setup trace-group-flow --session demo-house --group-address <word of a name> --detail-level SUMMARY` | Text that is not an address is searched in group address names. | A whole set (`match_count` over 100, `ambiguous` True). |
| `knx-agent setup trace-group-flow --session demo-house --object-ref <communication object id>` | Start from one communication object. | One entry per group address that the object is linked to. |

The direction labels come only from the flags of the communication object in the project: `SENDER` (it transmits), `RECEIVER` (it accepts writes or updates), `SENDER_RECEIVER` (both) and `UNDETERMINED` (no usable flag). There is no routing and no live bus data: `current_value` is always `unknown`.

### 07-errors.sh : three calls that fail on purpose

| Command | Purpose | What to expect |
| --- | --- | --- |
| `knx-agent session describe --session demo-no-such-session` | A session that does not exist. | Exit 1, code `SESSION_NOT_FOUND`, `details.session_label` is the label asked for. |
| `knx-agent setup describe-component --session demo-house --component no-such-component-xyz` | A component that does not exist. | Exit 1, code `SELECTOR_UNRESOLVED`. `details` shows the `selector` you gave, the `selector_kind` (ANY) and `evaluated_kinds` (what was tried). |
| `knx-agent setup trace-group-flow --session demo-house --group-address 31/7/255` | A well-formed group address that the project does not use. | Exit 1, code `SELECTOR_UNRESOLVED`; `details.selector_kind` is GROUP_ADDRESS. |

These failures are the expected result. The script ends with success when all three failed with exit 1 and the right code, and the tour carries on.

## 6. Reading the JSON in more detail

| Field | Meaning |
| --- | --- |
| `envelope` | Bookkeeping of every answer: `detail_level`, `limitation_notes` (things to keep in mind, such as import warnings) and `log_book_entry_id`. |
| `match_count` | How many results the query found. |
| `ambiguous` | True when you gave a selector and more than one result matches. |
| `match_kinds` | How a selector matched: NAME, INDIVIDUAL_ADDRESS, ETS_ID or INSTANCE_PATH. Only present when a selector was given. |
| `identity.instance_path` | Location path plus component name; `null` for a component not placed in any location. |
| `derived.component_type` | The agent's own coarse guess (sensor, actuator, ...). It is derived, not read from the project. |
| `communication_objects[].flags` | What the object may do: read, write, communication, transmit, update, read_on_init. |
| `participants[].direction` | SENDER, RECEIVER, SENDER_RECEIVER or UNDETERMINED (see script 06). |

## 7. Clean up

```
demo/cleanup.sh                 # removes demo/.sessions
demo/cleanup.sh <session-root>  # removes another session root you used
demo/cleanup.sh <session-root> --dry-run   # only says what it would do
```

`cleanup.sh` removes only a *session root*: a folder whose name ends in `.sessions`, or a folder that contains nothing but session folders. It refuses (exit code 2, nothing deleted, message starting `cleanup.sh: refused:`) to touch the filesystem root, your home folder, this repository or any folder above it, the `demo` and `tests` folders, anything that is not an existing plain folder (missing paths, files, symbolic links) and any folder with other content. If the default `demo/.sessions` does not exist it says "Nothing to clean".

`demo/run-all.sh` calls `cleanup.sh` first, so every full tour starts fresh, and leaves the session in place afterwards so you can look at it.

## 8. Beyond the command line

The same capabilities are available as a Python SDK (`KnxSessionClient`) and as MCP tools (`knx-agent-mcp`) for agents. They are not part of this demo; see the main [README](../README.md).

## 9. Maintaining the demo (for developers)

**The demo rule.** Once a todo or story is implemented, it adds examples for its new actions and features to `./demo` (scripts, expectation entries and README text) and keeps the existing demo scripts working. The todos 05 to 11 and 14 carry this rule as a line.

Files:

- `lib.sh` holds the shared helpers (sourced, never run). `run-all.sh` and `cleanup.sh` are described above.
- `01-` to `07-` are the numbered tour scripts.
- `demo/.sessions` is the default session root (git-ignored).

To add a script:

1. Copy a numbered script, name it with the next number and use the helpers of `lib.sh`: `demo_init`, `demo_run <call id> <cli arguments>`, `demo_show`, `demo_report` (or `demo_report_error` and `demo_expect_error` for an error example), `demo_finish`.
2. Derive names, addresses and ids from CLI output at run time (`demo_pick_example`); never type personal names of the sample into a script.
3. Add the script to the list in `run-all.sh`.
4. Add its expectations to `tests/fixtures/demo_script_expectations.yaml` and mention the script in this README.

Rules for the scripts: no environment variables, no `set -e` (a failing call must not stop the tour), always print the command before running it, and end every call with one `RESULT` line. A `RESULT` line reads `RESULT <call> exit=<code>` followed by `name=value` pairs; error examples carry `error_code=<CODE>`.

The guard is `tests/test_demo_scripts.py`. It runs every script against the sample with a temporary session root, compares the `RESULT` lines with the expectation file (exit codes, error codes and key fields, no exact snapshots), checks that this README mentions every script, that all seven CLI actions appear in the scripts, that the todos carry the demo rule, that `cleanup.sh` refuses unsafe paths, and that nothing under `demo/` contains the family name of the sample owner (the only allowed occurrence is the sample file name). The test is skipped with a clear message when the sample file is absent.
