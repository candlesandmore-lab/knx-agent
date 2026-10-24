# Todo 03: Investigation session lifecycle and project refresh
Source: architecture 001 (2b), implementation 002 (Slice 1, session persistence contract)
Goal: create/describe/open sessions; mandatory `.knxproj` at creation (fail otherwise); unique session id and work-directory; `session-state.yaml` (session_id, label, created_at, work_directory, source_project_absolute_path, project_import, project_refresh, trace_artifacts, scenario_state, mutation + logbook refs); refresh check (path/mtime/size, later fingerprint) on EVERY session-scoped call with automatic re-import; active-session resolution; session log book initialised.
Logging: lifecycle INFO, refresh-check DEBUG (see task plan log_point_matrix).
Depends on: 02
