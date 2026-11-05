from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.finalization import router as finalization_router
from app.api.v1.health import router as health_router
from app.api.v1.integration import router as integration_router
from app.api.v1.products import router as products_router
from app.api.v1.result_corrections import router as result_corrections_router
from app.api.v1.scan_sessions import router as scan_sessions_router
from app.api.v1.users import router as users_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(products_router)
router.include_router(integration_router)
router.include_router(result_corrections_router)
router.include_router(scan_sessions_router)
router.include_router(finalization_router)
