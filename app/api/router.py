from fastapi import APIRouter
from api.routers import speaking, writing

api_router = APIRouter()
api_router.include_router(speaking.router)
api_router.include_router(writing.router)
