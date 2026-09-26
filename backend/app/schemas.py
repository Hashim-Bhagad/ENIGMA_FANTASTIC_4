from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Nutrient = Literal[
    "sodium_mg",
    "potassium_mg",
    "phosphorus_mg",
    "carbohydrates_g",
    "protein_g",
    "fat_g",
    "saturated_fat_g",
    "sugars_g",
    "fiber_g",
    "energy_kcal",
]
Allergen = Literal[
    "wheat", "milk", "eggs", "soy", "peanuts", "tree_nuts", "sesame", "fish", "shellfish"
]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    """Response-only base: unknown engine keys pass through so the contract can extend."""

    model_config = ConfigDict(extra="allow")


class Credentials(StrictModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class Login(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Limit(StrictModel):
    nutrient: Nutrient
    maximum: Positive
    scope: Literal["daily", "portion"] = "daily"
    source: str = Field(min_length=1, max_length=200)


class Goal(StrictModel):
    nutrient: Nutrient
    direction: Literal["lower", "higher"] = "lower"


class ProfileData(StrictModel):
    conditions: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        default_factory=list, max_length=20
    )
    allergies: list[Allergen] = Field(default_factory=list, max_length=9)
    ingredient_exclusions: list[Annotated[str, Field(min_length=2, max_length=80)]] = Field(
        default_factory=list, max_length=30
    )
    limits: list[Limit] = Field(default_factory=list, max_length=10)
    goals: list[Goal] = Field(default_factory=list, max_length=5)
    preferences: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def unique_targets(self):
        if len({x.nutrient for x in self.goals}) != len(self.goals):
            raise ValueError("Comparison goals must have unique nutrients")
        if len({(x.nutrient, x.scope) for x in self.limits}) != len(self.limits):
            raise ValueError("Limits must have unique nutrient/scope pairs")
        return self


class ProfileWrite(StrictModel):
    expected_version: int | None = Field(default=None, ge=1)
    data: ProfileData


class Source(StrictModel):
    kind: Literal["openfoodfacts", "apify_off", "manual", "label_extraction", "demo", "dish"]
    reference: str = Field(min_length=1, max_length=500)
    retrieved_at: str | None = Field(default=None, max_length=60)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    model: str | None = Field(default=None, max_length=100)
    edited_fields: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        default_factory=list, max_length=30
    )


class FoodObservation(StrictModel):
    name: str = Field(min_length=1, max_length=300)
    brand: str | None = Field(default=None, max_length=200)
    barcode: str | None = Field(default=None, pattern=r"^(?:[0-9]{8}|[0-9]{12,14})$")
    category: str | None = Field(default=None, min_length=1, max_length=120)
    basis: Literal["100g", "100ml"] | None = None
    ingredients_text: str | None = Field(default=None, max_length=15000)
    advisories_text: str | None = Field(default=None, max_length=4000)
    ingredients_complete: bool = False
    advisories_complete: bool = False
    declared_allergens: list[Allergen] = Field(default_factory=list, max_length=9)
    precautionary_allergens: list[Allergen] = Field(default_factory=list, max_length=9)
    reported_allergens: list[Allergen] = Field(default_factory=list, max_length=9)
    nutrients: dict[Nutrient, Annotated[float, Field(ge=0, allow_inf_nan=False)] | None] = Field(
        default_factory=dict
    )
    source: Source

    @model_validator(mode="after")
    def valid_observations(self):
        if self.ingredients_complete and not self.ingredients_text:
            raise ValueError("Complete ingredients require a nonempty ingredient list")
        if self.advisories_complete and self.advisories_text is None:
            raise ValueError("Confirmed advisory absence must be an explicit empty string")
        if any(v is not None for v in self.nutrients.values()) and self.basis is None:
            raise ValueError("Known nutrient values require a declared 100g/100ml basis")
        for key, value in self.nutrients.items():
            maximum = 100000 if key.endswith("_mg") else 1000 if key.endswith("_kcal") else 100
            if value is not None and value > maximum:
                raise ValueError(f"{key} is physically implausible on the declared basis")
        return self


