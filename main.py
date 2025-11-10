"""Main FastAPI application for Agentic SOAP Note System."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from pathlib import Path

from core.config import settings
from core.schema import HealthCheckResponse
from database.session import init_db
from api.intake import router as intake_router
from api.feedback import router as feedback_router
from api.websocket import ws_manager

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize database
    try:
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("👋 Shutting down application")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered SOAP note drafting system with browser automation",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(intake_router)
app.include_router(feedback_router)

# Mount static directories for screenshots, videos, and traces
logs_dir = Path("data/logs")
if logs_dir.exists():
    app.mount("/screenshots", StaticFiles(directory=str(logs_dir / "screenshots")), name="screenshots")
    app.mount("/videos", StaticFiles(directory=str(logs_dir / "videos")), name="videos")
    app.mount("/traces", StaticFiles(directory=str(logs_dir / "traces")), name="traces")


@app.get("/", response_model=HealthCheckResponse)
async def root():
    """Root endpoint - health check."""
    return HealthCheckResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENV,
        timestamp=datetime.utcnow()
    )


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return HealthCheckResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENV,
        timestamp=datetime.utcnow()
    )


@app.websocket("/ws/tasks/{task_id}")
async def websocket_task_updates(websocket: WebSocket, task_id: int):
    """
    WebSocket endpoint for real-time task updates.

    Args:
        websocket: WebSocket connection
        task_id: Task ID to watch
    """
    await ws_manager.connect(websocket, task_id)

    try:
        # Send initial connection message
        await websocket.send_json({
            "event": "connected",
            "task_id": task_id,
            "message": "Connected to task updates"
        })

        # Keep connection alive
        while True:
            # Wait for messages from client (ping/pong)
            data = await websocket.receive_text()

            # Echo back for keep-alive
            if data == "ping":
                await websocket.send_json({"event": "pong"})

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, task_id)
        logger.info(f"Client disconnected from task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket, task_id)


@app.websocket("/ws/tasks")
async def websocket_all_tasks(websocket: WebSocket):
    """
    WebSocket endpoint for all task updates.

    Args:
        websocket: WebSocket connection
    """
    await ws_manager.connect(websocket)

    try:
        # Send initial connection message
        await websocket.send_json({
            "event": "connected",
            "message": "Connected to all task updates"
        })

        # Keep connection alive
        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"event": "pong"})

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("Client disconnected from all tasks")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
