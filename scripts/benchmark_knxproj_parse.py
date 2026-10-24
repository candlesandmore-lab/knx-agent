# Copyright (c) 2026 agent-building-agent contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Dev benchmark (story 04, T1): stdlib ElementTree streaming read of the sample .knxproj.

Not part of the shipped package. Never extracts the archive: every entry is read through
``zipfile.ZipFile.open``. Run it through the MCP python_execution tool::

    scripts/benchmark_knxproj_parse.py [path-to.knxproj] [--runs 3]

The parent process starts ``--runs`` cold child processes (this script with ``--child``) and prints the
per-file times, total wall time and peak RSS of each run plus the median total.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import statistics
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

DEFAULT_SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "lifedata" / "20261010-EFH-Armbruster.knxproj"
CLEAR_TAGS = {"Translation", "TranslationUnit", "TranslationElement", "Language", "Dynamic", "when", "choose", "Channel"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _peak_rss_mib() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _timed(timings: dict[str, float], key: str, func):
    start = time.perf_counter()
    result = func()
    timings[key] = time.perf_counter() - start
    return result


def _read_zero_xml(archive: zipfile.ZipFile, name: str) -> dict:
    """Stream 0.xml; keep only what the program lookup needs (components and their referenced ids)."""
    components = []
    counts = {"DeviceInstance": 0, "GroupAddress": 0, "ComObjectInstanceRef": 0, "ParameterInstanceRef": 0}
    current = None
    with archive.open(name) as stream:
        for event, element in ET.iterparse(stream, events=("start", "end")):
            tag = _local(element.tag)
            if event == "start":
                if tag == "DeviceInstance":
                    current = {"hw2p": element.get("Hardware2ProgramRefId"), "com": set(), "par": set()}
                continue
            if tag in counts:
                counts[tag] += 1
            if tag == "ComObjectInstanceRef" and current is not None:
                current["com"].add(element.get("RefId"))
            elif tag == "ParameterInstanceRef" and current is not None:
                current["par"].add(element.get("RefId"))
            elif tag == "DeviceInstance" and current is not None:
                components.append(current)
                current = None
                element.clear()
    return {"components": components, "counts": counts}


def _hardware_map(archive: zipfile.ZipFile, name: str) -> dict[str, str]:
    mapping = {}
    with archive.open(name) as stream:
        current = None
        for event, element in ET.iterparse(stream, events=("start", "end")):
            tag = _local(element.tag)
            if event == "start" and tag == "Hardware2Program":
                current = element.get("Id")
            elif event == "end" and tag == "ApplicationProgramRef" and current:
                mapping[current] = element.get("RefId")
            elif event == "end" and tag == "Hardware2Program":
                current = None
    return mapping


def _read_program(archive: zipfile.ZipFile, name: str, com_ids: set[str], par_ids: set[str]) -> dict:
    """Stream one application program XML; keep only referenced ComObject/ComObjectRef/Parameter/ParameterRef."""
    kept = {"ComObject": 0, "ComObjectRef": 0, "Parameter": 0, "ParameterRef": 0}
    with archive.open(name) as stream:
        for _event, element in ET.iterparse(stream, events=("end",)):
            tag = _local(element.tag)
            if tag in kept:
                ident = element.get("Id", "")
                short = "_".join(ident.split("_")[2:])  # strip '<manufacturer>_<application>'
                if tag == "ComObjectRef" and short in com_ids:
                    kept[tag] += 1
                elif tag == "ParameterRef" and ident in par_ids:
                    kept[tag] += 1
                elif tag in ("ComObject", "Parameter"):
                    kept[tag] += 1
                element.clear()
            elif tag in CLEAR_TAGS:
                element.clear()
    return kept


def run_child(path: Path) -> dict:
    timings: dict[str, float] = {}
    total_start = time.perf_counter()
    fingerprint = _timed(timings, "sha256", lambda: _sha256(path))
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        project = next(n for n in names if n.endswith("/project.xml"))
        folder = project.rsplit("/", 1)[0]
        _timed(timings, project, lambda: sum(1 for _ in ET.iterparse(archive.open(project))))
        zero = _timed(timings, f"{folder}/0.xml", lambda: _read_zero_xml(archive, f"{folder}/0.xml"))
        if "knx_master.xml" in names:
            _timed(timings, "knx_master.xml", lambda: sum(1 for _ in ET.iterparse(archive.open("knx_master.xml"))))
        programs: dict[str, tuple[set[str], set[str]]] = {}
        hardware_maps: dict[str, dict[str, str]] = {}
        for component in zero["components"]:
            hw2p = component["hw2p"] or ""
            manufacturer = hw2p.split("_", 1)[0]
            hardware_name = f"{manufacturer}/Hardware.xml"
            if manufacturer not in hardware_maps and hardware_name in names:
                hardware_maps[manufacturer] = _timed(
                    timings, hardware_name, lambda n=hardware_name: _hardware_map(archive, n)
                )
            program_id = hardware_maps.get(manufacturer, {}).get(hw2p)
            if program_id:
                com, par = programs.setdefault(f"{manufacturer}/{program_id}.xml", (set(), set()))
                com |= component["com"]
                par |= component["par"]
        kept_total = {"ComObject": 0, "ComObjectRef": 0, "Parameter": 0, "ParameterRef": 0}
        read = 0
        for entry, (com, par) in sorted(programs.items()):
            if entry not in names:
                continue
            kept = _timed(timings, entry, lambda e=entry, c=com, p=par: _read_program(archive, e, c, p))
            read += 1
            for key, value in kept.items():
                kept_total[key] += value
    return {
        "fingerprint": fingerprint,
        "total_s": time.perf_counter() - total_start,
        "peak_rss_mib": _peak_rss_mib(),
        "timings_s": timings,
        "referenced_programs": len(programs),
        "programs_read": read,
        "zero_counts": zero["counts"],
        "kept": kept_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=str(DEFAULT_SAMPLE))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    path = Path(args.path)
    if args.child:
        print(json.dumps(run_child(path)))
        return
    results = []
    for _ in range(args.runs):
        completed = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).resolve()), str(path), "--child"],
            capture_output=True,
            text=True,
            check=True,
        )
        results.append(json.loads(completed.stdout))
    totals = [r["total_s"] for r in results]
    median_run = sorted(results, key=lambda r: r["total_s"])[len(results) // 2]
    print("runs total_s:", [round(t, 3) for t in totals])
    print("median total_s:", round(statistics.median(totals), 3))
    print("peak_rss_mib per run:", [round(r["peak_rss_mib"], 1) for r in results])
    print("median run per-file timings (s):")
    for key, value in median_run["timings_s"].items():
        print(f"  {key}: {value:.3f}")
    print("referenced programs:", median_run["referenced_programs"], "read:", median_run["programs_read"])
    print("0.xml counts:", median_run["zero_counts"])
    print("kept definitions:", median_run["kept"])
    print("fingerprint:", median_run["fingerprint"])


if __name__ == "__main__":
    main()
