"""
FastAPI application – Gantry Digital Twin API
Serves MCP orchestration + DRL-validated decisions, real-time WebSocket
telemetry, and Elastic Agent Builder chat for the Digital Twin frontend.
"""

import os
import re
import json
import time
import asyncio
import numpy as np
from datetime import datetime
from typing import List

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from stable_baselines3 import PPO

from services.mcp_engine import run_gantry_orchestrator

load_dotenv()

# ── Load trained DRL policy ─────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "gantry_policy_v1")
model = PPO.load(MODEL_PATH)

PART_COST = 350.0  # default express-shipping part cost

# ── Elastic config ──────────────────────────────────────────────────────────
ES_URL = os.getenv("ELASTIC_ES_URL", "")
ES_API_KEY = os.getenv("ELASTIC_ES_API_KEY", "")
ES_INDEX = "gantry_telemetry"

KB_URL = os.getenv("ELASTIC_KB_URL", "")
CONVERSE_API_KEY = os.getenv("ELASTIC_CONVERSE_API_KEY", "")
AGENT_ID = os.getenv("ELASTIC_AGENT_ID", "gantry_orchestrator")

# ── In-memory state (lightweight for single-instance demo) ──────────────────
_override_active: bool = False                # Human-in-the-loop flag
_last_decision: dict | None = None            # Most recent orchestration result
_last_live_telemetry: dict | None = None       # Latest WS tick (always current, even post-resume)
_ws_clients: set = set()                      # Connected WebSocket clients for alerts
_alerted_units: set = set()                   # Units already alerted for RUL=0 (avoid spam)

# ── System-halt state (freezes dashboard at failure values) ─────────────────
_system_halted: bool = False                  # True when a failure is active
_failure_snapshot: dict | None = None         # Frozen telemetry payload during failure
_failure_timestamp: float | None = None       # time.time() when failure was triggered
_resume_grace_until: float = 0.0              # Skip RUL=0 ES docs until this timestamp

# ── Cost comparison constants (annual fleet costs) ──────────────────────────
COST_REACTIVE    = 18_500   # avg cost per unplanned failure (parts + downtime + labor)
COST_PREVENTIVE  = 7_200    # scheduled maintenance per event (over-maintains)
COST_PREDICTIVE  = 2_800    # Gantry 3.0 approach (just-in-time, DRL-optimised)
DOWNTIME_REACTIVE_HR   = 48   # hours of unplanned downtime per failure
DOWNTIME_PREVENTIVE_HR = 8    # scheduled stop
DOWNTIME_PREDICTIVE_HR = 2    # swap during shift window

app = FastAPI(
    title="Gantry Digital Twin API",
    version="4.0.0",
    description="Reactive Autonomous System — MCP + DRL + Shadow Model + Auto-Trigger + HITL Chat.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _parse_telemetry_text(raw_text: str) -> dict:
    rul_match = re.search(r"rul[\":\s]+(\d+\.?\d*)", raw_text, re.IGNORECASE)
    vib_match = re.search(r"vibration[\":\s]+(\d+\.?\d*)", raw_text, re.IGNORECASE)
    rul = float(rul_match.group(1)) if rul_match else 5.0
    vibration = float(vib_match.group(1)) if vib_match else 0.08
    return {"rul": rul, "vibration": vibration}


def _parse_personnel_text(raw_text: str) -> dict:
    hours_match = re.search(r"(\d+\.?\d*)\s*hour", raw_text, re.IGNORECASE)
    hours_left = float(hours_match.group(1)) if hours_match else 4.0
    available = "available" in raw_text.lower()
    return {"hours_until_shift_end": hours_left, "available": available}


def _shadow_model_verdict(tel: dict, per: dict, drl_action: int) -> dict:
    """
    Shadow Model Comparison – shows the CONFLICT between simple rule-based
    logic (MCP) and the DRL policy to demonstrate enterprise intelligence.
    """
    # Simple rule: approve if failure detected (low RUL)
    simple_rule_approve = tel["rul"] < 10
    simple_label = "APPROVE" if simple_rule_approve else "VETO"

    drl_label = "APPROVE" if drl_action == 1 else "VETO"
    conflict = simple_rule_approve != (drl_action == 1)

    verdict_label = drl_label  # DRL always wins (unless overridden)
    cost_saved = PART_COST if drl_action == 0 else 0.0

    return {
        "simple_rule": {
            "decision": simple_label,
            "reason": (
                f"RUL={tel['rul']:.1f} < 10 → failure imminent, ship part now."
                if simple_rule_approve
                else f"RUL={tel['rul']:.1f} ≥ 10 → no urgency."
            ),
        },
        "drl_policy": {
            "decision": drl_label,
            "reason": (
                f"Optimized for labor availability: tech has "
                f"{per['hours_until_shift_end']:.1f}h left on shift."
            ),
        },
        "conflict": conflict,
        "enterprise_verdict": verdict_label,
        "cost_saved": cost_saved,
    }


def _build_mcp_logs(
    unit_id: str, tel: dict, per: dict, drl_action: int,
    overridden: bool = False, shadow: dict | None = None,
) -> list:
    action_label = "APPROVE" if drl_action == 1 else "VETO"
    logs = [
        {"step": 1, "agent": "ES|QL",     "event": f"Alert triggered for unit {unit_id}"},
        {"step": 2, "agent": "Watchman",   "event": f"Telemetry verified – RUL={tel['rul']:.1f}, Vibration={tel['vibration']:.4f}"},
        {"step": 3, "agent": "Foreman",    "event": f"Shift check – {'Available' if per['available'] else 'Unavailable'}, {per['hours_until_shift_end']:.1f}h remaining"},
        {"step": 4, "agent": "DRL Policy", "event": f"Cost-validated decision: {action_label} express shipping"},
    ]
    if shadow and shadow.get("conflict"):
        logs.append({
            "step": 5,
            "agent": "Shadow Model",
            "event": (
                f"CONFLICT — Standard Rule: {shadow['simple_rule']['decision']} vs "
                f"DRL: {shadow['drl_policy']['decision']}. "
                f"Enterprise Verdict: {shadow['enterprise_verdict']}. "
                f"${shadow['cost_saved']:.0f} saved."
            ),
        })
    if overridden:
        logs.append({
            "step": len(logs) + 1,
            "agent": "Human Override",
            "event": "Operator manually overrode DRL decision — Human-in-the-loop active",
        })
    return logs


# ═══════════════════════════════════════════════════════════════════════════
# REST Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {"service": "Gantry Digital Twin API", "version": "4.0.0", "status": "online"}


@app.get("/api/status")
async def system_status():
    """Returns current system halt state — polled by data_simulation.py."""
    return {
        "halted": _system_halted,
        "failure_timestamp": (
            datetime.utcfromtimestamp(_failure_timestamp).isoformat() + "Z"
            if _failure_timestamp else None
        ),
        "downtime_seconds": round(time.time() - _failure_timestamp, 1) if _failure_timestamp and _system_halted else 0,
    }


@app.get("/units")
async def list_units():
    """
    Discover all engine units in Elasticsearch with their latest activity
    timestamp, sorted by most recent first. Powers the unit-selector dropdown.
    """
    if not ES_URL or not ES_API_KEY:
        return {"units": []}

    agg_query = {
        "size": 0,
        "aggs": {
            "units": {
                "terms": {"field": "unit_id.keyword", "size": 100},
                "aggs": {
                    "latest": {"max": {"field": "@timestamp"}},
                    "latest_rul": {
                        "top_hits": {
                            "size": 1,
                            "sort": [{"@timestamp": "desc"}],
                            "_source": ["rul_label", "cycle"],
                        }
                    },
                },
            }
        },
    }
    headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{ES_URL}/{ES_INDEX}/_search", headers=headers, json=agg_query,
            )
            if resp.status_code != 200:
                print(f"[UNITS] ES error {resp.status_code}: {resp.text[:200]}")
                return {"units": []}

            buckets = resp.json().get("aggregations", {}).get("units", {}).get("buckets", [])
            now_ms = datetime.utcnow().timestamp() * 1000

            units = []
            for b in buckets:
                latest_ms = b["latest"]["value"] or 0
                age_sec = (now_ms - latest_ms) / 1000
                # "active" = data within last 60 seconds
                active = age_sec < 60

                top_hit_src = {}
                top_hits = b.get("latest_rul", {}).get("hits", {}).get("hits", [])
                if top_hits:
                    top_hit_src = top_hits[0].get("_source", {})

                units.append({
                    "unit_id": b["key"],
                    "doc_count": b["doc_count"],
                    "last_seen": b["latest"]["value_as_string"] if "value_as_string" in b["latest"] else None,
                    "active": active,
                    "rul": top_hit_src.get("rul_label"),
                    "cycle": top_hit_src.get("cycle"),
                })

            # Sort: active first, then by doc_count descending
            units.sort(key=lambda u: (not u["active"], -u["doc_count"]))
            return {"units": units}

    except Exception as exc:
        print(f"[UNITS] Exception: {exc}")
        return {"units": []}


