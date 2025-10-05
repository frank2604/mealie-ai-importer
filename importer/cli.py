"""Command line interface for the Mealie PDF importer."""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx

from .image_utils import prepare_image_asset, select_best_image
from .mealie_schema import recipe_to_mealie
from .services.ingredients import IngredientService
from .models import Recipe
from .pdf_extractor import PdfExtractionError, extract_text_and_images
from .simple_parser import parse_recipe
from .modules import CachePaths, PipelineContext, PipelineRunner
from .modules.add_food_ids import AddFoodIdsModule
from .modules.add_unit_ids import AddUnitIdsModule
from .modules.ai_analyser import AiAnalyserModule
from .modules.create_foods import CreateFoodsModule
from .modules.create_recipe import CreateRecipeModule
from .modules.create_units import CreateUnitsModule
from .modules.food_checker import FoodCheckerModule
from .modules.input import PdfInputModule
from .modules.unit_checker import UnitCheckerModule

_LOG_LEVEL = os.getenv("LOG_LEVEL") or os.getenv("PYTHONLOGLEVEL") or "INFO"
logging.basicConfig(level=getattr(logging, _LOG_LEVEL.upper(), logging.INFO), format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("data/parsed")

try:
    from .config import AppConfig, ConfigError, LlmConfig, load_config  # type: ignore
    _CONFIG_IMPORT_ERROR: Optional[Exception] = None
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    ConfigError = RuntimeError  # type: ignore[assignment]
    AppConfig = object  # type: ignore[assignment]
    LlmConfig = object  # type: ignore[assignment]
    load_config = None  # type: ignore[assignment]
    _CONFIG_IMPORT_ERROR = exc

try:
    from .llm_parser import OpenAiClient  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    OpenAiClient = None  # type: ignore[assignment]
    _LLM_IMPORT_ERROR = exc
else:
    _LLM_IMPORT_ERROR = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mealie-importer", description="Verarbeite Rezept-PDFs für Mealie")
    parser.add_argument("--config", type=Path, help="Alternativer Pfad zur settings.yaml")

    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="PDF lesen und Rohtext anzeigen")
    extract_parser.add_argument("pdf", type=Path, help="Pfad zur PDF-Datei")
    extract_parser.add_argument(
        "--output",
        type=Path,
        help="Pfad für die Textausgabe (Standard: data/parsed/<name>.txt)",
    )

    parse_parser = subparsers.add_parser("parse", help="PDF in Rezept-Struktur überführen (heuristisch)")
    parse_parser.add_argument("pdf", type=Path, help="Pfad zur PDF-Datei")
    parse_parser.add_argument(
        "--json",
        type=Path,
        help="Optionaler Pfad für die Ausgabe als JSON",
    )

    parse_llm_parser = subparsers.add_parser("parse-llm", help="PDF mit LLM analysieren und strukturieren")
    parse_llm_parser.add_argument("pdf", type=Path, help="Pfad zur PDF-Datei")
    parse_llm_parser.add_argument(
        "--json",
        type=Path,
        help="Pfad für die Ausgabe als JSON (Standard: data/parsed/<name>.json)",
    )
    parse_llm_parser.add_argument(
        "--servings",
        type=str,
        help="Optionaler Hinweis zu Portionen, der ins Prompt übernommen wird",
    )

    export_parser = subparsers.add_parser(
        "export-mealie", help="Konvertiere internes JSON in Mealie-Format"
    )
    export_parser.add_argument("source", type=Path, help="Pfad zur neutralen Rezept-JSON")
    export_parser.add_argument(
        "--output",
        type=Path,
        help="Zielpfad für das Mealie-JSON (Standard: data/mealie/<name>.json)",
    )

    upload_parser = subparsers.add_parser("upload", help="Rezept nach Mealie übertragen")
    upload_parser.add_argument("source", type=Path, help="Pfad zur Rezept-JSON oder zur PDF-Datei")
    upload_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur Payload anzeigen, nicht senden",
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if load_config is None and args.command in {"parse-llm"}:
        logger.error(
            "Konfigurationsmodul fehlt (%s). Installiere 'pyyaml', um parse-llm nutzen zu können.",
            _CONFIG_IMPORT_ERROR,
        )
        return 1

    config_path: Optional[Path] = args.config
    output_dir = DEFAULT_OUTPUT_DIR
    config = None

    if load_config is not None:
        try:
            config = load_config(config_path)
            output_dir = config.processing.output_folder
        except ConfigError as exc:
            if args.command in {"parse", "extract"}:
                logger.warning("Konfiguration nicht geladen (%s). Verwende Standard-Ausgabeordner %s.", exc, output_dir)
            else:
                logger.error("Konfiguration fehlt oder ist ungültig: %s", exc)
                return 1
    elif args.command in {"parse-llm"}:
        logger.error("Konfiguration nicht verfügbar. parse-llm benötigt settings.yaml oder Umgebungsvariablen.")
        return 1

    if args.command == "extract":
        return _handle_extract(args.pdf, args.output, output_dir)
    if args.command == "parse":
        llm_cfg = config.llm if config is not None else None  # type: ignore[attr-defined]
        return _handle_parse(args.pdf, args.json, output_dir, llm_cfg)
    if args.command == "parse-llm":
        if OpenAiClient is None:
            logger.error("LLM-Modul konnte nicht geladen werden (%s).", _LLM_IMPORT_ERROR)
            return 1
        assert config is not None  # for type checkers
        return _handle_parse_llm(
            pdf_path=args.pdf,
            json_path=args.json,
            default_output_dir=output_dir,
            llm_config=config.llm,  # type: ignore[arg-type]
            config=config,
            servings_hint=args.servings,
        )
    if args.command == "export-mealie":
        return _handle_export_mealie(args.source, args.output, config)
    if args.command == "upload":
        if config is None or not config.mealie.base_url or not config.mealie.token:
            logger.error("Mealie-Konfiguration fehlt. Bitte MEALIE_BASE_URL und MEALIE_TOKEN setzen.")
            return 1
        return _handle_upload(
            source=args.source,
            config=config,
            dry_run=args.dry_run,
        )

    parser.print_help()
    return 0


