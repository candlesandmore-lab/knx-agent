"""Adapter tests: delegation to the SDK (mocked) and end-to-end through the real SDK."""

import asyncio
import importlib
import json
import logging

import pytest
from conftest import apply_change, fixture_cases, load_fixture, read_log_book
from graph_factory import graph_for_case, graphs_of
from surface_helpers import CLI_COMMANDS, SURFACES, install_graph, sdk_call
from typer.testing import CliRunner

from knx_agent.adapters import mcp as mcp_package
from knx_agent.adapters.mcp import server
from knx_agent.cli import app
from knx_agent.contracts import (
    DescribeSessionResponse,
    ErrorInfo,
    KnxAgentError,
    ProjectImportInfo,
    ProjectImportSummary,
    ProjectRefreshInfo,
    ResponseEnvelope,
)
from knx_agent.sdk import KnxSessionClient

# The package re-exports the MCPServer instance as `server`; the module is needed for startup state.
smod = importlib.import_module("knx_agent.adapters.mcp.server")

SENTINEL = DescribeSessionResponse(
    session_label="lbl",
    work_directory="/w/lbl",
    source_project_absolute_path="/p.knxproj",
    project_refresh=ProjectRefreshInfo(last_status="UNCHANGED"),
    project_import=ProjectImportInfo(
        imported_at="2026-01-01T00:00:00Z",
        project_import_summary=ProjectImportSummary(file_name="p.knxproj", archive_entry_count=1),
    ),
    active_setup="sentinel-setup",
    envelope=ResponseEnvelope(setup="sentinel-setup", limitation_notes=["sentinel"]),
)


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    def fake(self, session_label, log_level=None):
        recorded.append((self._service._root_arg, session_label, log_level))
        return SENTINEL

    monkeypatch.setattr(KnxSessionClient, "describe_session", fake)
    return recorded


@pytest.fixture
def mcp_startup(monkeypatch):
    monkeypatch.setitem(smod._startup, "session_root", None)
    monkeypatch.setitem(smod._startup, "log_level", "INFO")
    return smod._startup


# --- CLI delegation (mocked SDK) ------------------------------------------------------------------
def test_cli_delegates_unchanged(calls, valid_case, tmp_path):
    label = valid_case["session_label"]
    result = CliRunner().invoke(
        app, ["session", "describe", "--session", label, "--session-root", str(tmp_path), "--log-level", "DEBUG"]
    )
    assert result.exit_code == 0
    assert calls == [(tmp_path, label, "DEBUG")]
    assert json.loads(result.stdout) == SENTINEL.model_dump(mode="json")


def test_cli_maps_sdk_exception(monkeypatch, invalid_case):
    def boom(self, session_label, log_level=None):
        raise KnxAgentError(ErrorInfo(code=invalid_case["expected_error_code"], message="bad"))

    monkeypatch.setattr(KnxSessionClient, "describe_session", boom)
    result = CliRunner().invoke(app, ["session", "describe", "--session", invalid_case["session_label"]])
    assert result.exit_code == 1
    last = result.stderr.strip().splitlines()[-1]
    assert json.loads(last) == {"code": invalid_case["expected_error_code"], "message": "bad", "details": None}
    assert result.stdout == ""


# --- CLI end to end -------------------------------------------------------------------------------
def test_cli_create_describe_reimport_end_to_end(project, session_root):
    runner = CliRunner()
    root = ["--session-root", str(session_root)]
    created = runner.invoke(
        app, ["session", "create", "--project", str(project), "--session-label", "s1", *root]
    )
    assert created.exit_code == 0, created.stderr
    assert json.loads(created.stdout)["work_directory"] == str(session_root.resolve() / "s1")

    described = runner.invoke(app, ["session", "describe", "--session", "s1", *root])
    assert described.exit_code == 0
    assert json.loads(described.stdout)["project_refresh"]["last_status"] == "UNCHANGED"

    apply_change(project, "both")
    described = runner.invoke(app, ["session", "describe", "--session", "s1", *root])
    assert json.loads(described.stdout)["project_refresh"]["last_status"] == "CHANGED"

    reimported = runner.invoke(app, ["session", "reimport", "--session", "s1", "--log-level", "FULL", *root])
    assert reimported.exit_code == 0
    assert json.loads(reimported.stdout)["project_refresh_status"] == "UNCHANGED"
    # create INFO, automatic re-import INFO, then the explicit re-import at FULL: DEBUG "Import started" + INFO
    assert [e["level"] for e in read_log_book(session_root, "s1")] == ["INFO", "INFO", "DEBUG", "INFO"]


