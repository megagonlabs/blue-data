from __future__ import annotations

import json
import os

import pandas as pd

from blue_data.core.schema import DataSchema
from blue_data.source.source import DataSource

_FORMATS = ("csv", "json", "jsonl", "parquet")


class FileSource(DataSource):
    """DataSource backed by a directory of tabular files (CSV, JSON, JSONL).

    Each file in the directory maps to one collection.  There is no database
    concept — ``database`` is always ``"default"``.
    """

    def __init__(self, name: str, directory: str = ".", properties: dict | None = None):
        super().__init__(name, properties=properties)
        self._directory = os.path.abspath(directory)
        os.makedirs(self._directory, exist_ok=True)

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

    def execute_query(
        self,
        query,
        database: str | None = None,
        collection: str | None = None,
        optional_properties: dict | None = None,
    ) -> list[dict]:
        """Return rows from *collection*.

        ``query`` can be:
        - ``None`` — return all rows
        - ``dict`` — equality filter ``{column: value, ...}``
        """
        if collection is None:
            raise ValueError("collection is required for FileSource.execute_query")
        try:
            path, fmt = self._resolve_file(collection)
        except FileNotFoundError:
            return []
        rows = self._read_file(path, fmt)
        if query and isinstance(query, dict):
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
        sample = rows[:10]
        return {
            "row_count": len(rows),
            "row_samples": sample,
            "row_sample_size": len(sample),
            "row_samples_aligned": len(rows) >= 2,
        }

    # ---------- import ----------

    def import_data(
        self,
        source: DataSource,
        collection: str,
        database: str = "default",
        entity: str | None = None,
        mode: str = "append",
        options: dict | None = None,
    ) -> dict:
        """Import rows from *source* into *collection*.

        Args:
            source: A DataSource to read rows from via ``execute_query``.
            collection: Target collection name (file stem).
            database: Ignored; FileSource has no database concept.
            mode: ``"append"`` (default) or ``"overwrite"``.
            options:
                ``format``: ``"csv"`` (default), ``"json"``, or ``"jsonl"``.
                    Inferred from an existing file when omitted.
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
