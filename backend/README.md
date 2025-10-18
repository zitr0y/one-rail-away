# Train Network Visualization System

A backend system for visualizing train network connections from Essen HBF (Hauptbahnhof) using the Deutsche Bahn Timetables API.

## Project Purpose

This project provides a Python-based backend that:
- Fetches train departure data from Essen HBF using the Deutsche Bahn API
- Processes and analyzes train network connections
- Provides data for visualization of the train network radiating from Essen

## Prerequisites

- Python 3.8 or higher
- A Deutsche Bahn API key (obtain from [Deutsche Bahn Developer Portal](https://developers.deutschebahn.com/))

## Setup Instructions

### 1. Clone or navigate to the project directory

```bash
cd de-trains-speed-map
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Configure API credentials

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Edit `.env` and replace `your_api_key_here` with your actual Deutsche Bahn API key:

```
DB_API_KEY=your_actual_api_key_here
```

### 5. Run the application

```bash
cd backend
python main.py
```

## Project Structure

```
de-trains-speed-map/
├── backend/              # Backend application code
│   ├── api/             # API routes and endpoints
│   ├── core/            # Core business logic
│   ├── data/            # Data storage directory (cached data)
│   ├── requirements.txt # Python dependencies
│   ├── config.py        # Configuration management
│   └── main.py          # Application entry point
├── .env.example         # Example environment variables
└── README.md           # This file
```

## Configuration

The application is configured through environment variables:

- `DB_API_KEY` (required): Your Deutsche Bahn API key
- `DB_API_BASE_URL` (optional): Override the default API base URL
- `DATA_DIR` (optional): Directory for storing cached data (defaults to `./data`)

## Development

The project is organized into modular components:

- **api/**: Contains FastAPI routes and endpoint handlers
- **core/**: Contains core business logic for data fetching and processing
- **data/**: Storage location for cached train network data

## License

TBD
