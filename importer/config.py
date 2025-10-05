"""Configuration helpers for the Mealie importer."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path("config/settings.yaml")


@dataclass
class MealieConfig:
    base_url: Optional[str]
    token: Optional[str]


@dataclass
class ProcessingConfig:
    watch_folder: Path
    output_folder: Path
    ocr_enabled: bool = False
    language: str = "de"
    skip_ai_if_cached: bool = False


@dataclass
class LlmConfig:
    provider: str
    model: str
    temperature: Optional[float]
    max_tokens: Optional[int]
    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1"
    vision_model: Optional[str] = None
    timeout: float = 120.0


@dataclass
class IngredientConfig:
    fuzzy_threshold: int = 90
    cache_dir: Path = Path("data/cache")
    default_category: str = "Sonstiges"
    default_category_color: str = "#959595"
    use_llm_classifier: bool = True


@dataclass
class AppConfig:
    mealie: MealieConfig
    processing: ProcessingConfig
    llm: LlmConfig
    ingredients: IngredientConfig


class ConfigError(RuntimeError):
    """Raised when configuration cannot be loaded."""


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """Load application configuration from YAML + environment variables."""
    load_dotenv()

    path = config_path or _DEFAULT_CONFIG_PATH
    data = _read_yaml(path) if path.exists() else {}

    mealie_section = data.get("mealie", {})
    processing_section = data.get("processing", {})
    llm_section = data.get("llm", {})

    base_url = _env_or_default("MEALIE_BASE_URL", mealie_section.get("base_url"))
    token = _env_or_default("MEALIE_TOKEN", mealie_section.get("token"))

    mealie = MealieConfig(base_url=base_url, token=token)

    watch_folder = Path(_env_or_default("WATCH_FOLDER", processing_section.get("watch_folder", "PDFs")))
    output_folder = Path(_env_or_default("OUTPUT_FOLDER", processing_section.get("output_folder", "data/parsed")))

    processing = ProcessingConfig(
        watch_folder=watch_folder,
        output_folder=output_folder,
        ocr_enabled=_env_flag("OCR_ENABLED", processing_section.get("ocr_enabled", False)),
        language=_env_or_default("LANGUAGE", processing_section.get("language", "de")),
        skip_ai_if_cached=_env_flag(
            "SKIP_AI_IF_CACHED",
            processing_section.get("skip_ai_if_cached", False),
        ),
    )

    llm = LlmConfig(
        provider=_env_or_default("LLM_PROVIDER", llm_section.get("provider", "openai")),
        model=_env_or_default("LLM_MODEL", llm_section.get("model", "gpt-4o-mini")),
        temperature=_maybe_float(_env_or_default("LLM_TEMPERATURE", llm_section.get("temperature"))),
        max_tokens=_maybe_int(_env_or_default("LLM_MAX_TOKENS", llm_section.get("max_tokens")), default=4096),
        api_key=_env_or_default("LLM_API_KEY", llm_section.get("api_key")),
        base_url=_env_or_default("LLM_BASE_URL", llm_section.get("base_url", "https://api.openai.com/v1")),
        vision_model=_env_or_default("LLM_VISION_MODEL", llm_section.get("vision_model")),
        timeout=_maybe_float(_env_or_default("LLM_TIMEOUT", llm_section.get("timeout")), default=120.0) or 120.0,
    )

    ingredient_section = data.get("ingredients", {})
    ingredients = IngredientConfig(
        fuzzy_threshold=int(_env_or_default("INGREDIENT_FUZZY_THRESHOLD", ingredient_section.get("fuzzy_threshold", 90))),
        cache_dir=Path(_env_or_default("INGREDIENT_CACHE_DIR", ingredient_section.get("cache_dir", "data/cache"))),
        default_category=_env_or_default("INGREDIENT_DEFAULT_CATEGORY", ingredient_section.get("default_category", "Sonstiges")),
        default_category_color=_env_or_default("INGREDIENT_DEFAULT_CATEGORY_COLOR", ingredient_section.get("default_category_color", "#959595")),
        use_llm_classifier=_env_flag("INGREDIENT_USE_LLM_CLASSIFIER", ingredient_section.get("use_llm_classifier", True)),
    )

    if mealie.base_url is None or mealie.token is None:
        logger.debug("Mealie-Konfiguration unvollständig – Upload-Funktionen sind erst später verfügbar")

    if not llm.api_key:
        logger.debug("LLM_API_KEY ist nicht gesetzt – parse-llm wird scheitern, bis ein Key vorliegt")

    logger.debug(
        "Configuration loaded",
        extra={
            "mealie_base": mealie.base_url,
            "processing_watch": str(processing.watch_folder),
            "processing_output": str(processing.output_folder),
            "llm_provider": llm.provider,
            "llm_model": llm.model,
        },
    )

    return AppConfig(mealie=mealie, processing=processing, llm=llm, ingredients=ingredients)


def _read_yaml(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Invalid YAML configuration in {path}: {exc}") from exc
    except OSError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Failed to read configuration file {path}: {exc}") from exc


def _env_or_default(name: str, default=None):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return bool(default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _maybe_float(value: Optional[str], default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Ungültiger Float-Wert für Temperatur: %s", value)
        return default


def _maybe_int(value: Optional[str], default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Ungültiger Integer-Wert: %s", value)
        return default
