#!/usr/bin/env bash
# Remove the demo session root.
# Usage: demo/cleanup.sh [session-root] [--dry-run]     (default session root: demo/.sessions)
# Exit code 0: removed, nothing to clean, or dry run accepted. Exit code 2: REFUSED, nothing was deleted.
# Only a folder that looks like a session root is removed: its name ends in .sessions, or every entry in it is a
# session folder (contains session-state.yaml) or an interrupted create (.<label>.creating-<suffix>).
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
cd "$REPO_ROOT" || { echo "cleanup.sh: refused: cannot change into the repository root" >&2; exit 2; }

refuse() {
    echo "cleanup.sh: refused: $1" >&2
    exit 2
}

DRY_RUN=0
ARG_GIVEN=0
ROOT_ARG=""
for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN=1
    elif [ "$ARG_GIVEN" -eq 0 ]; then
        ARG_GIVEN=1
        ROOT_ARG="$arg"
    else
        refuse "unexpected extra argument. Usage: cleanup.sh [session-root] [--dry-run]"
    fi
done

if [ "$ARG_GIVEN" -eq 0 ]; then
    candidate="$REPO_ROOT/demo/.sessions"
    if [ ! -e "$candidate" ] && [ ! -L "$candidate" ]; then
        echo "Nothing to clean: $candidate does not exist."
        exit 0
    fi
else
    candidate="$ROOT_ARG"
    # R1: empty or blank
    case "$candidate" in
        *[![:space:]]*) ;;
        *) refuse "the session root argument is empty" ;;
    esac
fi

# Remove trailing slashes (but keep a lone "/").
while [ "${candidate%/}" != "$candidate" ] && [ -n "${candidate%/}" ]; do
    candidate="${candidate%/}"
done

# R7: a symbolic link is never followed for deletion.
if [ -L "$candidate" ]; then
    refuse "$candidate is a symbolic link"
fi
# R6: must be an existing directory.
if [ ! -d "$candidate" ]; then
    refuse "$candidate is not an existing directory"
fi

resolved="$(cd -P "$candidate" 2>/dev/null && pwd -P)"
if [ -z "$resolved" ]; then
    refuse "$candidate cannot be resolved"
fi

# R2: filesystem root
if [ "$resolved" = "/" ]; then
    refuse "the filesystem root is never removed"
fi
# R3: the home directory
home_dir="$(cd ~ 2>/dev/null && pwd -P)"
if [ -n "$home_dir" ] && [ "$resolved" = "$home_dir" ]; then
    refuse "$resolved is your home directory"
fi
# R4: the repository root or any folder above it
case "$REPO_ROOT/" in
    "$resolved"/*) refuse "$resolved is the repository or contains it" ;;
esac
# R5: the demo and tests folders, anything that holds lib.sh or .git
if [ "$resolved" = "$REPO_ROOT/demo" ] || [ "$resolved" = "$REPO_ROOT/tests" ]; then
    refuse "$resolved is a folder of this repository"
fi
if [ -e "$resolved/lib.sh" ] || [ -e "$resolved/.git" ]; then
    refuse "$resolved contains lib.sh or .git, it is not a session root"
fi

# Acceptance: a name ending in .sessions, or a folder that looks like a session root.
base="${resolved##*/}"
case "$base" in
    *.sessions) ;;
    *)
        for entry in "$resolved"/* "$resolved"/.[!.]* "$resolved"/..?*; do
            if [ ! -e "$entry" ] && [ ! -L "$entry" ]; then
                continue
            fi
            name="${entry##*/}"
            if [ -L "$entry" ] || [ ! -d "$entry" ]; then
                refuse "$resolved holds '$name', which is not a session folder"
            fi
            case "$name" in
                .*.creating-*) ;;
                *)
                    if [ ! -f "$entry/session-state.yaml" ]; then
                        refuse "$resolved holds '$name', which does not look like a session folder"
                    fi
                    ;;
            esac
        done
        ;;
esac

if [ "$DRY_RUN" -eq 1 ]; then
    echo "Would remove $resolved"
    exit 0
fi

if [ -z "$resolved" ]; then
    refuse "internal error: empty path"
fi
rm -rf -- "$resolved"
echo "Removed $resolved"
exit 0