def _handle_extract(pdf_path: Path, output: Optional[Path], default_output_dir: Path) -> int:
    try:
        result = extract_text_and_images(pdf_path)
    except PdfExtractionError as exc:
        logger.error("PDF konnte nicht gelesen werden: %s", exc)
        return 2

    destination = output or default_output_dir / f"{pdf_path.stem}.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result.text, encoding="utf-8")

    logger.info("%s Seiten gelesen, Text nach %s geschrieben", result.page_count, destination)

    if result.images:
        image_dir = destination.parent / f"{pdf_path.stem}_images"
        saved = 0
        for index, image in enumerate(result.images, start=1):
            base_name = f"{pdf_path.stem}-{index}"
            prepared = prepare_image_asset(image.data, base_name=base_name, output_dir=image_dir)
            if prepared:
                saved += 1
            else:
                raw_path = image_dir / f"{base_name}.bin"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(image.data)
        if saved:
            logger.info("%s Bilder als JPEG/PNG gespeichert (siehe %s)", saved, image_dir)
        else:
            logger.info("Keine konvertierbaren Bilder gefunden – Rohdaten liegen in %s", image_dir)
    else:
        logger.info("Keine eingebetteten Bilder gefunden")

    return 0


def _handle_parse(
    pdf_path: Path,
    json_path: Optional[Path],
    default_output_dir: Path,
    llm_config: Optional[LlmConfig],
) -> int:
    try:
        result = extract_text_and_images(pdf_path)
    except PdfExtractionError as exc:
        logger.error("PDF konnte nicht gelesen werden: %s", exc)
        return 2

    try:
        recipe = parse_recipe(result.text, pdf_path)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Rezept konnte nicht geparst werden: %s", exc)
        return 3

    _attach_image_assets(
        recipe,
        images=result.images,
        pdf_path=pdf_path,
        output_dir=default_output_dir / "images",
        llm_config=llm_config,
    )

    json_data = recipe.dict()

    destination = json_path or default_output_dir / f"{pdf_path.stem}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Rezept nach %s geschrieben", destination)
    logger.info("Titel: %s", recipe.title)

    return 0


def _handle_parse_llm(
    *,
    pdf_path: Path,
    json_path: Optional[Path],
    default_output_dir: Path,
    llm_config: LlmConfig,
    config,
    servings_hint: Optional[str],
) -> int:
    if llm_config.provider.lower() != "openai":
        logger.error("Unbekannter LLM-Provider '%s'. Aktuell wird nur 'openai' unterstützt.", llm_config.provider)
        return 1
    if not llm_config.api_key:
        logger.error("OpenAI-API-Key fehlt. Setze LLM_API_KEY in .env oder settings.yaml.")
        return 1

    try:
        client = _create_openai_client(llm_config)
    except ValueError as exc:
        logger.error("LLM-Client konnte nicht erstellt werden: %s", exc)
        return 1

    output_json = json_path or default_output_dir / f"{pdf_path.stem}.json"
    cache_paths = CachePaths(config.ingredients.cache_dir, pdf_path.stem)
    context = PipelineContext(
        source_pdf=pdf_path,
        output_dir=default_output_dir,
        config=config,
        cache_paths=cache_paths,
        servings_hint=servings_hint,
        recipe_output_path=output_json,
    )

    modules = [
        PdfInputModule(),
        AiAnalyserModule(
            llm_client=client,
            llm_config=llm_config,
            output_json=output_json,
            image_output_dir=default_output_dir / "images",
        ),
    ]

    runner = PipelineRunner(modules)
    try:
        runner.run(context)
    except RuntimeError as exc:
        logger.error("LLM-Analyse fehlgeschlagen: %s", exc)
        return 4

    logger.info("LLM-Rezept nach %s geschrieben", output_json)
    logger.info("Titel: %s", context.ensure_recipe().title)

    return 0


