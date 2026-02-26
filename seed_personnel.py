"""
Seed the gantry_personnel index with technician records.
Required by the Foreman (personnel_locator) MCP tool.
"""

import os
from datetime import datetime
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv

load_dotenv()

es = Elasticsearch(
    hosts=[os.getenv("ELASTIC_ES_URL")],
    api_key=os.getenv("ELASTIC_ES_API_KEY"),
)

INDEX = "gantry_personnel"

TECHNICIANS = [
    {
        "tech_name": "Soufiane",
        "role": "Senior Crane Technician",
        "shift": "day",
        "status": "available",
        "location": "Bay 3 – Main Gantry",
        "certifications": ["hydraulics", "structural", "electrical"],
        "years_experience": 12,
    },
    {
        "tech_name": "Fatima",
        "role": "Electrical Systems Engineer",
        "shift": "day",
        "status": "available",
        "location": "Control Room A",
        "certifications": ["electrical", "PLC", "SCADA"],
        "years_experience": 8,
    },
    {
        "tech_name": "Youssef",
        "role": "Hydraulics Specialist",
        "shift": "night",
        "status": "off-shift",
        "location": "Off-site",
        "certifications": ["hydraulics", "pneumatics"],
        "years_experience": 6,
    },
    {
        "tech_name": "Amina",
        "role": "Safety Inspector",
        "shift": "day",
        "status": "available",
        "location": "Bay 1 – Inspection Zone",
        "certifications": ["safety", "structural", "NDT"],
        "years_experience": 10,
    },
    {
        "tech_name": "Rachid",
        "role": "Junior Crane Technician",
        "shift": "night",
        "status": "off-shift",
        "location": "Off-site",
        "certifications": ["structural"],
        "years_experience": 2,
    },
]


def seed():
    actions = []
    now = datetime.utcnow().isoformat()
    for tech in TECHNICIANS:
        tech["@timestamp"] = now
        actions.append({"_index": INDEX, "_source": tech})

    helpers.bulk(es, actions)
    print(f"✅ Seeded {len(TECHNICIANS)} technicians into '{INDEX}'.")


if __name__ == "__main__":
    seed()