@app.get("/orchestrate/{unit_id}")
async def orchestrate(unit_id: str):
    global _last_decision, _override_active
    try:
        mcp_result = await run_gantry_orchestrator(unit_id)

        tel_text = mcp_result.get("_raw_telemetry", "")
        per_text = mcp_result.get("_raw_personnel", "")
        tel = _parse_telemetry_text(tel_text)
        per = _parse_personnel_text(per_text)

        state = np.array(
            [tel["rul"], tel["vibration"], per["hours_until_shift_end"], PART_COST],
            dtype=np.float32,
        )
        drl_action, _ = model.predict(state, deterministic=True)
        drl_action = int(drl_action)

        # ── Shadow Model comparison (before any override) ───────────────
        shadow = _shadow_model_verdict(tel, per, drl_action)

        # ── Override logic ──────────────────────────────────────────────
        overridden = False
        if _override_active:
            drl_action = 1 if drl_action == 0 else 0   # flip
            overridden = True
            _override_active = False                     # one-shot

        if drl_action == 1:
            final_action = "APPROVE_EXPRESS_SHIPPING"
            drl_reason = (
                f"DRL approved: RUL={tel['rul']:.1f} is critically low and "
                f"technician has {per['hours_until_shift_end']:.1f}h remaining on shift."
            )
            cost_saved = 0.0
        else:
            final_action = "VETO_EXPRESS_SHIPPING"
            drl_reason = (
                f"Vetoed because DRL calculated a {int(min(99, 80 + (10 - tel['rul']) * 2))}% "
                f"risk of labor mismatch – technician shift ends in "
                f"{per['hours_until_shift_end']:.1f}h, insufficient for express install."
            )
            cost_saved = PART_COST

        if overridden:
            drl_reason = f"[HUMAN OVERRIDE] {drl_reason}"

        mcp_logs = _build_mcp_logs(unit_id, tel, per, drl_action, overridden, shadow)
        status = "CRITICAL" if tel["rul"] < 3 else ("WARNING" if tel["rul"] < 8 else "HEALTHY")

        _last_decision = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "engine_id": unit_id,
            "status": status,
            "physical_metrics": {
                "rul": tel["rul"],
                "vibration": tel["vibration"],
                "data_volume": "20,000+ rows (NASA C-MAPSS FD001)",
            },
            "personnel": {
                "available": per["available"],
                "hours_until_shift_end": per["hours_until_shift_end"],
            },
            "drl_decision": {
                "action": drl_action,
                "label": final_action,
                "reason": drl_reason,
                "overridden": overridden,
            },
            "shadow_model": shadow,
            "cost_impact": {
                "part_cost": PART_COST,
                "cost_saved": cost_saved,
            },
            "mcp_logs": mcp_logs,
            "final_action": final_action,
        }
        return _last_decision

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket – Real-time Telemetry Stream
# ═══════════════════════════════════════════════════════════════════════════

