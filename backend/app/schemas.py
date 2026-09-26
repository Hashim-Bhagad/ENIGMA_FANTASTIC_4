from typing import Annotated, Literal

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
    kind: Literal["openfoodfacts", "apify_off", "manual", "label_extraction", "demo"]
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
    profile_id: str
    profile_version: int = Field(ge=1)
    food: FoodObservation
    portion: Positive | None = None


class RecommendationRequest(StrictModel):
    assessment_id: str
    preferences: str | None = Field(default=None, max_length=500)


class GuideRequest(StrictModel):
    profile_id: str
    profile_version: int = Field(ge=1)
