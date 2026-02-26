"""
trigger_failure.py – Inject a critical failure into Elasticsearch.

Injects a single RUL=0 document for ENGINE-001, then broadcasts a
critical alert so the CriticalOverlay appears instantly. The MCP agent
swarm auto-launches to propose a fix.
"""

import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("ELASTIC_ES_URL")
API_KEY  = os.getenv("ELASTIC_ES_API_KEY")
API_BASE = os.getenv("GANTRY_API_BASE", "http://localhost:8000")

if not ENDPOINT or not API_KEY:
    print("ERROR: ELASTIC_ES_URL or ELASTIC_ES_API_KEY not set in .env")
    sys.exit(1)


def _broadcast_alert(unit_id, rul, vibration, cycle):
    """POST to the Gantry API to push an instant critical overlay."""
    import httpx
    try:
        resp = httpx.post(f"{API_BASE}/api/broadcast-alert", json={
            "unit_id": unit_id,
            "rul": rul,
            "vibration": vibration,
            "cycle": cycle,
        }, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"   📡 Alert broadcast to {data.get('clients', 0)} connected client(s)")
        else:
            print(f"   ⚠️  Broadcast returned {resp.status_code}: {resp.text[:120]}")
    except Exception as exc:
        print(f"   ⚠️  Could not broadcast alert (is the API running?): {exc}")

try:
    from elasticsearch import Elasticsearch
    es = Elasticsearch(hosts=[ENDPOINT], api_key=API_KEY)

    # ── Single failure: ENGINE-001 reaches RUL=0 ─────────────────────
    es.index(index="gantry_telemetry", document={
        "@timestamp": datetime.now(timezone.utc).isoformat(),
        "unit_id": "ENGINE-001",
        "cycle": 999,
        "sensor_measure_11": 50.0,
        "vibration": 0.25,
        "rul_label": 0,
    })
    print("✅ Critical failure injected for ENGINE-001 (RUL=0, cycle=999)")

    # ── Broadcast alert overlay ──────────────────────────────────────
    _broadcast_alert("ENGINE-001", rul=0, vibration=0.25, cycle=999)

    print("\n🚀 Check the Gantry UI — red overlay + agent swarm should appear.")

except ImportError:
    import httpx, json

    headers = {
        "Authorization": f"ApiKey {API_KEY}",
        "Content-Type": "application/json",
    }
    doc = {
        "unit_id": "ENGINE-001", "cycle": 999, "sensor_measure_11": 50.0,
        "vibration": 0.25, "rul_label": 0,
        "@timestamp": datetime.now(timezone.utc).isoformat(),
    }
    resp = httpx.post(f"{ENDPOINT}/gantry_telemetry/_doc", headers=headers, json=doc)
    print(f"✅ Failure injected via httpx: {resp.status_code}")
    _broadcast_alert("ENGINE-001", rul=0, vibration=0.25, cycle=999)