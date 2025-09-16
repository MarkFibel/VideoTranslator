import asyncio
import logging
import json
from typing import Dict, Optional, Any
from fastapi import Request
from fastapi.responses import StreamingResponse
import uuid

logger = logging.getLogger(__name__)


class SSEConnection:
    """Represents a single SSE connection"""
    def __init__(self, client_id: str, request: Request):
        self.client_id = client_id
        self.request = request
        self.queue: asyncio.Queue = asyncio.Queue()
        self.is_active = True
        logger.info(f"SSE connection created for client: {client_id}")

    async def send_message(self, event_type: str, data: Any):
        """Send a message to this connection"""
        if not self.is_active:
            logger.warning(f"Attempt to send message to inactive connection: {self.client_id}")
            return
        
        message = {
            "event": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        try:
            await self.queue.put(message)
            logger.debug(f"Message queued for client {self.client_id}: {event_type}")
        except Exception as e:
            logger.error(f"Failed to queue message for client {self.client_id}: {str(e)}")
            self.is_active = False

    async def close(self):
        """Close the connection"""
        self.is_active = False
        # Send a close signal to the queue
        await self.queue.put(None)
        logger.info(f"SSE connection closed for client: {self.client_id}")


class SSEService:
    """Service for managing Server-Sent Events connections"""
    
    def __init__(self):
        self.connections: Dict[str, SSEConnection] = {}
        self.client_mapping: Dict[str, str] = {}  # Maps secondary client_id to primary client_id
        logger.info("SSE Service initialized")

    def create_connection(self, request: Request, client_id: Optional[str] = None) -> tuple[str, SSEConnection]:
        """Create a new SSE connection"""
        if client_id is None:
            client_id = str(uuid.uuid4())
        
        # Remove existing connection if it exists
        if client_id in self.connections:
            asyncio.create_task(self.connections[client_id].close())
            del self.connections[client_id]
        
        connection = SSEConnection(client_id, request)
        self.connections[client_id] = connection
        
        logger.info(f"SSE connection established for client: {client_id}")
        return client_id, connection

    async def send_to_client(self, client_id: str, event_type: str, data: Any) -> bool:
        """Send a message to a specific client"""
        # Check if client_id is mapped to another client_id
        target_client_id = self.client_mapping.get(client_id, client_id)
        
        if target_client_id not in self.connections:
            logger.warning(f"Attempt to send message to non-existent client: {client_id} (mapped to: {target_client_id})")
            return False
        
        connection = self.connections[target_client_id]
        if not connection.is_active:
            logger.warning(f"Attempt to send message to inactive client: {target_client_id}")
            self.remove_connection(target_client_id)
            return False
        
        await connection.send_message(event_type, data)
        return True

    async def broadcast(self, event_type: str, data: Any):
        """Send a message to all connected clients"""
        disconnected_clients = []
        
        for client_id, connection in self.connections.items():
            if connection.is_active:
                try:
                    await connection.send_message(event_type, data)
                except Exception as e:
                    logger.error(f"Failed to send broadcast to client {client_id}: {str(e)}")
                    disconnected_clients.append(client_id)
            else:
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.remove_connection(client_id)
        
        logger.info(f"Broadcast sent to {len(self.connections) - len(disconnected_clients)} clients")

    def remove_connection(self, client_id: str):
        """Remove a connection"""
        if client_id in self.connections:
            asyncio.create_task(self.connections[client_id].close())
            del self.connections[client_id]
            logger.info(f"SSE connection removed for client: {client_id}")

    def get_active_connections_count(self) -> int:
        """Get the number of active connections"""
        active_count = sum(1 for conn in self.connections.values() if conn.is_active)
        return active_count

    def map_client_id(self, secondary_id: str, primary_id: str):
        """Map a secondary client ID to a primary client ID"""
        self.client_mapping[secondary_id] = primary_id
        logger.info(f"Client ID mapping created: {secondary_id} -> {primary_id}")

    def unmap_client_id(self, secondary_id: str):
        """Remove client ID mapping"""
        if secondary_id in self.client_mapping:
            primary_id = self.client_mapping.pop(secondary_id)
            logger.info(f"Client ID mapping removed: {secondary_id} -> {primary_id}")

    def get_mapped_client_id(self, client_id: str) -> str:
        """Get the mapped client ID or return the original if no mapping exists"""
        return self.client_mapping.get(client_id, client_id)

    async def create_stream_response(self, connection: SSEConnection) -> StreamingResponse:
        """Create a StreamingResponse for SSE"""
        
        async def event_stream():
            try:
                # Send initial connection confirmation
                yield f"data: {json.dumps({'event': 'connected', 'client_id': connection.client_id})}\n\n"
                
                while connection.is_active:
                    try:
                        # Wait for a message with timeout (increased to 120 seconds)
                        message = await asyncio.wait_for(connection.queue.get(), timeout=120.0)
                        
                        if message is None:  # Close signal
                            break
                        
                        # Format the SSE message
                        event_data = json.dumps(message)
                        yield f"data: {event_data}\n\n"
                        
                    except asyncio.TimeoutError:
                        # Send heartbeat to keep connection alive (every 2 minutes)
                        heartbeat = json.dumps({
                            'event': 'heartbeat', 
                            'timestamp': asyncio.get_event_loop().time(),
                            'client_id': connection.client_id
                        })
                        yield f"data: {heartbeat}\n\n"
                        logger.debug(f"Heartbeat sent to client: {connection.client_id}")
                        
            except Exception as e:
                logger.error(f"Error in SSE stream for client {connection.client_id}: {str(e)}")
            finally:
                connection.is_active = False
                logger.info(f"SSE stream ended for client: {connection.client_id}")

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )


# Global SSE service instance
sse_service = SSEService()