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
    "wheat",
    "milk",
    "eggs",
    "soy",
    "peanuts",
    "tree_nuts",
    "sesame",
    "fish",
    "shellfish",
    # EU-14 remainder: these are matched by ingredient name only, never by a packaged
    # "contains" tag, so the evidence stays explicit about what was actually declared.
    "celery",
    "mustard",
    "lupin",
    "molluscs",
    "sulphites",
]
Sex = Literal["female", "male", "unspecified"]
AgeBand = Literal["under_18", "18_29", "30_44", "45_59", "60_74", "75_plus", "unspecified"]
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
    allergies: list[Allergen] = Field(default_factory=list, max_length=14)
    ingredient_exclusions: list[Annotated[str, Field(min_length=2, max_length=80)]] = Field(
        default_factory=list, max_length=30
    )
    limits: list[Limit] = Field(default_factory=list, max_length=10)
    goals: list[Goal] = Field(default_factory=list, max_length=5)
    preferences: str = Field(default="", max_length=500)
    # Optional: reference ranges and energy/iron baselines differ by sex and age band.
    # "unspecified" keeps the wider range and says so in the intake plan.
    sex: Sex = "unspecified"
    age_band: AgeBand = "unspecified"

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
    declared_allergens: list[Allergen] = Field(default_factory=list, max_length=14)
    precautionary_allergens: list[Allergen] = Field(default_factory=list, max_length=14)
    reported_allergens: list[Allergen] = Field(default_factory=list, max_length=14)
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


class DishEstimateExclusion(ResponseModel):
    input_text: str
    reason: str


class DishEstimate(ResponseModel):
    available: bool
    basis: str | None = None
    nutrients: dict[str, float | None] = Field(default_factory=dict)
    total_grams: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    # A reference table is not a recipe book: ingredients it does not measure are listed
    # here so the estimate is read as a floor rather than the whole dish.
    matched_count: int = 0
    matched_grams: float | None = None
    excluded: list[DishEstimateExclusion] = Field(default_factory=list)
    coverage_note: str = ""


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


# --- Health reports and personal intake (frozen contract) -------------------------------
ReferenceSource = Literal["document", "standard", "unknown"]
ParameterStatus = Literal["low", "normal", "high", "unknown"]
GuidanceConfidence = Literal["established", "general_wellbeing", "clinician_only"]


class LabParameter(StrictModel):
    """One measured value from a health report.

    ``status`` and any unit conversion are always computed in code; the model only
    reads the document. ``raw_text`` keeps the label as printed so a correction is
    auditable.
    """

    key: str = Field(min_length=2, max_length=60)
    label: str = Field(min_length=1, max_length=120)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=30)
    reference_low: float | None = None
    reference_high: float | None = None
    reference_source: ReferenceSource = "unknown"
    raw_text: str | None = Field(default=None, max_length=200)
    status: ParameterStatus = "unknown"


class ReportConfirm(LabParameter):
    """A confirmed parameter as the user accepts it (edited values allowed)."""


class HealthReportResult(ResponseModel):
    id: str
    status: Literal["extracted", "confirmed"]
    collected_on: str | None = None
    parameters: list[LabParameter]
    abnormal_parameters: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confirmation_required: bool = True
    source: dict[str, Any] = Field(default_factory=dict)
    provider: dict[str, Any] = Field(default_factory=dict)


class HealthReportSummary(ResponseModel):
    id: str
    status: Literal["extracted", "confirmed"]
    collected_on: str | None = None
    parameter_count: int
    abnormal_count: int
    created_at: str


class HealthReportList(ResponseModel):
    reports: list[HealthReportSummary]
    total: int
    limit: int
    offset: int


class HealthReportConfirmRequest(StrictModel):
    parameters: list[ReportConfirm] = Field(default_factory=list, max_length=60)
    collected_on: str | None = Field(default=None, max_length=20)
    note: str = Field(default="", max_length=500)


class ConditionInfo(ResponseModel):
    slug: str
    label: str
    category: str
    aliases: list[str] = Field(default_factory=list)
    nutrient_focus: list[str] = Field(default_factory=list)
    awareness: str
    questions: list[str] = Field(default_factory=list, max_length=10)
    sources: list[str] = Field(default_factory=list, max_length=6)
    lab_links: list[str] = Field(default_factory=list)
    guidance_confidence: GuidanceConfidence = "general_wellbeing"


class ConditionRegistry(ResponseModel):
    version: str
    conditions: list[ConditionInfo]
    categories: list[str] = Field(default_factory=list)
    coverage: str
    notes: list[str] = Field(default_factory=list)


class IntakeEvidence(ResponseModel):
    kind: Literal["lab", "condition", "baseline"]
    label: str
    detail: str
    parameter_key: str | None = None
    value: float | None = None
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    report_id: str | None = None
    # The date printed on the report, so a measured value reads "Report 2026-09-20".
    measured_on: str | None = None


class IntakeEquivalent(ResponseModel):
    """A human-scale reading of the same number (grams of salt, teaspoons of sugar)."""

    label: str
    value: float
    unit: str


class AvoidItem(ResponseModel):
    """One concrete thing to avoid or limit, with the reason it is listed."""

    label: str
    examples: list[str] = Field(default_factory=list, max_length=12)
    reason: str
    linked_nutrients: list[str] = Field(default_factory=list, max_length=6)


class AvoidGroup(ResponseModel):
    id: str
    title: str
    detail: str
    severity: Literal["avoid", "limit", "ask"] = "limit"
    items: list[AvoidItem] = Field(default_factory=list, max_length=12)
    confidence: GuidanceConfidence = "general_wellbeing"
    sources: list[str] = Field(default_factory=list, max_length=6)
    evidence: list["IntakeEvidence"] = Field(default_factory=list)


class IntakeTarget(ResponseModel):
    nutrient: str
    label: str
    unit: str
    baseline_value: float | None = None
    baseline_source: str
    proposed_value: float | None = None
    direction: Literal["lower", "higher", "maintain"]
    rule_id: str
    basis: str
    confidence: GuidanceConfidence
    requires_clinician: bool = False
    evidence: list[IntakeEvidence] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list, max_length=6)
    limit_scope: Literal["daily", "portion"] = "daily"
    suggested_limit_source: str | None = None
    # The same number in the units people cook with, and the arithmetic that produced it.
    display_value: str | None = None
    equivalents: list[IntakeEquivalent] = Field(default_factory=list)
    derivation: str | None = None
    measured: list["IntakeEvidence"] = Field(default_factory=list)


class IntakePlan(ResponseModel):
    version: str
    targets: list[IntakeTarget]
    avoid: list[AvoidGroup] = Field(default_factory=list)
    conditions: list[ConditionInfo] = Field(default_factory=list)
    unrecognised_conditions: list[str] = Field(default_factory=list)
    reports_used: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    coverage: str


class IntakePlanRequest(StrictModel):
    profile_id: UUID
    profile_version: int = Field(ge=1)
