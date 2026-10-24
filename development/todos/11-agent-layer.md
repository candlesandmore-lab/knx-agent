# Todo 11: Investigation agent layer (instructed)
Source: architecture 001 (1), implementation 002 (Slice 7a), 001 (agent interaction model)
Goal: instructed agent/skills for commercial reasoning agents: hypothesis -> session -> setup/environment/mutation -> trace -> simulate -> compare -> explanation + next checks; technical, short, crisp; never guess names/rooms/actions, ask for clarification; distinguish fact, inference, unknown; map natural-language actions to capability calls and telegram intents.
Answered: must work with commercial agents (GHCP, Claude or similar), so assets need rendering/installation guidance for more than one host; this is the only place natural language is handled; compares default vs. mutated results; creates multiple mutations when asked for "all options"; asks instead of guessing room/function names absent in the project.
Depends on: 01, then contracts from 10

Demo rule (todo 16): once implemented, add examples for new actions/features to ./demo (scripts and README) and keep existing demo scripts working.
