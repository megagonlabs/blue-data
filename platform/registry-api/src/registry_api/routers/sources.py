"""Source-level endpoints.

Paths:
    GET    /sources
    GET    /{source_name}
    DELETE /{source_name}

    GET    /{source_name}/properties
    GET    /{source_name}/property/{property_name}
    POST   /{source_name}/property/{property_name}
    DELETE /{source_name}/property/{property_name}

    PUT    /{source_name}/sync
    PUT    /{source_name}/stats
    PUT    /{source_name}/enrich
    PUT    /{source_name}/metadata

    POST   /{source_name}/connect
    POST   /{source_name}/query

    GET    /{source_name}/databases
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from blue_data.registry.data_registry import DataRegistry
from registry_api.deps import get_registry
from registry_api.models import QueryRequest

router = APIRouter(tags=["sources"])


def _require_source(registry: DataRegistry, source_name: str) -> dict:
    source = registry.connect_source(source_name)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
    return source


# ---------------------------------------------------------------------------
# Source records
# ---------------------------------------------------------------------------

@router.get("/sources")
def list_sources(registry: DataRegistry = Depends(get_registry)):
    return {"results": registry.list_sources()}


@router.get("/{source_name}")
def get_source(source_name: str, registry: DataRegistry = Depends(get_registry)):
    _require_source(registry, source_name)
    return {"result": registry.get_source_record(source_name)}


@router.delete("/{source_name}")
def delete_source(source_name: str, registry: DataRegistry = Depends(get_registry)):
    _require_source(registry, source_name)
    registry.deregister_source(source_name)
    return {"message": "Success"}


# ---------------------------------------------------------------------------
# Source properties
# ---------------------------------------------------------------------------

@router.get("/{source_name}/properties")
def get_source_properties(source_name: str, registry: DataRegistry = Depends(get_registry)):
    _require_source(registry, source_name)
    return {"results": registry.get_source_properties(source_name)}


@router.get("/{source_name}/property/{property_name}")
def get_source_property(
    source_name: str, property_name: str, registry: DataRegistry = Depends(get_registry)
):
    _require_source(registry, source_name)
    return {"result": registry.get_source_property(source_name, property_name)}


@router.post("/{source_name}/property/{property_name}")
def set_source_property(
    source_name: str,
    property_name: str,
    value: Any,
    registry: DataRegistry = Depends(get_registry),
):
    _require_source(registry, source_name)
    registry.set_source_property(source_name, property_name, value, rebuild=True)
    return {"message": "Success"}


@router.delete("/{source_name}/property/{property_name}")
def delete_source_property(
    source_name: str, property_name: str, registry: DataRegistry = Depends(get_registry)
):
    _require_source(registry, source_name)
    registry.delete_source_property(source_name, property_name, rebuild=True)
    return {"message": "Success"}


# ---------------------------------------------------------------------------
# Source operations
# ---------------------------------------------------------------------------

@router.put("/{source_name}/sync")
def sync_source(
    source_name: str,
    recursive: bool = True,
    registry: DataRegistry = Depends(get_registry),
):
    """Sync registry records from the live source."""
    _require_source(registry, source_name)
    try:
        registry.sync_source(source_name, recursive=recursive)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Success"}


@router.put("/{source_name}/stats")
def collect_source_stats(
    source_name: str,
    recursive: bool = True,
    registry: DataRegistry = Depends(get_registry),
):
    """Collect statistics from the live source."""
    _require_source(registry, source_name)
    try:
        registry.collect_source_stats(source_name, recursive=recursive)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Success"}


@router.put("/{source_name}/enrich")
def enrich_source(source_name: str, registry: DataRegistry = Depends(get_registry)):
    """Run deterministic semantic type inference on all attributes."""
    _require_source(registry, source_name)
    try:
        registry.enrich_source(source_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Success"}


@router.put("/{source_name}/metadata")
def enrich_source_metadata(
    source_name: str,
    recursive: bool = True,
    rebuild: bool = False,
    registry: DataRegistry = Depends(get_registry),
):
    """Run the full MetaData enrichment pipeline."""
    _require_source(registry, source_name)
    try:
        registry.enrich_source_metadata(source_name, recursive=recursive, rebuild=rebuild)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Success"}


# ---------------------------------------------------------------------------
# Connect and query
# ---------------------------------------------------------------------------

@router.post("/{source_name}/connect")
def connect_source(source_name: str, registry: DataRegistry = Depends(get_registry)):
    """Lazily connect a source from its stored registry properties."""
    _require_source(registry, source_name)
    try:
        source_instance = registry.connect_source(source_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not source_instance:
        raise HTTPException(
            status_code=422,
            detail=f"Source '{source_name}' has no connection properties or uses an unsupported protocol.",
        )
    source_tree: dict = {}
    try:
        for db in source_instance.fetch_databases():
            source_tree[db] = {}
            for col in source_instance.fetch_database_collections(db):
                entities = source_instance.fetch_database_collection_entities(db, col)
                source_tree[db][col] = list(entities.keys())
    except Exception:
        pass
    return {"result": {"type": type(source_instance).__name__, "source_tree": source_tree}}


@router.post("/{source_name}/query")
def execute_query(
    source_name: str,
    payload: QueryRequest,
    registry: DataRegistry = Depends(get_registry),
):
    """Execute a query against a live source."""
    _require_source(registry, source_name)
    try:
        results = registry.execute_query(
            source=source_name,
            query=payload.query,
            database=payload.database,
            collection=payload.collection,
            optional_properties={"commit": True},
        )
        return {"results": results or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Database listing (convenience shortcut)
# ---------------------------------------------------------------------------

@router.get("/{source_name}/databases")
def list_databases(source_name: str, registry: DataRegistry = Depends(get_registry)):
    _require_source(registry, source_name)
    return {"results": registry.list_source_databases(source_name)}