def test_cli_error_json_on_stderr_and_exit_code_1(make_project, session_root):
    result = CliRunner().invoke(
        app,
        ["session", "create", "--project", str(make_project("not_zip")), "--session-label", "s1",
         "--session-root", str(session_root)],
    )  # fmt: skip
    assert result.exit_code == 1
    assert result.stdout == ""
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error["code"] == "PROJECT_PARSE_ERROR"
    assert any("ERROR knx_agent" in line for line in result.stderr.splitlines())  # Python logging handler


def test_cli_returns_real_import_results(build, session_root):
    runner = CliRunner()
    root = ["--session-root", str(session_root)]
    project = build(edits=[{"path": "areas.0.lines.0.components.0.objects.0.links", "value": ["GA-999"]}])
    created = json.loads(
        runner.invoke(app, ["session", "create", "--project", str(project), "--session-label", "s1", *root]).stdout
    )
    summary = created["project_import_summary"]
    assert summary["node_counts"]["component"] == 3 and summary["warning_counts"] == {"GROUP_ADDRESS_LINK_UNRESOLVED": 1}
    assert created["envelope"]["limitation_notes"][0].startswith("[GROUP_ADDRESS_LINK_UNRESOLVED]")
    described = json.loads(runner.invoke(app, ["session", "describe", "--session", "s1", *root]).stdout)
    assert described["project_import"]["project_import_summary"] == summary
    assert len(described["project_import"]["fingerprint"]) == 64
    assert described["project_import"]["graph_file"].endswith("project-graph.json")
    reimported = json.loads(runner.invoke(app, ["session", "reimport", "--session", "s1", *root]).stdout)
    assert reimported["changes"] == [] and reimported["invalidated_references"] == []
    assert reimported["envelope"]["limitation_notes"] == created["envelope"]["limitation_notes"]


def test_cli_parse_error_prints_logging_line_then_error_json_with_reason(make_project, session_root):
    result = CliRunner().invoke(
        app,
        ["session", "create", "--project", str(make_project("encrypted")), "--session-label", "s1",
         "--session-root", str(session_root)],
    )  # fmt: skip
    assert result.exit_code == 1 and result.stdout == ""
    lines = result.stderr.strip().splitlines()
    assert "ERROR knx_agent" in lines[0] and "PROJECT_PARSE_ERROR" in lines[0]
    error = json.loads(lines[-1])
    assert error["code"] == "PROJECT_PARSE_ERROR" and error["details"]["reason"] == "ENCRYPTED"


def test_cli_invalid_log_level(project, session_root):
    result = CliRunner().invoke(
        app,
        ["session", "create", "--project", str(project), "--session-label", "s1",
         "--session-root", str(session_root), "--log-level", "LOUD"],
    )  # fmt: skip
    assert result.exit_code == 1
    assert json.loads(result.stderr.strip().splitlines()[-1])["code"] == "INVALID_LOG_LEVEL"


def test_cli_session_root_option_on_every_subcommand():
    for command in ("create", "describe", "reimport"):
        result = CliRunner().invoke(app, ["session", command, "--help"])
        assert "--session-root" in result.stdout


# --- MCP ---------------------------------------------------------------------------------------------
def test_mcp_tools_registered_under_capability_names():
    tools = asyncio.run(server.list_tools())
    assert sorted(t.name for t in tools) == [
        "create_session", "describe_component", "describe_session", "list_components",
        "reimport_system_definition", "summarize_topology", "trace_group_flow",
    ]  # fmt: skip


def test_mcp_delegates_unchanged(calls, mcp_startup, valid_case, tmp_path):
    mcp_startup["session_root"] = str(tmp_path)
    mcp_startup["log_level"] = "DEBUG"
    assert mcp_package.describe_session(valid_case["session_label"]) == SENTINEL
    assert calls == [(str(tmp_path), valid_case["session_label"], None)]


def test_mcp_maps_sdk_exception(monkeypatch, mcp_startup, invalid_case):
    code = invalid_case["expected_error_code"]

    def boom(self, session_label, log_level=None):
        raise KnxAgentError(ErrorInfo(code=code, message="bad"))

    monkeypatch.setattr(KnxSessionClient, "describe_session", boom)
    with pytest.raises(ValueError, match=f"{code}: bad"):
        mcp_package.describe_session(invalid_case["session_label"])


