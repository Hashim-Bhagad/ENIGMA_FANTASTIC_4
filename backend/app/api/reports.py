"""Uploaded health reports: deterministic parameter building, never a diagnosis.

The extraction model only reads the document. Canonicalisation, unit conversion,
plausibility quarantine and every reference-range decision happen in
:mod:`app.services.labs`, so the stored value, its range and its status always agree
and can be reproduced from the stored row alone. The uploaded bytes are never stored
or logged: ``source`` keeps only the file's name, media type, size, SHA-256 and page
count.
"""

from __future__ import annotations

import hashlib
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import DependencyError, PyPdfError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.integrations.off import ProviderError
from app.models import HealthReport, Profile, User
from app.rate_limit import rate_limit
from app.schemas import (
    AgeBand,
    HealthReportConfirmRequest,
    HealthReportList,
    HealthReportResult,
    HealthReportSummary,
    LabParameter,
    ProfileData,
    Sex,
)
from app.security import current_user
from app.services.labs import LAB_REGISTRY, build_parameters, canonicalise

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health reports"], dependencies=[Depends(current_user)])

# A PDF whose text layer is shorter than this is a scan: photographs of its pages read
# far better than a silently empty extraction.
MIN_PDF_TEXT_CHARACTERS = 100

ABNORMAL_STATUSES = {"low", "high"}


def _sniff(content: bytes) -> str:
    """The media type of the upload from its leading bytes, never from the filename."""
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    raise HTTPException(415, "Upload a JPEG, PNG or PDF health report")


def _verify_image(content: bytes) -> None:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "Upload a readable JPEG or PNG report photo") from exc


def _pdf_text(content: bytes, max_pages: int) -> tuple[str, int]:
    """The PDF's own text layer and page count; a scan has no text layer."""
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = len(reader.pages)
        if pages > max_pages:
            raise HTTPException(
                422,
                f"Upload at most {max_pages} pages at a time; photograph the pages if the "
                "PDF is longer.",
            )
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PyPdfError, DependencyError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(
            422, "This PDF could not be read; photograph the pages and upload the photos instead"
        ) from exc
    return text.strip(), pages


def _profile_axes(session: Session, owner_id: str) -> tuple[Sex, AgeBand]:
    """The sex/age band that standard ranges are looked up with.

    Falls back to ``unspecified`` when the account has no saved profile, so an
    unknown sex or age never narrows a range by accident.
    """
    profile = session.scalars(select(Profile).where(Profile.owner_id == owner_id)).first()
    if profile is None:
        return ("unspecified", "unspecified")
    data = ProfileData.model_validate(profile.data)
    return (data.sex, data.age_band)


def _readings(raw: dict) -> tuple[list[dict], list[str]]:
    """The model's readings as ``build_parameters`` items, plus unrecognised-name warnings.

    A canonical key the model did not return is resolved from the printed name here, so
    the mapping the prompt asked for is never trusted blindly.
    """
    items: list[dict] = []
    warnings: list[str] = []
    for reading in raw["parameters"]:
        printed = reading.get("printed_name")
        key = reading.get("key") if reading.get("key") in LAB_REGISTRY else None
        if key is None:
            key = canonicalise(printed or "")
        entry = LAB_REGISTRY.get(key or "")
        if entry is None:
            named = printed or "Unnamed parameter"
            warnings.append(
                f"{named} is not a parameter this app recognises; its printed values are kept "
                "as unknown."
            )
        items.append(
            {
                "key": key or "unrecognised",
                "label": entry["label"] if entry else (printed or "Unrecognised parameter"),
                "value": reading.get("value"),
                "unit": reading.get("unit"),
                "reference_low": reading.get("reference_low"),
                "reference_high": reading.get("reference_high"),
                "raw_text": reading.get("raw_text") or printed,
            }
        )
    return items, warnings


def _parameters(report: HealthReport) -> list[LabParameter]:
    return [LabParameter.model_validate(row) for row in report.parameters or []]


def _abnormal(parameters: list[LabParameter]) -> list[str]:
    return [item.label for item in parameters if item.status in ABNORMAL_STATUSES]


def _result(report: HealthReport) -> HealthReportResult:
    parameters = _parameters(report)
    return HealthReportResult(
        id=report.id,
        status=report.status,
        collected_on=report.collected_on,
        parameters=parameters,
        abnormal_parameters=_abnormal(parameters),
        warnings=list(report.warnings or []),
        confirmation_required=report.status != "confirmed",
        source=dict(report.source or {}),
        provider=dict(report.provider or {}),
    )


