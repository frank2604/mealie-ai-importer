"""Command line interface for the Mealie PDF importer."""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

from .image_utils import prepare_image_asset, select_best_image
from .mealie_schema import recipe_to_mealie
from .services.ingredients import IngredientService
from .models import Recipe, RecipeAsset
from .pdf_extractor import PdfExtractionError, extract_text_and_images
from .simple_parser import parse_recipe

_LOG_LEVEL = os.getenv("LOG_LEVEL") or os.getenv("PYTHONLOGLEVEL") or "INFO"
logging.basicConfig(level=getattr(logging, _LOG_LEVEL.upper(), logging.INFO), format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("data/parsed")

try:
    from .config import ConfigError, LlmConfig, load_config  # type: ignore
    _CONFIG_IMPORT_ERROR: Optional[Exception] = None
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    ConfigError = RuntimeError  # type: ignore[assignment]
    LlmConfig = object  # type: ignore[assignment]
    load_config = None  # type: ignore[assignment]
    _CONFIG_IMPORT_ERROR = exc

try:
    from .llm_parser import LlmParsingError, OpenAiClient, parse_with_llm  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    LlmParsingError = RuntimeError  # type: ignore[assignment]
    OpenAiClient = None  # type: ignore[assignment]
    parse_with_llm = None  # type: ignore[assignment]
    _LLM_IMPORT_ERROR = exc
else:
    _LLM_IMPORT_ERROR = None

try:
    from .vision_cropper import crop_image_with_llm  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    crop_image_with_llm = None  # type: ignore[assignment]
    _VISION_IMPORT_ERROR = exc
else:
    _VISION_IMPORT_ERROR = None


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
    upload_parser.add_argument("source", type=Path, help="Pfad zur neutralen Rezept-JSON")
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
        if parse_with_llm is None or OpenAiClient is None:
            logger.error("LLM-Modul konnte nicht geladen werden (%s).", _LLM_IMPORT_ERROR)
            return 1
        assert config is not None  # for type checkers
        return _handle_parse_llm(
            pdf_path=args.pdf,
            json_path=args.json,
            default_output_dir=output_dir,
            llm_config=config.llm,  # type: ignore[arg-type]
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
    servings_hint: Optional[str],
) -> int:
    if llm_config.provider.lower() != "openai":
        logger.error("Unbekannter LLM-Provider '%s'. Aktuell wird nur 'openai' unterstützt.", llm_config.provider)
        return 1
    if not llm_config.api_key:
        logger.error("OpenAI-API-Key fehlt. Setze LLM_API_KEY in .env oder settings.yaml.")
        return 1

    try:
        extraction = extract_text_and_images(pdf_path)
    except PdfExtractionError as exc:
        logger.error("PDF konnte nicht gelesen werden: %s", exc)
        return 2

    if not extraction.text.strip():
        logger.error("PDF enthielt keinen lesbaren Text. Evtl. OCR nötig.")
        return 3

    client = OpenAiClient(
        api_key=llm_config.api_key,
        model=llm_config.model,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        base_url=llm_config.base_url,
    )

    try:
        recipe = parse_with_llm(
            extraction.text,
            llm_client=client,
            source=pdf_path,
            servings_hint=servings_hint,
        )
    except LlmParsingError as exc:
        logger.error("LLM konnte Rezept nicht verarbeiten: %s", exc)
        return 4

    _attach_image_assets(
        recipe,
        images=extraction.images,
        pdf_path=pdf_path,
        output_dir=default_output_dir / "images",
        llm_config=llm_config,
    )

    json_path = json_path or default_output_dir / f"{pdf_path.stem}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(recipe.dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("LLM-Rezept nach %s geschrieben", json_path)
    logger.info("Titel: %s", recipe.title)

    return 0


def _attach_image_assets(
    recipe,
    images,
    pdf_path: Path,
    output_dir: Path,
    llm_config: Optional[LlmConfig],
) -> None:
    if not images:
        return

    best_image = select_best_image(images)
    if best_image is None:
        return

    image_bytes = best_image.data

    if (
        llm_config
        and llm_config.api_key
        and crop_image_with_llm is not None
    ):
        cropped = crop_image_with_llm(
            image_bytes,
            llm_config=llm_config,
            title=recipe.title or pdf_path.stem,
        )
        if cropped:
            image_bytes = cropped
        else:
            logger.debug("Vision-Crop nicht möglich, verwende Originalbild")
    elif llm_config and llm_config.api_key and crop_image_with_llm is None:
        logger.warning("Vision-Modul nicht verfügbar (%s) – verwende Originalbild", _VISION_IMPORT_ERROR)

    prepared = prepare_image_asset(
        image_bytes,
        base_name=pdf_path.stem,
        output_dir=output_dir,
    )

    if not prepared:
        logger.warning("Bild konnte nicht konvertiert werden (%s)", pdf_path.name)
        return

    recipe.image_path = str(prepared.file_path)
    recipe.assets.append(
        RecipeAsset(
            file_name=prepared.file_path.name,
            data=prepared.data_url,
            title=recipe.title or pdf_path.stem,
        )
    )

    logger.info("Bild nach %s geschrieben und als Asset eingebettet", prepared.file_path)


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


def _handle_upload(*, source: Path, config, dry_run: bool) -> int:
    try:
        recipe = _load_recipe(source)
    except (OSError, ValueError) as exc:
        logger.error("Rezept konnte nicht geladen werden: %s", exc)
        return 1

    if dry_run:
        mealie_payload = recipe_to_mealie(recipe, None).to_dict()
        logger.info("Dry-Run aktiviert – Payload wird nicht gesendet")
        print(json.dumps(mealie_payload, ensure_ascii=False, indent=2))
        return 0

    ingredient_service: Optional[IngredientService] = None
    client: Optional[OpenAiClient] = None

    try:
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

        mealie_payload = recipe_to_mealie(recipe, ingredient_service).to_dict()
    finally:
        if ingredient_service:
            ingredient_service.close()

    base_url = config.mealie.base_url.rstrip("/")  # type: ignore[union-attr]
    endpoint = f"{base_url}/api/recipes"
    headers = {
        "Authorization": f"Bearer {config.mealie.token}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(endpoint, headers=headers, json=mealie_payload, timeout=60)
    except httpx.HTTPError as exc:
        logger.error("HTTP-Anfrage fehlgeschlagen: %s", exc)
        return 1

    if response.status_code >= 300:
        logger.error(
            "Mealie-API meldet Fehler %s: %s",
            response.status_code,
            response.text[:500],
        )
        return 1

    slug = _parse_slug_from_response(response)
    logger.info("Rezept erfolgreich importiert (%s)", slug or response.text[:200])

    if slug and recipe.assets:
        asset = recipe.assets[0]
        try:
            file_name, mime_type, file_bytes = _data_url_to_file(asset)
        except ValueError as exc:
            logger.warning("Bild konnte nicht verarbeitet werden: %s", exc)
            return 0

        asset_info = _upload_asset(
            base_url=base_url,
            token=config.mealie.token,  # type: ignore[union-attr]
            slug=slug,
            file_name=file_name,
            title=asset.title or recipe.title,
            mime_type=mime_type,
            file_bytes=file_bytes,
        )
        if asset_info:
            logger.info("Bild erfolgreich angehängt")
            extension = file_name.split(".")[-1]
            if _set_recipe_image_via_upload(
                base_url=base_url,
                token=config.mealie.token,  # type: ignore[union-attr]
                slug=slug,
                file_bytes=file_bytes,
                mime_type=mime_type,
                extension=extension,
            ):
                logger.info("Bild als Feature gesetzt")
        else:
            logger.warning("Bild konnte nicht als Asset hochgeladen werden")
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


def _parse_slug_from_response(response: httpx.Response) -> Optional[str]:
    slug: Optional[str] = None
    try:
        data = response.json()
    except ValueError:
        data = response.text

    if isinstance(data, dict):
        slug = data.get("slug") or data.get("id") or data.get("name")
    elif isinstance(data, str):
        slug = data

    if slug:
        return slug.strip().strip('"')
    return None


def _data_url_to_file(asset: RecipeAsset) -> tuple[str, str, bytes]:
    if not asset.data.startswith("data:"):
        raise ValueError("Asset enthält keine data:-URL")
    header, b64 = asset.data.split(",", 1)
    if ";base64" not in header:
        raise ValueError("Asset ist nicht Base64-kodiert")
    mime = header.split(":", 1)[1].split(";")[0]
    extension = "jpg"
    if "/" in mime:
        extension = mime.split("/", 1)[1]
    file_name = asset.file_name or f"asset.{extension}"
    import base64

    file_bytes = base64.b64decode(b64)
    return file_name, mime, file_bytes


def _upload_asset(*, base_url: str, token: str, slug: str, file_name: str, title: str,
                  mime_type: str, file_bytes: bytes) -> Optional[Dict[str, Any]]:
    endpoint = f"{base_url.rstrip('/')}/api/recipes/{slug}/assets"
    files = {
        "file": (file_name, file_bytes, mime_type),
    }
    data = {
        "name": title,
        "icon": "mdi-image",
        "extension": file_name.split(".")[-1],
    }
    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        response = httpx.post(endpoint, headers=headers, data=data, files=files, timeout=60)
    except httpx.HTTPError as exc:
        logger.error("Asset-Upload fehlgeschlagen: %s", exc)
        return None

    if response.status_code >= 300:
        logger.error("Asset-Upload Fehler %s: %s", response.status_code, response.text[:200])
        return None

    try:
        return response.json()
    except ValueError:
        return {"fileName": file_name}


def _set_recipe_image_via_upload(*, base_url: str, token: str, slug: str,
                                 file_bytes: bytes, mime_type: str, extension: str) -> bool:
    endpoint = f"{base_url.rstrip('/')}/api/recipes/{slug}/image"
    headers = {
        "Authorization": f"Bearer {token}",
    }
    files = {
        "image": (f"image.{extension}", file_bytes, mime_type),
    }
    data = {"extension": extension}

    try:
        response = httpx.put(endpoint, headers=headers, data=data, files=files, timeout=60)
    except httpx.HTTPError as exc:
        logger.error("Bild-Upload fehlgeschlagen: %s", exc)
        return False

    if response.status_code >= 300:
        logger.error("Bild-Upload Fehler %s: %s", response.status_code, response.text[:200])
        return False
    return True


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