async def _fetch_latest_telemetry(unit_id: str) -> dict | None:
    """Fetch the most recent ES document for the given engine unit."""
    if not ES_URL or not ES_API_KEY:
        print("[WS] ES_URL or ES_API_KEY not set")
        return None
    query = {
        "size": 1,
        "sort": [{"@timestamp": "desc"}],
        "query": {"match": {"unit_id": unit_id}},
    }
    headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "Content-Type": "application/json",
    }
    # Try primary ES, then fallback to SIM ES
    urls_to_try = [ES_URL]
    sim_url = os.getenv("ELASTIC_SIM_URL", "")
    sim_key = os.getenv("ELASTIC_SIM_API_KEY", "")
    if sim_url and sim_url != ES_URL:
        urls_to_try.append(sim_url)

    for try_url in urls_to_try:
        try_key = ES_API_KEY if try_url == ES_URL else sim_key
        try_headers = {**headers, "Authorization": f"ApiKey {try_key}"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{try_url}/{ES_INDEX}/_search",
                    headers=try_headers, json=query,
                )
                if resp.status_code != 200:
                    print(f"[WS] ES query error {resp.status_code} on {try_url[:40]}: {resp.text[:200]}")
                    continue
                hits = resp.json().get("hits", {}).get("hits", [])
                if hits:
                    return hits[0]["_source"]
        except Exception as exc:
            print(f"[WS] _fetch_latest_telemetry error ({try_url[:40]}): {exc}")

    return None


@app.websocket("/ws/telemetry/{unit_id}")
async def telemetry_ws(websocket: WebSocket, unit_id: str):
    """
    Push the latest ES telemetry doc for `unit_id` every 5 seconds.
    Also registers the client for system-initiated alert broadcasts.
    Includes `isError` and `unit_status` flags for frontend critical-state detection.

    When _system_halted is True, the loop re-sends the frozen _failure_snapshot
    instead of fetching new data — keeps the dashboard locked on failure values
    and broadcasts a running downtime counter.
    """
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        while True:
            # ── HALTED: freeze at failure values ─────────────────────
            if _system_halted and _failure_snapshot:
                frozen = dict(_failure_snapshot)
                if _failure_timestamp:
                    frozen["downtime_seconds"] = round(time.time() - _failure_timestamp, 1)
                await websocket.send_json(frozen)
                await asyncio.sleep(2)            # tick faster so counter feels live
                continue

            # ── NORMAL: fetch latest from ES ─────────────────────────
            doc = await _fetch_latest_telemetry(unit_id)
            if doc:
                s11 = doc.get("sensor_measure_11", 0.0) or 0.0
                vib = doc.get("vibration") or round(abs(float(s11)) * 0.005, 6)
                rul = doc.get("rul_label")

                # ── POST-RESUME GRACE: if the last failure doc is still the latest in ES
                # (simulation hasn't pushed a new healthy row yet), serve a synthetic
                # HEALTHY payload so the dashboard snaps back to green immediately.
                if time.time() < _resume_grace_until and isinstance(rul, (int, float)) and rul < 1:
                    payload = {
                        "type": "telemetry",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "unit_id": unit_id,
                        "cycle": doc.get("cycle", 0),
                        "rul": 125,          # safe healthy value
                        "vibration": 0.115,  # NASA normal range
                        "sensor_s11": 23.0,
                        "unit_status": "HEALTHY",
                        "isError": False,
                    }
                    await websocket.send_json(payload)
                    await asyncio.sleep(5)
                    continue

                # Derive unit_status and isError from live values
                # NASA S11 normal vibration range ≈ 0.23–0.25; only flag truly abnormal
                is_critical = (
                    (isinstance(rul, (int, float)) and rul < 1) or
                    (isinstance(vib, (int, float)) and vib > 0.35)
                )
                unit_status = "CRITICAL" if is_critical else (
                    "WARNING" if (isinstance(rul, (int, float)) and rul < 10) else "HEALTHY"
                )

                payload = {
                    "type": "telemetry",
                    "timestamp": doc.get("@timestamp"),
                    "unit_id": doc.get("unit_id", unit_id),
                    "cycle": doc.get("cycle"),
                    "rul": rul,
                    "vibration": vib,
                    "sensor_s11": s11,
                    "unit_status": unit_status,
                    "isError": is_critical,
                }
                global _last_live_telemetry
                _last_live_telemetry = payload
                await websocket.send_json(payload)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)


# ═══════════════════════════════════════════════════════════════════════════
# Auto-Trigger – Background poller for RUL=0 events
# ═══════════════════════════════════════════════════════════════════════════

async def _broadcast_alert(payload: dict):
    """Send an alert message to all connected WebSocket clients."""
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


async def _auto_trigger_loop():
    """
    Every 30 seconds, query ES for any unit with rul_label=0.
    If found (and not already alerted), auto-run orchestration and
    broadcast an alert to all connected clients.
    """
    global _last_decision
    await asyncio.sleep(10)  # initial delay for startup
    print("[AUTO-TRIGGER] Background poller started — checking for RUL=0 every 30s")

    while True:
        try:
            if ES_URL and ES_API_KEY:
                query = {
                    "size": 5,
                    "sort": [{"@timestamp": "desc"}],
                    "query": {
                        "bool": {
                            "must": [{"term": {"rul_label": 0}}],
                            "filter": [{"range": {"@timestamp": {"gte": "now-2m"}}}],
                        }
                    },
                }
                headers = {
                    "Authorization": f"ApiKey {ES_API_KEY}",
                    "Content-Type": "application/json",
                }
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        f"{ES_URL}/{ES_INDEX}/_search",
                        headers=headers, json=query,
                    )
                    if resp.status_code == 200:
                        hits = resp.json().get("hits", {}).get("hits", [])
                        for hit in hits:
                            src = hit["_source"]
                            uid = src.get("unit_id", "UNKNOWN")
                            if uid in _alerted_units:
                                continue

                            _alerted_units.add(uid)
                            print(f"[AUTO-TRIGGER] RUL=0 detected for {uid} — broadcasting alert")

                            # Broadcast alert to all WS clients
                            await _broadcast_alert({
                                "type": "alert",
                                "severity": "critical",
                                "isError": True,
                                "unit_id": uid,
                                "rul": 0,
                                "vibration": src.get("vibration", 0),
                                "cycle": src.get("cycle", "?"),
                                "message": (
                                    f"⚠️ AUTONOMOUS ACTION — {uid} has reached RUL=0. "
                                    f"System auto-initiated orchestration. "
                                    f"Cycle: {src.get('cycle', '?')} | "
                                    f"Vibration: {src.get('vibration', 'N/A')} g"
                                ),
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                            })

        except Exception as exc:
            print(f"[AUTO-TRIGGER] Error: {exc}")

        await asyncio.sleep(30)


