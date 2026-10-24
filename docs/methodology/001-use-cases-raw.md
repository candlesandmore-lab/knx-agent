**IMPORTANT (terminology)**: when I write user, I mean either human (CLI), another program (SDK) or agent (MCP surface)

+ IMPORTANT addition: the solution shall include a agent/skill layer that serves as the agent the user can prompt with natural language instructions and queries. That must be part of the solution. The coding agent that uses those agent/skill will be any commercial agent GHCP, Claude or similar. The reasoning of those agents must be able to use the APIs to close the gap between human instruction and require KNX level action.
  - As for agent/skill implementation. The agent must work with technical short and crisp tone. It must never guess anything (like a component name). If user input is not clear, complete or ambigious, the agent/skill must ask and clarify with the human.

Review annotations below are intentionally phrased as open questions. They mark information that should be clarified before these use cases are converted into stable APIs or formal implementation contracts.

1) User goal: Understand settings/configuration/parameters of components in KNX system
Success criteria:
- The user is able to query available components by name or purpose (blind actor, ...), the system provides available components
  - A broad query for all components in available, the solution returns information with configurable detail level (SUMMARY, MEDIUM, FULL (all available info))
- The user is able to get the  configuration data of a component, selected by name
- settings/configuration/parameters are coming from the knxproj file, the form the **terminology! : KNX system setup**

Questions / ambiguities:
- What is the canonical selector for a component: display name, individual address, ETS identifier, device instance path, or a combination? A: either of them
- How should the system handle non-unique names, such as multiple actuators with the same room-oriented label? A: a query without room oriented part will return a set of components, user can add room oriented part. There is an importance on 'name', user can provide it partially like 'Kid' to get components in all Kids rooms for instance
- What exactly counts as `purpose`: device application type, room role, communication-object semantics, tags inferred from names, or vendor metadata? A: the solution shall be able to understand sensor or actor purpose and annotate the system setup with it. E.g. a component type that points to a shade actor has a purpose 'shade controls'.
- Should `SUMMARY`, `MEDIUM`, and `FULL` be fixed output profiles with named field sets, or just general guidance for later API design? A: the API design shall support user provided level, default being 'MEDIUM'
- Does `FULL` mean only decoded `.knxproj` data, or also enriched vendor documentation when available? A: Anything the solution has including purpose if avaialble.
- Should the returned configuration include only device-level parameters, or also linked group addresses, communication objects, and topology placement? A: topology yes, device-level parameters yes (both for SUMMARY), when it comes to FULL, group addresses and comm objects as well.

2) User goal: Understand and update system environment information
Success criteria:
- The user is able to query sensor values that are input to the KNX system
  - Query by name or purpose
  - Query broadly to understand what is an input
- The user is able to provide a value for simulation
  - The solution stores the information in an **terminology! : environment model**
  - The system understands the KNX activity (group address an value) and simulates its impact on the **terminology! : KNX system state**

Questions / ambiguities:
- What is the boundary between a sensor value from the KNX project, a live or traced observation, and a user-supplied simulation override? A: The 'KNX system state' can be impaced by (a) the user suppied simulation overwrite or (b) a KNX bus trace provided by the user. The KNX project itself does not have sensor values. Sensor value state lives in the **terminology! : KNX system state**
- Is the user expected to set environment information by semantic concept such as `room temperature`, by sensor name, by group address, or by a combination? A: let us start with name, that requires the sensor names to be find-able in use case (1)
- Are environment values global, room-scoped, facade-scoped, or device-scoped? A: their scope must be the actual sensor in the KNX system, the solution must mimic the event(s) based on it, e.g. user providing a sun-lux-value, solution shall check which actor would act (if any) with whatever group-address-packet that other components will read (ripple-down)
- How should units and value normalization be handled, such as Celsius versus Fahrenheit or percentage versus raw datapoint value? A: normalize to KNX datatypes from ETS (KNX org)
- Does a user-supplied environment value replace a trace-derived value, coexist beside it, or require an explicit override rule? A: Last come wins. If a user reads in a trace, then the trace data is valid. If later in the SDK/CLI/MCP flow other value is provided, then this becomes the value in the environment model
- What exactly is the intended difference between **environment model** and **KNX system state**? A: The environment model capture the primary inputs and the system state is the simulated resulting state, e.g. SUN=20.000LUX is environment model data => If that causes an action in the wheather station, it changes the system state, e.g. sun-protection enabled send to KNX bus. The solution must model KNX component communication.

