"""Guard of the demo scripts in ./demo (story 06): runs every script against the committed ETS 6 sample.

The script-running tests skip (with the reason in the report) when the sample file, bash or uv is absent. The static
checks (README, actions, family name, environment variables, demo rule in the todos, cleanup.sh) need no sample.
Expectations are data-driven from tests/fixtures/demo_script_expectations.yaml; key fields only, no byte-exact snapshots.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import fixture_cases, load_fixture

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "demo"
SAMPLE = REPO / "tests" / "lifedata" / "20261010-EFH-Armbruster.knxproj"
EXPECT = load_fixture("demo_script_expectations.yaml")
RESULT_LINE = re.compile(r"^RESULT (\S+) exit=(\d+)(.*)$", re.MULTILINE)
TIMEOUT = 300

_missing = (
    f"sample project {SAMPLE.name} is absent; demo script tests are skipped"
    if not SAMPLE.exists()
    else "bash or uv is not installed; demo script tests are skipped"
    if not (shutil.which("bash") and shutil.which("uv"))
    else None
)
needs_sample = pytest.mark.skipif(_missing is not None, reason=_missing or "")


def run_bash(script: Path, *args: str, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script), *args], cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, env=env, check=False
    )


def parse_results(stdout: str) -> dict[str, tuple[int, dict[str, str]]]:
    results: dict[str, tuple[int, dict[str, str]]] = {}
    for call_id, code, rest in RESULT_LINE.findall(stdout):
        fields = dict(part.split("=", 1) for part in rest.split() if "=" in part)
        results[call_id] = (int(code), fields)
    return results


def non_comment_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")]


# ----- scripts against the sample -------------------------------------------------------------------------------------


class Tour:
    """One shared session root for the scripts 01..07; each script is run once and its result remembered."""

    def __init__(self, root: Path, cwd: Path) -> None:
        self.root = root
        self.cwd = cwd
        self.completed: dict[str, subprocess.CompletedProcess] = {}

    def run(self, script: str) -> subprocess.CompletedProcess:
        if script not in self.completed:
            self.completed[script] = run_bash(DEMO / script, str(self.root), cwd=self.cwd)
        return self.completed[script]


@pytest.fixture(scope="module")
def tour(tmp_path_factory) -> Tour:
    base = tmp_path_factory.mktemp("demo")
    other_cwd = tmp_path_factory.mktemp("elsewhere")  # proves the scripts do not depend on the current directory
    return Tour(base / "sessions", other_cwd)  # absolute, not created: 01 creates it


def check_value(spec, actual: str | None, where: str) -> None:
    assert actual is not None, f"{where}: field missing"
    if isinstance(spec, dict):
        assert int(actual) >= int(spec["min"]), f"{where}: {actual} < min {spec['min']}"
    else:
        assert actual == str(spec), f"{where}: {actual!r} != {spec!r}"


@needs_sample
@pytest.mark.parametrize(
    "entry", [pytest.param(entry, id=entry["script"]) for entry in EXPECT["scripts"]]
)
def test_script(entry, tour):
    if entry["script"] != "01-create-session.sh":
        tour.run("01-create-session.sh")  # idempotent: the session may already exist
    done = tour.run(entry["script"])
    assert done.returncode == entry["exit_code"], f"{entry['script']}\n{done.stdout[-3000:]}\n{done.stderr[-2000:]}"
    assert "FAILED:" not in done.stdout
    results = parse_results(done.stdout)
    for expected in entry["results"]:
        where = f"{entry['script']}:{expected['id']}"
        assert expected["id"] in results, f"{where}: no RESULT line\n{done.stdout[-3000:]}"
        code, fields = results[expected["id"]]
        assert code == expected["exit"], f"{where}: exit {code}"
        if "error_code" in expected:
            assert fields.get("error_code") == expected["error_code"], f"{where}: {fields}"
        for name, spec in (expected.get("fields") or {}).items():
            check_value(spec, fields.get(name), f"{where}.{name}")


@needs_sample
def test_run_all(tmp_path_factory):
    root = tmp_path_factory.mktemp("demo-all") / "sessions"
    done = run_bash(DEMO / "run-all.sh", str(root), cwd=tmp_path_factory.mktemp("elsewhere-all"))
    assert done.returncode == EXPECT["run_all"]["exit_code"], f"{done.stdout[-3000:]}\n{done.stderr[-2000:]}"
    assert EXPECT["run_all"]["summary_line"] in done.stdout
    results = parse_results(done.stdout)
    for entry in EXPECT["scripts"]:
        assert (DEMO / entry["script"]).name in done.stdout
        for expected in entry["results"]:
            assert expected["id"] in results, f"run-all: no RESULT line for {expected['id']}"
    assert (root / "demo-house" / "session-state.yaml").exists()  # the tour leaves the session for the user


# ----- static checks ---------------------------------------------------------------------------------------------------


def test_session_root_default_is_git_ignored():
    if not shutil.which("git"):
        pytest.skip("git is not installed")
    done = subprocess.run(["git", "check-ignore", "-q", "demo/.sessions"], cwd=REPO, check=False)
    assert done.returncode == 0, "demo/.sessions must be git-ignored"


def test_expected_scripts_exist_and_are_executable():
    names = {entry["script"] for entry in EXPECT["scripts"]} | {"lib.sh", "run-all.sh", "cleanup.sh"}
    for name in names:
        path = DEMO / name
        assert path.is_file(), name
        assert os.access(path, os.X_OK), f"{name} must be executable"


def test_readme_mentions_every_script():
    readme = (DEMO / "README.md").read_text(encoding="utf-8")
    scripts = sorted(path.name for path in DEMO.glob("*.sh"))
    assert scripts, "no demo scripts found"
    missing = [name for name in scripts if name not in readme]
    assert not missing, f"demo/README.md does not mention: {missing}"
    for action in EXPECT["actions"]:
        assert f"knx-agent {action}" in readme, f"demo/README.md shows no command for: {action}"


def test_all_seven_actions_appear():
    text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(DEMO.glob("*.sh")))
    assert len(EXPECT["actions"]) == 7
    for action in EXPECT["actions"]:
        assert action in text, f"no demo script uses: {action}"
    for level in EXPECT["detail_levels_used"]:
        assert f"--detail-level {level}" in text, level


def test_no_family_name():
    family = EXPECT["family_name"].casefold()
    sample_name = EXPECT["sample_file_name"]
    checked = 0
    for path in sorted(DEMO.rglob("*")):
        if not path.is_file() or ".sessions" in path.relative_to(DEMO).parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").replace(sample_name, "").casefold()
        assert family not in text, f"{path.relative_to(REPO)} contains the family name"
        checked += 1
    assert checked >= 11


def test_no_environment_variables_and_no_set_e():
    for path in sorted(DEMO.glob("*.sh")):
        for line in non_comment_lines(path):
            assert "export " not in line and "printenv" not in line, f"{path.name}: {line}"
            assert "$HOME" not in line and "${HOME" not in line, f"{path.name}: {line}"
            stripped = line.strip()
            if stripped.startswith("set -"):
                flags = stripped.split()[1]
                assert "e" not in flags, f"{path.name}: set -e is not allowed ({stripped})"


def test_todo_demo_rule():
    rule = EXPECT["demo_rule_line"]
    todos = REPO / "development" / "todos"
    for number in EXPECT["todos_with_demo_rule"]:
        files = sorted(todos.glob(f"{number}-*.md"))
        assert len(files) == 1, number
        assert files[0].read_text(encoding="utf-8").rstrip().endswith(rule), files[0].name
    for number in EXPECT["todos_without_demo_rule"]:
        for path in todos.glob(f"{number}-*.md"):
            assert "Demo rule (todo 16)" not in path.read_text(encoding="utf-8"), path.name


# ----- cleanup.sh ------------------------------------------------------------------------------------------------------


def make_session_root(path: Path, sessions: tuple[str, ...] = ("demo-house",)) -> Path:
    for label in sessions:
        (path / label).mkdir(parents=True)
        (path / label / "session-state.yaml").write_text("session_label: x\n", encoding="utf-8")
    return path


def cleanup(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return run_bash(DEMO / "cleanup.sh", *args, cwd=REPO.parent, env=env)


def build_target(kind: str, tmp: Path) -> tuple[str, dict | None, list[Path]]:
    """The cleanup.sh argument, the subprocess environment (None = unchanged) and the paths that must survive."""
    env = None
    survivors: list[Path] = []
    if kind == "empty_string":
        arg = ""
    elif kind == "whitespace_string":
        arg = "   "
    elif kind == "filesystem_root":
        arg = "/"
    elif kind == "repository_root":
        arg = str(REPO)
    elif kind == "repository_parent":
        arg = str(REPO.parent)
    elif kind == "demo_folder":
        arg = str(DEMO)
    elif kind == "throwaway_home":
        home = tmp / "home"
        home.mkdir()
        env = dict(os.environ, HOME=str(home))  # only the subprocess sees it
        arg = str(home)
        survivors = [home]
    elif kind == "missing_explicit_path":
        arg = str(tmp / "no-such-folder")
    elif kind == "regular_file":
        target = tmp / "a-file.sessions"
        target.write_text("x", encoding="utf-8")
        arg, survivors = str(target), [target]
    elif kind == "symlink_to_sessions_dir":
        real = make_session_root(tmp / "real.sessions")
        link = tmp / "link.sessions"
        link.symlink_to(real, target_is_directory=True)
        arg, survivors = str(link), [real, real / "demo-house" / "session-state.yaml", link]
    elif kind == "plain_directory_with_file":
        target = tmp / "important"
        target.mkdir()
        (target / "notes.txt").write_text("keep me", encoding="utf-8")
        arg, survivors = str(target), [target, target / "notes.txt"]
    elif kind == "foreign_subfolder_directory":
        target = tmp / "foreign"
        (target / "photos").mkdir(parents=True)
        arg, survivors = str(target), [target, target / "photos"]
    else:
        raise ValueError(kind)
    return arg, env, survivors


@pytest.mark.parametrize("case", fixture_cases("demo_script_expectations.yaml", "cleanup_refusals"))
def test_cleanup_refuses(case, tmp_path):
    arg, env, survivors = build_target(case["target"], tmp_path)
    args = [arg, "--dry-run"] if case["dry_run"] else [arg]
    done = cleanup(*args, env=env)
    assert done.returncode == 2, f"{case['id']}: {done.stdout} {done.stderr}"
    assert "refused" in done.stderr
    assert case["message"] in done.stderr, done.stderr
    assert done.stdout == ""
    for path in survivors:
        assert path.exists() or path.is_symlink(), f"{case['id']}: {path} was removed"
    assert REPO.exists() and DEMO.exists() and (DEMO / "lib.sh").exists()


def test_cleanup_removes_session_root(tmp_path):
    root = make_session_root(tmp_path / "x.sessions", ("demo-house", "other"))
    (root / ".demo.creating-ab12").mkdir()
    done = cleanup(str(root))
    assert done.returncode == 0, done.stderr
    assert "Removed" in done.stdout
    assert not root.exists()


def test_cleanup_dry_run_keeps_session_root(tmp_path):
    root = make_session_root(tmp_path / "x.sessions")
    done = cleanup(str(root), "--dry-run")
    assert done.returncode == 0, done.stderr
    assert "Would remove" in done.stdout
    assert (root / "demo-house" / "session-state.yaml").exists()


def test_cleanup_removes_plain_named_session_root(tmp_path):
    root = make_session_root(tmp_path / "sessions", ("a", "b"))
    done = cleanup(str(root) + "/")  # trailing slash is accepted
    assert done.returncode == 0, done.stderr
    assert not root.exists()


def test_cleanup_removes_empty_explicit_directory(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    done = cleanup(str(root))
    assert done.returncode == 0, done.stderr
    assert not root.exists()