def _handle_export_mealie(source: Path, output: Optional[Path], config) -> int:
    try:
        recipe = _load_recipe(source)
    except (OSError, ValueError) as exc:
        logger.error("Rezept konnte nicht geladen werden: %s", exc)
        return 1

    ingredient_service: Optional[IngredientService] = None
    client: Optional[OpenAiClient] = None
    if config is not None:
        try:
            client = _create_openai_client(config.llm)
        except ValueError:
            client = None
        ingredient_service = IngredientService(
            base_url=config.mealie.base_url,
            token=config.mealie.token,
            config=config.ingredients,
            llm_client=client,
        )

    try:
        payload = recipe_to_mealie(recipe, ingredient_service).to_dict()
    finally:
        if ingredient_service:
            ingredient_service.close()

    destination = output or Path("data/mealie") / f"{source.stem}-mealie.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Mealie-JSON nach %s geschrieben", destination)
    return 0


def _handle_upload(*, source: Path, config: AppConfig, dry_run: bool) -> int:
    if source.suffix.lower() == ".pdf":
        return _handle_upload_pdf(pdf_path=source, config=config, dry_run=dry_run)
    return _handle_upload_json(source=source, config=config, dry_run=dry_run)


def _handle_upload_pdf(*, pdf_path: Path, config: AppConfig, dry_run: bool) -> int:
    if OpenAiClient is None:
        logger.error("LLM-Modul konnte nicht geladen werden (%s).", _LLM_IMPORT_ERROR)
        return 1
    try:
        llm_client = _create_openai_client(config.llm)
    except ValueError as exc:
        logger.error("LLM-Client konnte nicht erstellt werden: %s", exc)
        return 1

    ingredient_service = IngredientService(
        base_url=config.mealie.base_url,
        token=config.mealie.token,
        config=config.ingredients,
        llm_client=llm_client,
    )

    cache_paths = CachePaths(config.ingredients.cache_dir, pdf_path.stem)
    output_dir = config.processing.output_folder
    output_json = output_dir / f"{pdf_path.stem}.json"
    context = PipelineContext(
        source_pdf=pdf_path,
        output_dir=output_dir,
        config=config,
        cache_paths=cache_paths,
        servings_hint=None,
        recipe_output_path=output_json,
    )

    modules: List = [
        PdfInputModule(),
        AiAnalyserModule(
            llm_client=llm_client,
            llm_config=config.llm,
            output_json=output_json,
            image_output_dir=output_dir / "images",
        ),
        FoodCheckerModule(ingredient_service, llm_client=llm_client),
        CreateFoodsModule(ingredient_service, dry_run=dry_run),
        AddFoodIdsModule(),
        UnitCheckerModule(ingredient_service, llm_client=llm_client),
        CreateUnitsModule(ingredient_service, dry_run=dry_run),
        AddUnitIdsModule(),
        CreateRecipeModule(config=config, ingredient_service=ingredient_service, dry_run=dry_run),
    ]

    runner = PipelineRunner(modules)
    try:
        runner.run(context)
    except RuntimeError as exc:
        logger.error("Pipeline fehlgeschlagen: %s", exc)
        return 1
    finally:
        ingredient_service.close()

    return 0


def _handle_upload_json(*, source: Path, config: AppConfig, dry_run: bool) -> int:
    try:
        recipe = _load_recipe(source)
    except (OSError, ValueError) as exc:
        logger.error("Rezept konnte nicht geladen werden: %s", exc)
        return 1

    try:
        llm_client = _create_openai_client(config.llm)
    except ValueError:
        llm_client = None

    ingredient_service = IngredientService(
        base_url=config.mealie.base_url,
        token=config.mealie.token,
        config=config.ingredients,
        llm_client=llm_client,
    )

    cache_paths = CachePaths(config.ingredients.cache_dir, source.stem)
    context = PipelineContext(
        source_pdf=source,
        output_dir=config.processing.output_folder,
        config=config,
        cache_paths=cache_paths,
    )
    context.recipe = recipe

    module = CreateRecipeModule(config=config, ingredient_service=ingredient_service, dry_run=dry_run)
    try:
        module.run(context)
    except RuntimeError as exc:
        logger.error("Rezept konnte nicht hochgeladen werden: %s", exc)
        return 1
    finally:
        ingredient_service.close()

    return 0


def _load_recipe(path: Path) -> Recipe:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ungültiges JSON in {path}: {exc}") from exc
    return Recipe.parse_obj(data)


def _create_openai_client(llm_config: LlmConfig) -> Optional[OpenAiClient]:
    if not llm_config.api_key:
        raise ValueError("Kein OpenAI API Key konfiguriert")
    return OpenAiClient(
        api_key=llm_config.api_key,
        model=llm_config.model,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        base_url=llm_config.base_url,
        timeout=llm_config.timeout,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
