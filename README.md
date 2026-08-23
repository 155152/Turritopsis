# Turritopsis

**A shared handoff layer for long-running projects.**

**1 human + 4 agents. 71 days. 500K lines of active code.**

> Agents come and go. Projects shouldn't forget.

Your coding agent can read the code. Turritopsis tells it:

- what is true now;
- why the project ended up this way;
- where the current work stopped;
- what has already failed;
- which boundaries must not be broken;
- and where to continue.

```text
list_stages()
search_stages("why is release frozen?")
get_stage("project.handoff")
```

Turritopsis is not private agent memory, code indexing, session continuation, a project wiki, or chunked RAG. It is a small, Git-friendly address space for project knowledge that code and Git cannot reliably reconstruct.

## One MCP, many agents: a field-tested workflow

Turritopsis grew out of one human running a real long-term system with four different agents across chat, coding, local, and VPS workspaces. They did not share a private memory or a continuous session. They shared one project map through one MCP.

**Chat windows were for thinking.** ChatGPT and Claude could keep long-context brainstorming, product decisions, and difficult design conversations in the conversational surface where they belonged. Their context and token budgets were spent on reasoning instead of repeatedly reconstructing the repository.

**Coding windows were for execution.** A clean coding agent could arrive, call `list_stages`, `search_stages`, and `get_stage`, and take over in seconds. It did not need its own agent-memory system, a replay of old conversations, or a newly written handoff document. Clean windows stayed clean without losing engineering progress.

**A cheaper model handled routine maintenance.** It could inspect recent diffs and stale verification dates, refresh evidence-backed knowledge, and leave uncertain facts unresolved. Expensive models were reserved for decisions that deserved them.

**The human edited direction, not bookkeeping.** The Web UI provided a project map, Stage editor, live Markdown preview, revision conflicts, proposals, and history. The human corrected priorities, boundaries, and project meaning while agents maintained implementation detail from traceable evidence.

The practical result was continuity without forcing every agent to become the memory system. Agents could disappear, sessions could end, and a new coding window could still find the current truth and continue the work.

## Install and start

```bash
python -m pip install -e .
turritopsis init --yes --name "My Project" --description "What this project does"
turritopsis init --yes --name "My Project" --modules "API, Worker, Web"
turritopsis add anatomy anatomy.components "Current components"
turritopsis serve --stdio
```

HTTP uses streamable MCP and listens only on loopback by default:

```bash
turritopsis serve                 # 127.0.0.1:3013
turritopsis serve --port 4013
turritopsis serve --data /project/.turritopsis/stages.json
```

Open `http://127.0.0.1:3013/` for the human Project Map. The same process serves:

- `/` — Project Map, search, Stage reader/editor, handoff, Authority, proposals, and history;
- `/mcp` — the four MCP tools;
- `/api/...` — the local UI API, backed by the same `Turritopsis`, `Store`, search, and update implementation.

`turritopsis ui` is an explicit alias when only the human surface is wanted. No Node runtime, frontend build, LLM, or API key is needed after installation.

Remote exposure is explicit (`--host 0.0.0.0`) and should be placed behind an authentication layer.

## Knowledge model

A **Current** routes a kind of project question. The default currents are `anatomy`, `flow`, `bounds`, `manual`, and `genesis`; a long-lived domain may also be its own Current.

A **Stage** is one complete, named knowledge region—not an arbitrary text chunk. Stage Markdown may contain English or Chinese metadata:

```markdown
# Current work and handoff

Purpose: Tell a new contributor where work currently stands.
Search hints: handoff blocker next step release current work
Summary: Release is frozen pending hardware regression.
Verified: 2026-08-24 by agent
Status: current
Authority: current work, next action
```

Keep current truth, historical explanation, and deterministic generated facts in separate Stages. `Status: historical` never silently presents itself as current authority. A generated Stage should say that manual edits will be overwritten.

## Four MCP tools

- `list_stages(current?)` maps currents or compact Stage metadata, never bodies.
- `search_stages(...)` provides explainable weighted routing or exact line/context matches.
- `get_stage(stage_id)` returns one complete Stage and its body-hash revision.
- `update_stage(...)` supports replace/append, optional `expected_revision`, actor logs, rolling backups, and conflict responses.

