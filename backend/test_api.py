"""
Simple test script to check Deutsche Bahn API connectivity and response format.
"""
import asyncio
from core.db_api_client import DBAPIClient
from config import config

async def test_api():
    """Test the Bahnhof API client."""
    print("Testing Deutsche Bahn API...")
    #print(f"API Key configured: {'Yes' if config.DB_API_KEY else 'No'}")
    #print(f"API Base URL: {config.DB_API_BASE_URL}")
    print()

    client = DBAPIClient()

    # Test 1: Search for Essen Hbf
    print("Test 1: Searching for 'Essen Hbf'...")
    try:
        stations = await client.search_station("Essen Hbf")
        print(f"✓ Found {len(stations)} stations")
        if stations:
            print(f"  First result: {stations[0]}")
            print()
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 2: Get specific station
    print("Test 2: Getting station by name...")
    try:
        station = await client.get_station_by_name("Essen Hbf")
        if station:
            print(f"✓ Station found: {station.get('name')}")
            print(f"  ID: {station.get('id')}")
            print(f"  Location: {station.get('lat')}, {station.get('lon')}")
            print()

            # Test 3: Get departures
            print("Test 3: Getting departures...")
            station_id = station.get('id')
            departures = await client.get_departures(station_id)
            print(f"✓ Found {len(departures)} departures")
            if departures:
                print(f"  First departure: {departures[0]}")
        else:
            print("✗ Station not found")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api())
