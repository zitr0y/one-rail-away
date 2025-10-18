# Train Network Speed Map

A full-stack application for visualizing train network connections and aerial speeds across Germany using Deutsche Bahn API data.

## Features

- Interactive geographic map showing train connections
- Color-coded visualization based on aerial speed (straight-line distance / travel time)
- Filter connections by minimum speed threshold
- Display statistics: total connections, average speed, max speed, max distance
- Data caching to reduce API calls
- Support for different starting stations (default: Essen Hbf)

## Project Structure

```
de-trains-speed-map/
├── backend/              # FastAPI backend
│   ├── api/             # API routes and endpoints
│   │   └── routes.py    # Network data endpoints
│   ├── core/            # Core business logic
│   │   ├── models.py    # Pydantic data models
│   │   ├── db_api_client.py  # Deutsche Bahn API client
│   │   ├── network_service.py  # Network data processing
│   │   └── cache_service.py    # Data caching
│   ├── data/            # Cached network data (JSON files)
│   ├── config.py        # Configuration management
│   ├── main.py          # FastAPI application entry point
│   └── requirements.txt # Python dependencies
├── frontend/            # Next.js frontend
│   ├── app/            # Next.js app router
│   │   └── page.tsx    # Main page
│   ├── components/     # React components
│   │   ├── TrainNetworkMap.tsx  # Leaflet map component
│   │   └── FilterPanel.tsx      # Filters and statistics
│   ├── lib/            # Utilities and API client
│   │   ├── api.ts      # Backend API client
│   │   └── utils.ts    # Helper functions
│   ├── types/          # TypeScript type definitions
│   │   └── index.ts
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

Edit `.env` and add your Deutsche Bahn API key:

```
DB_API_KEY=your_actual_api_key_here
```

#### Run the backend

```bash
cd backend
python main.py
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

```
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

2. **Load network data**: Click "Load Essen Hbf Network" to fetch connections from Essen Hauptbahnhof

3. **View the map**:
   - Lines connect origin to destinations
   - Colors indicate aerial speed (red=slow, yellow=medium, green=fast)
   - Click markers to see connection details

4. **Filter connections**:
   - Use the speed slider to filter by minimum aerial speed
   - Statistics update automatically

5. **Refresh data**: Click "Refresh Data" to fetch fresh data from the API

## API Endpoints

### Backend API

- `POST /api/fetch-network` - Fetch and cache network data for a station
- `GET /api/network/{station_id}` - Get cached network data
- `GET /api/stations/cached` - List all cached stations
- `GET /api/stations/top` - Get top stations by connection count
- `POST /api/connections/filter` - Filter connections by criteria
- `DELETE /api/cache/{station_id}` - Clear cache for a station
- `DELETE /api/cache` - Clear all cached data

## Data Models

### Station
- ID, name, latitude, longitude, connection count

### Connection
- Origin and destination stations
- Train type and number
- Departure/arrival times
- Travel time in minutes
- Straight-line distance in kilometers
- Aerial speed in km/h
- Platform, delay

### Network Data
- Timestamp
- Origin station
- List of connections
- Statistics (total connections, avg speed, max speed, max distance)

## How Aerial Speed Works

Aerial speed represents how efficiently a train connection covers geographic distance:

```
Aerial Speed (km/h) = (Straight-line Distance / Travel Time) * 60
```

This metric is useful for:
- Identifying fast direct connections
- Comparing route efficiency
- Finding connections that follow straighter paths

## Future Enhancements

- [ ] Fetch destination station coordinates from the backend
- [ ] Support for multi-hop connections (connections of connections)
- [ ] Build complete Germany network map
- [ ] Filter by train type (ICE, IC, RE, etc.)
- [ ] Time-based filtering (morning, afternoon, evening)
- [ ] Historical data tracking
- [ ] Export data to CSV/JSON
- [ ] Automated daily data refresh

## Troubleshooting

### Backend Issues

**"DB_API_KEY is required"**
- Make sure you've created a `.env` file with your API key

**"Station not found"**
- Check the station name spelling
- Try searching for the station first in the DB API

### Frontend Issues

**Map not loading**
- Check that the backend is running on port 8000
- Check browser console for errors
- Ensure Leaflet CSS is loading correctly

**No markers appearing**
- This is expected initially - destination coordinates need to be fetched
- Future enhancement will add this functionality

## License

TBD

## Contributing

This is a personal project, but suggestions and feedback are welcome!
