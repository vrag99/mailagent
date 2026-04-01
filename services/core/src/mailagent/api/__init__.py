from __future__ import annotations

from fastapi import FastAPI

from ..config import ConfigManager
from ..provisioner import Provisioner
from .auth import create_auth_dependency
from .routes.health import router as health_router
from .routes.inboxes import router as inboxes_router
from .routes.providers import router as providers_router
from .routes.workflows import router as workflows_router
from .routes.emails import router as emails_router


def create_app(
    config_manager: ConfigManager,
    api_keys_path: str | None = None,
    provisioner: Provisioner | None = None,
) -> FastAPI:
    app = FastAPI(
        title="mailagent",
        description="REST API for managing mailagent inboxes, workflows, and providers.",
        version="0.1.0",
    )

    app.state.config_manager = config_manager
    app.state.provisioner = provisioner

    auth = create_auth_dependency(api_keys_path)

    app.include_router(health_router)
    app.include_router(
        inboxes_router,
        prefix="/api/inboxes",
        tags=["inboxes"],
        dependencies=[auth],
    )
    app.include_router(
        workflows_router,
        prefix="/api/inboxes/{inbox_address}/workflows",
        tags=["workflows"],
        dependencies=[auth],
    )
    app.include_router(
        providers_router,
        prefix="/api/providers",
        tags=["providers"],
        dependencies=[auth],
    )
    app.include_router(
        emails_router,
        prefix="/api/emails",
        tags=["emails"],
        dependencies=[auth],
    )

    return app
