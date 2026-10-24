<!-- Copyright (c) 2026 agent-building-agent contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Source: https://TBD (training course) -->

# Agent-Dev-Agent Installation and Usage Guide

This guide has two parts:

- **[Part 1: Setup and start](#part-1-setup-and-start)** — for the main user: install agent-dev-agent, configure it, and start developing with the prompted flow. Once you finish Part 1, you are ready to go.
- **[Part 2: Advanced reference](#part-2-advanced-reference)** — for users who also need CLI, SDK, coded-agent, testing, or release-packaging details. The main user does not need to read Part 2.

## Table of Contents

### Part 1: Setup and start

1. [Package contents](#package-contents)
2. [Prepare a Python environment](#prepare-a-python-environment)
3. [Install the Python package](#install-the-python-package)
4. [Set up API keys](#set-up-api-keys)
5. [Install prompted assets and MCP server](#install-prompted-assets-and-mcp-server)
6. [Cline MCP setup](#cline-mcp-setup)
7. [Start working](#start-working)

### Part 2: Advanced reference

8. [Coded sub-agents](#coded-sub-agents)
9. [MCP tools](#mcp-tools)
10. [Command-line reference](#command-line-reference)
11. [Instructed-agent fixtures and prompt-flow checks](#instructed-agent-fixtures-and-prompt-flow-checks)
12. [Run the live-endpoint test suite](#run-the-live-endpoint-test-suite)
13. [Build a release package](#build-a-release-package)
14. [Appendix: MCP JSON examples](#appendix-mcp-json-examples)
15. [License](#license)

---

# Part 1: Setup and start

[&#8593; Back to TOC](#table-of-contents)

Follow these sections in order. When you finish, your workspace is ready for prompted development with `agent-dev-agent`.

## Package contents

[&#8593; Back to TOC](#table-of-contents)

The release tarball contains:

- the `agent-building-agent` wheel
- the full `instructed-agents` asset tree
- `docs/schemas` with the story, review, gate, and task-plan schema assets used by new workspaces
- `coded-agent-config.yaml`, the runtime configuration for the four coded sub-agents (story-telling, review-validation, instructed-agent-creation, and QA)
- this `AGENT-DEV-AGENT-USAGE.md`, the installation and usage guide
- `LICENSE`, the GPL-3.0-or-later license text that must accompany all copies

## Prepare a Python environment

[&#8593; Back to TOC](#table-of-contents)

Before installing the wheel, you need `uv` and a target virtual environment.

If you are starting from an empty workspace, the minimal setup is:

```sh
uv venv
source .venv/bin/activate
```

You can then install the wheel into that environment with `uv pip install`.

A `pyproject.toml` file is not required for wheel installation. Create one only if you want the target workspace to be a uv-managed Python project as well.

If you want that project metadata, initialize it before installing the wheel:

```sh
uv init --bare
```

That produces a starter `pyproject.toml`, after which you can continue with the same wheel installation step below.

## Install the Python package

[&#8593; Back to TOC](#table-of-contents)

From the extracted release directory, install the wheel into your target Python environment:

```sh
uv pip install ./agent_building_agent-0.1.0-py3-none-any.whl
```

This installs the `agent-building-agent` CLI, SDK import package, and MCP server module.

## Set up API keys

[&#8593; Back to TOC](#table-of-contents)

The four coded sub-agents each need an API key to call their LLM endpoint. Each section in `coded-agent-config.yaml` names the environment variable its key must be read from (for example `ANTHROPIC_API_KEY`).

The recommended way is a key file — it gets baked into the MCP server config at install time (next section), so the framework host has the keys available automatically:

1. Create a plain-text file (e.g. `keys.env`) with one `KEY=value` line per key:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

2. Remember the path — you will pass it with `--api-config-file` in the next step.

> **Alternative:** If your API keys are already exported in your shell environment, you can skip the key file. The MCP server will inherit them as long as the framework host loads your shell profile.

## Install prompted assets and MCP server

[&#8593; Back to TOC](#table-of-contents)

From the extracted release directory, render the instructed-agent assets into your development workspace and register the MCP server:

```sh
agent-building-agent install --output-path /path/to/workspace
```

**With a key file** (if you created one in the previous step):

```sh
agent-building-agent install --output-path /path/to/workspace --api-config-file /path/to/keys.env
```

The `--api-config-file` flag bakes the key file path into the generated MCP server's `args`, so the framework-host-launched server has your API keys applied automatically at startup — no manual shell wrapping needed.

**Choose your framework target** (add `--framework-agent <target>` to the install command):

| Target | Agents | Skills | MCP config file | MCP config key |
|---|---|---|---|---|
| `vs-code-ghcp` | `.github/agents/*.agent.md` | `.github/skills` | `.vscode/mcp.json` | `servers` |
| `vs-code-claude` | `.claude/rules/*.md` | `.claude/skills` | `.mcp.json` | `mcpServers` |
| `cli-claude` | `.claude/rules/*.md` | `.claude/skills` | `.mcp.json` | `mcpServers` |
| `cli-cline` | `.clinerules/agents/*.md` | `.clinerules/skills` | `.mcp.json` + `.vscode/mcp.json` | `mcpServers` + `servers` |
| `vs-code-cline` | `.clinerules/agents/*.md` | `.clinerules/skills` | `.vscode/mcp.json` + `.mcp.json` | `servers` + `mcpServers` |

> **MCP config key difference:** GitHub Copilot (VS Code) reads the `servers` key; Claude (VS Code extension and CLI) reads the `mcpServers` key. The installer writes the correct key for each target automatically. Every generated server entry includes `"type": "stdio"` so it works out of the box in both formats.

> **Claude rule files:** `vs-code-claude` and `cli-claude` render agents as rule files under `.claude/rules/` and skills under `.claude/skills/` -- the only locations Claude Code's CLI and VS Code extension hosts actually discover as project instructions. The installer also creates or updates `.claude/CLAUDE.md` with a single line referencing the installed `agent-dev-agent` rule file, so Claude has a working entry point into the development flow immediately after install. On an `update`-mode install for these two targets, the installer also removes any files left at the old, pre-fix locations (`.vscode/claude/agents`, `.vscode/claude/skills`, `.claude/agents`).

The default command is equivalent to:

```sh
agent-building-agent install --mode new --framework-agent vs-code-ghcp --assets-path ./instructed-agents --docs-schemas-path ./docs/schemas --output-path /path/to/workspace
```

The install command bootstraps a development workspace skeleton at the output path (`development/backlog/`, `development/todos/`, `docs/`, `coded-agent-config.yaml`, `LICENSE`, `.gitignore`, agent/skill files in framework-specific locations, and the MCP server config). It also registers the MCP server so agents can call git, Python, pytest, YAML-validation, and coded-agent tools directly.

**Install modes:**
- `new` (default): create missing files and skip existing ones.
- `update`: overwrite rendered agent/skill files and the MCP server config entry. Never overwrites `docs/README.md`, `coded-agent-config.yaml`, or installed fixtures. For `vs-code-claude`/`cli-claude`, `update` also removes any files left at the old, pre-fix agent/skill locations (`.vscode/claude/agents`, `.vscode/claude/skills`, `.claude/agents`) before writing the new ones.
- `.claude/CLAUDE.md`'s single `agent-dev-agent` reference line (`vs-code-claude`/`cli-claude` only) is created or refreshed on every install, regardless of mode, the same as `.gitignore`; the rest of an existing `CLAUDE.md` is left untouched.

## Cline MCP setup

[&#8593; Back to TOC](#table-of-contents)

If you use Cline (`cli-cline` or `vs-code-cline` target), one extra manual step is required: Cline does not read workspace `.mcp.json` or `.vscode/mcp.json`. You must add the `agent-building-agent` server entry to Cline's global settings file — see [Appendix: MCP JSON examples](#appendix-mcp-json-examples) for the exact JSON and the global file path for each operating system.

After adding the entry, reload VS Code (Cmd+Shift+P → "Developer: Reload Window") or restart the Cline extension.

If you do not use Cline, skip this section.

## Start working

[&#8593; Back to TOC](#table-of-contents)

1. Open your workspace in your chosen framework (VS Code with Copilot, Claude CLI, Cline, etc.).
2. For `vs-code-ghcp`, select `agent-dev-agent` from the framework's agent surface. For Claude and Cline targets, just start a chat — `CLAUDE.md`/`.clinerules` load the development flow automatically.
3. Describe your development task. The `agent-dev-agent` follows the development flow: it creates stories from your todos, plans architecture, implements code, runs reviews, and validates results.

| Target | How to start |
|---|---|
| `vs-code-ghcp` | Select `agent-dev-agent` from the GitHub Copilot Chat agent picker in VS Code. |
| `vs-code-claude` | Start a chat in the Claude VS Code extension; `.claude/CLAUDE.md` references the installed `agent-dev-agent` rule file automatically. |
| `cli-claude` | Start a chat with the Claude CLI in the workspace; `.claude/CLAUDE.md` references the installed `agent-dev-agent` rule file automatically. |
| `cli-cline` | Start a chat and describe your task; the `.clinerules/` markdown guides Cline to follow the agent-dev-agent flow. |
| `vs-code-cline` | Same as `cli-cline` — start a chat and describe your task. |

**You are now ready to develop with agent-dev-agent.** The rest of this guide is for advanced users who also need CLI, SDK, coded-agent, testing, or release-packaging details.

---

# Part 2: Advanced reference

[&#8593; Back to TOC](#table-of-contents)

The main user does not need to read this part. It covers coded-agent invocation, MCP tool inventory, CLI/SDK reference, testing, release packaging, and MCP JSON examples.

## Coded sub-agents

[&#8593; Back to TOC](#table-of-contents)

The four coded sub-agents are Python/LangGraph implementations invoked over MCP, CLI, or SDK — not markdown files. They are configured by `coded-agent-config.yaml` at the workspace root.

| Slug | What it does |
|---|---|
| `story-telling-agent` | Transforms todo input into backlog-ready story YAML. |
| `review-validation-agent` | Executes review steps, produces findings, and emits gate decisions. |
| `instructed-agent-creation-agent` | Generates agent markdown, skill, and sub-skill assets. |
| `qa-agent` | Runs unit, interface, prompt, and demo validation layers. |

### Invocation surfaces

**MCP tool** (available to all framework targets via the registered MCP config):

The `coded_agent_invoke` MCP tool accepts:
- `agent_slug` — one of the four slugs above.
- `task_id` — a caller-supplied id; a new id starts a run, an existing id resumes persisted state.
- `inputs` — agent-specific input payload (dict).
- `answers` — answers to a prior failure contract's questions (dict), used to resume.

**CLI**:

```sh
agent-building-agent coded-agents <slug> --task-id <id> --input '<json>'
# or with a file:
agent-building-agent coded-agents <slug> --task-id <id> --input-file <path.json>
```

The four CLI subcommands are `story-telling`, `review-validation`, `instructed-agent-creation`, and `qa`.

**SDK**:

```python
from agent_building_agent.sdk import AgentBuildingAgentSdk

sdk = AgentBuildingAgentSdk()
response = sdk.run_coded_agent(
    agent_slug="qa-agent",
    task_id="smoke-test",
    inputs={"validation_scope": ["pytest"], "pytest_scope": "tests/test_models.py"},
)
```

### Failure and resume

If a coded agent cannot complete its task after five internal iterations, it returns `status: failed_after_iterations` with `questions` for you to answer. Re-run the same command with the same `task_id` and an `--answers` payload (CLI) or `answers` dict (MCP/SDK) to resume.

### `coded-agent-config.yaml`

Located at the workspace root. Each coded sub-agent section carries:
- `llm_endpoint` — provider (`claude` or `openai-compatible`), `base_url`, and `api_key_env`.
- `model` — model name.
- `system_prompt` — user-reviewable system prompt.
- `max_tokens` — maximum output tokens for structured payloads (default 8192).

Edit this file to change a coded agent's provider, model, or system prompt. Re-running `install --mode update` preserves your `system_prompt`, `model`, and `llm_endpoint` fields and only merges in new non-user-owned fields.

## MCP tools

[&#8593; Back to TOC](#table-of-contents)

The `agent-building-agent mcp-serve` MCP server registers the following tools, available to every framework target:

**Git tools**:
- `git_repository_context` — inspect repository state, status, branch list, log, and show.
- `git_change_review` — review working-tree or staged diffs.
- `git_staging` — stage approved file paths.
- `git_commit_workflow` — create an approved commit.
- `git_branch_sync` — manage branches and remote synchronization (branch_create, switch, pull, push).

**Execution tools**:
- `render_python_execution` — render a Python command for a module or script.
- `render_pytest_execution` — render the pytest command for a test scope.
- `validate_yaml` — validate YAML files and return structured parse findings.

**Coded-agent tool**:
- `coded_agent_invoke` — invoke any of the four coded sub-agents.

## Command-line reference

[&#8593; Back to TOC](#table-of-contents)

### Install

```sh
agent-building-agent install [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--mode` | `new` | Install mode: `new` (skip existing files) or `update` (overwrite rendered files). |
| `--framework-agent` | `vs-code-ghcp` | Framework target: `vs-code-ghcp`, `vs-code-claude`, `cli-claude`, `cli-cline`, `vs-code-cline`. |
| `--assets-path` | `./instructed-agents` | Path to the canonical instructed-agents asset tree. |
| `--docs-schemas-path` | `./docs/schemas` | Path to the docs schema assets copied into new workspaces. |
| `--coded-agent-config-path` | `./coded-agent-config.yaml` | Path to the coded-agent runtime configuration YAML. |
| `--agent-usage-path` | `./AGENT-DEV-AGENT-USAGE.md` | Path to the agent usage README. |
| `--license-path` | `./LICENSE` | Path to the LICENSE file. |
| `--output-path` | `.` | Workspace root where rendered files are installed. |
| `--api-config-file` | *(none)* | Path to a `KEY=value` API-key file baked into the generated MCP server `args` as `--api-config-file`. |
| `--target` | `target-workspace` | Install target: `target-workspace` (default, everything above) or `development-workspace`. |

**`--target development-workspace`** is for agent-building-agent maintainers only: it runs the installer against agent-building-agent's own source repository (for example its own pip-installed `.venv/bin/agent-building-agent`) to validate the packaged install flow end to end, without touching `development/`, `docs/`, `instructed-agents/`, `src/`, or `tests/` in that repository -- it skips the `development`/`docs` bootstrap and the `instructed-agents`/`docs/schemas` copy-back steps, since source and destination are the same tree there. Framework-agent rendering, MCP registration, `.gitignore`, and `coded-agent-config.yaml` still run. From the agent-building-agent repository root, after `uv build --wheel` and `uv pip install dist/*.whl`:

```sh
.venv/bin/agent-building-agent install --target development-workspace --mode update --framework-agent cli-claude
```

`--mode update` intentionally overwrites any existing hand-authored `agent-building-agent` MCP entry in place with the resolved installed-binary command; edit `.mcp.json`/`.vscode/mcp.json` by hand afterwards to switch back to a source-based `uv run` dev loop.

### MCP server

```sh
agent-building-agent mcp-serve [--api-config-file <path>]
```

Runs the MCP server over stdio. Use `--api-config-file` to apply a key file to the process environment before the server starts serving tool calls.

### Coded agents

```sh
agent-building-agent coded-agents <slug> --task-id <id> [OPTIONS]
```

| Option | Description |
|---|---|
| `--task-id` | Required. A caller-supplied id; new starts a run, existing resumes. |
| `--input` | JSON input payload. |
| `--input-file` | Path to a JSON input file (alternative to `--input`). |
| `--answers` | JSON answers payload to resume after `failed_after_iterations`. |

### Release package

```sh
agent-building-agent release-package <wheel-path> [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--assets-path` | `./instructed-agents` | Path to the instructed-agents asset tree. |
| `--docs-schemas-path` | `./docs/schemas` | Path to docs schema assets. |
| `--coded-agent-config-path` | `./coded-agent-config.yaml` | Path to the coded-agent runtime configuration YAML. |
| `--agent-usage-path` | `./AGENT-DEV-AGENT-USAGE.md` | Path to the agent usage README. |
| `--license-path` | `./LICENSE` | Path to the LICENSE file. |
| `--output-dir` | `./dist` | Directory where the release tarball is written. |

### Global options

| Option | Description |
|---|---|
| `--api-config-file <path>` | Path to a `KEY=value` file applied to the process environment before any command runs. |
| `--log-dir <dir>` | Log directory. Defaults to `agent_building_agent/` in the current directory. Every run writes a shared, datetime-stamped log file in this directory (`agent_building_agent_<datetime>.log`); coded agents additionally write their own `<agent-slug>.log` file here. |
| `--log-level <level>` | Log level: `info`, `debug`, `warning`, or `error`. Defaults to `info`. |

## Instructed-agent fixtures and prompt-flow checks

[&#8593; Back to TOC](#table-of-contents)

Every installed agent ships one small, user-editable YAML fixture at `instructed-agents/agents/<agent-slug>/fixtures/<fixture-slug>.yaml` in your workspace. For the four coded sub-agents (`story-telling-agent`, `review-validation-agent`, `instructed-agent-creation-agent`, `qa-agent`), this is the same input fixture used by the live-endpoint test suite below and by their `coded-agents` CLI commands.

For instructed agents with no CLI/SDK/MCP entry point of their own — for example `coded-subagent-creation-agent`, invoked by prompt rather than by a runnable command — the fixture instead seeds a prompt-flow check: edit the fixture's fields to describe a real scenario, paste them as the task input when you invoke the agent (directly, or by asking `agent-dev-agent` to delegate to it), and confirm the agent follows its skill's routing and handoff rules before treating the check as passed. `update`-mode installs never overwrite an already-installed fixture, so your edits persist across upgrades.

## Run the live-endpoint test suite

[&#8593; Back to TOC](#table-of-contents)

If you are working from a checkout of the development repository (not just the installed wheel), you can run each coded sub-agent end to end against its real configured endpoint before relying on the shipped default system prompts in production. The suite is opt-in and skips cleanly when API keys are not configured.

Edit the fixture templates under `tests/coded_agents/fixtures/`:

- `llm-endpoints.yaml`: the central fixture carrying `provider`, `base_url`, `api_key_env`, and `model` for each of the four coded agents.
- `story-telling-agent-input.yaml`, `review-validation-agent-input.yaml`, `instructed-agent-creation-agent-input.yaml`, `qa-agent-input.yaml`: small, per-agent input payloads. These are also valid `--input-file` arguments for the `coded-agents` CLI commands shown above.

Export the API key environment variable named by the endpoint you want to exercise (for example `ANTHROPIC_API_KEY`), then run:

```sh
uv run pytest -m live_endpoint
```

Tests for agents whose `api_key_env` is not set are skipped, not failed. The default `uv run pytest tests` invocation never runs these live tests.

## Build a release package

[&#8593; Back to TOC](#table-of-contents)

Repository maintainers can build the wheel and assemble the release tarball with:

```sh
uv build --wheel
uv run agent-building-agent release-package dist/agent_building_agent-0.1.0-py3-none-any.whl
```

The release tarball is written to `dist/agent-dev-agent-0.1.0.tar.gz` and contains the wheel, `instructed-agents`, `docs/schemas`, `coded-agent-config.yaml`, `AGENT-DEV-AGENT-USAGE.md`, and `LICENSE`.

If you run plain `uv build`, uv also creates `dist/agent_building_agent-0.1.0.tar.gz`. That file is the Python source distribution and is not the agent-dev-agent release package.

## Appendix: MCP JSON examples

[&#8593; Back to TOC](#table-of-contents)

This appendix collects the exact MCP JSON formats for each framework target. The installer writes these automatically; they are shown here for reference, troubleshooting, and manual Cline setup.

### Claude format (`.mcp.json`, `mcpServers` key)

Used by `vs-code-claude` and `cli-claude`:

```json
{
  "mcpServers": {
    "agent-building-agent": {
      "type": "stdio",
      "command": "/absolute/path/to/your/workspace/.venv/bin/agent-building-agent",
      "args": ["mcp-serve"],
      "cwd": "/absolute/path/to/your/workspace"
    }
  }
}
```

With `--api-config-file` baked in at install time:

```json
{
  "mcpServers": {
    "agent-building-agent": {
      "type": "stdio",
      "command": "/absolute/path/to/your/workspace/.venv/bin/agent-building-agent",
      "args": ["mcp-serve", "--api-config-file", "/absolute/path/to/keys.env"],
      "cwd": "/absolute/path/to/your/workspace"
    }
  }
}
```

### GitHub Copilot format (`.vscode/mcp.json`, `servers` key)

Used by `vs-code-ghcp`:

```json
{
  "servers": {
    "agent-building-agent": {
      "type": "stdio",
      "command": "/absolute/path/to/your/workspace/.venv/bin/agent-building-agent",
      "args": ["mcp-serve"],
      "cwd": "/absolute/path/to/your/workspace"
    }
  }
}
```

### Cline global settings file location

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` |
| Windows | `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json` |
| Linux | `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` |

If you use a VS Code distribution other than standard VS Code (e.g. VS Code Insiders, Cursor, VSCodium, Windsurf), replace the `Code` segment accordingly.

### Cline global settings JSON

Add the `agent-building-agent` entry under `mcpServers` in the global settings file:

```json
{
  "mcpServers": {
    "agent-building-agent": {
      "type": "stdio",
      "command": "/absolute/path/to/your/workspace/.venv/bin/agent-building-agent",
      "args": ["mcp-serve"],
      "cwd": "/absolute/path/to/your/workspace"
    }
  }
}
```

With `--api-config-file`:

```json
{
  "mcpServers": {
    "agent-building-agent": {
      "type": "stdio",
      "command": "/absolute/path/to/your/workspace/.venv/bin/agent-building-agent",
      "args": ["mcp-serve", "--api-config-file", "/absolute/path/to/keys.env"],
      "cwd": "/absolute/path/to/your/workspace"
    }
  }
}
```

After editing the global settings file, reload VS Code (Cmd+Shift+P → "Developer: Reload Window") or restart the Cline extension. The workspace `.mcp.json` and `.vscode/mcp.json` files the installer writes coexist with the global Cline config without conflict.

## License

[&#8593; Back to TOC](#table-of-contents)

This project is licensed under the GNU General Public License v3 or later (GPL-3.0-or-later). The `LICENSE` file in the release tarball and at the installed workspace root contains the full license text. You may freely use and copy the assets, provided that all copies carry the `LICENSE` file and an attribution pointer to the training course (https://TBD).