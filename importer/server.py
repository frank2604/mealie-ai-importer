"""FastAPI service exposing the Mealie importer pipeline."""
from __future__ import annotations

import base64
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .cli import _create_openai_client  # pylint: disable=protected-access
from .config import AppConfig, ConfigError, load_config
from .exceptions import UserAbort
from .modules import CachePaths, PipelineContext, PipelineRunner
from .modules.context import build_recipe_data_payload, normalize_recipe_payload
from .models import Recipe
from .modules.ai_analyser import AiAnalyserModule
from .modules.assign_metadata import AssignMetadataModule
from .modules.food_checker import FoodCheckerModule
from .modules.input import PdfInputModule
from .modules.refresh_caches import RefreshCachesModule
from .modules.unit_checker import UnitCheckerModule
from .modules.review import ApplyUserDecisionsModule
from .modules.create_foods import CreateFoodsModule
from .modules.add_food_ids import AddFoodIdsModule
from .modules.create_units import CreateUnitsModule
from .modules.add_unit_ids import AddUnitIdsModule
from .modules.create_recipe import CreateRecipeModule
from .services.run_workspace import PipelineRecorder, RunInfo, RunWorkspace
from .services.ingredients import IngredientService
from .prompt_store import load_prompts, save_prompts, get_prompt_defaults

logger = logging.getLogger(__name__)

UPLOAD_ROOT = Path("data/uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

DEFAULT_IMAGE_FILE = "02_RecipeImage.jpg"
DEFAULT_IMAGE_JSON = "03_RecipeImage.json"

RUN_STATE_LOCK = Lock()
ACTIVE_RUNS: Dict[str, "RunState"] = {}
PENDING_UPLOADS: Dict[str, "PendingUpload"] = {}

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"\[(?P<level>[A-Z]+)\] "
    r"(?P<logger>[^:]+): "
    r"(?P<message>.*)$"
)


def _apply_cors_headers(response: FileResponse, request: Request) -> FileResponse:
    """Ensure static file responses can be used in canvas operations."""
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    return response


class UploadResponse(BaseModel):
    uploadId: str
    fileName: str
    recipeName: str


class StartAnalysisResponse(BaseModel):
    runId: str
    status: str
    recipeName: str
    startedAt: str


class TransferStartResponse(BaseModel):
    runId: str
    status: str
    recipeName: str
    startedAt: str


class RunStatusResponse(BaseModel):
    runId: str
    status: str
    recipeName: str
    startedAt: str
    completedAt: Optional[str] = None
    error: Optional[str] = None


class LogEntryModel(BaseModel):
    id: str
    level: str
    message: str
    timestamp: str


class ImageUploadResponse(BaseModel):
    imageUrl: str


class LogResponse(BaseModel):
    runId: str
    entries: List[LogEntryModel]
    nextCursor: int


class ActiveRunResponse(BaseModel):
    runId: str
    status: str
    recipeName: str
    startedAt: str
    completedAt: Optional[str] = None


class CategoryOption(BaseModel):
    id: str
    name: Optional[str] = None
    groupId: Optional[str] = None
    slug: Optional[str] = None


class TagCategory(BaseModel):
    category: str
    tags: List[CategoryOption] = Field(default_factory=list)


