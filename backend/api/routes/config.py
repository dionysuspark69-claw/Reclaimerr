from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.clients import client_manager
from backend.core.logger import LOG
from backend.core.settings import settings
from backend.database.database import get_db
from backend.database.models import ServiceConfig
from backend.enums import Service
from backend.models.config import ServiceConfigUpdate

router = APIRouter(prefix="/api/config", tags=["Configuration"])


# def get_clients() -> ClientManager:
#     """FastAPI dependency to get ClientManager instance."""
#     from backend.core.clients import get_client_manager
#     return get_client_manager()


# class ClientsStatusResponse(BaseModel):
#     """Response showing which clients are configured and active."""
#     jellyfin: dict[str, bool | str]
#     plex: dict[str, bool | str]
#     radarr: dict[str, bool | str]


# class ReloadResponse(BaseModel):
#     """Response after reloading clients."""
#     success: bool
#     message: str
#     clients_active: dict[str, bool]


# class ServiceConfigUpdate(BaseModel):
#     service_type: Service
#     base_url: str
#     api_key: str
#     enabled: bool


@router.post("/clients/update")
async def update_client_config(
    data: ServiceConfigUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update service configuration and reinitialize client."""
    LOG.info(f"Updating config for {data.service_type}")
    
    # upsert into database
    insert_statement = sqlite_insert(ServiceConfig).values(
        service_type=data.service_type,
        base_url=data.base_url,
        api_key=data.api_key,
        enabled=data.enabled,
    )
    upsert_statement = insert_statement.on_conflict_do_update(
        index_elements=['service_type'],
        set_={
            'base_url': data.base_url,
            'api_key': data.api_key,
            'enabled': data.enabled,
        }
    )
    
    await db.execute(upsert_statement)
    
    # reinitialize the client if needed
    if data.enabled:
        if data.service_type is Service.JELLYFIN:
            client_manager.clear_jellyfin()
            client_manager.initialize_jellyfin(data.base_url, data.api_key)
        elif data.service_type is Service.PLEX:
            client_manager.clear_plex()
            client_manager.initialize_plex(data.base_url, data.api_key)
        elif data.service_type is Service.RADARR:
            client_manager.clear_radarr()
            client_manager.initialize_radarr(data.base_url, data.api_key)
        elif data.service_type is Service.SONARR:
            client_manager.clear_sonarr()
            client_manager.initialize_sonarr(data.base_url, data.api_key)
    else:
        # clear client if disabled
        if data.service_type is Service.JELLYFIN:
            client_manager.clear_jellyfin()
        elif data.service_type is Service.PLEX:
            client_manager.clear_plex()
        elif data.service_type is Service.RADARR:
            client_manager.clear_radarr()
        elif data.service_type is Service.SONARR:
            client_manager.clear_sonarr()
    
    return {"success": True, "message": f"{data.service_type} config updated"}

    # if data.service_type is Service.JELLYFIN:
    #     client_manager.jellyfin.


# @router.get("/clients/status", response_model=ClientsStatusResponse)
# async def get_clients_status(clients: ClientManager = Depends(get_clients)):
#     """Get status of all configured clients."""
#     return ClientsStatusResponse(
#         jellyfin={
#             "configured": bool(settings.jellyfin_api_key),
#             "url": settings.jellyfin_url if settings.jellyfin_api_key else "Not configured",
#             "active": clients._jellyfin is not None,
#         },
#         plex={
#             "configured": bool(settings.plex_token),
#             "url": settings.plex_url if settings.plex_token else "Not configured",
#             "active": clients._plex is not None,
#         },
#         radarr={
#             "configured": bool(settings.radarr_api_key),
#             "url": settings.radarr_url if settings.radarr_api_key else "Not configured",
#             "active": clients._radarr is not None,
#         },
#     )


# @router.post("/clients/reload", response_model=ReloadResponse)
# async def reload_clients(clients: ClientManager = Depends(get_clients)):
#     """Reload all clients after configuration changes.

#     Use this endpoint after updating environment variables or configuration
#     to reinitialize clients with new credentials.
#     """
#     try:
#         LOG.info("Reloading all clients via API request")

#         # Note: For dynamic config reloading, you'll need to implement
#         # a method to reload settings from .env or database
#         # For now, clients will reload from current settings

#         # Reload all clients
#         clients.reload_all()

#         # Check which clients are now active
#         status = {
#             "jellyfin": clients.jellyfin is not None,
#             "plex": clients.plex is not None,
#             "radarr": clients.radarr is not None,
#         }

#         LOG.info(f"Clients reloaded: {status}")

#         return ReloadResponse(
#             success=True,
#             message="All clients reloaded successfully",
#             clients_active=status,
#         )
#     except Exception as e:
#         LOG.error(f"Failed to reload clients: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post("/clients/reload/{client_name}", response_model=ReloadResponse)
# async def reload_specific_client(
#     client_name: str,
#     clients: ClientManager = Depends(get_clients),
# ):
#     """Reload a specific client after configuration changes.

#     Args:
#         client_name: One of 'jellyfin', 'plex', 'radarr'
#     """
#     if client_name not in ["jellyfin", "plex", "radarr"]:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Invalid client name. Must be one of: jellyfin, plex, radarr"
#         )

#     try:
#         LOG.info(f"Reloading {client_name} client via API request")

#         # Reload specific client
#         if client_name == "jellyfin":
#             clients.reload_jellyfin()
#         elif client_name == "plex":
#             clients.reload_plex()
#         elif client_name == "radarr":
#             clients.reload_radarr()

#         # Check status
#         status = {
#             "jellyfin": clients._jellyfin is not None,
#             "plex": clients._plex is not None,
#             "radarr": clients._radarr is not None,
#         }

#         LOG.info(f"{client_name} client reloaded: active={status[client_name]}")

#         return ReloadResponse(
#             success=True,
#             message=f"{client_name} client reloaded successfully",
#             clients_active=status,
#         )
#     except Exception as e:
#         LOG.error(f"Failed to reload {client_name} client: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
