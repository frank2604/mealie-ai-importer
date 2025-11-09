"""Modules to coordinate user review and apply decisions before committing changes."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..exceptions import UserAbort
from ..models import OrganizerReference
from .context import IngredientRef, PipelineContext

logger = logging.getLogger("Review")


def _prompt_yes_no(message: str, *, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{message} [{suffix}]: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer with y or n.")


class ReviewPromptModule:
    """Pause the pipeline to let the user review and optionally edit proposal files."""

    name = "Review Decisions"

    def run(self, context: PipelineContext) -> None:
        review_paths = [
            ("ingredients", context.food_review_path),
            ("units", context.unit_review_path),
            ("metadata", context.metadata_review_path),
        ]
        for label, path in review_paths:
            if path:
                logger.info("Review %s decisions at %s", label, path)
        if not any(path for _, path in review_paths):
            logger.info("No review files were generated, so we continue without manual confirmation")
            return

        if not _prompt_yes_no("Continue with the current review files?", default=False):
            raise UserAbort("Stopped before applying user decisions")


class ApplyUserDecisionsModule:
    """Apply user edits from the review files before committing to Mealie."""

    name = "Apply User Decisions"

    def run(self, context: PipelineContext) -> None:
        logger.info("Applying user decisions for foods, units, and metadata")
        ingredient_map = self._build_ingredient_map(context)
        self._apply_food_decisions(context, ingredient_map)
        self._apply_unit_decisions(context, ingredient_map)
        self._apply_metadata_decision(context)

    # ------------------------------------------------------------------
    # Helpers for foods
    # ------------------------------------------------------------------
    def _apply_food_decisions(
        self,
        context: PipelineContext,
        ingredient_map: Dict[str, IngredientRef],
    ) -> None:
        review_path = context.food_review_path
        if not review_path or not Path(review_path).exists():
            context.food_decisions = {}
            return

        try:
            payload = json.loads(Path(review_path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Foods review file is not valid JSON (%s): %s", review_path, exc)
            context.food_decisions = {}
            return

        decisions: Dict[str, Dict[str, object]] = {}
        new_matches: Dict[str, str] = dict(context.food_matches)

        items = payload.get("ingredients") or []
        if not isinstance(items, list):
            logger.warning("Foods review file is malformed: 'ingredients' must be a list")
            context.food_decisions = {}
            return

        for item in items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "")
            if not key or key not in ingredient_map:
                continue
            user_decision = item.get("userDecision") or {}
            if not isinstance(user_decision, dict):
                user_decision = {}
            action = str(user_decision.get("action") or "auto").strip().lower()
            use_food_id = user_decision.get("useFoodId")
            create_payload = user_decision.get("create")

            if action == "use_existing" and use_food_id:
                new_matches[key] = str(use_food_id)
                decisions[key] = {
                    "action": "use_existing",
                    "use_food_id": str(use_food_id),
                }
                continue

            if action == "create" and isinstance(create_payload, dict):
                decisions[key] = {
                    "action": "create",
                    "create": {
                        "nameSingular": create_payload.get("nameSingular"),
                        "namePlural": create_payload.get("namePlural"),
                        "aliases": create_payload.get("aliases") or [],
                        "categoryId": create_payload.get("categoryId"),
                        "categoryName": create_payload.get("categoryName"),
                        "description": create_payload.get("description"),
                    },
                }
                continue

            if action == "skip":
                decisions[key] = {"action": "skip"}
                if key in new_matches:
                    new_matches.pop(key, None)
                continue

            # default behaviour: auto (use existing matches or create via automation)
            decisions[key] = {"action": "auto"}

        context.food_decisions = decisions
        context.food_matches = new_matches

        # rebuild missing refs list based on decisions
        missing: List[IngredientRef] = []
        for ref in context.iter_ingredients():
            decision = decisions.get(ref.key, {"action": "auto"})
            action = decision.get("action")
            has_match = ref.key in context.food_matches and context.food_matches[ref.key]
            if action == "use_existing" and has_match:
                continue
            if action == "skip":
                continue
            if action == "create":
                missing.append(ref)
                continue
            if not has_match:
                missing.append(ref)

        context.missing_food_refs = missing

    # ------------------------------------------------------------------
    # Helpers for units
    # ------------------------------------------------------------------
    def _apply_unit_decisions(
        self,
        context: PipelineContext,
        ingredient_map: Dict[str, IngredientRef],
    ) -> None:
        review_path = context.unit_review_path
        if not review_path or not Path(review_path).exists():
            context.unit_decisions = {}
            return

        try:
            payload = json.loads(Path(review_path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Units review file is not valid JSON (%s): %s", review_path, exc)
            context.unit_decisions = {}
            return

        decisions: Dict[str, Dict[str, object]] = {}
        new_matches: Dict[str, str] = dict(context.unit_matches)

        items = payload.get("units") or []
        if not isinstance(items, list):
            logger.warning("Units review file is malformed: 'units' must be a list")
            context.unit_decisions = {}
            return

        for item in items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "")
            if not key or key not in ingredient_map:
                continue
            user_decision = item.get("userDecision") or {}
            if not isinstance(user_decision, dict):
                user_decision = {}
            action = str(user_decision.get("action") or "auto").strip().lower()
            use_unit_id = user_decision.get("useUnitId")
            create_payload = user_decision.get("create")

            if action == "use_existing" and use_unit_id:
                new_matches[key] = str(use_unit_id)
                decisions[key] = {
                    "action": "use_existing",
                    "use_unit_id": str(use_unit_id),
                }
                continue

            if action == "create" and isinstance(create_payload, dict):
                decisions[key] = {
                    "action": "create",
                    "create": {
                        "name": create_payload.get("name"),
                        "pluralName": create_payload.get("pluralName"),
                        "abbreviation": create_payload.get("abbreviation"),
                        "pluralAbbreviation": create_payload.get("pluralAbbreviation"),
                        "useAbbreviation": bool(create_payload.get("useAbbreviation")),
                    },
                }
                continue

            if action == "skip":
                decisions[key] = {"action": "skip"}
                if key in new_matches:
                    new_matches.pop(key, None)
                continue

            decisions[key] = {"action": "auto"}

        context.unit_decisions = decisions
        context.unit_matches = new_matches

        missing: List[IngredientRef] = []
        for ref in context.iter_ingredients():
            if not ref.ingredient.unit:
                continue
            decision = decisions.get(ref.key, {"action": "auto"})
            action = decision.get("action")
            has_match = ref.key in context.unit_matches and context.unit_matches[ref.key]
            if action == "use_existing" and has_match:
                continue
            if action == "skip":
                continue
            if action == "create":
                missing.append(ref)
                continue
            if not has_match:
                missing.append(ref)
        context.missing_unit_refs = missing

    # ------------------------------------------------------------------
    # Helpers for metadata
    # ------------------------------------------------------------------
    def _apply_metadata_decision(self, context: PipelineContext) -> None:
        review_path = context.metadata_review_path
        if not review_path or not Path(review_path).exists():
            context.metadata_decision = {}
            return

        try:
            payload = json.loads(Path(review_path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Metadata review file is not valid JSON (%s): %s", review_path, exc)
            context.metadata_decision = {}
            return

        recipe = context.ensure_recipe()
        user_decision = payload.get("userDecision") or {}
        proposal = payload.get("proposal") or {}
        available = payload.get("available") or {}

        if not isinstance(user_decision, dict):
            user_decision = {}
        if not isinstance(proposal, dict):
            proposal = {}
        if not isinstance(available, dict):
            available = {}

        final = {}

        final["recipeServings"] = user_decision.get("recipeServings", proposal.get("recipeServings"))
        final["totalTime"] = user_decision.get("totalTime", proposal.get("totalTime"))
        final["categoryId"] = user_decision.get("categoryId", proposal.get("categoryId"))
        final["tagIds"] = user_decision.get("tagIds", proposal.get("tagIds") or [])

        categories = {
            item.get("id"): item
            for item in available.get("categories", [])
            if isinstance(item, dict) and item.get("id")
        }

        tags_by_id: Dict[str, Dict[str, object]] = {}
        for group in available.get("tagCategories", []):
            if not isinstance(group, dict):
                continue
            category = group.get("category")
            for tag in group.get("tags") or []:
                if not isinstance(tag, dict):
                    continue
                tag_id = tag.get("id")
                if not tag_id:
                    continue
                tags_by_id[str(tag_id)] = {
                    "id": str(tag_id),
                    "name": tag.get("name"),
                    "groupId": tag.get("groupId") or category,
                    "slug": tag.get("slug"),
                }

        if final.get("recipeServings") is not None:
            try:
                recipe.recipe_servings = float(final["recipeServings"])
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid recipeServings value in metadata decision: %s", final["recipeServings"]
                )

        if final.get("totalTime") is not None:
            value = final.get("totalTime")
            if isinstance(value, str):
                recipe.total_time = value
            elif value is None:
                recipe.total_time = None

        mealie_categories: List[OrganizerReference] = []
        category_id = final.get("categoryId")
        if category_id and category_id in categories:
            category = categories[category_id]
            mealie_categories.append(
                OrganizerReference(
                    id=str(category_id),
                    name=str(category.get("name") or ""),
                    group_id=category.get("groupId"),
                    slug=category.get("slug"),
                )
            )

        mealie_tags: List[OrganizerReference] = []
        for tag_id in final.get("tagIds", []):
            info = tags_by_id.get(str(tag_id))
            if not info:
                continue
            mealie_tags.append(
                OrganizerReference(
                    id=str(info.get("id")),
                    name=str(info.get("name") or ""),
                    group_id=info.get("groupId"),
                    slug=info.get("slug"),
                )
            )

        recipe.metadata.mealie_categories = mealie_categories
        recipe.metadata.mealie_tags = mealie_tags

        context.metadata_decision = final
        context.recipe = recipe
        context.update_recipe_file()

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_ingredient_map(context: PipelineContext) -> Dict[str, IngredientRef]:
        return {ref.key: ref for ref in context.iter_ingredients()}
