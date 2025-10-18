# Current Status - Train Network Speed Map

**Last Updated:** October 18, 2025

## ✅ What's Working

### Backend
- ✅ FastAPI server running on port 8000
- ✅ Deutsche Bahn Timetables API integration (requires both Client ID and API Key)
- ✅ XML parsing from `/plan` endpoint
- ✅ Fetches 12 hours of departure data (multiple API calls)
- ✅ Parses train paths to find intermediate stations
- ✅ Data caching system (JSON files in `backend/data/`)
- ✅ API endpoints for fetching, caching, and filtering network data
- ✅ CORS configured for frontend communication

### Frontend
- ✅ Next.js 15 with TypeScript and Tailwind CSS
- ✅ Leaflet map integration
- ✅ Filter panel with speed slider
- ✅ Statistics display (total connections, avg/max speed, max distance)
- ✅ API client for backend communication
- ✅ Loading states and error handling

### Data
- ✅ Hardcoded EVA numbers for 10 major German stations
- ✅ Hardcoded coordinates (lat/lon) for these stations
- ✅ Distance calculation (straight-line using geopy)

## ⚠️ Current Limitations

### 1. **CRITICAL: Estimated Travel Times (Not Real)**
**Problem:** The DB API `/plan` endpoint only provides:
- Departure time from origin station
- List of stations on the route (path)
- **NOT** arrival times at destination stations
- Does not refresh cache

**Current Hack:** Estimating travel time based on:
```python
estimated_time = distance / estimated_speed_for_train_type
```

**Why This Is Bad:**
- Defeats the purpose of calculating "aerial speed"
- Not real data, just estimates
- Speeds are made up (ICE=200km/h, IC=150km/h, etc.)

**Possible Solutions:**
1. Use `/journeyDetail` endpoint for each train to get full schedule with real arrival times (slow, many API calls)
2. Parse arrival times from intermediate stations if included in XML
3. Use a different API that provides complete journey information
4. Accept estimates as "good enough" for visualization purposes

### 2. **Limited Station Coverage**
**Problem:** Only showing connections to 10 hardcoded major stations:
- Essen Hbf, Berlin Hbf, München Hbf, Hamburg Hbf, Frankfurt Hbf
- Köln Hbf, Düsseldorf Hbf, Stuttgart Hbf, Hannover Hbf, Nürnberg Hbf

**Why:** We need both EVA numbers and coordinates for each station.

**Impact:** From ~200 departures in 12 hours, only showing connections that pass through these 10 stations (probably 20-50 connections).

**Solutions:**
- Use DB Station API to dynamically fetch station data
- Use OpenStreetMap Nominatim API to get coordinates
- Scrape/download complete station database
- Expand hardcoded list (manual but easy)

### 3. **No Destination Markers on Map**
**Problem:** The map only shows the origin station marker, not destination markers.

**Why:** The `TrainNetworkMap.tsx` component has placeholder code that filters out destinations without coordinates.

**Fix:** Simple - just remove the filter that checks for `lat === 0 && lon === 0`.

### 4. **Only Direct Connections**
**Status:** As designed - only showing direct trains from Essen Hbf.

**Future:** Plan is to build full network by fetching connections from connections.

## 📊 Current Performance

**API Response Time:**
- Single hour: ~500ms
- 12 hours: ~6 seconds (sequential API calls)
- Could be parallelized for better performance

**Data Volume:**
- 19 departures per hour from Essen Hbf
- ~200 departures in 12 hours
- After filtering: 20-50 connections to major stations
- Cached file size: ~50KB

## 🚀 Quick Setup (For New Chat)

### Backend
```bash
cd backend
source venv/bin/activate  # or create: python -m venv venv
pip install -r requirements.txt

# Edit .env file with your credentials:
# DB_CLIENT_ID=your_client_id
# DB_API_KEY=your_api_key

python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Visit: http://localhost:3000

## 🔧 Key Files to Understand

### Backend
- `core/db_api_client.py` - Fetches data from DB Timetables API `/plan` endpoint
  - Returns departure time, train type, path stations
  - Hardcoded station coordinates

- `core/network_service.py` - Processes departures into connections
  - **Line 119:** The FAKE speed estimation (`_estimate_speed()`)
  - **Line 96-146:** Loops through path stations to create connections

- `api/routes.py` - FastAPI endpoints
  - `POST /api/fetch-network` - Main endpoint

### Frontend
- `app/page.tsx` - Main page, handles state and API calls
- `components/TrainNetworkMap.tsx` - Leaflet map
  - **Lines 117-121:** Filtering that causes only origin marker to show

- `lib/api.ts` - API client

## 🎯 Next Steps (Priority Order)

### High Priority
1. **Fix destination markers on map** (5 minutes)
   - Remove the coordinate filter in `TrainNetworkMap.tsx`

2. **Decide on travel time strategy:**
   - Option A: Accept estimates for MVP, focus on visualization
   - Option B: Fetch real times from `/journeyDetail` endpoint
   - Option C: Use alternative API (transport.rest, hafas, etc.)

### Medium Priority
3. **Expand station coverage:**
   - Add more hardcoded stations (manual but works)
   - Or implement dynamic station lookup

4. **Improve performance:**
   - Parallelize API calls (fetch multiple hours concurrently)
   - Cache station lookups

### Low Priority
5. **Features:**
   - Filter by train type (ICE, IC, RE, etc.)
   - Time-based filtering
   - Show connection frequency
   - Build multi-hop network

## 🐛 Known Issues

1. Destination markers not showing on map (simple fix)
2. Travel times are estimated, not real (architectural decision needed)
3. Only 10 stations have coordinates (needs more data)
4. Frontend shows "Loading map..." flash even when using cached data
5. Error messages could be more user-friendly

## 📝 Notes

- The `/plan` endpoint returns timetable data in XML format
- Each stop (`<s>`) has departure (`<dp>`) and/or arrival (`<ar>`) elements
- The `@ppth` attribute contains pipe-separated list of stations
- Times are in format `YYMMDDhhmm` (e.g., `2510182117` = Oct 18, 2025, 21:17)
- DB API has rate limits (60 requests per minute with our key)

## 🤝 For Continuation

When starting a new chat, focus on:
1. Deciding the travel time strategy (real vs estimated)
2. Fixing the map markers (quick win)
3. Expanding station coverage if needed

The core infrastructure is working - it's mostly about data quality and coverage now!
