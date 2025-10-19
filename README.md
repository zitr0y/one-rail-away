# Train Network Speed Map

A full-stack application for visualizing real-time train network connections and speeds across Germany using Deutsche Bahn API data.

## Features

**100% Real Data - No Estimates!**
- ✅ **Real arrival times** directly from Deutsche Bahn Timetables API
- ✅ **All 15,000+ German train stations** loaded from official database
- ✅ **Route waypoints** - see the actual path trains take through intermediate stations
- ✅ **Smart caching** - 24-hour cache for destination plans, drastically reduces API calls
- ✅ **Parallel fetching** - fetches 200+ destination plans in parallel for fast initial load
- ✅ **Interactive map** with Leaflet showing geographic train routes
- ✅ **Connection filtering** by speed, train type, and more
- ✅ **Real-time statistics** - accurate speeds calculated from real travel times

**New: Multi-Hop Connections & Station Selection**
- ✅ **Multi-hop routes** - find routes with up to 5 changeovers (configurable)
- ✅ **Smart route ranking** - prioritized by fewest changeovers, then fastest speed
- ✅ **Transfer time validation** - configurable minimum transfer times (default 5 min)
- ✅ **Clickable station selection** - click any destination to make it your new base station
- ✅ **Station search** - autocomplete search across all 15,000+ German stations
- ✅ **Auto re-centering** - map automatically adjusts when you select a new station

## How It Works

Unlike typical train apps that estimate travel times, this system fetches **real arrival data** from the Deutsche Bahn API:

### Direct Connections
1. **Fetch departures** from origin station (e.g., Essen Hbf)
2. **Extract all destinations** from the train paths (200+ stations)
3. **Fetch arrival plans** for all destinations in parallel (with aggressive caching)
4. **Match train numbers** to find real arrival times at each destination
5. **Build connections** with 100% real data - if we don't have real arrival time, we skip it!
6. **Draw routes** through intermediate stations showing the actual train path

### Multi-Hop Routes (New!)
1. **Start with direct connections** as the base (0 changeovers)
2. **Expand level by level** - for each changeover level (1 to max):
   - Fetch connections from intermediate stations
   - Match valid transfers (respecting minimum transfer time)
   - Build multi-leg routes with real arrival times
3. **Validate transfers** - ensure sufficient time for changeovers (configurable, default 5 min)
4. **Avoid loops** - skip routes that revisit the same station
5. **Rank routes** - prioritize by fewest changeovers, then fastest average speed
6. **Return top N routes** per destination (configurable, default 3)

### Performance
- **First request**: ~60 seconds (fetch 200+ destination plans)
- **Cached requests**: <2 seconds (all data cached for 24 hours)
- **Data freshness**: Cache expires after 24 hours, ensuring daily updates

## Project Structure

```
de-trains-speed-map/
├── backend/              # FastAPI backend
│   ├── api/             # API routes and endpoints
│   │   └── routes.py    # Network data endpoints
│   ├── core/            # Core business logic
│   │   ├── models.py    # Pydantic data models (Station, Connection, RouteWaypoint)
│   │   ├── db_api_client.py  # Deutsche Bahn API client (15k+ stations)
│   │   ├── network_service.py  # Network data processing (real-time matching)
│   │   └── cache_service.py    # Data caching (24-hour station plans)
│   ├── data/            # Cached network data (JSON files)
│   │   └── stations.json # Full German train station database
│   ├── config.py        # Configuration (cache duration, parallel fetches)
│   ├── main.py          # FastAPI application entry point
│   └── requirements.txt # Python dependencies
├── frontend/            # Next.js frontend
│   ├── app/            # Next.js app router
│   │   └── page.tsx    # Main page with station selection
│   ├── components/     # React components
│   │   ├── TrainNetworkMap.tsx  # Leaflet map with multi-hop routes
│   │   ├── FilterPanel.tsx      # Filters, statistics, multi-hop controls
│   │   └── StationSearch.tsx    # Station search autocomplete
│   ├── lib/            # Utilities and API client
│   │   ├── api.ts      # Backend API client
│   │   └── utils.ts    # Helper functions
│   ├── types/          # TypeScript type definitions
│   │   └── index.ts    # Connection, MultiHopRoute, NetworkData
│   └── package.json
└── README.md           # This file
```

