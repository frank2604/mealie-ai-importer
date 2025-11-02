"""Create the final recipe in Mealie or provide the payload."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import httpx

from ..context import PipelineContext
from ...config import AppConfig
from ...exceptions import UserAbort
from ...mealie_schema import recipe_to_mealie
from ...models import RecipeAsset
from ...services.ingredients import IngredientService
from ...services.run_workspace import ApiLabel, ApiPayloadRecorder

logger = logging.getLogger("Create Recipe")


def _response_cache_payload(response: httpx.Response) -> Dict[str, Any]:
    """Return a JSON-safe representation of an HTTP response body."""
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text
    return {
        "status": response.status_code,
        "body": body,
    }


def _log_payload(label: str, data: Dict[str, object]) -> None:
    """Log recipe payloads without flooding the log with large binary fields."""

    def _sanitize(value: object) -> object:
        if isinstance(value, dict):
            sanitized: Dict[str, object] = {}
            for key, item in value.items():
                if key in {"assets", "image"}:
                    continue
                sanitized[key] = _sanitize(item)
            return sanitized
        if isinstance(value, list):
            return [_sanitize(item) for item in value][:10]
        if isinstance(value, str) and len(value) > 200:
            return value[:200] + "…"
        return value

    summary: Dict[str, object] = {}
    try:
        summary = _sanitize(data) if isinstance(data, dict) else {}
        if isinstance(data, dict) and data.get("assets"):
            summary["assets"] = [
                {
                    "fileName": asset.get("fileName"),
                    "title": asset.get("title"),
                }
                for asset in data.get("assets", [])[:3]
                if isinstance(asset, dict)
            ]
    except Exception:  # pragma: no cover - logging only
        summary = {}

    try:
        logger.debug("Mealie-Payload %s: %s", label, json.dumps(summary, ensure_ascii=False))
    except TypeError:  # pragma: no cover - logging only
        logger.debug("Mealie payload %s contains data that cannot be serialized", label)


def _slugify(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug


def _is_duplicate_slug(slug: str, expected_slug: str) -> bool:
    if not slug or not expected_slug:
        return False
    if slug == expected_slug:
        return False
    if not slug.startswith(f"{expected_slug}-"):
        return False
    suffix = slug[len(expected_slug) + 1 :]
    return suffix.isdigit()


_RECIPE_API_LABELS: Dict[str, ApiLabel] = {
    "post_recipe_request": ApiLabel(
        "POST",
        "/api/recipes",
        "request",
        "name",
        include_entity=False,
        action_template="Sending recipe details to Mealie",
    ),
    "post_recipe_response": ApiLabel(
        "POST",
        "/api/recipes",
        "response",
        "body.slug",
        include_entity=False,
        action_template="Mealie accepted the recipe details",
    ),
    "post_recipe_response_error": ApiLabel(
        "POST",
        "/api/recipes",
        "response_error",
        include_entity=False,
        action_template="Mealie reported an issue while creating the recipe",
    ),
    "get_recipe_request_initial": ApiLabel(
        "GET",
        "/api/recipes/{slug}",
        "request_initial",
        "slug",
        include_entity=False,
        action_template="Checking if the recipe already exists in Mealie",
    ),
    "get_recipe_response_initial": ApiLabel(
        "GET",
        "/api/recipes/{slug}",
        "response_initial",
        "body.slug",
        include_entity=False,
        action_template="Mealie responded to the initial recipe lookup",
    ),
    "put_recipe_request": ApiLabel(
        "PUT",
        "/api/recipes/{slug}",
        "request",
        "slug",
        include_entity=False,
        action_template="Updating the recipe in Mealie",
    ),
    "put_recipe_response": ApiLabel(
        "PUT",
        "/api/recipes/{slug}",
        "response",
        "body.slug",
        include_entity=False,
        action_template="Mealie confirmed the recipe update",
    ),
    "put_recipe_response_error": ApiLabel(
        "PUT",
        "/api/recipes/{slug}",
        "response_error",
        include_entity=False,
        action_template="Mealie reported an issue while updating the recipe",
    ),
    "get_recipe_request_after_put": ApiLabel(
        "GET",
        "/api/recipes/{slug}",
        "request_after_put",
        "slug",
        include_entity=False,
        action_template="Confirming the saved recipe in Mealie",
    ),
    "get_recipe_response_after_put": ApiLabel(
        "GET",
        "/api/recipes/{slug}",
        "response_after_put",
        "body.slug",
        include_entity=False,
        action_template="Mealie returned the saved recipe details",
    ),
    "patch_recipe_request": ApiLabel(
        "PATCH",
        "/api/recipes/{slug}",
        "request",
        "slug",
        include_entity=False,
        action_template="Sending final recipe adjustments to Mealie",
    ),
    "patch_recipe_response": ApiLabel(
        "PATCH",
        "/api/recipes/{slug}",
        "response",
        "body.slug",
        include_entity=False,
        action_template="Mealie confirmed the final adjustments",
    ),
    "patch_recipe_response_error": ApiLabel(
        "PATCH",
        "/api/recipes/{slug}",
        "response_error",
        include_entity=False,
        action_template="Mealie reported an issue while applying the adjustments",
    ),
    "upload_asset_request": ApiLabel(
        "POST",
        "/api/recipes/{slug}/assets",
        "request",
        "slug",
        include_entity=False,
        action_template="Uploading recipe files to Mealie",
    ),
    "upload_asset_response": ApiLabel(
        "POST",
        "/api/recipes/{slug}/assets",
        "response",
        "body.slug",
        include_entity=False,
        action_template="Mealie confirmed the file upload",
    ),
    "upload_asset_response_error": ApiLabel(
        "POST",
        "/api/recipes/{slug}/assets",
        "response_error",
        include_entity=False,
        action_template="Mealie reported an issue with the file upload",
    ),
    "set_feature_image_request": ApiLabel(
        "POST",
        "/api/recipes/{slug}/image",
        "request",
        "slug",
        include_entity=False,
        action_template="Setting the feature image in Mealie",
    ),
    "set_feature_image_response": ApiLabel(
        "POST",
        "/api/recipes/{slug}/image",
        "response",
        "body.slug",
        include_entity=False,
        action_template="Mealie confirmed the feature image",
    ),
    "set_feature_image_response_error": ApiLabel(
        "POST",
        "/api/recipes/{slug}/image",
        "response_error",
        include_entity=False,
        action_template="Mealie reported an issue while setting the feature image",
    ),
    "delete_recipe_request": ApiLabel(
        "DELETE",
        "/api/recipes/{slug}",
        "request_delete",
        "slug",
        include_entity=False,
        action_template="Removing the placeholder recipe in Mealie",
    ),
    "delete_recipe_response": ApiLabel(
        "DELETE",
        "/api/recipes/{slug}",
        "response_delete",
        "body.slug",
        include_entity=False,
        action_template="Mealie confirmed the placeholder removal",
    ),
    "delete_recipe_response_error": ApiLabel(
        "DELETE",
        "/api/recipes/{slug}",
        "response_delete_error",
        include_entity=False,
        action_template="Mealie reported an issue while removing the placeholder",
    ),
}


class CreateRecipeModule:
    """Send the recipe to Mealie or expose the payload for inspection."""

    name = "Create Recipe"

    def __init__(
        self,
        config: AppConfig,
        ingredient_service: Optional[IngredientService],
        *,
        dry_run: bool = False,
        on_duplicate: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        self._config = config
        self._service = ingredient_service
        self._dry_run = dry_run
        self._verify = config.mealie.verify_option()
        self._on_duplicate = on_duplicate

    def run(self, context: PipelineContext) -> None:
        recipe = context.ensure_recipe()
        logger.info("Preparing the data that will be sent to Mealie")

        full_payload = recipe_to_mealie(recipe, self._service).to_dict()
        _log_payload("PREPARED", full_payload)

        instructions_payload = full_payload.get("recipeInstructions", [])
        base_payload = dict(full_payload)
        base_payload.pop("recipeInstructions", None)
        base_payload.pop("assets", None)

        context.mealie_payload = full_payload

        if self._dry_run:
            logger.info("Dry-run is enabled, so the recipe is not sent to Mealie")
            print(json.dumps(full_payload, ensure_ascii=False, indent=2))
            return

        base_url = (self._config.mealie.base_url or "").rstrip("/")
        token = self._config.mealie.token
        if not base_url or not token:
            raise RuntimeError("Mealie base URL or token is missing; cannot upload")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        read_headers = {"Authorization": f"Bearer {token}"}
        api_recorder = ApiPayloadRecorder(
            recorder=context.pipeline_recorder,
            logger=logger,
            label_prefix="Mealie",
            mapping=_RECIPE_API_LABELS,
            fallback_dir=context.output_dir / "recipe_api_debug",
        )

        # 1) POST: nur Name übertragen
        post_endpoint = f"{base_url}/api/recipes"
        post_payload = {"name": base_payload.get("name")}
        if not post_payload.get("name"):
            raise RuntimeError("The recipe name is missing; the upload cannot start")
        _log_payload("POST_INIT", post_payload)
        api_recorder.write("post_recipe_request", post_payload)

        try:
            response = httpx.post(
                post_endpoint,
                headers=headers,
                json=post_payload,
                timeout=60,
                verify=self._verify,
            )
        except httpx.HTTPError as exc:
            api_recorder.write("post_recipe_response_error", {"error": str(exc)})
            raise RuntimeError(f"The HTTP request to Mealie failed: {exc}") from exc

        api_recorder.write("post_recipe_response", _response_cache_payload(response))
        if response.status_code >= 300:
            raise RuntimeError(
                f"Mealie returned error {response.status_code}: {response.text[:500]}"
            )

        response_data = _parse_recipe_from_response(response)
        slug = response_data.get("slug") or _parse_slug_from_response(response)
        if not slug:
            raise RuntimeError("Could not find a slug in Mealie's response body")
        logger.info("Created a placeholder recipe in Mealie (%s)", slug)

        expected_slug = _slugify(post_payload.get("name") or recipe.title or "")
        if self._on_duplicate and _is_duplicate_slug(slug, expected_slug):
            proceed = self._on_duplicate(slug, recipe.title or context.source_pdf.stem)
            if not proceed:
                logger.info("Stopped the import because a duplicate was detected, so the placeholder %s is removed", slug)
                self._delete_recipe_placeholder(
                    base_url=base_url,
                    slug=slug,
                    headers=headers,
                    api_recorder=api_recorder,
                )
                raise UserAbort("Duplicate detected; import aborted")
            logger.info("A duplicate was detected, but we continue with the import as requested")

        endpoint_with_slug = f"{base_url}/api/recipes/{slug}"

        # 2) GET: frisch angelegtes Rezept abrufen
        api_recorder.write("get_recipe_request_initial", {"slug": slug})
        try:
            response = httpx.get(
                endpoint_with_slug,
                headers=read_headers,
                timeout=60,
                verify=self._verify,
            )
        except httpx.HTTPError as exc:
            api_recorder.write("get_recipe_response_initial", {"error": str(exc)})
            raise RuntimeError(f"The HTTP request to Mealie failed: {exc}") from exc

        api_recorder.write("get_recipe_response_initial", _response_cache_payload(response))
        if response.status_code >= 300:
            raise RuntimeError(
                f"Fetching the newly created recipe failed ({response.status_code}): {response.text[:500]}"
            )
        initial_recipe = _parse_recipe_from_response(response)

        # 3) PUT: Details ohne Zubereitungsschritte übertragen
        put_payload = _build_put_payload(initial_recipe, base_payload, slug)
        _log_payload("PUT_BODY", put_payload)
        api_recorder.write("put_recipe_request", put_payload)

        try:
            response = httpx.put(
                endpoint_with_slug,
                headers=headers,
                json=put_payload,
                timeout=60,
                verify=self._verify,
            )
        except httpx.HTTPError as exc:
            api_recorder.write("put_recipe_response_error", {"error": str(exc)})
            raise RuntimeError(f"The HTTP request to Mealie failed: {exc}") from exc

        api_recorder.write("put_recipe_response", _response_cache_payload(response))
        if response.status_code >= 300:
            raise RuntimeError(f"Mealie returned error {response.status_code}: {response.text[:500]}")

        # 4) GET: Rezept nach PUT abrufen (u. a. für referenceIds)
        api_recorder.write("get_recipe_request_after_put", {"slug": slug})
        try:
            response = httpx.get(
                endpoint_with_slug,
                headers=read_headers,
                timeout=60,
                verify=self._verify,
            )
        except httpx.HTTPError as exc:
            api_recorder.write("get_recipe_response_after_put", {"error": str(exc)})
            raise RuntimeError(f"The HTTP request to Mealie failed: {exc}") from exc

        api_recorder.write("get_recipe_response_after_put", _response_cache_payload(response))
        if response.status_code >= 300:
            raise RuntimeError(
                f"Fetching the recipe after the update failed ({response.status_code}): {response.text[:500]}"
            )
        recipe_after_put = _parse_recipe_from_response(response)

        # 5) PATCH: Zubereitungsschritte anreichern
        patch_payload = _build_patch_payload(recipe_after_put, instructions_payload)
        _log_payload("PATCH_BODY", patch_payload)
        api_recorder.write("patch_recipe_request", patch_payload)

        try:
            response = httpx.patch(
                endpoint_with_slug,
                headers=headers,
                json=patch_payload,
                timeout=60,
                verify=self._verify,
            )
        except httpx.HTTPError as exc:
            api_recorder.write("patch_recipe_response_error", {"error": str(exc)})
            raise RuntimeError(f"The HTTP request to Mealie failed: {exc}") from exc

        api_recorder.write("patch_recipe_response", _response_cache_payload(response))
        if response.status_code >= 300:
            raise RuntimeError(f"Mealie returned error {response.status_code}: {response.text[:500]}")

        final_recipe = _parse_recipe_from_response(response)
        context.mealie_payload = final_recipe or patch_payload
        logger.info("Updated the recipe details and added the preparation steps")

        # 6) Bild setzen
        if slug and recipe.assets:
            asset = recipe.assets[0]
            try:
                file_name, mime_type, file_bytes = _data_url_to_file(asset)
            except ValueError as exc:
                logger.warning("Could not process the image: %s", exc)
                return

            extension = file_name.split(".")[-1]
            if _set_recipe_image_via_upload(
                base_url=base_url,
                token=token,
                slug=slug,
                file_bytes=file_bytes,
                mime_type=mime_type,
                extension=extension,
                payload_recorder=api_recorder,
                verify=self._verify,
            ):
                logger.info("Set the feature image for the recipe")
            else:
                logger.warning("Could not set the image as the feature image")

        # 7) Original-PDF als Asset anhängen
        if slug and context.source_pdf and context.source_pdf.suffix.lower() == ".pdf":
            try:
                pdf_bytes = context.source_pdf.read_bytes()
            except OSError as exc:
                logger.warning("Could not read the PDF attachment: %s", exc)
            else:
                pdf_name = context.source_pdf.name
                pdf_title = context.source_pdf.stem
                pdf_info = _upload_asset(
                    base_url=base_url,
                    token=token,
                    slug=slug,
                    file_name=pdf_name,
                    title=pdf_title,
                    mime_type="application/pdf",
                    file_bytes=pdf_bytes,
                    icon="mdi-file-pdf-box",
                    payload_recorder=api_recorder,
                    verify=self._verify,
                )
                if pdf_info:
                    logger.info("Uploaded the original PDF as an attachment")
                else:
                    logger.warning("Could not upload the original PDF as an attachment")


def _parse_recipe_from_response(response: httpx.Response) -> Dict[str, object]:
    try:
        data = response.json()
    except ValueError:
        text = (response.text or "").strip()
        if text:
            logger.debug("Could not read the response as JSON: %s", text[:200])
            return {"rawResponse": text}
        return {}
    if isinstance(data, dict):
        return data

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                return item
        logger.debug("Response list did not contain any objects: %s", str(data)[:200])
        return {"rawResponse": data}

    if isinstance(data, str):
        stripped = data.strip()
        if stripped:
            return {"rawResponse": stripped, "slug": stripped.strip('"')}
        return {}

    logger.debug("Unexpected response format while creating the recipe: %r", data)
    return {}


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


def _build_put_payload(
    initial_recipe: Optional[Dict[str, Any]],
    prepared_payload: Dict[str, Any],
    slug: str,
) -> Dict[str, Any]:
    """Combine server-provided metadata with the locally vorbereiteten Daten."""
    payload: Dict[str, Any] = {}
    if isinstance(initial_recipe, dict):
        payload.update(initial_recipe)

    prepared = dict(prepared_payload)
    payload.update(prepared)
    default_group_id = None
    if isinstance(prepared, dict):
        default_group_id = prepared.get("groupId") or prepared.get("groupID")
    if default_group_id is None and isinstance(initial_recipe, dict):
        default_group_id = initial_recipe.get("groupId") or initial_recipe.get("groupID")
    payload["recipeIngredient"] = _simplify_ingredients(prepared.get("recipeIngredient"))
    if "recipeCategory" in payload:
        payload["recipeCategory"] = _simplify_organizers(payload.get("recipeCategory"), default_group_id)
    if "tags" in payload:
        payload["tags"] = _simplify_organizers(payload.get("tags"), default_group_id)
    payload["slug"] = slug
    payload["recipeInstructions"] = []
    payload.pop("assets", None)

    # Preserve server identifiers if present.
    if isinstance(initial_recipe, dict):
        for key in ("id", "userId", "householdId", "groupId", "name", "slug"):
            if key in initial_recipe:
                payload[key] = initial_recipe[key]
    elif slug:
        payload["slug"] = slug

    payload.setdefault("recipeIngredient", [])
    return payload


def _simplify_ingredients(items: Optional[Any]) -> List[Dict[str, Any]]:
    simplified: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return simplified
    for entry in items:
        if not isinstance(entry, dict):
            continue
        ingredient: Dict[str, Any] = {}
        if "quantity" in entry:
            ingredient["quantity"] = entry["quantity"]
        note = entry.get("note")
        if note:
            ingredient["note"] = note

        unit_raw = entry.get("unit") or {}
        unit: Dict[str, Any] = {}
        if isinstance(unit_raw, dict):
            if unit_raw.get("id"):
                unit["id"] = unit_raw["id"]
            elif entry.get("unitId"):
                unit["id"] = entry["unitId"]
            if unit_raw.get("name"):
                unit["name"] = unit_raw["name"]
        if unit:
            ingredient["unit"] = unit

        food_raw = entry.get("food") or {}
        food: Dict[str, Any] = {}
        if isinstance(food_raw, dict):
            if food_raw.get("id"):
                food["id"] = food_raw["id"]
            elif entry.get("foodId"):
                food["id"] = entry["foodId"]
            if food_raw.get("name"):
                food["name"] = food_raw["name"]
        if food:
            ingredient["food"] = food

        simplified.append(ingredient)
    return simplified


def _simplify_organizers(items: Optional[Any], default_group_id: Optional[Any] = None) -> List[Dict[str, Any]]:
    simplified: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return simplified
    for entry in items:
        if not isinstance(entry, dict):
            continue
        organizer_id = entry.get("id")
        name = entry.get("name")
        if not organizer_id or not name:
            continue
        record: Dict[str, Any] = {
            "id": organizer_id,
            "name": name,
        }
        group_id = entry.get("groupId") or entry.get("groupID") or default_group_id
        if group_id:
            record["groupId"] = group_id
        if entry.get("slug"):
            record["slug"] = entry["slug"]
        simplified.append(record)
    return simplified


_PATCH_BASE_KEYS = {
    "id",
    "userId",
    "householdId",
    "groupId",
    "name",
    "slug",
    "image",
    "recipeServings",
    "recipeYield",
    "recipeYieldQuantity",
    "totalTime",
    "prepTime",
    "cookTime",
    "performTime",
    "description",
    "recipeCategory",
    "tags",
    "tools",
    "notes",
    "orgURL",
    "settings",
    "nutrition",
    "recipeIngredient",
    "assets",
    "rating",
    "extras",
    "comments",
    "dateAdded",
    "dateUpdated",
    "createdAt",
    "updatedAt",
    "lastMade",
}


def _build_patch_payload(
    recipe_after_put: Optional[Dict[str, Any]],
    instructions: Optional[Any],
) -> Dict[str, Any]:
    """Construct the PATCH payload with required Kopf-Informationen und Schritten."""
    payload: Dict[str, Any] = {}
    if isinstance(recipe_after_put, dict):
        payload.update({key: recipe_after_put[key] for key in _PATCH_BASE_KEYS if key in recipe_after_put})
        if "slug" not in payload and recipe_after_put.get("slug"):
            payload["slug"] = recipe_after_put["slug"]

    payload["recipeInstructions"] = instructions or []
    return payload


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
    icon: str = "mdi-image",
    payload_recorder: Optional[ApiPayloadRecorder] = None,
    verify: Union[bool, str] = True,
) -> Optional[Dict[str, object]]:
    endpoint = f"{base_url.rstrip('/')}/api/recipes/{slug}/assets"
    files = {
        "file": (file_name, file_bytes, mime_type),
    }
    data = {
        "name": title,
        "icon": icon,
        "extension": file_name.split(".")[-1],
    }
    headers = {
        "Authorization": f"Bearer {token}",
    }

    if payload_recorder:
        payload_recorder.write(
            "upload_asset_request",
            {
                "slug": slug,
                "data": data,
                "file": {
                    "fileName": file_name,
                    "mimeType": mime_type,
                    "sizeBytes": len(file_bytes),
                },
            },
        )

    try:
        response = httpx.post(
            endpoint,
            headers=headers,
            data=data,
            files=files,
            timeout=60,
            verify=verify,
        )
    except httpx.HTTPError as exc:
        logger.error("Failed to upload the attachment: %s", exc)
        if payload_recorder:
            payload_recorder.write("upload_asset_response_error", {"error": str(exc)})
        return None

    if payload_recorder:
        payload_recorder.write("upload_asset_response", _response_cache_payload(response))

    if response.status_code >= 300:
        logger.error("Attachment upload failed with status %s: %s", response.status_code, response.text[:200])
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
    payload_recorder: Optional[ApiPayloadRecorder] = None,
    verify: Union[bool, str] = True,
) -> bool:
    endpoint = f"{base_url.rstrip('/')}/api/recipes/{slug}/image"
    headers = {
        "Authorization": f"Bearer {token}",
    }
    files = {
        "image": (f"image.{extension}", file_bytes, mime_type),
    }
    data = {"extension": extension}

    if payload_recorder:
        payload_recorder.write(
            "set_feature_image_request",
            {
                "slug": slug,
                "extension": extension,
                "mimeType": mime_type,
                "sizeBytes": len(file_bytes),
            },
        )

    try:
        response = httpx.put(
            endpoint,
            headers=headers,
            data=data,
            files=files,
            timeout=60,
            verify=verify,
        )
    except httpx.HTTPError as exc:
        logger.error("Failed to upload the image: %s", exc)
        if payload_recorder:
            payload_recorder.write("set_feature_image_response_error", {"error": str(exc)})
        return False

    if payload_recorder:
        payload_recorder.write("set_feature_image_response", _response_cache_payload(response))

    if response.status_code >= 300:
        logger.error("Image upload failed with status %s: %s", response.status_code, response.text[:200])
        return False
    return True

    @staticmethod
    def _slugify(value: str) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize("NFKD", value)
        ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
        return slug

    @staticmethod
    def _is_duplicate_slug(slug: str, expected_slug: str) -> bool:
        if not slug or not expected_slug:
            return False
        if slug == expected_slug:
            return False
        if not slug.startswith(f"{expected_slug}-"):
            return False
        suffix = slug[len(expected_slug) + 1 :]
        return suffix.isdigit()

    def _delete_recipe_placeholder(
        self,
        *,
        base_url: str,
        slug: str,
        headers: Dict[str, str],
        api_recorder: ApiPayloadRecorder,
    ) -> None:
        endpoint = f"{base_url}/api/recipes/{slug}"
        api_recorder.write("delete_recipe_request", {"slug": slug})
        try:
            response = httpx.delete(
                endpoint,
                headers=headers,
                timeout=60,
                verify=self._verify,
            )
        except httpx.HTTPError as exc:
            api_recorder.write("delete_recipe_response_error", {"error": str(exc)})
            logger.warning("Could not delete the placeholder recipe %s: %s", slug, exc)
            return

        api_recorder.write("delete_recipe_response", _response_cache_payload(response))
        if response.status_code >= 300:
            logger.warning(
                "Deleting the placeholder recipe %s failed (%s): %s",
                slug,
                response.status_code,
                response.text[:200],
            )
