"""Create the final recipe in Mealie or provide the payload."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from ..context import PipelineContext
from ...config import AppConfig
from ...mealie_schema import recipe_to_mealie
from ...models import RecipeAsset
from ...services.ingredients import IngredientService

logger = logging.getLogger(__name__)


class CreateRecipeModule:
    """Send the recipe to Mealie or expose the payload for inspection."""

    name = "Create Recipe"

    def __init__(
        self,
        config: AppConfig,
        ingredient_service: Optional[IngredientService],
        *,
        dry_run: bool = False,
    ) -> None:
        self._config = config
        self._service = ingredient_service
        self._dry_run = dry_run

    def run(self, context: PipelineContext) -> None:
        recipe = context.ensure_recipe()
        logger.info("Erzeuge Mealie-Payload")

        payload = recipe_to_mealie(recipe, self._service).to_dict()
        context.mealie_payload = payload

        if self._dry_run:
            logger.info("Dry-Run aktiviert – Rezept wird nicht gesendet")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        base_url = (self._config.mealie.base_url or "").rstrip("/")
        token = self._config.mealie.token
        if not base_url or not token:
            raise RuntimeError("Mealie-Basis-URL oder Token fehlen für den Upload")

        endpoint = f"{base_url}/api/recipes"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=60)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"HTTP-Anfrage fehlgeschlagen: {exc}") from exc

        if response.status_code >= 300:
            raise RuntimeError(
                f"Mealie-API meldet Fehler {response.status_code}: {response.text[:500]}"
            )

        response_data = _parse_recipe_from_response(response)
        slug = response_data.get("slug") or _parse_slug_from_response(response)
        logger.info("Rezept erfolgreich importiert (%s)", slug or response.text[:200])

        if slug:
            try:
                _update_recipe_details(
                    base_url=base_url,
                    token=token,
                    slug=slug,
                    payload=payload,
                    created_recipe=response_data,
                )
            except RuntimeError as exc:
                logger.warning("Rezeptdetails konnten nicht aktualisiert werden: %s", exc)
            else:
                logger.info("Rezeptdetails aktualisiert")

        if slug and recipe.assets:
            asset = recipe.assets[0]
            try:
                file_name, mime_type, file_bytes = _data_url_to_file(asset)
            except ValueError as exc:
                logger.warning("Bild konnte nicht verarbeitet werden: %s", exc)
                return

            asset_info = _upload_asset(
                base_url=base_url,
                token=token,
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
                    token=token,
                    slug=slug,
                    file_bytes=file_bytes,
                    mime_type=mime_type,
                    extension=extension,
                ):
                    logger.info("Bild als Feature gesetzt")
            else:
                logger.warning("Bild konnte nicht als Asset hochgeladen werden")


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


def _update_recipe_details(
    base_url: str,
    token: str,
    slug: str,
    payload: Dict[str, object],
    created_recipe: Optional[Dict[str, Any]] = None,
) -> None:
    recipe = created_recipe or _fetch_recipe(base_url=base_url, token=token, slug=slug)

    update_payload = _merge_recipe_payload(recipe, payload, slug)

    _send_recipe_update(
        base_url=base_url,
        token=token,
        slug=slug,
        update_payload=update_payload,
    )


def _send_recipe_update(
    base_url: str,
    token: str,
    slug: str,
    update_payload: Dict[str, object],
) -> None:
    endpoint = f"{base_url.rstrip('/')}/api/recipes/{slug}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.put(endpoint, headers=headers, json=update_payload, timeout=60)
    except httpx.HTTPError as exc:  # pragma: no cover - runtime safeguard
        raise RuntimeError(f"HTTP-Anfrage fehlgeschlagen: {exc}") from exc

    if response.status_code >= 300:
        raise RuntimeError(f"{response.status_code}: {response.text[:500]}")


def _fetch_recipe(base_url: str, token: str, slug: str) -> Dict[str, object]:
    endpoint = f"{base_url.rstrip('/')}/api/recipes/{slug}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        response = httpx.get(endpoint, headers=headers, timeout=30)
    except httpx.HTTPError as exc:  # pragma: no cover - runtime safeguard
        raise RuntimeError(f"HTTP-Abfrage fehlgeschlagen: {exc}") from exc

    if response.status_code >= 300:
        raise RuntimeError(f"{response.status_code}: {response.text[:500]}")

    try:
        data = response.json()
    except ValueError as exc:  # pragma: no cover - runtime safeguard
        raise RuntimeError("Antwort konnte nicht gelesen werden") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Unerwartete Antwort beim Lesen des Rezepts")

    return data


def _merge_recipe_payload(
    existing: Dict[str, object],
    new_payload: Dict[str, object],
    slug: Optional[str],
) -> Dict[str, object]:
    merged: Dict[str, object] = dict(existing)

    payload_copy = dict(new_payload)
    payload_copy.pop("assets", None)

    for key in [
        "name",
        "description",
        "recipeServings",
        "recipeIngredient",
        "recipeInstructions",
        "recipeCategory",
        "tags",
        "tools",
        "notes",
        "totalTime",
        "orgURL",
    ]:
        if key in payload_copy:
            if key == "tags":
                merged[key] = _merge_name_slug_list(existing.get(key), payload_copy[key])
            elif key == "recipeCategory":
                merged[key] = _merge_name_slug_list(existing.get(key), payload_copy[key])
            else:
                merged[key] = payload_copy[key]

    if "settings" in payload_copy:
        merged_settings: Dict[str, object] = {}
        existing_settings = existing.get("settings")
        if isinstance(existing_settings, dict):
            merged_settings.update(existing_settings)
        new_settings = payload_copy.get("settings")
        if isinstance(new_settings, dict):
            merged_settings.update(new_settings)
        merged["settings"] = merged_settings

    if slug:
        merged["slug"] = slug
    elif existing.get("slug"):
        merged["slug"] = existing["slug"]

    for key in ("id", "userId", "groupId", "householdId"):
        if existing.get(key) is not None:
            merged[key] = existing[key]

    return merged


def _parse_recipe_from_response(response: httpx.Response) -> Dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}

    if isinstance(data, dict):
        return data
    return {}


def _merge_name_slug_list(
    existing: Optional[object], new_entries: Optional[object]
) -> Optional[List[Dict[str, object]]]:
    if not isinstance(new_entries, list):
        return None

    existing_map: Dict[str, Dict[str, object]] = {}
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, dict):
                slug = item.get("slug")
                if isinstance(slug, str):
                    existing_map[slug] = dict(item)

    merged_entries: List[Dict[str, object]] = []
    for item in new_entries:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug")
        if isinstance(slug, str) and slug in existing_map:
            combined = existing_map[slug]
            combined.update(item)
            merged_entries.append(combined)
        else:
            merged_entries.append(dict(item))

    return merged_entries


def _data_url_to_file(asset: RecipeAsset) -> tuple[str, str, bytes]:
    if not asset.data or not asset.data.startswith("data:"):
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


def _upload_asset(
    *,
    base_url: str,
    token: str,
    slug: str,
    file_name: str,
    title: str,
    mime_type: str,
    file_bytes: bytes,
) -> Optional[Dict[str, object]]:
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


def _set_recipe_image_via_upload(
    *,
    base_url: str,
    token: str,
    slug: str,
    file_bytes: bytes,
    mime_type: str,
    extension: str,
) -> bool:
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

