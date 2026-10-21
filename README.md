# blue-data

A data intelligence layer that makes heterogeneous enterprise data understandable to AI agents and language models.

LLMs querying enterprise data fail in silent, predictable ways — they guess coded values, miss what columns actually mean, and never see the data-quality problems that make a syntactically correct query return a wrong answer. `blue-data` sits between raw data sources and the AI layer, enriching schemas with the semantic metadata — coded values, natural-language descriptions, data-quality signals, and process semantics — that lets agents discover, reason about, and query data correctly.

→ **[Full documentation](docs/README.md)** · **[Quick start](docs/quickstart.md)** · **[Installation](docs/installation.md)** · **[Examples](examples/README.md)** · **[CLI](docs/cli.md)** · **[MCP server](docs/registry-mcp.md)**

---

## What it does

- **Register** heterogeneous data sources — SQL, document, graph, vector, stream, and file — behind one consistent interface, and mirror their structure as a searchable catalog.
- **Enrich** schemas with semantic metadata: coded-value detection, natural-language column descriptions, semantic types, and process/temporal semantics — cheaply, mostly without LLM calls.
- **Discover** the right data by meaning with hybrid BM25 + vector search, so *"shipping cost"* finds `orders.freight`.
- **Profile** data quality before querying — outliers, disguised missing values, representation fragmentation, suspected typos — stored as registry properties agents can act on.
- **Query** sources in natural language, grounded in the enriched schema, as a one-shot translation or a multi-turn tool loop.
- **Serve** all of this through a REST API, a CLI, and MCP servers for Claude and other agents.

Full feature list: [docs/features.md](docs/features.md). Runnable demos: [examples/](examples/README.md). Demo datasets: [data/](data/README.md).

---

## Repository layout

```
blue-data/
├── lib/                      # Core Python library (blue-data)
│   ├── src/blue_data/        # DataRegistry, DataSource adapters, enrichment, search
│   └── tests/                # unit, integration, and benchmark tests
├── platform/
│   ├── registry-api/         # FastAPI REST service (port 8000) — `blue-data-api`
│   ├── registry-cli/         # `blue-registry` command-line interface
│   ├── registry-mcp/         # MCP server for registry operations (Claude Desktop / Claude Code)
│   └── json-mcp/             # MCP server for raw JSONSource key/value operations
├── docs/                     # Documentation
├── examples/                 # Runnable example scripts with captured output
├── design/                   # Architecture decision records
├── data/                     # Demo datasets (Northwind, Czech banking, finance, BIRD)
└── example.envrc             # Sample environment configuration (copy to .envrc)
```

---

## Requirements

- Python 3.10+
- Runtime dependencies `pandas`, `numpy`, `jsonpath-ng` — installed automatically; no build step.
- Optional: Redis Stack (`redis-stack-server`) for production registry persistence and vector search.
- Optional: an LLM API key for metadata enrichment and natural-language queries (deterministic enrichment needs none):

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or
export OPENAI_API_KEY=sk-...
```

Optional extras (`[postgres]`, `[mysql]`, `[mongodb]`, `[neo4j]`, `[redis]`, `[chromadb]`, `[bn]`, `[parquet]`, `[llm]`, `[all]`) are documented in [docs/installation.md](docs/installation.md). Full configuration — store backends, LLM providers, search tuning, and profiles — is in [docs/configuration.md](docs/configuration.md).

---

## Quick start

```bash
bash lib/scripts/install.sh          # editable install of blue-data (with dev extras)

# Minimal end-to-end — build a tiny SQLite DB, register it, sync, and search. No API key needed:
python3 - <<'PY'
import os, sqlite3, tempfile
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

d = tempfile.mkdtemp()
con = sqlite3.connect(os.path.join(d, "shop.db"))
con.executescript("CREATE TABLE customers(id INTEGER PRIMARY KEY, company_name TEXT, country TEXT);")
con.commit(); con.close()

