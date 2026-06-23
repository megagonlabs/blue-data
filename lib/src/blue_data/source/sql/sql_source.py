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

    def execute_query_nl(
        self,
        query: str,
        database: str | None = None,
        collection: str | None = None,
        schema: dict | None = None,
        llm_fn=None,
        optional_properties: dict | None = None,
    ) -> list[dict]:
        """Translate *query* from natural language to SQL and execute it.

        Uses *llm_fn* to produce a SELECT statement grounded by *schema*,
        then runs it via ``execute_query``. Raises ``ValueError`` if
        *llm_fn* is not provided.
        """
        if llm_fn is None:
            raise ValueError("execute_query_nl requires an llm_fn")
        sql = self._translate_nl_to_sql(query, schema, llm_fn)
        if not sql:
            return []
        return self.execute_query(
            sql,
            database=database,
            collection=collection,
            optional_properties=optional_properties,
        )

    def _translate_nl_to_sql(self, query: str, schema: dict | None, llm_fn) -> str | None:
        schema_text = self._format_schema_for_sql_prompt(schema)
        prompt = (
            "You are a SQL expert. Convert the natural language query to a valid SQL SELECT statement.\n\n"
            f"Database schema:\n{schema_text}\n\n"
            f"Natural language query: {query}\n\n"
            "Rules:\n"
            "- Return ONLY the SQL query, no explanation or markdown\n"
            "- Use only tables and columns that exist in the schema above\n\n"
            "SQL:"
        )
        raw = llm_fn(prompt)
        return self._extract_sql(raw) if raw else None

    @staticmethod
    def _format_schema_for_sql_prompt(schema: dict | None) -> str:
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

    @staticmethod
    def _extract_sql(raw: str) -> str | None:
        raw = re.sub(r"```(?:sql)?\s*", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
        match = re.search(r"(SELECT\b.+)", raw, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return raw or None
