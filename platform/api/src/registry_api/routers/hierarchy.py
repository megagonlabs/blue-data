"""Database → Collection → Entity → Attribute / Relation hierarchy endpoints.

All paths nest under /{source_name}/database/{database_name}/...

CRUD pattern per level:
    GET    .../                  list
    GET    .../{name}            get one
    POST   .../{name}            register (with RecordSchema body)
    PUT    .../{name}            update description / properties
    DELETE .../{name}            deregister

Operations:
    PUT    .../{name}/sync       sync from live source
    PUT    .../{name}/stats      collect stats
    PUT    .../{name}/metadata   run MetaData enrichment
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from registry.data_registry import DataRegistry
from registry_api.deps import get_registry
from registry_api.models import RecordSchema

router = APIRouter(tags=["hierarchy"])

_DB   = "/{source_name}/database/{database_name}"
_COL  = _DB  + "/collection/{collection_name}"
_ENT  = _COL + "/entity/{entity_name}"
_ATTR = _ENT + "/attribute/{attribute_name}"
_REL  = _COL + "/relation/{relation_name}"


def _404(label: str):
    raise HTTPException(status_code=404, detail=f"{label} not found")


def _wrap(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# DATABASE
# ===========================================================================

@router.get(_DB + "/collections")
def list_collections(
    source_name: str, database_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    return {"results": registry.list_database_collections(source_name, database_name)}


@router.get(_DB)
def get_database(
    source_name: str, database_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    r = registry.get_source_database(source_name, database_name)
    if r is None:
        _404(f"Database '{database_name}'")
    return {"result": r}


@router.post(_DB)
def register_database(
    source_name: str, database_name: str,
    data: RecordSchema = RecordSchema(),
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.register_source_database,
        source_name, database_name,
        description=data.description,
        properties=data.properties or {},
    )
    return {"message": "Success"}


@router.put(_DB)
def update_database(
    source_name: str, database_name: str,
    data: RecordSchema = RecordSchema(),
    sync: bool = False,
    recursive: bool = False,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.update_source_database,
        source_name, database_name,
        description=data.description,
        properties=data.properties or {},
    )
    if sync:
        _wrap(registry.sync_source_database, source_name, database_name, recursive=recursive)
    return {"message": "Success"}


@router.delete(_DB)
def delete_database(
    source_name: str, database_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    r = registry.get_source_database(source_name, database_name)
    if r is None:
        _404(f"Database '{database_name}'")
    registry.deregister_source_database(source_name, database_name)
    return {"message": "Success"}


@router.put(_DB + "/sync")
def sync_database(
    source_name: str, database_name: str,
    recursive: bool = True,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(registry.sync_source_database, source_name, database_name, recursive=recursive)
    return {"message": "Success"}


@router.put(_DB + "/stats")
def collect_database_stats(
    source_name: str, database_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(registry.collect_source_database_stats, source_name, database_name)
    return {"message": "Success"}


# ===========================================================================
# COLLECTION
# ===========================================================================

@router.get(_COL + "/entities")
def list_entities(
    source_name: str, database_name: str, collection_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    return {"results": registry.list_collection_entities(source_name, database_name, collection_name)}


@router.get(_COL + "/relations")
def list_relations(
    source_name: str, database_name: str, collection_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    return {"results": registry.list_collection_relations(source_name, database_name, collection_name)}


@router.get(_COL)
def get_collection(
    source_name: str, database_name: str, collection_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    r = registry.get_source_database_collection(source_name, database_name, collection_name)
    if r is None:
        _404(f"Collection '{collection_name}'")
    return {"result": r}


@router.post(_COL)
def register_collection(
    source_name: str, database_name: str, collection_name: str,
    data: RecordSchema = RecordSchema(),
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.register_source_database_collection,
        source_name, database_name, collection_name,
        description=data.description,
        properties=data.properties or {},
    )
    return {"message": "Success"}


@router.put(_COL)
def update_collection(
    source_name: str, database_name: str, collection_name: str,
    data: RecordSchema = RecordSchema(),
    sync: bool = False,
    recursive: bool = False,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.update_source_database_collection,
        source_name, database_name, collection_name,
        description=data.description,
        properties=data.properties or {},
    )
    if sync:
        _wrap(registry.sync_source_database_collection, source_name, database_name, collection_name)
    return {"message": "Success"}


@router.delete(_COL)
def delete_collection(
    source_name: str, database_name: str, collection_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    r = registry.get_source_database_collection(source_name, database_name, collection_name)
    if r is None:
        _404(f"Collection '{collection_name}'")
    registry.deregister_source_database_collection(source_name, database_name, collection_name)
    return {"message": "Success"}


@router.put(_COL + "/sync")
def sync_collection(
    source_name: str, database_name: str, collection_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(registry.sync_source_database_collection, source_name, database_name, collection_name)
    return {"message": "Success"}


@router.put(_COL + "/stats")
def collect_collection_stats(
    source_name: str, database_name: str, collection_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.collect_source_database_collection_stats,
        source_name, database_name, collection_name,
    )
    return {"message": "Success"}


@router.put(_COL + "/metadata")
def enrich_collection_metadata(
    source_name: str, database_name: str, collection_name: str,
    rebuild: bool = False,
    registry: DataRegistry = Depends(get_registry),
):
    """Run MetaData enrichment on all entities in this collection."""
    _wrap(
        registry.enrich_source_metadata,
        source_name, recursive=True, rebuild=rebuild,
    )
    return {"message": "Success"}


# ===========================================================================
# ENTITY
# ===========================================================================

@router.get(_ENT + "/attributes")
def list_attributes(
    source_name: str, database_name: str, collection_name: str, entity_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    return {"results": registry.list_entity_attributes(source_name, database_name, collection_name, entity_name)}


@router.get(_ENT)
def get_entity(
    source_name: str, database_name: str, collection_name: str, entity_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    r = registry.get_source_database_collection_entity(
        source_name, database_name, collection_name, entity_name
    )
    if r is None:
        _404(f"Entity '{entity_name}'")
    return {"result": r}


@router.post(_ENT)
def register_entity(
    source_name: str, database_name: str, collection_name: str, entity_name: str,
    data: RecordSchema = RecordSchema(),
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.register_source_database_collection_entity,
        source_name, database_name, collection_name, entity_name,
        description=data.description,
        properties=data.properties or {},
    )
    return {"message": "Success"}


@router.put(_ENT)
def update_entity(
    source_name: str, database_name: str, collection_name: str, entity_name: str,
    data: RecordSchema = RecordSchema(),
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.update_source_database_collection_entity,
        source_name, database_name, collection_name, entity_name,
        description=data.description,
        properties=data.properties or {},
    )
    return {"message": "Success"}


@router.delete(_ENT)
def delete_entity(
    source_name: str, database_name: str, collection_name: str, entity_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    r = registry.get_source_database_collection_entity(
        source_name, database_name, collection_name, entity_name
    )
    if r is None:
        _404(f"Entity '{entity_name}'")
    registry.deregister_source_database_collection_entity(
        source_name, database_name, collection_name, entity_name
    )
    return {"message": "Success"}


@router.put(_ENT + "/sync")
def sync_entity(
    source_name: str, database_name: str, collection_name: str, entity_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.sync_source_database_collection,
        source_name, database_name, collection_name,
    )
    return {"message": "Success"}


@router.put(_ENT + "/stats")
def collect_entity_stats(
    source_name: str, database_name: str, collection_name: str, entity_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.collect_source_database_collection_entity_stats,
        source_name, database_name, collection_name, entity_name,
    )
    return {"message": "Success"}


@router.put(_ENT + "/metadata")
def enrich_entity_metadata(
    source_name: str, database_name: str, collection_name: str, entity_name: str,
    rebuild: bool = False,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(registry.enrich_source_metadata, source_name, recursive=True, rebuild=rebuild)
    return {"message": "Success"}


# ===========================================================================
# ATTRIBUTE
# ===========================================================================

@router.get(_ATTR)
def get_attribute(
    source_name: str, database_name: str, collection_name: str,
    entity_name: str, attribute_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    r = registry.get_source_database_collection_entity_attribute(
        source_name, database_name, collection_name, entity_name, attribute_name
    )
    if r is None:
        _404(f"Attribute '{attribute_name}'")
    return {"result": r}


@router.put(_ATTR)
def update_attribute(
    source_name: str, database_name: str, collection_name: str,
    entity_name: str, attribute_name: str,
    data: RecordSchema = RecordSchema(),
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.update_source_database_collection_entity_attribute,
        source_name, database_name, collection_name, entity_name, attribute_name,
        description=data.description,
        properties=data.properties or {},
    )
    return {"message": "Success"}


@router.delete(_ATTR)
def delete_attribute(
    source_name: str, database_name: str, collection_name: str,
    entity_name: str, attribute_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    r = registry.get_source_database_collection_entity_attribute(
        source_name, database_name, collection_name, entity_name, attribute_name
    )
    if r is None:
        _404(f"Attribute '{attribute_name}'")
    registry.deregister_source_database_collection_entity_attribute(
        source_name, database_name, collection_name, entity_name, attribute_name
    )
    return {"message": "Success"}


@router.put(_ATTR + "/stats")
def collect_attribute_stats(
    source_name: str, database_name: str, collection_name: str,
    entity_name: str, attribute_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.collect_source_database_collection_entity_attribute_stats,
        source_name, database_name, collection_name, entity_name, attribute_name,
    )
    return {"message": "Success"}


@router.put(_ATTR + "/metadata")
def enrich_attribute_metadata(
    source_name: str, database_name: str, collection_name: str,
    entity_name: str, attribute_name: str,
    rebuild: bool = False,
    registry: DataRegistry = Depends(get_registry),
):
    """Run enrichment scoped to this attribute's parent entity."""
    _wrap(registry.enrich_source_metadata, source_name, recursive=True, rebuild=rebuild)
    return {"message": "Success"}


# ===========================================================================
# RELATION
# ===========================================================================

@router.get(_REL)
def get_relation(
    source_name: str, database_name: str, collection_name: str, relation_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    r = registry.get_source_database_collection_relation(
        source_name, database_name, collection_name, relation_name
    )
    if r is None:
        _404(f"Relation '{relation_name}'")
    return {"result": r}


@router.put(_REL + "/sync")
def sync_relation(
    source_name: str, database_name: str, collection_name: str, relation_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(registry.sync_source_database_collection, source_name, database_name, collection_name)
    return {"message": "Success"}


@router.put(_REL + "/stats")
def collect_relation_stats(
    source_name: str, database_name: str, collection_name: str, relation_name: str,
    registry: DataRegistry = Depends(get_registry),
):
    _wrap(
        registry.collect_source_database_collection_entity_stats,
        source_name, database_name, collection_name, relation_name,
    )
    return {"message": "Success"}
