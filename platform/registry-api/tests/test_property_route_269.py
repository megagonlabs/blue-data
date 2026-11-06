"""#269: POST /{source}/property/{key} passed rebuild=True to set_source_property,
which did not accept it, so a valid call returned 500 (TypeError). The DELETE route
had the same shape. These assert both routes work end to end.
"""


def test_set_source_property_route_succeeds(client):
    r = client.post("/sales/property/description_note", params={"value": "a note"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Success"
    got = client.get("/sales/property/description_note")
    assert got.json()["result"] == "a note"


def test_set_source_property_route_does_not_persist_a_secret(client):
    r = client.post("/sales/property/api_token", params={"value": "FAKE-TOKEN-269"})
    assert r.status_code == 200, r.text
    # the credential must not be stored on the record
    props = client.get("/sales/properties").json()["results"]
    assert "FAKE-TOKEN-269" not in str(props)


def test_delete_source_property_route_succeeds(client):
    client.post("/sales/property/description_note", params={"value": "x"})
    r = client.delete("/sales/property/description_note")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Success"
