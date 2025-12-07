"""Data models for representing recipe information during the import workflow."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, validator, ConfigDict


class Ingredient(BaseModel):
    id: Optional[str] = None
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    note: Optional[str] = None
    deleted: Optional[bool] = Field(default=False, alias="deleted")
    mealie_food_id: Optional[str] = Field(default=None, alias="mealieFoodId")
    mealie_unit_id: Optional[str] = Field(default=None, alias="mealieUnitId")
    food_badge_id: Optional[str] = Field(default=None, alias="foodBadgeId")
    unit_badge_id: Optional[str] = Field(default=None, alias="unitBadgeId")
    food_original_name: Optional[str] = Field(default=None, alias="foodOriginalName")
    unit_original_name: Optional[str] = Field(default=None, alias="unitOriginalName")
    food_new_id: Optional[str] = Field(default=None, alias="foodNewId")
    unit_new_id: Optional[str] = Field(default=None, alias="unitNewId")
    reference_id: Optional[str] = Field(default=None, alias="referenceId")
    model_config = ConfigDict(populate_by_name=True)

    @validator("name")
    def name_must_not_be_blank(cls, value: str) -> str:  # noqa: N805 - pydantic validator signature
        if not value.strip():
            raise ValueError("Ingredient name cannot be empty")
        return value


class IngredientSection(BaseModel):
    name: Optional[str] = None
    ingredients: List[Ingredient] = Field(default_factory=list)


class InstructionStep(BaseModel):
    id: Optional[str] = None
    order: int
    instruction: str
    timer_minutes: Optional[int] = None
    ingredient_ids: List[str] = Field(default_factory=list, alias="ingredientIds")
    ingredient_reference_ids: List[str] = Field(default_factory=list, alias="ingredientReferenceIds")

    @validator("instruction")
    def instruction_must_not_be_blank(cls, value: str) -> str:  # noqa: N805
        if not value.strip():
            raise ValueError("Instruction step cannot be empty")
        return value


class InstructionSection(BaseModel):
    name: Optional[str] = None
    steps: List[InstructionStep] = Field(default_factory=list)


class OrganizerReference(BaseModel):
    id: str
    name: str
    group_id: Optional[str] = Field(default=None, alias="groupId")
    slug: Optional[str] = None
    model_config = ConfigDict(populate_by_name=True)


class RecipeMetadata(BaseModel):
    source: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    cuisine: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    mealie_categories: List[OrganizerReference] = Field(default_factory=list)
    mealie_tags: List[OrganizerReference] = Field(default_factory=list)


class RecipeAsset(BaseModel):
    file_name: str
    data: Optional[str] = Field(default=None, exclude=True)
    title: Optional[str] = Field(default=None, exclude=True)
    description: Optional[str] = Field(default=None, exclude=True)
    data_path: Optional[str] = Field(default=None, alias="dataPath")


class Recipe(BaseModel):
    title: str
    description: Optional[str] = None
    recipe_servings: Optional[float] = Field(default=None, alias="recipeServings")
    recipe_yield_quantity: Optional[float] = Field(default=None, alias="recipeYieldQuantity")
    recipe_yield: Optional[str] = Field(default=None, alias="recipeYield")
    total_time: Optional[str] = Field(default=None, alias="totalTime")
    prep_time: Optional[str] = Field(default=None, alias="prepTime")
    perform_time: Optional[str] = Field(default=None, alias="performTime")
    ingredients: List[IngredientSection] = Field(default_factory=list)
    instructions: List[InstructionSection] = Field(default_factory=list)
    notes: Optional[str] = None
    image_path: Optional[str] = None
    image_url: Optional[HttpUrl] = None
    metadata: RecipeMetadata = Field(default_factory=RecipeMetadata)
    assets: List[RecipeAsset] = Field(default_factory=list)
    model_config = ConfigDict(populate_by_name=True)

    @validator("title")
    def title_must_not_be_blank(cls, value: str) -> str:  # noqa: N805
        if not value.strip():
            raise ValueError("Recipe title cannot be empty")
        return value
