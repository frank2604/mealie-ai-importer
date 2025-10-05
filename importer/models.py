"""Data models for representing recipe information during the import workflow."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, validator


class Ingredient(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    note: Optional[str] = None
    mealie_food_id: Optional[str] = Field(default=None, alias="mealieFoodId")
    mealie_unit_id: Optional[str] = Field(default=None, alias="mealieUnitId")

    @validator("name")
    def name_must_not_be_blank(cls, value: str) -> str:  # noqa: N805 - pydantic validator signature
        if not value.strip():
            raise ValueError("Ingredient name cannot be empty")
        return value

    class Config:
        allow_population_by_field_name = True


class IngredientSection(BaseModel):
    name: Optional[str] = None
    ingredients: List[Ingredient] = Field(default_factory=list)


class InstructionStep(BaseModel):
    order: int
    instruction: str
    timer_minutes: Optional[int] = None

    @validator("instruction")
    def instruction_must_not_be_blank(cls, value: str) -> str:  # noqa: N805
        if not value.strip():
            raise ValueError("Instruction step cannot be empty")
        return value


class InstructionSection(BaseModel):
    name: Optional[str] = None
    steps: List[InstructionStep] = Field(default_factory=list)


class RecipeMetadata(BaseModel):
    source: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    cuisine: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class RecipeAsset(BaseModel):
    file_name: str
    data: str
    title: Optional[str] = None
    description: Optional[str] = None


class Recipe(BaseModel):
    title: str
    description: Optional[str] = None
    portions: Optional[float] = None
    total_time_minutes: Optional[int] = None
    ingredients: List[IngredientSection] = Field(default_factory=list)
    instructions: List[InstructionSection] = Field(default_factory=list)
    notes: Optional[str] = None
    image_path: Optional[str] = None
    image_url: Optional[HttpUrl] = None
    metadata: RecipeMetadata = Field(default_factory=RecipeMetadata)
    assets: List[RecipeAsset] = Field(default_factory=list)

    @validator("title")
    def title_must_not_be_blank(cls, value: str) -> str:  # noqa: N805
        if not value.strip():
            raise ValueError("Recipe title cannot be empty")
        return value

    class Config:
        allow_population_by_field_name = True
