from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from registry.data_registry import DataRegistry
from registry_api.deps import get_registry

router = APIRouter(tags=["records"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/")
def list_records(
    record_type: Optional[str] = Query(None, alias="type"),
    scope: Optional[str] = None,
    registry: DataRegistry = Depends(get_registry),
):
    """List all registry records, optionally filtered by type and/or scope."""
    results = registry.list_records(record_type=record_type, scope=scope)
    return {"results": results}


@router.get("/search")
def search_records(
    keywords: str = Query(..., alias="q"),
    record_type: Optional[str] = Query(None, alias="type"),
    scope: Optional[str] = None,
    page: int = 0,
    page_size: int = 10,
    registry: DataRegistry = Depends(get_registry),
):
    """Hybrid BM25 + vector search over all registry records."""
    results = registry.search_records(
        keywords, type=record_type, scope=scope, page=page, page_size=page_size
    )
    return {"results": results}


@router.get("/record")
def get_record(
    name: str,
    record_type: str = Query(..., alias="type"),
    scope: str = "",
    registry: DataRegistry = Depends(get_registry),
):
    """Get a specific record by (name, type, scope) identity."""
    result = registry.get_record(name, record_type, scope)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Record '{name}' not found")
    return {"result": result}
