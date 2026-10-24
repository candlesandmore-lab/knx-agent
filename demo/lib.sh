# Shared helpers of the knx-agent demo scripts. Sourced by the numbered scripts and run-all.sh, never executed.
#
# Contract for maintainers (see demo/README.md, section "Maintaining the demo"):
#   - Plain bash that also runs on macOS bash 3.2: no associative arrays, no mapfile.
#   - Every script starts with:  source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"; demo_init "$@"
#     demo_init changes into the repository root, so relative paths mean the same whatever the current directory is.
#   - The demo reads and sets no environment variables (only shell variables of its own).
#   - Never use "set -e": a failing call or an error example must not stop the tour.
#   - Every call is made through demo_run (prints the command first) and ends with one RESULT line
#     (demo_report for a call that must succeed, demo_report_error + demo_expect_error for an error example).
#   - Values such as component names, addresses and ids are derived at run time (demo_pick_example), never typed here.

DEMO_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$DEMO_LIB_DIR/.." && pwd -P)"
SAMPLE="tests/lifedata/20261010-EFH-Armbruster.knxproj"
SESSION_LABEL="demo-house"
DEFAULT_SESSION_ROOT="demo/.sessions"
DEMO_FAILED=0
LAST_ID=""
LAST_RC=0
LAST_OUT=""
LAST_ERR=""

# demo_init [session-root]: go to the repository root, fix the session root, prepare temporary files.
demo_init() {
    cd "$REPO_ROOT" || { echo "demo: cannot change into $REPO_ROOT" >&2; exit 2; }
    SESSION_ROOT="${1:-}"
    if [ -z "$SESSION_ROOT" ]; then
        SESSION_ROOT="$DEFAULT_SESSION_ROOT"
    fi
    if ! command -v uv >/dev/null 2>&1; then
        echo "demo: the tool 'uv' was not found. Install uv first (see demo/README.md, Prerequisites)." >&2
        exit 2
    fi
    if [ ! -f "$SAMPLE" ]; then
        echo "demo: the sample project was not found: $SAMPLE" >&2
        exit 2
    fi
    LAST_OUT="$(mktemp -t knxdemo-out.XXXXXX)" || exit 2
    LAST_ERR="$(mktemp -t knxdemo-err.XXXXXX)" || exit 2
    trap 'rm -f "$LAST_OUT" "$LAST_ERR"' EXIT
}

# ----- Printing helpers -----------------------------------------------------------------------------------------

# demo_header <script file name> <title> <purpose>
demo_header() {
    echo
    echo "================================================================================"
    echo "$1 - $2"
    echo "$3"
    echo "================================================================================"
}

demo_step() {
    echo
    echo "## $1"
}

demo_note() {
    echo "   $1"
}

# demo_quote_args <args...>: the arguments as a user could type them (quotes only where needed).
demo_quote_args() {
    local out="" a q
    for a in "$@"; do
        case "$a" in
            "") q="''" ;;
            *[!A-Za-z0-9_./:=@%+,-]*) q="'$a'" ;;
            *) q="$a" ;;
        esac
        out="$out $q"
    done
    printf '%s' "${out# }"
}

# ----- Running calls ----------------------------------------------------------------------------------------------

# demo_run <call id> <cli arguments...>: print the command, run the real CLI, keep stdout, stderr and exit code.
# The session root is appended here; the callers never pass --session-root.
demo_run() {
    LAST_ID="$1"
    shift
    echo
    echo "\$ knx-agent $(demo_quote_args "$@") --session-root $(demo_quote_args "$SESSION_ROOT")"
    uv run knx-agent "$@" --session-root "$SESSION_ROOT" >"$LAST_OUT" 2>"$LAST_ERR"
    LAST_RC=$?
}

# demo_show [max_lines]: pretty-print the JSON answer (shortened), or the error when the call failed.
demo_show() {
    local max="${1:-40}"
    if [ "$LAST_RC" -ne 0 ]; then
        demo_show_error
        return 0
    fi
    uv run python -c '
import json, sys
scalars = {}
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if isinstance(data, dict):
        scalars = {key: value for key, value in data.items() if not isinstance(value, (dict, list))}
except Exception:
    with open(sys.argv[1], encoding="utf-8") as handle:
        text = handle.read()
lines = text.splitlines()
limit = int(sys.argv[2])
print("\n".join(lines[:limit]))
if len(lines) > limit:
    print("... %d more lines (the full JSON is long; run the command to see all of it)" % (len(lines) - limit))
    if scalars:
        print("top-level values further down: " + ", ".join("%s=%s" % (k, v) for k, v in scalars.items()))
' "$LAST_OUT" "$max"
    if [ -s "$LAST_ERR" ]; then
        echo "log output (stderr):"
        sed 's/^/  /' "$LAST_ERR"
    fi
}

