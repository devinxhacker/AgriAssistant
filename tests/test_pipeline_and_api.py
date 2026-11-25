"""End-to-end API, WhatsApp webhook, Admin RBAC, and Privacy tests."""


def test_health_and_query_and_feedback_flow(client):
    h = client.get("/health")
    assert h.status_code == 200
    assert h.json()["approved_documents"] >= 8

    q = client.post(
        "/api/v1/query",
        json={
            "text": "माझ्या कापूस पिकाची पाने पिवळी पडत आहेत, काय करावे?",
            "phone_number": "+919876543210",
            "synthesize_audio": True,
        },
    )
    assert q.status_code == 200
    data = q.json()
    assert data["decision"] == "answer"
    assert data["language"] == "mr"
    assert data["audio_url"] is not None

    # Audio endpoint serves generated reply
    aud = client.get(data["audio_url"])
    assert aud.status_code == 200

    # Feedback endpoint
    fb = client.post(
        "/api/v1/feedback",
        json={"interaction_id": data["interaction_id"], "rating": 1, "comment": "Helpful"},
    )
    assert fb.status_code == 200


def test_whatsapp_webhook_verify_and_dedup(client):
    verify = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "sagveek_agri_verify_2026",
            "hub.challenge": "123456",
        },
    )
    assert verify.status_code == 200
    assert verify.text == "123456"

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.test_001",
                                    "from": "919876543210",
                                    "type": "text",
                                    "text": {"body": "PM-KISAN e-KYC कैसे करें?"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    r1 = client.post("/webhooks/whatsapp", json=payload)
    assert r1.status_code == 200
    assert r1.json()["processed"][0]["decision"] == "answer"

    # Second delivery with same message id must be deduplicated
    r2 = client.post("/webhooks/whatsapp", json=payload)
    assert r2.status_code == 200
    assert r2.json()["processed"][0]["status"] == "duplicate_ignored"


def test_admin_rbac_and_privacy_erasure(client):
    # Analyst cannot approve documents
    resp = client.post(
        "/api/v1/admin/documents/doc_missing/approval?status=approved",
        headers={"X-Admin-Role": "analyst"},
    )
    assert resp.status_code == 403

    # Delete user data
    from app.db.privacy import hash_phone

    p_hash = hash_phone("+919811122233")
    client.post(
        "/api/v1/privacy/consent",
        json={"phone_number": "+919811122233", "granted": True},
    )
    del_resp = client.delete(f"/api/v1/privacy/user/{p_hash}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted_sessions"] == 1
