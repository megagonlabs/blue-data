import json
import re
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from blue_data.source.source import DataSource


class SQLSource(DataSource, ABC):
    """Base class for SQL data sources."""

    @abstractmethod
    def _db_connect(self, database):
        raise NotImplementedError

    def _db_disconnect(self, connection):
        if connection:
            connection.close()

    def fetch_collection_stats(
        self,
        database,
        collection,
        entities=None,
        relations=None,
        sample_limit=None,
    ):
        return {
            "num_entities": len(entities or []),
            "num_relations": len(relations or []),
        }

    def execute_query(
        self,
        query,
        database=None,
        collection=None,
        optional_properties=None,
    ):
        optional_properties = optional_properties or {}
        if database is None:
            raise Exception("No database provided")
        if query is None:
            if collection is None:
                raise ValueError("collection is required when query is None")
            query = f"SELECT * FROM {collection}"
        conn = self._db_connect(database)
        cur = conn.cursor()
        try:
            cur.execute(query)
            result = []
            if cur.description:
                data = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                df = pd.DataFrame(data, columns=columns)
                df.fillna(value=np.nan, inplace=True)
                result = json.loads(df.to_json(orient="records"))
            if optional_properties.get("commit"):
                conn.commit()
            return result
        finally:
            cur.close()
            self._db_disconnect(conn)

    def execute_query_nl(self, query, database=None, collection=None, schema=None, llm_fn=None, optional_properties=None):
        """Translate *query* from natural language to SQL and execute it.

        Requires *llm_fn* — raises ``ValueError`` when absent, because SQL
        generation needs an LLM; there is no rule-based fallback.
        The schema prompt lists tables and columns so the LLM can produce
        correct ``SELECT`` statements for this database.
        """
        if llm_fn is None:
            raise ValueError("execute_query_nl requires an llm_fn")
        return super().execute_query_nl(query, database=database, collection=collection, schema=schema, llm_fn=llm_fn, optional_properties=optional_properties)

    def _format_schema_for_nl(self, schema: dict | None) -> str:
        if not schema:
            return "(no schema available)"
        lines = []
        for entity in schema.get("entities", []):
            name = entity.get("name", "")
            lines.append(f"Table: {name}")
            for attr_name, attr_props in entity.get("attributes", {}).items():
                col_type = attr_props.get("type", "TEXT") if isinstance(attr_props, dict) else "TEXT"
                lines.append(f"  - {attr_name} ({col_type})")
        return "\n".join(lines) or "(no schema available)"

    def _build_nl_prompt(self, query: str, schema_text: str) -> str:
        return (
            "You are a SQL expert. Convert the natural language query to a valid SQL SELECT statement.\n\n"
            f"Database schema:\n{schema_text}\n\n"
            f"Natural language query: {query}\n\n"
            "Rules:\n"
            "- Return ONLY the SQL query, no explanation or markdown\n"
            "- Use only tables and columns that exist in the schema above\n\n"
            "SQL:"
        )

    def _extract_native_query(self, raw: str) -> str | None:
        raw = re.sub(r"```(?:sql)?\s*", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
        match = re.search(r"(SELECT\b.+)", raw, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return raw or None