3) User goal: Understand and update KNX user input
Success criteria:
- The user is able to provide input to the KNX system that in a real system relates to a user action like pressing a button
  - The system understands the KNX activity (group address an value) and simulates its impact on the KNX system state

Questions / ambiguities:
- Should user input be represented as a semantic action such as `press kitchen wall switch up`, as a KNX telegram payload, or both? A: human language control will be on the agent (agent/skill file) level. The agent shall use the APIs to identify the required KNX telegram payload.
- Do we need to support richer input gestures such as long press, short press, dimming, double press, rocker pair semantics, or scene invocation? A: if they are configured in the component in the knxproj file, yes!
- Must the system map a human action onto the underlying group address automatically from project data, or is the user expected to provide the address/value pair? A: The human input goes to the commercial agent (GHCP, ...) which must be able to use the solutions APIs to infer the exact KNX bus command.
- Should simulated user input become part of session history so later questions can refer to prior actions? A: That is an important point, for debug of the KNX session, it is important to maintain a **terminology! : KNX session log book** that can be used by the agent as well to reason behavior.
- How should conflicting or impossible user inputs be handled, for example pressing a control that cannot be resolved from the project graph? A: that is an error

4) User goal: Ask question about KNX system activities
Success criteria:
- The user can ask question on actions in the system, example:
  - Should the ligth in room#1 be on now?
  - Should the blind go down in sun-automation now?

Questions / ambiguities:
- What does `now` mean in this context: current session scenario state, latest trace-derived observations, a simulated timeline position, or wall-clock time? A: NOW is the point in time after taking all the previous user input into account. That means the answer could be "I don't know, since I need some environment model input". E.g. when asking if light in room#1 is on, and never providing an input on the related component button, the solution won;t know. The soluiton must model all input by order of provision and based on that create a latest KNX system state. That state can be queries as of 'now'.
- Is the expected answer binary only, or should it also include confidence, reasoning, evidence sources, and unresolved assumptions? A: evidency sources and unresolved assumptions are important. It is also important to update the session log book
- Should the system answer only `should` questions, or also `why`, `why not`, `what changed`, and `what input caused this` questions? A: any of those and the agent must be able to use the APIs to do its best to find out.
- How should the system behave when the answer depends on missing environment values or unsupported device behavior? A: tell the user to provide it. If the user asks for all options, the agent should be able to create multiple what-if mutations and give answers.
- Do we need to support room- and function-level abstractions such as `room#1 light`, even when the project naming is inconsistent? A: the agent must not guess, if there is no notion of 'room#1' or 'light' in the KNX project, don't guess. Ask for clarification

5) User goal: what-if analysis with mutation of KNX system setup
Success criteria:
- The user can run a what-if analysis by providing updates to the KNX system setup on top of the knxproj settings
  - The user can run use-cases 1-4 on the mutated settings as well as on the original data
  - The settings are names and identifiable, knxproj settings are *default* and mutated settings are user names

Questions / ambiguities:
- Which parts of the KNX system setup are allowed to mutate: parameters, group memberships, topology, device replacement assumptions, names, or all of these? A: only parameters for now.
- Are mutations temporary overlays only, or can a session hold multiple named variants in parallel? A: a KNX session can hold multiple mutations in parallel. Information about them shall be persistent in mutation specific files in the session work dir. They shall be documented in the session state. Each mutation shall have a unique session log book (for actions on it) **and** the actions are also logged in the overall session log book.
- Can one session contain multiple what-if branches, and if so how are they selected and compared? A: yes, they are named and mutation names can be provided on API level. If not provided the default (none mutated) setup is used.
- Should mutations be stored as deltas against the bound `.knxproj` defaults rather than as rewritten full copies? A: YES
- What does `user names` mean here: user-defined labels for mutations, user identity, or user-defined configuration profiles? A: user defined name for a mutation provided upon creation and used optionally in any API.
- Do we need comparison outputs such as `original versus mutated expected reaction`, and if yes, what should be the minimal comparison format? A: That comparison should be done by agents (GHCP, ...) only, hence would be in the scope of the agent/skill implementation of the solution.
