from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.accounts import owned_profile
from app.db import get_session
from app.errors import ApiError
from app.models import Assessment, Product, Profile, RecommendationRun, User
from app.rate_limit import rate_limit
from app.schemas import (
    AssessmentHistory,
    AssessmentRequest,
    AssessmentResponse,
    FoodObservation,
    ProfileData,
    RecommendationRecord,
    RecommendationRequest,
)
from app.security import current_user
from app.services.assessment import assess
from app.services.provenance import product_provenance
from app.services.recommendations import select_replacements
from app.services.result_history import normalize_assessment_payload, normalize_result

router = APIRouter(prefix="/api", tags=["assessments and replacements"])


def assessment_response(record: Assessment):
    return {
        "id": record.id,
        "profile_id": record.profile_id,
        "profile_version": record.profile_version,
        "profile_snapshot": record.profile_snapshot,
        "food": record.food_snapshot,
        "result": normalize_result(record.result),
        "created_at": record.created_at.isoformat(),
    }


def owned_assessment(session: Session, user_id: str, record_id: str):
    # Request bodies carry UUID objects; the column stores the canonical string form.
    record = session.scalar(
        select(Assessment).where(Assessment.id == str(record_id), Assessment.owner_id == user_id)
    )
    if record is None:
        raise HTTPException(404, "Assessment not found")
    return record


@router.post("/assessments", status_code=201, response_model=AssessmentResponse)
def create_assessment(
    body: AssessmentRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    profile = owned_profile(session, user.id, body.profile_id)
    if profile.version != body.profile_version:
        raise ApiError(409, "profile_version_stale", "Profile changed; reload before assessment")
    profile_data = ProfileData.model_validate(profile.data)
    # Lock/check the profile version through the write so an edit cannot silently race this snapshot.
    session.refresh(profile, with_for_update=True)
    if profile.version != body.profile_version:
        raise ApiError(409, "profile_version_stale", "Profile changed; reload before assessment")
    source_trace = None
    if body.food.barcode:
        product = session.scalar(select(Product).where(Product.barcode == body.food.barcode))
        if (
            product
            and product.source_kind == body.food.source.kind
            and product.observation["source"]["reference"] == body.food.source.reference
        ):
            source_trace = product_provenance(product)
            submitted = body.food.model_dump(mode="json")
            changed = [
                field
                for field in ("name", "category", "basis", "ingredients_text", "advisories_text")
                if submitted.get(field) != product.observation.get(field)
            ]
            changed.extend(
                key
                for key, value in body.food.nutrients.items()
                if value != product.observation.get("nutrients", {}).get(key)
            )
            source_trace["edited_fields"] = sorted(
                set(changed) | set(body.food.source.edited_fields)
            )
            source_trace["submitted_source_retrieved_at"] = body.food.source.retrieved_at
            source_trace["scope"] = (
                "Catalog source snapshot at assessment time; submitted corrections are held in food_snapshot."
            )
    record = Assessment(
        owner_id=user.id,
        profile_id=profile.id,
        profile_version=profile.version,
        profile_snapshot=profile_data.model_dump(mode="json"),
        food_snapshot=body.food.model_dump(mode="json"),
        result={
            **assess(profile_data, body.food, body.portion),
            "portion": body.portion,
            "source_trace": source_trace,
        },
    )
    session.add(record)
    session.commit()
    return assessment_response(record)


@router.get("/assessments", response_model=AssessmentHistory)
def history(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    owner = Assessment.owner_id == user.id
    total = session.scalar(select(func.count()).select_from(Assessment).where(owner)) or 0
    records = session.scalars(
        select(Assessment)
        .where(owner)
        .order_by(Assessment.created_at.desc(), Assessment.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return {
        "assessments": [assessment_response(x) for x in records],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get("/assessments/{record_id}", response_model=AssessmentResponse)
def assessment_detail(
    record_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    return assessment_response(owned_assessment(session, user.id, record_id))


@router.post(
    "/recommendations",
    status_code=201,
    response_model=RecommendationRecord,
    dependencies=[Depends(rate_limit("recommendations", 20, 60, "user"))],
)
async def recommend(
    body: RecommendationRequest,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    assessment = owned_assessment(session, user.id, body.assessment_id)
    profile = owned_profile(session, user.id, assessment.profile_id)
    if profile.version != assessment.profile_version:
        raise ApiError(
            409,
            "profile_version_stale",
            "Profile changed; create a new assessment before requesting replacements",
        )
    data, food = (
        ProfileData.model_validate(assessment.profile_snapshot),
        FoodObservation.model_validate(assessment.food_snapshot),
    )
    if food.source.kind == "dish":
        raise HTTPException(422, "Recommendations are not offered for cooked dishes")
    products = (
        list(
            session.scalars(
                select(Product)
                .where(Product.category == food.category)
                .order_by(Product.id)
                .limit(100)
            )
        )
        if food.category
        else []
    )
    candidates = [(x.id, FoodObservation.model_validate(x.observation)) for x in products]
    result = select_replacements(data, food, candidates, assessment.result.get("portion"))
    owner_id, profile_id, profile_version, assessment_id = (
        user.id,
        profile.id,
        profile.version,
        assessment.id,
    )
    session.rollback()
    result = await request.app.state.models.rank_preferences(
        result, body.preferences if body.preferences is not None else data.preferences
    )
    # Do not hold a transaction while waiting for inference; recheck profile before persisting.
    current = session.scalar(
        select(Profile)
        .where(Profile.id == profile_id, Profile.owner_id == owner_id)
        .with_for_update()
    )
    if current is None or current.version != profile_version:
        raise ApiError(
            409,
            "profile_version_stale",
            "Profile changed during recommendation; create a new assessment",
        )
    record = RecommendationRun(owner_id=owner_id, assessment_id=assessment_id, result=result)
    session.add(record)
    session.commit()
    return {"id": record.id, "assessment_id": assessment_id, **result}


@router.get("/recommendations/{record_id}", response_model=RecommendationRecord)
def recommendation_detail(
    record_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    record = session.scalar(
        select(RecommendationRun).where(
            RecommendationRun.id == record_id, RecommendationRun.owner_id == user.id
        )
    )
    if record is None:
        raise HTTPException(404, "Recommendation not found")
    return {
        "id": record.id,
        "assessment_id": record.assessment_id,
        **normalize_assessment_payload(record.result),
    }
