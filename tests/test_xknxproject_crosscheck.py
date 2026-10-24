"""Cross-check of our import against xknxproject (dev-only dependency, GPL-2.0; never imported by src/).

Skips with a message when xknxproject is not installed or when the sample project is absent. No code of
xknxproject is copied; only its parse result is compared.

Known difference, explained: xknxproject lists only communication objects that have at least one group address
link, so its total (677) is lower than ours (692). We therefore compare per component on our objects that have a
membership.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from knx_agent.application.project_importer import import_project

xknxproject = pytest.importorskip("xknxproject", reason="xknxproject is not installed (dev dependency group)")

SAMPLE = Path(__file__).parent / "lifedata" / "20261010-EFH-Armbruster.knxproj"

pytestmark = pytest.mark.skipif(
    not SAMPLE.exists(), reason=f"sample project {SAMPLE.name} is absent; the cross-check is skipped"
)


@pytest.fixture(scope="module")
def both():
    ours = import_project(SAMPLE).graph
    theirs = xknxproject.XKNXProj(path=SAMPLE).parse()
    return ours, theirs


def test_individual_addresses_are_equal(both):
    ours, theirs = both
    ours_addresses = {c.individual_address for c in ours.nodes_of("component")}
    assert ours_addresses == set(theirs["devices"])
    assert len(ours_addresses) == 28


def test_group_addresses_are_equal(both):
    ours, theirs = both
    ours_addresses = {g.address for g in ours.nodes_of("group_address")}
    assert ours_addresses == set(theirs["group_addresses"])
    assert len(ours_addresses) == 695
    raw = {g.address: g.address_raw for g in ours.nodes_of("group_address")}
    assert all(raw[address] == entry["raw_address"] for address, entry in theirs["group_addresses"].items())


def test_communication_objects_with_links_match_per_component(both):
    ours, theirs = both
    components = {c.id: c.individual_address for c in ours.nodes_of("component")}
    owner = {o.id: o.component_id for o in ours.nodes_of("communication_object")}
    linked = {relation.communication_object_id for relation in ours.source_facts.relations.membership}
    per_component = Counter(components[owner[object_id]] for object_id in linked)
    expected = {address: len(device["communication_object_ids"]) for address, device in theirs["devices"].items()}
    assert {address: per_component.get(address, 0) for address in expected} == expected
    assert sum(expected.values()) == len(theirs["communication_objects"]) == len(linked)


def test_the_object_count_gap_is_objects_without_group_address_links(both):
    ours, theirs = both
    linked = {relation.communication_object_id for relation in ours.source_facts.relations.membership}
    total = len(ours.nodes_of("communication_object"))
    assert total > len(theirs["communication_objects"])  # we keep objects that have no link
    assert total - len(linked) == total - len(theirs["communication_objects"])