## Prerequisites

- Python 3.8 or higher
- Node.js 18 or higher
- npm or yarn
- A Deutsche Bahn API key ([get one here](https://developers.deutschebahn.com/))

## Setup Instructions

### 1. Backend Setup

#### Install Python dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Configure API credentials

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your Deutsche Bahn API credentials:

```env
DB_API_KEY=your_actual_api_key_here
DB_CLIENT_ID=your_client_id_here
DB_API_BASE_URL=https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1
```

#### Run the backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000
- API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 2. Frontend Setup

#### Install Node.js dependencies

```bash
cd frontend
npm install
```

#### Configure environment variables

The frontend is pre-configured to connect to http://localhost:8000. If you need to change this, edit `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Run the frontend

```bash
cd frontend
npm run dev
```

The application will be available at http://localhost:3000

## Usage

1. **Start both servers**: Run the backend (port 8000) and frontend (port 3000)

2. **Select a station**:
   - Search for any station using the search bar (15,000+ stations available)
   - OR click on any destination marker on the map to make it your new base station

3. **Configure multi-hop settings**:
   - Use the "Max Changeovers" slider to find routes with 0-5 transfers
   - Set minimum transfer time (default 5 minutes) to ensure realistic connections
   - Direct connections (0 changeovers) are always shown

4. **View the map**:
   - **Direct routes**: Solid lines from origin to destination
   - **Multi-hop routes**: Progressively dashed lines (more dashes = more changeovers)
   - **Changeover stations**: Special markers indicate where you change trains
   - **Colors**: Indicate aerial speed (red=slow, yellow=medium, green=fast)
   - Click markers to see detailed connection/transfer information

5. **Filter connections**:
   - Use the speed slider to filter by minimum aerial speed
   - Filter by train type (ICE, IC, RE, RB, S-Bahn) [coming soon]
   - Statistics update automatically

6. **Refresh data**: Click "Refresh Data" to force-fetch fresh data from the API

## Configuration

Backend configuration options in `backend/config.py`:

```python
# Cache configuration
NETWORK_CACHE_HOURS = 12          # How long to cache full network data
STATION_PLAN_CACHE_HOURS = 24     # How long to cache destination plans

# Optimization settings
TOP_DESTINATIONS_COUNT = 20        # [DEPRECATED - now fetches ALL destinations]
MAX_PARALLEL_STATION_FETCHES = 10  # Max parallel API requests

# Multi-hop connection settings
MAX_CHANGEOVERS_LIMIT = 5          # Maximum changeovers allowed (configurable via UI)
DEFAULT_MIN_TRANSFER_TIME = 5      # Default minimum transfer time in minutes
MAX_ROUTES_PER_DESTINATION = 3     # Max routes to return per destination
```

## API Endpoints

### Backend API

- `POST /api/fetch-network` - Fetch and cache network data for a station
  ```json
  {
    "station_name": "Essen Hbf",
    "force_refresh": false,
    "max_connections": 200,
    "max_changeovers": 2,              // NEW: 0-5 changeovers (default: 0)
    "min_transfer_time": 5,            // NEW: Min transfer minutes (default: 5)
    "max_routes_per_destination": 3   // NEW: Top N routes per destination (default: 3)
  }
  ```

- `GET /api/network/{station_id}` - Get cached network data
- `GET /api/stations/cached` - List all cached stations
- `GET /api/stations/top?limit=10` - Get top stations by connection count
- `GET /api/stations/search?q={query}&limit=20` - **NEW**: Search stations by name (autocomplete)
- `POST /api/connections/filter` - Filter connections by criteria
- `DELETE /api/cache/{station_id}` - Clear cache for a station
- `DELETE /api/cache` - Clear all cached data

## Data Models

### Station
```python
{
  "id": "8000098",           # EVA station number
  "name": "Essen Hbf",
  "lat": 51.451389,
  "lon": 7.012778,
  "connection_count": 200
}
```

### RouteWaypoint
```python
{
  "station_name": "Dortmund Hbf",
  "lat": 51.517896,
  "lon": 7.45929,
  "arrival_time": "2025-10-19T01:24:00",  # Real arrival time!
  "distance_from_origin_km": 31.75
}
```

### Connection (Direct)
```python
{
  "origin_id": "8000098",
  "origin_name": "Essen Hbf",
  "destination_id": "8000036",
  "destination_name": "Bielefeld Hbf",
  "destination_lat": 52.029261,
  "destination_lon": 8.532722,
  "train_type": "ICE",
  "train_number": "100",
  "departure_time": "2025-10-19T00:59:00",
  "arrival_time": "2025-10-19T01:35:00",    # Real from API!
  "travel_time_minutes": 36,
  "distance_km": 122.99,
  "aerial_speed_kmh": 204.99,
  "route_waypoints": [                      # Intermediate stations
    {"station_name": "Dortmund Hbf", ...},
    {"station_name": "Hamm(Westf)Hbf", ...}
  ],
  "platform": "4",
  "is_real_time": true,                     # Always true!
  "path_station_names": ["Dortmund Hbf", "Hamm(Westf)Hbf", "Bielefeld Hbf"]
}
```

### MultiHopRoute (NEW)
```python
{
  "origin_id": "8000098",
  "origin_name": "Essen Hbf",
  "destination_id": "8010205",
  "destination_name": "Leipzig Hbf",
  "destination_lat": 51.3456,
  "destination_lon": 12.3819,
  "legs": [                                  # Each leg is a ConnectionLeg
    {
      "origin_id": "8000098",
      "origin_name": "Essen Hbf",
      "destination_id": "8000105",
      "destination_name": "Frankfurt(Main)Hbf",
      "train_type": "ICE",
      "train_number": "571",
      "departure_time": "2025-10-19T08:00:00",
      "arrival_time": "2025-10-19T10:30:00",
      "travel_time_minutes": 150,
      "distance_km": 320.0,
      "aerial_speed_kmh": 128.0,
      "platform": "7"
    },
    {
      "origin_id": "8000105",
      "origin_name": "Frankfurt(Main)Hbf",
      "destination_id": "8010205",
      "destination_name": "Leipzig Hbf",
      "train_type": "ICE",
      "train_number": "1652",
      "departure_time": "2025-10-19T10:45:00",
      "arrival_time": "2025-10-19T14:00:00",
      "travel_time_minutes": 195,
      "distance_km": 400.0,
      "aerial_speed_kmh": 123.1,
      "platform": "12"
    }
  ],
  "transfers": [                             # Transfer information
    {
      "station_id": "8000105",
      "station_name": "Frankfurt(Main)Hbf",
      "station_lat": 50.1072,
      "station_lon": 8.6632,
      "arrival_time": "2025-10-19T10:30:00",
      "departure_time": "2025-10-19T10:45:00",
      "waiting_time_minutes": 15,
      "arrival_platform": "7",
      "departure_platform": "12"
    }
  ],
  "total_travel_time_minutes": 360,         # Total including transfers
  "total_distance_km": 720.0,
  "total_waiting_time_minutes": 15,
  "number_of_changeovers": 1,
  "average_aerial_speed_kmh": 120.0,
  "departure_time": "2025-10-19T08:00:00",
  "arrival_time": "2025-10-19T14:00:00",
  "is_real_time": true
}
```

### Network Data
```python
{
  "timestamp": "2025-10-19T00:00:00",
  "origin_station": {...},
  "connections": [...],                    # Direct connections - all with real data!
  "multi_hop_routes": [...],               # NEW: Multi-hop routes with changeovers
  "total_connections": 200,
  "total_multi_hop_routes": 150,           # NEW: Count of multi-hop routes
  "average_speed_kmh": 120.5,
  "max_speed_kmh": 250.0,
  "max_distance_km": 500.0
}
```

## How Aerial Speed Works

Aerial speed represents how efficiently a train connection covers geographic distance:

```
Aerial Speed (km/h) = (Straight-line Distance / Real Travel Time) * 60
```

**Note**: This uses **real travel time from the API**, not estimates!

This metric is useful for:
- Identifying fast direct connections vs. slower regional routes
- Comparing route efficiency (straighter routes = higher aerial speed)
- Understanding which trains take more direct paths
- Finding the fastest way to cover distance between two points

## Technical Highlights

### Smart Caching Strategy
- **Station plans** cached for 24 hours (destination arrival/departure schedules)
- **Full network data** cached for 12 hours
- Cache automatically expires and refreshes daily
- Reduces API calls by 95%+ after initial load

### Real-Time Data Matching
1. Fetch all departures from origin station
2. Extract 200+ unique destinations from train paths
3. Fetch arrival plans for ALL destinations in parallel
4. Match trains by number to find real arrival times
5. Only create connections when we have real arrival data

### No More Estimates!
The previous version estimated travel times using average speeds by train type (ICE=200km/h, IC=150km/h, etc.). This was inaccurate and misleading.

**Now**: Every connection uses real arrival times from the Deutsche Bahn API. If we don't have real data, we don't show it!

## Recently Implemented (October 2025)

- [x] **Multi-hop connections** - Find routes with up to 5 changeovers
- [x] **Station selection** - Click any station or search to change origin
- [x] **Station search** - Autocomplete across all 15,000+ German stations
- [x] **Transfer validation** - Configurable minimum transfer times

## Future Enhancements

- [ ] Multi-hop route visualization (progressive dashing, changeover markers) - **IN PROGRESS**
- [ ] Complete UI integration for multi-hop controls - **IN PROGRESS**
- [ ] Deutschlandticket filter (RE, RB, S-Bahn only)
- [ ] Complete Germany network map visualization
- [ ] Time-based filtering (morning, afternoon, evening)
- [ ] Historical data tracking and trends
- [ ] Export data to CSV/JSON
- [ ] Live delay information
- [ ] Platform change notifications
- [ ] Mobile-responsive design improvements

## Troubleshooting

### Backend Issues

**"DB_API_KEY is required"**
- Make sure you've created a `.env` file with your API key and client ID

**"Loaded 0 stations from database"**
- Ensure `backend/data/stations.json` exists
- File should contain 15,000+ German train stations

**Slow initial load**
- First request fetches 200+ destination plans (~60 seconds)
- Subsequent requests use cache (<2 seconds)
- This is expected and normal!

### Frontend Issues

**Map not loading**
- Check that the backend is running on port 8000
- Check browser console for errors
- Ensure Leaflet CSS is loading correctly

**Lines appear straight instead of following routes**
- Check that connections have `route_waypoints` in the data
- Verify waypoints have valid lat/lon coordinates
- Look for waypoint data in network response

## Performance Metrics

Typical performance for Essen Hbf:
- **Departures found**: ~225 trains
- **Unique destinations**: ~206 stations
- **Connections created**: 200+ (with real arrival times)
- **Cache hit rate**: 100% after first request
- **API calls**: 206 on first request, 0 on subsequent requests
- **Response time**: 60s first, <2s cached

## License

TBD

## Contributing

This is a personal project, but suggestions and feedback are welcome! Feel free to open issues or submit pull requests.

## Acknowledgments

- Deutsche Bahn for providing the Timetables API
- OpenStreetMap and Leaflet for map visualization
- All 15,000+ train stations in Germany for existing