def test_mcp_tools_end_to_end_with_startup_arguments(mcp_startup, project, session_root):
    mcp_startup["session_root"] = str(session_root)
    mcp_startup["log_level"] = "DEBUG"
    created = mcp_package.create_session(project_path=str(project), session_label="s1")
    assert created.work_directory == str(session_root.resolve() / "s1")
    mcp_package.describe_session("s1")
    assert mcp_package.reimport_system_definition("s1").project_refresh_status == "UNCHANGED"
    assert [e["level"] for e in read_log_book(session_root, "s1")] == ["DEBUG", "INFO", "DEBUG", "DEBUG", "INFO"]
    with pytest.raises(ValueError, match="SESSION_NOT_FOUND"):
        mcp_package.describe_session("ghost")


def test_mcp_tools_return_real_import_results(mcp_startup, build, session_root):
    mcp_startup["session_root"] = str(session_root)
    project = build(edits=[{"path": "areas.0.lines.0.components.0.objects.0.links", "value": ["GA-999"]}])
    created = mcp_package.create_session(project_path=str(project), session_label="s1")
    assert created.project_import_summary.node_counts["communication_object"] == 6
    assert created.project_import_summary.warning_total == 1
    assert created.envelope.limitation_notes[0].startswith("[GROUP_ADDRESS_LINK_UNRESOLVED]")
    described = mcp_package.describe_session("s1")
    assert described.project_import.project_import_summary == created.project_import_summary
    reimported = mcp_package.reimport_system_definition("s1")
    assert reimported.project_refresh_status == "UNCHANGED" and reimported.changes == []


def test_mcp_parse_error_maps_code_and_message(mcp_startup, make_project, session_root):
    mcp_startup["session_root"] = str(session_root)
    with pytest.raises(ValueError, match="PROJECT_PARSE_ERROR"):
        mcp_package.create_session(project_path=str(make_project("not_zip")), session_label="s1")


def test_mcp_startup_arguments_parsed():
    args = smod.parse_startup_arguments(["--session-root", "/x", "--log-level", "debug"])
    assert (args.session_root, args.log_level) == ("/x", "DEBUG")
    defaults = smod.parse_startup_arguments([])
    assert (defaults.session_root, defaults.log_level) == (None, "INFO")
    with pytest.raises(SystemExit):
        smod.parse_startup_arguments(["--log-level", "LOUD"])


def test_mcp_entry_point_configures_stderr_logging_and_runs(monkeypatch, mcp_startup, capsys):
    ran = []
    monkeypatch.setattr(server, "run", lambda *a, **k: ran.append(True))
    smod.mcp(["--session-root", "/some/root", "--log-level", "FULL"])
    assert ran == [True]
    assert mcp_startup == {"session_root": "/some/root", "log_level": "FULL"}
    logging.getLogger("knx_agent.test").error("boom")
    captured = capsys.readouterr()
    assert captured.out == ""  # MCP stdio owns stdout
    assert "ERROR knx_agent.test: boom" in captured.err


def test_console_scripts_registered():
    from importlib.metadata import entry_points

    scripts = {e.name: e.value for e in entry_points(group="console_scripts")}
    if "knx-agent-mcp" not in scripts:
        pytest.skip("package metadata not refreshed; run uv sync")
    assert scripts["knx-agent-mcp"] == "knx_agent.adapters.mcp:mcp"


# =====================================================================================================
# Story 05: component inspection capabilities on CLI (setup group) and MCP
# =====================================================================================================
SURFACE_CASES = load_fixture("surface_cases.yaml")
CAPABILITIES = list(CLI_COMMANDS)
RECORD_ARGS = {
    "list_components": dict(component_selector="q", selector_kind="NAME", detail_level="full", mutation_name="m"),
    "describe_component": dict(component_selector="c", selector_kind="ets_id", detail_level="summary", mutation_name="m"),
    "summarize_topology": dict(detail_level="FULL", mutation_name="m"),
    "trace_group_flow": dict(group_address_selector="5/0/12", communication_object_ref="a/co/b", detail_level="x", mutation_name="m"),
}


@pytest.fixture
def recorded_queries(monkeypatch):
    """Replace the four query methods of the SDK client with recorders (arguments only)."""
    calls = []

    def make(name):
        def fake(self, session_label, *args, **kwargs):
            parameters = SURFACE_CASES["sdk_parameters"][name]
            names = [p for p in parameters if p != "session_label"]
            bound = dict(zip(names, args, strict=False)) | kwargs
            calls.append((name, self._service._root_arg, session_label, bound))
            return SENTINEL

        return fake

    for name in CAPABILITIES:
        monkeypatch.setattr(KnxSessionClient, name, make(name))
    return calls


