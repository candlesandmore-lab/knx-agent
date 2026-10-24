# Todo 05: KNX bus-trace ingestion and observation decoding
Source: implementation 002 (Slice 3)
Goal: parse a first supported trace format into timestamped trace observations; resolve addresses/datapoints against the project graph; infer candidate environment conditions and user actions with explicit confidence and provenance; store observations separately from project facts and accepted scenario state. Capabilities: load_bus_trace, decode_telegram, infer_environment_from_trace, summarize_recent_activity.
Blocker: user must name the first trace format and provide a sanitized sample.
Depends on: 02, 03, 04

Additional information (user, 2026-10-24):
- (b) KNX bus traces come from the ETS 6 Professional bus monitor, so the first supported trace format is the ETS 6 bus monitor export. Per KNX support documentation ETS can export recorded telegrams as XML (contains the raw cEMI frame as hex) or CSV; the exact ETS 6 layout is not publicly specified, so a real sample export is still needed to fix the format. No Python parser for ETS trace exports was found (eibparser targets knxd output); decode the raw cEMI frames ourselves and cross-check against ETS.
- Blocker remains only for a sample trace file from the user (to be placed under tests/lifedata/). `ProjectTrace` elements inside a `.knxproj` are ETS change history and are not bus traces.
