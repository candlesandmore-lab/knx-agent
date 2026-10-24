"""Measure the end-to-end import of the committed sample (dev script, not part of the shipped package).

Runs create_session on tests/lifedata/20261010-EFH-Armbruster.knxproj in a temporary session root (fingerprint,
archive guard, parser, derivation, persisted project-graph.json and session-state.yaml) and prints wall time,
peak RSS, graph file size and the summary counts as JSON on one line.

Usage: python scripts/measure_sample_import.py [--print-summary]
Run it through the MCP python_execution tool (cold process); repeat for a median.
"""

from __future__ import annotations

import json
import resource
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SAMPLE = REPO / "tests" / "lifedata" / "20261010-EFH-Armbruster.knxproj"


def main() -> int:
    if not SAMPLE.exists():
        print(json.dumps({"error": f"sample not found: {SAMPLE.name}"}))
        return 1
    sys.path.insert(0, str(REPO / "src"))
    from knx_agent.sdk import KnxSessionClient

    with tempfile.TemporaryDirectory() as root:
        client = KnxSessionClient(session_root=root)
        started = time.perf_counter()
        response = client.create_session(project_path=SAMPLE, session_label="measure")
        elapsed = time.perf_counter() - started
        graph = Path(response.work_directory) / "project-graph.json"
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_mib = peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024
        result = {
            "end_to_end_s": round(elapsed, 3),
            "peak_rss_mib": round(peak_mib, 1),
            "graph_file_bytes": graph.stat().st_size,
            "graph_file_mb": round(graph.stat().st_size / 1_000_000, 2),
        }
        if "--print-summary" in sys.argv:
            result["summary"] = json.loads(response.project_import_summary.model_dump_json())
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
