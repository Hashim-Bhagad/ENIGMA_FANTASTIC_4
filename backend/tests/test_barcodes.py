"""Barcode-from-image decoding: the web path that replaces a phone camera scan."""

import io

import barcode
import pytest
from barcode.writer import ImageWriter
from PIL import Image

from app.services.barcodes import decode_barcodes
from tests.conftest import signup


def retail_png(code: str = "890123456789", symbology: str = "ean13") -> bytes:
    """A real barcode rendered by python-barcode (checksum computed for us)."""
    writer = ImageWriter()
    stream = io.BytesIO()
    barcode.get(symbology, code, writer=writer).write(
        stream,
        options={"module_width": 0.5, "module_height": 18.0, "quiet_zone": 9.0, "font_size": 0},
    )
    return stream.getvalue()


def test_decode_reads_a_retail_barcode_and_ignores_non_retail_payloads():
    decoded = decode_barcodes(retail_png("890123456789"))
    assert decoded == [{"barcode": "8901234567890", "format": "EAN-13"}]

    # A Code-128 carrying letters is not a product identifier and must never be returned.
    text_code = retail_png("PROMO-ABC-123", symbology="code128")
    assert decode_barcodes(text_code) == []

    assert decode_barcodes(b"not an image") == []


def test_scan_endpoint_returns_the_number_from_a_photo(client):
    headers = signup(client)
    response = client.post(
        "/api/barcodes/scan",
        headers=headers,
        files={"file": ("barcode.png", retail_png("890123456789"), "image/png")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["barcode"] == "8901234567890"
    assert body["format"] == "EAN-13"
    assert "message" in body


def test_scan_endpoint_explains_an_image_without_a_barcode(client):
    headers = signup(client)
    blank = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(blank, format="PNG")
    response = client.post(
        "/api/barcodes/scan",
        headers=headers,
        files={"file": ("blank.png", blank.getvalue(), "image/png")},
    )
    assert response.status_code == 422
    assert "No barcode found" in response.json()["detail"]
    assert response.json()["code"] == "validation_error"


def test_scan_endpoint_rejects_junk_oversize_and_anonymous_callers(client):
    headers = signup(client)
    junk = client.post(
        "/api/barcodes/scan",
        headers=headers,
        files={"file": ("notes.txt", b"this is not an image", "text/plain")},
    )
    assert junk.status_code == 422
    assert "readable image" in junk.json()["detail"]

    oversized = client.post(
        "/api/barcodes/scan",
        headers=headers,
        files={"file": ("big.png", b"x" * (8 * 1024 * 1024 + 10), "image/png")},
    )
    assert oversized.status_code == 413
    assert "limit is 8 MB" in oversized.json()["detail"]

    assert (
        client.post(
            "/api/barcodes/scan", files={"file": ("barcode.png", retail_png(), "image/png")}
        ).status_code
        == 401
    )


def test_scan_endpoint_is_rate_limited(client, monkeypatch):
    from app import rate_limit as rate_limit_module
    from app.config import get_settings

    monkeypatch.setattr(
        rate_limit_module,
        "get_settings",
        lambda: get_settings().model_copy(update={"rate_limit_barcode_scan_per_minute": 2}),
    )
    rate_limit_module.reset()
    headers = signup(client)
    statuses = [
        client.post(
            "/api/barcodes/scan",
            headers=headers,
            files={"file": ("barcode.png", retail_png(), "image/png")},
        ).status_code
        for _ in range(3)
    ]
    assert statuses[:2] == [200, 200], statuses
    assert statuses[2] == 429, statuses


@pytest.mark.parametrize("code", ["8901234567890", "1234567890128"])
def test_scan_accepts_other_retail_codes(client, code):
    headers = signup(client)
    response = client.post(
        "/api/barcodes/scan",
        headers=headers,
        files={"file": ("barcode.png", retail_png(code[:-1]), "image/png")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["barcode"] == code
