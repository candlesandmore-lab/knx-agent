"""Golden-structure tests of the query capabilities on the committed ETS 6 sample (story 05, T8).

Every test skips when the sample file is absent. Only counts, ids and structure are asserted; names used in
selectors are taken at run time from the imported graph (nothing from the sample is copied into the repository).
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

import pytest
from conftest import load_fixture, state_bytes
from typer.testing import CliRunner

from knx_agent.application.graph_store import read_graph
from knx_agent.cli import app
from knx_agent.contracts import DetailLevel
from knx_agent.domain.graph_index import GraphIndex
from knx_agent.domain.group_flow import trace
from knx_agent.sdk import KnxSessionClient

SAMPLE = Path(__file__).parent / "lifedata" / "20261010-EFH-Armbruster.knxproj"
EXPECT = load_fixture("sample_query_expectations.yaml")
IMPORT_COUNTS = load_fixture("sample_project_counts.yaml")
LEVELS = ["SUMMARY", "MEDIUM", "FULL"]
DIRECTIONS = {"SENDER", "RECEIVER", "SENDER_RECEIVER", "UNDETERMINED"}

pytestmark = pytest.mark.skipif(
    not SAMPLE.exists(), reason=f"sample project {SAMPLE.name} is absent; sample-based tests are skipped"
)

TIMINGS: dict[str, float] = {}


def timed(label: str, call):
    started = time.perf_counter()
    result = call()
    elapsed = time.perf_counter() - started
    TIMINGS[label] = elapsed
    assert elapsed < EXPECT["timing_bound_s"], f"{label} took {elapsed:.1f} s"
    return result


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    root = tmp_path_factory.mktemp("sample_sessions")
    client = KnxSessionClient(session_root=root)
    client.create_session(project_path=SAMPLE, session_label="sample")
    return client, root


@pytest.fixture(scope="module")
def client(env):
    return env[0]


@pytest.fixture(scope="module")
def components(client):
    """SUMMARY listing of every component, as JSON dicts."""
    response = timed("list_components SUMMARY (all)", lambda: client.list_components("sample", detail_level="SUMMARY"))
    return [json.loads(match.model_dump_json()) for match in response.matches]


@pytest.fixture(scope="module")
def index(env):
    graph = read_graph(env[1] / "sample").graph
    assert graph is not None
    return GraphIndex.build(graph)


def test_sample_fixtures_agree_with_the_story_04_counts():
    assert EXPECT["sample_file"] == IMPORT_COUNTS["sample_file"]
    assert EXPECT["components"]["total"] == IMPORT_COUNTS["node_counts"]["component"]
    assert EXPECT["topology"]["locations"] == IMPORT_COUNTS["node_counts"]["space"]
    assert EXPECT["totals"]["parameters"] == IMPORT_COUNTS["node_counts"]["parameter"]
    assert EXPECT["totals"]["communication_objects"] == IMPORT_COUNTS["node_counts"]["communication_object"]
    assert EXPECT["totals"]["group_addresses"] == IMPORT_COUNTS["node_counts"]["group_address"]
    assert EXPECT["totals"]["memberships"] == IMPORT_COUNTS["relation_counts"]["membership"]
    assert EXPECT["components"]["component_type_counts"] == IMPORT_COUNTS["component_type_counts"]


def test_list_components_summary_counts_and_types(client, components):
    expected = EXPECT["components"]
    assert len(components) == expected["total"]
    assert sum(1 for c in components if c["identity"]["instance_path"] is not None) == expected["placed"]
    assert sum(1 for c in components if c["identity"]["instance_path"] is None) == expected["unplaced"]
    distribution = Counter(c["derived"]["component_type"] for c in components)
    assert dict(sorted(distribution.items())) == expected["component_type_counts"]
    assert all(set(c) == {"identity", "derived"} for c in components)  # SUMMARY, no selector: no match_kinds
    notes = client.list_components("sample", detail_level="SUMMARY").envelope.limitation_notes
    assert any("2 returned components are not placed" in note for note in notes)


def test_every_component_is_found_exactly_by_individual_address_and_by_ets_id(client, components):
    assert EXPECT["example_component_id"] in {c["identity"]["ets_id"] for c in components}
    for component in components:
        identity = component["identity"]
        for selector, kind in ((identity["individual_address"], "INDIVIDUAL_ADDRESS"), (identity["ets_id"], "ETS_ID")):
            response = client.list_components("sample", selector, detail_level="SUMMARY")
            assert [m.identity.ets_id for m in response.matches] == [identity["ets_id"]], (kind, selector)
            assert kind in response.matches[0].match_kinds
            explicit = client.list_components("sample", selector, selector_kind=kind, detail_level="SUMMARY")
            assert [m.match_kinds for m in explicit.matches] == [[kind]]
            assert [m.identity.ets_id for m in explicit.matches] == [identity["ets_id"]]


def test_instance_path_round_trip(client, components):
    placed = [c["identity"] for c in components if c["identity"]["instance_path"] is not None]
    by_path = Counter(i["instance_path"] for i in placed)
    for identity in placed:
        path = identity["instance_path"]
        response = client.list_components("sample", path, selector_kind="INSTANCE_PATH", detail_level="SUMMARY")
        found = [m.identity for m in response.matches]
        assert identity["ets_id"] in {i.ets_id for i in found}
        exact = [i for i in found if i.instance_path == path]
        assert len(exact) == by_path[path]  # only components with that exact path carry it
        assert all(i.instance_path is not None for i in found)  # unplaced components are never matched by path


def test_trailing_slash_location_queries(client, env):
    topology = client.summarize_topology("sample", detail_level="FULL").topology_summary
    assert max(location.depth for location in topology.locations) == EXPECT["topology"]["max_location_depth"]
    assert len(topology.locations) == EXPECT["topology"]["locations"]
    checked = 0
    for location in topology.locations:
        direct = {c.ets_id for c in location.components}
        for query in (location.path + "/", "/" + location.path + "/"):
            response = client.list_components("sample", query, selector_kind="INSTANCE_PATH", detail_level="SUMMARY")
            returned = {m.identity.ets_id for m in response.matches}
            assert direct <= returned, query
            segments = [s.casefold() for s in location.path.split("/")]
            for match in response.matches:
                path_segments = match.identity.instance_path.split("/")[:-1]
                assert len(path_segments) >= len(segments)
                if query.startswith("/"):
                    assert all(q in s.casefold() for q, s in zip(segments, path_segments, strict=False))
        checked += 1
    assert checked == EXPECT["topology"]["locations"]


def test_levels_are_distinct_and_nested_on_every_component(client):
    views = {level: client.list_components("sample", detail_level=level).matches for level in LEVELS}
    assert [len(v) for v in views.values()] == [EXPECT["components"]["total"]] * 3
    for summary, medium, full in zip(views["SUMMARY"], views["MEDIUM"], views["FULL"], strict=True):
        s, m, f = (json.loads(v.model_dump_json()) for v in (summary, medium, full))
        assert set(s) < set(m) < set(f)
        assert s["identity"] == m["identity"] == f["identity"]
        assert set(s["derived"]) < set(f["derived"]) and m["derived"] == s["derived"]
        assert m["component_parameters"] == [
            {k: v for k, v in p.items() if k != "parameter_type_id"} for p in f["component_parameters"]
        ]
        assert m["topology"] == f["topology"]
    medium_parameters = sum(len(v.component_parameters) for v in views["MEDIUM"])
    assert medium_parameters == EXPECT["totals"]["parameters"]
    assert sum(len(v.communication_objects) for v in views["FULL"]) == EXPECT["totals"]["communication_objects"]
    programs = {v.application.application_program_id for v in views["FULL"]} - {None}
    assert len(programs) == EXPECT["totals"]["distinct_application_program_ids"]
    assert all(v.topology.line is not None and v.topology.area is not None for v in views["MEDIUM"])
    assert sum(1 for v in views["MEDIUM"] if v.topology.location_path) == EXPECT["components"]["placed"]


def test_describe_component_by_run_time_names(client, components):
    named = [c["identity"] for c in components if c["identity"]["name"] and c["identity"]["instance_path"]]
    first = named[0]
    needle = first["name"][:3].upper()
    expected = {c["identity"]["ets_id"] for c in components if c["identity"]["name"] and needle.casefold() in c["identity"]["name"].casefold()}
    response = client.describe_component("sample", needle, detail_level="SUMMARY")
    assert {m.identity.ets_id for m in response.components} == expected
    assert response.ambiguous is (len(expected) > 1)
    assert first["ets_id"] in expected and all("NAME" in m.match_kinds for m in response.components)


def test_summarize_topology_counts_and_consistency(client):
    expected = EXPECT["topology"]
    counts = EXPECT["components"]
    summary = timed("summarize_topology SUMMARY", lambda: client.summarize_topology("sample", detail_level="SUMMARY"))
    assert summary.topology_summary.counts.model_dump() == {"areas": expected["areas"], "lines": expected["lines"], "locations": expected["locations"]}
    assert summary.component_counts.total == counts["total"] and summary.component_counts.placed == counts["placed"]
    assert summary.component_counts.by_component_type == counts["component_type_counts"]
    medium = timed("summarize_topology MEDIUM", lambda: client.summarize_topology("sample"))
    topology = medium.topology_summary
    assert sum(line.component_count for area in topology.areas for line in area.lines) + topology.unassigned_to_line == counts["total"]
    assert sum(location.component_count for location in topology.locations) + topology.unplaced_component_count == counts["total"]
    full = timed("summarize_topology FULL", lambda: client.summarize_topology("sample", detail_level="FULL")).topology_summary
    listed = [c.ets_id for area in full.areas for line in area.lines for c in line.components]
    listed += [c.ets_id for c in full.unassigned_components]
    assert len(listed) == counts["total"] == len(set(listed))
    assert len(full.unplaced_components) == counts["unplaced"]


def test_all_group_addresses_are_addressable_and_participants_equal_the_memberships(index):
    group_addresses = index.group_addresses
    assert len(group_addresses) == EXPECT["totals"]["group_addresses"]
    participants = 0
    for ga in group_addresses:
        for selector in {ga.address}:  # project style (ThreeLevel) equals the 3-level form
            result = trace(index, selector, None, DetailLevel.SUMMARY)
            assert result.match_count == 1 and result.entries[0].group_address.ets_id == ga.id
        entry = result.entries[0]
        participants += len(entry.participants)
        assert all(p.direction in DIRECTIONS for p in entry.participants)
        assert entry.current_value == "unknown" and entry.propagation_path.scope == "DIRECT_PARTICIPANTS"
    assert participants == EXPECT["totals"]["memberships"]


def test_partial_group_address_name_returns_an_ambiguous_set(index):
    named = [g for g in index.group_addresses if g.name]
    # 3-character prefixes without surrounding whitespace (the selector is stripped before matching)
    prefixes = Counter(g.name[:3].casefold() for g in named if len(g.name) >= 3 and g.name[:3] == g.name[:3].strip())
    prefix, _ = prefixes.most_common(1)[0]
    expected = [g for g in index.group_addresses if g.name and prefix in g.name.casefold()]
    assert len(expected) > 1
    query = prefix.upper() if prefix.isascii() else prefix  # upper-casing non-ASCII letters can change their casefold
    result = trace(index, query, None, DetailLevel.MEDIUM)
    assert result.ambiguous is True and result.match_count == len(expected)
    raws = [e.group_address.ets_id for e in result.entries]
    assert raws == [g.id for g in sorted(expected, key=lambda g: (g.address_raw, g.id))]


def test_trace_group_flow_through_the_sdk_on_the_sample(client, index):
    linked = next(g for g in index.group_addresses if index.memberships_by_group_address.get(g.id))
    for level in LEVELS:
        response = timed(f"trace_group_flow {level}", lambda lv=level: client.trace_group_flow("sample", linked.address, detail_level=lv))
        assert response.match_count == 1 and response.group_addresses[0].current_value == "unknown"
    obj_id = index.memberships_by_group_address[linked.id][0].communication_object_id
    by_object = client.trace_group_flow("sample", communication_object_ref=obj_id)
    assert linked.id in {e.group_address.ets_id for e in by_object.group_addresses}


def test_sdk_flow_leaves_session_state_unchanged_and_records_timing(env):
    client, root = env
    before = state_bytes(root, "sample")
    for level in LEVELS:
        timed(f"list_components {level}", lambda lv=level: client.list_components("sample", detail_level=lv))
        timed(f"describe_component {level}", lambda lv=level: client.describe_component("sample", EXPECT["example_component_id"], detail_level=lv))
        timed(f"summarize_topology {level} (again)", lambda lv=level: client.summarize_topology("sample", detail_level=lv))
        timed(f"trace_group_flow {level} (name)", lambda lv=level: client.trace_group_flow("sample", group_address_selector="a", detail_level=lv))
    assert state_bytes(root, "sample") == before
    print("\nquery wall times (s):")
    for label, seconds in TIMINGS.items():
        print(f"  {label}: {seconds:.2f}")


def test_cli_on_the_sample(env):
    _client, root = env
    runner = CliRunner()
    listed = runner.invoke(app, ["setup", "list-components", "--session", "sample", "--session-root", str(root), "--detail-level", "SUMMARY"])
    assert listed.exit_code == 0, listed.stderr
    assert json.loads(listed.stdout)["match_count"] == EXPECT["components"]["total"]
    flow = runner.invoke(app, ["setup", "trace-group-flow", "--session", "sample", "--session-root", str(root), "--group-address", "a"])
    assert flow.exit_code == 0, flow.stderr
    assert json.loads(flow.stdout)["match_count"] >= 1