reg = DataRegistry()
reg.register_source(SQLiteDBSource(name="shop", properties={"connection": {"database_directory": d}}))
reg.sync_source("shop", recursive=True)
print("entities:", [e["name"] for e in reg.list_collection_entities("shop", "shop", "public")])
print("search  :", [r["name"] for r in reg.search_records("customers")])
PY
```

For the full walkthrough — stats collection, LLM enrichment, hybrid search, and natural-language queries — see [docs/quickstart.md](docs/quickstart.md).

---

## Packages

| Package | Description |
|---|---|
| [`lib/`](lib/README.md) | Core library `blue-data` — `DataRegistry`, `DataSource` adapters, enrichment, and search. Install: `bash lib/scripts/install.sh` |
| [`platform/registry-api/`](platform/registry-api/README.md) | FastAPI REST service on port 8000, command `blue-data-api`. Install: `pip install -e platform/registry-api` |
| [`platform/registry-cli/`](platform/registry-cli/README.md) | Command-line interface `blue-registry` over the core ops. Install: `pip install -e platform/registry-cli` |
| [`platform/registry-mcp/`](platform/registry-mcp/README.md) | MCP server exposing registry ops as AI-callable tools, command `blue-data-registry-mcp`. Install: `pip install -e platform/registry-mcp` |
| [`platform/json-mcp/`](platform/json-mcp/README.md) | MCP server for raw JSONSource key/value operations, command `blue-data-json-mcp`. Install: `pip install -e platform/json-mcp` |

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code. Report unacceptable behavior
to contact_oss@megagon.ai.

---

## Disclosures

This software may include, incorporate, or access open source software (OSS) components,
datasets and other third party components, including those identified below. The license terms
respectively governing the datasets and third-party components continue to govern those
portions, and you agree to those license terms may limit any distribution, use, and copying.
You may use any OSS components under the terms of their respective licenses, which may
include BSD 3, Apache 2.0, and other licenses. In the event of conflicts between Megagon Labs,
Inc. (“Megagon”) license conditions and the OSS license conditions, the applicable OSS
conditions governing the corresponding OSS components shall prevail.
You agree not to, and are not permitted to, distribute actual datasets used with the OSS
components listed below. You agree and are limited to distribute only links to datasets from
known sources by listing them in the datasets overview table below. You agree that any right to
modify datasets originating from parties other than Megagon are governed by the respective
third party’s license conditions.
You agree that Megagon grants no license as to any of its intellectual property and patent rights.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS (INCLUDING
MEGAGON) “AS IS” AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. You agree to cease using,
incorporating, and distributing any part of the provided materials if you do not agree with the
terms or the lack of any warranty herein.
While Megagon makes commercially reasonable efforts to ensure that citations in this
document are complete and accurate, errors may occur. If you see any error or omission, please
help us improve this document by sending information to contact_oss@megagon.ai.

### Datasets

All datasets used within the product are listed below (including their copyright holders and the license information).

For Datasets having different portions released under different licenses, please refer to the included source link specified for each of the respective datasets for identifications of dataset files released under the identified licenses.

</br>

| ID  | Dataset Name | Modified | Copyright Holder | Upstream Link | License  |
|-----|----------------------------------|----------|------------------|-----------------------------------------------------------------------------------------------------------|--------------------|
| 1 | BIRD benchmark databases (`data/bird/*` — fetched separately, not redistributed; derived subset `data/finance_sqlite.sql`; discovery-query and entity-mapping annotations) | Yes | BIRD benchmark authors (Li et al.) | [link](https://bird-bench.github.io/) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| 2 | Northwind sample database (`data/northwind_sqlite.sql`, `data/northwind_postgres.sql`) | Yes | Microsoft Corporation (original "Northwind" sample database) | [link](https://github.com/microsoft/sql-server-samples) | MIT License |

### Open Source Software (OSS) Components

All OSS components used within the product are listed below (including their copyright holders and the license information).

For OSS components having different portions released under different licenses, please refer to the included Upstream link(s) specified for each of the respective OSS components for identifications of code files released under the identified licenses.

</br>

| ID  | OSS Component Name | Modified | Copyright Holder | Upstream Link | License  |
|-----|----------------------------------|----------|------------------|-----------------------------------------------------------------------------------------------------------|--------------------|
| 1 | anthropic | No | Anthropic, PBC | [link](https://github.com/anthropics/anthropic-sdk-python) | MIT License |
| 2 | chromadb | No | Chroma | [link](https://github.com/chroma-core/chroma) | Apache Software License |
| 3 | click | No | Pallets | [link](https://github.com/pallets/click) | BSD License |
| 4 | fastapi | No | Sebastián Ramírez | [link](https://github.com/fastapi/fastapi) | MIT License |
| 5 | jsonpath-ng | No | Tomas Aparicio | [link](https://github.com/h2non/jsonpath-ng) | Apache Software License |
| 6 | MCP | No | Anthropic, PBC | [link](https://github.com/modelcontextprotocol/python-sdk) | MIT License |
| 7 | mysql-connector-python | No | Oracle and/or its affiliates | [link](https://dev.mysql.com/doc/connector-python/en/) | GNU General Public License |
| 8 | networkx | No | NetworkX Developers | [link](https://github.com/networkx/networkx) | BSD License |
| 9 | neo4j | No | Neo4j, Inc. | [link](https://github.com/neo4j/neo4j-python-driver) | Apache Software License |
| 10 | numpy | No | NumPy Developers | [link](https://numpy.org/) | BSD License |
| 11 | pandas | No | AQR Capital Management, LLC, Lambda Foundry, Inc. and PyData Development Team | [link](https://pandas.pydata.org/) | BSD License |
| 12 | pgmpy | No | pgmpy contributors | [link](https://github.com/pgmpy/pgmpy) | MIT License |
| 13 | psycopg2-binary | No | Federico Di Gregorio, Daniele Varrazzo, and The Psycopg Team | [link](https://github.com/psycopg/psycopg2) | GNU Lesser General Public License (LGPL) |
| 14 | pyarrow | No | The Apache Software Foundation | [link](https://github.com/apache/arrow) | Apache Software License |
| 15 | pydantic | No | Pydantic Services Inc. and individual contributors | [link](https://github.com/pydantic/pydantic) | MIT License |
| 16 | pymongo | No | MongoDB, Inc. | [link](https://github.com/mongodb/mongo-python-driver) | Apache Software License |
| 17 | redis | No | Redis, inc. | [link](https://github.com/redis/redis-py) | MIT License |
| 18 | rich | No | Will McGugan | [link](https://github.com/Textualize/rich) | MIT License |
| 19 | uvicorn | No | Encode OSS Ltd | [link](https://github.com/encode/uvicorn) | BSD License |
