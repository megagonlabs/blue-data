"""blue-data Registry REST API.

Run:
    # install
    pip install -e ../../lib && pip install -e .

    # start (auto-reload for dev)
    uvicorn registry_api.main:app --reload --port 8000

    # or via the installed script
    blue-data-api

Env vars (same as registry-mcp):
    BLUE_DATA_REGISTRY_STORE, BLUE_DATA_REGISTRY_REDIS_URL, BLUE_DATA_LLM_PROVIDER,
    ANTHROPIC_API_KEY, BLUE_DATA_SOURCES_CONFIG
"""
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI

from registry_api.deps import auth_disabled, require_api_key, require_safe_content_type
from registry_api.routers import records, sources, hierarchy

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from registry_api.config import get_registry
    if not os.environ.get("BLUE_DATA_API_KEY"):
        if auth_disabled():
            logger.warning(
                "BLUE_DATA_API_KEY not set and BLUE_DATA_API_AUTH_DISABLED is on — "
                "the API is running WITHOUT authentication."
            )
        else:
            logger.warning(
                "BLUE_DATA_API_KEY not set — data endpoints will return 401. Set "
                "BLUE_DATA_API_KEY, or BLUE_DATA_API_AUTH_DISABLED=true to disable auth."
            )
    get_registry()
    yield


app = FastAPI(
    title="blue-data Registry API",
    description="REST API for discovering, exploring, and enriching data assets.",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(require_api_key), Depends(require_safe_content_type)],
)

# records router must be registered before sources so /search and /health
# are matched before the /{source_name} parameter route.
app.include_router(records.router)
app.include_router(sources.router)
app.include_router(hierarchy.router)


def run():
    from blue_data.server import resolve_bind
    host, port = resolve_bind("BLUE_DATA_API", default_port=8000)
    uvicorn.run("registry_api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