# demo_show_error: print the stderr of a failed call (log line, then the error as pretty JSON) and the exit code.
demo_show_error() {
    echo "The call failed. Exit code: $LAST_RC. Nothing on stdout; the error is on stderr:"
    uv run python -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    lines = [line.rstrip("\n") for line in handle if line.strip()]
if not lines:
    print("  (stderr is empty)")
else:
    for line in lines[:-1]:
        print("  " + line)
    try:
        text = json.dumps(json.loads(lines[-1]), indent=2, ensure_ascii=False)
    except Exception:
        text = lines[-1]
    print("\n".join("  " + row for row in text.splitlines()))
' "$LAST_ERR"
}

# ----- Reading JSON -----------------------------------------------------------------------------------------------

# demo_json <python expression on d>: print the value from the stdout JSON of the last call.
demo_json() {
    uv run python -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    d = json.load(handle)
print(eval(sys.argv[2]))
' "$LAST_OUT" "$1"
}

# demo_error_json <python expression on e>: print a value from the ErrorInfo JSON (last stderr line) of the last call.
demo_error_json() {
    uv run python -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    lines = [line for line in handle if line.strip()]
e = json.loads(lines[-1])
print(eval(sys.argv[2]))
' "$LAST_ERR" "$1"
}

# ----- RESULT lines -----------------------------------------------------------------------------------------------

# demo_report <call id> [<label>=<python expression on d> ...]
# Prints "RESULT <id> exit=<rc> <label>=<value> ..."; a call that was expected to succeed but did not counts as failed.
demo_report() {
    local id="$1"
    shift
    if [ "$LAST_RC" -ne 0 ]; then
        demo_report_error "$id"
        DEMO_FAILED=$((DEMO_FAILED + 1))
        echo "FAILED: $id"
        return 0
    fi
    local fields
    fields="$(uv run python -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    d = json.load(handle)
parts = []
for spec in sys.argv[2:]:
    label, expression = spec.split("=", 1)
    try:
        value = eval(expression, {}, {"d": d})
    except Exception:
        value = "ERROR"
    if isinstance(value, (list, tuple)):
        value = ",".join(str(item) for item in value)
    text = "_".join(str(value).split()) or "-"
    parts.append(label + "=" + text)
print(" ".join(parts))
' "$LAST_OUT" "$@")"
    echo "RESULT $id exit=$LAST_RC${fields:+ $fields}"
}

# demo_report_error <call id>: RESULT line with the error code of the last call (NONE when it succeeded).
demo_report_error() {
    local id="$1" code="NONE"
    if [ "$LAST_RC" -ne 0 ]; then
        code="$(demo_error_json "e['code']" 2>/dev/null)"
        if [ -z "$code" ]; then
            code="UNPARSEABLE"
        fi
    fi
    echo "RESULT $id exit=$LAST_RC error_code=$code"
}

# demo_expect_error <call id> <expected code>: the call must have failed with exit 1 and exactly that code.
demo_expect_error() {
    local id="$1" expected="$2" code="NONE"
    if [ "$LAST_RC" -ne 0 ]; then
        code="$(demo_error_json "e['code']" 2>/dev/null)"
    fi
    if [ "$LAST_RC" -ne 1 ] || [ "$code" != "$expected" ]; then
        DEMO_FAILED=$((DEMO_FAILED + 1))
        echo "FAILED: $id (expected exit 1 with $expected, got exit $LAST_RC with $code)"
    fi
}

# demo_finish: end of a script; exit 1 when any call failed unexpectedly.
demo_finish() {
    echo
    if [ "$DEMO_FAILED" -gt 0 ]; then
        echo "$DEMO_FAILED call(s) did not behave as expected."
        exit 1
    fi
    echo "All calls behaved as expected."
    exit 0
}

# ----- Session and example values ---------------------------------------------------------------------------------

