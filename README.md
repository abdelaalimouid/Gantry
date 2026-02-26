# Gantry 3.0 — Autonomous Digital Twin Command Center

> **Elastic Agent Builder Hackathon 2026** — Predictive Industrial Maintenance powered by MCP Agent Swarm, Deep Reinforcement Learning, and Elasticsearch.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.x-005571.svg)](https://elastic.co)

---

## Overview

Gantry 3.0 monitors live engine telemetry streamed from Elasticsearch, detects imminent failures using a trained PPO Deep Reinforcement Learning policy, and deploys an autonomous 10-step MCP agent swarm to propose and execute a repair plan — all before a human operator would notice the problem.

```
Sensor Data → ES → WS Stream → Failure Detected → MCP Swarm (10 agents) → DRL Decision
     ↓                                                                           ↓
Dashboard                                                               Cost Comparison
     ↓                                                                           ↓
Operator Chat ←──────────────────── Agent Builder /converse ←───── Solution Proposal
     ↓
One-Click Resume → System Back to Green
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GANTRY 3.0                               │
│                                                                 │
│   ┌──────────────┐    WebSocket     ┌──────────────────────┐   │
│   │  React+Vite  │◄────────────────►│   FastAPI Backend    │   │
│   │  Frontend    │                  │   (api/main.py)      │   │
│   │              │   REST /api/*    │                      │   │
│   │  • Dashboard │◄────────────────►│  • WS telemetry loop │   │
│   │  • CriticalOverlay             │  • MCP orchestration │   │
│   │  • Agent Chat│                  │  • DRL inference     │   │
│   │  • CostPanel │                  │  • Chat proxy        │   │
│   └──────────────┘                  └──────────┬───────────┘   │
│                                                │               │
│        ┌───────────────────────────────────────┤               │
│        │               │               │       │               │
│        ▼               ▼               ▼       ▼               │
│   ┌─────────┐   ┌────────────┐  ┌──────────┐  ┌──────────┐   │
│   │Elastic  │   │  Elastic   │  │  DRL     │  │  Agent   │   │
│   │   ES    │   │  Kibana    │  │  Model   │  │ Builder  │   │
│   │(telemetry│  │(MCP tools) │  │(PPO/SB3) │  │/converse │   │
│   │personnel)│  │            │  │          │  │          │   │
│   └─────────┘   └────────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## MCP Agent Swarm — 10-Step Pipeline

When a failure is detected (RUL = 0), the backend fires a 10-step autonomous agent pipeline:

```
Step 1  │ Watchman Agent      │ Queries live telemetry via ES|QL
Step 2  │ Foreman Agent       │ Builds situational context
Step 3  │ Inventory Agent     │ Checks parts stock (MCP inventory_procurement)
Step 4  │ Procurement Agent   │ Evaluates express shipping approval
Step 5  │ Logistics Agent     │ Estimates delivery timeline
Step 6  │ Shadow Model Agent  │ Runs deterministic rule-based policy in parallel
Step 7  │ DRL Policy Agent    │ PPO model outputs repair/monitor decision
Step 8  │ Personnel Agent     │ Finds available technicians (MCP personnel_locator)
Step 9  │ Auditor Agent       │ Validates decision against cost thresholds
Step 10 │ Gantry AI           │ Synthesizes final solution with cost comparison
```

Each step is broadcast live over WebSocket to the `CriticalOverlay` UI, creating a real-time "reasoning log" visible to the operator.

---

## Deep Reinforcement Learning

The DRL policy (`models/gantry_policy_v1`) was trained using **Stable-Baselines3 PPO** on the **NASA C-MAPSS FD001** dataset (20,631 sensor records).

### Training Environment (`models/gantry_env.py`)

```
State space  : [rul_norm, vibration_norm, cost_norm, tech_available]  (4-dim)
Action space : {0: MONITOR, 1: APPROVE_EXPRESS_SHIPPING}              (discrete)
Reward       :  RUL > 50  → +1.0   (healthy, no action needed)
                RUL 20–50 → +0.5 if action=MONITOR   (conservative is fine)
                RUL < 20  → +1.5 if action=1, -2.0 if action=0  (must act)
                RUL = 0   → -5.0 regardless           (failure reached)
```

### Shadow Model — Explainability Layer

A deterministic rule-based policy (`RUL < 10 → ORDER`) runs in parallel with the DRL model. When the two policies disagree, the conflict is shown to the operator with both recommendations and the enterprise verdict — enabling genuine human-in-the-loop oversight.

### Maintenance Cost Comparison

| Strategy       | Cost / Event | Downtime |
|----------------|-------------|---------|
| Reactive       | $18,500      | 72 h    |
| Preventive     | $7,200       | 24 h    |
| **Predictive AI** | **$2,800** | **4 h** |
| **Savings**    | **$15,700**  | **68 h** |

---

## Project Structure

```
Gantry_Local/
│
├── api/
│   ├── main.py              # FastAPI backend — WS, MCP orchestration, DRL, chat
│   └── __init__.py
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Root — WS state, overlay trigger, orchestration
│   │   ├── components/
│   │   │   ├── CriticalOverlay.jsx  # Failure modal — agent steps, solution, cost panel
│   │   │   ├── TelemetryPanel.jsx   # RUL gauge, vibration gauge, status
│   │   │   ├── DigitalTwin.jsx      # SVG gantry crane animation
│   │   │   ├── ChatPanel.jsx        # Agent Builder /converse chat UI
│   │   │   ├── ReasoningLog.jsx     # MCP step timeline
│   │   │   ├── Header.jsx           # Nav, unit selector, orchestrate button
│   │   │   └── JudgingBanner.jsx    # Hackathon judging mode banner
│   │   └── hooks/
│   │       └── useWebSocket.js      # WS hook with auto-reconnect, event routing
│   ├── index.html
│   ├── vite.config.js       # Proxy: /api → :8000, /ws → ws://:8000
│   ├── tailwind.config.js
│   └── package.json
│
├── models/
│   ├── gantry_env.py        # Custom OpenAI Gym environment
│   └── __init__.py
│
├── services/
│   └── mcp_engine.py        # MCP tool wrappers
│
├── train_drl.py             # PPO training script (SB3)
├── data_ingestion.py        # Bulk-ingest NASA C-MAPSS → gantry_telemetry index
├── data_simulation.py       # Live simulation — streams rows to ES (pauses on halt)
├── trigger_failure.py       # Inject RUL=0 failure event for demos
├── agent.py                 # Standalone agent runner
├── webhook.py               # Agent Builder webhook helper
├── train_FD001.txt          # NASA C-MAPSS FD001 dataset
│
├── .env.example             # Environment variable template (copy → .env)
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

---

## Prerequisites

- Python 3.12+
- Node.js 18+
- An **Elastic Cloud** deployment (serverless or hosted) with:
  - Elasticsearch index access
  - Kibana / Agent Builder enabled
  - An Agent Builder agent created (ID → `ELASTIC_AGENT_ID`)

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/abdelaalimouid/Gantry.git
cd Gantry
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your Elastic Cloud credentials:

```dotenv
ELASTIC_KB_URL=https://YOUR-DEPLOYMENT.kb.REGION.gcp.elastic.cloud
ELASTIC_MCP_API_KEY=your_mcp_api_key_here
ELASTIC_CONVERSE_API_KEY=your_converse_api_key_here
ELASTIC_ES_URL=https://YOUR-DEPLOYMENT.es.REGION.gcp.elastic.cloud
ELASTIC_ES_API_KEY=your_es_api_key_here
ELASTIC_AGENT_ID=gantry_orchestrator
```

> **Where to find your API key:** Kibana → Stack Management → API Keys → Create API key. Grant `indices:data:read`, `indices:data:write` on `gantry_*`, and Kibana `all` permissions.

### 3. Install Python dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Ingest the NASA C-MAPSS dataset

```bash
python data_ingestion.py
```

This creates the `gantry_telemetry` index and ingests 20,631 sensor records with RUL labels derived from max-cycle normalization.

### 6. Seed personnel data

```bash
python seed_personnel.py
```

Creates the `gantry_personnel` index with 5 technician records used by the Personnel Locator agent.

### 7. Train the DRL model (optional — pre-trained model included)

```bash
python train_drl.py
```

Trains a PPO policy for ~50,000 steps on `GantryEnv`. Saves to `models/gantry_policy_v1`.

---

## Running the Application

You need **3 terminals** running simultaneously:

### Terminal 1 — FastAPI Backend

```bash
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 — React Frontend

```bash
cd frontend
npm run dev
```

The app will be available at **http://localhost:5174**

### Terminal 3 — Live Simulation

```bash
source .venv/bin/activate
python data_simulation.py
```

Streams live sensor rows to Elasticsearch every 5 seconds. Automatically pauses when a failure is active and resumes after the operator accepts the solution.

---

## Demo Walkthrough

### Simulating a Failure

In a 4th terminal, trigger an ENGINE-001 failure:

```bash
source .venv/bin/activate
python trigger_failure.py
```

This injects a `RUL=0` document directly into Elasticsearch and broadcasts a critical alert over all WebSocket connections.

### What happens next (automated)

1. **Dashboard freezes** — WS loop locks on failure values (RUL=0, vib=0.25)
2. **Downtime counter starts** — live timer appears on the `CriticalOverlay`
3. **10-step agent swarm fires** — each step appears live with agent name and event
4. **DRL policy runs** — PPO model outputs `APPROVE_EXPRESS_SHIPPING`
5. **Shadow model conflict check** — if rule-based policy disagrees, conflict is shown
6. **Cost comparison appears** — Reactive / Preventive / Predictive AI side-by-side
7. **Operator clicks "Accept & Resume System"** — backend clears halt flag, broadcasts `system_resumed`
8. **Dashboard returns to green** — 30-second grace window prevents stale-doc flicker

### Agent Chat

Type in the chat panel at any time:

| Query | Response |
|-------|----------|
| `status` | Current RUL, vibration, unit status from live telemetry |
| `cost` | Cost comparison between maintenance strategies |
| `crew` | Technician name, shift remaining, availability |
| `Override` | Human-in-the-loop flag — flips the DRL decision |
| `help` | Full command menu |

---

## Key Technical Details

### WebSocket Flow

```
ES (every 5s) → data_simulation.py → POST /{index}/_doc
                                          ↓
FastAPI WS loop → GET /{index}/_search (latest doc)
                → send_json(payload) to all connected clients
                                          ↓
              React useWebSocket hook → setLastMessage(data)
                                     → CriticalOverlay, TelemetryPanel
```

### Halt / Resume State Machine

```
trigger_failure.py
    ↓ POST /api/broadcast-alert
    ↓ _system_halted = True
    ↓ _failure_snapshot = {rul:0, vib:0.25, ...}

WS loop (while halted):
    → sends frozen snapshot every 2s (downtime counter ticks)

data_simulation.py:
    → polls GET /api/status → pauses loop while halted=True

POST /api/system-resume (Accept button):
    → _system_halted = False
    → _resume_grace_until = now + 30s
    → broadcasts system_resumed
    → WS loop sends synthetic HEALTHY payload for 30s
    → then hands off to real simulation data
```

### Chat Context Injection

The `/chat` endpoint injects live telemetry context into every Agent Builder `/converse` call:

```python
# Priority order:
# 1. _failure_snapshot  (system halted — use frozen failure values)
# 2. _last_live_telemetry  (healthy — use latest WS tick)
# 3. _last_decision  (fallback — last orchestration result)

context = f"Unit: {unit_id} | Status: {status} | RUL: {rul} cycles | ..."
enriched_message = f"CONTEXT: {context}\nUSER MESSAGE: {user_message}"
```

### Vite Proxy

The dev server proxies all backend calls to avoid CORS:

```javascript
// vite.config.js
proxy: {
  "/api": { target: "http://127.0.0.1:8000", rewrite: path => path.replace(/^\/api/, "") },
  "/ws":  { target: "ws://127.0.0.1:8000", ws: true }
}
```

> **Note:** Because `/api` is stripped, FastAPI routes must **not** include `/api` prefix (e.g. `@app.post("/system-resume")` not `@app.post("/api/system-resume")`).

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/api/status` | Halt state, downtime seconds |
| `GET` | `/units` | List available unit IDs |
| `GET` | `/orchestrate/{unit_id}` | Run full MCP orchestration |
| `POST` | `/api/broadcast-alert` | Inject failure alert (trigger_failure.py) |
| `POST` | `/system-resume` | Clear halt, start grace window |
| `POST` | `/chat` | Agent Builder chat proxy |
| `WS` | `/ws/telemetry/{unit_id}` | Live telemetry stream |

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `ELASTIC_KB_URL` | ✅ | Kibana base URL (`https://...elastic.cloud`) |
| `ELASTIC_MCP_API_KEY` | ✅ | API key for MCP tool calls |
| `ELASTIC_CONVERSE_API_KEY` | ✅ | API key for Agent Builder `/converse` |
| `ELASTIC_ES_URL` | ✅ | Elasticsearch base URL |
| `ELASTIC_ES_API_KEY` | ✅ | API key for telemetry read/write |
| `ELASTIC_AGENT_ID` | ✅ | Agent Builder agent ID (default: `gantry_orchestrator`) |

---

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `get_telemetry_status` | Fetch latest sensor readings for a unit |
| `inventory_procurement` | Check parts stock and request express shipping |
| `personnel_locator` | Find available technicians by shift |
| `platform_core_execute_esql` | Run arbitrary ES\|QL queries |
| `observability_get_alerts` | Check for active Elastic observability alerts |

---

## Requirements

```
fastapi
uvicorn[standard]
python-dotenv
httpx
elasticsearch
stable-baselines3
gymnasium
numpy
pandas
scikit-learn
```

See [requirements.txt](requirements.txt) for pinned versions.

---

## License

[MIT](LICENSE) © 2026 Abdelaali Mouid
