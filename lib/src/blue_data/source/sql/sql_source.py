import json
import os
import re
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from blue_data.source.source import DataSource


class SQLSource(DataSource, ABC):
    """Base class for SQL data sources."""

    @staticmethod
    def _resolve_env_refs(config: dict) -> dict:
        """Resolve ``<key>_env`` credential references to ``<key>`` from the environment
        and drop the reference, so a stored reference (e.g. ``password_env``) is never
        passed to the DB driver, which rejects it as an unknown connection option (#207).
        Mutates and returns *config*. An explicit base key already present wins."""
        for key in [k for k in config if isinstance(k, str) and k.endswith("_env")]:
            ref = config.pop(key)
            base = key[: -len("_env")]
            if base and base not in config and isinstance(ref, str):
                value = os.environ.get(ref)
                if value is not None:
                    config[base] = value
        return config

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
        # Ops-based interface: {"op": "SQL.QUERY", "query": "..."} or {"op": "SQL.FETCH_ALL"}
        # Unknown ops fall through to the source implementation unchanged.
        if isinstance(query, dict) and "op" in query:
            op = query["op"].upper()
            if op == "SQL.QUERY":
                query = query["query"]
            elif op == "SQL.FETCH_ALL":
                query = None
        if query is None:
            if collection is None:
                raise ValueError("collection is required when query is None")
            query = f"SELECT * FROM {collection}"

        commit = bool(optional_properties.get("commit"))
        write_guard_msg = (
            "Write query executed without commit=True. "
            "Pass optional_properties={'commit': True} to commit writes."
        )

        if not commit and self._is_multi_statement(query):
            raise ValueError(
                "Multiple SQL statements require commit=True. "
                "Pass optional_properties={'commit': True} to execute writes."
            )

        conn = self._db_connect(database)
        cur = conn.cursor()
        try:
            if not commit:
                self._set_read_only(conn)
            try:
                cur.execute(query)
            except Exception as e:
                if not commit and self._is_read_only_error(e):
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    raise ValueError(write_guard_msg) from None
                raise
            result = []
            if cur.description:
                data = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                df = pd.DataFrame(data, columns=columns)
                df.fillna(value=np.nan, inplace=True)
                result = json.loads(df.to_json(orient="records"))
            elif not commit:
                conn.rollback()
                raise ValueError(write_guard_msg)
            if commit:
                conn.commit()
            return result
        finally:
            cur.close()
            self._db_disconnect(conn)

    def _is_multi_statement(self, query) -> bool:
        if not isinstance(query, str):
            return False
        return ";" in query.strip().rstrip(";").rstrip()

    def _set_read_only(self, conn) -> None:
        """Make *conn* reject writes/DDL before the statement runs. Override per dialect."""
        return None

    @staticmethod
    def _is_read_only_error(exc) -> bool:
        msg = str(exc).lower()
        return "readonly" in msg or "read-only" in msg or "read only" in msg

    def get_nl_tools(self, database=None, collection=None):
        tools = super().get_nl_tools(database=database, collection=collection)
        for tool in tools:
            if tool["name"] == "execute_query":
                tool["description"] = (
                    "Execute a SQL SELECT statement against the database and return results. "
                    "Use standard SQL syntax."
                )
        return tools

    def execute_query_nl(self, query, database=None, collection=None, schema=None, llm_fn=None, optional_properties=None, read_only=True):
        """Translate *query* from natural language to SQL and execute it.

        Requires *llm_fn* — raises ``ValueError`` when absent, because SQL
        generation needs an LLM; there is no rule-based fallback.
        The schema prompt lists tables and columns so the LLM can produce
        correct ``SELECT`` statements for this database. Read-only by default;
        pass ``read_only=False`` with ``commit`` to allow writes.
        """
        if llm_fn is None:
            raise ValueError("execute_query_nl requires an llm_fn")
        return super().execute_query_nl(query, database=database, collection=collection, schema=schema, llm_fn=llm_fn, optional_properties=optional_properties, read_only=read_only)

    def _format_schema_for_nl(self, schema: dict | None) -> str:
        if not schema:
            return "(no schema available)"
        lines = []
        for entity in schema.get("entities", []):
            name = entity.get("name", "")
            lines.append(f"Table: {name}")
            for attr_name, attr_props in entity.get("attributes", {}).items():
                col_type = attr_props.get("type", "TEXT") if isinstance(attr_props, dict) else "TEXT"
                vs = attr_props.get("value_semantics", {}) if isinstance(attr_props, dict) else {}
                meta = attr_props.get("metadata", {}) if isinstance(attr_props, dict) else {}
                sem_type = vs.get("semantic_type", "") if vs else ""
                examples = vs.get("examples", []) if vs else []
                description = meta.get("description", "") if meta else ""
                skip_ann = sem_type in ("UNKNOWN", "STRING") or sem_type.upper() == col_type.upper()
                ann = f"; {sem_type}" if sem_type and not skip_ann else ""
                line = f"  - {attr_name} ({col_type}{ann})"
                if description:
                    line += f"  — {description}"
                if examples:
                    sample = ", ".join(str(v) for v in examples[:5])
                    line += f"  [values: {sample}]"
                lines.append(line)
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
