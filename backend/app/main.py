from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.v1.router import router as api_router
from app.core.config import Settings
from app.core.errors import (
    BusinessError,
    business_error_handler,
    request_validation_error_handler,
)
from app.core.trace import TraceIdMiddleware
from app.db.session import create_database_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or Settings()
    app = FastAPI(title="涉案卷烟智能统计系统", version="0.1.0")
    app.add_middleware(TraceIdMiddleware)
    app.add_exception_handler(BusinessError, business_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.state.settings = application_settings
    app.state.engine = create_database_engine(application_settings.database_url)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.include_router(api_router, prefix="/api/v1")
    return app
