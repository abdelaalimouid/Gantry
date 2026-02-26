"""
MCP Engine – Gantry Orchestrator Service
Handles all MCP communication with Elastic's Agent Builder.

Uses the built-in Elastic MCP platform tools:
  • platform_core_execute_esql  → Watchman (telemetry) & Foreman (personnel)
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

MCP_URL = os.getenv("ELASTIC_KB_URL") + "/api/agent_builder/mcp"
MCP_API_KEY = os.getenv("ELASTIC_MCP_API_KEY")

HEADERS = {
    "Authorization": f"ApiKey {MCP_API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ── ES|QL queries used by each agent ────────────────────────────────────────
WATCHMAN_ESQL = (
    'FROM gantry_telemetry | WHERE unit_id == "{unit_id}" '
    "| SORT @timestamp DESC | LIMIT 5 "
    "| KEEP unit_id, cycle, sensor_measure_11, rul_label, @timestamp"
)

FOREMAN_ESQL = (
    'FROM gantry_personnel | WHERE tech_name == "{tech_name}" '
    "| KEEP tech_name, role, shift, status, location, certifications"
)


def _extract_text(response_json: dict) -> str:
    """Pull the text content from an MCP tools/call result."""
    try:
        return response_json["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return json.dumps(response_json)


def _decision_engine(tel_text: str, per_text: str, unit_id: str) -> dict:
    """Processes raw MCP tool outputs into a clean frontend-ready JSON."""
    # Check for critical RUL in multiple possible formats
    critical_failure = (
        '"rul_label": 0' in tel_text         # JSON format
        or '"rul_label",0' in tel_text        # compact JSON
        or "rul_label | 0" in tel_text        # table format
        or ",0," in tel_text                  # CSV-like
        or "critical" in tel_text.lower()
    )

    # Also parse structured ES|QL results for rul_label == 0
    if not critical_failure:
        try:
            parsed = json.loads(tel_text)
            for result_block in parsed.get("results", []):
                data = result_block.get("data", {})
                columns = data.get("columns", [])
                values = data.get("values", [])
                if columns and values:
                    col_names = [c["name"] for c in columns]
                    if "rul_label" in col_names:
                        rul_idx = col_names.index("rul_label")
                        for row in values:
                            if row[rul_idx] == 0:
                                critical_failure = True
                                break
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

    tech_ready = "available" in per_text.lower()

    return {
        "engine_id": unit_id,
        "status": "CRITICAL" if critical_failure else "HEALTHY",
        "action": (
            "APPROVE_EXPRESS_SHIPPING"
            if (critical_failure and tech_ready)
            else "VETO_EXPRESS_SHIPPING"
        ),
        "reason": (
            "Technical failure confirmed and staff on-shift."
            if tech_ready
            else "VETO: Technician shift ends before delivery."
        ),
    }


async def run_gantry_orchestrator(unit_id: str) -> dict:
    """
    Full MCP orchestration cycle for a given engine unit.
    Uses Elastic's built-in platform_core_execute_esql tool via MCP.
    Returns a clean JSON dict ready for the frontend.
    """
    async with httpx.AsyncClient(timeout=None) as client:
        # 1. MCP Handshake
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Gantry-Web-App", "version": "1.0.0"},
            },
        }
        await client.post(MCP_URL, headers=HEADERS, json=init_payload)

        # 2. Watchman – Telemetry via ES|QL
        tel_query = WATCHMAN_ESQL.format(unit_id=unit_id)
        tel_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "platform_core_execute_esql",
                "arguments": {"query": tel_query},
            },
        }
        tel_resp = await client.post(MCP_URL, headers=HEADERS, json=tel_payload)
        telemetry_data = tel_resp.json()

        # 3. Foreman – Personnel via ES|QL
        per_query = FOREMAN_ESQL.format(tech_name="Soufiane")
        per_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "platform_core_execute_esql",
                "arguments": {"query": per_query},
            },
        }
        per_resp = await client.post(MCP_URL, headers=HEADERS, json=per_payload)
        personnel_data = per_resp.json()

    # 4. Extract raw text blobs
    tel_text = _extract_text(telemetry_data)
    per_text = _extract_text(personnel_data)

    decision = _decision_engine(tel_text, per_text, unit_id)
    decision["_raw_telemetry"] = tel_text
    decision["_raw_personnel"] = per_text
    return decision


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio

    result = asyncio.run(run_gantry_orchestrator("ENGINE-001"))
    print(json.dumps(result, indent=2))
