BASE = "/sales/database/prod"
COL  = BASE + "/collection/public"
ENT  = COL  + "/entity/orders"
ATTR = ENT  + "/attribute/total"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def test_get_database(client):
    r = client.get(BASE)
    assert r.status_code == 200
    assert r.json()["result"]["name"] == "prod"


def test_get_database_not_found(client):
    assert client.get("/sales/database/ghost").status_code == 404


def test_list_collections(client):
    r = client.get(BASE + "/collections")
    assert r.status_code == 200
    names = [c["name"] for c in r.json()["results"]]
    assert "public" in names


def test_register_and_delete_database(client):
    r = client.post("/sales/database/staging", json={"description": "Staging DB"})
    assert r.status_code == 200
    assert client.get("/sales/database/staging").status_code == 200
    assert client.delete("/sales/database/staging").status_code == 200
    assert client.get("/sales/database/staging").status_code == 404


def test_update_database(client):
    r = client.put(BASE, json={"description": "Production database"})
    assert r.status_code == 200


def test_sync_database(client):
    assert client.put(BASE + "/sync").status_code == 200


def test_collect_database_stats(client):
    assert client.put(BASE + "/stats").status_code == 200


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def test_get_collection(client):
    r = client.get(COL)
    assert r.status_code == 200
    assert r.json()["result"]["name"] == "public"


def test_get_collection_not_found(client):
    assert client.get(BASE + "/collection/ghost").status_code == 404


def test_list_entities(client):
    r = client.get(COL + "/entities")
    assert r.status_code == 200
    names = [e["name"] for e in r.json()["results"]]
    assert "orders" in names
    assert "customers" in names


def test_list_relations(client):
    r = client.get(COL + "/relations")
    assert r.status_code == 200
    assert isinstance(r.json()["results"], list)


def test_sync_collection(client):
    assert client.put(COL + "/sync").status_code == 200


def test_collect_collection_stats(client):
    assert client.put(COL + "/stats").status_code == 200


def test_collection_metadata_enrichment(client):
    assert client.put(COL + "/metadata").status_code == 200


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

def test_get_entity(client):
    r = client.get(ENT)
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["name"] == "orders"
    assert result.get("description") == "Customer purchase orders"


def test_get_entity_not_found(client):
    assert client.get(COL + "/entity/ghost").status_code == 404


def test_register_update_delete_entity(client):
    path = COL + "/entity/temp_table"
    assert client.post(path, json={"description": "Temp"}).status_code == 200
    assert client.put(path, json={"description": "Updated"}).status_code == 200
    assert client.delete(path).status_code == 200
    assert client.get(path).status_code == 404


def test_collect_entity_stats(client):
    assert client.put(ENT + "/stats").status_code == 200


def test_entity_metadata_enrichment(client):
    assert client.put(ENT + "/metadata").status_code == 200


# ---------------------------------------------------------------------------
# Attribute
# ---------------------------------------------------------------------------

def test_list_attributes(client):
    r = client.get(ENT + "/attributes")
    assert r.status_code == 200
    names = [a["name"] for a in r.json()["results"]]
    assert "total" in names
    assert "status" in names


def test_get_attribute(client):
    r = client.get(ATTR)
    assert r.status_code == 200
    assert r.json()["result"]["name"] == "total"


def test_get_attribute_not_found(client):
    assert client.get(ENT + "/attribute/ghost").status_code == 404


def test_update_attribute(client):
    r = client.put(ATTR, json={"description": "Order total in USD"})
    assert r.status_code == 200
    # verify description was stored
    result = client.get(ATTR).json()["result"]
    assert result.get("description") == "Order total in USD"


def test_collect_attribute_stats(client):
    assert client.put(ATTR + "/stats").status_code == 200


def test_attribute_metadata_enrichment(client):
    assert client.put(ATTR + "/metadata").status_code == 200


def test_delete_attribute(client):
    path = ENT + "/attribute/status"
    assert client.delete(path).status_code == 200
    assert client.get(path).status_code == 404
