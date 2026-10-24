# Todo 07: Minimal expectation engine and activity questions
Source: use case 4, implementation 002 (Slice 4)
Goal: declarative rule-based propagation through group addresses and participants; ordered inputs so `now` = latest KNX system state; answers to should/why/why-not/what-changed with confidence, evidence sources, unresolved assumptions, and explicit statement of unsupported behaviour. Capabilities: explain_expected_reaction, simulate_outcome, list_possible_causes (003 proposes a single answer_activity_question; see todo 01).
Answered: `now` = state after applying ALL prior inputs in order of provision; "unknown, please provide input X" is a valid answer (three-valued, not binary); answers carry evidence sources and unresolved assumptions and write to the session log book; must support should/why/why-not/what-changed/what-input-caused-this; KNX component communication (sensor -> group address -> actuator and other readers) must be modelled. "All options" scenarios are built by the agent from multiple mutations.
Not in scope for the engine: original-vs-mutated comparison (agent level).
Depends on: 04, 05, 06
