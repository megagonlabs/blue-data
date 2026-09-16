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
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from registry_api.routers import records, sources, hierarchy


@asynccontextmanager
async def lifespan(app: FastAPI):
    from registry_api.config import get_registry
    get_registry()
    yield


app = FastAPI(
    title="blue-data Registry API",
    description="REST API for discovering, exploring, and enriching data assets.",
    version="0.1.0",
    lifespan=lifespan,
)

# records router must be registered before sources so /search and /health
# are matched before the /{source_name} parameter route.
app.include_router(records.router)
app.include_router(sources.router)
app.include_router(hierarchy.router)


def run():
    uvicorn.run("registry_api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