Search weights preserve the proven live routing order: Stage id, search hints, title, authority, summary, purpose, status/verification, Current, then headings/body. `semantic` is an explainable structured-field router; it does not claim embeddings.

All reads reload `stages.json`. Writes take a file lock, compare only the target Stage revision, write through a temporary file with `fsync`, atomically replace the canonical file, append `changelog.jsonl`, and keep rolling backups.

## Structure and maintenance

```text
.turritopsis/
├── stages.json
├── config.json
├── scan-evidence.json
├── changelog.jsonl
├── maintenance.jsonl
├── backups/
└── proposals/
```

Ordinary `turritopsis init` asks for the main modules and creates initial Current/Stage addresses. `--modules` supplies the same answer non-interactively.

`turritopsis init --scan` reads a bounded project tree, README files, manifests, CI/configuration documents, and other non-sensitive text materials. An LLM classifies that evidence into the first 3–8 Currents and Stage addresses. It may author titles, Purpose, Search hints, Authority, and evidence routing; unverified canonical knowledge remains an explicit placeholder. The captured input is written to `scan-evidence.json` for reviewability.

Scan and maintenance share `.turritopsis/config.json`:

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

Supported providers are `openai`, `anthropic`, and `openai-compatible`. Compatible providers require `base_url`. Settings can be overridden with `TURRITOPSIS_LLM_PROVIDER`, `TURRITOPSIS_LLM_MODEL`, `TURRITOPSIS_LLM_API_KEY_ENV`, `TURRITOPSIS_LLM_BASE_URL`, `TURRITOPSIS_LLM_TIMEOUT`, and `TURRITOPSIS_LLM_MAX_TOKENS`. API key values are read only from the configured environment variable and are never written to project files.

`turritopsis maintain` checks recent Git changes, missing referenced paths, and verification age. For each affected curated Stage it sends the current body and bounded project evidence to the configured LLM, validates the returned JSON and cited evidence ids, updates `Verified`, then writes through the normal Stage revision, lock, backup, atomic replace, and changelog path. If evidence is insufficient, the model must return `no_change`.

```bash
turritopsis maintain
turritopsis maintain --model CHEAP_MODEL
turritopsis maintain --proposal-only
turritopsis maintain --schedule "0 3 * * *" --model CHEAP_MODEL
turritopsis maintain --show-schedule
turritopsis maintain --unschedule
turritopsis export --format md
turritopsis export --format json --output project-knowledge.json
```

`--proposal-only` preserves a review-first drift report when desired; `--apply` still applies an explicitly reviewed proposal. They are optional workflows, not restrictions on normal evidence-backed maintenance.

`--schedule` installs or replaces one path-scoped entry in the current POSIX user's crontab. The example above runs every day at 03:00 in the cron host's local timezone, writes output to `.turritopsis/maintenance-cron.log`, and is idempotent when repeated. It never writes an API key into crontab: the `api_key_env` named in `config.json` must already be available to the cron environment. `--show-schedule` and `--unschedule` inspect or remove only Turritopsis' marked block for this project. On hosts without `crontab`, invoke the same `turritopsis maintain --model CHEAP_MODEL` command from CI or the native scheduler.

The sole automatic-write exception is an explicitly generated Stage with a deterministic generator configuration:

```json
{
  "id": "anatomy.revision",
  "title": "Current Git revision",
  "status": "generated",
  "generator": {"type": "git_revision"},
  "body": ""
}
```

Built-in deterministic types are `git_revision`, `file_hash`, and `path_exists`. Their output is visibly marked auto-generated and does not use the LLM.

Core list/search/get/update, Web UI, and MCP serving require no LLM and no API key. Only `init --scan` and automatic curated maintenance do.

## License

Turritopsis is open-source software released under the standard [MIT License](LICENSE). Commercial use, modification, distribution, sublicensing, and private use are permitted subject to the license notice requirement.

## Development

```bash
python -m pip install -e ".[test]"
pytest
```
