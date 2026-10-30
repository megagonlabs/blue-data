"""Regression tests for issue #207.

The <key>_env credential references (#100) must be resolved to the base key and
dropped before the connection dict reaches a DB driver — otherwise psycopg2 /
mysql.connector reject an unknown option like 'password_env' and a persisted
password-protected source can never connect. No real database is needed: the
driver-boundary helper SQLSource._resolve_env_refs is exercised directly.
"""
import pytest

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


def test_empty_base_key_does_not_mask_the_ref(monkeypatch):
    monkeypatch.setenv("DEMO_PGPW", "testpw")
    config = SQLSource._resolve_env_refs({"password": "", "password_env": "DEMO_PGPW"})
    assert config == {"password": "testpw"}


def _capture_connect(monkeypatch, module, attr):
    seen = []

    def fake_connect(**kwargs):
        seen.append(kwargs)
        return None

    monkeypatch.setattr(module, attr, fake_connect)
    return seen


def test_real_sources_built_from_password_env_alone_pass_the_password(monkeypatch):
    """#239: the sources' default password="" used to win over password_env, so a
    source configured with the reference alone connected with an empty password."""
    monkeypatch.setenv("DEMO_PGPW", "testpw")
    conn = {"host": "127.0.0.1", "user": "test", "database": "demo", "password_env": "DEMO_PGPW"}
    cases = []
    try:
        from blue_data.source.sql.postgres import postgres_sql_source as pg
        cases.append((pg, "psycopg2", pg.PostgresDBSource))
    except ImportError:
        pass
    try:
        from blue_data.source.sql.mysql import mysql_sql_source as my
        cases.append((my, "cpy", my.MySQLDBSource))
    except ImportError:
        pass
    if not cases:
        pytest.skip("no SQL driver installed")

    for module, driver, cls in cases:
        seen = _capture_connect(monkeypatch, getattr(module, driver), "connect")
        src = cls("db", properties={"connection": dict(conn)})
        src._db_connect("demo")
        assert seen, cls.__name__
        for kwargs in seen:
            assert kwargs["password"] == "testpw", cls.__name__
            assert "password_env" not in kwargs
