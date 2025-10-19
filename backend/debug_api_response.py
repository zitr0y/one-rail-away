"""
Debug script to see what the API actually returns
"""
import asyncio
import httpx
import xmltodict
import json
from datetime import datetime
from config import config

async def fetch_and_dump():
    """Fetch raw API data and dump it"""

    eva = "8000098"  # Essen Hbf
    now = datetime.now()
    date_str = now.strftime("%y%m%d")
    hour_str = now.strftime("%H")

    url = f"{config.DB_API_BASE_URL}/plan/{eva}/{date_str}/{hour_str}"

    headers = {
        "DB-Client-Id": config.DB_CLIENT_ID,
        "DB-Api-Key": config.DB_API_KEY,
    }

    print(f"Fetching: {url}\n")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()

        # Save raw XML
        with open("debug_raw.xml", "w") as f:
            f.write(response.text)
        print("Saved raw XML to debug_raw.xml")

        # Parse and save JSON
        data = xmltodict.parse(response.text)
        with open("debug_parsed.json", "w") as f:
            json.dump(data, f, indent=2)
        print("Saved parsed JSON to debug_parsed.json")

        # Print first stop details
        if "timetable" in data and "s" in data["timetable"]:
            stops = data["timetable"]["s"]
            if isinstance(stops, list) and len(stops) > 0:
                first_stop = stops[0]
            else:
                first_stop = stops

            print("\n=== FIRST STOP DETAILS ===")
            print(json.dumps(first_stop, indent=2))

            # Check if there's journey detail reference
            if "dp" in first_stop:
                dp = first_stop["dp"]
                print("\n=== DEPARTURE INFO ===")
                print(json.dumps(dp, indent=2))

                # Look for journey reference
                if "@l" in dp:
                    print(f"\nJourney reference found: {dp['@l']}")

if __name__ == "__main__":
    asyncio.run(fetch_and_dump())
