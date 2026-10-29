"""Regression tests for issue #207.

The <key>_env credential references (#100) must be resolved to the base key and
dropped before the connection dict reaches a DB driver — otherwise psycopg2 /
mysql.connector reject an unknown option like 'password_env' and a persisted
password-protected source can never connect. No real database is needed: the
driver-boundary helper SQLSource._resolve_env_refs is exercised directly.
"""
from blue_data.source.sql.sql_source import SQLSource


def test_resolves_env_ref_to_base_key_and_drops_it(monkeypatch):
    monkeypatch.setenv("DEMO_PGPW", "testpw")
    config = SQLSource._resolve_env_refs(
        {"host": "h", "user": "u", "password_env": "DEMO_PGPW", "protocol": "sql/postgres"}
    )
    assert config["password"] == "testpw"
    assert "password_env" not in config  # never passed to the driver


def test_explicit_password_wins_over_ref(monkeypatch):
    monkeypatch.setenv("DEMO_PGPW", "fromenv")
    config = SQLSource._resolve_env_refs({"password": "literal", "password_env": "DEMO_PGPW"})
    assert config["password"] == "literal"
    assert "password_env" not in config


def test_unset_env_ref_is_dropped_without_setting_base(monkeypatch):
    monkeypatch.delenv("MISSING_PW", raising=False)
    config = SQLSource._resolve_env_refs({"host": "h", "password_env": "MISSING_PW"})
    # The dangling reference is removed; no password is injected.
    assert "password_env" not in config
    assert "password" not in config


def test_postgres_and_mysql_inherit_the_helper(monkeypatch):
    # Both SQL sources must strip refs at their connect boundary.
    monkeypatch.setenv("DEMO_PGPW", "testpw")
    from blue_data.source.sql.postgres.postgres_sql_source import PostgresDBSource
    from blue_data.source.sql.mysql.mysql_sql_source import MySQLDBSource

    for cls in (PostgresDBSource, MySQLDBSource):
        config = cls._resolve_env_refs({"user": "u", "password_env": "DEMO_PGPW"})
        assert config == {"user": "u", "password": "testpw"}
