"""Тесты валидации входных данных POST /api/contact."""

from __future__ import annotations


async def test_valid_contact_accepted(client, valid_payload):
    resp = await client.post("/api/contact", json=valid_payload)
    assert resp.status_code == 202
    body = resp.json()
    assert body["id"] > 0
    assert body["status"] == "received"


async def test_phone_normalized_to_e164(client, valid_payload):
    # Разные форматы одного номера должны приниматься.
    for phone in ["+7 900 123-45-67", "8 (900) 123-45-67", "89001234567"]:
        payload = {**valid_payload, "phone": phone}
        resp = await client.post("/api/contact", json=payload)
        assert resp.status_code == 202, f"phone={phone} -> {resp.text}"


async def test_invalid_email_rejected(client, valid_payload):
    resp = await client.post("/api/contact", json={**valid_payload, "email": "not-an-email"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_invalid_phone_rejected(client, valid_payload):
    resp = await client.post("/api/contact", json={**valid_payload, "phone": "123"})
    assert resp.status_code == 422


async def test_short_name_rejected(client, valid_payload):
    resp = await client.post("/api/contact", json={**valid_payload, "name": "A"})
    assert resp.status_code == 422


async def test_short_comment_rejected(client, valid_payload):
    resp = await client.post("/api/contact", json={**valid_payload, "comment": "hi"})
    assert resp.status_code == 422


async def test_extra_fields_forbidden(client, valid_payload):
    # extra="forbid" — защита от мусорных/инъекционных полей.
    resp = await client.post("/api/contact", json={**valid_payload, "is_admin": True})
    assert resp.status_code == 422


async def test_error_envelope_has_request_id(client, valid_payload):
    resp = await client.post("/api/contact", json={**valid_payload, "email": "bad"})
    body = resp.json()
    assert "request_id" in body
    assert resp.headers.get("X-Request-ID")