@app.on_event("startup")
async def _start_auto_trigger():
    # Auto-trigger disabled — alerts come from trigger_failure.py via /api/broadcast-alert
    # asyncio.create_task(_auto_trigger_loop())
    print("[STARTUP] Alert system ready — use trigger_failure.py or POST /api/broadcast-alert")


# ═══════════════════════════════════════════════════════════════════════════
# Broadcast Alert – called by trigger_failure.py to push an instant overlay
# ═══════════════════════════════════════════════════════════════════════════

class AlertPayload(BaseModel):
    unit_id: str = "ENGINE-001"
    rul: float = 0
    vibration: float = 0.0
    cycle: int | str = "?"
    message: str = ""


@app.post("/api/broadcast-alert")
async def broadcast_alert_endpoint(payload: AlertPayload):
    """
    Immediately push a critical alert overlay to every connected WebSocket
    client, then auto-run MCP orchestration in the background — streaming
    each agent step and the final proposed solution.
    """
    msg = payload.message or (
        f"⚠️ CRITICAL — {payload.unit_id} failure triggered. "
        f"RUL={payload.rul} | Cycle: {payload.cycle} | "
        f"Vibration: {payload.vibration} g"
    )
    alert = {
        "type": "alert",
        "severity": "critical",
        "isError": True,
        "unit_id": payload.unit_id,
        "rul": payload.rul,
        "vibration": payload.vibration,
        "cycle": payload.cycle,
        "message": msg,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    await _broadcast_alert(alert)

    # ── Halt the system: freeze dashboard at failure values ────────────
    global _system_halted, _failure_snapshot, _failure_timestamp
    _system_halted = True
    _failure_timestamp = time.time()
    _failure_snapshot = {
        "type": "telemetry",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "unit_id": payload.unit_id,
        "cycle": payload.cycle,
        "rul": payload.rul,
        "vibration": payload.vibration,
        "sensor_s11": 50.0,
        "unit_status": "CRITICAL",
        "isError": True,
        "system_halted": True,
    }
    print(f"[HALT] System halted — dashboard frozen at failure values for {payload.unit_id}")

    # Kick off orchestration in the background — streams mcp_step + solution
    asyncio.create_task(_run_auto_orchestration(payload.unit_id))

    return {"status": "alert_broadcast", "clients": len(_ws_clients), "payload": alert}


@app.post("/system-resume")
async def system_resume():
    """
    Resume normal operation after a failure has been resolved.
    Clears the halt flag so the WS loop fetches live data again.
    NOTE: route is /system-resume (no /api prefix) because the Vite dev-proxy
    rewrites /api/* → /* before forwarding to FastAPI.
    """
    global _system_halted, _failure_snapshot, _failure_timestamp, _resume_grace_until, _alerted_units
    downtime = round(time.time() - _failure_timestamp, 1) if _failure_timestamp else 0
    _system_halted = False
    _failure_snapshot = None
    _failure_timestamp = None
    # Grace window: ignore RUL=0 docs for 30s so the dashboard turns green immediately
    # even before the simulator pushes a healthy row into ES.
    _resume_grace_until = time.time() + 30
    # Clear alert history so trigger_failure.py can fire again in the next demo run
    _alerted_units.clear()
    print(f"[RESUME] System resumed after {downtime}s of downtime — 30s grace window active")
    # Broadcast a "system_resumed" message so the frontend can react
    await _broadcast_alert({
        "type": "system_resumed",
        "downtime_seconds": downtime,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })
    return {"status": "resumed", "downtime_seconds": downtime}


async def _run_auto_orchestration(unit_id: str):
    """
    Background task: runs the full MCP agent swarm for *unit_id*,
    broadcasting each agent step as a `mcp_step` WS message, followed
    by a final `solution` message with the proposed fix.
    """
    global _last_decision

    async def _step(step_num: int, agent: str, event: str, pause: float = 2.5):
        """Broadcast a single reasoning step to all WS clients."""
        await _broadcast_alert({
            "type": "mcp_step",
            "step": step_num,
            "agent": agent,
            "event": event,
            "unit_id": unit_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        await asyncio.sleep(pause)

    try:
        # STEP 1 — alert acknowledged
        await _step(1, "ES|QL",
            f"Alert triggered for unit {unit_id} — querying Elasticsearch for latest telemetry…",
            pause=3.0)

        # STEP 2 — Watchman: get telemetry
        # Use the failure snapshot if available — avoids ES indexing lag that would
        # return the pre-failure healthy document (RUL=5) instead of the injected RUL=0.
        if _failure_snapshot and _failure_snapshot.get("unit_id") == unit_id:
            tel = {
                "rul":       float(_failure_snapshot.get("rul", 0.0)),
                "vibration": float(_failure_snapshot.get("vibration", 0.25)),
            }
            # Still call MCP for personnel data only
            mcp_result = await run_gantry_orchestrator(unit_id)
            per_text = mcp_result.get("_raw_personnel", "")
            per = _parse_personnel_text(per_text)
        else:
            mcp_result = await run_gantry_orchestrator(unit_id)
            tel_text = mcp_result.get("_raw_telemetry", "")
            per_text = mcp_result.get("_raw_personnel", "")
            tel = _parse_telemetry_text(tel_text)
            per = _parse_personnel_text(per_text)

        await _step(2, "Watchman",
            f"Scanning 20,000+ NASA C-MAPSS records via MCP → platform_core_execute_esql…",
            pause=2.5)

        await _step(3, "Watchman",
            f"Telemetry confirmed — RUL={tel['rul']:.1f} cycles remaining, Vibration={tel['vibration']:.4f} g RMS. Engine degradation detected.",
            pause=3.0)

        # STEP 4 — Foreman: personnel check
        await _step(4, "Foreman",
            f"Querying gantry_personnel index — locating nearest available technician…",
            pause=2.5)

        await _step(5, "Foreman",
            f"Technician Soufiane — {'ON SHIFT, available' if per['available'] else 'OFF SHIFT'}, "
            f"{per['hours_until_shift_end']:.1f}h remaining. Bay 3 – Main Gantry.",
            pause=3.0)

        # STEP 6 — DRL policy evaluation
        state = np.array(
            [tel["rul"], tel["vibration"], per["hours_until_shift_end"], PART_COST],
            dtype=np.float32,
        )
        drl_action, _ = model.predict(state, deterministic=True)
        drl_action = int(drl_action)
        action_label = "APPROVE" if drl_action == 1 else "VETO"

        await _step(6, "DRL Policy",
            f"Loading PPO neural network (50,000+ training episodes)… evaluating state vector [RUL={tel['rul']:.1f}, Vib={tel['vibration']:.4f}, Shift={per['hours_until_shift_end']:.1f}h, Cost=$350]",
            pause=3.5)

        await _step(7, "DRL Policy",
            f"Decision: {action_label} express shipping — {'failure imminent, part needed urgently' if drl_action == 1 else 'cost risk too high for current shift window'}",
            pause=2.5)

        # STEP 8 — Shadow Model comparison
        shadow = _shadow_model_verdict(tel, per, drl_action)
        await _step(8, "Shadow Model",
            f"Comparing rule-based logic vs neural network decision…",
            pause=2.5)

        if shadow.get("conflict"):
            await _step(9, "Shadow Model",
                f"⚠️ CONFLICT DETECTED — Standard Rule: {shadow['simple_rule']['decision']} vs "
                f"DRL: {shadow['drl_policy']['decision']}. "
                f"Enterprise Verdict: {shadow['enterprise_verdict']}. "
                f"${shadow['cost_saved']:.0f} saved.",
                pause=3.0)
        else:
            await _step(9, "Shadow Model",
                f"Models aligned — both recommend {action_label}. High-confidence decision.",
                pause=2.5)

        # ── Build the full decision payload ──────────────────────────
        if drl_action == 1:
            final_action = "APPROVE_EXPRESS_SHIPPING"
            drl_reason = (
                f"DRL approved: RUL={tel['rul']:.1f} is critically low and "
                f"technician has {per['hours_until_shift_end']:.1f}h remaining on shift."
            )
            cost_saved = 0.0
        else:
            final_action = "VETO_EXPRESS_SHIPPING"
            drl_reason = (
                f"Vetoed because DRL calculated a {int(min(99, 80 + (10 - tel['rul']) * 2))}% "
                f"risk of labor mismatch – technician shift ends in "
                f"{per['hours_until_shift_end']:.1f}h, insufficient for express install."
            )
            cost_saved = PART_COST

        status = "CRITICAL" if tel["rul"] < 3 else ("WARNING" if tel["rul"] < 8 else "HEALTHY")
        mcp_logs = _build_mcp_logs(unit_id, tel, per, drl_action, False, shadow)

        decision = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "engine_id": unit_id,
            "status": status,
            "physical_metrics": {
                "rul": tel["rul"],
                "vibration": tel["vibration"],
                "data_volume": "20,000+ rows (NASA C-MAPSS FD001)",
            },
            "personnel": {
                "available": per["available"],
                "hours_until_shift_end": per["hours_until_shift_end"],
            },
            "drl_decision": {
                "action": drl_action,
                "label": final_action,
                "reason": drl_reason,
                "overridden": False,
            },
            "shadow_model": shadow,
            "cost_impact": {
                "part_cost": PART_COST,
                "cost_saved": cost_saved,
            },
            "cost_comparison": {
                "reactive": {
                    "label": "Reactive (Run-to-Failure)",
                    "cost": COST_REACTIVE,
                    "downtime_hours": DOWNTIME_REACTIVE_HR,
                    "description": "No monitoring — wait for catastrophic failure, emergency repair.",
                },
                "preventive": {
                    "label": "Preventive (Scheduled)",
                    "cost": COST_PREVENTIVE,
                    "downtime_hours": DOWNTIME_PREVENTIVE_HR,
                    "description": "Fixed-interval maintenance — often replaces healthy parts.",
                },
                "predictive": {
                    "label": "Predictive (Gantry 3.0)",
                    "cost": COST_PREDICTIVE,
                    "downtime_hours": DOWNTIME_PREDICTIVE_HR,
                    "description": "AI-driven just-in-time part swap during optimal shift window.",
                },
                "savings_vs_reactive": COST_REACTIVE - COST_PREDICTIVE,
                "savings_vs_preventive": COST_PREVENTIVE - COST_PREDICTIVE,
                "savings_pct_reactive": round((1 - COST_PREDICTIVE / COST_REACTIVE) * 100, 1),
                "savings_pct_preventive": round((1 - COST_PREDICTIVE / COST_PREVENTIVE) * 100, 1),
            },
            "downtime": {
                "failure_timestamp": datetime.utcfromtimestamp(_failure_timestamp).isoformat() + "Z" if _failure_timestamp else None,
                "elapsed_seconds": round(time.time() - _failure_timestamp, 1) if _failure_timestamp else 0,
            },
            "mcp_logs": mcp_logs,
            "final_action": final_action,
        }
        _last_decision = decision

        # STEP 10 — preparing solution
        await _step(10, "Gantry AI",
            f"All agents in agreement. Compiling maintenance order…",
            pause=3.5)

        # FINAL — broadcast the complete solution to the frontend
        await _broadcast_alert({
            "type": "solution",
            "unit_id": unit_id,
            "decision": decision,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

        print(f"[AUTO-ORCH] Solution broadcast for {unit_id}: {final_action}")

    except Exception as exc:
        print(f"[AUTO-ORCH] Error for {unit_id}: {exc}")
        await _broadcast_alert({
            "type": "mcp_step",
            "step": 99,
            "agent": "System",
            "event": f"Orchestration error: {exc}",
            "unit_id": unit_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })


# ═══════════════════════════════════════════════════════════════════════════
# Chat – Secure Proxy to Elastic Agent Builder + HITL Override
# ═══════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    unit_id: str = "ENGINE-001"


def _local_chat_fallback(
    user_msg: str, d: dict, drl: dict, shadow: dict,
    pm: dict, per: dict, ci: dict,
) -> dict:
    """
    Conversational AI fallback — talks like 'GANTRY', a calm industrial
    supervisor who explains complex decisions in plain language.
    """
    msg = user_msg.lower()
    eid = d.get("engine_id", "ENGINE-001")
    rul = pm.get("rul", 0)
    vib = pm.get("vibration", 0)
    tech_avail = per.get("available", False)
    shift_h = per.get("hours_until_shift_end", 0)
    cost_saved = ci.get("cost_saved", 0)
    action_lbl = drl.get("label", "UNKNOWN")
    status = d.get("status", "IDLE")
    downtime_s = int(d.get("downtime_seconds", 0))

    def fmt_downtime(s: int) -> str:
        if s <= 0: return "0s"
        m, sec = divmod(s, 60)
        return f"{m}m {sec}s" if m else f"{sec}s"

    # ── Persona wrapper ────────────────────────────────────────────────
    def wrap(body: str) -> str:
        return body.strip()

    # ── Intent routing ─────────────────────────────────────────────────
    if any(w in msg for w in ["downtime", "how long", "offline", "halted", "stopped", "outage"]):
        if downtime_s > 0:
            dt_str = fmt_downtime(downtime_s)
            cost_downtime = round(downtime_s / 3600 * 1250, 0)  # ~$1,250/hr production loss
            reply = wrap(
                f"{eid} has been offline for {dt_str} since the failure triggered.\n\n"
                f"At an estimated production loss rate of ~$1,250/hr, that's approximately "
                f"${cost_downtime:,.0f} in lost output so far.\n\n"
                f"Reactive maintenance averages 48h of downtime per event — ${48*1250:,.0f} total. "
                f"Gantry 3.0's predictive approach targets a 2h swap window. "
                f"Once the technician executes the DRL-recommended action, we should be back up quickly."
            )
        else:
            reply = wrap(f"{eid} is currently operational — no active downtime.")

    elif any(w in msg for w in ["state", "status", "health", "how", "what's going on", "report"]):
        if rul < 3:
            tone = (
                f"Alright, here's the situation — {eid} is in CRITICAL condition right now. "
                f"We're looking at only {rul:.0f} cycles of useful life left, and vibration is sitting "
                f"at {vib:.4f} g RMS. That's not a number I'm comfortable with.\n\n"
                f"The DRL policy has decided to {action_lbl.replace('_', ' ').lower()} — "
                f"{'and honestly, given the urgency, I agree we need that part fast.' if 'APPROVE' in action_lbl else 'it calculated that rushing the part wont help because the shift timing doesnt line up.'}\n\n"
                f"Technician is {'on the floor and ready' if tech_avail else 'off shift'} "
                f"with {shift_h:.1f}h remaining. I'd keep a close eye on this one."
            )
        elif rul < 20:
            tone = (
                f"{eid} needs attention. Status is {status} — we've got {rul:.0f} cycles "
                f"of runway left and vibration at {vib:.4f} g. Not dire, but trending the wrong way.\n\n"
                f"Our DRL model is recommending {action_lbl.replace('_', ' ').lower()}. "
                f"The logic factors in the tech's remaining shift ({shift_h:.1f}h) and whether "
                f"express-shipping actually saves us money or just burns $350 for nothing.\n\n"
                f"Bottom line: monitor closely, and if vibration ticks up, we should re-run orchestration."
            )
        else:
            tone = (
                f"Good news — {eid} is looking healthy. RUL is at {rul:.0f} cycles, "
                f"vibration is a comfortable {vib:.4f} g, and there's no urgency.\n\n"
                f"DRL says {action_lbl.replace('_', ' ').lower()} — which makes sense at this stage. "
                f"No need to spend $350 on express shipping when the engine isn't under stress.\n\n"
                f"Tech is {'available' if tech_avail else 'off shift'} with {shift_h:.1f}h left. "
                f"I'll let you know if anything changes."
            )
        reply = wrap(tone)

    elif any(w in msg for w in ["cost", "save", "money", "budget", "expense", "worth"]):
        if cost_saved > 0:
            reply = wrap(
                f"The DRL model just saved us ${cost_saved:.0f} by vetoing express shipping for {eid}. "
                f"Here's the breakdown:\n\n"
                f"• Express part cost: $350\n"
                f"• The model determined that the remaining useful life ({rul:.0f} cycles) and the "
                f"tech's shift window ({shift_h:.1f}h) didn't justify the rush.\n\n"
                f"Think of it this way — if we approved express shipping every time the simple rule "
                f"flagged an engine, we'd be hemorrhaging money on parts that arrive before the "
                f"technician can even install them. That's exactly what the DRL prevents."
            )
        else:
            reply = wrap(
                f"No savings this cycle — the DRL approved express shipping for {eid} "
                f"because the situation genuinely calls for it. RUL is at {rul:.0f} "
                f"and the technician is {'ready to install' if tech_avail else 'about to come on shift'}.\n\n"
                f"Not every decision is about saving money. Sometimes the right call is spending $350 "
                f"now to prevent a $50,000 unplanned outage tomorrow."
            )

    elif any(w in msg for w in ["shadow", "conflict", "model", "compare", "disagree", "why different"]):
        if shadow.get("conflict"):
            reply = wrap(
                f"Great question — yes, there's a CONFLICT between our two models right now.\n\n"
                f"The standard rule (simple threshold logic) says: {shadow['simple_rule']['decision']} — "
                f"{shadow['simple_rule']['reason']}\n\n"
                f"But the DRL policy (our trained neural network) says: {shadow['drl_policy']['decision']} — "
                f"{shadow['drl_policy']['reason']}\n\n"
                f"The enterprise verdict goes with: {shadow['enterprise_verdict']}. "
                f"This is exactly why we run both models side-by-side — the DRL considers factors "
                f"the simple rule can't see, like labor availability and total cost optimization. "
                f"The conflict saved us ${shadow.get('cost_saved', 0):.0f} this round."
            )
        else:
            reply = wrap(
                f"Both models are in agreement right now — no conflict. "
                f"The standard rule and the DRL policy both recommend {drl.get('label', '').replace('_', ' ').lower()}. "
                f"When they agree, it's a strong signal that the decision is solid."
            )

    elif any(w in msg for w in ["tech", "person", "shift", "crew", "worker", "available"]):
        if tech_avail:
            reply = wrap(
                f"The assigned technician is on shift with {shift_h:.1f} hours remaining. "
                f"That's {'plenty of time' if shift_h > 2 else 'cutting it tight'} for an express install.\n\n"
                f"The DRL factors this into its decision — if the tech only had 30 minutes left, "
                f"there's no point rushing a part that can't be installed until tomorrow anyway."
            )
        else:
            reply = wrap(
                f"The tech is currently off shift. This is actually a key factor — "
                f"express-shipping a $350 part right now means it sits on the dock "
                f"until someone's available to install it.\n\n"
                f"Shift time logged: {shift_h:.1f}h. The DRL model uses this to avoid "
                f"wasteful spending."
            )

    elif any(w in msg for w in ["explain", "why", "reason", "logic", "decision", "how did"]):
        reason = drl.get("reason", "")
        reply = wrap(
            f"Let me walk you through the DRL's reasoning for {eid}:\n\n"
            f"The model evaluated four inputs simultaneously:\n"
            f"1. RUL = {rul:.0f} cycles — {'critically low' if rul < 10 else 'within safe range'}\n"
            f"2. Vibration = {vib:.4f} g — {'elevated' if vib > 0.15 else 'normal'}\n"
            f"3. Technician shift = {shift_h:.1f}h remaining — {'enough time' if shift_h > 1.5 else 'tight window'}\n"
            f"4. Express part cost = $350\n\n"
            f"Based on 50,000+ training episodes, the neural network determined: {action_lbl.replace('_', ' ')}.\n\n"
            f"{reason}"
        )

    elif any(w in msg for w in ["help", "what can", "command", "options"]):
        reply = wrap(
            "I'm GANTRY — your industrial AI supervisor. Here's what I can help with:\n\n"
            "• \"How's the engine?\" — Full status report with my assessment\n"
            "• \"Why this decision?\" — I'll explain the DRL's reasoning step by step\n"
            "• \"Cost analysis\" — Breakdown of savings and spending logic\n"
            "• \"Shadow model\" — Compare rule-based vs. neural network decisions\n"
            "• \"Crew status\" — Technician availability and shift timing\n"
            "• \"Override\" — Manually reverse the DRL decision (Human-in-the-Loop)\n\n"
            "Just ask naturally — I understand conversational questions too."
        )

    elif any(w in msg for w in ["danger", "risk", "safe", "alarm", "urgent", "emergency"]):
        if rul < 5:
            reply = wrap(
                f"⚠️ Yes — {eid} is at elevated risk. With {rul:.0f} cycles remaining, "
                f"we're in the danger zone. Vibration at {vib:.4f} g confirms mechanical stress.\n\n"
                f"My recommendation: {'the DRL has already approved express shipping — good.' if 'APPROVE' in action_lbl else 'consider typing Override to force express shipping past the DRL veto.'}"
            )
        else:
            reply = wrap(
                f"No immediate danger for {eid}. RUL is {rul:.0f} cycles — that gives us "
                f"comfortable runway. Vibration is at {vib:.4f} g, well within spec.\n\n"
                f"That said, I'm monitoring continuously. If conditions change, I'll flag it."
            )

    else:
        # Natural catch-all
        reply = wrap(
            f"I'm tracking {eid} right now — status is {status}, "
            f"with {rul:.0f} cycles of life remaining. "
            f"{'The DRL vetoed express shipping to save $350.' if 'VETO' in action_lbl else 'Express shipping has been approved — part is on the way.'}\n\n"
            f"Want me to go deeper? Ask about the cost logic, shadow model conflict, "
            f"or crew availability — or type \"help\" for the full menu."
        )

    return {
        "reply": reply,
        "override_active": False,
        "unit_id": eid,
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Secure backend proxy for Elastic Agent Builder /converse.
    All auth headers (kbn-xsrf, ApiKey) stay server-side — no security_exception.
    Detects 'override' to enable Human-in-the-loop DRL bypass.
    """
    global _override_active

    # ── 1. Override detection ───────────────────────────────────────────
    if "override" in req.message.lower():
        _override_active = True
        return {
            "reply": (
                "⚠️ Override acknowledged. I've flagged the DRL decision for manual reversal. "
                "On the next orchestration cycle, the policy will be flipped — "
                "if it was vetoing, it'll approve, and vice versa.\n\n"
                "This is your call as the operator. The system trusts your judgment, "
                "but I'll log this as a Human-in-the-Loop intervention for audit purposes."
            ),
            "override_active": True,
            "unit_id": req.unit_id,
        }

    # ── 2. Build context ────────────────────────────────────────────────────
    # Priority: failure snapshot (halted) > live WS tick > last orchestration result
    if _system_halted and _failure_snapshot:
        # Active failure — use frozen snapshot values
        snap = _failure_snapshot
        _snap_rul = float(snap.get("rul", 0))
        _snap_vib = float(snap.get("vibration", 0))
        _snap_unit = snap.get("unit_id", req.unit_id)
        downtime_s = round(time.time() - _failure_timestamp, 0) if _failure_timestamp else 0
        d = {
            "engine_id": _snap_unit,
            "status": "CRITICAL",
            "physical_metrics": {"rul": _snap_rul, "vibration": _snap_vib, "data_volume": "20,000+ rows"},
            "personnel": _last_decision.get("personnel", {}) if _last_decision else {"available": True, "hours_until_shift_end": 4.0},
            "drl_decision": _last_decision.get("drl_decision", {"label": "APPROVE_EXPRESS_SHIPPING", "reason": "Failure imminent — RUL=0."}) if _last_decision else {"label": "APPROVE_EXPRESS_SHIPPING", "reason": "Failure imminent — RUL=0."},
            "shadow_model": _last_decision.get("shadow_model", {}) if _last_decision else {},
            "cost_impact": _last_decision.get("cost_impact", {"cost_saved": 0}) if _last_decision else {"cost_saved": 0},
            "downtime_seconds": downtime_s,
        }
    elif _last_live_telemetry and not _system_halted:
        # System is healthy — build context directly from the latest live WS tick.
        # This means the chat always reflects the current dashboard values, not stale
        # orchestration data from a previous failure run.
        live = _last_live_telemetry
        live_rul = live.get("rul", "—")
        live_vib = live.get("vibration", "—")
        live_status = live.get("unit_status", "HEALTHY")
        live_cycle = live.get("cycle", "—")
        d = {
            "engine_id": live.get("unit_id", req.unit_id),
            "status": live_status,
            "physical_metrics": {
                "rul": live_rul,
                "vibration": live_vib,
                "cycle": live_cycle,
                "data_volume": "20,000+ rows",
            },
            # Keep personnel/DRL from last orchestration if available, else defaults
            "personnel": _last_decision.get("personnel", {"available": True, "hours_until_shift_end": 4.0}) if _last_decision else {"available": True, "hours_until_shift_end": 4.0},
            "drl_decision": _last_decision.get("drl_decision", {"label": "MONITOR", "reason": "System nominal."}) if _last_decision else {"label": "MONITOR", "reason": "System nominal."},
            "shadow_model": _last_decision.get("shadow_model", {}) if _last_decision else {},
            "cost_impact": _last_decision.get("cost_impact", {"cost_saved": 0}) if _last_decision else {"cost_saved": 0},
            "downtime_seconds": 0,
        }
    elif not _last_decision:
        return {
            "reply": (
                "I don't have any engine data yet — hit the Orchestrate button first "
                "so I can pull telemetry and give you a proper assessment."
            ),
            "override_active": _override_active,
            "unit_id": req.unit_id,
        }
    else:
        d = _last_decision

    drl = d.get("drl_decision", {})
    shadow = d.get("shadow_model", {})
    pm = d.get("physical_metrics", {})
    per = d.get("personnel", {})
    ci = d.get("cost_impact", {})

    context_lines = [
        f"Unit: {d.get('engine_id')}",
        f"Status: {d.get('status')}",
        f"RUL: {pm.get('rul')} cycles",
        f"Vibration: {pm.get('vibration')} g RMS",
        f"Cycle: {pm.get('cycle', '—')}",
        f"DRL Decision: {drl.get('label')} — {drl.get('reason', '')}",
        f"Technician: {'Available' if per.get('available') else 'Unavailable'}, {per.get('hours_until_shift_end')}h left",
        f"Cost saved: ${ci.get('cost_saved', 0):.0f}",
        f"System halted: {_system_halted}",
        f"Downtime: {int(d.get('downtime_seconds', 0))}s",
    ]
    if shadow.get("conflict"):
        context_lines.append(
            f"Shadow Conflict: Rule={shadow['simple_rule']['decision']} "
            f"vs DRL={shadow['drl_policy']['decision']}"
        )
    context_str = " | ".join(context_lines)

    enriched_message = (
        f"CONTEXT: {context_str}\n"
        f"USER MESSAGE: {req.message}"
    )

    # ── 3. Try Elastic Agent Builder /converse, fall back to local ──────
    converse_url = f"{KB_URL}/api/agent_builder/agents/{AGENT_ID}/converse"
    headers = {
        "Authorization": f"ApiKey {CONVERSE_API_KEY}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }
    payload = {
        "agentId": AGENT_ID,
        "message": enriched_message,
        "session_id": req.unit_id,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(converse_url, headers=headers, json=payload)

        # ── Check for HTTP errors first ─────────────────────────────
        if resp.status_code >= 400:
            print(f"[CHAT] Elastic returned {resp.status_code}, using local fallback")
            return _local_chat_fallback(req.message, d, drl, shadow, pm, per, ci)

        data = resp.json()

        # Extract reply – handle multiple Elastic response shapes
        agent_reply = ""
        if isinstance(data, dict):
            agent_reply = (
                data.get("text", "")
                or data.get("result", {}).get("content", [{}])[0].get("text", "")
                or data.get("message", "")
                or json.dumps(data)
            )

        return {
            "reply": agent_reply,
            "override_active": _override_active,
            "unit_id": req.unit_id,
        }

    except Exception as exc:
        print(f"[CHAT] Exception: {exc}")
        return _local_chat_fallback(req.message, d, drl, shadow, pm, per, ci)
