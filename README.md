# Rollout Copilot

An AI assistant that helps a technical program manager run a 200-site network rollout.
It answers questions about the program, spots sites at risk, works out what vendors owe
under their contracts, and drafts status reports and escalations for a person to approve.

It runs inside **Claude Code** on your Mac and uses your Claude plan, so there are no API
charges. The rollout data is realistic but made up.

## What this project teaches you

| Concept | Where it is in this project | Plain-words meaning |
|---|---|---|
| **AI agent** | Claude Code, guided by `CLAUDE.md` | The AI decides which tools to call, in what order, to answer you |
| **Tool use** | `server/rollout_server.py` | Small functions the AI can call, like "list at-risk sites" |
| **MCP** | `.mcp.json` and the server | The standard plug that connects an AI to your own data and systems |
| **RAG** | `search_docs` tool | The AI looks up the right contract section and quotes it, instead of answering from memory |
| **Skills** | `.claude/skills/` | Saved, repeatable workflows: weekly status, vendor escalation, credit claim |
| **Evals** | `evals/` | A test set with known right answers, so you can prove accuracy |
| **Guardrails** | `draft_email`, `audit/` | The AI can only draft emails, never send, and every tool call is logged |

## Setup

### Option A: Claude Code on the web (nothing to install)

1. Open [claude.ai/code](https://claude.ai/code) and pick the `rollout-copilot` repository.
2. Start a session and type `/mcp` to confirm `rollout` is connected. The first session takes
   a few seconds longer while it installs the one Python package it needs.

### Option B: on your Mac

You need a paid Claude plan (Pro or Max) for Claude Code.

1. Install Claude Code: `curl -fsSL https://claude.ai/install.sh | bash`, then reopen Terminal.
2. Install uv, a free tool that brings a current Python: `curl -LsSf https://astral.sh/uv/install.sh | sh`,
   then reopen Terminal.
3. Clone the repository, `cd` into it, and run `claude`. Say yes when it asks to trust the folder
   and to use the `rollout` MCP server.

The server sets itself up on first start (`server/start.sh`), on the web and on your Mac.
To check the tools without the AI: `bash server/start.sh --setup-only && .venv/bin/python tests/test_tools.py`

## Things to try

Ask in plain English:

- `How is the rollout going?`
- `Which sites are at risk in the next 3 weeks, and what is the most common cause?`
- `Can S073 go live on schedule?`
- `Compare our two carriers.`
- `Is NorthStar meeting its contract? What does the contract let us do?`
- `The routers are backordered. Which go-live dates move, and what decision do I need from engineering?`

Run the skills:

- `/weekly-status` writes the Monday report to `reports/`
- `/vendor-escalation Cascade Fiber` drafts an evidence-based escalation to `outbox/`
- `/credit-claim Cascade Fiber` works out the credits owed and drafts the claim

Watch what happens: Claude shows each tool it calls. That is the agent at work.
Then open `audit/audit_log.jsonl` to see the record of every call.

## Update the data

**From the chat.** Tell Claude what changed, in plain words:

- `S073's routers arrived today and the store says it's ready.`
- `Cascade delivered the S072 circuit on 2026-11-17.`
- `Book a technician for S058 on 2026-11-20.`
- `Add a new site: Denver Store #301, Central, wave 15, Bluewave, ordered 2026-12-11.`
- `What changed on S073 this week?`

Claude uses the `update_site` and `add_site` tools. Claude Code asks you to approve each change.

**From the web GUI.** Start it and open http://localhost:8000:

```
bash gui/start.sh
```

It has an overview (tiles, risk by cause, at-risk list), a searchable and filterable site table,
the vendor scorecard, late circuits and a change log. Click any row to edit that site, or use
**+ Add site**.

**The same rules apply both ways** (`server/site_store.py`):
- Every value is checked first. Bad dates, unknown status words and unknown vendors are refused, and nothing is saved.
- Some fields fill themselves in. `circuit_status` follows from the circuit dates, a `live_date` makes the site Live, and `circuit_due` defaults to 30 days after the order.
- Every change goes to `audit/changes.jsonl` with the time, who made it (Claude or GUI), the reason, and the old and new values.

Once you edit the data, the numbers in `tests/test_tools.py` and `evals/questions.json` no longer
match. To go back to the demo data, run `git checkout data/sites.csv`.
To check the editing rules on a throwaway copy, run `.venv/bin/python tests/test_site_store.py`.

## Prove it works

On your Mac:

```
.venv/bin/python evals/run_evals.py
```

On the web, ask: `Run the eval questions in evals/questions.json one at a time using the rollout tools, then score each answer against its checks.`

The runner asks Claude 13 questions with known right answers, including two traps: a site that
does not exist, and a request to send an email it must not send. It prints a score and saves
every answer to `evals/results.md`. Run it after any change to the instructions or tools.

## The planted problems

The data hides a few real-world problems for the AI to find:
- One carrier delivers circuits late far more often than the other.
- One install vendor is well below its contract target for first-time installs.
- A router backorder threatens two weekly waves.
- Several stores told us they are not ready.

## How to talk about it in an interview

> "I built an AI copilot for a network rollout program. Claude acts as an agent over an MCP
> server I wrote, with tools for program status, risk detection and vendor performance, and
> retrieval over contracts and vendor emails so every answer cites its source. I added skills
> for the weekly leadership report, vendor escalations and carrier credit claims, a 13-question
> eval set including hallucination and safety traps, and guardrails: the AI can only draft
> emails, and every tool call is audit-logged."

## What's next

- **Week 2:** swap the made-up CSV for a Google Sheet, and connect Gmail so it reads real vendor emails.
- **Week 2:** upgrade search to meaning-based search (embeddings) with a free local model.
- **Week 3:** run the evals, fix what fails, and record a 3-minute demo video.

## Folder map

```
CLAUDE.md               instructions the AI follows in this project
.mcp.json               tells Claude Code how to start the rollout server
.claude/skills/         the three saved workflows
server/                 the MCP server, its tools, start.sh, and site_store.py (checked edits)
gui/                    the web GUI: app.py (server), index.html (page), start.sh
data/                   sites, vendors, vendor emails (rebuild: python data/generate_data.py)
docs/                   contracts and runbooks the AI searches
evals/                  test questions and the runner
tests/                  quick checks of the tools without the AI
outbox/  reports/  audit/   created as you use it
```
