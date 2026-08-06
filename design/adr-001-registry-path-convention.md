# ADR-001: Registry Path Convention `{scope}/{type}/{name}`

**Status:** Accepted

## Context

The registry stores catalog records for sources, databases, collections, entities, attributes, and relations. We needed a key scheme that:

- Encodes the full ancestry of a record (which source, database, collection it belongs to)
- Supports scoped listing (e.g., "all entities under collection X")
- Is human-readable in Redis or a JSON file
- Avoids collisions between records at different levels with the same name

## Decision

Every record is keyed by:

```
{scope}/{type}/{name}
```

Where `scope` encodes the full ancestry path:

| Level | scope | type | Example key |
|---|---|---|---|
| Source | `/` | `source` | `/source/northwind` |
| Database | `/source/northwind` | `database` | `/source/northwind/database/northwind` |
| Collection | `/source/northwind/database/northwind` | `collection` | `/source/northwind/database/northwind/collection/public` |
| Entity | `/source/northwind/database/northwind/collection/public` | `entity` | `/source/northwind/database/northwind/collection/public/entity/orders` |
| Attribute | `/source/northwind/database/northwind/collection/public/entity/orders` | `attribute` | `…/entity/orders/attribute/order_date` |

The root key `$` holds top-level registry metadata.

## Consequences

**Good:**
- Listing all records of a type under a scope is a prefix scan — no secondary index needed.
- The path is self-describing: reading a key tells you exactly where in the hierarchy the record lives.
- Adding new levels (e.g., a "schema" level between database and collection) only requires a new `type` value — the convention itself doesn't change.

**Trade-off:**
- Keys grow long for deep records (attribute keys can be 100+ characters).
- Renaming a source requires rewriting all descendant keys — there is no normalization.
