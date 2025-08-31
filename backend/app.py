from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Healthcare Agent API",
    description="Healthcare automation MVP with intelligent workflows and audit capabilities",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

class AppStatus(BaseModel):
    status: str
    message: str
    timestamp: str
    version: str
    environment: str

@app.get("/", response_model=AppStatus)
async def root():
    """Root endpoint that returns the application status."""
    return AppStatus(
        status="healthy",
        message="Healthcare Agent API is running successfully",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        environment=os.getenv("ENVIRONMENT", "development")
    )

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True if os.getenv("ENVIRONMENT") == "development" else False
    )