# demo_require_session: stop with a hint when the session demo-house does not exist in the session root.
demo_require_session() {
    uv run knx-agent session describe --session "$SESSION_LABEL" --session-root "$SESSION_ROOT" >"$LAST_OUT" 2>"$LAST_ERR"
    LAST_RC=$?
    if [ "$LAST_RC" -ne 0 ]; then
        echo "Session $SESSION_LABEL not found in $SESSION_ROOT. Run demo/01-create-session.sh first (or demo/run-all.sh)."
        exit 1
    fi
}

# demo_pick_example: derive the example values of this run from the project (nothing is typed in by hand).
# Sets EX_NAME_PART EX_ADDRESS EX_ETS_ID EX_INSTANCE_PATH EX_LOCATION_QUERY EX_GROUP_ADDRESS EX_OBJECT_REF EX_NAME_WORD.
demo_pick_example() {
    demo_note "The example values below (a name, an address, an id, a path, a group address) are looked up in the"
    demo_note "project at run time: first a broad listing of all components is read, then the first suitable one is used."
    demo_run pick setup list-components --session "$SESSION_LABEL" --detail-level FULL
    if [ "$LAST_RC" -ne 0 ]; then
        demo_show_error
        echo "demo: the listing needed for the examples failed."
        exit 1
    fi
    local picked
    picked="$(uv run python -c '
import json, re, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    d = json.load(handle)
STRIP = ".,;:()[]"
group_names = {}
for component in d["matches"]:
    for obj in component.get("communication_objects", []):
        for group in obj.get("group_addresses", []):
            if group.get("name"):
                group_names[group["address"]] = group["name"]
found = None
for component in d["matches"]:
    identity = component["identity"]
    name = (identity.get("name") or "").strip()
    path = identity.get("instance_path")
    if not name or not path or "/" not in path:
        continue
    first_segment = name.split("/")[0].strip()
    # Name part: the first run of at least 4 letters or digits that also matches at least 2 components (the whole run,
    # else its first 4 characters); fallback: the first 4 non-space characters.
    all_names = [(c["identity"].get("name") or "").casefold() for c in d["matches"]]
    runs = re.findall(r"[^\W_]{4,}", first_segment)
    part = ""
    for candidate in [run for run in runs] + [run[:4] for run in runs]:
        if sum(1 for n in all_names if candidate.casefold() in n) >= 2:
            part = candidate
            break
    if not part:
        part = "".join(first_segment.split())[:4]
    if not part:
        continue
    for obj in component.get("communication_objects", []):
        if obj.get("group_addresses"):
            found = (component, part, obj)
            break
    if found:
        break
if not found:
    sys.exit(3)
component, part, obj = found
identity = component["identity"]
path = identity["instance_path"]
location_query = "/".join(path.split("/")[:-1]) + "/"
address = obj["group_addresses"][0]["address"]
counts = {}
for name in set(group_names.values()):
    for word in set(token.strip(STRIP) for token in name.split()):
        if len(word) >= 3:
            counts[word] = counts.get(word, 0) + 1
word = None
if counts:
    best = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    if best[1] >= 2:
        word = best[0]
if word is None:
    own = group_names.get(address) or ""
    words = [token.strip(STRIP) for token in own.split() if token.strip(STRIP)]
    word = words[0] if words else ""
values = [part, identity["individual_address"], identity["ets_id"], path, location_query, address, obj["ets_id"], word]
if not all(values):
    sys.exit(3)
print("\t".join(values))
' "$LAST_OUT")"
    if [ -z "$picked" ]; then
        echo "demo: no suitable example found in the sample"
        exit 3
    fi
    IFS=$'\t' read -r EX_NAME_PART EX_ADDRESS EX_ETS_ID EX_INSTANCE_PATH EX_LOCATION_QUERY EX_GROUP_ADDRESS EX_OBJECT_REF EX_NAME_WORD <<< "$picked"
    echo "RESULT pick exit=$LAST_RC"
    echo "   name part: $EX_NAME_PART | individual address: $EX_ADDRESS | ETS id: $EX_ETS_ID"
    echo "   instance path: $EX_INSTANCE_PATH"
    echo "   location query: $EX_LOCATION_QUERY"
    echo "   group address: $EX_GROUP_ADDRESS | communication object: $EX_OBJECT_REF | name word: $EX_NAME_WORD"
}
