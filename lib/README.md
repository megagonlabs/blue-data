# blue-data (lib)

The core Python library. Provides `DataRegistry`, `DataSource`, `JSONSource`, and `VectorSource` abstractions.

## Install

```bash
pip install -e lib/
```

Runtime dependencies: `pandas`, `numpy`. No build step required.

Optional extras:

```bash
pip install -e "lib/[llm]"      # Anthropic client for LLM enrichment
pip install -e "lib/[redis]"    # Redis backend for persistent registry
pip install -e "lib/[dev]"      # pytest, pytest-cov for running tests
```

## Quick example

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

registry = DataRegistry()
source = SQLiteDBSource(
    name="mydb",
    properties={"connection": {"database_directory": "/tmp/my-data"}},
)
registry.register_source(source)

registry.sync_source("mydb", recursive=True)
registry.collect_source_stats("mydb", recursive=True)
registry.enrich_source_metadata("mydb", recursive=True)

results = registry.search_records("customer revenue")
```

## Running tests

```bash
pip install -e "lib/[dev]"
cd lib && python3 -m pytest tests/unit/ -v
```

Integration tests (require Redis Stack):

```bash
redis-stack-server &
python3 -m pytest tests/integration/ -v
```

## Documentation

- **[Quick start](../docs/quickstart.md)** — five-step workflow
- **[Developer guide](../docs/guide.md)** — syncing, enrichment, DQ profiling, search, and NL queries
- **[Architecture](../docs/architecture.md)** — system architecture and design decisions
- **[Extending](../docs/extending.md)** — implementing a new DataSource or custom NL translation
- **[Profiles](../README.md#profiles-bluedatautilsconfig)** — `blue_data.utils.config`, the profile-driven configuration engine every Blue CLI shares

## Source layout

```
lib/
├── src/
│   └── blue_data/
│       ├── core/           # DataSource, Registry, DataSchema
│       ├── source/         # SQL, file, vector, JSON backends
│       ├── registry/       # DataRegistry, search, enrichment
│       └── utils/
│           └── config/     # Profile-driven CLI configuration (spec, .profiles, precedence, secrets)
└── tests/
    ├── unit/
    ├── integration/
    └── benchmarks/
```
