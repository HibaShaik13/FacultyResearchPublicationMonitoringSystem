"""Discovery pipeline endpoints."""
from fastapi import APIRouter
router = APIRouter()

@router.get("/runs")
async def list_discovery_runs():
    """List past and current discovery runs."""
    return {"message": "Discovery runs — implemented in Phase 4"}

@router.post("/trigger")
async def trigger_discovery():
    """Manually trigger a discovery sync."""
    return {"message": "Discovery trigger — implemented in Phase 4"}

@router.get("/status")
async def discovery_status():
    """Get current discovery pipeline status."""
    return {"message": "Discovery status — implemented in Phase 4"}
