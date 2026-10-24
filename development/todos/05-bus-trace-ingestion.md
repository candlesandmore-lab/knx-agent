# Todo 05: KNX bus-trace ingestion and observation decoding
Source: implementation 002 (Slice 3)
Goal: parse a first supported trace format into timestamped trace observations; resolve addresses/datapoints against the project graph; infer candidate environment conditions and user actions with explicit confidence and provenance; store observations separately from project facts and accepted scenario state. Capabilities: load_bus_trace, decode_telegram, infer_environment_from_trace, summarize_recent_activity.
Blocker: user must name the first trace format and provide a sanitized sample.
Depends on: 02, 03, 04
