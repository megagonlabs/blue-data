from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel

JSONObject = Dict[str, Any]


class RecordSchema(BaseModel):
    """Body for create / update record endpoints."""
    description: Optional[str] = None
    icon: Optional[Union[str, dict]] = None
    properties: Optional[JSONObject] = None


class QueryRequest(BaseModel):
    # str for SQL sources; dict for sources that take JSON ops (doc, kb, web).
    query: Union[str, JSONObject]
    database: Optional[str] = None
    collection: Optional[str] = None
    commit: bool = False
