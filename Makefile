.PHONY: help \
        install install-lib install-platform \
        install-api install-cli install-json-mcp install-registry-mcp \
        build build-lib build-api build-cli build-json-mcp build-registry-mcp \
        test test-lib test-lib-unit test-lib-integration \
        test-platform test-api test-cli test-json-mcp test-registry-mcp

# ── default ──────────────────────────────────────────────────────────────────

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Install targets (editable, with dev extras):"
	@echo "  install               Install lib + all platform components"
	@echo "  install-lib           Install the core lib only"
	@echo "  install-platform      Install all platform components (requires install-lib)"
	@echo "  install-api           Install the REST API"
	@echo "  install-cli           Install the CLI"
	@echo "  install-json-mcp      Install the JSON MCP server"
	@echo "  install-registry-mcp  Install the registry MCP server"
	@echo ""
	@echo "Build targets (produces wheel + sdist in each component's dist/):"
	@echo "  build                 Build lib + all platform components"
	@echo "  build-lib             Build the core lib"
	@echo "  build-api             Build the REST API"
	@echo "  build-cli             Build the CLI"
	@echo "  build-json-mcp        Build the JSON MCP server"
	@echo "  build-registry-mcp    Build the registry MCP server"
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

# ── install ──────────────────────────────────────────────────────────────────

install: install-lib install-platform

install-lib:
	pip install -e "lib[dev]"

install-platform: install-api install-cli install-json-mcp install-registry-mcp

install-api: install-lib
	pip install -e "platform/api[dev]"

install-cli: install-lib
	pip install -e "platform/cli[dev]"

install-json-mcp: install-lib
	pip install -e "platform/json-mcp[dev]"

install-registry-mcp: install-lib
	pip install -e "platform/registry-mcp[dev]"

# ── build ────────────────────────────────────────────────────────────────────

build: build-lib build-api build-cli build-json-mcp build-registry-mcp

build-lib:
	python3 -m build lib/

build-api:
	python3 -m build platform/api/

build-cli:
	python3 -m build platform/cli/

build-json-mcp:
	python3 -m build platform/json-mcp/

build-registry-mcp:
	python3 -m build platform/registry-mcp/

# ── test ─────────────────────────────────────────────────────────────────────

test: test-lib test-platform

test-lib: test-lib-unit

test-lib-unit:
	cd lib && pytest tests/unit -v

test-lib-integration:
	cd lib && pytest tests/integration -v

test-platform: test-api test-cli test-json-mcp test-registry-mcp

test-api:
	cd platform/api && pytest -v

test-cli:
	cd platform/cli && pytest -v

test-json-mcp:
	cd platform/json-mcp && pytest -v

test-registry-mcp:
	cd platform/registry-mcp && pytest -v
