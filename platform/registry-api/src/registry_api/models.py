from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel

JSONObject = Dict[str, Any]


class RecordSchema(BaseModel):
    """Body for create / update record endpoints."""
    description: Optional[str] = None
    icon: Optional[Union[str, dict]] = None
    properties: Optional[JSONObject] = None


class QueryRequest(BaseModel):
    query: str
    database: Optional[str] = None
    collection: Optional[str] = None
    commit: bool = False