def test_sdk_signatures_match_the_projection_table():
    import inspect

    for name, expected in SURFACE_CASES["sdk_parameters"].items():
        assert list(inspect.signature(getattr(KnxSessionClient, name)).parameters)[1:] == expected


def test_cli_setup_options_match_the_projection_table():
    for command, options in SURFACE_CASES["cli_options"].items():
        helptext = CliRunner().invoke(app, ["setup", command, "--help"]).stdout
        for option in options:
            assert option in helptext, (command, option)
    assert "setup" in CliRunner().invoke(app, ["--help"]).stdout


def test_cli_delegates_query_arguments_unchanged(recorded_queries, tmp_path):
    runner = CliRunner()
    common = ["--session", "lbl", "--session-root", str(tmp_path), "--log-level", "DEBUG"]
    assert runner.invoke(app, ["setup", "list-components", *common, "--query", "q", "--selector-kind", "NAME",
                               "--detail-level", "full", "--mutation", "m"]).exit_code == 0  # fmt: skip
    assert runner.invoke(app, ["setup", "describe-component", *common, "--component", "c", "--selector-kind", "ets_id",
                               "--detail-level", "summary", "--mutation", "m"]).exit_code == 0  # fmt: skip
    assert runner.invoke(app, ["setup", "summarize-topology", *common, "--detail-level", "FULL", "--mutation", "m"]).exit_code == 0
    assert runner.invoke(app, ["setup", "trace-group-flow", *common, "--group-address", "5/0/12", "--object-ref", "a/co/b",
                               "--detail-level", "x", "--mutation", "m"]).exit_code == 0  # fmt: skip
    expected = [
        ("list_components", tmp_path, "lbl", {**RECORD_ARGS["list_components"], "log_level": "DEBUG"}),
        ("describe_component", tmp_path, "lbl", {**RECORD_ARGS["describe_component"], "log_level": "DEBUG"}),
        ("summarize_topology", tmp_path, "lbl", {**RECORD_ARGS["summarize_topology"], "log_level": "DEBUG"}),
        ("trace_group_flow", tmp_path, "lbl", {**RECORD_ARGS["trace_group_flow"], "log_level": "DEBUG"}),
    ]
    assert recorded_queries == expected


def test_cli_omitted_options_are_none(recorded_queries, tmp_path):
    CliRunner().invoke(app, ["setup", "list-components", "--session", "lbl", "--session-root", str(tmp_path)])
    assert recorded_queries == [
        ("list_components", tmp_path, "lbl",
         {"component_selector": None, "selector_kind": None, "detail_level": None, "mutation_name": None, "log_level": "INFO"}),
    ]  # fmt: skip


def test_mcp_tool_arguments_match_the_projection_table():
    tools = {t.name: t for t in asyncio.run(server.list_tools())}
    for name, arguments in SURFACE_CASES["mcp_arguments"].items():
        schema = tools[name].input_schema
        assert list(schema["properties"]) == arguments
        assert schema.get("required", []) == SURFACE_CASES["mcp_required"][name]
        assert "log_level" not in schema["properties"]  # startup argument (C6)
        for argument in arguments:
            if argument != "session_label":
                text = json.dumps(schema["properties"][argument])
                assert '"string"' in text and "enum" not in text  # plain strings, validated by the core


def test_mcp_delegates_query_arguments_unchanged(recorded_queries, mcp_startup, tmp_path):
    mcp_startup["session_root"] = str(tmp_path)
    mcp_startup["log_level"] = "DEBUG"
    for name in CAPABILITIES:
        getattr(mcp_package, name)("lbl", **RECORD_ARGS[name])
    assert recorded_queries == [(name, str(tmp_path), "lbl", RECORD_ARGS[name]) for name in CAPABILITIES]


def test_mcp_maps_query_error_with_code_and_details(mcp_startup, project, session_root):
    mcp_startup["session_root"] = str(session_root)
    mcp_package.create_session(project_path=str(project), session_label="s1")
    with pytest.raises(ValueError, match="SELECTOR_UNRESOLVED: ") as excinfo:
        mcp_package.describe_component("s1", "Nope")
    info = json.loads(str(excinfo.value).splitlines()[-1])
    assert info["code"] == "SELECTOR_UNRESOLVED" and info["details"]["selector"] == "Nope"


