from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.exports import router as exports_router
from app.api.routes.journeys import router as journeys_router
from app.api.routes.map import router as map_router
from app.api.routes.memories import router as memories_router
from app.api.routes.places import router as places_router
from app.api.routes.search import router as search_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(auth_router)
api_router.include_router(exports_router)
api_router.include_router(journeys_router)
api_router.include_router(map_router)
api_router.include_router(memories_router)
api_router.include_router(places_router)
api_router.include_router(search_router)
