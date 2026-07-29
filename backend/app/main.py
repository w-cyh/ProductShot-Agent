from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import settings
from app.database import Base, engine, ensure_sqlite_compat_schema
from app import models  # noqa: F401
from app.providers.text_provider import ProviderConfigurationError, ProviderRequestError, TextProviderError, TextProviderUnavailable
from app.services import mark_interrupted_generation_tasks


def create_app() -> FastAPI:
    settings.ensure_dirs()
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_compat_schema()
    mark_interrupted_generation_tasks()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
    app.include_router(router)

    @app.exception_handler(ProviderConfigurationError)
    @app.exception_handler(TextProviderUnavailable)
    async def provider_configuration_error(_: Request, exc: TextProviderUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ProviderRequestError)
    @app.exception_handler(TextProviderError)
    async def provider_request_error(_: Request, exc: TextProviderError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
