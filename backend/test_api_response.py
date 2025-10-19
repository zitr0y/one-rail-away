"""Debug script to check API response structure."""
import asyncio
import httpx
import xmltodict
import json
from config import config

async def test_failing_request():
    """Test one of the failing requests to see the structure."""
    station_id = "8000263"
    date_str = "251019"
    hour = 3

    url = f"{config.DB_API_BASE_URL}/plan/{station_id}/{date_str}/{hour:02d}"

    headers = {
        "DB-Client-Id": config.DB_CLIENT_ID,
        "DB-Api-Key": config.DB_API_KEY,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()

        # Parse XML
        data = xmltodict.parse(response.text)

        print("Full response structure:")
        print(json.dumps(data, indent=2, default=str))

        print("\n\nChecking timetable:")
        timetable = data.get("timetable")
        print(f"timetable type: {type(timetable)}")
        print(f"timetable value: {timetable}")

        if timetable:
            print(f"Is dict? {isinstance(timetable, dict)}")
            if isinstance(timetable, dict):
                print(f"Keys: {timetable.keys()}")
                print(f"Has 's'? {'s' in timetable}")

if __name__ == "__main__":
    asyncio.run(test_failing_request())