def _summary(report: HealthReport) -> HealthReportSummary:
    parameters = _parameters(report)
    return HealthReportSummary(
        id=report.id,
        status=report.status,
        collected_on=report.collected_on,
        parameter_count=len(parameters),
        abnormal_count=len(_abnormal(parameters)),
        created_at=report.created_at.isoformat(),
    )


def _owned_report(session: Session, owner_id: str, report_id: str) -> HealthReport:
    """One report of this owner; another account's report does not exist for them."""
    report = session.get(HealthReport, report_id)
    if report is None or report.owner_id != owner_id:
        raise HTTPException(404, "Report not found")
    return report


async def _read_capped(file: UploadFile, settings: Settings) -> bytes:
    """Read at most the cap plus one byte, so an oversized body is rejected, not buffered."""
    content = await file.read(settings.report_max_bytes + 1)
    if len(content) > settings.report_max_bytes:
        raise HTTPException(
            413,
            f"Report file must be at most {settings.report_max_bytes / (1024 * 1024):g} MB",
        )
    return content


@router.post(
    "/reports/extract",
    response_model=HealthReportResult,
    dependencies=[Depends(rate_limit("report_extract", 10, 60, "user"))],
)
async def extract_report(
    request: Request,
    file: UploadFile,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Read one uploaded report and build its parameters in code. Requires a bearer token.

    JPEG/PNG photos go to the reading model; a PDF is read through its own text layer
    and sent as text, so a scanned PDF is refused with an explanation instead of
    returning nothing. The extraction is stored as ``extracted`` and must be confirmed
    before it can inform an intake plan.
    """
    settings = get_settings()
    content = await _read_capped(file, settings)
    media_type = _sniff(content)
    pages = 1
    if media_type == "application/pdf":
        document, pages = _pdf_text(content, settings.report_max_pages)
        if len(document) < MIN_PDF_TEXT_CHARACTERS:
            raise HTTPException(
                422,
                "This PDF has no text layer, so it is a scan rather than a digital report. "
                f"Photograph its {pages} page{'s' if pages != 1 else ''} and upload the photos.",
            )
    else:
        _verify_image(content)
        document = content
    try:
        raw = await request.app.state.models.extract_report(document, media_type)
    except ProviderError as exc:
        logger.warning("report extraction failed: %s", type(exc).__name__)
        raise HTTPException(503, str(exc)) from exc
    sex, age_band = _profile_axes(session, user.id)
    items, unrecognised = _readings(raw)
    parameters, warnings = build_parameters(items, sex, age_band)
    report = HealthReport(
        owner_id=user.id,
        status="extracted",
        collected_on=raw["collected_on"],
        parameters=[parameter.model_dump(mode="json") for parameter in parameters],
        warnings=[*raw["warnings"], *unrecognised, *warnings],
        source={
            "kind": "report_extraction",
            "reference": "User-uploaded health report",
            "filename": (file.filename or "")[:200] or None,
            "mime": media_type,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "pages": pages,
        },
        provider=dict(raw["provider"]),
    )
    session.add(report)
    session.commit()
    return _result(report)


@router.post("/reports/{report_id}/confirm", response_model=HealthReportResult)
def confirm_report(
    report_id: str,
    body: HealthReportConfirmRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Confirm the user's edited rows after rebuilding them deterministically.

    Every row is canonicalised, converted, quarantined and re-classified here, so a
    value the user never saw, or a status that no longer matches its value, cannot be
    stored.
    """
    report = _owned_report(session, user.id, report_id)
    sex, age_band = _profile_axes(session, user.id)
    parameters, warnings = build_parameters(
        [item.model_dump() for item in body.parameters], sex, age_band
    )
    report.status = "confirmed"
    report.collected_on = body.collected_on
    report.note = body.note
    report.parameters = [parameter.model_dump(mode="json") for parameter in parameters]
    report.warnings = warnings
    session.commit()
    return _result(report)


@router.get("/reports", response_model=HealthReportList)
def list_reports(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Newest-first summaries of the caller's own saved reports."""
    owner = HealthReport.owner_id == user.id
    total = session.scalar(select(func.count()).select_from(HealthReport).where(owner)) or 0
    reports = session.scalars(
        select(HealthReport)
        .where(owner)
        .order_by(HealthReport.created_at.desc(), HealthReport.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "reports": [_summary(report) for report in reports],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/reports/{report_id}", response_model=HealthReportResult)
def report_detail(
    report_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    """One owned report with its stored parameters, ranges, statuses and warnings."""
    return _result(_owned_report(session, user.id, report_id))


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(
    report_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> None:
    """Delete one owned report and its stored values."""
    session.delete(_owned_report(session, user.id, report_id))
    session.commit()