# --- CLI end to end (typer CliRunner) ----------------------------------------------------------------
@pytest.fixture
def s1(project, session_root):
    KnxSessionClient(session_root=session_root).create_session(project_path=project, session_label="s1")
    return "s1"


def test_cli_setup_commands_end_to_end(s1, session_root):
    runner = CliRunner()
    root = ["--session", s1, "--session-root", str(session_root)]
    listed = json.loads(runner.invoke(app, ["setup", "list-components", *root, "--query", "1.1.2"]).stdout)
    assert listed["match_count"] == 1 and listed["matches"][0]["match_kinds"] == ["INDIVIDUAL_ADDRESS"]
    located = json.loads(runner.invoke(app, ["setup", "list-components", *root, "--query", "Hall/", "--detail-level", "SUMMARY"]).stdout)
    assert [m["identity"]["name"] for m in located["matches"]] == ["Sensor", "Controller"]
    described = json.loads(runner.invoke(app, ["setup", "describe-component", *root, "--component", "P-0001-0_DI-1", "--detail-level", "FULL"]).stdout)
    assert described["components"][0]["communication_objects"][0]["ets_id"] == "P-0001-0_DI-1/co/O-0_R-1"
    topology = json.loads(runner.invoke(app, ["setup", "summarize-topology", *root, "--detail-level", "MEDIUM"]).stdout)
    assert topology["component_counts"]["unplaced"] == 1
    flow = json.loads(runner.invoke(app, ["setup", "trace-group-flow", *root, "--group-address", "0/0/1"]).stdout)
    assert flow["group_addresses"][0]["participants"][0]["direction"] == "SENDER"
    by_object = json.loads(runner.invoke(app, ["setup", "trace-group-flow", *root, "--object-ref", "P-0001-0_DI-2/co/O-2_R-3"]).stdout)
    assert by_object["match_count"] == 2


def test_cli_selector_unresolved_prints_error_json_and_exits_1(s1, session_root):
    result = CliRunner().invoke(
        app, ["setup", "describe-component", "--session", s1, "--session-root", str(session_root), "--component", "Nope"]
    )
    assert result.exit_code == 1 and result.stdout == ""
    lines = result.stderr.strip().splitlines()
    assert "ERROR knx_agent" in lines[0] and "SELECTOR_UNRESOLVED" in lines[0]
    error = json.loads(lines[-1])
    assert error["code"] == "SELECTOR_UNRESOLVED" and error["details"]["selector"] == "Nope"


def test_cli_invalid_detail_level_is_a_core_error_not_a_usage_error(s1, session_root):
    result = CliRunner().invoke(
        app, ["setup", "summarize-topology", "--session", s1, "--session-root", str(session_root), "--detail-level", "HUGE"]
    )
    assert result.exit_code == 1
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error["code"] == "INVALID_DETAIL_LEVEL" and error["details"]["allowed"] == ["SUMMARY", "MEDIUM", "FULL"]


def test_cli_trace_group_flow_exactly_one_rule_is_enforced_by_the_core(s1, session_root):
    for extra, reason in (([], "SELECTOR_MISSING"), (["--group-address", "0/0/1", "--object-ref", "a/co/b"], "SELECTOR_CONFLICT")):
        result = CliRunner().invoke(app, ["setup", "trace-group-flow", "--session", s1, "--session-root", str(session_root), *extra])
        assert result.exit_code == 1
        error = json.loads(result.stderr.strip().splitlines()[-1])
        assert error["code"] == "INVALID_REQUEST" and error["details"]["reason"] == reason


def test_cli_describe_component_requires_the_component_option(s1, session_root):
    result = CliRunner().invoke(app, ["setup", "describe-component", "--session", s1, "--session-root", str(session_root)])
    assert result.exit_code == 2  # typer usage error; the core rule SELECTOR_MISSING is reachable via SDK and MCP


def test_cli_setup_help_lists_the_four_commands():
    result = CliRunner().invoke(app, ["setup", "--help"])
    for command in CLI_COMMANDS.values():
        assert command in result.stdout


