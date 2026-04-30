"""WebSocket endpoint for live incident feed"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.repositories.connections import redis_client

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


manager = ConnectionManager()


@router.websocket("/ws/incidents")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Subscribe to Redis pub/sub channels
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("incidents:new", "incidents:update")

        async def listen_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await manager.broadcast(
                        {"channel": message["channel"], "data": data}
                    )

        # Run Redis listener and WebSocket receiver concurrently
        redis_task = asyncio.create_task(listen_redis())

        try:
            while True:
                # Keep connection alive, handle client messages
                data = await websocket.receive_text()
                # Client can send ping/pong
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            redis_task.cancel()
            await pubsub.unsubscribe()

    except Exception:
        pass
    finally:
        manager.disconnect(websocket)
