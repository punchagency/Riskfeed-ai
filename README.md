# RiskFeed Agentic Chatbot

This repo is the agentic chatbot service for RiskFeed.

RiskFeed = “risk intelligence” for U.S. residential construction projects. The chatbot is the part that **asks questions, calls tools, explains risk, and proposes next actions**.

> *This repo stays testable and replaceable.*

---

## What we are building (IN SCOPE)

We are building a **single Python service** that exposes an API and runs a LangGraph-powered agent loop.

- **LangGraph orchestration**
  - role/intent routing (homeowner vs contractor)
  - missing-info collection
  - planner → tool execution → verifier → repair loop → response composer
- **Tool registry (MCP-style)**
  - tools have clear schemas (Pydantic)
  - tools read/write **mock state only** (in-memory / JSON fixtures)
  - write tools are **idempotent** (no double execution)
- **Retrieval (RAG)**
  - offline-first **TF‑IDF** retrieval (local)
  - citations returned in responses
- **RBAC**
  - homeowner vs contractor permissions
  - tools enforce role access
- **Confirmation gates**
  - sensitive actions require an explicit “confirm” step
  - this includes anything like “release funds”, “approve milestone”, “send invite”, etc. (even if mocked)
- **Tests**
  - unit tests for tools + policies
  - “golden path” and adversarial tests for safety and consistency

---

## Project Goals

The chatbot should be:

- **Tool‑first (no hallucinated state)**
  - if it needs project/contractor data, it must call tools (or say it’s missing)
- **Explainable risk**
  - return **risk drivers**, **mitigations**, and **confidence/missing data**
- **Safe by default**
  - strict **RBAC**
  - **confirmation gates** for sensitive actions
- **Integration‑ready**
  - stable tool contracts (schemas)
  - clear API response shape the UI/backend can rely on later

---

## Tech Stack

- **Python**: 3.11+
- **API**: FastAPI + Uvicorn
- **Orchestration**: LangGraph
- **Schemas**: Pydantic v2
- **Tests**: pytest
- **Retrieval (offline)**: TF‑IDF (local, deterministic)

> *We can swap in a real LLM later.*

---

## Setup

### 1) Create and activate a virtual environment

Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

Once `requirements.txt` exists:

```bash
pip install -r requirements.txt
```

### 3) Run the API

Target command (once implemented):

```bash
uvicorn riskfeed.api.main:app --reload --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

---

## API usage

### `GET /health`

Response:

```json
{ "status": "ok" }
```

### `POST /chat`

This is the main endpoint. It must return a **stable response shape**.

#### Request

```json
{
  "role": "homeowner",
  "message": "I want to remodel my kitchen in Austin.",
  "session_id": "optional-string",
  "confirm_action_id": null,
  "debug": false
}
```

Notes:
- `role` is required and drives RBAC + routing.
- `session_id` lets us keep conversation state (mocked storage is fine).
- `confirm_action_id` is used to confirm a previously proposed sensitive action (see below).
- `debug` toggles extra info in the response (never required for normal operation).

#### Response

```json
{
  "message": "…assistant text…",
  "role": "homeowner",
  "checklist": [
    { "id": "define_scope", "label": "Define the project scope", "done": false }
  ],
  "missing_info": [
    { "field": "budget_usd", "question": "What is your target budget range?" }
  ],
  "actions": [
    {
      "id": "action_01",
      "type": "tool_call_proposed",
      "tool_name": "project.create_project_draft",
      "args": { "location": "Austin, TX", "project_type": "kitchen remodel" },
      "requires_confirmation": false,
      "confirm_action_id": null
    }
  ],
  "citations": [
    {
      "source_id": "doc_01#chunk_03",
      "title": "Permits overview",
      "snippet": "…short quoted text…",
      "uri": "local://docs/permits.md"
    }
  ],
  "debug": {
    "intent": "create_project",
    "tool_calls": [],
    "retrieval": { "hits": 0 }
  }
}
```

Field meanings:
- `message`: human-readable assistant output (what you’d show in UI).
- `role`: echoes the caller role.
- `checklist`: structured steps (good for UI checklists).
- `missing_info`: questions the agent still needs answered before it can proceed safely.
- `actions`: proposed next actions (tool calls), some may require confirmation.
- `citations`: retrieval grounding (may be empty).
- `debug`: optional diagnostics (present when `debug=true`; otherwise can be `{}` or omitted—pick one and stay consistent).

---

## Confirmation gates: `confirm_action_id` pattern

Sensitive actions must **never execute immediately**. Instead, the agent proposes them and returns a `confirm_action_id`.

Example action that requires confirmation:

```json
{
  "id": "action_release_01",
  "type": "tool_call_proposed",
  "tool_name": "payments.release_milestone_funds",
  "args": { "milestone_id": "ms_123" },
  "requires_confirmation": true,
  "confirm_action_id": "confirm_7f2a..."
}
```

To confirm, the client calls `/chat` again:

```json
{
  "role": "homeowner",
  "message": "Confirm.",
  "session_id": "same-session",
  "confirm_action_id": "confirm_7f2a...",
  "debug": false
}
```

Rules:
- A `confirm_action_id` must be **single-use** (idempotency + safety).
- RBAC applies: only the correct role can confirm.
- If confirmation is missing/invalid/expired → return a safe error message and no tool execution.

> *Note (why this matters): confirmation gates prevent accidental “money movement” logic (even mocked).*

---

## How to run tests

Once tests exist:

```bash
pytest
```

Recommended (later):
- `pytest -q` for quick runs
- `pytest -k rbac` to focus on safety tests

---

## Target folder structure (high level)

*This is the intended layout for the next commits:*

```
riskfeed/
  README.md
  requirements.txt

  api/
    __init__.py
    main.py              # FastAPI app (health + chat)
    schemas.py           # request/response models
    routes.py            # /chat route handler
    
  graph/
    __init__.py
    orchestrator.py      # LangGraph wiring
    nodes.py             # router, missing-info, planner, verifier, composer
    state.py             # conversation state helpers
  
  tools/
    __init__.py
    registry.py          # tool registry (name → handler)
    state_store.py       # mock in-memory/fixtures store
    project.py           # project.create_project_draft
    contractor.py        # contractor.list_contractors
    payment.py           # confirmation-gated tools

  auth/
    __init__.py
    rbac.py              # role permissions + enforcement helpers
    confirmation.py      # confirmation gate store + TTL

  retrieval/
    __init__.py
    tfidf.py             # local TF-IDF index + query
    types.py             # retrieval/citation types

  utils/
    __init__.py
    ids.py
    time.py
    redaction.py

  knowledge_base/
    .gitkeep

tests/
  test_health.py
  test_chat_shape.py
  test_rbac.py
  test_confirmations.py
  test_tools.py
```

> *Note (why this matters): a consistent structure makes it easier to find code and keeps tests close to the safety features we care about.*