# --- MCP end to end (real tool calls) ---------------------------------------------------------------------
def test_mcp_tool_calls_return_structured_content_per_level(mcp_startup, s1, session_root):
    mcp_startup["session_root"] = str(session_root)
    for level, keys in (("SUMMARY", {"identity", "derived"}), ("MEDIUM", {"identity", "derived", "topology", "component_parameters"})):
        result = asyncio.run(server.call_tool("list_components", {"session_label": s1, "detail_level": level}))
        assert not result.is_error
        assert {key for match in result.structured_content["matches"] for key in match} == keys
    result = asyncio.run(server.call_tool("describe_component", {"session_label": s1, "component_selector": "Sensor", "detail_level": "FULL"}))
    assert "communication_objects" in result.structured_content["components"][0]
    result = asyncio.run(server.call_tool("trace_group_flow", {"session_label": s1, "group_address_selector": "0/0/1"}))
    assert result.structured_content["group_addresses"][0]["current_value"] == "unknown"
    result = asyncio.run(server.call_tool("summarize_topology", {"session_label": s1}))
    assert result.structured_content["component_counts"]["total"] == 3


# --- parity SDK / CLI / MCP ---------------------------------------------------------------------------------
def _subset(actual, expected):
    from json_subset import assert_subset

    assert_subset(actual, expected)


@pytest.mark.parametrize("case", fixture_cases("surface_cases.yaml", "success_cases"))
def test_identical_json_on_sdk_cli_and_mcp(case, s1, session_root, mcp_startup):
    outcomes = {name: caller(session_root, case["capability"], s1, case["args"]) for name, caller in SURFACES.items()}
    assert all(kind == "ok" for kind, _ in outcomes.values()), outcomes
    sdk = outcomes["sdk"][1]
    assert outcomes["cli"][1] == sdk and outcomes["mcp"][1] == sdk
    _subset(sdk, case["expect"])


@pytest.mark.parametrize("case", fixture_cases("surface_cases.yaml", "error_cases"))
def test_identical_error_code_and_reason_on_sdk_cli_and_mcp(case, s1, session_root, mcp_startup):
    outcomes = {name: caller(session_root, case["capability"], s1, case["args"]) for name, caller in SURFACES.items()}
    assert all(kind == "error" for kind, _ in outcomes.values()), outcomes
    sdk = outcomes["sdk"][1]
    assert sdk["code"] == case["code"]
    assert (sdk["details"] or {}).get("reason") == case.get("reason")
    assert outcomes["cli"][1] == sdk and outcomes["mcp"][1] == sdk  # the full ErrorInfo is identical


@pytest.mark.parametrize("case", SURFACE_CASES["session_not_found"], ids=lambda c: c["capability"])
def test_session_not_found_on_all_surfaces(case, session_root, mcp_startup):
    outcomes = {name: caller(session_root, case["capability"], "ghost", case["args"]) for name, caller in SURFACES.items()}
    assert all(o[0] == "error" and o[1]["code"] == "SESSION_NOT_FOUND" for o in outcomes.values())
    assert outcomes["cli"][1] == outcomes["sdk"][1] == outcomes["mcp"][1]


def test_describe_component_without_selector_sdk_and_mcp_schema(s1, session_root):
    case = SURFACE_CASES["cli_unsupported"][0]
    kind, error = sdk_call(session_root, case["capability"], s1, {"component_selector": None})
    assert kind == "error" and error["code"] == case["code"] and error["details"]["reason"] == case["reason"]
    tools = {t.name: t for t in asyncio.run(server.list_tools())}
    assert "component_selector" in tools["describe_component"].input_schema["required"]


def _overlap_cases():
    cases = load_fixture("selector_overlap_cases.yaml")["cases"]
    return [pytest.param(case, id=case["id"]) for case in cases]


@pytest.mark.parametrize("case", _overlap_cases())
def test_any_overlap_cases_are_identical_on_all_surfaces(case, s1, session_root, mcp_startup):
    graph = graph_for_case(graphs_of("selector_overlap_cases.yaml"), case)
    install_graph(session_root, s1, graph)
    args = {"component_selector": case["selector"], "detail_level": "SUMMARY"}
    if "kind" in case:
        args["selector_kind"] = case["kind"]
    outcomes = {name: caller(session_root, "list_components", s1, args) for name, caller in SURFACES.items()}
    assert all(kind == "ok" for kind, _ in outcomes.values()), outcomes
    sdk = outcomes["sdk"][1]
    assert outcomes["cli"][1] == sdk and outcomes["mcp"][1] == sdk
    assert [(m["identity"]["ets_id"], m["match_kinds"]) for m in sdk["matches"]] == [
        (item["id"], item["kinds"]) for item in case["expect"]
    ]
    assert sdk["match_count"] == len(case["expect"])
    assert sdk["ambiguous"] is (len(case["expect"]) > 1)