class MatchInfo(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    strategy: Optional[str] = None


class CandidateOption(BaseModel):
    id: str
    name: Optional[str] = None
    pluralName: Optional[str] = None
    abbreviation: Optional[str] = None
    pluralAbbreviation: Optional[str] = None


class UnitSuggestion(BaseModel):
    name: Optional[str] = None
    pluralName: Optional[str] = None
    abbreviation: Optional[str] = None
    pluralAbbreviation: Optional[str] = None
    useAbbreviation: Optional[bool] = None


class FoodSuggestion(BaseModel):
    nameSingular: Optional[str] = None
    namePlural: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    categoryId: Optional[str] = None
    categoryName: Optional[str] = None


class FoodSelection(BaseModel):
    mealieFoodId: Optional[str] = None
    name: Optional[str] = None
    badgeId: Optional[str] = None
    status: Optional[str] = None
    newId: Optional[str] = None


class UnitSelection(BaseModel):
    mealieUnitId: Optional[str] = None
    name: Optional[str] = None
    badgeId: Optional[str] = None
    status: Optional[str] = None
    newId: Optional[str] = None


class ReviewIngredient(BaseModel):
    id: str
    sectionIndex: int
    ingredientIndex: int
    sectionName: Optional[str] = None
    amount: Optional[float] = None
    amountText: Optional[str] = None
    unit: Optional[str] = None
    unitOriginalName: Optional[str] = None
    name: str
    foodOriginalName: Optional[str] = None
    foodNewId: Optional[str] = None
    unitNewId: Optional[str] = None
    note: Optional[str] = None
    notes: Optional[str] = None
    foodStatus: str
    foodMatch: Optional[MatchInfo] = None
    foodSuggestion: Optional[FoodSuggestion] = None
    foodDecision: Dict[str, Any] = Field(default_factory=dict)
    unitStatus: str
    unitMatch: Optional[MatchInfo] = None
    unitSuggestion: Optional[UnitSuggestion] = None
    unitDecision: Dict[str, Any] = Field(default_factory=dict)
    foodSelection: Optional[FoodSelection] = None
    unitSelection: Optional[UnitSelection] = None


class ReviewInstruction(BaseModel):
    id: str
    sectionIndex: int
    stepIndex: int
    order: int
    text: str
    timerMinutes: Optional[int] = None
    ingredientIds: List[str] = Field(default_factory=list)
    ingredientReferenceIds: List[str] = Field(default_factory=list)


class ReviewAssets(BaseModel):
    pdfUrl: Optional[str] = None
    imageUrl: Optional[str] = None


class ReviewOptions(BaseModel):
    foods: List[CandidateOption] = Field(default_factory=list)
    units: List[CandidateOption] = Field(default_factory=list)
    foodCategories: List[CategoryOption] = Field(default_factory=list)


class ReviewSummary(BaseModel):
    title: str
    description: str
    recipeServings: Optional[float] = None
    recipeYieldQuantity: Optional[float] = None
    recipeYield: Optional[str] = None
    totalTime: Optional[str] = None
    prepTime: Optional[str] = None
    performTime: Optional[str] = None
    categoryId: Optional[str] = None
    tagIds: List[str] = Field(default_factory=list)
    availableCategories: List[CategoryOption] = Field(default_factory=list)
    availableTagCategories: List[TagCategory] = Field(default_factory=list)


class ReviewDataResponse(BaseModel):
    runId: str
    summary: ReviewSummary
    ingredients: List[ReviewIngredient] = Field(default_factory=list)
    instructions: List[ReviewInstruction] = Field(default_factory=list)
    assets: ReviewAssets
    options: ReviewOptions = Field(default_factory=ReviewOptions)


class ReviewSummaryUpdate(BaseModel):
    title: str
    description: str
    recipeServings: Optional[float] = None
    recipeYieldQuantity: Optional[float] = None
    recipeYield: Optional[str] = None
    totalTime: Optional[str] = None
    prepTime: Optional[str] = None
    performTime: Optional[str] = None
    categoryId: Optional[str] = None
    tagIds: List[str] = Field(default_factory=list)


class ReviewIngredientUpdate(BaseModel):
    id: str
    notes: Optional[str] = None
    foodDecision: Dict[str, Any] = Field(default_factory=dict)
    unitDecision: Dict[str, Any] = Field(default_factory=dict)
    foodSelection: Optional[FoodSelection] = None
    unitSelection: Optional[UnitSelection] = None


class ReviewInstructionUpdate(BaseModel):
    id: str
    order: Optional[int] = None
    text: str
    timerMinutes: Optional[int] = None
    ingredientIds: Optional[List[str]] = None


class ReviewUpdateRequest(BaseModel):
    summary: ReviewSummaryUpdate
    ingredients: List[ReviewIngredientUpdate] = Field(default_factory=list)
    instructions: List[ReviewInstructionUpdate] = Field(default_factory=list)


class PromptModuleConfig(BaseModel):
    free: str = ""
    system: str = ""


class PromptUpdateRequest(BaseModel):
    prompts: Dict[str, Dict[str, PromptModuleConfig]]


class PromptResponse(BaseModel):
    prompts: Dict[str, Dict[str, PromptModuleConfig]]
    defaults: Dict[str, Dict[str, PromptModuleConfig]]


class ResetWorkspaceResponse(BaseModel):
    status: str


@dataclass
class PendingUpload:
    upload_id: str
    file_path: Path
    original_name: str
    recipe_name: str
    created_at: str


@dataclass
class RunState:
    run_id: str
    upload_id: str
    recipe_name: str
    status: str
    started_at: str
    log_file: Path
    analysis_log_file: Path
    transfer_log_file: Path
    pipeline_dir: Path
    error: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class ReviewContext:
    run_info: RunInfo
    pipeline_dir: Path
    raw_path: Path
    recipe_path: Path
    foods_path: Optional[Path]
    units_path: Optional[Path]
    metadata_path: Optional[Path]
    pdf_path: Optional[Path]
    image_path: Optional[Path]


UI_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

app = FastAPI(title="Mealie Importer API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=UI_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now_utc() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _load_app_config() -> AppConfig:
    try:
        return load_config()
    except ConfigError as exc:
        logger.exception("Konfiguration konnte nicht geladen werden")
        raise HTTPException(status_code=500, detail=f"Konfiguration ungültig: {exc}") from exc


def _assert_no_running_job() -> None:
    with RUN_STATE_LOCK:
        busy = any(state.status in {"starting", "running", "transferring"} for state in ACTIVE_RUNS.values())
    if busy:
        raise HTTPException(status_code=409, detail="Ein anderer Importlauf ist noch aktiv.")


def _store_pending_upload(path: Path, original_name: str) -> PendingUpload:
    upload_id = uuid4().hex
    pending = PendingUpload(
        upload_id=upload_id,
        file_path=path,
        original_name=original_name,
        recipe_name=Path(original_name).stem or "import",
        created_at=_now_utc(),
    )
    with RUN_STATE_LOCK:
        PENDING_UPLOADS[upload_id] = pending
    return pending


def _pop_pending_upload(upload_id: str) -> PendingUpload:
    with RUN_STATE_LOCK:
        pending = PENDING_UPLOADS.pop(upload_id, None)
    if not pending:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden oder bereits gestartet.")
    return pending


def _register_run_state(pending: PendingUpload, run_info: RunInfo, pipeline_dir: Path) -> RunState:
    analysis_log = Path(
        run_info.analysis_log_file
        or run_info.log_file
        or pipeline_dir / f"{run_info.run_id}_analysis.log"
    )
    transfer_log = Path(
        run_info.transfer_log_file
        or pipeline_dir / f"{run_info.run_id}_transfer.log"
    )
    state = RunState(
        run_id=run_info.run_id,
        upload_id=pending.upload_id,
        recipe_name=pending.recipe_name,
        status="starting",
        started_at=run_info.started_at,
        log_file=analysis_log,
        analysis_log_file=analysis_log,
        transfer_log_file=transfer_log,
        pipeline_dir=pipeline_dir,
    )
    with RUN_STATE_LOCK:
        ACTIVE_RUNS[state.run_id] = state
    return state


def _update_run_state(
    run_id: str,
    *,
    status: Optional[str] = None,
    error: Optional[str] = None,
    completed_at: Optional[str] = None,
    clear_error: bool = False,
    recipe_name: Optional[str] = None,
) -> None:
    with RUN_STATE_LOCK:
        state = ACTIVE_RUNS.get(run_id)
        if not state:
            return
        if status:
            state.status = status
        if error is not None:
            state.error = error
        elif clear_error:
            state.error = None
        if completed_at:
            state.completed_at = completed_at
        if recipe_name:
            state.recipe_name = recipe_name


def _read_run_state(run_id: str) -> RunState:
    with RUN_STATE_LOCK:
        state = ACTIVE_RUNS.get(run_id)
    if state:
        return state
    config = _load_app_config()
    workspace = _build_workspace(config)
    run_info = workspace.load_run_info()
    if not run_info or run_info.run_id != run_id:
        raise HTTPException(status_code=404, detail="Importlauf nicht gefunden.")
    analysis_log = Path(
        run_info.analysis_log_file
        or run_info.log_file
        or workspace.pipeline_dir / f"{run_id}_analysis.log"
    )
    transfer_log = Path(
        run_info.transfer_log_file
        or workspace.pipeline_dir / f"{run_id}_transfer.log"
    )
    current_log = transfer_log if (run_info.status or "").lower() in {"transferring", "completed"} else analysis_log

    recreated = RunState(
        run_id=run_info.run_id,
        upload_id="resume",
        recipe_name=run_info.recipe_name,
        status=run_info.status or "review",
        started_at=run_info.started_at,
        log_file=current_log,
        analysis_log_file=analysis_log,
        transfer_log_file=transfer_log,
        pipeline_dir=workspace.pipeline_dir,
        error=getattr(run_info, "error", None),
        completed_at=run_info.completed_at,
    )
    with RUN_STATE_LOCK:
        ACTIVE_RUNS[run_id] = recreated
    return recreated


def _build_workspace(config: AppConfig) -> RunWorkspace:
    pipeline_dir = Path(config.processing.output_folder)
    cache_dir = Path(config.ingredients.cache_dir)
    data_root = pipeline_dir.parent if pipeline_dir.parent != pipeline_dir else Path("data")
    return RunWorkspace(
        pipeline_dir=pipeline_dir,
        cache_dir=cache_dir,
        log_dir=None,
        archive_dir=data_root / "archive",
    )


_STATUS_MAP = {
    "matched": "found",
    "missing": "new",
    "conflict": "error",
    "error": "error",
    "found": "found",
    "found_word": "found",
    "found_fuzzy": "found",
    "found_ai": "found",
    "manual": "manual",
    "none": "none",
}

_STRATEGY_MAP = {
    "exact": "word-match",
    "preassigned": "word-match",
    "word": "word-match",
    "word-match": "word-match",
    "fuzzy": "fuzzy",
    "similar": "fuzzy",
    "ai": "ai",
}


def _find_single_file(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if not matches:
        raise HTTPException(status_code=404, detail=f"Erwartete Datei '{pattern}' wurde im Pipeline-Ordner nicht gefunden.")
    return matches[-1]


def _find_optional_file(directory: Path, pattern: str) -> Optional[Path]:
    matches = sorted(directory.glob(pattern))
    for candidate in matches:
        if candidate.is_file():
            return candidate
    return None


def _load_json_file(path: Optional[Path]) -> Dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Die Datei {path.name} enthält ungültiges JSON: {exc}") from exc


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _resume_pipeline_recorder(directory: Path) -> PipelineRecorder:
    recorder = PipelineRecorder(directory)
    max_index = 0
    for entry in directory.iterdir():
        match = re.match(r"^(\d{2})_", entry.name)
        if match:
            max_index = max(max_index, int(match.group(1)))
    recorder._counter = max_index  # type: ignore[attr-defined]
    return recorder


def _write_recipe_image_json(pipeline_dir: Path, file_name: str, data: bytes, mime_type: str) -> None:
    data_url = f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"
    payload = {"fileName": file_name, "dataUrl": data_url}
    json_path = _find_optional_file(pipeline_dir, "*RecipeImage.json")
    if not json_path:
        json_path = pipeline_dir / DEFAULT_IMAGE_JSON
    _write_json_file(json_path, payload)


def _load_candidate_options(path: Path, key: str) -> List[CandidateOption]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = payload.get(key)
    if not isinstance(items, list):
        return []
    options: List[CandidateOption] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        options.append(
            CandidateOption(
                id=str(item.get("id")),
                name=item.get("name"),
                pluralName=item.get("pluralName"),
                abbreviation=item.get("abbreviation"),
                pluralAbbreviation=item.get("pluralAbbreviation"),
            )
        )
    return options


def _load_food_categories(path: Path) -> List[CategoryOption]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = payload.get("categories")
    if not isinstance(items, list):
        return []
    categories: List[CategoryOption] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        categories.append(
            CategoryOption(
                id=str(item.get("id")),
                name=item.get("name"),
                groupId=item.get("groupId"),
                slug=item.get("slug"),
            )
        )
    return categories


def _resolve_review_context(config: AppConfig, run_id: str) -> ReviewContext:
    workspace = _build_workspace(config)
    run_info = workspace.load_run_info()
    if run_info is None or run_info.run_id != run_id:
        raise HTTPException(status_code=404, detail="Importlauf nicht gefunden oder bereits archiviert.")

    pipeline_dir = workspace.pipeline_dir
    raw_path = _find_single_file(pipeline_dir, "*RecipeRawData.json")
    try:
        recipe_path = _find_single_file(pipeline_dir, "*RecipeData.json")
    except HTTPException:
        try:
            recipe_path = _find_single_file(pipeline_dir, "*Recipe.json")
        except HTTPException:
            try:
                recipe_path = _find_single_file(pipeline_dir, "*RecipeRawDataEnriched.json")
            except HTTPException:
                recipe_path = raw_path

    foods_path = _find_optional_file(pipeline_dir, "*FoodsReview.json") or pipeline_dir / "05_FoodsReview.json"
    units_path = _find_optional_file(pipeline_dir, "*UnitsReview.json") or pipeline_dir / "06_UnitsReview.json"
    metadata_path = _find_optional_file(pipeline_dir, "*MetadataReview.json") or pipeline_dir / "07_MetadataReview.json"
    pdf_path = _find_optional_file(pipeline_dir, "*.pdf")
    image_path = _find_optional_file(pipeline_dir, "*RecipeImage.*")

    return ReviewContext(
        run_info=run_info,
        pipeline_dir=pipeline_dir,
        raw_path=raw_path,
        recipe_path=recipe_path,
        foods_path=foods_path,
        units_path=units_path,
        metadata_path=metadata_path,
        pdf_path=pdf_path,
        image_path=image_path,
    )


def _current_recipe_title(run_id: str) -> Optional[str]:
    """Lese den aktuellen Rezepttitel aus der RecipeData.json, falls vorhanden."""
    try:
        config = _load_app_config()
        review_context = _resolve_review_context(config, run_id)
        recipe_payload = _load_json_file(review_context.recipe_path)
        title = recipe_payload.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    except Exception:  # pragma: no cover - defensive fallback
        return None
    return None



def _prepare_transfer_context(config: AppConfig, run_state: RunState) -> PipelineContext:
    review_context = _resolve_review_context(config, run_state.run_id)
    source_pdf = (
        review_context.pdf_path
        or (Path(review_context.run_info.source_pdf) if review_context.run_info.source_pdf else None)
        or (review_context.pipeline_dir / f"{review_context.run_info.recipe_name}.pdf")
    )
    if not source_pdf.exists():
        source_pdf.parent.mkdir(parents=True, exist_ok=True)
        try:
            source_pdf.touch(exist_ok=True)
        except OSError:
            pass

    recorder = _resume_pipeline_recorder(review_context.pipeline_dir)
    cache_paths = CachePaths(Path(config.ingredients.cache_dir))
    context = PipelineContext(
        source_pdf=source_pdf,
        output_dir=review_context.pipeline_dir,
        config=config,
        cache_paths=cache_paths,
        run_id=run_state.run_id,
        pipeline_recorder=recorder,
        log_file=run_state.log_file,
    )
    context.recipe_data_path = review_context.recipe_path
    context.recipe_output_path = review_context.recipe_path
    context.food_review_path = review_context.foods_path
    context.unit_review_path = review_context.units_path
    context.metadata_review_path = review_context.metadata_path

    recipe = context.ensure_recipe()
    for ref in context.iter_ingredients():
        if ref.ingredient.mealie_food_id:
            context.food_matches[ref.key] = ref.ingredient.mealie_food_id
        if ref.ingredient.mealie_unit_id:
            context.unit_matches[ref.key] = ref.ingredient.mealie_unit_id
    context.recipe = recipe
    return context


def _map_status(value: Optional[str]) -> str:
    if not value:
        return "none"
    normalized = value.lower()
    if normalized in _STATUS_MAP:
        return _STATUS_MAP[normalized]
    return normalized


def _map_strategy(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return _STRATEGY_MAP.get(value.lower(), value.lower())


def _format_quantity(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if int(value) == value:
            return str(int(value))
        return str(value)
    return str(value)


def _build_review_payload(run_id: str, config: AppConfig) -> ReviewDataResponse:
    context = _resolve_review_context(config, run_id)

    recipe_data = normalize_recipe_payload(_load_json_file(context.recipe_path))
    foods_review = _load_json_file(context.foods_path)
    units_review = _load_json_file(context.units_path)
    metadata_review = _load_json_file(context.metadata_path)

    recipe_sections = recipe_data.get("ingredients") or []
    recipe_ingredient_map: Dict[str, Dict[str, Any]] = {}
    recipe_id_to_key: Dict[str, str] = {}
    for section_index, section in enumerate(recipe_sections):
        items = section.get("ingredients") or []
        for ingredient_index, ingredient in enumerate(items):
            key = f"{section_index}:{ingredient_index}"
            recipe_ingredient_map[key] = ingredient
            rec_id = ingredient.get("id")
            if isinstance(rec_id, str) and rec_id:
                recipe_id_to_key[rec_id] = key

    foods_map = {
        str(item.get("key")): item for item in foods_review.get("ingredients", []) if isinstance(item, dict)
    }
    units_map = {
        str(item.get("key")): item for item in units_review.get("units", []) if isinstance(item, dict)
    }

    ingredients_payload: List[ReviewIngredient] = []
    ingredients_sections = recipe_data.get("ingredients") or []

    for section_index, section in enumerate(ingredients_sections):
        section_name = section.get("name")
        for ingredient_index, ingredient in enumerate(section.get("ingredients") or []):
            key = f"{section_index}:{ingredient_index}"
            food_entry = foods_map.get(key, {})
            unit_entry = units_map.get(key, {})
            recipe_entry = recipe_ingredient_map.get(key, {})

            food_status = _map_status(recipe_entry.get("foodBadgeId"))
            unit_status = _map_status(recipe_entry.get("unitBadgeId"))

            recipe_food_id = recipe_entry.get("mealieFoodId")
            recipe_unit_id = recipe_entry.get("mealieUnitId")

            food_match_obj = (
                MatchInfo(
                    id=recipe_food_id,
                    name=recipe_entry.get("name"),
                    strategy=_map_strategy(recipe_entry.get("foodBadgeId")),
                )
                if recipe_food_id
                else None
            )

            unit_match_obj = (
                MatchInfo(
                    id=recipe_unit_id,
                    name=recipe_entry.get("unit"),
                    strategy=_map_strategy(recipe_entry.get("unitBadgeId")),
                )
                if recipe_unit_id
                else None
            )

            food_decision = dict(food_entry.get("userDecision") or {})
            unit_decision = dict(unit_entry.get("userDecision") or {})
            food_selection = FoodSelection(
                mealieFoodId=recipe_food_id,
                name=recipe_entry.get("name"),
                badgeId=recipe_entry.get("foodBadgeId"),
                status=food_status,
                newId=recipe_entry.get("foodNewId"),
            )
            unit_selection = UnitSelection(
                mealieUnitId=recipe_unit_id,
                name=recipe_entry.get("unit"),
                badgeId=recipe_entry.get("unitBadgeId"),
                status=unit_status,
                newId=recipe_entry.get("unitNewId"),
            )

            notes_value = None
            if "notes" in food_decision:
                notes_value = food_decision.get("notes")
            elif "notes" in unit_decision:
                notes_value = unit_decision.get("notes")

            if notes_value is None or notes_value == "":
                source_note = ingredient.get("note")
                notes_value = str(source_note) if source_note else ""

            ingredient_payload = ReviewIngredient(
                id=key,
                sectionIndex=section_index,
                ingredientIndex=ingredient_index,
                sectionName=section_name,
                amount=ingredient.get("quantity"),
                amountText=_format_quantity(ingredient.get("quantity")),
                unit=ingredient.get("unit"),
                unitOriginalName=ingredient.get("unitOriginalName"),
                name=str(ingredient.get("name") or ""),
                foodOriginalName=ingredient.get("foodOriginalName"),
                foodNewId=food_entry.get("newId"),
                unitNewId=unit_entry.get("newId"),
                note=ingredient.get("note"),
                notes=notes_value or "",
                foodStatus=food_status,
                foodMatch=food_match_obj,
                foodSuggestion=FoodSuggestion(
                    nameSingular=(food_entry.get("suggestion") or {}).get("nameSingular"),
                    namePlural=(food_entry.get("suggestion") or {}).get("namePlural"),
                    aliases=list((food_entry.get("suggestion") or {}).get("aliases") or []),
                    categoryId=(food_entry.get("suggestion") or {}).get("categoryId"),
                    categoryName=(food_entry.get("suggestion") or {}).get("categoryName"),
                )
                if food_entry.get("suggestion")
                else None,
                foodDecision=food_decision,
                unitStatus=unit_status,
                unitMatch=unit_match_obj,
                unitSuggestion=UnitSuggestion(
                    name=(unit_entry.get("suggestion") or {}).get("name"),
                    pluralName=(unit_entry.get("suggestion") or {}).get("pluralName"),
                    abbreviation=(unit_entry.get("suggestion") or {}).get("abbreviation"),
                    pluralAbbreviation=(unit_entry.get("suggestion") or {}).get("pluralAbbreviation"),
                    useAbbreviation=(unit_entry.get("suggestion") or {}).get("useAbbreviation"),
                )
                if unit_entry.get("suggestion")
                else None,
                unitDecision=unit_decision,
                foodSelection=food_selection,
                unitSelection=unit_selection,
            )
            ingredients_payload.append(ingredient_payload)

    instructions_payload: List[ReviewInstruction] = []
    instructions_sections = recipe_data.get("instructions") or []
    for section_index, section in enumerate(instructions_sections):
        for step_index, step in enumerate(section.get("steps") or []):
            raw_ids = step.get("ingredientIds") or []
            mapped_ids = []
            for ing_id in raw_ids:
                if isinstance(ing_id, str) and ing_id:
                    mapped_ids.append(recipe_id_to_key.get(ing_id, ing_id))
            instruction_payload = ReviewInstruction(
                id=str(step.get("id") or f"{section_index}:{step_index}"),
                sectionIndex=section_index,
                stepIndex=step_index,
                order=int(step.get("order") or step_index + 1),
                text=str(step.get("instruction") or ""),
                timerMinutes=step.get("timer_minutes"),
                ingredientIds=mapped_ids,
                ingredientReferenceIds=list(step.get("ingredientReferenceIds") or []),
            )
            instructions_payload.append(instruction_payload)

    metadata_user_decision = metadata_review.get("userDecision", {})
    servings_value = recipe_data.get("recipeServings")
    if servings_value is None:
        servings_value = recipe_data.get("portions")
    if not isinstance(servings_value, (int, float)):
        candidate = metadata_user_decision.get("recipeServings") or metadata_user_decision.get("portions")
        servings_value = candidate if isinstance(candidate, (int, float)) else None

    total_time_value = recipe_data.get("totalTime")
    if total_time_value is None:
        legacy_minutes = recipe_data.get("total_time_minutes")
        if isinstance(legacy_minutes, (int, float)):
            total_time_value = f"{int(legacy_minutes)} Minuten"
    if not isinstance(total_time_value, str):
        candidate = metadata_user_decision.get("totalTime") or metadata_user_decision.get("totalTimeMinutes")
        if isinstance(candidate, str):
            total_time_value = candidate
        elif isinstance(candidate, (int, float)):
            total_time_value = f"{int(candidate)} Minuten"
        else:
            total_time_value = None

    summary = ReviewSummary(
        title=str(recipe_data.get("title") or context.run_info.recipe_name),
        description=str(recipe_data.get("description") or ""),
        recipeServings=servings_value,
        recipeYieldQuantity=recipe_data.get("recipeYieldQuantity"),
        recipeYield=recipe_data.get("recipeYield"),
        totalTime=total_time_value,
        prepTime=recipe_data.get("prepTime"),
        performTime=recipe_data.get("performTime"),
        categoryId=metadata_user_decision.get("categoryId"),
        tagIds=list(metadata_user_decision.get("tagIds") or []),
        availableCategories=[
            CategoryOption(
                id=str(item.get("id")),
                name=item.get("name"),
                groupId=item.get("groupId"),
                slug=item.get("slug"),
            )
            for item in metadata_review.get("available", {}).get("categories", [])
            if item.get("id")
        ],
        availableTagCategories=[
            TagCategory(
                category=block.get("category") or "",
                tags=[
                    CategoryOption(
                        id=str(tag.get("id")),
                        name=tag.get("name"),
                        groupId=tag.get("groupId"),
                        slug=tag.get("slug"),
                    )
                    for tag in block.get("tags") or []
                    if tag.get("id")
                ],
            )
            for block in metadata_review.get("available", {}).get("tagCategories", [])
            if block.get("category")
        ],
    )

    assets = ReviewAssets(
        pdfUrl=f"/api/imports/{run_id}/pdf" if context.pdf_path else None,
        imageUrl=f"/api/imports/{run_id}/image" if context.image_path else None,
    )

    cache_root = Path(config.ingredients.cache_dir)
    foods_options = _load_candidate_options(cache_root / "MealieFoodsCache.json", "foods")
    units_options = _load_candidate_options(cache_root / "MealieUnitsCache.json", "units")
    food_categories = _load_food_categories(cache_root / "MealieFoodCategoriesCache.json")

    return ReviewDataResponse(
        runId=run_id,
        summary=summary,
        ingredients=ingredients_payload,
        instructions=instructions_payload,
        assets=assets,
        options=ReviewOptions(foods=foods_options, units=units_options, foodCategories=food_categories),
    )


def _apply_review_update(run_id: str, config: AppConfig, payload: ReviewUpdateRequest) -> None:
    context = _resolve_review_context(config, run_id)
    workspace = _build_workspace(config)

    raw_snapshot = normalize_recipe_payload(_load_json_file(context.raw_path))
    recipe_data = normalize_recipe_payload(_load_json_file(context.recipe_path))
    foods_review = _load_json_file(context.foods_path)
    units_review = _load_json_file(context.units_path)
    metadata_review = _load_json_file(context.metadata_path)

    # Ensure instructions structure exists
    if "instructions" not in recipe_data or not isinstance(recipe_data["instructions"], list):
        recipe_data["instructions"] = raw_snapshot.get("instructions", [])

    # Update summary fields
    recipe_data["title"] = payload.summary.title
    recipe_data["description"] = payload.summary.description
    if payload.summary.recipeServings is not None:
        recipe_data["recipeServings"] = payload.summary.recipeServings
    if payload.summary.recipeYieldQuantity is not None:
        recipe_data["recipeYieldQuantity"] = payload.summary.recipeYieldQuantity
    if payload.summary.recipeYield is not None:
        recipe_data["recipeYield"] = payload.summary.recipeYield
    if payload.summary.totalTime is not None:
        recipe_data["totalTime"] = payload.summary.totalTime
    if payload.summary.prepTime is not None:
        recipe_data["prepTime"] = payload.summary.prepTime
    if payload.summary.performTime is not None:
        recipe_data["performTime"] = payload.summary.performTime
    if payload.summary.title:
        context.run_info.recipe_name = payload.summary.title

    # Update metadata review selections
    user_decision = metadata_review.setdefault("userDecision", {})
    if payload.summary.recipeServings is not None:
        user_decision["recipeServings"] = payload.summary.recipeServings
    if payload.summary.totalTime is not None:
        user_decision["totalTime"] = payload.summary.totalTime
    user_decision["categoryId"] = payload.summary.categoryId
    user_decision["tagIds"] = payload.summary.tagIds

    current_state = metadata_review.setdefault("current", {})
    if payload.summary.recipeServings is not None:
        current_state["recipeServings"] = payload.summary.recipeServings
    if payload.summary.totalTime is not None:
        current_state["totalTime"] = payload.summary.totalTime
    if payload.summary.categoryId is not None:
        current_state["category"] = payload.summary.categoryId
    if payload.summary.tagIds is not None:
        current_state["tagIds"] = payload.summary.tagIds

    # Update ingredient decisions
    foods_entries = foods_review.setdefault("ingredients", [])
    foods_map = {
        str(entry.get("key")): entry for entry in foods_entries if isinstance(entry, dict)
    }
    units_entries = units_review.setdefault("units", [])
    units_map = {
        str(entry.get("key")): entry for entry in units_entries if isinstance(entry, dict)
    }

    def _locate_ingredient(target: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
        try:
            section_index_str, ingredient_index_str = key.split(":", 1)
            section_index = int(section_index_str)
            ingredient_index = int(ingredient_index_str)
        except (ValueError, AttributeError):
            return None
        sections = target.setdefault("ingredients", [])
        if not (0 <= section_index < len(sections)):
            return None
        section = sections[section_index]
        items = section.setdefault("ingredients", [])
        if not (0 <= ingredient_index < len(items)):
            return None
        return items[ingredient_index]

    def _set_ingredient_note(target: Dict[str, Any], key: str, value: Optional[str]) -> None:
        entry = _locate_ingredient(target, key)
        if entry is None:
            return
        entry["note"] = value or None

    for ingredient_update in payload.ingredients:
        key = ingredient_update.id
        notes_value = ingredient_update.notes if ingredient_update.notes is not None else ""

        if key in foods_map:
            decision = dict(ingredient_update.foodDecision or {})
            if notes_value is not None:
                decision["notes"] = notes_value
            foods_map[key]["userDecision"] = decision

        if key in units_map:
            decision = dict(ingredient_update.unitDecision or {})
            if notes_value is not None:
                decision["notes"] = notes_value
            units_map[key]["userDecision"] = decision

        _set_ingredient_note(recipe_data, key, notes_value)
        entry = _locate_ingredient(recipe_data, key)
        if entry and ingredient_update.foodSelection:
            selection = ingredient_update.foodSelection
            entry["mealieFoodId"] = selection.mealieFoodId
            entry["foodNewId"] = selection.newId
            if selection.name is not None:
                entry["name"] = selection.name
            entry["foodBadgeId"] = selection.badgeId
        if entry and ingredient_update.unitSelection:
            selection = ingredient_update.unitSelection
            entry["mealieUnitId"] = selection.mealieUnitId
            entry["unitNewId"] = selection.newId
            if selection.name is not None:
                entry["unit"] = selection.name
            entry["unitBadgeId"] = selection.badgeId

    # Update instructions
    instructions_sections = recipe_data.setdefault("instructions", [])

    # Map UI ingredient keys back to recipe ingredient ids if present
    key_to_recipe_id: Dict[str, str] = {}
    for section_index, section in enumerate(recipe_data.get("ingredients") or []):
        for ingredient_index, ingredient in enumerate(section.get("ingredients") or []):
            key = f"{section_index}:{ingredient_index}"
            rec_id = ingredient.get("id") or key
            key_to_recipe_id[key] = rec_id

    def _locate_instruction_by_id(target: Dict[str, Any], instr_id: str) -> Optional[Dict[str, Any]]:
        for section in target.get("instructions") or []:
            for step in section.get("steps") or []:
                if str(step.get("id")) == instr_id:
                    return step
        # fallback by index pattern
        try:
            section_index_str, step_index_str = instr_id.split(":", 1)
            section_index = int(section_index_str)
            step_index = int(step_index_str)
        except (ValueError, AttributeError):
            return None
        if not (0 <= section_index < len(instructions_sections)):
            return None
        steps = instructions_sections[section_index].setdefault("steps", [])
        if not (0 <= step_index < len(steps)):
            return None
        return steps[step_index]

    for instruction_update in payload.instructions:
        step = _locate_instruction_by_id(recipe_data, instruction_update.id)
        if step is None:
            continue
        step["instruction"] = instruction_update.text
        if instruction_update.order is not None:
            step["order"] = instruction_update.order
        if instruction_update.timerMinutes is not None or "timer_minutes" in step:
            step["timer_minutes"] = instruction_update.timerMinutes
        if instruction_update.ingredientIds is not None:
            mapped = []
            for ing_id in instruction_update.ingredientIds:
                mapped_id = key_to_recipe_id.get(ing_id, ing_id)
                mapped.append(mapped_id)
            step["ingredientIds"] = mapped

    # Persist files
    recipe_model = Recipe.parse_obj(recipe_data)
    _write_json_file(context.recipe_path, build_recipe_data_payload(recipe_model))
    if context.foods_path:
        _write_json_file(context.foods_path, foods_review)
    if context.units_path:
        _write_json_file(context.units_path, units_review)
    if context.metadata_path:
        _write_json_file(context.metadata_path, metadata_review)
    workspace.save_run_info(context.run_info)
    _update_run_state(run_id, recipe_name=context.run_info.recipe_name)


def _run_analysis(run_state: RunState, pending: PendingUpload, config: AppConfig, workspace: RunWorkspace, run_info: RunInfo) -> None:
    logger.info("Starte Analyse für Lauf %s (%s)", run_state.run_id, run_state.recipe_name)
    try:
        llm_client = _create_openai_client(config.llm)
    except ValueError as exc:
        logger.error("LLM-Konfiguration fehlerhaft: %s", exc)
        run_info.mark_completed(status="failed")
        workspace.save_run_info(run_info)
        _update_run_state(run_state.run_id, status="failed", error=str(exc), completed_at=run_info.completed_at or _now_utc())
        return

    ingredient_service: Optional[IngredientService] = None
    if config.mealie.base_url and config.mealie.token:
        try:
            ingredient_service = IngredientService(
                base_url=config.mealie.base_url,
                token=config.mealie.token,
                config=config.ingredients,
                llm_client=llm_client,
                verify=config.mealie.verify_option(),
                auto_seed=False,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("IngredientService konnte nicht initialisiert werden: %s", exc)
            run_info.mark_completed(status="failed")
            workspace.save_run_info(run_info)
            _update_run_state(run_state.run_id, status="failed", error=str(exc), completed_at=run_info.completed_at or _now_utc())
            return
    else:
        logger.info("Keine Mealie-Verbindungsdaten vorhanden – wir überspringen API-gestützte Schritte.")

    log_file = Path(run_info.log_file) if run_info.log_file else run_state.log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    try:
        _update_run_state(run_state.run_id, status="running")

        recorder = PipelineRecorder(workspace.pipeline_dir)
        recorder.copy_file(pending.file_path, label=run_state.recipe_name)

        cache_paths = CachePaths(Path(config.ingredients.cache_dir))
        context = PipelineContext(
            source_pdf=pending.file_path,
            output_dir=workspace.pipeline_dir,
            config=config,
            cache_paths=cache_paths,
            pipeline_recorder=recorder,
            run_id=run_state.run_id,
            log_file=log_file,
        )
        context.requires_user_review = True

        modules = [
            RefreshCachesModule(ingredient_service),
            PdfInputModule(),
            AiAnalyserModule(
                llm_client=llm_client,
                llm_config=config.llm,
                image_output_dir=workspace.pipeline_dir,
            ),
            FoodCheckerModule(ingredient_service, llm_client=llm_client),
            UnitCheckerModule(ingredient_service, llm_client=llm_client),
            AssignMetadataModule(ingredient_service, llm_client=llm_client),
        ]

        runner = PipelineRunner(modules)
        try:
            runner.run(context)
        except UserAbort as exc:
            logger.warning("Pipeline vom Benutzer abgebrochen: %s", exc)
            run_info.mark_completed(status="aborted")
            workspace.save_run_info(run_info)
            _update_run_state(run_state.run_id, status="aborted", completed_at=_now_utc(), error=str(exc))
            return

        run_info.mark_completed(status="review")
        workspace.save_run_info(run_info)
        _update_run_state(run_state.run_id, status="review", completed_at=run_info.completed_at or _now_utc())
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Analyse fehlgeschlagen: %s", exc)
        run_info.mark_completed(status="failed")
        workspace.save_run_info(run_info)
        _update_run_state(run_state.run_id, status="failed", error=str(exc), completed_at=run_info.completed_at or _now_utc())
    finally:
        if ingredient_service:
            ingredient_service.close()
        root_logger.removeHandler(file_handler)
        file_handler.close()
        try:
            pending.file_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Hochgeladene Datei konnte nicht gelöscht werden: %s", pending.file_path)


def _run_transfer(run_state: RunState, config: AppConfig, workspace: RunWorkspace, run_info: RunInfo) -> None:
    logger.info("Starte Übertragung für Lauf %s (%s)", run_state.run_id, run_state.recipe_name)
    ingredient_service: Optional[IngredientService] = None
    file_handler: Optional[logging.Handler] = None
    root_logger = logging.getLogger()
    try:
        if not (config.mealie.base_url and config.mealie.token):
            raise RuntimeError("Mealie-Zugangsdaten fehlen – Übertragung nicht möglich.")

        ingredient_service = IngredientService(
            base_url=config.mealie.base_url,
            token=config.mealie.token,
            config=config.ingredients,
            llm_client=None,
            verify=config.mealie.verify_option(),
            auto_seed=False,
        )

        if run_state.log_file:
            file_handler = logging.FileHandler(run_state.log_file, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
            root_logger.addHandler(file_handler)

        context = _prepare_transfer_context(config, run_state)
        context.requires_user_review = False

        modules = [
            ApplyUserDecisionsModule(),
            CreateFoodsModule(ingredient_service),
            AddFoodIdsModule(),
            CreateUnitsModule(ingredient_service),
            AddUnitIdsModule(),
            CreateRecipeModule(
                config=config,
                ingredient_service=ingredient_service,
                dry_run=False,
                on_duplicate=None,
            ),
        ]

        runner = PipelineRunner(modules)
        runner.run(context)

        run_info.mark_completed(status="completed")
        workspace.save_run_info(run_info)
        _update_run_state(run_state.run_id, status="completed", completed_at=run_info.completed_at or _now_utc(), clear_error=True)
        logger.info("Übertragung erfolgreich abgeschlossen")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Übertragung fehlgeschlagen: %s", exc)
        run_info.status = "review"
        workspace.save_run_info(run_info)
        _update_run_state(run_state.run_id, status="review", error=str(exc))
    finally:
        if ingredient_service:
            ingredient_service.close()
        if file_handler:
            root_logger.removeHandler(file_handler)
            file_handler.close()


def _parse_log_entries(log_file: Path, run_state: RunState, after: int) -> LogResponse:
    if not log_file.exists():
        return LogResponse(runId=run_state.run_id, entries=[], nextCursor=after)

    entries: List[LogEntryModel] = []
    total = 0
    with log_file.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            total = index + 1
            if index < after:
                continue
            text = line.strip()
            if not text:
                continue
            match = LOG_PATTERN.match(text)
            if match:
                raw_level = match.group("level")
                message = match.group("message")
                timestamp = match.group("timestamp") + "Z"
            else:
                raw_level = "INFO"
                message = text
                timestamp = run_state.started_at
            level = _normalize_level(raw_level)
            entries.append(
                LogEntryModel(
                    id=f"{run_state.run_id}-{index}",
                    level=level,
                    message=message,
                    timestamp=timestamp,
                )
            )
    return LogResponse(runId=run_state.run_id, entries=entries, nextCursor=total)


def _normalize_level(level_name: str) -> str:
    normalized = level_name.upper()
    if normalized in {"INFO", "WARN", "ERROR"}:
        return "WARN" if normalized == "WARN" else normalized
    if normalized == "WARNING":
        return "WARN"
    if normalized in {"CRITICAL", "EXCEPTION"}:
        return "ERROR"
    if normalized == "DEBUG":
        return "INFO"
    return "INFO"


@app.post("/api/imports/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    if file.content_type not in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Es werden nur PDF-Dateien unterstützt.")

    file_suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    pending_path = UPLOAD_ROOT / f"{uuid4().hex}{file_suffix}"

    try:
        with pending_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    finally:
        await file.close()

    pending = _store_pending_upload(pending_path, file.filename or pending_path.name)
    logger.info("PDF %s unter %s gespeichert (Upload-ID %s)", pending.original_name, pending.file_path, pending.upload_id)
    return UploadResponse(uploadId=pending.upload_id, fileName=pending.original_name, recipeName=pending.recipe_name)


@app.post("/api/imports/{upload_id}/start", response_model=StartAnalysisResponse)
async def start_analysis(upload_id: str, background_tasks: BackgroundTasks) -> StartAnalysisResponse:
    pending = _pop_pending_upload(upload_id)
    _assert_no_running_job()
    config = _load_app_config()

    workspace = _build_workspace(config)
    run_info = workspace.start_run(recipe_name=pending.recipe_name, source_pdf=pending.file_path)
    run_state = _register_run_state(pending, run_info, workspace.pipeline_dir)

    background_tasks.add_task(_run_analysis, run_state, pending, config, workspace, run_info)

    return StartAnalysisResponse(
        runId=run_state.run_id,
        status=run_state.status,
        recipeName=run_state.recipe_name,
        startedAt=run_state.started_at,
    )


@app.post("/api/imports/{run_id}/transfer", response_model=TransferStartResponse)
async def start_transfer(run_id: str, background_tasks: BackgroundTasks) -> TransferStartResponse:
    state = _read_run_state(run_id)
    if state.status not in {"review"}:
        raise HTTPException(status_code=409, detail="Die Analyse muss abgeschlossen sein, bevor die Übertragung starten kann.")
    _assert_no_running_job()
    config = _load_app_config()
    workspace = _build_workspace(config)
    run_info = workspace.load_run_info()
    if not run_info or run_info.run_id != run_id:
        raise HTTPException(status_code=404, detail="Importlauf nicht gefunden oder bereits archiviert.")

    try:
        state.transfer_log_file.unlink()
    except FileNotFoundError:
        pass
    state.log_file = state.transfer_log_file

    _update_run_state(run_id, status="transferring", clear_error=True)
    run_info.status = "transferring"
    workspace.save_run_info(run_info)
    background_tasks.add_task(_run_transfer, state, config, workspace, run_info)

    return TransferStartResponse(
        runId=run_id,
        status="transferring",
        recipeName=run_info.recipe_name,
        startedAt=run_info.started_at,
    )


@app.get("/api/imports/active", response_model=ActiveRunResponse)
async def get_active_run() -> ActiveRunResponse:
    config = _load_app_config()
    workspace = _build_workspace(config)
    run_info = workspace.load_run_info()
    if not run_info:
        raise HTTPException(status_code=404, detail="Es ist kein aktiver Importlauf vorhanden.")
    return ActiveRunResponse(
        runId=run_info.run_id,
        status=run_info.status,
        recipeName=run_info.recipe_name,
        startedAt=run_info.started_at,
        completedAt=run_info.completed_at,
    )


@app.delete("/api/imports/workspace", response_model=ResetWorkspaceResponse)
async def reset_workspace_endpoint() -> ResetWorkspaceResponse:
    config = _load_app_config()
    workspace = _build_workspace(config)
    workspace.reset_current_run()
    pending_files: List[Path] = []
    with RUN_STATE_LOCK:
        for pending in PENDING_UPLOADS.values():
            pending_files.append(pending.file_path)
        PENDING_UPLOADS.clear()
        ACTIVE_RUNS.clear()
    for file_path in pending_files:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Konnte Upload-Datei nicht löschen: %s", file_path)
    return ResetWorkspaceResponse(status="ok")


@app.get("/api/imports/{run_id}/review", response_model=ReviewDataResponse)
async def get_review_data(run_id: str) -> ReviewDataResponse:
    config = _load_app_config()
    return _build_review_payload(run_id, config)


@app.put("/api/imports/{run_id}/review", response_model=ReviewDataResponse)
async def update_review_data(run_id: str, update: ReviewUpdateRequest) -> ReviewDataResponse:
    config = _load_app_config()
    _apply_review_update(run_id, config, update)
    return _build_review_payload(run_id, config)


@app.get("/api/prompts", response_model=PromptResponse)
async def get_prompts() -> PromptResponse:
    prompts = load_prompts()
    defaults = get_prompt_defaults()
    return PromptResponse(prompts=prompts, defaults=defaults)


@app.put("/api/prompts", response_model=PromptResponse)
async def update_prompts(payload: PromptUpdateRequest) -> PromptResponse:
    existing = load_prompts()
    for locale, modules in payload.prompts.items():
        locale_entry = existing.setdefault(locale, {})
        for module, config in modules.items():
            locale_entry[module] = {"free": config.free, "system": config.system}
    save_prompts(existing)
    return PromptResponse(prompts=existing, defaults=get_prompt_defaults())


@app.get("/api/imports/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str) -> RunStatusResponse:
    state = _read_run_state(run_id)
    recipe_title = _current_recipe_title(run_id) or state.recipe_name
    return RunStatusResponse(
        runId=state.run_id,
        status=state.status,
        recipeName=recipe_title,
        startedAt=state.started_at,
        completedAt=state.completed_at,
        error=state.error,
    )


@app.post("/api/imports/{run_id}/archive", response_model=ResetWorkspaceResponse)
async def archive_run(run_id: str) -> ResetWorkspaceResponse:
    config = _load_app_config()
    workspace = _build_workspace(config)
    run_info = workspace.load_run_info()
    if not run_info or run_info.run_id != run_id:
        raise HTTPException(status_code=404, detail="Importlauf nicht gefunden oder bereits archiviert.")
    workspace.archive_current_run(run_info)
    with RUN_STATE_LOCK:
        ACTIVE_RUNS.pop(run_id, None)
    return ResetWorkspaceResponse(status="archived")

@app.get("/api/imports/{run_id}/logs", response_model=LogResponse)
async def get_run_logs(run_id: str, after: int = 0, phase: Optional[str] = None) -> LogResponse:
    state = _read_run_state(run_id)
    normalized = (phase or "").strip().lower()
    analysis_log = getattr(state, "analysis_log_file", state.log_file)
    transfer_log = getattr(state, "transfer_log_file", state.log_file)
    if normalized == "analysis":
        target = analysis_log
    elif normalized == "transfer":
        target = transfer_log
    else:
        target = state.log_file
    return _parse_log_entries(target, state, after)


@app.get("/api/imports/{run_id}/pdf")
async def download_run_pdf(run_id: str, request: Request) -> FileResponse:
    config = _load_app_config()
    context = _resolve_review_context(config, run_id)
    if not context.pdf_path or not context.pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF-Datei für diesen Lauf wurde nicht gefunden.")
    response = FileResponse(path=context.pdf_path, media_type="application/pdf", filename=context.pdf_path.name)
    response.headers["Cache-Control"] = "no-store"
    return _apply_cors_headers(response, request)


@app.get("/api/imports/{run_id}/image")
async def download_run_image(run_id: str, request: Request) -> FileResponse:
    config = _load_app_config()
    context = _resolve_review_context(config, run_id)
    if not context.image_path or not context.image_path.exists():
        raise HTTPException(status_code=404, detail="Bilddatei für diesen Lauf wurde nicht gefunden.")
    suffix = context.image_path.suffix.lower()
    media_type = IMAGE_MEDIA_TYPES.get(suffix, "application/octet-stream")
    response = FileResponse(
        path=context.image_path,
        media_type=media_type,
        filename=context.image_path.name,
    )
    response.headers["Cache-Control"] = "no-store"
    return _apply_cors_headers(response, request)


@app.post("/api/imports/{run_id}/image", response_model=ImageUploadResponse)
async def upload_run_image(run_id: str, file: UploadFile = File(...)) -> ImageUploadResponse:
    if not file:
        raise HTTPException(status_code=400, detail="Keine Datei übergeben.")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Die hochgeladene Datei ist leer.")

    suffix = Path(file.filename or "").suffix.lower() or ".jpg"
    if suffix not in IMAGE_MEDIA_TYPES:
        suffix = ".jpg"

    config = _load_app_config()
    context = _resolve_review_context(config, run_id)
    target_name = context.image_path.name if context.image_path else DEFAULT_IMAGE_FILE
    if not target_name.endswith(suffix):
        target_name = Path(target_name).with_suffix(suffix).name
    target_path = context.pipeline_dir / target_name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(contents)

    _write_recipe_image_json(context.pipeline_dir, target_name, contents, IMAGE_MEDIA_TYPES[suffix])

    cache_buster = int(time.time())
    return ImageUploadResponse(imageUrl=f"/api/imports/{run_id}/image?ts={cache_buster}")


@app.get("/api/health")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


__all__ = ["app"]
