"""
Main entry point for the train network visualization backend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import config
from api.routes import router as api_router

# Validate configuration on startup
config.validate()

app = FastAPI(
    title="Train Network Visualization API",
    description="API for visualizing train network connections from Essen HBF",
    version="0.1.0"
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Train Network Visualization API",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
