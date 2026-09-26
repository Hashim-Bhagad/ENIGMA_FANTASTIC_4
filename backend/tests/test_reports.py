"""Health-report API: extraction, deterministic building, confirmation and ownership.

The Fireworks endpoint is replaced with ``httpx.MockTransport`` so the tests exercise the
real client code path (schema, prompt, error handling) without a provider. Every number
the API stores must be reproducible from the document and the code, never from the model.
"""

import base64
import hashlib
import io
import json
from datetime import UTC, datetime

import httpx
import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import reports as reports_module
from app.config import Settings
from app.integrations.models import ModelAssist
from app.models import HealthReport, User
from app.services.labs import confirmed_reports
from tests.conftest import signup

REPORTS = "/api/reports"
FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"

# A five-row report whose text layer is well over the scanned-PDF threshold.
PDF_ROWS = [
    "Patient: A. Sharma    Collected: 2026-03-14",
    "Haemoglobin 10.2 g/dL 12.0 - 16.0",
    "Fasting Blood Glucose 92 mg/dL 70 - 100",
    "Total Cholesterol 5.4 mmol/L 3.6 - 5.2",
    "Serum Creatinine 1.1 mg/dL 0.7 - 1.3",
]


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (12, 12)).save(buffer, format="PNG")
    return buffer.getvalue()


