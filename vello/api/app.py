import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vello.database import init_db
from vello.logging_config import (
    BodySizeLimitMiddleware,
    RequestLoggingMiddleware,
    setup_logging,
)
from vello.scheduler import start_scheduler, stop_scheduler
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
from vello.api.routes.briefing import router as briefing_router
from vello.api.routes.webhook import router as webhook_router
from vello.api.routes.waitlist import router as waitlist_router
from vello.api.routes.hypotheses import router as hypotheses_router
from vello.api.routes.household import router as household_router
from vello.api.routes.world import router as world_router
from vello.api.routes.lists import router as lists_router
from vello.api.routes.inventory import router as inventory_router
from vello.api.routes.drafts import router as drafts_router
from vello.api.routes.agent import router as agent_router
from vello.api.routes.playbooks import router as playbooks_router
from vello.api.routes.integrations import router as integrations_router
from vello.api.routes.push import router as push_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from vello.config import validate_config
    setup_logging()
    validate_config()
    init_db()
    from vello.agent.playbooks import seed_builtins
    seed_builtins()
    start_scheduler()
    yield
    stop_scheduler()


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
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
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
    app.include_router(briefing_router,    prefix="/api/v1/briefing",   tags=["briefing"])
    app.include_router(webhook_router,     prefix="/api/v1/webhook",    tags=["webhook"])
    app.include_router(waitlist_router,    prefix="/api/v1",            tags=["waitlist"])
    app.include_router(hypotheses_router,  prefix="/api/v1/hypotheses", tags=["hypotheses"])
    app.include_router(household_router,   prefix="/api/v1/household",  tags=["household"])
    app.include_router(world_router,       prefix="/api/v1/world",      tags=["world"])
    app.include_router(lists_router,       prefix="/api/v1/lists",      tags=["lists"])
    app.include_router(inventory_router,   prefix="/api/v1/inventory",  tags=["inventory"])
    app.include_router(drafts_router,      prefix="/api/v1/drafts",     tags=["drafts"])
    app.include_router(agent_router,       prefix="/api/v1/agent",      tags=["agent"])
    app.include_router(playbooks_router,    prefix="/api/v1/playbooks",     tags=["playbooks"])
    app.include_router(integrations_router, prefix="/api/v1/integrations",  tags=["integrations"])
    app.include_router(push_router,         prefix="/api/v1/push",           tags=["push"])

    @app.get("/health", include_in_schema=False)
    async def health():
        from vello.database import get_connection
        try:
            conn = get_connection()
            conn.execute("SELECT 1").fetchone()
            conn.close()
            return {"status": "ok"}
        except Exception as exc:
            return JSONResponse({"status": "error", "detail": str(exc)}, status_code=503)

    return app
