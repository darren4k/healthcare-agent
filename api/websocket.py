"""WebSocket service for real-time automation updates."""
import asyncio
import json
import logging
from typing import Dict, Set, Optional
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self.task_watchers: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: Optional[int] = None):
        """
        Connect a WebSocket client.

        Args:
            websocket: WebSocket connection
            task_id: Optional task ID to watch
        """
        await websocket.accept()
        self.active_connections.add(websocket)

        if task_id is not None:
            if task_id not in self.task_watchers:
                self.task_watchers[task_id] = set()
            self.task_watchers[task_id].add(websocket)

        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, task_id: Optional[int] = None):
        """
        Disconnect a WebSocket client.

        Args:
            websocket: WebSocket connection
            task_id: Optional task ID being watched
        """
        self.active_connections.discard(websocket)

        if task_id is not None and task_id in self.task_watchers:
            self.task_watchers[task_id].discard(websocket)
            if not self.task_watchers[task_id]:
                del self.task_watchers[task_id]

        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_to_task_watchers(self, task_id: int, message: Dict):
        """
        Send message to all clients watching a specific task.

        Args:
            task_id: Task ID
            message: Message to send
        """
        if task_id not in self.task_watchers:
            return

        # Add timestamp
        message["timestamp"] = datetime.utcnow().isoformat()

        disconnected = set()
        for websocket in self.task_watchers[task_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(websocket)

        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket, task_id)

    async def broadcast(self, message: Dict):
        """
        Broadcast message to all connected clients.

        Args:
            message: Message to send
        """
        message["timestamp"] = datetime.utcnow().isoformat()

        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.add(websocket)

        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)

    async def send_task_started(self, task_id: int, patient_id: str, total_steps: int):
        """Send task started event."""
        await self.send_to_task_watchers(task_id, {
            "event": "task_started",
            "task_id": task_id,
            "patient_id": patient_id,
            "total_steps": total_steps,
            "status": "running"
        })

    async def send_step_started(
        self,
        task_id: int,
        step_number: int,
        total_steps: int,
        action: str,
        description: str
    ):
        """Send step started event."""
        await self.send_to_task_watchers(task_id, {
            "event": "step_started",
            "task_id": task_id,
            "step_number": step_number,
            "total_steps": total_steps,
            "action": action,
            "description": description,
            "progress": int((step_number / total_steps) * 100)
        })

    async def send_step_completed(
        self,
        task_id: int,
        step_number: int,
        total_steps: int,
        screenshot_url: Optional[str] = None
    ):
        """Send step completed event."""
        await self.send_to_task_watchers(task_id, {
            "event": "step_completed",
            "task_id": task_id,
            "step_number": step_number,
            "total_steps": total_steps,
            "screenshot_url": screenshot_url,
            "progress": int((step_number / total_steps) * 100)
        })

    async def send_step_failed(
        self,
        task_id: int,
        step_number: int,
        error: str,
        screenshot_url: Optional[str] = None
    ):
        """Send step failed event."""
        await self.send_to_task_watchers(task_id, {
            "event": "step_failed",
            "task_id": task_id,
            "step_number": step_number,
            "error": error,
            "screenshot_url": screenshot_url
        })

    async def send_task_completed(
        self,
        task_id: int,
        success: bool,
        confidence: int,
        emr_url: Optional[str] = None,
        video_url: Optional[str] = None,
        trace_url: Optional[str] = None
    ):
        """Send task completed event."""
        await self.send_to_task_watchers(task_id, {
            "event": "task_completed",
            "task_id": task_id,
            "success": success,
            "confidence": confidence,
            "emr_url": emr_url,
            "video_url": video_url,
            "trace_url": trace_url,
            "status": "completed" if success else "failed"
        })

    async def send_recovery_started(
        self,
        task_id: int,
        attempt: int,
        strategy: str,
        reason: str
    ):
        """Send error recovery started event."""
        await self.send_to_task_watchers(task_id, {
            "event": "recovery_started",
            "task_id": task_id,
            "attempt": attempt,
            "strategy": strategy,
            "reason": reason
        })


# Global connection manager
ws_manager = ConnectionManager()
