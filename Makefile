.PHONY: help test test-lib test-lib-unit test-lib-integration \
        test-platform test-api test-cli test-json-mcp test-registry-mcp \
        install install-lib install-platform

# ── default ─────────────────────────────────────────────────────────────────

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Test targets:"
	@echo "  test                  Run all unit tests (lib + all platform components)"
	@echo "  test-lib              Run lib unit tests"
	@echo "  test-lib-unit         Alias for test-lib"
	@echo "  test-lib-integration  Run lib integration tests (requires Redis, Postgres, MySQL, Neo4j)"
	@echo "  test-platform         Run all platform component tests"
	@echo "  test-api              Run REST API tests"
	@echo "  test-cli              Run CLI tests"
	@echo "  test-json-mcp         Run JSON MCP server tests"
	@echo "  test-registry-mcp     Run registry MCP server tests"
	@echo ""
	@echo "Install targets:"
	@echo "  install               Install all packages in editable mode (dev extras)"
	@echo "  install-lib           Install the core lib only"
	@echo "  install-platform      Install all platform components"

# ── combined ────────────────────────────────────────────────────────────────

test: test-lib test-platform

# ── lib ─────────────────────────────────────────────────────────────────────

test-lib: test-lib-unit

test-lib-unit:
	cd lib && pytest tests/unit -v

test-lib-integration:
	cd lib && pytest tests/integration -v

# ── platform ────────────────────────────────────────────────────────────────

test-platform: test-api test-cli test-json-mcp test-registry-mcp

test-api:
	cd platform/api && pytest -v

test-cli:
	cd platform/cli && pytest -v

test-json-mcp:
	cd platform/json-mcp && pytest -v

test-registry-mcp:
	cd platform/registry-mcp && pytest -v

# ── install ──────────────────────────────────────────────────────────────────

install: install-lib install-platform

install-lib:
	pip install -e "lib[dev]"

install-platform: install-lib
	pip install -e "platform/api[dev]"
	pip install -e "platform/cli[dev]"
	pip install -e "platform/json-mcp[dev]"
	pip install -e "platform/registry-mcp[dev]"
