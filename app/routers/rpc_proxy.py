"""
RPC Proxy endpoint for Outlook compatibility
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response
import logging

router = APIRouter()

@router.get("/rpc/rpcproxy.dll")
@router.post("/rpc/rpcproxy.dll")
async def rpc_proxy(request: Request):
    """RPC Proxy endpoint for Outlook RPC over HTTP"""
    logger = logging.getLogger(__name__)
    
    # Log the RPC proxy request
    logger.info(f"RPC Proxy request from {request.client.host if request.client else 'unknown'}")
    
    # Return a basic RPC proxy response
    # This is a simplified implementation - real RPC proxy would handle RPC over HTTP
    return Response(
        status_code=200,
        content="RPC Proxy endpoint active",
        headers={
            "Content-Type": "text/plain",
            "Server": "365-Email-System/1.0"
        }
    )
