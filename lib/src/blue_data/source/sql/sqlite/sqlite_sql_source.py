import copy
import os
import sqlite3

import pandas as pd

from blue_data.source.sql.sql_source import SQLSource
from blue_data.core.schema import DataSchema


class SQLiteDBSource(SQLSource):
    def __init__(self, name, properties=None):
        super().__init__(name, properties=properties)

    def _initialize_connection_properties(self):
        connection = self.properties.get("connection", {})

        connection.setdefault("protocol", "sql/sqlite")
        connection.setdefault("database_directory", ".")
        connection.setdefault("stat_sample_size", 2000)

        self.properties["connection"] = connection

    
    def _connect(self, **connection):
        c = copy.deepcopy(connection)
        if 'protocol' in c:
            del c['protocol']

        if 'database' in connection:
            database = connection['database']
            return sqlite3.connect(self._get_database_path(database))
        else:
            # only database specific connection
            return {}

    def _disconnect(self):
        # SQLite uses per-query connections via _db_connect — no persistent connection to close.
        return None

   
    # database  path
    def _get_database_directory(self):
        connection_properties = self.properties['connection']
        database_directory = connection_properties['database_directory']

        absolute_database_directory = os.path.abspath(database_directory)
        # make sure it exists, create if not
        os.makedirs(absolute_database_directory, exist_ok=True)
        return absolute_database_directory

    def _get_database_path(self, database):
        database_directory = self._get_database_directory()
        for suffix in (".db", ".sqlite"):
            path = os.path.join(database_directory, database + suffix)
            if os.path.exists(path):
                return path
        return os.path.join(database_directory, database + ".db")

    ######### source
    def fetch_metadata(self):
        """
        Fetch metadata for source.

        Parameters:
            None.

        Returns:
            dict: Metadata dictionary (currently empty for SQLite).
        """
        return {}

    def fetch_schema(self):
        """
        Fetch schema for source.

        Parameters:
            None.

        Returns:
            dict: Metadata dictionary (currently empty for SQLite).
        """

        return {}

    ######### database
    def fetch_databases(self):
        """
        List all SQLite databases in the configured data directory.

        Returns:
            list[str]: Names of database files (without extension). Recognises
            both ``.db`` and ``.sqlite`` files; if both exist for the same name
            only one entry is returned.
        """
        ls = os.listdir(self._get_database_directory())
        seen = set()
        dbs = []
        for filename in ls:
            for suffix in (".db", ".sqlite"):
                if filename.endswith(suffix):
                    name = filename[: -len(suffix)]
                    if name not in seen:
                        seen.add(name)
                        dbs.append(name)
                    break
        return dbs

    def fetch_database_metadata(self, database):
        """
        Fetch metadata for a specific database.

        Parameters:
            database (str): Database name.

        Returns:
            dict: Metadata dictionary (currently empty for SQLite).
        """
        return {}

    def create_database(self, database, properties={}, overwrite=False):
        """Create a new SQLite database file."""
        """
        Create a new SQLite database file.

        Parameters:
            database (str): Name of the database to create.
            properties (dict, optional): Additional properties (unused in SQLite).
            overwrite (bool, optional): If True, overwrite existing database file.

        Returns:
            dict: Status of the operation: {"status": "success"} or {"status": "skipped"}.
        """
        # Check if database file already exists
        db_path = self._get_database_path(database)
        if os.path.exists(db_path):
            if overwrite:
                self.logger.info(f"Overwriting existing database file '{db_path}'")
                os.remove(db_path)
            else:
                self.logger.info(f"Database file '{db_path}' already exists, skipping creation")
                return {"status": "skipped"}

        db_connection = self._db_connect(database, create=True)
        self._db_disconnect(db_connection)
        self.logger.info(f"Successfully created SQLite database '{database}' at '{db_path}'")
        return {"status": "success"}

    def _db_connect(self, database, create=False):
        if not create:
            db_path = self._get_database_path(database)
            if not os.path.exists(db_path):
                raise FileNotFoundError(f"Database '{database}' does not exist at '{db_path}'")
        c = copy.deepcopy(self.properties['connection'])
        if 'protocol' in c:
            del c['protocol']
        c['database'] = database
        return self._connect(**c)

 ######### database/collection
    def fetch_database_collections(self, database):
        """
        Fetch the list of logical 'collections' (schemas or namespaces) in the specified SQLite database.

        Since SQLite does not support multiple schemas or collections like other RDBMS systems
        (e.g., PostgreSQL), this method returns a single default collection name "public" so that
        a consistent data registry entry can be created for the database.

        Parameters:
            database (str): The name or path of the SQLite database file.

        Returns:
            list[str]: A list containing a single element, "public".
        """
        ## for sqlite, there is no collection actually. We are returning "public" to have data registry entry
        collections = []
        collections.append("public")
        return collections

    def fetch_database_collection_metadata(self, database, collection):
        """
        Fetch metadata for a given 'collection' within the SQLite database.

        Since SQLite does not have the concept of separate collections or schemas,
        this function returns an empty metadata dictionary placeholder for consistency
        with other database source implementations.

        Parameters:
            database (str): The name or path of the SQLite database file.
            collection (str): The logical collection name (typically "public").

        Returns:
            dict: An empty dictionary, as SQLite does not support collection-level metadata.
        """
        return {}

    def fetch_enum_types(self, db_connection):
        """
        Fetch enumerated types for a database connection.

        Parameters:
            db_connection (sqlite3.Connection): Active SQLite database connection.

        Returns:
            list: List of enum types (currently empty for SQLite).
        """
        # TODO
        return []

    def fetch_database_collection_entities(self, database, collection, max_distinct=50, max_ratio=0.1, max_length=100):
        ## for sqlite, database and collection is same
        """
        For SQLite: since database == collection, we ignore `collection`.
        Returns tables and their column metadata.
        """
        db_connection = self._db_connect(database)
        cursor = db_connection.cursor()

        # 1. Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        result = []
        schema = DataSchema()

        for table in tables:
            # 2. Get all columns for this table

            if not schema.has_entity(table):
                schema.add_entity(table)

            cursor.execute(f'PRAGMA table_info("{table}");')
            columns = cursor.fetchall()

            for col in columns:
                # columns schema: (cid, name, type, notnull, dflt_value, pk)
                data_type = col[2]
                column_name = col[1]
                property_def = {"type": data_type}

                # TODO: add enum, values to property_def
                property_def["values"] = []
                schema.add_entity_attribute(table, column_name, property_def)

        self._db_disconnect(db_connection)
        return schema.get_entities()

    def fetch_database_collection_relations(self, database, collection):
        """
        Fetch relationships (foreign keys) within a database collection.

        Parameters:
            database (str): Name of the database.
            collection (str): Name of the collection.

        Returns:
            dict: Collection-level relationship metadata (currently empty for SQLite).
        """
        return {}

    def create_database_collection(self, database, collection, properties={}, overwrite=False):
        """The SQLite collection is the database. NOP - only registry update needed"""
        return {"status": "registry_only"}

    ######### source/database/collection/entity
    def create_database_collection_entity(self, database, collection, entity, properties={}, overwrite=False):
        """Create a new SQLite table (entity)."""
        # Check if table already exists
        db_connection = self._db_connect(database)
        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (entity,))
        table_exists = cursor.fetchone() is not None
        self._db_disconnect(db_connection)

        if table_exists:
            if overwrite:
                self.logger.info(f"Overwriting existing table '{entity}'")
                drop_query = f"DROP TABLE IF EXISTS \"{entity}\""
                self.execute_query(drop_query, database=database, optional_properties={"commit": True})
            else:
                self.logger.info(f"Table '{entity}' already exists, skipping creation")
                return {"status": "skipped"}

        query = "CREATE TABLE " + f"\"{entity}\""

        # column definitions
        column_definitions_str = ""
        column_definitions = properties['cols_definition']
        for i, column_def in enumerate(column_definitions):
            if i > 0:
                column_definitions_str += ", "
            column_definitions_str += column_def['name']
            if 'type' in column_def:
                column_definitions_str += " " + column_def['type']
            if 'misc' in column_def:
                column_definitions_str += " " + column_def['misc']

        # add primary key constraint if provided
        primary_key = properties.get('primary_key', [])
        if primary_key:
            pk_cols = ', '.join([f'"{col}"' for col in primary_key])
            pk_clause = f", PRIMARY KEY ({pk_cols})"
            column_definitions_str += pk_clause

        # add foreign key constraints if provided
        foreign_keys = properties.get('foreign_keys', [])
        if foreign_keys:
            for fk in foreign_keys:
                source_cols = ', '.join([f'"{col}"' for col in fk['foreign_keys_source_columns']])
                target_cols = ', '.join([f'"{col}"' for col in fk['foreign_keys_target_columns']])
                fk_clause = f", FOREIGN KEY ({source_cols}) REFERENCES \"{fk['foreign_keys_target_table']}\" ({target_cols})"
                column_definitions_str += fk_clause

        query += "( " + column_definitions_str + " )"
        self.logger.info(f"Generated SQL query: {query}")
        self.execute_query(query, database=database, optional_properties={"commit": True})
        self.logger.info(f"Successfully created table '{entity}' in collection '{collection}' of database '{database}' in SQLite")
        return {"status": "success"}

    ######### source/database/collection/relation
    def create_database_collection_relation(self, database, collection, relation, properties={}, overwrite=False):
        """SQLite doesn't support adding foreign keys after table creation.
        We only support adding foreign keys when creating tables (see create_database_collection_entity).
        """
        return {"status": "skipped"}

    ######### import

    def import_data(self, source, database="default", collection="default", entity=None, mode="append", options=None):
        """Import rows from *source* into a SQLite table.

        Args:
            source: DataSource to pull rows from via
                ``source.execute_query(None, collection=collection)``.
            database: SQLite database file name (without ``.db`` extension).
            collection: Collection name passed to the *source* side to identify
                which data to read (e.g. the schema name or file stem on the
                source). Not used to determine the target table.
            entity: **Required.** Name of the SQLite table to write into.
                Must already exist in *database*. This is separate from
                *collection* because the source and target may use different
                names for the same data.
            mode: ``"append"`` (default) inserts rows into the existing table.
                ``"overwrite"`` deletes all existing rows first, then inserts.
            options: Unused; accepted for interface consistency.

        Raises:
            ValueError: If *entity* is ``None``.
        """
        if entity is None:
            raise ValueError("entity (table name) is required for SQLiteDBSource.import_data")

        rows = source.execute_query(None, database=database, collection=collection)
        if not rows:
            return {"status": "success", "rows_imported": 0}

        df = pd.DataFrame(rows)
        conn = self._db_connect(database)
        try:
            if mode == "overwrite":
                cur = conn.cursor()
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (entity,)
                )
                if cur.fetchone():
                    cur.execute(f'DELETE FROM "{entity}"')
                conn.commit()

            df.to_sql(entity, conn, if_exists="append", index=False)
            conn.commit()
            return {"status": "success", "rows_imported": len(df)}
        finally:
            self._db_disconnect(conn)

    ######### stats

    def fetch_source_stats(self):
        """
        Fetch source-level statistics for the SQLite source.

        Returns:
            dict: A dictionary containing:
                - ``database_count``: number of .db files in the directory.
                - ``total_size_bytes``: combined size of all database files.
                - ``directory``: absolute path to the database directory.
        """
        try:
            directory = self._get_database_directory()
            db_files = [
                f for f in os.listdir(directory)
                if f.endswith(".db") or f.endswith(".sqlite")
            ]
            total_size = sum(
                os.path.getsize(os.path.join(directory, f))
                for f in db_files
                if os.path.isfile(os.path.join(directory, f))
            )
            return {
                "database_count": len(db_files),
                "total_size_bytes": total_size,
                "directory": directory,
            }
        except Exception as e:
            self.logger.warning(f"Failed to fetch SQLite source stats: {e}")
            return {"error": str(e)}

    def fetch_database_stats(self, database):
        """
        Fetch basic statistics for an SQLite database.

        Parameters:
            database (str): Name of the database to analyze.

        Returns:
            dict: A dictionary containing database-level statistics:
                - size_bytes (int): Size of the database file in bytes.
                - table_count (int): Total number of tables in the database.

        """
        stats = {}

        db_path = self._get_database_path(database)

        if not os.path.exists(db_path):
            self.logger.warning(f"Database file {db_path} does not exist")
            return stats

        try:
            # Size in bytes
            stats["size_bytes"] = os.path.getsize(db_path)
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            # Number of tables
            cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            stats["table_count"] = cur.fetchone()[0]

            conn.close()

        except Exception as e:
            self.logger.warning(f"Error fetching SQLite database stats: {e}")

        return stats

    def fetch_entity_stats(self, database, collection, entity, row_sample_size=100):
        """Fetch row count and a sample of rows for *entity*."""
        stats = {
            "row_count": None,
            "row_samples": [],
            "row_sample_size": 0,
            "row_samples_aligned": False,
        }
        db_path = self._get_database_path(database)
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(f'SELECT COUNT(*) FROM "{entity}";')
            stats["row_count"] = cursor.fetchone()[0]

            if stats["row_count"] and stats["row_count"] > 0:
                cursor.execute(
                    f'SELECT * FROM "{entity}" ORDER BY RANDOM() LIMIT {row_sample_size};'
                )
                rows = cursor.fetchall()
                if rows:
                    stats["row_samples"] = [dict(row) for row in rows]
                    stats["row_sample_size"] = len(stats["row_samples"])
                    stats["row_samples_aligned"] = len(stats["row_samples"]) >= 2

            conn.close()
        except sqlite3.Error:
            pass

        return stats

    def fetch_property_stats(self, database, collection, table, property_name, sample_limit=10):
        """
        Fetch basic statistics for a column/property in a SQLite table.

        Parameters:
            database (str): Name or path of the SQLite database.
            collection (str): Ignored in SQLite (no schema support).
            table (str): Table name to analyze.
            property_name (str): Column name to fetch stats for.
            sample_limit (int, optional): Number of sample values to retrieve. Defaults to 10.

        Returns:
            dict: Dictionary containing property statistics:
                - count: number of non-null values
                - distinct_count: number of unique values
                - null_count: number of null values
                - sample_values: list of sample non-null values
                - min: minimum value (if numeric/date)
                - max: maximum value (if numeric/date)
                - most_common_vals: list of (value, count) pairs for the top-20 most frequent non-null values, descending by frequency
        """
        db_path = self._get_database_path(database)
        stat_sample_size = self.properties["connection"].get("stat_sample_size") or 0

        stats = {}

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cursor = conn.cursor()

            # Find column type from PRAGMA
            cursor.execute(f'PRAGMA table_info("{table}");')
            columns = cursor.fetchall()
            column_type = None
            for col in columns:
                if col[1] == property_name:
                    column_type = col[2]
                    break

            column = f'"{property_name}"'

            # Decide whether to sample. Row count is cheap (SQLite stores it).
            cursor.execute(f'SELECT COUNT(*) FROM "{table}";')
            row_count = cursor.fetchone()[0]

            if stat_sample_size and row_count > stat_sample_size:
                cte = f'WITH _sample AS (SELECT * FROM "{table}" LIMIT {stat_sample_size})'
                src = "_sample"
            else:
                cte = ""
                src = f'"{table}"'

            prefix = cte + " " if cte else ""

            # Basic counts (from sample when large)
            cursor.execute(
                f"""
                {prefix}SELECT
                    COUNT({column}) AS non_null_count,
                    COUNT(DISTINCT {column}) AS distinct_count,
                    SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS null_count
                FROM {src};
                """
            )
            row = cursor.fetchone()
            stats["count"] = row[0]
            stats["distinct_count"] = row[1]
            stats["null_count"] = row[2]

            # Sample values
            cursor.execute(
                f"""
                {prefix}SELECT {column}
                FROM {src}
                WHERE {column} IS NOT NULL
                LIMIT {sample_limit};
                """
            )
            stats["sample_values"] = [r[0] for r in cursor.fetchall()]

            # Min / Max
            include_min_max = column_type and any(t in column_type.upper() for t in ["INT", "REAL", "NUM", "DATE", "TIME"])
            if include_min_max:
                cursor.execute(f"{prefix}SELECT MIN({column}), MAX({column}) FROM {src};")
                min_val, max_val = cursor.fetchone()
                stats["min"] = min_val
                stats["max"] = max_val
            else:
                stats["min"] = None
                stats["max"] = None

            # Mean + variance for numeric columns
            is_numeric = include_min_max and any(
                t in column_type.upper() for t in ["INT", "REAL", "NUM", "FLOAT", "DOUBLE"]
            )
            if is_numeric:
                cursor.execute(
                    f"{prefix}SELECT AVG({column}),"
                    f" AVG({column} * {column}) - AVG({column}) * AVG({column})"
                    f" FROM {src};"
                )
                mean_val, var_val = cursor.fetchone()
                stats["mean"] = mean_val
                stats["variance"] = var_val
            else:
                stats["mean"] = None
                stats["variance"] = None

            # Top-20 most common values
            cursor.execute(
                f"""
                {prefix}SELECT {column}, COUNT(*) AS freq
                FROM {src}
                WHERE {column} IS NOT NULL
                GROUP BY {column}
                ORDER BY freq DESC
                LIMIT 20;
                """
            )
            stats["most_common_vals"] = [(r[0], r[1]) for r in cursor.fetchall()]
            return stats

        except Exception as e:
            self.logger.warning(f"Failed to fetch property stats for {table}.{property_name}: {str(e)}")
            return {}
        finally:
            self._db_disconnect(conn)