class AssessmentRequest(StrictModel):
    profile_id: UUID
    profile_version: int = Field(ge=1)
    food: FoodObservation
    portion: Positive | None = None


class RecommendationRequest(StrictModel):
    assessment_id: UUID
    preferences: str | None = Field(default=None, max_length=500)


class GuideRequest(StrictModel):
    profile_id: UUID
    profile_version: int = Field(ge=1)


class DishIngredient(StrictModel):
    text: str = Field(min_length=1, max_length=200)
    reference_code: str | None = Field(default=None, min_length=1, max_length=40)
    grams: Positive | None = None


class DishRequest(StrictModel):
    profile_id: UUID
    profile_version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    ingredients: list[DishIngredient] = Field(min_length=1, max_length=40)
    cooking_notes: list[str] = Field(default_factory=list, max_length=10)
    # The cook confirms the list is complete and the dish has no packaged advisory panel.
    declarations_confirmed: bool = False
    portion_g: Positive | None = None


class Finding(ResponseModel):
    """One explanation row. `code` is stable; `title`/`detail`/`next_step` are user-facing."""

    code: str = Field(min_length=2, max_length=60)
    group: Literal["conflict", "unresolved", "consideration"]
    title: str = Field(min_length=2, max_length=160)
    detail: str = Field(min_length=2, max_length=700)
    next_step: str | None = Field(default=None, max_length=400)
    affects: list[str] = Field(default_factory=list, max_length=20)
    message: str = Field(min_length=2, max_length=400)
    evidence: list[str] = Field(default_factory=list, max_length=50)


class AssessmentResult(ResponseModel):
    rule_version: str
    ingredient_taxonomy_version: str
    status: Literal["recorded_conflict", "needs_information", "no_matching_concern_found"]
    status_reason: str
    conflicts: list[Finding]
    unresolved: list[Finding]
    considerations: list[Finding]
    ingredient_findings: list[dict[str, Any]]
    source_warnings: list[str]
    coverage: str


class RecommendationCandidate(ResponseModel):
    product_id: str
    food: dict[str, Any]
    assessment: AssessmentResult
    comparisons: list[dict[str, Any]]
    improvements: list[str]
    verified: bool = True
    review_reasons: list[str] = Field(default_factory=list, max_length=10)


class RecommendationResult(ResponseModel):
    candidates: list[RecommendationCandidate]
    needs_review: list[RecommendationCandidate] = Field(default_factory=list)
    excluded: list[dict[str, Any]]
    ranking_method: str
    fallback_reason: str | None = None
    message: str


# --- Response wrappers appended for OpenAPI wiring (record metadata around engine payloads) ---


class AssessmentResponse(ResponseModel):
    id: str
    profile_id: str
    profile_version: int
    profile_snapshot: dict[str, Any]
    food: dict[str, Any]
    result: AssessmentResult
    created_at: str


class AssessmentHistory(ResponseModel):
    assessments: list[AssessmentResponse]
    limit: int
    offset: int
    total: int


class RecommendationRecord(RecommendationResult):
    id: str
    assessment_id: str


class DishMatch(ResponseModel):
    input_text: str
    code: str
    name: str
    basis: str | None = None
    grams: float | None = None
    matched_by: str


class DishUnmatched(ResponseModel):
    input_text: str
    reason: str


class DishEstimate(ResponseModel):
    available: bool
    basis: str | None = None
    nutrients: dict[str, float | None] = Field(default_factory=dict)
    total_grams: float | None = None
    assumptions: list[str] = Field(default_factory=list)


class DishResult(ResponseModel):
    name: str
    matches: list[DishMatch]
    unmatched: list[DishUnmatched]
    estimate: DishEstimate


class CookingNote(ResponseModel):
    code: str
    label: str
    detail: str
    next_step: str | None = None


class DishOptions(ResponseModel):
    cooking_notes: list[CookingNote]
    unknowns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class DishAssessmentResponse(ResponseModel):
    id: str
    dish: DishResult
    assessment: AssessmentResult
