"""Интеграционные тесты полного цикла и системных эндпоинтов."""

from __future__ import annotations


async def test_full_flow_processes_contact(client, valid_payload):
    """POST /contact → фоновая обработка (AI+email) должна проставить статус
    processed и заполнить AI-поля. httpx-клиент выполняет BackgroundTasks
    синхронно после ответа, поэтому к моменту проверки метрик всё готово."""
    resp = await client.post("/api/contact", json=valid_payload)
    assert resp.status_code == 202

    metrics = (await client.get("/api/metrics")).json()
    assert metrics["total"] == 1
    # После фоновой обработки обращение должно быть processed.
    assert metrics["by_status"].get("processed") == 1
    # Категория "project" распознана rule-based анализатором.
    assert metrics["by_category"].get("project") == 1


async def test_health_ok(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["ai_provider"] == "mock"


async def test_metrics_empty_initially(client):
    resp = await client.get("/api/metrics")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_emails_written_to_console_backend(client, valid_payload, tmp_path):
    """Проверяем, что console-бэкенд создаёт два .eml файла (владельцу + юзеру)."""
    import app.services.email_service as email_module

    # Перенаправляем вывод писем во временную папку.
    sender = email_module.ConsoleEmailSender(out_dir=str(tmp_path))
    email_module.get_email_service()._sender = sender

    await client.post("/api/contact", json=valid_payload)

    eml_files = list(tmp_path.glob("*.eml"))
    assert len(eml_files) == 2  # два письма


async def test_openapi_available(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "/api/contact" in schema["paths"]
