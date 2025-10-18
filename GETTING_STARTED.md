# Getting Started - Train Network Speed Map

Quick start guide to get the application running on your local machine.

## Quick Start (5 minutes)

### Step 1: Get a Deutsche Bahn API Key

1. Go to https://developers.deutschebahn.com/
2. Create an account or sign in
3. Subscribe to the "Timetables" API
4. Copy your API key

### Step 2: Set Up the Backend

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file in the project root
cd ..
cp .env.example .env

# Edit .env and add your API key
# DB_API_KEY=your_actual_api_key_here
```

### Step 3: Set Up the Frontend

```bash
# Navigate to frontend directory (in a new terminal)
cd frontend

# Install dependencies
npm install
```

### Step 4: Run the Application

```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
python main.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

### Step 5: Open the Application

1. Open your browser to http://localhost:3000
2. Click "Load Essen Hbf Network"
3. Wait for the data to load (first fetch can take 1-2 minutes)
4. Explore the map!

## What You'll See

### Initial Screen
- Left sidebar with filters and statistics (empty initially)
- Large map view area with a "Load Network" button

### After Loading Data
- **Map**: Geographic visualization of train connections
  - Lines from Essen Hbf to destination stations
  - Color-coded by aerial speed (red=slow, green=fast)
  - Click markers for connection details

- **Sidebar Statistics**:
  - Total connections count
  - Average aerial speed
  - Maximum speed
  - Maximum distance

- **Filters**:
  - Minimum speed slider - filter out slower connections
  - Direct connections toggle (currently always ON)

## Understanding Aerial Speed

Aerial speed is calculated as:
```
Aerial Speed = (Straight-line Distance / Travel Time) × 60
```

**Example:**
- Berlin to Munich: 504 km straight-line distance
- ICE train: 4 hours = 240 minutes
- Aerial Speed: (504 / 240) × 60 = 126 km/h

This is different from actual train speed because:
- Trains follow tracks, not straight lines
- Includes station stops
- Includes acceleration/deceleration

**High aerial speed = efficient, direct route**

## Common Questions

### Why is the initial data fetch slow?
The Deutsche Bahn API can be slow to respond. The first fetch for a station queries:
1. Station information
2. Departure board (all trains)
3. Journey details for each train (to get final destination and arrival time)

Once cached, subsequent loads are instant.

### Why don't I see destination markers on the map?
Currently, the backend doesn't return destination station coordinates. This is a known limitation and will be added in a future update. For now, you'll see:
- Origin station marker (Essen Hbf)
- Statistics in the sidebar
- Connection data (when you check the browser console)

### How do I fetch data for a different station?
Currently, Essen Hbf is hardcoded as the default. To add support for custom stations:
1. Modify the FilterPanel component to accept user input
2. Pass the station name to the fetchNetwork function

This feature is planned for a future update.

### How often should I refresh the data?
The backend caches data for 24 hours by default. You can:
- Click "Refresh Data" to force a new fetch
- Use the API endpoint `DELETE /api/cache/{station_id}` to clear cache
- Check cached data timestamp in the sidebar

## Troubleshooting

### Backend won't start
```
Error: DB_API_KEY is required
```
**Solution**: Make sure you created a `.env` file in the project root with your API key.

### Frontend shows "Failed to fetch network data"
**Solution**: Check that:
1. Backend is running on port 8000
2. You can access http://localhost:8000/health
3. No firewall is blocking the connection

### Map doesn't load
**Solution**: Check browser console for errors. Common issues:
- Leaflet CSS not loading
- JavaScript errors in components
- Try refreshing the page

### Data fetch takes forever
The Deutsche Bahn API can be slow. If it's taking more than 3 minutes:
1. Check your internet connection
2. Try again (API might be having issues)
3. Check the backend logs for errors

## Next Steps

### Explore the API Documentation
Visit http://localhost:8000/docs to see:
- All available endpoints
- Request/response schemas
- Try out API calls directly

### Check the Data
Look at cached data in `backend/data/`:
```bash
ls backend/data/
cat backend/data/network_*.json | jq .
```

### Modify the Code
Some ideas to try:
1. Change the default station name
2. Adjust the speed color gradient
3. Add more filters (train type, time of day)
4. Fetch and display destination coordinates

## Resources

- [Deutsche Bahn API Docs](https://developers.deutschebahn.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Leaflet Documentation](https://leafletjs.com/)
- [React Leaflet Documentation](https://react-leaflet.js.org/)

## Support

For issues, questions, or suggestions:
1. Check the main README.md
2. Review the API documentation at /docs
3. Look at the code comments
4. Open an issue in the repository (if applicable)

Happy exploring! 🚄
