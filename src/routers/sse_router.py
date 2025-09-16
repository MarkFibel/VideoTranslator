import logging
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

from ..services.sse_service import sse_service

router = APIRouter(prefix='/events', tags=["sse"])
logger = logging.getLogger(__name__)


@router.get("/stream")
async def sse_stream(
    request: Request,
    client_id: str = Query(None, description="Optional client ID for the SSE connection")
) -> StreamingResponse:
    """
    Establish Server-Sent Events connection for real-time updates
    
    Args:
        request: FastAPI request object
        client_id: Optional client identifier. If not provided, a UUID will be generated
        
    Returns:
        StreamingResponse: SSE stream for real-time events
    """
    logger.info(f"SSE connection request from client: {client_id or 'auto-generated'}")
    
    try:
        # Create new SSE connection
        final_client_id, connection = sse_service.create_connection(request, client_id)
        
        # Return streaming response
        response = await sse_service.create_stream_response(connection)
        
        logger.info(f"SSE stream established for client: {final_client_id}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to establish SSE connection: {str(e)}", exc_info=True)
        raise


@router.get("/stats")
async def get_sse_stats():
    """Get SSE connection statistics"""
    active_connections = sse_service.get_active_connections_count()
    
    logger.info(f"SSE stats requested: {active_connections} active connections")
    
    return {
        "status": "success",
        "data": {
            "active_connections": active_connections,
            "total_connections": len(sse_service.connections)
        },
        "message": f"Active SSE connections: {active_connections}"
    }


@router.post("/broadcast")
async def broadcast_message(
    event_type: str,
    message: dict
):
    """
    Broadcast a message to all connected SSE clients (for testing/debugging)
    
    Args:
        event_type: Type of the event
        message: Message data to broadcast
    """
    logger.info(f"Broadcasting SSE message: {event_type}")
    
    try:
        await sse_service.broadcast(event_type, message)
        
        return {
            "status": "success",
            "message": f"Message broadcasted to {sse_service.get_active_connections_count()} clients"
        }
        
    except Exception as e:
        logger.error(f"Failed to broadcast SSE message: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Broadcast failed: {str(e)}"
        }