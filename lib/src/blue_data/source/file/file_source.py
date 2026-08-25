from __future__ import annotations

import json
import re
import os
from typing import Any

import pandas as pd

from blue_data.core.schema import DataSchema
from blue_data.source.source import DataSource

_FORMATS = ("csv", "json", "jsonl", "parquet")

# Keys that identify a structured query dict (vs. old equality-filter dict).
_STRUCTURED_KEYS = frozenset(
    {"filter", "group_by", "aggregate", "select", "sort_by", "sort_desc", "limit"}
)


class FileSource(DataSource):
    """DataSource backed by a directory of tabular files (CSV, JSON, JSONL).

    Each file in the directory maps to one collection.  There is no database
    concept — ``database`` is always ``"default"``.
    """

    def __init__(self, name: str, directory: str | None = None, properties: dict | None = None):
        props = dict(properties or {})
        if directory is not None:
            props.setdefault("connection", {})["directory"] = directory
        super().__init__(name, properties=props)
        self._directory = os.path.abspath(self.properties["connection"]["directory"])
        os.makedirs(self._directory, exist_ok=True)

    def _initialize_connection_properties(self) -> None:
        conn = self.properties.get("connection", {})
        conn.setdefault("protocol", "file")
        conn.setdefault("directory", ".")
        self.properties["connection"] = conn

    # ---------- internal helpers ----------

    def _file_path(self, collection: str, fmt: str) -> str:
        return os.path.join(self._directory, f"{collection}.{fmt}")

    def _resolve_file(self, collection: str) -> tuple[str, str]:
        """Return (path, format) for *collection*, trying each supported format."""
        for fmt in _FORMATS:
            path = self._file_path(collection, fmt)
            if os.path.exists(path):
                return path, fmt
        raise FileNotFoundError(
            f"No file found for collection '{collection}' in {self._directory}"
        )

    def _read_file(self, path: str, fmt: str) -> list[dict]:
        if fmt == "csv":
            try:
                return pd.read_csv(path).to_dict(orient="records")
            except pd.errors.EmptyDataError:
                return []
        if fmt == "json":
            with open(path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else [data]
        if fmt == "jsonl":
            with open(path) as f:
                return [json.loads(line) for line in f if line.strip()]
        if fmt == "parquet":
            return pd.read_parquet(path).to_dict(orient="records")
        return []

    def _infer_python_type(self, value) -> str:
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        return "str"

    # ---------- DataSource interface ----------

    def fetch_databases(self) -> list[str]:
        return ["default"]

    def fetch_database_collections(self, database: str) -> list[str]:
        seen = set()
        for fname in os.listdir(self._directory):
            for fmt in _FORMATS:
                if fname.endswith(f".{fmt}"):
                    seen.add(fname[: -(len(fmt) + 1)])
        return sorted(seen)

    def fetch_database_collection_metadata(self, database: str, collection: str) -> dict:
        try:
            path, fmt = self._resolve_file(collection)
            return {"format": fmt, "size_bytes": os.path.getsize(path)}
        except FileNotFoundError:
            return {}

    def fetch_database_collection_entities(self, database: str, collection: str) -> dict:
        try:
            path, fmt = self._resolve_file(collection)
        except FileNotFoundError:
            return {}
        rows = self._read_file(path, fmt)
        if not rows:
            return {}
        schema = DataSchema()
        schema.add_entity(collection)
        for key, value in rows[0].items():
            schema.add_entity_attribute(collection, key, self._infer_python_type(value))
        return schema.get_entities()

    def _apply_structured_query(self, df: "pd.DataFrame", q: dict) -> list[dict]:
        """Apply a structured query dict to *df* and return matching records."""
        # 1. filter (pandas query expression string)
        filter_expr = q.get("filter")
        if filter_expr and isinstance(filter_expr, str):
            df = df.query(filter_expr)

        # 2. group_by + aggregate
        group_by = q.get("group_by")
        agg = q.get("aggregate")

        if agg is not None:
            if group_by is not None:
                cols = [group_by] if isinstance(group_by, str) else list(group_by)
                df = df.groupby(cols).agg(agg).reset_index()
            else:
                # whole-table aggregation → single-row result
                row: dict = {}
                if isinstance(agg, dict):
                    for col, func in agg.items():
                        if col not in df.columns:
                            continue
                        fn = "mean" if func == "avg" else func
                        if func == "count":
                            row[f"count_{col}"] = int(df[col].count())
                        elif fn in ("sum", "mean", "min", "max"):
                            row[f"{func}_{col}"] = float(getattr(df[col], fn)())
                elif isinstance(agg, str):
                    func = agg.strip()
                    if func == "count":
                        row = {"count": len(df)}
                return [row] if row else []

        # 3. select
        select = q.get("select")
        if select:
            cols = [c for c in select if c in df.columns]
            if cols:
                df = df[cols]

        # 4. sort
        sort_by = q.get("sort_by")
        if sort_by:
            sort_cols = [sort_by] if isinstance(sort_by, str) else list(sort_by)
            valid = [c for c in sort_cols if c in df.columns]
            if valid:
                df = df.sort_values(valid, ascending=not q.get("sort_desc", False))

        # 5. limit
        limit = q.get("limit")
        if limit:
            df = df.head(int(limit))

        return df.to_dict(orient="records")

    def execute_query(
        self,
        query: Any,
        database: str | None = None,
        collection: str | None = None,
        optional_properties: dict | None = None,
    ) -> list[dict]:
        """Return rows from *collection*.

        ``query`` can be:
        - ``{"op": "FILE.READ"}``                       — return all rows
        - ``{"op": "FILE.FIND", "filter": {...}}``      — structured or equality filter
        - ``None``                                       — return all rows (deprecated)
        - ``str``                                        — JSON-encoded dict (deprecated)
        - ``dict`` without ``"op"``                      — legacy equality / structured filter (deprecated)

        Structured filter keys: ``filter`` (pandas query string), ``group_by``,
        ``aggregate`` (dict of ``{col: func}`` where func is count/sum/mean/min/max),
        ``select``, ``sort_by``, ``sort_desc``, ``limit``.
        """
        if collection is None:
            raise ValueError("collection is required for FileSource.execute_query")
        try:
            path, fmt = self._resolve_file(collection)
        except FileNotFoundError:
            return []
        rows = self._read_file(path, fmt)

        # Ops-based interface.
        if isinstance(query, dict) and "op" in query:
            op = query["op"].upper()
            if op == "FILE.READ":
                return rows
            elif op == "FILE.FIND":
                query = query.get("filter")
                if query is None:
                    return rows
            else:
                raise ValueError(f"Unknown FILE op: {query['op']!r}")

        if query is None:
            return rows

        # Normalise string → dict when it looks like JSON.
        if isinstance(query, str):
            stripped = query.strip()
            if stripped.startswith("{"):
                try:
                    query = json.loads(stripped)
                except json.JSONDecodeError:
                    pass

        if isinstance(query, dict):
            if query.keys() & _STRUCTURED_KEYS:
                if not rows:
                    return []
                return self._apply_structured_query(pd.DataFrame(rows), query)
            # Legacy equality filter.
            rows = [r for r in rows if all(r.get(k) == v for k, v in query.items())]

        return rows

    def fetch_source_stats(self) -> dict:
        collections = self.fetch_database_collections("default")
        total_bytes = 0
        for c in collections:
            try:
                path, _ = self._resolve_file(c)
                total_bytes += os.path.getsize(path)
            except FileNotFoundError:
                pass
        return {"total_collections": len(collections), "total_bytes": total_bytes}

    def fetch_entity_stats(
        self,
        database: str,
        collection: str,
        entity: str,
        row_sample_size: int = 10,
    ) -> dict:
        try:
            path, fmt = self._resolve_file(collection)
            rows = self._read_file(path, fmt)
        except FileNotFoundError:
            return {
                "row_count": 0,
                "row_samples": [],
                "row_sample_size": 0,
                "row_samples_aligned": False,
            }
        sample = rows[:row_sample_size]
        return {
            "row_count": len(rows),
            "row_samples": sample,
            "row_sample_size": len(sample),
            "row_samples_aligned": len(rows) >= 2,
        }

    def fetch_property_stats(
        self,
        database: str,
        collection: str,
        entity: str,
        property_name: str,
        sample_limit: int | None = None,
    ) -> dict:
        try:
            path, fmt = self._resolve_file(collection)
            rows = self._read_file(path, fmt)
        except FileNotFoundError:
            return {}
        if not rows:
            return {}
        values = [r.get(property_name) for r in rows]
        non_null = [v for v in values if v is not None]
        limit = sample_limit or 10
        seen: dict = {}
        for v in non_null:
            k = str(v)
            if k not in seen:
                seen[k] = v
            if len(seen) >= limit:
                break
        sample_values = list(seen.values())
        result: dict = {
            "total_count": len(values),
            "null_count": len(values) - len(non_null),
            "distinct_count": len({str(v) for v in non_null}),
            "sample_values": sample_values,
        }
        numeric = [v for v in non_null if isinstance(v, (int, float))]
        if numeric:
            result["min"] = min(numeric)
            result["max"] = max(numeric)
        return result

    # ---------- NL2Q ----------

    def _format_schema_for_nl(self, schema: dict | None) -> str:
        if not schema:
            return "(no schema available)"
        lines = []
        for entity in schema.get("entities", []):
            name = entity.get("name", "")
            lines.append(f"File: {name}")
            for attr_name, attr_props in entity.get("attributes", {}).items():
                col_type = attr_props.get("type", "str") if isinstance(attr_props, dict) else "str"
                vs = attr_props.get("value_semantics", {}) if isinstance(attr_props, dict) else {}
                sem_type = vs.get("semantic_type", "") if vs else ""
                examples = vs.get("examples", []) if vs else []
                skip_ann = sem_type in ("UNKNOWN", "STRING") or sem_type.upper() == col_type.upper()
                ann = f"; {sem_type}" if sem_type and not skip_ann else ""
                line = f"  - {attr_name} ({col_type}{ann})"
                if examples:
                    sample = ", ".join(str(v) for v in examples[:5])
                    line += f"  [values: {sample}]"
                lines.append(line)
        return "\n".join(lines) or "(no schema available)"

    def _build_nl_prompt(self, query: str, schema_text: str) -> str:
        return (
            "You are a data analyst. Given a file schema, translate the natural language "
            "query into a structured JSON query object.\n\n"
            f"File schema:\n{schema_text}\n\n"
            f"Natural language query: {query}\n\n"
            "Output a JSON object with these optional fields:\n"
            '  "filter"    : pandas query expression string (e.g. "age > 30 and country == \'USA\'")\n'
            '  "group_by"  : column name or list of column names to group by\n'
            '  "aggregate" : dict mapping column → function (count / sum / mean / min / max)\n'
            '  "select"    : list of column names to return\n'
            '  "sort_by"   : column name to sort by\n'
            '  "sort_desc" : true for descending order (default false)\n'
            '  "limit"     : maximum number of rows to return\n\n'
            "Rules:\n"
            "- For simple row retrieval use \"filter\" only.\n"
            "- For whole-table aggregations (count, sum, …) use \"aggregate\" without \"group_by\".\n"
            "- For grouped aggregations use both \"group_by\" and \"aggregate\".\n"
            "- Use only columns that exist in the schema.\n"
            "- Return ONLY valid JSON, no explanation or markdown fences.\n\n"
            "JSON:"
        )

    def _extract_native_query(self, raw: str):
        if not raw:
            return None
        cleaned = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return cleaned or None

    def get_nl_tools(self, database: str | None = None, collection: str | None = None) -> list[dict]:
        base = super().get_nl_tools(database=database, collection=collection)
        # Files have no database concept and no FK relations.
        tools = [t for t in base if t["name"] not in ("list_databases", "get_relations")]
        for tool in tools:
            if tool["name"] == "execute_query":
                tool["description"] = (
                    "Query the file using a structured JSON object. "
                    "Optional fields: "
                    "\"filter\" (pandas query string, e.g. \"age > 30 and country == 'USA'\"), "
                    "\"group_by\" (column or list), "
                    "\"aggregate\" (dict of {column: func} — func is count/sum/mean/min/max), "
                    "\"select\" (list of columns), "
                    "\"sort_by\" (column), \"sort_desc\" (bool), \"limit\" (int). "
                    "Pass an empty object {} to return all rows."
                )
                tool["input_schema"]["properties"]["query"] = {
                    "type": "object",
                    "description": "Structured query object (see tool description)",
                }
        return tools

    def execute_nl_tool(
        self,
        name: str,
        tool_input: dict,
        database: str | None = None,
        collection: str | None = None,
        optional_properties: dict | None = None,
    ):
        if name == "execute_query":
            db = tool_input.get("database", database)
            coll = tool_input.get("collection", collection)
            query = tool_input.get("query", {})
            return self.execute_query(query, database=db, collection=coll,
                                      optional_properties=optional_properties)
        return super().execute_nl_tool(
            name, tool_input,
            database=database, collection=collection,
            optional_properties=optional_properties,
        )

    # ---------- import ----------

    def import_data(
        self,
        source: DataSource,
        database: str = "default",
        collection: str = "default",
        entity: str | None = None,
        mode: str = "append",
        options: dict | None = None,
    ) -> dict:
        """Import rows from *source* into *collection*.

        ``collection`` is used for both sides of the transfer: it is passed to
        ``source.execute_query`` to identify which collection to read from, and
        it becomes the output file stem (e.g. ``"orders"`` → ``orders.csv``).
        This means source and target collection names must be the same; there
        is no separate ``source_collection`` parameter.

        Args:
            source: A DataSource to read rows from via ``execute_query``.
            collection: Collection name used as both the source collection and
                the target file stem.
            database: Ignored; FileSource has no database concept.
            entity: Accepted for interface consistency but not used.
            mode: ``"append"`` (default) or ``"overwrite"``.
            options:
                ``format``: ``"csv"`` (default), ``"json"``, ``"jsonl"``, or
                    ``"parquet"``. Inferred from an existing file when omitted;
                    defaults to ``"csv"`` if no file exists yet.
        """
        options = options or {}
        fmt = options.get("format")

        rows = source.execute_query(None, collection=collection)
        df_new = pd.DataFrame(rows)

        if fmt is None:
            for candidate in _FORMATS:
                if os.path.exists(self._file_path(collection, candidate)):
                    fmt = candidate
                    break
            else:
                fmt = "csv"

        path = self._file_path(collection, fmt)

        if mode == "append" and os.path.exists(path):
            existing_rows = self._read_file(path, fmt)
            df_existing = pd.DataFrame(existing_rows)
            df_new = pd.concat([df_existing, df_new], ignore_index=True)

        if fmt == "csv":
            df_new.to_csv(path, index=False)
        elif fmt == "json":
            df_new.to_json(path, orient="records", indent=2)
        elif fmt == "jsonl":
            with open(path, "w") as f:
                for record in df_new.to_dict(orient="records"):
                    f.write(json.dumps(record) + "\n")
        elif fmt == "parquet":
            df_new.to_parquet(path, index=False)

        return {
            "status": "success",
            "rows_written": len(df_new),
            "path": path,
            "format": fmt,
        }
