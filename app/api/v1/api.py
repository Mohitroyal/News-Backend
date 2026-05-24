from fastapi import APIRouter
from app.api.v1.endpoints import generate, auth, upload, subscriptions

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(generate.router, prefix="/generate", tags=["generation"])
api_router.include_router(upload.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])

