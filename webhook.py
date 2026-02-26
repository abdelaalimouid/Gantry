import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELASTIC_CONVERSE_API_KEY")
AGENT_ID = "gantry_orchestrator"
URL = os.getenv("ELASTIC_KB_URL") + "/api/agent_builder/converse"

def get_engine_decision(engine_id):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"ApiKey {API_KEY}",
        "kbn-xsrf": "true"
    }
    
    # Prompting the agent to act as a pure data engine
    payload = {
        "agentId": AGENT_ID,
        "message": f"ANALYSIS_MODE: Unit {engine_id}. Use Watchman, Quartermaster, and Foreman. "
                   "Output a JSON object with: 'status', 'decision', and 'reason'.",
        "stream": False
    }

    response = requests.post(URL, headers=headers, json=payload)
    return response.json()

# Test call
print(json.dumps(get_engine_decision("ENGINE-AUTONOMY-TEST-99"), indent=2))