def pdf_bytes(rows=None) -> bytes:
    """A PDF with a real (Helvetica) text layer, pages are joined by newlines."""
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    for text in rows if rows is not None else ["\n".join(PDF_ROWS)]:
        page = writer.add_blank_page(width=595, height=842)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        stream = DecodedStreamObject()
        body = (
            "BT /F1 11 Tf 40 780 Td 14 TL\n"
            + "".join(f"({line}) Tj T*\n" for line in text.split("\n"))
            + "ET"
        )
        stream.set_data(body.encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def reading(key=None, printed_name=None, value=None, unit=None, low=None, high=None, raw=None):
    return {
        "key": key,
        "printed_name": printed_name,
        "value": value,
        "unit": unit,
        "reference_low": low,
        "reference_high": high,
        "raw_text": raw,
    }


def provider(handler, **overrides) -> ModelAssist:
    """A reading model whose Fireworks endpoint is the supplied handler."""
    settings = Settings(fireworks_api_key="test-provider-key", **overrides)
    return ModelAssist(httpx.AsyncClient(transport=httpx.MockTransport(handler)), settings)


def replies(*documents: dict) -> tuple[object, list[httpx.Request]]:
    """One scripted response per call, recording each request for inspection."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert str(request.url) == FIREWORKS_URL
        payload = documents[min(len(seen) - 1, len(documents) - 1)]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(payload)}}
                ]
            },
        )

    return handler, seen


def document(parameters, collected_on=None, warnings=None) -> dict:
    return {
        "parameters": parameters,
        "collected_on": collected_on,
        "warnings": warnings if warnings is not None else [],
    }


def upload(client, headers, content=None, name="report.png", media="image/png"):
    return client.post(
        f"{REPORTS}/extract",
        headers=headers,
        files={"file": (name, content if content is not None else png_bytes(), media)},
    )


def user_id(client, headers) -> str:
    return client.get("/api/auth/me", headers=headers).json()["id"]


def save_profile(client, headers, data):
    response = client.put("/api/profiles/me", headers=headers, json={"data": data})
    assert response.status_code == 200, response.text


def pin_created_at(session, report_id, moment):
    """Ordering must not depend on two rows landing in the same microsecond."""
    session.get(HealthReport, report_id).created_at = datetime(*moment, tzinfo=UTC)


def test_extraction_canonicalises_converts_and_never_stores_the_file_bytes(client, db_engine):
    handler, seen = replies(
        document(
            [
                reading(
                    "hemoglobin_g_dl",
                    "Haemoglobin",
                    10.2,
                    "g/dL",
                    12.0,
                    16.0,
                    "Haemoglobin 10.2 g/dL 12.0 - 16.0",
                ),
                reading(None, "S. Cholesterol", 5.4, "mmol/L", 3.6, 5.2, "S. Cholesterol 5.4"),
                reading(None, "Vitamin E", 12.0, "mg/L", None, None, "Vitamin E 12.0"),
            ],
            collected_on="2026-03-14",
            warnings=["One row was faint."],
        )
    )
    headers = signup(client)
    client.app.state.models = provider(handler)
    image = png_bytes()
    response = upload(client, headers, image)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "extracted"
    assert body["confirmation_required"] is True
    assert body["collected_on"] == "2026-03-14"
    by_key = {item["key"]: item for item in body["parameters"]}

    haemoglobin = by_key["hemoglobin_g_dl"]
    assert (haemoglobin["value"], haemoglobin["unit"]) == (10.2, "g/dL")
    assert haemoglobin["reference_source"] == "document"
    assert (haemoglobin["reference_low"], haemoglobin["reference_high"]) == (12.0, 16.0)
    assert haemoglobin["status"] == "low"

    # The printed name was canonicalised and its unit converted by code, not the model.
    cholesterol = by_key["total_cholesterol_mg_dl"]
    assert cholesterol["unit"] == "mg/dL"
    assert cholesterol["value"] == pytest.approx(208.8, rel=1e-3)
    assert cholesterol["reference_source"] == "document"
    assert cholesterol["reference_high"] == pytest.approx(201.1, rel=1e-3)
    assert cholesterol["status"] == "high"

    # A printed name the registry does not know stays unknown instead of being repaired.
    unnamed = by_key["unrecognised"]
    assert unnamed["status"] == "unknown"
    assert unnamed["reference_source"] == "unknown"

    assert body["abnormal_parameters"] == ["Haemoglobin", "Total cholesterol"]
    assert any("Vitamin E" in warning for warning in body["warnings"])
    assert "One row was faint." in body["warnings"]
    # Only the first request carried the image, and the prompt asked for the canonical keys.
    assert len(seen) == 1
    request_body = json.loads(seen[0].content)
    assert request_body["temperature"] == 0
    assert request_body["response_format"]["type"] == "json_schema"
    assert request_body["max_tokens"] == Settings().report_max_tokens
    parts = request_body["messages"][0]["content"]
    assert [part["type"] for part in parts] == ["text", "image_url"]
    assert "hemoglobin_g_dl" in parts[0]["text"]
    assert "never infer a value" in parts[0]["text"]

    assert body["provider"] == {
        "provider": "fireworks",
        "model": Settings().fireworks_model,
        "input": "image",
    }
    assert body["source"] == {
        "kind": "report_extraction",
        "reference": "User-uploaded health report",
        "filename": "report.png",
        "mime": "image/png",
        "bytes": len(image),
        "sha256": hashlib.sha256(image).hexdigest(),
        "pages": 1,
    }

    with Session(db_engine) as session:
        stored = session.scalars(select(HealthReport)).one()
        # The row stores exactly the confirmed dumps, so no translation is needed.
        assert stored.parameters == [item for item in body["parameters"]]
        dumped = json.dumps({"parameters": stored.parameters, "source": stored.source})
        assert base64.b64encode(image).decode() not in dumped
        assert image[:24].hex() not in dumped


def test_document_range_wins_and_a_quarantined_value_gets_no_verdict(client):
    handler, _ = replies(
        document(
            [
                reading("fasting_glucose_mg_dl", "FBS", 110.0, "mg/dL", 70.0, 120.0),
                reading("hemoglobin_g_dl", "Hb", 900.0, "g/dL", None, None),
            ]
        )
    )
    headers = signup(client)
    client.app.state.models = provider(handler)
    body = upload(client, headers).json()
    by_key = {item["key"]: item for item in body["parameters"]}

    glucose = by_key["fasting_glucose_mg_dl"]
    assert glucose["status"] == "normal"  # the standard 70-100 range would have said high
    assert glucose["reference_source"] == "document"

    haemoglobin = by_key["hemoglobin_g_dl"]
    assert haemoglobin["value"] is None
    assert haemoglobin["status"] == "unknown"
    assert haemoglobin["reference_source"] == "standard"
    assert any("plausible range" in warning for warning in body["warnings"])
    assert body["abnormal_parameters"] == []


def test_profile_sex_and_age_choose_the_standard_range(client):
    handler, _ = replies(document([reading("hemoglobin_g_dl", "Hb", 11.8, "g/dL", None, None)]))
    headers = signup(client)
    client.app.state.models = provider(handler)

    without_profile = upload(client, headers).json()["parameters"][0]
    assert without_profile["status"] == "low"
    assert without_profile["reference_low"] == 12.0
    assert without_profile["reference_source"] == "standard"

    save_profile(client, headers, {"sex": "female", "age_band": "75_plus"})
    with_profile = upload(client, headers).json()["parameters"][0]
    assert with_profile["status"] == "normal"
    assert with_profile["reference_low"] == 11.7
    assert with_profile["reference_high"] == 15.0


def test_a_pdf_is_read_from_its_text_layer(client):
    handler, seen = replies(
        document([reading("fasting_glucose_mg_dl", "Fasting Blood Glucose", 92.0, "mg/dL", 70.0, 100.0)])
    )
    headers = signup(client)
    client.app.state.models = provider(handler)
    content = pdf_bytes()
    response = upload(client, headers, content, name="report.pdf", media="application/pdf")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parameters"][0]["status"] == "normal"
    assert body["source"]["mime"] == "application/pdf"
    assert body["source"]["pages"] == 1
    assert body["source"]["sha256"] == hashlib.sha256(content).hexdigest()
    assert body["provider"]["input"] == "pdf_text"
    parts = json.loads(seen[0].content)["messages"][0]["content"]
    assert [part["type"] for part in parts] == ["text", "text"]
    assert "Haemoglobin" in parts[1]["text"] and "Fasting Blood Glucose" in parts[1]["text"]
    assert "data:image" not in json.dumps(parts)


def test_a_scanned_pdf_asks_for_page_photos_and_never_calls_the_provider(client):
    handler, seen = replies(document([]))
    headers = signup(client)
    client.app.state.models = provider(handler)
    response = upload(
        client, headers, pdf_bytes([" "]), name="scan.pdf", media="application/pdf"
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "validation_error"
    assert "no text layer" in response.json()["detail"]
    assert "Photograph" in response.json()["detail"]
    assert seen == []


def test_a_pdf_longer_than_the_page_cap_is_refused(client, monkeypatch):
    handler, seen = replies(document([]))
    headers = signup(client)
    client.app.state.models = provider(handler)
    monkeypatch.setattr(
        reports_module, "get_settings", lambda: Settings(report_max_pages=1)
    )
    response = upload(
        client,
        headers,
        pdf_bytes(["\n".join(PDF_ROWS), "\n".join(PDF_ROWS)]),
        name="long.pdf",
        media="application/pdf",
    )
    assert response.status_code == 422, response.text
    assert "at most 1 pages" in response.json()["detail"]
    assert seen == []


def test_provider_failure_and_unconfigured_reading_return_503(client):
    headers = signup(client)
    client.app.state.models = provider(lambda request: httpx.Response(500, json={"error": "boom"}))
    failure = upload(client, headers)
    assert failure.status_code == 503, failure.text
    assert failure.json()["code"] == "provider_unavailable"
    assert "manually" in failure.json()["detail"]

    client.app.state.models = ModelAssist(
        httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))),
        Settings(),
    )
    unconfigured = upload(client, headers)
    assert unconfigured.status_code == 503, unconfigured.text
    assert unconfigured.json()["code"] == "provider_unavailable"
    assert "not configured" in unconfigured.json()["detail"]


def test_an_unparsable_provider_answer_requires_manual_entry(client):
    def handler(request):
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "not json"}}]}
        )

    headers = signup(client)
    client.app.state.models = provider(handler)
    response = upload(client, headers)
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "provider_unavailable"


def test_upload_limits_cover_size_and_media_type(client, monkeypatch):
    headers = signup(client)
    client.app.state.models = provider(lambda request: httpx.Response(500))
    monkeypatch.setattr(reports_module, "get_settings", lambda: Settings(report_max_bytes=2048))
    oversize = upload(client, headers, b"\x89PNG\r\n\x1a\n" + b"x" * 4096)
    assert oversize.status_code == 413, oversize.text
    assert oversize.json()["code"] == "payload_too_large"

    monkeypatch.undo()
    wrong_type = upload(client, headers, b"Fasting glucose 92 mg/dL", name="notes.txt", media="text/plain")
    assert wrong_type.status_code == 415, wrong_type.text
    assert wrong_type.json()["code"] == "unsupported_media_type"

    unreadable = upload(client, headers, b"\xff\xd8\xff" + b"garbage", name="broken.jpg")
    assert unreadable.status_code == 422, unreadable.text


def test_report_routes_require_a_token(client):
    assert client.post(f"{REPORTS}/extract").status_code == 401
    assert client.get(REPORTS).status_code == 401
    assert client.get(f"{REPORTS}/missing").status_code == 401
    assert client.delete(f"{REPORTS}/missing").status_code == 401
    assert client.post(f"{REPORTS}/missing/confirm", json={"parameters": []}).status_code == 401


def test_confirm_rebuilds_every_edited_row(client, db_engine):
    handler, _ = replies(
        document([reading("fasting_glucose_mg_dl", "FBS", 92.0, "mg/dL", 70.0, 100.0)])
    )
    headers = signup(client)
    client.app.state.models = provider(handler)
    extracted = upload(client, headers).json()
    assert extracted["parameters"][0]["status"] == "normal"

    rows = [dict(extracted["parameters"][0], value=250.0)]
    rows.append(
        {
            "key": "hemoglobin_g_dl",
            "label": "Haemoglobin",
            "value": 900.0,
            "unit": "g/dL",
            "reference_low": None,
            "reference_high": None,
            "reference_source": "unknown",
            "raw_text": "Hb 900",
            "status": "unknown",
        }
    )
    confirmed = client.post(
        f"{REPORTS}/{extracted['id']}/confirm",
        headers=headers,
        json={"parameters": rows, "collected_on": "2026-03-14", "note": "Checked against the sheet"},
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["status"] == "confirmed"
    assert body["confirmation_required"] is False
    assert body["collected_on"] == "2026-03-14"
    by_key = {item["key"]: item for item in body["parameters"]}
    # The edited value is re-classified against the document range in code.
    assert by_key["fasting_glucose_mg_dl"]["status"] == "high"
    assert by_key["fasting_glucose_mg_dl"]["reference_source"] == "document"
    assert by_key["hemoglobin_g_dl"]["value"] is None
    assert by_key["hemoglobin_g_dl"]["status"] == "unknown"
    assert any("plausible range" in warning for warning in body["warnings"])

    with Session(db_engine) as session:
        stored = session.get(HealthReport, extracted["id"])
        assert stored.status == "confirmed"
        assert stored.note == "Checked against the sheet"
        assert stored.parameters == [item for item in body["parameters"]]

    detail = client.get(f"{REPORTS}/{extracted['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "confirmed"


def test_list_detail_delete_are_owner_scoped_newest_first_and_total_counted(client, db_engine):
    handler, _ = replies(
        document([reading("tsh_miu_l", "TSH", 2.4, "mIU/L", 0.4, 4.0)]),
        document([reading("hba1c_percent", "HbA1c", 5.2, "%", 4.0, 5.6)]),
    )
    headers = signup(client)
    client.app.state.models = provider(handler)
    older = upload(client, headers).json()
    newer = upload(client, headers).json()
    with Session(db_engine) as session:
        pin_created_at(session, older["id"], (2026, 1, 1))
        pin_created_at(session, newer["id"], (2026, 2, 1))
        session.commit()

    page = client.get(REPORTS, headers=headers, params={"limit": 1})
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert page.json()["limit"] == 1
    assert [item["id"] for item in page.json()["reports"]] == [newer["id"]]
    assert page.json()["reports"][0]["parameter_count"] == 1
    assert page.json()["reports"][0]["abnormal_count"] == 0

    second_page = client.get(REPORTS, headers=headers, params={"limit": 5, "offset": 1})
    assert [item["id"] for item in second_page.json()["reports"]] == [older["id"]]

    other = signup(client, "other@example.com")
    assert client.get(REPORTS, headers=other).json()["total"] == 0
    assert client.get(f"{REPORTS}/{newer['id']}", headers=other).status_code == 404
    assert (
        client.post(
            f"{REPORTS}/{newer['id']}/confirm",
            headers=other,
            json={"parameters": []},
        ).status_code
        == 404
    )
    assert client.delete(f"{REPORTS}/{newer['id']}", headers=other).status_code == 404

    deleted = client.delete(f"{REPORTS}/{older['id']}", headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"{REPORTS}/{older['id']}", headers=headers).status_code == 404
    assert client.get(REPORTS, headers=headers).json()["total"] == 1


def test_confirmed_reports_returns_this_owners_confirmed_rows_newest_first(client, db_engine):
    handler, _ = replies(
        document([reading("tsh_miu_l", "TSH", 2.4, "mIU/L", 0.4, 4.0)]),
        document([reading("hba1c_percent", "HbA1c", 5.2, "%", 4.0, 5.6)]),
    )
    headers = signup(client)
    client.app.state.models = provider(handler)
    first = upload(client, headers).json()
    second = upload(client, headers).json()
    for report in (first, second):
        rows = client.get(f"{REPORTS}/{report['id']}", headers=headers).json()["parameters"]
        assert (
            client.post(
                f"{REPORTS}/{report['id']}/confirm", headers=headers, json={"parameters": rows}
            ).status_code
            == 200
        )
    other = signup(client, "second@example.com")
    other_report = upload(client, other).json()
    other_rows = client.get(f"{REPORTS}/{other_report['id']}", headers=other).json()["parameters"]
    assert (
        client.post(
            f"{REPORTS}/{other_report['id']}/confirm", headers=other, json={"parameters": other_rows}
        ).status_code
        == 200
    )

    with Session(db_engine) as session:
        for report, moment in ((first, (2026, 1, 1)), (second, (2026, 2, 1))):
            pin_created_at(session, report["id"], moment)
        session.commit()
        owner = session.get(User, user_id(client, headers)).id
        confirmed = confirmed_reports(session, owner)

    assert [item["id"] for item in confirmed] == [second["id"], first["id"]]
    assert confirmed[0]["parameters"][0]["key"] == "hba1c_percent"
    assert confirmed[0]["parameters"][0]["status"] == "normal"
    assert other_report["id"] not in [item["id"] for item in confirmed]

    # An unconfirmed extraction never reaches the intake plan.
    with Session(db_engine) as session:
        pending = session.get(HealthReport, second["id"])
        pending.status = "extracted"
        session.commit()
        assert [item["id"] for item in confirmed_reports(session, owner)] == [first["id"]]
