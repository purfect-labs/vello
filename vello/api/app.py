import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vello.database import init_db
from vello.api.routes.auth import router as auth_router
from vello.api.routes.dialogue import router as dialogue_router
from vello.api.routes.life_context import router as context_router
from vello.api.routes.contacts import router as contacts_router
from vello.api.routes.routines import router as routines_router
from vello.api.routes.zones import router as zones_router
from vello.api.routes.inferences import router as inferences_router
from vello.api.routes.kortex_sync import router as kortex_router
from vello.api.routes.signals import router as signals_router
from vello.api.routes.temporal import router as temporal_router
from vello.api.routes.gaps import router as gaps_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Vello API",
        version="0.1.0",
        description="Personal life agent",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
    )

    cors_origins = [
        o.strip()
        for o in os.environ.get("CORS_ORIGIN", "http://localhost:5174").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(auth_router,        prefix="/api/v1/auth",       tags=["auth"])
    app.include_router(dialogue_router,    prefix="/api/v1/dialogue",   tags=["dialogue"])
    app.include_router(context_router,     prefix="/api/v1/context",    tags=["context"])
    app.include_router(contacts_router,    prefix="/api/v1/contacts",   tags=["contacts"])
    app.include_router(routines_router,    prefix="/api/v1/routines",   tags=["routines"])
    app.include_router(zones_router,       prefix="/api/v1/zones",      tags=["zones"])
    app.include_router(inferences_router,  prefix="/api/v1/inferences", tags=["inferences"])
    app.include_router(kortex_router,      prefix="/api/v1/kortex",     tags=["kortex"])
    app.include_router(signals_router,     prefix="/api/v1/signals",    tags=["signals"])
    app.include_router(temporal_router,    prefix="/api/v1/temporal",   tags=["temporal"])
    app.include_router(gaps_router,        prefix="/api/v1/gaps",       tags=["gaps"])

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok"}

    return app
